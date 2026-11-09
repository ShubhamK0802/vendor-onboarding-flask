"""Vendor onboarding checker, Flask edition. Run: python app.py  (or: gunicorn app:app --workers 1 --threads 4)."""
import csv
import hashlib
import io
import os
import threading
import time
import uuid
from datetime import datetime
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # the database and sample_inputs are found next to this file

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for, Response  # noqa: E402
from markupsafe import Markup  # noqa: E402

import mailer  # noqa: E402
import store  # noqa: E402
from config import EVIDENCE_FIELDS, FIELD_LABELS, NEEDS_REVIEW, REASON_LABELS, REJECT_ON_ITS_OWN, RATE_LIMIT_PER_HOUR, RULE_VERSION, VENDOR_ACTION  # noqa: E402
from checks import link_reasons  # noqa: E402
from decide import build_decision, iter_stages, parse_submission  # noqa: E402

app = Flask(__name__)
app.config["RATE_LIMIT"] = RATE_LIMIT_PER_HOUR
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
app.secret_key = os.environ.get("SECRET_KEY", "demo-only-key")  # only signs flash messages; ponytail: no CSRF/auth, this is a demo

STAGE_PAUSE = 0.35  # seconds per check, so the live view is watchable
FIELDS = ["company_name", "country", "email", "mobile", "address", "tax_id", "pan", "bank_account_name", "bank_account_number", "bank_code", "website"]
COUNTRY_NAMES = {"IN": "India", "US": "United States", "DE": "Germany", "Other": "Other (not supported yet)"}
COUNTRY = list(COUNTRY_NAMES)
DOC_SLOTS = {"tax_document": "Tax document (GST certificate, W-9 or German VAT registration)", "registration": "Registration document",
             "voided_cheque": "Voided cheque", "passbook": "Passbook page (alternative to a voided cheque)"}
LEVELS = {1: "Vendor can fix", 2: "Needs review", 3: "Contradiction"}
COLOR = {"Approved": "green", "Pending": "orange", "Rejected": "red"}
SAMPLE_HINTS = {"01_approved_india_clean.json": "submit it twice to see 'already registered'", "06_edge_existing_vendor_changes_bank_account.json": "submit 01 first"}
SEEN = defaultdict(list)  # source -> times of its recent submissions (rate limit). ponytail: in memory, like PROGRESS
PROGRESS = {}  # token -> live progress of one run. ponytail: in-memory, so one worker process; use the database if it must scale out
HIGH_RISK_BANK_CODES = {"BANK_DETAILS_CHANGED", "DUPLICATE_BANK_ACCOUNT"}
VERIFICATION_METHODS = {"known_contact": "Callback to a trusted contact", "bank_confirmation": "Independent bank confirmation"}


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


SUBMITTED_FIELDS = [("company_name", "Company name"), ("country", "Country"), ("tax_id", "Tax ID"), ("pan", "PAN"),
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


def current_vendor_message(run):
    if run["decision_by"]:
        return mailer.decision_mail(run, run["decision_by"]["decision"])[1]
    return run["decision"]["vendor_message"]


def effect(finding):
    """What a finding does to the run, in words (a lone contradiction is fixable; two at once reject)."""
    return "Rejects the application" if finding["code"] in REJECT_ON_ITS_OWN else LEVELS[finding["level"]]


def age(run):
    minutes = int((datetime.now() - datetime.fromisoformat(run["ts"])).total_seconds() // 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h" if minutes < 2880 else f"{minutes // 1440} days"


app.jinja_env.globals.update(submitted=submitted, effect=effect, badge=badge, reasons=reasons, vendor_entered=vendor_entered, outcome=outcome, system_verdict=system_verdict,
                             current_vendor_message=current_vendor_message,
                             levels=LEVELS, reason_labels=REASON_LABELS, doc_slots=DOC_SLOTS, docs_for=lambda rid: store.get_docs(rid, with_data=False),
                             rule_version=RULE_VERSION, high_risk_bank_codes=HIGH_RISK_BANK_CODES, verification_methods=VERIFICATION_METHODS)


NAV = {"version": -1, "at": 0.0, "count": 0}  # the reviewer-queue badge: counted at most every few seconds, not on every page


def load_runs_and_badge():
    """All runs, and the reviewer-queue badge counted from the same load (so rendering the next page needs no second query)."""
    runs = store.load_runs()
    NAV.update(version=store.version(), at=time.time(), count=sum(r["waiting_on"] == "Reviewer" for r in runs))
    return runs


@app.context_processor
def nav_counts():
    if NAV["version"] != store.version() or time.time() - NAV["at"] > 5:
        load_runs_and_badge()
    return {"n_reviewer": NAV["count"]}


def get_run(run_id):
    return next((r for r in store.load_runs() if r["run_id"] == run_id), None)


def sample_files():
    return sorted(n for n in os.listdir("sample_inputs") if n.endswith(".json"))


# ---------------------------------------------------------------- submit + live run view

@app.get("/")
def submit_page():
    return render_submit()


def render_submit(prefill=None, correction=None):
    samples = [(n, n[:-5].replace("_", " ") + (f"  ({SAMPLE_HINTS[n]})" if n in SAMPLE_HINTS else "")) for n in sample_files()]
    return render_template("submit.html", samples=samples, country=COUNTRY, names=COUNTRY_NAMES,
                           prefill=prefill or {}, correction=correction)


@app.get("/correct/<run_id>")
def correct_application(run_id):
    run = get_run(run_id)
    if not run:
        abort(404)
    if run["waiting_on"] != "Vendor":
        flash("This application is not waiting for corrections.", "error")
        return redirect(url_for("submit_page"))
    return render_submit(run["payload"], run)


def form_submission(existing=None):
    documents, files = {}, {}
    stored = {d["slot"]: d for d in store.get_docs(existing["run_id"]) } if existing else {}
    earlier = (existing["payload"].get("documents") or {}) if existing else {}
    for slot in DOC_SLOTS:
        upload = request.files.get(slot)
        if upload and upload.filename:
            data = upload.read()
            extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
            signature_valid = (extension == "pdf" and data.startswith(b"%PDF-")) or (extension == "png" and data.startswith(b"\x89PNG\r\n\x1a\n")) \
                              or (extension in ("jpg", "jpeg") and data.startswith(b"\xff\xd8\xff"))
            files[slot] = (upload.filename, data)
            documents[slot] = {"filename": upload.filename, "file_type": extension,
                               "size_bytes": len(data), "declared_type": slot, "signature_valid": signature_valid,
                               "sha256": hashlib.sha256(data).hexdigest()}  # the hash spots a re-used file
        elif earlier.get(slot):
            documents[slot] = earlier[slot]
            if slot in stored:
                files[slot] = (stored[slot]["filename"], stored[slot]["data"])
        else:
            documents[slot] = None
    return {**{f: request.form.get(f, "") for f in FIELDS}, "documents": documents}, files


def worker(token, submission, files, parent_id=None):
    progress = PROGRESS[token]
    try:
        history = store.load_runs()
        known, stages, started = store.known_vendors(history), [], time.perf_counter()
        pause = 0 if os.environ.get("VERCEL") else STAGE_PAUSE
        for stage in iter_stages(submission, known, history):
            stages.append(stage)
            if stage["stage"] == "repeat_attempts":  # an internal control for staff: recorded, but never shown to the vendor
                continue
            progress["stages"].append({"name": stage["stage"].replace("_", " "), "status": stage["status"],
                                       "detail": stage.get("note") or (f"{len(stage['findings'])} found" if stage["findings"] else "")})
            time.sleep(pause)
        seconds = max(time.perf_counter() - started - pause * len(stages), 0)
        # The same applicant keeps one vendor ID across attempts, even when the tax ID was the thing that was wrong or the earlier attempt was rejected.
        # Only strong links count here (a shared name or file is a hint for the reviewer, not proof of identity).
        same_as = parent_id or next((r["run_id"] for r in reversed(history) if {"company ID", "bank account", "phone", "email"} & set(link_reasons(submission, r))), None)
        progress["run_id"] = store.save_run(submission, build_decision(stages), seconds, files=files, same_as=same_as, parent_id=parent_id)
        run = next(r for r in load_runs_and_badge() if r["run_id"] == progress["run_id"])
        mailer.enqueue_verdict(progress["run_id"], run)  # the vendor is told the verdict; a background worker sends it
    except Exception as error:  # never leave the page spinning
        progress["error"] = f"Something went wrong: {error}"
        run = None
    progress["done"] = True
    return run


def too_many():
    """True when this source (IP address) has sent too many submissions this hour: stops fast trial and error."""
    source = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    now = time.time()
    recent = [t for t in SEEN[source] if now - t < 3600]
    SEEN[source] = recent + [now]
    return len(recent) >= app.config["RATE_LIMIT"]


@app.post("/api/submit")
def api_submit():
    if too_many():
        return jsonify(error="Too many submissions from your network in the last hour. Please try again later."), 429
    mode, files = request.form.get("mode"), None
    revision = get_run(request.form.get("revision_of")) if request.form.get("revision_of") else None
    if request.form.get("revision_of") and (not revision or revision["waiting_on"] != "Vendor"):
        return jsonify(error="This application is not waiting for corrections"), 400
    if mode == "sample":
        name = request.form.get("sample")
        if not name:
            return jsonify(error="Select a sample or choose a JSON file first"), 400
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
        (submission, files), error = form_submission(revision), None
    if error:
        return jsonify(error=error), 400
    token = uuid.uuid4().hex[:10]
    if len(PROGRESS) > 200:
        PROGRESS.pop(next(iter(PROGRESS)))
    PROGRESS[token] = {"stages": [], "done": False, "run_id": None, "error": None}
    parent_id = (revision["application_id"] if revision else None)
    if os.environ.get("VERCEL"):
        run = worker(token, submission, files, parent_id)
        progress = PROGRESS[token]
        result_html = render_template("_run.html", run=run, vendor_view=True) if run else ""
        return jsonify(token=token, progress=progress, result_html=result_html)
    threading.Thread(target=worker, args=(token, submission, files, parent_id), daemon=True).start()
    return jsonify(token=token)


@app.get("/api/progress/<token>")
def api_progress(token):
    return jsonify(PROGRESS.get(token) or {"stages": [], "done": True, "run_id": None, "error": "Unknown submission"})


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
    """A reviewer can decide the runs the rules sent to them."""
    return bool(run) and run["final"] == "Pending" and run["waiting_on"] == "Reviewer"


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
    picked = next((r for r in queue if r["run_id"] == request.args.get("run")), queue[0] if queue else None)
    return render_template("review.html", queue=queue, everyone=everyone, picked=picked,
                           decisions=list(reversed(store.load_decisions())),
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
    verification_method = request.form.get("verification_method", "")
    run, back = get_run(run_id), back_args(request.form)
    holder = store.claims().get(run_id)
    if not reviewable(run):
        flash("That submission is no longer waiting for a reviewer.", "error")
    elif not reviewer or not note:
        flash("Please enter your name and a reason. Every decision needs both.", "error")
        return redirect(url_for("review_page", run=run_id, **back))
    elif not holder:
        flash("Take this submission before deciding it.", "error")
        return redirect(url_for("review_page", run=run_id, **back))
    elif holder["reviewer"].lower() != reviewer.lower():
        flash(f"{holder['reviewer']} is handling this submission, so you cannot decide it. Ask them to release it.", "error")
        return redirect(url_for("review_page", run=run_id, **back))
    elif decision not in ("Approved", "Rejected", "Info requested"):
        flash("Unknown decision.", "error")
    elif decision == "Approved" and HIGH_RISK_BANK_CODES.intersection(run["codes"]) and verification_method not in VERIFICATION_METHODS:
        flash("Record an independent verification method before approving this bank-risk case.", "error")
        return redirect(url_for("review_page", run=run_id, **back))
    else:
        if decision == "Approved" and verification_method in VERIFICATION_METHODS:
            note = f"Independent verification: {VERIFICATION_METHODS[verification_method]}. {note}"
        mailer.enqueue_decision(run_id, store.save_decision(run_id, decision, note, reviewer))  # and told the outcome, in the same thread
        flash(f"{run['company']}: {decision} by {reviewer}.", "ok")
    return redirect(url_for("review_page", **back))  # opens the next one in the same order


# ---------------------------------------------------------------- dashboard

@app.get("/dashboard")
def dashboard():
    runs = store.load_runs()
    current = [r for r in runs if not r["superseded_by"]]
    total = len(current)
    pct = lambda n: f"{n / total:.0%}" if total else "0%"
    count = lambda **kw: sum(all(r[k] == v for k, v in kw.items()) for r in current)
    handled = sum(r["sub_status"] != NEEDS_REVIEW for r in current)
    metrics = [("Sorted without a reviewer", handled, pct(handled), "The rules approved, rejected or returned it with a clear next step"),
               ("Approved automatically", count(final="Approved", decided_by="Automatic"), pct(count(final="Approved", decided_by="Automatic")), "The rules approved it with no human involved"),
               ("Vendor action required", count(final_sub=VENDOR_ACTION), pct(count(final_sub=VENDOR_ACTION)), "The application stays open while the vendor corrects it"),
               ("Sent to a reviewer", count(sub_status=NEEDS_REVIEW), pct(count(sub_status=NEEDS_REVIEW)), "The rules could not decide, so a reviewer must"),
               ("Rejected", count(final="Rejected"), pct(count(final="Rejected")), "A terminal rule or reviewer decision stopped the application")]
    show = request.args.get("show", "All")
    history = [r for r in reversed(runs) if show in ("All", r["final"])]
    return render_template("dashboard.html", runs=runs, total=total, submissions=len(runs), metrics=metrics, show=show, history=history,
                           with_reviewer=count(waiting_on="Reviewer"),
                           outcomes=Counter(outcome(r) for r in current).most_common(),
                           top=Counter(c for r in current for c in set(r["codes"])).most_common(),
                           picked=next((r for r in runs if r["run_id"] == request.args.get("run")), None))


@app.get("/messages")
def messages_page():
    return render_template("messages.html", threads=mailer.threads(), transport=mailer.transport_name())


@app.get("/export.csv")
def export_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["submission id", "vendor id", "submitted at", "company", "country", "status now", "automatic verdict", "decided by", "reasons"])
    for r in store.load_runs():
        writer.writerow([r["run_id"], r["vendor_id"], r["ts"], r["company"], r["country"], outcome(r), system_verdict(r), r["decided_by"], reasons(r)])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=vendor_onboarding_history.csv"})


@app.get("/about")
def about():
    return render_template("about.html")


@app.post("/reset")
def reset():
    store.reset()
    PROGRESS.clear()
    SEEN.clear()
    flash("Demo data cleared: no submissions, no decisions. The vendors already on file were restored.", "ok")
    return redirect(url_for("submit_page"))


@app.before_request
def start_timing():
    store.timing_reset()


@app.after_request
def server_timing(response):
    """What the database cost this request, in the standard Server-Timing header (visible in the browser's network tab). Shows where time goes on a remote database."""
    t = store.TIMING
    response.headers["Server-Timing"] = (f'db;dur={t["ms"]:.0f};desc="{t["n"]} statements, slowest {t["slowest"][0]} {t["slowest"][1]:.0f}ms", '
                                         f'commit;dur={t["commit_ms"]:.0f}, connect;dur={t["connect_ms"]:.0f}')
    return response


@app.before_request
def start_mail_worker():
    """Started on the first request, not at import: if the host forks the app after import, a thread started earlier is gone in the child while the
    lock it held stays locked for ever (the app then hangs). The tests switch the worker off and drive the sender by hand."""
    if not os.environ.get("VERCEL") and os.environ.get("MAIL_WORKER", "1") == "1":
        mailer.start_background()  # does nothing after the first call


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
