"""Outbox and background sender. Every message the vendor should get is saved first, then sent by a background worker.

Sending is SIMULATED unless a mail provider is configured (BREVO_API_KEY and MAIL_FROM) AND the recipient is on MAIL_ALLOWLIST,
so a public copy of this app can never be used to email strangers. The demo vendors' addresses are fake, so they are always simulated.
"""
import json
import os
import threading
import time
import traceback
import urllib.request
from contextlib import closing
from datetime import datetime

import store
from config import ALREADY_REGISTERED, NEEDS_REVIEW, VENDOR_DOCUMENTS, VENDOR_REASONS

MAX_ATTEMPTS, LOOP_SECONDS = 3, 3
HEADLINES = {("Approved", None): "Approved", ("Approved", ALREADY_REGISTERED): "Already registered", ("Pending", NEEDS_REVIEW): "Under review", ("Rejected", None): "Rejected"}
STATUS = {"queued": "Queued", "failed": f"Failed after {MAX_ATTEMPTS} tries", "noaddr": "Not sent: no email address"}


def now():
    return datetime.now().isoformat(timespec="seconds")


def unique(items):
    return list(dict.fromkeys(items))


def decision_mail(run, decision):
    """What the vendor is told when a reviewer decides. Worked out from the findings: the reviewer types nothing, and no internal detail leaks."""
    if decision == "Approved":
        return "Approved", "Your application is approved."
    if decision == "Rejected":
        reasons = unique(VENDOR_REASONS[c] for c in run["codes"] if c in VENDOR_REASONS) or ["we could not verify your information"]
        return "Rejected", "Your application is rejected because " + "; ".join(reasons) + "."
    documents = unique(VENDOR_DOCUMENTS[c] for c in run["codes"] if c in VENDOR_DOCUMENTS) or ["documents that confirm your company's identity and bank details"]
    return "More information needed", ("We need these from you to validate your information and continue with your application:\n"
                                       + "\n".join(f"{i}. {d}" for i, d in enumerate(documents, 1)) + "\nPlease send a new application with them on the Onboard vendor page.")


# ---------------------------------------------------------------- the outbox

def get_run(run_id):
    return next(r for r in store.load_runs() if r["run_id"] == run_id)


def enqueue(conn, run, event, headline, body):
    """Idempotent: one message per (submission, event). One thread per application: Re: after its first mail."""
    root = run["run_id"]
    to = (run["payload"].get("email") or "").strip()
    subject = f"Your vendor application ({root})"
    if conn.execute("SELECT COUNT(*) FROM outbox WHERE thread_id=?", (root,)).fetchone()[0]:
        subject = "Re: " + subject
    conn.execute("INSERT OR IGNORE INTO outbox(thread_id, run_id, event, recipient, subject, body, headline, created, status, attempts) VALUES (?,?,?,?,?,?,?,?,?,0)",
                 (root, run["run_id"], event, to, subject, body, headline, now(), "queued" if to else "noaddr"))


def enqueue_verdict(run_id):
    run = get_run(run_id)
    with closing(store.connect()) as conn, conn:
        enqueue(conn, run, "verdict", HEADLINES[(run["status"], run["sub_status"])], run["decision"]["vendor_message"])


def enqueue_decision(run_id, decision_id):
    run, decision = get_run(run_id), store.query("SELECT decision FROM decisions WHERE id=?", (decision_id,))[0]["decision"]
    headline, body = decision_mail(run, decision)
    with closing(store.connect()) as conn, conn:
        enqueue(conn, run, f"decision:{decision_id}", headline, body)


# ---------------------------------------------------------------- sending

def allowed():
    return {a.strip().lower() for a in os.environ.get("MAIL_ALLOWLIST", "").split(",") if a.strip()}


def real_mail(recipient):
    return bool(os.environ.get("BREVO_API_KEY") and os.environ.get("MAIL_FROM")) and recipient.lower() in allowed()


def transport_name():
    if os.environ.get("BREVO_API_KEY") and os.environ.get("MAIL_FROM"):
        return f"Brevo, for {len(allowed())} allowed address(es). Every other address is simulated."
    return "Simulated: no mail service is set up, so nothing leaves the app."


def brevo_send(row, previous_id):
    payload = {"sender": {"email": os.environ["MAIL_FROM"]}, "to": [{"email": row["recipient"]}], "subject": row["subject"], "textContent": row["body"]}
    if previous_id:  # makes mail programs show it as a reply in the same conversation
        payload["headers"] = {"In-Reply-To": previous_id, "References": previous_id}
    request = urllib.request.Request("https://api.brevo.com/v3/smtp/email", json.dumps(payload).encode("utf-8"),
                                     {"api-key": os.environ["BREVO_API_KEY"], "content-type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as reply:
        return json.load(reply).get("messageId")


def send(row):
    """Returns (transport, provider message id): simulated unless real sending is set up AND this recipient is on the allowed list."""
    if real_mail(row["recipient"]):
        earlier = store.query("SELECT provider_id FROM outbox WHERE thread_id=? AND provider_id IS NOT NULL AND id<? ORDER BY id DESC LIMIT 1", (row["thread_id"], row["id"]))
        return "brevo", brevo_send(row, earlier[0]["provider_id"] if earlier else None)
    return "simulated", None


def deliver_queued():
    for row in store.query("SELECT * FROM outbox WHERE status='queued' ORDER BY id"):
        try:
            transport, provider_id = send(row)
            outcome = ("sent", now(), transport, provider_id, None)
        except Exception as error:  # retried on the next pass, up to MAX_ATTEMPTS
            outcome = ("failed" if row["attempts"] + 1 >= MAX_ATTEMPTS else "queued", None, None, None, f"{type(error).__name__}: {error}")
        with closing(store.connect()) as conn, conn:
            conn.execute("UPDATE outbox SET status=?, sent_at=?, transport=?, provider_id=?, error=?, attempts=attempts+1 WHERE id=?", (*outcome, row["id"]))


# ---------------------------------------------------------------- what the Messages page shows

def status_label(row):
    return STATUS.get(row["status"]) or ("Sent (simulated)" if row["transport"] == "simulated" else "Sent")


def threads():
    """One email thread per application, newest activity first."""
    companies = {r["run_id"]: r["company"] for r in store.query("SELECT run_id, company FROM runs")}
    grouped = {}
    for row in store.query("SELECT * FROM outbox ORDER BY id"):
        thread = grouped.setdefault(row["thread_id"], {"id": row["thread_id"], "company": companies.get(row["thread_id"], ""), "messages": []})
        thread["messages"].append({**row, "label": status_label(row)})
    for thread in grouped.values():
        thread.update(latest=thread["messages"][-1], subject=thread["messages"][0]["subject"], to=thread["messages"][-1]["recipient"] or "(no email given)")
    return sorted(grouped.values(), key=lambda t: t["latest"]["id"], reverse=True)


# ---------------------------------------------------------------- the background worker

_started = False


def start_background():
    """One worker thread: sends what is queued every few seconds."""
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            try:
                deliver_queued()
            except Exception:
                traceback.print_exc()  # a failed pass is simply retried on the next one
            time.sleep(LOOP_SECONDS)

    threading.Thread(target=loop, daemon=True, name="mail-sender").start()
