"""Application persistence: PostgreSQL in production, with a local SQLite fallback.

Raw submissions stay in the database; everything shown in the UI is masked.
"""
import os
import uuid
import json
import re
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from checks import company_key
from config import ALREADY_REGISTERED, VENDOR_ACTION, VENDORS_ON_FILE

DB_PATH = os.environ.get("DB_PATH") or "onboarding.db"
POSTGRES_URL = os.environ.get("POSTGRES_URL")
SNAPSHOT_FIELDS = ["company_name", "bank_account_name", "tax_id", "pan", "country", "bank_code", "mobile", "email"]
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, ts TEXT, company TEXT, country TEXT, status TEXT, sub_status TEXT,
    rule_version TEXT, seconds REAL, decision TEXT, payload TEXT, snapshot TEXT, parent_id TEXT);
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, run_id TEXT, decision TEXT, note TEXT, reviewer TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS docs(run_id TEXT, slot TEXT, filename TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS vendor_ids(company_key TEXT PRIMARY KEY, vendor_id TEXT);
CREATE TABLE IF NOT EXISTS run_vendor(run_id TEXT PRIMARY KEY, vendor_id TEXT);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, thread_id TEXT, run_id TEXT, event TEXT, recipient TEXT, subject TEXT, body TEXT, headline TEXT,
    created TEXT, status TEXT, sent_at TEXT, attempts INTEGER, error TEXT, transport TEXT, provider_id TEXT, UNIQUE(run_id, event));
CREATE TABLE IF NOT EXISTS claims(run_id TEXT PRIMARY KEY, reviewer TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS vendors(company_key TEXT PRIMARY KEY, company_name TEXT, bank_account_number TEXT, mobile TEXT, email TEXT, address TEXT);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, seq BIGSERIAL UNIQUE, ts TEXT, company TEXT, country TEXT, status TEXT, sub_status TEXT,
    rule_version TEXT, seconds DOUBLE PRECISION, decision TEXT, payload TEXT, snapshot TEXT, parent_id TEXT);
CREATE TABLE IF NOT EXISTS decisions(id BIGSERIAL PRIMARY KEY, run_id TEXT, decision TEXT, note TEXT, reviewer TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS docs(run_id TEXT, slot TEXT, filename TEXT, data BYTEA);
CREATE TABLE IF NOT EXISTS vendor_ids(company_key TEXT PRIMARY KEY, vendor_id TEXT);
CREATE TABLE IF NOT EXISTS run_vendor(run_id TEXT PRIMARY KEY, vendor_id TEXT);
CREATE TABLE IF NOT EXISTS outbox(id BIGSERIAL PRIMARY KEY, thread_id TEXT, run_id TEXT, event TEXT, recipient TEXT, subject TEXT, body TEXT, headline TEXT,
    created TEXT, status TEXT, sent_at TEXT, attempts INTEGER, error TEXT, transport TEXT, provider_id TEXT, UNIQUE(run_id, event));
CREATE TABLE IF NOT EXISTS claims(run_id TEXT PRIMARY KEY, reviewer TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS vendors(company_key TEXT PRIMARY KEY, company_name TEXT, bank_account_number TEXT, mobile TEXT, email TEXT, address TEXT);
"""


def new_vendor_id(country):
    """V + country code + 6 random letters/digits, e.g. VIN7A3D49. Letters and digits only."""
    return "V" + (country if isinstance(country, str) and len(country) == 2 and country.isalpha() and country.isupper() else "XX") + uuid.uuid4().hex[:6].upper()


_lock, _shared = threading.RLock(), {"target": None, "conn": None, "postgres": False, "version": 0}
TIMING = {"n": 0, "ms": 0.0, "commit_ms": 0.0, "connect_ms": 0.0, "slowest": ("", 0.0)}  # what the database cost this request (Server-Timing header)


def timing_reset():
    TIMING.update(n=0, ms=0.0, commit_ms=0.0, connect_ms=0.0, slowest=("", 0.0))


def timed(label, started):
    took = (time.perf_counter() - started) * 1000
    TIMING["n"] += 1
    TIMING["ms"] += took
    if took > TIMING["slowest"][1]:
        TIMING["slowest"] = (label, took)


def version():
    """Bumped by every write in this process; lets callers cache cheap read-only summaries."""
    return _shared["version"]


def using_postgres():
    return bool(POSTGRES_URL)


def psycopg_url(url):
    """Remove provider metadata that libpq does not recognise.

    Supabase's Vercel integration appends ``supa=...`` to identify its pooler.
    The value is useful to provider tooling but is not a PostgreSQL connection
    option, so psycopg correctly rejects it unless it is removed.
    """
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "supa"])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def compatible_sql(sql):
    """Translate the small SQLite-flavoured query subset used by this demo to PostgreSQL."""
    if not using_postgres():
        return sql
    statement = sql.strip()
    if statement.upper().startswith("INSERT OR REPLACE INTO CLAIMS VALUES"):
        statement = ("INSERT INTO claims(run_id, reviewer, ts) VALUES (?,?,?) "
                     "ON CONFLICT (run_id) DO UPDATE SET reviewer=EXCLUDED.reviewer, ts=EXCLUDED.ts")
    elif statement.upper().startswith("INSERT OR IGNORE"):
        statement = re.sub(r"^INSERT\s+OR\s+IGNORE", "INSERT", statement, count=1, flags=re.I)
        statement += " ON CONFLICT DO NOTHING"
    statement = statement.replace("ORDER BY ts, rowid", "ORDER BY ts, seq")
    return statement.replace("?", "%s")


class Handle:
    """A shared connection held by the calling thread until close().

    Serialising access also keeps the SQLite fallback safe when the local app and
    its background mail worker use the database at the same time.
    """

    def __getattr__(self, name):
        return getattr(_shared["conn"], name)

    def execute(self, sql, args=()):
        started = time.perf_counter()
        try:
            return _shared["conn"].execute(compatible_sql(sql), args)
        finally:
            timed(" ".join(sql.split()[:4]), started)

    def executemany(self, sql, args):
        statement, started = compatible_sql(sql), time.perf_counter()
        try:
            if _shared["postgres"]:
                with _shared["conn"].cursor() as cursor:
                    cursor.executemany(statement, args)
                return None
            return _shared["conn"].executemany(statement, args)
        finally:
            timed(" ".join(sql.split()[:4]), started)

    def __enter__(self):
        _shared["conn"].__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        started, conn = time.perf_counter(), _shared["conn"]
        try:
            if _shared["postgres"]:
                # psycopg's own `with conn:` CLOSES the connection on exit (sqlite3's does not). This connection is shared, so closing it made the
                # next request reconnect and re-run the schema: about 11 seconds on a remote database. Commit or roll back and keep it open.
                conn.rollback() if exc_type else conn.commit()
                return False
            return conn.__exit__(exc_type, exc, traceback)
        finally:
            TIMING["commit_ms"] += (time.perf_counter() - started) * 1000

    def close(self):
        _lock.release()


def connect():
    _lock.acquire()
    try:
        target = POSTGRES_URL or DB_PATH
        stale = _shared["postgres"] and _shared["conn"] is not None and _shared["conn"].closed
        if _shared["target"] != target or stale:
            opened = time.perf_counter()
            if _shared["conn"]:
                _shared["conn"].close()
            if using_postgres():
                import psycopg
                from psycopg.rows import dict_row
                conn = psycopg.connect(psycopg_url(POSTGRES_URL), row_factory=dict_row, prepare_threshold=None)
                present = conn.execute("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = current_schema() AND table_name IN "
                                       "('runs','decisions','docs','vendor_ids','run_vendor','outbox','claims','vendors')").fetchone()["n"]
                if present < 8:  # create the tables only the first time: each statement is a network round trip
                    for statement in POSTGRES_SCHEMA.split(";"):
                        if statement.strip():
                            conn.execute(statement)
                conn.commit()
            else:
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.executescript(SQLITE_SCHEMA)
            _shared.update(target=target, conn=conn, postgres=using_postgres())
            seed()  # once per connection, not once per call: on a remote database every statement is a network round trip
            TIMING["connect_ms"] += (time.perf_counter() - opened) * 1000
        return Handle()
    except BaseException:
        _lock.release()
        raise


def seed():
    """Fill an empty vendor master with the vendors that were already on file."""
    conn = _shared["conn"]
    if not conn.execute("SELECT 1 FROM vendors").fetchone():
        values = [(v["company_key"], v["company_name"], v["bank_account_number"], v["mobile"], v["email"], v["address"]) for v in VENDORS_ON_FILE]
        Handle().executemany("INSERT OR IGNORE INTO vendors VALUES (?,?,?,?,?,?)", values)
        Handle().executemany("INSERT OR IGNORE INTO vendor_ids VALUES (?,?)", [(v["company_key"], new_vendor_id(v["country"])) for v in VENDORS_ON_FILE])
        conn.commit()


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


def save_run(submission, decision, seconds, files=None, same_as=None, parent_id=None):
    """files: {slot: (filename, bytes)} - the uploaded documents, kept so a reviewer can open them."""
    run_id, key = uuid.uuid4().hex[:8], company_key(submission)  # random, so nobody can guess another submission's ID
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO runs(run_id, ts, company, country, status, sub_status, rule_version, seconds, decision, payload, snapshot, parent_id) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            run_id, now(), submission.get("company_name"), submission.get("country"), decision["status"], decision["sub_status"],
            decision["rule_version"], round(seconds, 3), json.dumps(decision), json.dumps(submission), json.dumps(make_snapshot(submission)), parent_id))
        conn.executemany("INSERT INTO docs VALUES (?,?,?,?)", [(run_id, slot, name, data) for slot, (name, data) in (files or {}).items()])
        vendor = vendor_for(conn, submission, key, same_as)  # same_as: an earlier run by the same applicant (any status)
        conn.execute("INSERT INTO run_vendor VALUES (?,?)", (run_id, vendor))
        if key and not using_postgres():  # on Postgres vendor_for already inserted it
            conn.execute("INSERT OR IGNORE INTO vendor_ids VALUES (?,?)", (key, vendor))
    _shared["version"] += 1
    return run_id


def vendor_for(conn, submission, key, same_as):
    """Every applicant gets a vendor ID on its first submission. A company already known by its tax identity keeps its ID, and so does a new
    application by the same applicant (even if the tax ID was the typo, or the earlier one was rejected); otherwise a new ID."""
    earlier = same_as and conn.execute("SELECT vendor_id FROM run_vendor WHERE run_id=?", (same_as,)).fetchone()
    candidate = (earlier or {"vendor_id": new_vendor_id(submission.get("country"))})["vendor_id"]
    if key and using_postgres():
        # One canonical vendor ID wins even when two serverless instances receive
        # the first submission for the same company at exactly the same time.
        inserted = conn.execute(
            "INSERT INTO vendor_ids(company_key, vendor_id) VALUES (?,?) ON CONFLICT (company_key) DO NOTHING RETURNING vendor_id",
            (key, candidate),
        ).fetchone()
        return (inserted or conn.execute("SELECT vendor_id FROM vendor_ids WHERE company_key=?", (key,)).fetchone())["vendor_id"]
    known = key and conn.execute("SELECT vendor_id FROM vendor_ids WHERE company_key=?", (key,)).fetchone()
    return (known or {"vendor_id": candidate})["vendor_id"]


def save_decision(run_id, decision, note, reviewer):
    with closing(connect()) as conn, conn:
        sql = "INSERT INTO decisions(run_id, decision, note, reviewer, ts) VALUES (?,?,?,?,?)"
        if using_postgres():
            decision_id = conn.execute(sql + " RETURNING id", (run_id, decision, note, reviewer, now())).fetchone()["id"]
        else:
            decision_id = conn.execute(sql, (run_id, decision, note, reviewer, now())).lastrowid
        conn.execute("DELETE FROM claims WHERE run_id=?", (run_id,))  # a decided run is nobody's any more
    return decision_id


def claims():
    return {c["run_id"]: c for c in query("SELECT * FROM claims")}


def claim(run_id, reviewer):
    """Take a run so two reviewers do not work on it at once. Returns who already holds it, or None when you now do."""
    with closing(connect()) as conn, conn:
        if using_postgres():
            acquired = conn.execute(
                "INSERT INTO claims(run_id, reviewer, ts) VALUES (?,?,?) ON CONFLICT (run_id) DO NOTHING RETURNING reviewer",
                (run_id, reviewer, now()),
            ).fetchone()
            if acquired:
                return None
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
        seed()  # restored at once, so no later call has to check
    _shared["version"] += 1


def final_state(run):
    """What a run is NOW, after a reviewer's decision (the rules' own verdict stays in status/sub_status)."""
    d = run["decision_by"]
    if d and d["decision"] in ("Approved", "Rejected"):
        return {"final": d["decision"], "final_sub": f"{d['decision']} by reviewer", "waiting_on": "-"}
    if d:  # information requested: the application stays open for a correction
        return {"final": "Pending", "final_sub": VENDOR_ACTION, "waiting_on": "Vendor"}
    if run["status"] == "Pending":
        return {"final": "Pending", "final_sub": run["sub_status"],
                "waiting_on": "Reviewer" if run["sub_status"] != VENDOR_ACTION else "Vendor"}
    return {"final": run["status"], "final_sub": run["sub_status"], "waiting_on": "-"}


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
    for run in runs:
        run["application_id"] = run.get("parent_id") or run["run_id"]
    latest_revision = {run["application_id"]: run["run_id"] for run in runs}
    for run in runs:
        latest_id = latest_revision[run["application_id"]]
        run["superseded_by"] = latest_id if latest_id != run["run_id"] else None
        if run["superseded_by"]:
            run.update(final="Pending", final_sub="Corrected submission received", waiting_on="-")
        else:
            run.update(final_state(run))
        run["decided_by"] = run["decision_by"]["reviewer"] if run["decision_by"] and run["decision_by"]["decision"] in ("Approved", "Rejected") else "Automatic"
    return runs


def known_vendors(runs):
    """What the duplicate check compares against: the vendors on file plus everything finally approved (by the rules or a reviewer)."""
    approved = [{"company_key": company_key(r["payload"]), "company_name": r["company"], "bank_account_number": r["payload"].get("bank_account_number"),
                 "mobile": r["payload"].get("mobile"), "email": r["payload"].get("email"), "address": r["payload"].get("address")} for r in runs if r["final"] == "Approved" and r["sub_status"] != ALREADY_REGISTERED]
    return query("SELECT * FROM vendors") + approved
