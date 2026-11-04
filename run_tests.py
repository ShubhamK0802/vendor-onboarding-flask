"""Run: python run_tests.py   (exit code 1 if anything fails, so scripts and CI can catch regressions)"""
import copy
import io
import json
import os
import re
import sys
import tempfile
import time

import store

os.environ["MAIL_WORKER"] = "0"  # the background sender is driven by hand in the tests
from decide import parse_submission, run_pipeline
from datetime import datetime, timedelta

from samples import CASES, SAMPLES, INDIA, american, fresh, make_iban, short_tax_id

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
for name, data, history, status, sub_status, _ in CASES:
    result = run_pipeline(copy.deepcopy(data), history)
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

data, error = parse_submission('{"company_name": "Apex Global",')
check(data is None and error, "malformed JSON gives a clear error", f"-> {error}")

# ---- workflow: starts empty, then real runs ----
check(store.load_runs() == [] and len(store.known_vendors([])) == 1, "history starts empty; only the vendors on file are known")

first = submit(INDIA)
check(len(first) == 8 and first != run(submit(INDIA))["run_id"] and not first.startswith("S-") and re.fullmatch(r"VIN[0-9A-F]{6}", run(first)["vendor_id"]) and "-" not in run(first)["vendor_id"], "submission IDs are random 8-character codes, not a guessable sequence, and vendors get a V- ID")
check(run(first)["final"] == "Approved", "clean vendor is approved")
again = submit(INDIA)
check(run(again)["final"] == "Rejected" and "DUPLICATE_APPLICATION" in run(again)["codes"] and "exactly these details" in run(again)["decision"]["vendor_message"],
      "an already-onboarded vendor applying again with nothing new is rejected as a duplicate, with a safe reason")
check(run(submit(INDIA))["vendor_id"] == run(first)["vendor_id"], "every submission by the same company carries the same vendor ID")
moved = submit(dict(INDIA, address="99 Somewhere Else Road, Mumbai 400001"))
check(run(moved)["final"] == "Pending" and run(moved)["waiting_on"] == "Reviewer" and "EXISTING_VENDOR" in run(moved)["codes"], "an onboarded vendor whose details changed goes to a reviewer, never auto-approved")
changed = submit(dict(INDIA, bank_account_number="99900011122233"))
check("BANK_DETAILS_CHANGED" in run(changed)["codes"], "a changed bank account on an onboarded vendor is called out")

near = copy.deepcopy(INDIA)
near.update(company_name="Orion Lookalike Traders", pan="LMNOP4321Q", tax_id="27LMNOP4321Q1Z5", bank_account_name="Orion Lookalike Traders", bank_account_number="60200345678912")
shared = submit(near)
check(run(shared)["waiting_on"] == "Reviewer" and "DUPLICATE_BANK_ACCOUNT" in run(shared)["codes"], "a bank account already on file sends the run to a reviewer")

vid = run(shared)["vendor_id"]
check(re.fullmatch(r"VIN[0-9A-F]{6}", vid), "vendor ID: every applicant gets one on its first submission, approved or not")
store.save_decision(shared, "Info requested", "Please send a bank letter", "Asha")
check(run(shared)["waiting_on"] == "Vendor", "info requested: leaves the reviewer queue but stays visible, waiting on the vendor")
store.save_decision(shared, "Approved", "Bank letter received", "Asha")
check(run(shared)["vendor_id"] == vid, "vendor ID: approval does not change it")
check(run(shared)["final"] == "Approved" and run(shared)["decided_by"] == "Asha", "reviewer approval changes the final status and records who")
check(any(v["company_name"] == "Orion Lookalike Traders" for v in store.known_vendors(store.load_runs())), "reviewer-approved vendor joins the duplicate check list")

bad = copy.deepcopy(INDIA)
bad.update(tax_id="29ABCCA1234D1", company_name="Fresh Vendor Pvt Ltd", pan="QWERT1234Y", bank_account_name="Fresh Vendor Pvt Ltd", bank_account_number="11122233344455")
pending = submit(bad)
child = submit(bad, parent_id=pending, files={"tax_document": ("w9.pdf", b"%PDF-1.4 test")})
check(run(pending)["final"] == "Replaced" and run(pending)["superseded_by"] == child, "resubmission supersedes the earlier run")
check(store.get_docs(child)[0]["data"] == b"%PDF-1.4 test", "uploaded document is stored and retrievable")
check(store.mask_account("50100234567891") == "****7891" and "50100234567891" not in str(run(first)["snapshot"]), "account numbers are masked in what the UI reads")

# ---- the status definitions
quartz = fresh(copy.deepcopy(INDIA), "Quartz Mills Private Limited", "QUACM2345Q", "79000123456709")
outcome = lambda d, prev=(): (lambda r: (r["status"], r["sub_status"]))(run_pipeline(d, [], prev))
check(outcome(quartz) == ("Approved", None), "status definitions: a vendor with nothing wrong is approved")
never = submit(dict(quartz, tax_id="123456789"))
check(re.fullmatch(r"VIN[0-9A-F]{6}", run(never)["vendor_id"]), "vendor ID: a sent-back company has one too")

# vendor IDs carry the company's country and nothing but letters and digits
from store import new_vendor_id  # noqa: E402
check(all(re.fullmatch(rf"V{cc}[0-9A-F]{{6}}", new_vendor_id(cc)) for cc in ("IN", "US", "DE")) and re.fullmatch(r"VBR[0-9A-F]{6}", new_vendor_id("BR")) and re.fullmatch(r"VXX[0-9A-F]{6}", new_vendor_id(None)), "vendor ID: V + the applicant's country (XX if unknown) + 6 letters or digits, no special characters")
typo = submit(american("Zenith Fabricators LLC", "42958371", "5100999111"))
fixed = submit(american("Zenith Fabricators LLC", "04-2958371", "5100999111"), parent_id=typo)
later = submit(american("Zenith Fabricators LLC", "04-2958371", "5100999111"))
check(run(typo)["vendor_id"].startswith("VUS") and run(fixed)["vendor_id"] == run(typo)["vendor_id"] == run(later)["vendor_id"], "vendor ID: a corrected resubmission keeps the ID of the submission it replaces, and so does the company's next application")
keyless = dict(quartz, pan="")  # no PAN, so no company key to recognise it by
first_k, other_k = submit(keyless), submit(dict(keyless, company_name="Other Mills Private Limited"))
again_k = submit(keyless, parent_id=first_k)
check(run(first_k)["vendor_id"] and run(first_k)["vendor_id"] != run(other_k)["vendor_id"] and run(again_k)["vendor_id"] == run(first_k)["vendor_id"], "vendor ID: even with no tax identity every applicant gets an ID, and a linked resubmission keeps it")

# ---- the vendor message is short and to the point
two = run_pipeline(dict(quartz, bank_account_name="Zenith Traders", documents=dict(quartz["documents"], voided_cheque=None)), [])["vendor_message"]
check(two == "Please fix:\n1. Upload a voided cheque or passbook page\n2. Use a bank account in your company's name, or attach a signed authorisation letter" and len(two) < 150, "vendor message: two fixes are a short numbered list")
check(run_pipeline(dict(quartz, tax_id="123456789"), [])["vendor_message"].startswith("Please fix:"), "vendor message: starts with what to do")

check(outcome(dict(quartz, tax_id="123456789")) == ("Pending", "Vendor to fix"), "status definitions: one contradiction alone (tax ID of another country) is a mistake the vendor can fix")
check(outcome(dict(quartz, pan="ZZZZZ9999Z")) == ("Rejected", None), "status definitions: two contradictions at once are rejected")
near_miss = dict(quartz, bank_account_name="Quartz Mill Private Limited")
first_try = run_pipeline(near_miss, [])
check((first_try["status"], first_try["sub_status"]) == ("Pending", "Vendor to fix"), "status definitions: a near-miss name is first a vendor fix")
asked = [(f["code"], f["message"]) for f in first_try["findings"]]
second_try = run_pipeline(near_miss, [], asked)
check(second_try["status"] == "Rejected" and "not fixed after your resubmission" in second_try["vendor_message"], "status definitions: the same finding after being asked to fix it rejects")
check(outcome(quartz, asked) == ("Approved", None), "status definitions: a vendor who really fixes it is approved")
mismatch = dict(quartz, bank_account_name="Zenith Traders")
asked = [(f["code"], f["message"]) for f in run_pipeline(mismatch, [])["findings"]]
escalated = run_pipeline(mismatch, [], asked)
check(run_pipeline(mismatch, [])["sub_status"] == "Vendor to fix" and (escalated["status"], escalated["sub_status"]) == ("Pending", "Needs review"), "status definitions: a third-party bank account is a vendor fix first, then a person reads their explanation")

stale = submit(dict(quartz, tax_id=quartz["tax_id"][:13]))
recent = submit(dict(quartz, tax_id=quartz["tax_id"][:12]))
with store.connect() as conn:
    conn.execute("UPDATE runs SET ts=? WHERE run_id=?", ((datetime.now() - timedelta(days=8)).isoformat(timespec="seconds"), stale))
check(run(stale)["final"] == "Rejected" and "Closed" in run(stale)["final_sub"] and run(stale)["waiting_on"] == "-", "status definitions: a fix request nobody answers for 8 days closes as rejected")
check(run(recent)["final"] == "Pending" and run(recent)["waiting_on"] == "Vendor", "status definitions: a fresh fix request stays open")

# ---- verification: placeholders, registry, sanctions, embargoes, the EU check
import checks  # noqa: E402
from checks import check_verification, is_placeholder  # noqa: E402

vcodes = lambda sub: [f["code"] for f in check_verification(sub)["findings"]]
check(is_placeholder("123456789") and is_placeholder("111111111") and is_placeholder("987654321") and not is_placeholder("042958371") and not is_placeholder("271846352"), "verification: placeholder tax IDs are recognised, real-looking ones are not")
check(vcodes({"country": "US", "tax_id": "12-3456789"}) == ["PLACEHOLDER_TAX_ID"], "verification: the famous 12-3456789 EIN is a placeholder")
apex = {"country": "IN", "tax_id": "29ABCCA1234D1Z6", "company_name": "Apex Global Private Limited"}
check(vcodes(apex) == [] and vcodes(dict(apex, company_name="Apex Traders")) == ["REGISTRY_NAME_MISMATCH"], "verification: the registry accepts the registered name and flags a different one")
unknown = check_verification({"country": "IN", "tax_id": "27UNKNOWN1234Z1Z5", "company_name": "Nobody Ltd"})
check(unknown["findings"] == [] and "not checked" in unknown["note"], "verification: an ID the demo registry does not know is not checked, and says so")
check(vcodes({"company_name": "Northern Star Arms Trading Limited"}) == ["SANCTIONS_MATCH"] and vcodes({"company_name": "Northern Star Arm Trading Ltd"}) == ["SANCTIONS_POSSIBLE"] and vcodes({"company_name": "Quartz Mills Private Limited"}) == [],
      "verification: an exact watchlist name matches, a close one is only possible, an unrelated one is clear")
check(vcodes({"bank_account_name": "Red Falcon Shipping Co", "company_name": "Innocent Traders"}) == ["SANCTIONS_MATCH"], "verification: the bank account holder is screened too")
iran = {"bank_account_number": make_iban("IR", "0120000000012345678901"), "bank_code": "BKMTIRTHXXX"}
check(vcodes(iran) == ["EMBARGOED_BANK_COUNTRY"] and vcodes({"bank_account_number": "DE89370400440532013000", "bank_code": "COBADEFFXXX"}) == [], "verification: a bank in an embargoed country is caught, a German one is not")
os.environ["VIES_LIVE"] = "1"
de_vat = {"country": "DE", "tax_id": "DE136695976", "company_name": "Whoever GmbH"}
checks.vies_lookup = lambda vat: {"valid": True}
check(vcodes(de_vat) == [], "verification: the EU VAT check passes a registered number")
checks.vies_lookup = lambda vat: {"valid": False}
check(vcodes(de_vat) == ["REGISTRY_NOT_FOUND"], "verification: the EU VAT check flags an unregistered number")
checks.vies_lookup = lambda vat: None
down = check_verification(de_vat)
check(down["findings"] == [] and "not checked" in down["note"], "verification: if the EU service is unreachable the vendor is not blocked")
os.environ.pop("VIES_LIVE")

store.reset()
check(store.load_runs() == [] and store.load_decisions() == [] and len(store.known_vendors([])) == 1, "reset: no runs or decisions, vendors on file restored")

# ---- the app offers exactly six samples: one clean vendor and five edge cases
by_case = {case[0]: case for case in CASES}
shown = sorted(f[:-5] for f in os.listdir("sample_inputs"))
check(shown == sorted(file for file, _ in SAMPLES) and len(shown) == 6, "samples: the app offers exactly six (one clean vendor and five edge cases)", f"-> {shown}")
check([by_case[case][3:5] for _, case in SAMPLES] == [("Approved", None), ("Pending", "Vendor to fix"), ("Pending", "Vendor to fix"), ("Pending", "Vendor to fix"), ("Rejected", None), ("Pending", "Needs review")],
      "samples: they cover every outcome (approved, vendor to fix, rejected, needs review)")
for file, case in SAMPLES:
    with open(f"sample_inputs/{file}.json", encoding="utf-8") as handle:
        check(json.load(handle) == json.loads(json.dumps(by_case[case][1])), f"samples: {file} is the tested case {case}")

# ---- web: the Flask routes, end to end ----
import app  # noqa: E402  (imported after the test database is set)

app.STAGE_PAUSE = 0
client = app.app.test_client()


CASE = {case[0]: case[1] for case in CASES}


def run_case(name, **extra):
    """Submit one of the test cases through the web API as an uploaded JSON file (only five of them are samples in the app)."""
    body = json.dumps(CASE[name]).encode()
    return run_web(mode="json", json_file=(io.BytesIO(body), f"{name}.json"), **extra)


def run_web(**form):
    token = client.post("/api/submit", data=form, content_type="multipart/form-data").get_json()["token"]
    for _ in range(100):
        progress = client.get(f"/api/progress/{token}").get_json()
        if progress["done"]:
            return progress
        time.sleep(0.02)


check(b"No submissions yet" in client.get("/dashboard").data and b"Nothing is waiting" in client.get("/review").data, "web: dashboard and reviewer desk are empty before the first run")
check(client.get("/").status_code == 200 and client.get("/about").status_code == 200, "web: submit and about pages load")
check(client.post("/api/submit", data={"mode": "sample", "sample": "../app.py"}).status_code == 400, "web: a sample name that is not in the sample folder is refused")
check(client.post("/api/submit", data={"mode": "json", "json_file": (io.BytesIO(b'{"company_name": "x",'), "bad.json")}, content_type="multipart/form-data").status_code == 400, "web: malformed JSON gives a clear error, not a crash")

done = run_web(mode="sample", sample="01_approved_india_clean.json")
check(done["error"] is None and len(done["stages"]) == 8 and b"Approved" in client.get(f"/run/{done['run_id']}").data, "web: sample runs through 8 stages and shows Approved")
done = run_case("12_review_bank_account_shared_with_another_vendor")
pending_id = done["run_id"]
check(pending_id.encode() in client.get("/review").data, "web: a pending run appears on the reviewer desk")
seen = client.get(f"/run/{pending_id}").data.decode()
check("Harbor Freight Private Limited" in seen and "27HARCF6789P" in seen and "****8912" in seen and "60200345678912" not in seen and "flagged" in seen and "not provided" in seen,
      "web: the submission is shown (company, IDs, masked bank account, flagged fields, missing documents) and the full account number never is")
check(b"enter your name" in client.post(f"/review/{pending_id}", data={"decision": "Approved", "note": "ok ok ok"}, follow_redirects=True).data, "web: a decision without a name is refused")
check(b"Approved by Asha" in client.post(f"/review/{pending_id}", data={"reviewer": "Asha", "decision": "Approved", "note": "Checked by phone"}, follow_redirects=True).data, "web: a decision with name and reason is saved")

form = {f: "" for f in app.FIELDS}
form.update(mode="form", company_name="Form Vendor LLC", country="US", entity_type="company", tax_id="12-3456789", tax_document=(io.BytesIO(b"%PDF-1.4 hello"), "w9.pdf"))
done = run_web(**form)
check(client.get(f"/doc/{done['run_id']}/tax_document").data == b"%PDF-1.4 hello", "web: an uploaded document can be downloaded back")
check(client.get(f"/api/prefill/{done['run_id']}").get_json().get("company_name") == "Form Vendor LLC" and "bank_account_number" not in client.get(f"/api/prefill/{done['run_id']}").get_json(),
      "web: resubmission prefill leaves the bank account number out")
check(client.get("/export.csv").data.startswith(b"submission id,vendor id,submitted at,company"), "web: CSV export works")
check(b"Form Vendor LLC" in client.get("/dashboard").data and b"Handled without a human" in client.get("/dashboard").data and b"****" not in client.get("/export.csv").data, "web: dashboard lists the runs")
client.post("/reset")
check(b"No submissions yet" in client.get("/dashboard").data, "web: reset empties the dashboard again")

# a near-miss name: the vendor corrects it once; the same finding on the resubmission rejects
first = run_case("09_fix_near_miss_name")["run_id"]
check(next(r for r in store.load_runs() if r["run_id"] == first)["final"] == "Pending" and b"match your company name exactly" in client.get(f"/run/{first}").data, "web: a near-miss name is first sent back to the vendor to fix")
again = run_case("09_fix_near_miss_name", parent=first)["run_id"]
check(next(r for r in store.load_runs() if r["run_id"] == again)["final"] == "Rejected" and b"not fixed after your resubmission" in client.get(f"/run/{again}").data, "web: the same near-miss on the resubmission is rejected, and the vendor is told why")

# ---- reviewer desk: order, filters, taking a submission, next-up, info-requested runs ----
contact = run_case("14_review_shared_mobile_number")["run_id"]  # submitted first
clash = run_case("12_review_bank_account_shared_with_another_vendor")["run_id"]  # bank account clash, submitted second
near = run_case("16_review_unsupported_country")["run_id"]  # newest


def rows(html):
    text = html.decode()
    return sorted((text.find(f">{rid}</a>"), rid) for rid in (contact, clash, near) if f">{rid}</a>" in text)


order = lambda url: [rid for _, rid in rows(client.get(url).data)]
check(order("/review") == [contact, clash, near] and b"riority" not in client.get("/review").data, "reviewer desk: oldest first by default, and no priority anywhere")
check(order("/review?sort=oldest") == [contact, clash, near] and order("/review?sort=newest") == [near, clash, contact], "reviewer desk: oldest-first and newest-first orders")
check(order("/review?q=quill") == [contact] and order("/review?q=harbor") == [clash], "reviewer desk: search by company")
check(b"Being handled by" not in client.get(f"/review?run={contact}").data, "reviewer desk: nothing is taken at first")

client.post(f"/review/{contact}/claim", data={"reviewer": "Asha"})
check(b"Being handled by <b>Asha</b>" in client.get(f"/review?run={contact}").data, "reviewer desk: a reviewer can take a submission and everyone sees it")
check(b"already handling" in client.post(f"/review/{contact}/claim", data={"reviewer": "Priya"}, follow_redirects=True).data, "reviewer desk: a second reviewer cannot take it")
check(b"cannot decide it" in client.post(f"/review/{contact}", data={"reviewer": "Priya", "decision": "Approved", "note": "looks fine"}, follow_redirects=True).data, "reviewer desk: nobody else can decide a submission someone has taken")
check(b"Only Asha can give" in client.post(f"/review/{contact}/release", data={"reviewer": "Priya"}, follow_redirects=True).data, "reviewer desk: only the holder can give it back")
client.post(f"/review/{contact}/release", data={"reviewer": "asha"})
check(b"Being handled by" not in client.get(f"/review?run={contact}").data, "reviewer desk: giving it back frees it (names are not case-sensitive)")

page = client.post(f"/review/{clash}", data={"reviewer": "Asha", "decision": "Info requested", "note": "Send a bank letter", "sort": "oldest"}, follow_redirects=True).data
check(f">{contact}</a>" in page.decode() and f"run={clash}" in page.decode(), "reviewer desk: after a decision the next submission opens, and an info-requested run stays reachable")
check(store.load_runs() and next(r for r in store.load_runs() if r["run_id"] == clash)["waiting_on"] == "Vendor", "reviewer desk: info requested moves the run to waiting on the vendor")
done_page = client.post(f"/review/{clash}", data={"reviewer": "Priya", "decision": "Rejected", "note": "Vendor never replied"}, follow_redirects=True).data
check(b"Rejected by Priya" in done_page and next(r for r in store.load_runs() if r["run_id"] == clash)["final"] == "Rejected", "reviewer desk: a run waiting for the vendor's reply can still be closed by a reviewer")
client.post("/reset")


# ---- the outbox and the background sender (driven by hand here; in the app a worker thread does the same every few seconds)
import mailer  # noqa: E402

outbox = lambda: store.query("SELECT * FROM outbox ORDER BY id")
of = lambda run_id: [row for row in outbox() if row["run_id"] == run_id]
client.post("/reset")
check(outbox() == [], "outbox: empty after a reset")
approved = run_case("01_approved_india_clean")["run_id"]
check([(row["event"], row["status"]) for row in outbox()] == [("verdict", "queued")], "outbox: a verdict is queued the moment a submission is processed")
mailer.deliver_queued()
row = outbox()[0]
check(row["status"] == "sent" and row["transport"] == "simulated" and row["sent_at"] and row["body"] == "Your application is approved.", "outbox: the sender sends it (simulated, as no mail service is set up) and records the time")
mailer.deliver_queued()
check(len(outbox()) == 1 and outbox()[0]["attempts"] == 1, "outbox: a sent message is never sent twice")

fixing = run_case("04_fix_us_ein_dropped_zero")["run_id"]
closing_id = run_case("05_fix_wrong_document_in_slot")["run_id"]
days_ago = lambda days: (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
with store.connect() as conn:
    conn.execute("UPDATE runs SET ts=? WHERE run_id=?", (days_ago(4), fixing))
    conn.execute("UPDATE runs SET ts=? WHERE run_id=?", (days_ago(8), closing_id))
mailer.sweep()
mailer.sweep()
events = [row["event"] for row in outbox()]
check(events.count("reminder") == 1 and events.count("closed") == 1, "background sender: a 4-day-old fix request gets one reminder and an 8-day-old one a closing notice, however often it checks")

reviewing = run_case("12_review_bank_account_shared_with_another_vendor")["run_id"]
mailer.deliver_queued()
page = client.get("/messages").data.decode()
check("Simulated: no mail service" in page and "accounts@apexglobal.example" in page and "Sent (simulated)" in page and page.count("Your application is approved.") == 1, "messages: the page says the mail service is simulated, shows who it is to, and the status of each message")
check("Your application is under review. We will reach back to you if anything is needed." in page and "Please fix" in page and page.count("Reminder: your application is still waiting") == 1 and "did not hear back within 7 days" in page,
      "messages: under review, please-fix, reminder and closing notice all went out")
shown_to_vendor = "Your application is under review. We will reach back to you if anything is needed."
check(shown_to_vendor in client.get(f"/run/{reviewing}").data.decode() and shown_to_vendor not in client.get(f"/review?run={reviewing}").data.decode()
      and shown_to_vendor not in client.get(f"/dashboard?run={reviewing}").data.decode(), "the vendor's message shows on the vendor's result page, not on the reviewer desk or the dashboard detail")

client.post(f"/review/{reviewing}", data={"reviewer": "Asha", "decision": "Approved", "note": "Checked by phone"})
rejecting = run_case("14_review_shared_mobile_number")["run_id"]
client.post(f"/review/{rejecting}", data={"reviewer": "Asha", "decision": "Rejected", "note": "internal: looks like a shell company"})
asking = run_case("13_review_company_id_under_new_name")["run_id"]
client.post(f"/review/{asking}", data={"reviewer": "Asha", "decision": "Info requested", "note": "internal: check the certificate"})
check(all(row["status"] == "queued" for row in of(reviewing)[1:] + of(rejecting)[1:] + of(asking)[1:]) and len(of(asking)) == 2, "outbox: a reviewer's decision queues a message to the vendor automatically")
mailer.deliver_queued()
page = client.get("/messages").data.decode()
check(page.count("Your application is approved.") == 2, "messages: a reviewer's approval is sent to the vendor")
check("Your application is rejected because we could not verify your contact details." in page, "messages: a reviewer's rejection tells the vendor the reason, worked out from the findings")
check("1. your company registration certificate showing your current legal name" in page and "Please resubmit with them on the Onboard vendor page." in page, "messages: a request for more information lists the documents needed, worked out from the findings")
check("internal:" not in page and "different company" not in page and "another vendor" not in page, "messages: nothing the reviewer typed, and nothing about other vendors, reaches the vendor")

parent = run_case("09_fix_near_miss_name")["run_id"]
child = run_case("09_fix_near_miss_name", parent=parent)["run_id"]
by_thread = {t["id"]: t for t in mailer.threads()}
thread = by_thread[parent]
check(child not in by_thread and [m["run_id"] for m in thread["messages"]] == [parent, child] and thread["messages"][0]["subject"] == f"Your vendor application ({parent})"
      and thread["messages"][1]["subject"] == f"Re: Your vendor application ({parent})", "messages: a corrected resubmission is a reply in the same thread, with the same subject and Re:")
check(len(by_thread) == sum(1 for r in store.load_runs() if not r["parent_id"]), "messages: exactly one thread per application, however many resubmissions it has")

nobody = run_case("25_fix_incomplete_form_with_wrong_document")["run_id"]
mailer.deliver_queued()
check(of(nobody)[0]["status"] == "noaddr" and "Not sent: no email address" in client.get("/messages").data.decode(), "outbox: a submission with no email address is shown as not sent, honestly")

failing = run_case("19_reject_two_contradictions")["run_id"]
real_send = mailer.send


def broken(row):
    raise OSError("mail service down")


mailer.send = broken
for _ in range(3):
    mailer.deliver_queued()
mailer.send = real_send
row = of(failing)[0]
check(row["status"] == "failed" and row["attempts"] == 3 and "mail service down" in row["error"], "outbox: a send that keeps failing is retried three times, then shown as failed")

# a real provider: only for addresses on the allowed list, as a reply in the same thread (the network call is replaced by a stand-in here)
captured = []


class Reply:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b'{"messageId": "<abc123@brevo>"}'


real_urlopen = mailer.urllib.request.urlopen
mailer.urllib.request.urlopen = lambda request, timeout=None: (captured.append(request), Reply())[1]
os.environ.update(BREVO_API_KEY="test-key", MAIL_FROM="sender@example.org", MAIL_ALLOWLIST="Shubham@Example.org, other@example.org")
mine = run_web(mode="json", json_file=(io.BytesIO(json.dumps(dict(CASE["15_review_sole_proprietor_personal_account"], email="shubham@example.org")).encode()), "mine.json"))["run_id"]
client.post(f"/review/{mine}", data={"reviewer": "Asha", "decision": "Approved", "note": "ok ok ok"})
stranger = run_case("16_review_unsupported_country")["run_id"]
mailer.deliver_queued()
os.environ.pop("BREVO_API_KEY"), os.environ.pop("MAIL_FROM"), os.environ.pop("MAIL_ALLOWLIST")
mailer.urllib.request.urlopen = real_urlopen
first_request, second_request = captured[0], captured[1]
sent = json.loads(first_request.data)
check(len(captured) == 2 and [row["transport"] for row in of(mine)] == ["brevo", "brevo"] and of(stranger)[0]["transport"] == "simulated", "real mail: only the allowed address goes out for real; any other address stays simulated")
check(first_request.full_url == "https://api.brevo.com/v3/smtp/email" and first_request.get_header("Api-key") == "test-key" and sent["to"] == [{"email": "shubham@example.org"}]
      and sent["sender"] == {"email": "sender@example.org"} and sent["subject"] == f"Your vendor application ({mine})" and "headers" not in sent, "real mail: the request is shaped for the provider")
check(json.loads(second_request.data)["headers"] == {"In-Reply-To": "<abc123@brevo>", "References": "<abc123@brevo>"} and json.loads(second_request.data)["subject"].startswith("Re: "), "real mail: the second mail is a reply in the same conversation")
client.post("/reset")
check(b"No messages yet" in client.get("/messages").data and outbox() == [], "messages: empty after a reset")

print("ALL PASSED" if not failed else f"FAILED: {failed}")
sys.exit(1 if failed else 0)
