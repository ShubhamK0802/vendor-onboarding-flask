"""All persistence in one SQLite file (stdlib). Raw submissions stay in the DB; everything shown in the UI is masked."""
import uuid
import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime

from checks import company_key
from config import NEEDS_REVIEW, VENDORS_ON_FILE

DB_PATH = "onboarding.db"
SNAPSHOT_FIELDS = ["company_name", "bank_account_name", "tax_id", "pan", "entity_type", "country", "bank_code", "mobile", "email"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, ts TEXT, company TEXT, country TEXT, status TEXT, sub_status TEXT,
    rule_version TEXT, seconds REAL, decision TEXT, payload TEXT, snapshot TEXT, parent_id TEXT);
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, run_id TEXT, decision TEXT, note TEXT, reviewer TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS docs(run_id TEXT, slot TEXT, filename TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS vendor_ids(company_key TEXT PRIMARY KEY, vendor_id TEXT);
CREATE TABLE IF NOT EXISTS run_vendor(run_id TEXT PRIMARY KEY, vendor_id TEXT);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, thread_id TEXT, run_id TEXT, event TEXT, recipient TEXT, subject TEXT, body TEXT, headline TEXT,
    created TEXT, status TEXT, sent_at TEXT, attempts INTEGER, error TEXT, transport TEXT, provider_id TEXT, UNIQUE(run_id, event));
CREATE TABLE IF NOT EXISTS claims(run_id TEXT PRIMARY KEY, reviewer TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS vendors(company_key TEXT, company_name TEXT, bank_account_number TEXT, mobile TEXT, email TEXT, address TEXT);
"""


def new_vendor_id(country):
    """V + country code + 6 random letters/digits, e.g. VIN7A3D49. Letters and digits only."""
    return "V" + (country if isinstance(country, str) and len(country) == 2 and country.isalpha() and country.isupper() else "XX") + uuid.uuid4().hex[:6].upper()


_lock, _shared = threading.RLock(), {"path": None, "conn": None}


class Handle:
    """What connect() returns: the one shared connection, held by the calling thread until close(). The app is a single process, so all
    database access is serialised here and threads never fight over SQLite's file lock (which failed with 'database is locked' on the host)."""

    def __getattr__(self, name):
        return getattr(_shared["conn"], name)

    def __enter__(self):
        _shared["conn"].__enter__()
        return self

    def __exit__(self, *exc):
        return _shared["conn"].__exit__(*exc)

    def close(self):
        _lock.release()


def connect():
    _lock.acquire()
    try:
        if _shared["path"] != DB_PATH:
            if _shared["conn"]:
                _shared["conn"].close()
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA)
            _shared.update(path=DB_PATH, conn=conn)
        conn = _shared["conn"]
        if not conn.execute("SELECT 1 FROM vendors").fetchone():  # an empty master is re-filled with the vendors that were already on file
            conn.executemany("INSERT INTO vendors VALUES (:company_key, :company_name, :bank_account_number, :mobile, :email, :address)", VENDORS_ON_FILE)
            conn.executemany("INSERT OR IGNORE INTO vendor_ids VALUES (?,?)", [(v["company_key"], new_vendor_id(v["country"])) for v in VENDORS_ON_FILE])
            conn.commit()
        return Handle()
    except BaseException:
        _lock.release()
        raise


def query(sql, args=()):
    with closing(connect()) as conn:
        return [dict(row) for row in conn.execute(sql, args)]


def now():
    return datetime.now().isoformat(timespec="seconds")


def mask_account(number):
    digits = str(number or "")
    return "****" + digits[-4:] if digits else ""


def make_snapshot(submission):
    return {**{f: submission.get(f) for f in SNAPSHOT_FIELDS}, "bank_account_number": mask_account(submission.get("bank_account_number"))}


def save_run(submission, decision, seconds, files=None, same_as=None):
    """files: {slot: (filename, bytes)} - the uploaded documents, kept so a reviewer can open them."""
    run_id, key = uuid.uuid4().hex[:8], company_key(submission)  # random, so nobody can guess another submission's ID
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            run_id, now(), submission.get("company_name"), submission.get("country"), decision["status"], decision["sub_status"],
            decision["rule_version"], round(seconds, 3), json.dumps(decision), json.dumps(submission), json.dumps(make_snapshot(submission)), None))  # parent_id is no longer used: the column stays so existing databases keep working
        conn.executemany("INSERT INTO docs VALUES (?,?,?,?)", [(run_id, slot, name, data) for slot, (name, data) in (files or {}).items()])
        vendor = vendor_for(conn, submission, key, same_as)  # same_as: an earlier run by the same applicant (any status)
        conn.execute("INSERT INTO run_vendor VALUES (?,?)", (run_id, vendor))
        if key:
            conn.execute("INSERT OR IGNORE INTO vendor_ids VALUES (?,?)", (key, vendor))
    return run_id


def vendor_for(conn, submission, key, same_as):
    """Every applicant gets a vendor ID on its first submission. A company already known by its tax identity keeps its ID, and so does a new
    application by the same applicant (even if the tax ID was the typo, or the earlier one was rejected); otherwise a new ID."""
    known = key and conn.execute("SELECT vendor_id FROM vendor_ids WHERE company_key=?", (key,)).fetchone()
    earlier = same_as and conn.execute("SELECT vendor_id FROM run_vendor WHERE run_id=?", (same_as,)).fetchone()
    return (known or earlier or {"vendor_id": new_vendor_id(submission.get("country"))})["vendor_id"]


def save_decision(run_id, decision, note, reviewer):
    with closing(connect()) as conn, conn:
        decision_id = conn.execute("INSERT INTO decisions(run_id, decision, note, reviewer, ts) VALUES (?,?,?,?,?)", (run_id, decision, note, reviewer, now())).lastrowid
        conn.execute("DELETE FROM claims WHERE run_id=?", (run_id,))  # a decided run is nobody's any more
    return decision_id


def claims():
    return {c["run_id"]: c for c in query("SELECT * FROM claims")}


def claim(run_id, reviewer):
    """Take a run so two reviewers do not work on it at once. Returns who already holds it, or None when you now do."""
    with closing(connect()) as conn, conn:
        row = conn.execute("SELECT reviewer FROM claims WHERE run_id=?", (run_id,)).fetchone()
        if row and row["reviewer"].lower() != reviewer.lower():
            return row["reviewer"]
        conn.execute("INSERT OR REPLACE INTO claims VALUES (?,?,?)", (run_id, reviewer, now()))


def release(run_id, reviewer):
    """Give a run back. Only the holder can. Returns who holds it if that is someone else, else None."""
    with closing(connect()) as conn, conn:
        row = conn.execute("SELECT reviewer FROM claims WHERE run_id=?", (run_id,)).fetchone()
        if row and row["reviewer"].lower() != reviewer.lower():
            return row["reviewer"]
        conn.execute("DELETE FROM claims WHERE run_id=?", (run_id,))


def load_decisions():
    return query("SELECT * FROM decisions ORDER BY id")


def get_docs(run_id, with_data=True):
    return query(f"SELECT slot, filename{', data' if with_data else ''} FROM docs WHERE run_id=?", (run_id,))


def reset():
    """Demo only (a real audit trail is never deletable): clears every run and decision, and restores the vendors on file."""
    with closing(connect()) as conn, conn:
        for table in ("runs", "decisions", "docs", "vendors", "claims", "vendor_ids", "run_vendor", "outbox"):
            conn.execute(f"DELETE FROM {table}")


def final_state(run):
    """What a run is NOW, after a reviewer's decision (the rules' own verdict stays in status/sub_status)."""
    d = run["decision_by"]
    if d and d["decision"] in ("Approved", "Rejected"):
        return {"final": d["decision"], "final_sub": f"{d['decision']} by reviewer", "waiting_on": "-"}
    if d:  # information requested: the vendor cannot add to this application, so it is closed and the vendor applies again
        return {"final": "Rejected", "final_sub": "Information needed by reviewer", "waiting_on": "-"}
    if run["status"] == "Pending":
        return {"final": "Pending", "final_sub": run["sub_status"], "waiting_on": "Reviewer"}
    return {"final": run["status"], "final_sub": None, "waiting_on": "-"}


def load_runs():
    """Oldest first. Each run carries its parsed decision, latest reviewer decision, and final state."""
    runs = query("SELECT * FROM runs ORDER BY ts, rowid")
    latest = {d["run_id"]: d for d in load_decisions()}
    vendor_ids = {v["run_id"]: v["vendor_id"] for v in query("SELECT * FROM run_vendor")}
    for run in runs:
        run.update(decision=json.loads(run["decision"]), payload=json.loads(run["payload"]), snapshot=json.loads(run["snapshot"]))
        run["vendor_id"] = vendor_ids.get(run["run_id"], "")
        run["findings"] = run["decision"].get("findings", [])
        run["codes"] = [f["code"] for f in run["findings"]]
        run.update(decision_by=latest.get(run["run_id"]))
        run.update(final_state(run))
        run["decided_by"] = run["decision_by"]["reviewer"] if run["decision_by"] and run["decision_by"]["decision"] in ("Approved", "Rejected") else "Automatic"
    return runs


def known_vendors(runs):
    """What the duplicate check compares against: the vendors on file plus everything finally approved (by the rules or a reviewer)."""
    approved = [{"company_key": company_key(r["payload"]), "company_name": r["company"], "bank_account_number": r["payload"].get("bank_account_number"),
                 "mobile": r["payload"].get("mobile"), "email": r["payload"].get("email"), "address": r["payload"].get("address")} for r in runs if r["final"] == "Approved"]
    return query("SELECT * FROM vendors") + approved
