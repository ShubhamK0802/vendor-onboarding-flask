"""Run: python run_tests.py   (exit code 1 if anything fails, so scripts and CI can catch regressions)"""
import copy
import io
import os
import sys
import tempfile
import time

import store
from decide import parse_submission, run_pipeline
from samples import CASES, INDIA

store.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
failed = []


def check(ok, name, detail=""):
    print("PASS" if ok else "FAIL", name, detail)
    if not ok:
        failed.append(name)


def submit(data, parent_id=None, files=None):
    """What the app does for one submission: check against everything known, then save."""
    return store.save_run(data, run_pipeline(data, store.known_vendors(store.load_runs())), 0.01, parent_id=parent_id, files=files)


def run(run_id):
    return next(r for r in store.load_runs() if r["run_id"] == run_id)


# ---- rules: every sample gives the expected verdict (each with the vendors it needs on file) ----
for name, base, edit, history, status, sub_status in CASES:
    data = copy.deepcopy(base)
    edit(data)
    result = run_pipeline(data, history)
    check((result["status"], result["sub_status"]) == (status, sub_status), name, f"-> {result['status']} {result['sub_status']}")

from checks import check_formats, check_identity, check_name_match, german_vat_check_digit  # noqa: E402
check(german_vat_check_digit("13669597") == 6 and german_vat_check_digit("13669597") != 8, "German VAT check digit matches the published valid example DE136695976")
check(german_vat_check_digit("12345678") == 8, "German VAT check digit: DE123456788 is valid")
codes = lambda sub: [f["code"] for f in check_formats(sub)["findings"]]
de = {"country": "DE", "tax_id": "DE136695976", "bank_account_number": "DE89 3704 0044 0532 0130 00", "bank_code": "COBADEFFXXX"}
check(codes(de) == [] and codes(dict(de, tax_id="DE136695978")) == ["BAD_VAT_CHECKSUM"], "German VAT ID: valid passes, one wrong digit fails the checksum")
check(codes(dict(de, bank_account_number="DE89370400440532013001")) == ["BAD_IBAN_CHECKSUM"] and codes(dict(de, bank_account_number="DE8937040044053201300")) == ["BAD_IBAN_FORMAT"], "IBAN: wrong checksum and wrong German length are both caught")
check(codes(dict(de, bank_code="COBA")) == ["BAD_BIC_FORMAT"], "BIC with the wrong length is caught")
de_with_gstin = check_identity({"country": "DE", "tax_id": INDIA["tax_id"]})
us_with_vat = check_identity({"country": "US", "tax_id": "DE136695976"})
check([f["code"] for f in de_with_gstin["findings"] + us_with_vat["findings"]] == ["ID_COUNTRY_MISMATCH"] * 2, "a tax ID that belongs to another country is a red flag (Germany with a GSTIN, US with a German VAT ID)")
check([f["code"] for f in check_identity(dict(de, bank_account_number="GB82WEST12345698765432"))["findings"]] == ["BANK_COUNTRY_DIFFERS"], "a German company with a foreign IBAN goes to review, not auto-approval")
check(not check_name_match({"company_name": "M\u00fcller S\u00f6hne GmbH", "bank_account_name": "Mueller Soehne GmbH"})["findings"], "umlauts match their bank-statement spelling (ue, oe)")
check([f["code"] for f in check_name_match({"company_name": "Sakura K.K. \u682a\u5f0f\u4f1a\u793e", "bank_account_name": "Sakura KK"})["findings"]] == ["NAME_NON_LATIN"], "names in non-Latin scripts go to review instead of being compared by spelling")

with open("sample_inputs/11_malformed.json") as handle:
    data, error = parse_submission(handle.read())
check(data is None and error, "11_malformed_json", f"-> {error}")

# ---- workflow: starts empty, then real runs ----
check(store.load_runs() == [] and len(store.known_vendors([])) == 1, "history starts empty; only the vendors on file are known")

first = submit(INDIA)
check(run(first)["final"] == "Approved", "clean vendor is approved")
again = submit(INDIA)
check(run(again)["final"] == "Pending" and "EXISTING_VENDOR" in run(again)["codes"], "an already-onboarded vendor submitting again goes to review, never auto-approved")
changed = submit(dict(INDIA, bank_account_number="99900011122233"))
check("BANK_DETAILS_CHANGED" in run(changed)["codes"], "a changed bank account on an onboarded vendor is called out")

near = copy.deepcopy(INDIA)
near.update(company_name="Orion Lookalike Traders", pan="LMNOP4321Q", tax_id="27LMNOP4321Q1Z5", bank_account_name="Orion Lookalike Traders", bank_account_number="60200345678912")
shared = submit(near)
check(run(shared)["waiting_on"] == "Reviewer" and "DUPLICATE_BANK_ACCOUNT" in run(shared)["codes"], "a bank account already on file sends the run to a reviewer")

store.save_decision(shared, "Info requested", "Please send a bank letter", "Asha")
check(run(shared)["waiting_on"] == "Vendor", "info requested: leaves the reviewer queue but stays visible, waiting on the vendor")
store.save_decision(shared, "Approved", "Bank letter received", "Asha")
check(run(shared)["final"] == "Approved" and run(shared)["decided_by"] == "Asha", "reviewer approval changes the final status and records who")
check(any(v["company_name"] == "Orion Lookalike Traders" for v in store.known_vendors(store.load_runs())), "reviewer-approved vendor joins the duplicate check list")

bad = copy.deepcopy(INDIA)
bad.update(tax_id="29ABCCA1234D1", company_name="Fresh Vendor Pvt Ltd", pan="QWERT1234Y", bank_account_name="Fresh Vendor Pvt Ltd", bank_account_number="11122233344455")
pending = submit(bad)
child = submit(bad, parent_id=pending, files={"tax_document": ("w9.pdf", b"%PDF-1.4 test")})
check(run(pending)["final"] == "Replaced" and run(pending)["superseded_by"] == child, "resubmission supersedes the earlier run")
check(store.get_docs(child)[0]["data"] == b"%PDF-1.4 test", "uploaded document is stored and retrievable")
check(store.mask_account("50100234567891") == "****7891" and "50100234567891" not in str(run(first)["snapshot"]), "account numbers are masked in what the UI reads")

store.reset()
check(store.load_runs() == [] and store.load_decisions() == [] and len(store.known_vendors([])) == 1, "reset: no runs or decisions, vendors on file restored")

# ---- web: the Flask routes, end to end ----
import app  # noqa: E402  (imported after the test database is set)

app.STAGE_PAUSE = 0
client = app.app.test_client()


def run_web(**form):
    token = client.post("/api/submit", data=form, content_type="multipart/form-data").get_json()["token"]
    for _ in range(100):
        progress = client.get(f"/api/progress/{token}").get_json()
        if progress["done"]:
            return progress
        time.sleep(0.02)


check(b"No runs yet" in client.get("/dashboard").data and b"Nothing is waiting" in client.get("/review").data, "web: dashboard and reviewer desk are empty before the first run")
check(client.get("/").status_code == 200 and client.get("/about").status_code == 200, "web: submit and about pages load")
check(client.post("/api/submit", data={"mode": "sample", "sample": "../app.py"}).status_code == 400, "web: a sample name that is not in the sample folder is refused")
check(client.post("/api/submit", data={"mode": "json", "json_file": (io.BytesIO(b'{"company_name": "x",'), "bad.json")}, content_type="multipart/form-data").status_code == 400, "web: malformed JSON gives a clear error, not a crash")

done = run_web(mode="sample", sample="01_clean_india.json")
check(done["error"] is None and len(done["stages"]) == 7 and b"Approved" in client.get(f"/run/{done['run_id']}").data, "web: sample runs through 7 stages and shows Approved")
done = run_web(mode="sample", sample="07_shared_bank_account.json")
pending_id = done["run_id"]
check(pending_id.encode() in client.get("/review").data, "web: a pending run appears on the reviewer desk")
check(b"enter your name" in client.post(f"/review/{pending_id}", data={"decision": "Approved", "note": "ok ok ok"}, follow_redirects=True).data, "web: a decision without a name is refused")
check(b"Approved by Asha" in client.post(f"/review/{pending_id}", data={"reviewer": "Asha", "decision": "Approved", "note": "Checked by phone"}, follow_redirects=True).data, "web: a decision with name and reason is saved")

form = {f: "" for f in app.FIELDS}
form.update(mode="form", company_name="Form Vendor LLC", country="US", entity_type="company", tax_id="12-3456789", tax_document=(io.BytesIO(b"%PDF-1.4 hello"), "w9.pdf"))
done = run_web(**form)
check(client.get(f"/doc/{done['run_id']}/tax_document").data == b"%PDF-1.4 hello", "web: an uploaded document can be downloaded back")
check(client.get(f"/api/prefill/{done['run_id']}").get_json().get("company_name") == "Form Vendor LLC" and "bank_account_number" not in client.get(f"/api/prefill/{done['run_id']}").get_json(),
      "web: resubmission prefill leaves the bank account number out")
check(client.get("/export.csv").data.startswith(b"run,when,company"), "web: CSV export works")
check(b"Form Vendor LLC" in client.get("/dashboard").data and b"****" not in client.get("/export.csv").data, "web: dashboard lists the runs")
client.post("/reset")
check(b"No runs yet" in client.get("/dashboard").data, "web: reset empties the dashboard again")

# ---- reviewer desk: order, filters, taking a submission, next-up, info-requested runs ----
contact = run_web(mode="sample", sample="15_shared_contact.json")["run_id"]  # normal priority, submitted first
clash = run_web(mode="sample", sample="07_shared_bank_account.json")["run_id"]  # bank account clash: high priority, submitted second
near = run_web(mode="sample", sample="06_near_miss_name.json")["run_id"]  # normal priority, newest


def rows(html):
    text = html.decode()
    return sorted((text.find(f">{rid}</a>"), rid) for rid in (contact, clash, near) if f">{rid}</a>" in text)


order = lambda url: [rid for _, rid in rows(client.get(url).data)]
check(order("/review") == [clash, contact, near], "reviewer desk: default order puts the high-priority run first, then oldest")
check(order("/review?sort=oldest") == [contact, clash, near] and order("/review?sort=newest") == [near, clash, contact], "reviewer desk: oldest-first and newest-first orders")
check(order("/review?priority=High") == [clash] and order("/review?q=quill") == [contact], "reviewer desk: filter by priority and search by company")
check(b"Being handled by" not in client.get(f"/review?run={contact}").data, "reviewer desk: nothing is taken at first")

client.post(f"/review/{contact}/claim", data={"reviewer": "Asha"})
check(b"Being handled by <b>Asha</b>" in client.get(f"/review?run={contact}").data, "reviewer desk: a reviewer can take a submission and everyone sees it")
check(b"already handling" in client.post(f"/review/{contact}/claim", data={"reviewer": "Priya"}, follow_redirects=True).data, "reviewer desk: a second reviewer cannot take it")
check(b"cannot decide it" in client.post(f"/review/{contact}", data={"reviewer": "Priya", "decision": "Approved", "note": "looks fine"}, follow_redirects=True).data, "reviewer desk: nobody else can decide a submission someone has taken")
check(b"Only Asha can give" in client.post(f"/review/{contact}/release", data={"reviewer": "Priya"}, follow_redirects=True).data, "reviewer desk: only the holder can give it back")
client.post(f"/review/{contact}/release", data={"reviewer": "asha"})
check(b"Being handled by" not in client.get(f"/review?run={contact}").data, "reviewer desk: giving it back frees it (names are not case-sensitive)")

page = client.post(f"/review/{clash}", data={"reviewer": "Asha", "decision": "Info requested", "note": "Send a bank letter", "sort": "priority"}, follow_redirects=True).data
check(f">{contact}</a>" in page.decode() and f"run={clash}" in page.decode(), "reviewer desk: after a decision the next submission opens, and an info-requested run stays reachable")
check(store.load_runs() and next(r for r in store.load_runs() if r["run_id"] == clash)["waiting_on"] == "Vendor", "reviewer desk: info requested moves the run to waiting on the vendor")
done_page = client.post(f"/review/{clash}", data={"reviewer": "Priya", "decision": "Rejected", "note": "Vendor never replied"}, follow_redirects=True).data
check(b"Rejected by Priya" in done_page and next(r for r in store.load_runs() if r["run_id"] == clash)["final"] == "Rejected", "reviewer desk: a run waiting for the vendor's reply can still be closed by a reviewer")
client.post("/reset")


print("ALL PASSED" if not failed else f"FAILED: {failed}")
sys.exit(1 if failed else 0)
