"""Vendor onboarding checker, Flask edition. Run: python app.py  (or: gunicorn app:app --workers 1 --threads 4)."""
import csv
import io
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from collections import Counter

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # the database and sample_inputs are found next to this file

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for, Response  # noqa: E402
from markupsafe import Markup, escape  # noqa: E402

import store  # noqa: E402
from config import EVIDENCE_FIELDS, FIELD_LABELS, FIX_DEADLINE_DAYS, NEEDS_REVIEW, REASON_LABELS, REJECT_ON_ITS_OWN, REMINDER_DAYS, RULE_VERSION, VENDOR_DOCUMENTS, VENDOR_REASONS, VENDOR_TO_FIX  # noqa: E402
from decide import build_decision, iter_stages, parse_submission  # noqa: E402

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-only-key")  # only signs flash messages; ponytail: no CSRF/auth, this is a demo

STAGE_PAUSE = 0.35  # seconds per check, so the live view is watchable
FIELDS = ["company_name", "entity_type", "country", "email", "mobile", "address", "tax_id", "pan", "bank_account_name", "bank_account_number", "bank_code", "website"]
COUNTRY_NAMES = {"IN": "India", "US": "United States", "DE": "Germany", "Other": "Other (not supported yet)"}
ENTITY, COUNTRY = ["company", "llp", "partnership", "sole_proprietor", "trust"], list(COUNTRY_NAMES)
DOC_SLOTS = {"tax_document": "Tax document (GST certificate, W-9 or German VAT registration)", "registration": "Registration document",
             "voided_cheque": "Voided cheque", "passbook": "Passbook page (alternative to a voided cheque)"}
LEVELS = {1: "Vendor can fix", 2: "Needs review", 3: "Contradiction"}
COLOR = {"Approved": "green", "Pending": "orange", "Rejected": "red", "Replaced": "gray"}
SAMPLE_HINTS = {"04_edge_name_nearly_matches_bank_account.json": "submit twice, the 2nd as a resubmission", "06_edge_existing_vendor_changes_bank_account.json": "submit 01 first"}
PROGRESS = {}  # token -> live progress of one run. ponytail: in-memory, so one worker process; use the database if it must scale out


# ---------------------------------------------------------------- template helpers

def badge(final, sub=None):
    return Markup('<span class="badge {}">{}</span>').format(COLOR[final], f"{final}: {sub}" if sub else final)


def reasons(run):
    return ", ".join(REASON_LABELS.get(c, c) for c in sorted(set(run["codes"]))) or "None"


def vendor_entered(run):
    shown, lines = set(), []
    for code in sorted(set(run["codes"])):
        for field in EVIDENCE_FIELDS.get(code, []):
            if field not in shown and run["snapshot"].get(field):
                shown.add(field)
                lines.append(f"{FIELD_LABELS[field]}: {run['snapshot'][field]}")
    return " | ".join(lines)


SUBMITTED_FIELDS = [("company_name", "Company name"), ("entity_type", "Entity type"), ("country", "Country"), ("tax_id", "Tax ID"), ("pan", "PAN"),
                    ("address", "Address"), ("email", "Email"), ("mobile", "Mobile"), ("website", "Website"),
                    ("bank_account_name", "Bank account holder"), ("bank_account_number", "Bank account"), ("bank_code", "Bank code")]


def submitted(run):
    """Everything the vendor sent, as a reviewer needs to read it. The bank account is masked, as everywhere. Fields a finding points at are flagged."""
    payload = run["payload"]
    flagged = {field for code in set(run["codes"]) for field in EVIDENCE_FIELDS.get(code, [])}
    fields = []
    for key, label in SUBMITTED_FIELDS:
        value = payload.get(key)
        if key == "bank_account_number":
            value = store.mask_account(value)
        elif key == "country":
            value = f"{value} ({COUNTRY_NAMES[value]})" if value in COUNTRY_NAMES else value
        fields.append((label, str(value).strip() if value not in (None, "") else "", key in flagged))
    stored = {d["slot"] for d in store.get_docs(run["run_id"], with_data=False)}
    documents = []
    for slot, label in DOC_SLOTS.items():
        doc = (payload.get("documents") or {}).get(slot)
        doc = doc if isinstance(doc, dict) else None
        documents.append({"slot": slot, "label": label, "file": doc.get("filename") if doc else None, "type": doc.get("file_type") if doc else None,
                          "size": f"{doc['size_bytes'] / 1024:.0f} KB" if doc and doc.get("size_bytes") else None, "stored": slot in stored})
    return {"fields": fields, "documents": documents}


def outcome(run):
    return f"{run['final']}: {run['final_sub']}" if run["final_sub"] else run["final"]


def system_verdict(run):
    return f"{run['status']}: {run['sub_status']}" if run["sub_status"] else run["status"]


def effect(finding):
    """What a finding does to the run, in words (a lone contradiction is fixable; two at once reject)."""
    return "Rejects the application" if finding["code"] in REJECT_ON_ITS_OWN else LEVELS[finding["level"]]


def age(run):
    minutes = int((datetime.now() - datetime.fromisoformat(run["ts"])).total_seconds() // 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h" if minutes < 2880 else f"{minutes // 1440} days"


app.jinja_env.globals.update(reminder_days=REMINDER_DAYS, submitted=submitted, effect=effect, badge=badge, reasons=reasons, vendor_entered=vendor_entered, outcome=outcome, system_verdict=system_verdict,
                             levels=LEVELS, reason_labels=REASON_LABELS, doc_slots=DOC_SLOTS, docs_for=lambda rid: store.get_docs(rid, with_data=False),
                             rule_version=RULE_VERSION, fix_deadline_days=FIX_DEADLINE_DAYS)


@app.context_processor
def nav_counts():
    runs = store.load_runs()
    return {"n_reviewer": sum(r["waiting_on"] == "Reviewer" for r in runs), "n_vendor": sum(r["waiting_on"] == "Vendor" for r in runs)}


def get_run(run_id):
    return next((r for r in store.load_runs() if r["run_id"] == run_id), None)


def sample_files():
    return sorted(n for n in os.listdir("sample_inputs") if n.endswith(".json"))


# ---------------------------------------------------------------- submit + live run view

@app.get("/")
def submit_page():
    waiting = [r for r in store.load_runs() if r["waiting_on"] == "Vendor"]
    samples = [(n, n[:-5].replace("_", " ") + (f"  ({SAMPLE_HINTS[n]})" if n in SAMPLE_HINTS else "")) for n in sample_files()]
    return render_template("submit.html", waiting=waiting, samples=samples, entity=ENTITY, country=COUNTRY, names=COUNTRY_NAMES)


def form_submission():
    documents, files = {}, {}
    for slot in DOC_SLOTS:
        upload = request.files.get(slot)
        if upload and upload.filename:
            data = upload.read()
            files[slot] = (upload.filename, data)
            documents[slot] = {"filename": upload.filename, "file_type": upload.filename.rsplit(".", 1)[-1] if "." in upload.filename else "",
                               "size_bytes": len(data), "declared_type": slot}
        else:
            documents[slot] = None
    return {**{f: request.form.get(f, "") for f in FIELDS}, "documents": documents}, files


def worker(token, submission, files, parent_id, previous):
    progress = PROGRESS[token]
    try:
        known, stages, started = store.known_vendors(store.load_runs()), [], time.perf_counter()
        for stage in iter_stages(submission, known):
            stages.append(stage)
            progress["stages"].append({"name": stage["stage"].replace("_", " "), "status": stage["status"],
                                       "detail": stage.get("note") or (f"{len(stage['findings'])} found" if stage["findings"] else "")})
            time.sleep(STAGE_PAUSE)
        seconds = max(time.perf_counter() - started - STAGE_PAUSE * len(stages), 0)
        progress["run_id"] = store.save_run(submission, build_decision(stages, previous), seconds, parent_id=parent_id, files=files)
    except Exception as error:  # never leave the page spinning
        progress["error"] = f"Something went wrong: {error}"
    progress["done"] = True


@app.post("/api/submit")
def api_submit():
    mode, files = request.form.get("mode"), None
    if mode == "sample":
        name = request.form.get("sample")
        if name not in sample_files():  # only files from the sample folder, never a path from the browser
            return jsonify(error="Unknown sample"), 400
        with open(f"sample_inputs/{name}") as handle:
            submission, error = parse_submission(handle.read())
    elif mode == "json":
        upload = request.files.get("json_file")
        if not upload or not upload.filename:
            return jsonify(error="Choose a JSON file first"), 400
        submission, error = parse_submission(upload.read().decode("utf-8", errors="replace"))
    else:
        (submission, files), error = form_submission(), None
    if error:
        return jsonify(error=error), 400
    parent = request.form.get("parent") or None
    earlier = next((r for r in store.load_runs() if r["run_id"] == parent and r["waiting_on"] == "Vendor"), None)
    parent = earlier["run_id"] if earlier else None
    previous = [(f["code"], f["message"]) for f in earlier["findings"]] if earlier else []  # what this vendor was already asked to fix
    token = uuid.uuid4().hex[:10]
    if len(PROGRESS) > 200:
        PROGRESS.pop(next(iter(PROGRESS)))
    PROGRESS[token] = {"stages": [], "done": False, "run_id": None, "error": None}
    threading.Thread(target=worker, args=(token, submission, files, parent, previous), daemon=True).start()
    return jsonify(token=token)


@app.get("/api/progress/<token>")
def api_progress(token):
    return jsonify(PROGRESS.get(token) or {"stages": [], "done": True, "run_id": None, "error": "Unknown submission"})


@app.get("/api/prefill/<run_id>")
def api_prefill(run_id):
    """What a vendor corrects on resubmission. The bank account number is NOT sent back: they re-enter it."""
    run = get_run(run_id)
    if not run:
        abort(404)
    values = {f: run["payload"].get(f) or "" for f in FIELDS if f != "bank_account_number"}
    values["country"] = values["country"] if values["country"] in COUNTRY else "Other"
    values["entity_type"] = values["entity_type"] if values["entity_type"] in ENTITY else ENTITY[0]
    return jsonify(values)


@app.get("/run/<run_id>")
def run_partial(run_id):
    run = get_run(run_id)
    if not run:
        abort(404)
    return render_template("_run.html", run=run, vendor_view=True)


@app.get("/doc/<run_id>/<slot>")
def download_doc(run_id, slot):
    doc = next((d for d in store.get_docs(run_id) if d["slot"] == slot), None)
    if not doc:
        abort(404)
    return send_file(io.BytesIO(doc["data"]), download_name=doc["filename"], as_attachment=True)


# ---------------------------------------------------------------- reviewer desk

SORTS = {"oldest": "Oldest first", "newest": "Newest first"}
SORT_KEYS = {"oldest": lambda r: r["seq"], "newest": lambda r: -r["seq"]}  # seq = arrival order, so runs in the same second still sort


def reviewable(run):
    """A reviewer can decide runs the rules sent to them, and runs where they asked the vendor for more information."""
    return bool(run) and run["final"] == "Pending" and (run["waiting_on"] == "Reviewer" or bool(run["decision_by"]))


def back_args(source):
    return {k: source[k] for k in ("sort", "q") if source.get(k)}


@app.get("/review")
def review_page():
    held = store.claims()
    runs = store.load_runs()
    for seq, r in enumerate(runs):
        r.update(seq=seq, age=age(r), claimed_by=held.get(r["run_id"], {}).get("reviewer"))
    sort = request.args.get("sort") if request.args.get("sort") in SORTS else "oldest"
    text = request.args.get("q", "").strip().lower()
    everyone = [r for r in runs if r["waiting_on"] == "Reviewer"]
    queue = sorted([r for r in everyone if text in f"{r['company']} {r['run_id']}".lower()],
                   key=SORT_KEYS[sort])
    info_waiting = [r for r in runs if reviewable(r) and r["waiting_on"] == "Vendor"]
    picked = next((r for r in queue + info_waiting if r["run_id"] == request.args.get("run")), queue[0] if queue else None)
    return render_template("review.html", queue=queue, everyone=everyone, picked=picked,
                           info_waiting=info_waiting, waiting=[r for r in runs if r["waiting_on"] == "Vendor"], decisions=list(reversed(store.load_decisions())),
                           sorts=SORTS, sort=sort, q=request.args.get("q", ""), args={"sort": sort, "q": request.args.get("q", "")})


@app.post("/review/<run_id>/claim")
def review_claim(run_id):
    reviewer = request.form.get("reviewer", "").strip()
    if not reviewer:
        flash("Enter your name first, then take the submission.", "error")
    elif holder := store.claim(run_id, reviewer):
        flash(f"{holder} is already handling this submission.", "error")
    else:
        flash("You are handling this submission. Other reviewers can see it is taken.", "ok")
    return redirect(url_for("review_page", run=run_id, **back_args(request.form)))


@app.post("/review/<run_id>/release")
def review_release(run_id):
    reviewer = request.form.get("reviewer", "").strip()
    if holder := store.release(run_id, reviewer):
        flash(f"Only {holder} can give this one back.", "error")
    else:
        flash("Released: any reviewer can take it now.", "ok")
    return redirect(url_for("review_page", run=run_id, **back_args(request.form)))


@app.post("/review/<run_id>")
def review_decision(run_id):
    reviewer, note, decision = request.form.get("reviewer", "").strip(), request.form.get("note", "").strip(), request.form.get("decision")
    run, back = get_run(run_id), back_args(request.form)
    holder = store.claims().get(run_id)
    if not reviewable(run):
        flash("That submission is no longer waiting for a reviewer.", "error")
    elif not reviewer or not note:
        flash("Please enter your name and a reason. Every decision needs both.", "error")
        return redirect(url_for("review_page", run=run_id, **back))
    elif holder and holder["reviewer"].lower() != reviewer.lower():
        flash(f"{holder['reviewer']} is handling this submission, so you cannot decide it. Ask them to release it.", "error")
        return redirect(url_for("review_page", run=run_id, **back))
    elif decision not in ("Approved", "Rejected", "Info requested"):
        flash("Unknown decision.", "error")
    else:
        store.save_decision(run_id, decision, note, reviewer)
        flash(f"{run['company']}: {decision} by {reviewer}.", "ok")
    return redirect(url_for("review_page", **back))  # opens the next one in the same order


# ---------------------------------------------------------------- dashboard

@app.get("/dashboard")
def dashboard():
    runs = store.load_runs()
    total = len(runs)
    pct = lambda n: f"{n / total:.0%}" if total else "0%"
    count = lambda **kw: sum(all(r[k] == v for k, v in kw.items()) for r in runs)
    handled = sum(r["sub_status"] != NEEDS_REVIEW for r in runs)
    metrics = [("Handled without a human", handled, pct(handled), "Approved, sent back to the vendor, or rejected by the rules alone"),
               ("Approved automatically", count(status="Approved"), pct(count(status="Approved")), "The rules approved it with no human involved"),
               ("Sent to a reviewer", count(sub_status=NEEDS_REVIEW), pct(count(sub_status=NEEDS_REVIEW)), "The rules could not decide, so a reviewer must"),
               ("Sent back to vendor", count(sub_status=VENDOR_TO_FIX), pct(count(sub_status=VENDOR_TO_FIX)), "The vendor can fix it and resubmit"),
               ("Rejected", count(status="Rejected"), pct(count(status="Rejected")), "Identity red flags; not onboarded")]
    live = [r for r in runs if r["final"] != "Replaced"]
    show = request.args.get("show", "All")
    history = [r for r in reversed(runs) if show in ("All", r["final"])]
    return render_template("dashboard.html", runs=runs, total=total, metrics=metrics, show=show, history=history,
                           with_reviewer=count(waiting_on="Reviewer"), with_vendor=count(waiting_on="Vendor"),
                           outcomes=Counter(outcome(r) for r in live).most_common(),
                           top=Counter(c for r in runs for c in set(r["codes"])).most_common(),
                           picked=next((r for r in runs if r["run_id"] == request.args.get("run")), None))


VERDICT_HEADLINES = {("Approved", None): "Approved", ("Pending", NEEDS_REVIEW): "Under review", ("Pending", VENDOR_TO_FIX): "Action needed", ("Rejected", None): "Rejected"}


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
                                       + "\n".join(f"{i}. {d}" for i, d in enumerate(documents, 1)) + "\nPlease resubmit with them on the Onboard vendor page.")


def vendor_messages(runs):
    """One email thread per application (a corrected resubmission stays in its thread), newest first. SIMULATED: nothing is emailed."""
    by_id = {r["run_id"]: r for r in runs}

    def root(run):
        while run["parent_id"] in by_id:
            run = by_id[run["parent_id"]]
        return run["run_id"]

    threads = {}

    def add(run, when, headline, body):
        thread = threads.setdefault(root(run), {"id": root(run), "company": run["company"], "to": "", "messages": []})
        thread["to"] = run["payload"].get("email") or thread["to"]
        thread["messages"].append({"when": when, "headline": headline, "body": body, "run_id": run["run_id"]})

    for r in runs:
        add(r, r["ts"], VERDICT_HEADLINES[(r["status"], r["sub_status"])], r["decision"]["vendor_message"])
        d, latest = r["decision_by"], r["decision"]["vendor_message"]
        if d:
            headline, latest = decision_mail(r, d["decision"])
            add(r, d["ts"], headline, latest)
        since = datetime.fromisoformat((d or r)["ts"])
        if r["final"] == "Rejected" and (r["final_sub"] or "").startswith("Closed"):
            add(r, (since + timedelta(days=FIX_DEADLINE_DAYS)).isoformat(timespec="seconds"), "Rejected",
                f"Your application is rejected because we did not hear back within {FIX_DEADLINE_DAYS} days. If this was a mistake, submit a new application.")
        elif r["waiting_on"] == "Vendor" and datetime.now() >= since + timedelta(days=REMINDER_DAYS):
            add(r, (since + timedelta(days=REMINDER_DAYS)).isoformat(timespec="seconds"), "Reminder", "Reminder: your application is still waiting for you.\n" + latest)
    for thread in threads.values():
        thread["messages"].sort(key=lambda m: m["when"])
        subject = f"Your vendor application ({thread['id']})"
        for number, mail in enumerate(thread["messages"]):
            mail["subject"] = subject if number == 0 else "Re: " + subject
        thread.update(subject=subject, to=thread["to"] or "(no email given)", latest=thread["messages"][-1])
    return sorted(threads.values(), key=lambda t: t["latest"]["when"], reverse=True)


@app.get("/messages")
def messages_page():
    return render_template("messages.html", threads=vendor_messages(store.load_runs()), fix_deadline_days=FIX_DEADLINE_DAYS)


@app.get("/export.csv")
def export_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["submission id", "vendor id", "submitted at", "company", "country", "status now", "automatic verdict", "decided by", "reasons", "resubmission of"])
    for r in store.load_runs():
        writer.writerow([r["run_id"], r["vendor_id"], r["ts"], r["company"], r["country"], outcome(r), system_verdict(r), r["decided_by"], reasons(r), r["parent_id"] or ""])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=vendor_onboarding_history.csv"})


@app.get("/about")
def about():
    return render_template("about.html")


@app.post("/reset")
def reset():
    store.reset()
    PROGRESS.clear()
    flash("Demo data cleared: no submissions, no decisions. The vendors already on file were restored.", "ok")
    return redirect(url_for("submit_page"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
