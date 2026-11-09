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


from samples import APEX, CASES, SAMPLES, SEED, INDIA, american, fresh, indian, make_iban

store.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
failed = []


def check(ok, name, detail=""):
    print("PASS" if ok else "FAIL", name, detail)
    if not ok:
        failed.append(name)


def submit(data, same_as=None, files=None):
    """What the app does for one submission: check against everything known, then save."""
    return store.save_run(data, run_pipeline(data, store.known_vendors(store.load_runs())), 0.01, files=files, same_as=same_as)


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
check(run(again)["final"] == "Approved" and run(again)["final_sub"] == "Already registered" and "DUPLICATE_APPLICATION" in run(again)["codes"]
      and run(again)["decision"]["vendor_message"] == "You are already registered with us. No new application is needed.",
      "an already-onboarded vendor applying again with nothing new is Approved as 'already registered', and told so")
check(sum(1 for v in store.known_vendors(store.load_runs()) if v["company_key"] == "ABCCA1234D") == 1, "an 'already registered' repeat is not a second vendor on file")
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
check(run(shared)["final"] == "Rejected" and run(shared)["final_sub"] == "Information needed" and run(shared)["waiting_on"] == "-", "info requested: closes the application as rejected, nothing waits on the vendor")
store.save_decision(shared, "Approved", "Bank letter received", "Asha")
check(run(shared)["vendor_id"] == vid, "vendor ID: approval does not change it")
check(run(shared)["final"] == "Approved" and run(shared)["decided_by"] == "Asha", "reviewer approval changes the final status and records who")
check(any(v["company_name"] == "Orion Lookalike Traders" for v in store.known_vendors(store.load_runs())), "reviewer-approved vendor joins the duplicate check list")

bad = copy.deepcopy(INDIA)
bad.update(tax_id="29ABCCA1234D1", company_name="Fresh Vendor Pvt Ltd", pan="QWERT1234Y", bank_account_name="Fresh Vendor Pvt Ltd", bank_account_number="11122233344455")
child = submit(bad, files={"tax_document": ("w9.pdf", b"%PDF-1.4 test")})
check(store.get_docs(child)[0]["data"] == b"%PDF-1.4 test", "uploaded document is stored and retrievable")
check(store.mask_account("50100234567891") == "****7891" and "50100234567891" not in str(run(first)["snapshot"]), "account numbers are masked in what the UI reads")
bad_signature = copy.deepcopy(INDIA)
bad_signature["documents"]["registration"]["signature_valid"] = False
signature_result = run_pipeline(bad_signature, [])
check((signature_result["status"], signature_result["sub_status"]) == ("Rejected", None) and "MALFORMED_DOCUMENT" in [f["code"] for f in signature_result["findings"]],
      "document upload: a file whose bytes do not match its extension is returned for correction")

# ---- look-alike characters are rejected outright; honest digits in names are fine
import checks as C  # noqa: E402

shape = {r.code: r.shape for r in C.FORMATS if r.shape}
verdict = lambda d, history=(): (lambda r: (r["status"], r["sub_status"], [f["code"] for f in r["findings"]], r["vendor_message"]))(run_pipeline(copy.deepcopy(d), list(history)))
check(C.lookalike_only("29ABCCAI234D1Z6", shape["BAD_GSTIN_FORMAT"]) and C.lookalike_only("O21000021", shape["BAD_ROUTING_FORMAT"]) and C.lookalike_only("6O200345678912", "D*")
      and not C.lookalike_only("29AB23I3l07", shape["BAD_GSTIN_FORMAT"]) and not C.lookalike_only("29ABCCA!234D1Z6", shape["BAD_GSTIN_FORMAT"]) and not C.lookalike_only("29ABCCA1234D1Z6", shape["BAD_GSTIN_FORMAT"]),
      "look-alikes: swaps like I for 1 are recognised; a wrong length, a stray symbol or a valid ID are not look-alikes")
check(C.lookalike("g00gle", "google") and C.lookalike("Google India Private Limited", "G00gle India Pvt Ltd")
      and not C.lookalike("34square Private Limited", "34SQUARE PVT LTD") and not C.lookalike("add360", "ADD360") and not C.lookalike("Lumina Global", "Lumina Globe") and not C.lookalike("Apex Global Private Limited", "Apex Global Pvt Ltd"),
      "look-alikes: g00gle and google are look-alikes; names with honest digits (34square, add360) and ordinary spelling differences are not")
check(C.mixed_alphabets("\u0410pex Global") and not C.mixed_alphabets("\u0410\u043f\u0435\u043a\u0441 Global") and C.hidden_characters("29AB\u200bC") and not C.hidden_characters("29ABC"),
      "look-alikes: a Cyrillic letter inside a Latin word and invisible characters are caught; a name wholly in another alphabet is left to a reviewer")

google = indian("Google India Private Limited", "GOOCI1234G", "72000123456702")
rejected = lambda d, code, history=(): (lambda v: v[0] == "Rejected" and code in v[2] and "rejected because" in v[3])(verdict(d, history))
check(verdict(google)[:2] == ("Approved", None), "look-alikes: the control vendor is approved")
check(rejected(dict(google, bank_account_name="G00gle India Private Limited"), "LOOKALIKE_NAME"), "look-alikes: a bank holder spelled g00gle against a company spelled google is rejected, not sent back")
check(verdict(indian("34square Private Limited", "SQUCS1234S", "72000123456703", holder="34SQUARE PVT LTD"))[:2] == ("Approved", None)
      and verdict(indian("add360 Private Limited", "ADDCA3601A", "72000123456704", holder="ADD360 PRIVATE LIMITED"))[:2] == ("Approved", None), "look-alikes: honest digits in names (34square, add360) are approved")
check(rejected(indian("add360 Private Limited", "ADDCA3601A", "72000123456704", holder="add36O Private Limited"), "LOOKALIKE_NAME"), "look-alikes: add360 against add36O is rejected")
check(rejected(dict(google, company_name="G\u043e\u043egle India Private Limited"), "HIDDEN_CHARACTERS"), "look-alikes: Cyrillic letters inside a Latin name are rejected")
check(rejected(dict(INDIA, tax_id="29ABCCAI234D1Z6"), "LOOKALIKE_CHARACTERS"), "look-alikes: a GSTIN with I for 1 is rejected, not sent back")
check(rejected(dict(INDIA, tax_id=INDIA["tax_id"][:5] + "\u200b" + INDIA["tax_id"][5:]), "HIDDEN_CHARACTERS")
      and rejected(dict(INDIA, tax_id="".join(chr(ord(c) + 0xFEE0) if c.isdigit() else c for c in INDIA["tax_id"])), "HIDDEN_CHARACTERS"), "look-alikes: an invisible character or full-width digits in an ID are rejected")
check(rejected(dict(google, bank_account_number="7200012345670O"), "LOOKALIKE_CHARACTERS") and rejected(dict(american("Redwood Supply LLC", "84-2736195", "4400555111"), bank_code="O21000021"), "LOOKALIKE_CHARACTERS"),
      "look-alikes: a letter O in a bank account number or routing number is rejected, so it cannot dodge the duplicate-account check")
check(verdict(dict(google, bank_account_number="12345"))[:3] == ("Rejected", None, ["BAD_ACCOUNT_FORMAT"]), "look-alikes: a bank account of the wrong length is an ordinary mistake, returned to the vendor")
check(rejected(indian("N0rthern Star Arms Trading Limited", "NORCN3459R", "72000123456705"), "SANCTIONS_MATCH"), "look-alikes: a look-alike spelling of a watchlist name does not escape the screening")
check(rejected(indian("Apex G1obal Private Limited", "APXCG9876A", "73100123456703"), "LOOKALIKE_OF_EXISTING_VENDOR", history=[APEX]), "look-alikes: a name that looks like an onboarded vendor's is rejected")
check(rejected(dict(INDIA, company_name="Apex G1obal Private Limited", bank_account_name="Apex G1obal Private Limited"), "LOOKALIKE_NAME"), "look-alikes: a name that differs from the tax registry only in look-alikes is rejected")

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
fixed = submit(american("Zenith Fabricators LLC", "04-2958371", "5100999111"), same_as=typo)
later = submit(american("Zenith Fabricators LLC", "04-2958371", "5100999111"))
check(run(typo)["vendor_id"].startswith("VUS") and run(fixed)["vendor_id"] == run(typo)["vendor_id"] == run(later)["vendor_id"], "vendor ID: a new application by the same applicant keeps the ID of the earlier one, and so does the company's next application")
keyless = dict(quartz, pan="")  # no PAN, so no company key to recognise it by
first_k, other_k = submit(keyless), submit(dict(keyless, company_name="Other Mills Private Limited"))
again_k = submit(keyless, same_as=first_k)
check(run(first_k)["vendor_id"] and run(first_k)["vendor_id"] != run(other_k)["vendor_id"] and run(again_k)["vendor_id"] == run(first_k)["vendor_id"], "vendor ID: even with no tax identity every applicant gets an ID, and a linked new application keeps it")

# ---- the vendor message is short and to the point
two = run_pipeline(dict(quartz, bank_account_name="Zenith Traders", documents=dict(quartz["documents"], voided_cheque=None)), [])["vendor_message"]
check(two == "Your application is rejected. We found these problems:\n1. Bank proof is missing: upload a voided cheque or passbook page\n2. Use a bank account in your company's name, or attach a signed authorisation letter\nThis application is now closed. Please correct the details and submit a new application.", "vendor message: two problems are a short numbered list, then what to do")
check(run_pipeline(dict(quartz, tax_id="123456789"), [])["vendor_message"].startswith("Your application is rejected. We found"), "vendor message: starts by saying the application is rejected")

check(outcome(dict(quartz, tax_id="123456789")) == ("Rejected", None) and "submit a new application" in run_pipeline(dict(quartz, tax_id="123456789"), [])["vendor_message"], "status definitions: one contradiction alone is rejected, with a new application invited")
check(outcome(dict(quartz, pan="ZZZZZ9999Z")) == ("Rejected", None), "status definitions: two contradictions at once are rejected")
near_miss = dict(quartz, bank_account_name="Quartz Mill Private Limited")
first_try = run_pipeline(near_miss, [])
check((first_try["status"], first_try["sub_status"]) == ("Rejected", None), "status definitions: a near-miss name is rejected with what to correct")
check(outcome(quartz) == ("Approved", None), "status definitions: a vendor who fixes it is approved")
mismatch = dict(quartz, bank_account_name="Zenith Traders")
check((run_pipeline(mismatch, [])["status"], run_pipeline(mismatch, [])["sub_status"]) == ("Rejected", None), "status definitions: a third-party bank account stays open for correction or authorisation evidence")

fixable = submit(dict(quartz, tax_id=quartz["tax_id"][:13]))
check(run(fixable)["final"] == "Rejected" and run(fixable)["waiting_on"] == "-", "status definitions: a correctable mistake is rejected and closed")

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

# ---- the app offers nine samples (one clean vendor, six edge cases and two review cases) and the corrected version of each edge case a vendor can fix
by_case = {case[0]: case for case in CASES}
shown = sorted(f[:-5] for f in os.listdir("sample_inputs"))
check(shown == sorted(file for file, _ in SAMPLES) and len(SAMPLES) == 5, "samples: the app offers 01 plus the four edge cases of the demo", f"-> {shown}")
check([by_case[case][3:5] for _, case in SAMPLES] == [("Approved", None), ("Rejected", None), ("Rejected", None), ("Rejected", None), ("Pending", "Needs review")],
      "samples: they cover approved, vendor correction (twice), terminal rejection and reviewer decision")
for file, case in SAMPLES:
    with open(f"sample_inputs/{file}.json", encoding="utf-8") as handle:
        check(json.load(handle) == json.loads(json.dumps(by_case[case][1])), f"samples: {file} is the tested case {case}")

# ---- web: the Flask routes, end to end ----
import app  # noqa: E402  (imported after the test database is set)

app.STAGE_PAUSE = 0
client = app.app.test_client()
app.app.config["RATE_LIMIT"] = 10 ** 6  # the rate limit has its own test below


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
check(done["error"] is None and len(done["stages"]) == 8 and b"Approved" in client.get(f"/run/{done['run_id']}").data, "web: a first application runs through 8 stages (repeat attempts only appears when there is an earlier attempt) and shows Approved")
done = run_case("12_review_bank_account_shared_with_another_vendor")
pending_id = done["run_id"]
check(pending_id.encode() in client.get("/review").data, "web: a pending run appears on the reviewer desk")
seen = client.get(f"/run/{pending_id}").data.decode()
check("Harbor Freight Private Limited" in seen and "27HARCF6789P" in seen and "****8912" in seen and "60200345678912" not in seen and "flagged" in seen and "not provided" in seen,
      "web: the submission is shown (company, IDs, masked bank account, flagged fields, missing documents) and the full account number never is")
check(b"enter your name" in client.post(f"/review/{pending_id}", data={"decision": "Approved", "note": "ok ok ok"}, follow_redirects=True).data, "web: a decision without a name is refused")
check(b"Take this submission" in client.post(f"/review/{pending_id}", data={"reviewer": "Asha", "decision": "Approved", "note": "Checked by phone"}, follow_redirects=True).data, "web: a reviewer must take a submission before deciding it")
client.post(f"/review/{pending_id}/claim", data={"reviewer": "Asha"})
check(b"independent verification method" in client.post(f"/review/{pending_id}", data={"reviewer": "Asha", "decision": "Approved", "note": "Checked by phone"}, follow_redirects=True).data,
      "web: a bank-risk case cannot be approved without independent verification")
check(b"Approved by Asha" in client.post(f"/review/{pending_id}", data={"reviewer": "Asha", "decision": "Approved", "note": "Owner confirmed", "verification_method": "known_contact"}, follow_redirects=True).data,
      "web: a claimed bank-risk case can be approved after independent verification")
check("Independent verification: Callback to a trusted contact." in run(pending_id)["decision_by"]["note"], "web: the verification method is kept in the audit trail")

form = {f: "" for f in app.FIELDS}
form.update(mode="form", company_name="Form Vendor LLC", country="US", tax_id="84-273619", tax_document=(io.BytesIO(b"%PDF-1.4 hello"), "w9.pdf"))
done = run_web(**form)
check(client.get(f"/doc/{done['run_id']}/tax_document").data == b"%PDF-1.4 hello", "web: an uploaded document can be downloaded back")
check(client.get(f"/correct/{done['run_id']}").status_code == 404, "web: there is no correction route any more; a rejected vendor applies again")
fixed_form = {f: "" for f in app.FIELDS}
fixed_form.update(mode="form", company_name="Form Vendor LLC", country="US", website="https://formvendor.example",
                  email="payables@formvendor.example", mobile="3125550101", address="100 Market Street, Chicago, IL 60601", tax_id="74-8926371",
                  bank_account_name="Form Vendor LLC", bank_account_number="5100234567", bank_code="021000021",
                  tax_document=(io.BytesIO(b"%PDF-1.4 tax"), "w9.pdf"),
                  registration=(io.BytesIO(b"%PDF-1.4 registration"), "registration.pdf"),
                  voided_cheque=(io.BytesIO(b"%PDF-1.4 bank"), "bank.pdf"))
fixed_done = run_web(**fixed_form)
old_run, fixed_run = run(done["run_id"]), run(fixed_done["run_id"])
check(old_run["final"] == "Rejected" and old_run["waiting_on"] == "-" and fixed_run["final"] == "Approved" and fixed_done["run_id"] != done["run_id"]
      and {d["slot"] for d in store.get_docs(fixed_done["run_id"])} == {"tax_document", "registration", "voided_cheque"},
      "web: the new application is a separate submission, checked from scratch; the rejected one stays rejected and closed")
check("Submission " + fixed_done["run_id"] in client.get(f"/run/{fixed_done['run_id']}").data.decode() and b"Correct application" not in client.get(f"/run/{done['run_id']}").data,
      "web: no correction button anywhere; a rejected result tells the vendor to apply again")
check(client.get("/export.csv").data.startswith(b"submission id,vendor id,submitted at,company"), "web: CSV export works")
check(b"Form Vendor LLC" in client.get("/dashboard").data and b"Sorted without a reviewer" in client.get("/dashboard").data and b"****" not in client.get("/export.csv").data, "web: dashboard lists the runs")
client.post("/reset")
check(b"No submissions yet" in client.get("/dashboard").data, "web: reset empties the dashboard again")

# Vercel cannot keep working in a background thread after returning a response. It completes the same pipeline synchronously and returns the result HTML.
os.environ["VERCEL"] = "1"
serverless = client.post("/api/submit", data={"mode": "sample", "sample": "01_approved_india_clean.json"}).get_json()
check(serverless["progress"]["done"] and serverless["progress"]["run_id"] and "Approved" in serverless["result_html"],
      "Vercel: a submission completes in one request and returns its rendered result")
check(store.query("SELECT status, transport FROM outbox") == [{"status": "sent", "transport": "simulated"}],
      "Vercel: the outbox is delivered synchronously instead of relying on a background thread")
os.environ.pop("VERCEL")
client.post("/reset")

# a near-miss name: the application stays open with a clear correction path
first = run_case("09_fix_near_miss_name")["run_id"]
check(run(first)["final"] == "Rejected" and run(first)["waiting_on"] == "-" and b"match your company name exactly" in client.get(f"/run/{first}").data
      and b"submit a new application" in client.get(f"/run/{first}").data and b"Correct application" not in client.get(f"/run/{first}").data,
      "web: a near-miss name is rejected with the exact correction and an invitation to apply again")

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

client.post(f"/review/{clash}/claim", data={"reviewer": "Asha"})
page = client.post(f"/review/{clash}", data={"reviewer": "Asha", "decision": "Info requested", "note": "Send a bank letter", "sort": "oldest"}, follow_redirects=True).data
check(f">{contact}</a>" in page.decode(), "reviewer desk: after a decision the next submission opens")
check(run(clash)["final"] == "Rejected" and run(clash)["final_sub"] == "Information needed", "reviewer desk: info requested closes the run as rejected")
done_page = client.post(f"/review/{clash}", data={"reviewer": "Priya", "decision": "Rejected", "note": "Vendor never replied"}, follow_redirects=True).data
check(b"no longer waiting for a reviewer" in done_page, "reviewer desk: a closed run cannot be decided again")
client.post("/reset")


# ---- the form-submission kit: a clean vendor's values and four sample PDFs, used exactly as a person would use the form
kit_dir = "demo_form_submission"
with open(f"{kit_dir}/vendor_submission.json", encoding="utf-8") as handle:
    kit = json.load(handle)
pdf_files = {slot: f"{kit_dir}/{doc['filename']}" for slot, doc in kit["documents"].items()}
pdf_bytes = {slot: open(path, "rb").read() for slot, path in pdf_files.items()}
check(len(pdf_files) == 4 and all(data.startswith(b"%PDF-") and b"SAMPLE DOCUMENT FOR DEMONSTRATION ONLY" in data for data in pdf_bytes.values()), "kit: four sample PDFs exist, are real PDFs, and are marked as fictional samples")
check(kit["tax_id"].encode() in pdf_bytes["tax_document"] and kit["company_name"].encode() in pdf_bytes["registration"] and kit["bank_account_number"].encode() in pdf_bytes["voided_cheque"]
      and kit["bank_code"].encode() in pdf_bytes["passbook"], "kit: the documents show the same GSTIN, company name, account number and IFSC as the form values")
check(run_pipeline(kit, SEED)["status"] == "Approved", "kit: the JSON file is approved")
form = {f: kit.get(f) or "" for f in app.FIELDS}
form.update(mode="form", **{slot: (io.BytesIO(pdf_bytes[slot]), os.path.basename(path)) for slot, path in pdf_files.items()})
filled = run_web(**form)["run_id"]
check(next(r for r in store.load_runs() if r["run_id"] == filled)["final"] == "Approved" and {d["slot"] for d in store.get_docs(filled)} == set(pdf_files), "kit: typed into the form with the four PDFs uploaded, it is approved and the PDFs are kept for a reviewer")

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
mailer.deliver_queued()
check(not hasattr(mailer, "sweep") and [row["event"] for row in outbox()] == ["verdict", "verdict"], "outbox: there are no reminder mails and no closing notices, only a verdict per submission")

reviewing = run_case("12_review_bank_account_shared_with_another_vendor")["run_id"]
mailer.deliver_queued()
page = client.get("/messages").data.decode()
check("Simulated: no mail service" in page and "accounts@apexglobal.example" in page and "Sent (simulated)" in page and page.count("Your application is approved.") == 1, "messages: the page says the mail service is simulated, shows who it is to, and the status of each message")
check("Your application is under review. We will reach back to you if anything is needed." in page and "submit a new application." in page and "Reminder" not in page,
      "messages: under review and the rejection (with a new-application invitation) both went out, and no reminder")
shown_to_vendor = "Your application is under review. We will reach back to you if anything is needed."
check(shown_to_vendor in client.get(f"/run/{reviewing}").data.decode() and shown_to_vendor not in client.get(f"/review?run={reviewing}").data.decode()
      and shown_to_vendor not in client.get(f"/dashboard?run={reviewing}").data.decode(), "the vendor's message shows on the vendor's result page, not on the reviewer desk or the dashboard detail")

client.post(f"/review/{reviewing}/claim", data={"reviewer": "Asha"})
client.post(f"/review/{reviewing}", data={"reviewer": "Asha", "decision": "Approved", "note": "Owner confirmed", "verification_method": "bank_confirmation"})
rejecting = run_case("14_review_shared_mobile_number")["run_id"]
client.post(f"/review/{rejecting}/claim", data={"reviewer": "Asha"})
client.post(f"/review/{rejecting}", data={"reviewer": "Asha", "decision": "Rejected", "note": "internal: looks like a shell company"})
asking = run_case("13_review_company_id_under_new_name")["run_id"]
client.post(f"/review/{asking}/claim", data={"reviewer": "Asha"})
client.post(f"/review/{asking}", data={"reviewer": "Asha", "decision": "Info requested", "note": "internal: check the certificate"})
check(all(row["status"] == "queued" for row in of(reviewing)[1:] + of(rejecting)[1:] + of(asking)[1:]) and len(of(asking)) == 2, "outbox: a reviewer's decision queues a message to the vendor automatically")
mailer.deliver_queued()
page = client.get("/messages").data.decode()
check(page.count("Your application is approved.") == 2, "messages: a reviewer's approval is sent to the vendor")
check("Your application is rejected because we could not verify your contact details." in page, "messages: a reviewer's rejection tells the vendor the reason, worked out from the findings")
check("1. your company registration certificate showing your current legal name" in page and "Please submit a new application with them." in page, "messages: a request for more information closes the application, lists the documents needed and asks for a new application")
check("internal:" not in page and "different company" not in page and "another vendor" not in page, "messages: nothing the reviewer typed, and nothing about other vendors, reaches the vendor")
check("internal:" not in client.get(f"/run/{rejecting}").data.decode() and "internal:" not in client.get(f"/run/{asking}").data.decode(),
      "vendor pages: reviewer notes never leak after a decision")

by_thread = {t["id"]: t for t in mailer.threads()}
thread = by_thread[reviewing]
check([m["run_id"] for m in thread["messages"]] == [reviewing, reviewing] and thread["messages"][0]["subject"] == f"Your vendor application ({reviewing})"
      and thread["messages"][1]["subject"] == f"Re: Your vendor application ({reviewing})", "messages: the reviewer's outcome is a reply in the same thread, with the same subject and Re:")
check(len(by_thread) == len(store.load_runs()), "messages: exactly one thread per application")

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
mine = run_web(mode="json", json_file=(io.BytesIO(json.dumps(dict(CASE["14_review_shared_mobile_number"], email="shubham@example.org")).encode()), "mine.json"))["run_id"]
client.post(f"/review/{mine}/claim", data={"reviewer": "Asha"})
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

# ---- the vendor message for an incomplete form is plain and specific
from samples import incomplete_form
text = run_pipeline(incomplete_form(), [])["vendor_message"]
check(text == "Your application is rejected. We found these problems:\n1. Email is missing\n2. Tax ID is missing\n3. Bank proof is missing: upload a voided cheque or passbook page\n"
      "4. The document was declared as tax document but placed in the Registration document field\nThis application is now closed. Please correct the details and submit a new application.", "vendor message: an incomplete form lists plainly what is missing and where to upload", text)

# ---- already registered, hidden vendor ID, and what a reviewer is shown when an onboarded vendor's details differ
store.reset()
for name_ in ("01_approved_india_clean", "01_approved_india_clean"):
    last = run_case(name_)["run_id"]
page = client.get(f"/run/{last}").data.decode()
check(run(last)["final_sub"] == "Already registered" and "You are already registered with us" in page, "web: an exact repeat shows 'already registered' on the vendor's page")
check(run(last)["vendor_id"] and run(last)["vendor_id"] not in page and "Vendor VIN" not in page, "web: the vendor never sees a vendor ID")
check(run(last)["vendor_id"] in client.get("/dashboard").data.decode(), "web: the dashboard (for staff) still shows the vendor ID")
store.reset()
store.save_run(INDIA, run_pipeline(INDIA, store.known_vendors([])), 0.01)  # Apex Global is on file
onboarded = [{"company_key": "ABCCA1234D", "company_name": INDIA["company_name"], "bank_account_number": INDIA["bank_account_number"], "mobile": INDIA["mobile"], "email": INDIA["email"], "address": INDIA["address"]}]
changed = run_pipeline(dict(INDIA, company_name="Apex Holdings", bank_account_number="60100987654321", mobile="9000012345"), onboarded)
note = next(f["message"] for f in changed["findings"] if f["code"] == "DUPLICATE_KEY_NEW_NAME")
check("Same: company ID, email, address." in note and "company name (Apex Global \u2192 Apex Holdings)" in note and "bank account (****7891 \u2192 ****4321)" in note and "phone" in note.split("Different:")[1],
      "reviewer note: same company ID, different name and details lists what is the same and what differs", note)
clone = dict(indian("Apex Global Private Limited", "ZZYCA9999Z", "40100999999999", mobile="9000099999", email="other@elsewhere.example"), address=INDIA["address"])
res = run_pipeline(clone, onboarded)
note = next(f["message"] for f in res["findings"] if f["code"] == "SAME_NAME_DIFFERENT_COMPANY_ID")
check((res["status"], res["sub_status"]) == ("Pending", "Needs review") and "same address" in note and "Same: company name, address." in note and "company ID (ABCCA1234D" in note,
      "same name and address as an onboarded vendor but a different company ID goes to a reviewer, with what is the same and different", note)
name_only = indian("Apex Global Private Limited", "ZZYCA9999Z", "40100999999999", mobile="9000099999", email="other@elsewhere.example", address="77 Park Street, Kolkata 700016")
check("SAME_NAME_DIFFERENT_COMPANY_ID" not in [f["code"] for f in run_pipeline(name_only, onboarded)["findings"]], "the same name alone is not enough: many unrelated companies share a name")
store.reset()

# ---- the payment-fraud sample (06), used as a person would: submit 01 first, then 06
client.post("/reset")
run_web(mode="sample", sample="01_approved_india_clean.json")
reviewed = run_web(mode="sample", sample="06_edge_existing_vendor_changes_bank_account.json")["run_id"]
check(run(reviewed)["final"] == "Pending" and run(reviewed)["waiting_on"] == "Reviewer" and "BANK_DETAILS_CHANGED" in run(reviewed)["codes"] and f">{reviewed}</a>" in client.get("/review").data.decode(),
      "sample 06: goes to the reviewer desk with BANK_DETAILS_CHANGED")
check("Same:" in " ".join(f["message"] for f in run(reviewed)["findings"]) and "Different:" in " ".join(f["message"] for f in run(reviewed)["findings"]), "sample 06: shows the reviewer what is the same and what differs")
check("under review" in client.get(f"/run/{reviewed}").data.decode() and run(reviewed)["vendor_id"] not in client.get(f"/run/{reviewed}").data.decode(), "sample 06: tells the vendor only 'under review'")
client.post("/reset")

# ---- the repeat-attempts stage is internal: recorded for staff, never shown to the vendor
client.post("/reset")
one = run_web(mode="sample", sample="03_edge_tax_id_wrong_for_country.json")
two = run_web(mode="sample", sample="03_edge_tax_id_wrong_for_country.json")
check(all("repeat attempts" not in [x["name"] for x in r["stages"]] and len(r["stages"]) == 8 for r in (one, two)), "vendor view: the live view never shows the repeat-attempts stage")
check("repeat_attempts" not in [x["stage"] for x in run(one["run_id"])["decision"]["stages"]] and "repeat_attempts" in [x["stage"] for x in run(two["run_id"])["decision"]["stages"]],
      "repeat attempts: recorded for staff only once an earlier rejected application exists")
vendor_page = client.get(f"/run/{two['run_id']}").data.decode()
staff_page = client.get(f"/dashboard?run={two['run_id']}").data.decode()
check("Reviewer view" not in vendor_page and "repeat attempts" not in vendor_page and 'badge orange">flagged' not in vendor_page and "Vendor VIN" not in vendor_page, "vendor view: no reviewer view, no internal stage, no flagged marks, no vendor ID")
check("Reviewer view" in staff_page and 'badge orange">flagged' in staff_page, "staff view (dashboard detail): shows the reviewer view and the flags")
client.post("/reset")

# ---- an onboarded company and review cases are not 'attempts': no double flag
store.reset()
seen_codes = []
for sample_name in ["01_approved_india_clean", "06_edge_existing_vendor_changes_bank_account", "06_edge_existing_vendor_changes_bank_account"]:
    history_ = store.load_runs()
    with open(f"sample_inputs/{sample_name}.json", encoding="utf-8") as handle_:
        data_ = json.load(handle_)
    result_ = run_pipeline(data_, store.known_vendors(history_), history_)
    store.save_run(data_, result_, 0.01)
    seen_codes.append([stage_["stage"] for stage_ in result_["stages"] if stage_["stage"] == "repeat_attempts"])
check(all(not codes_ for codes_ in seen_codes), "no double flag: review samples of an onboarded company never trigger the repeat-attempts stage")
store.reset()
base_ = fresh(copy.deepcopy(INDIA), "Ridge Fabrics Private Limited", "RIDCF3456R", "71100234567891")
terminal_ = dict(base_, tax_id="61-4827395", pan="ZZZZZ9999Z")
store.save_run(terminal_, run_pipeline(terminal_, store.known_vendors([])), 0.01)
pending_ = dict(terminal_, mobile="9876500011")
history_ = store.load_runs()
store.save_run(pending_, run_pipeline(pending_, store.known_vendors(history_), history_), 0.01)
check(sum(1 for r in store.load_runs() if r["final"] == "Rejected") == 2, "attempts: both earlier applications were rejected, so both count")
store.reset()

# ---- repeat attempts: every rejected application followed by a new one is linked for staff
import checks as _checks
tries = []
base = fresh(copy.deepcopy(INDIA), "Ember Textiles Private Limited", "EMBCT5678E", "70100234567891")
bad_tax = dict(base, tax_id="29EMBCT5678E1Z1")  # wrong check character: rejected, the vendor must fix the tax ID
def attempt(data, extra=()):
    """One more application, checked against what exists so far (as the app does), then saved."""
    history = store.load_runs()
    decision = run_pipeline(data, store.known_vendors(history), history)
    rid = store.save_run(data, decision, 0.01)
    return decision, rid
d1, r1 = attempt(bad_tax)
check((d1["status"], d1["sub_status"]) == ("Rejected", None) and not any(f["code"] in ("REPEATED_ATTEMPTS", "IDENTITY_CHANGED_BETWEEN_ATTEMPTS") for f in d1["findings"]), "attempts: a correctable first application has no attempt findings")
d2, r2 = attempt(base)  # the vendor corrected exactly the tax ID they were asked to correct
check(d2["status"] == "Approved", "attempts: fixing exactly what was wrong gives a clean result")
store.reset()
terminal = dict(base, tax_id="61-4827395", pan="ZZZZZ9999Z")
d1, r1 = attempt(terminal)
d2, r2 = attempt(dict(terminal, mobile="9876500001"))
d3, r3 = attempt(dict(terminal, mobile="9876500002"))
d4, r4 = attempt(base)
check(all(d["status"] == "Rejected" for d in (d1, d2, d3)), "attempts: three terminally rejected fresh applications are counted")
check(d4["sub_status"] == "Needs review" and "REPEATED_ATTEMPTS" in [f["code"] for f in d4["findings"]], "attempts: a clean 4th fresh application goes to a reviewer")
d5, _ = attempt(base)  # the 5th is perfectly clean
check((d5["status"], d5["sub_status"]) == ("Pending", "Needs review"), "attempts: a perfect 5th attempt is NOT approved automatically, a reviewer decides")
check("under review" in d5["vendor_message"] and "attempt" not in d5["vendor_message"].lower(), "attempts: the vendor is only told it is under review, never why")
store.reset()
a1, _ = attempt(terminal)
swap, _ = attempt(dict(base, bank_account_number="70100999999999"))  # bank account was not one of the rejected fields
check("IDENTITY_CHANGED_BETWEEN_ATTEMPTS" in [f["code"] for f in swap["findings"]] and swap["sub_status"] == "Needs review", "attempts: changing the bank account between attempts goes to a reviewer")
store.reset()
attempt(dict(base, company_name="N0rthern Star Arms Trading Limited", bank_account_name="N0rthern Star Arms Trading Limited"))
again_hard, _ = attempt(dict(base, company_name="Northern Star Arms Trading Limited", bank_account_name="Northern Star Arms Trading Limited"))
check("SERIOUS_EARLIER_REJECTION" in [f["code"] for f in again_hard["findings"]], "attempts: an applicant earlier stopped for a serious reason is never approved automatically")
store.reset()
other = indian("Different Spices Private Limited", "DIFSC9999D", "70100234567999", mobile="9000099999", email="info@different.example")
attempt(base)
approved_first = store.load_runs()[0]
check(approved_first["final"] == "Approved" and not _checks.check_attempts(base, store.load_runs())["findings"], "attempts: an approved application is not an attempt (the duplicate check handles it)")
store.reset()
attempt(dict(base, mobile="9000000001", email="a@x.example", company_name="Ember Textiles Private Limited", bank_account_name="Ember Textile Private Limited"))
check(not _checks.link_reasons(other, store.load_runs()[0]), "attempts: an unrelated company is not linked")
check("company name" in _checks.link_reasons(dict(other, company_name="Ember Textile Private Limited"), store.load_runs()[0]), "attempts: a near-identical name links two applications even when every ID differs")
doc_a = {"tax_document": {"filename": "a.pdf", "sha256": "abc"}}
check("uploaded file" in _checks.link_reasons(dict(other, documents=doc_a), {"payload": dict(base, documents=doc_a)}), "attempts: the same uploaded file links two applications")
store.reset()
app.app.config["RATE_LIMIT"] = 2
app.SEEN.clear()
codes = [client.post("/api/submit", data={"mode": "sample", "sample": "01_approved_india_clean.json"}).status_code for _ in range(3)]
check(codes == [200, 200, 429], "rate limit: the third submission in an hour from one source is refused")
app.app.config["RATE_LIMIT"] = 10 ** 6
client.post("/reset")

# ---- round-trip budget: on a remote database (Postgres on Vercel) every statement is a network call, so a submit and a page load must stay cheap
time.sleep(1.0)  # let any worker threads started by the earlier tests finish, so only this submit is counted
store.reset()
store.query("SELECT 1 FROM vendors")
counted = []
store._shared["conn"].set_trace_callback(lambda statement: counted.append(" ".join(statement.strip().split()[:4]).upper()))
os.environ["VERCEL"] = "1"
try:
    run_web(mode="sample", sample="02_edge_incomplete_form_wrong_document.json")
    submit_statements = len([x for x in counted if x not in ("BEGIN", "COMMIT")])
    counted.clear()
    client.get("/about")
    client.get("/about")
    page_statements = len([x for x in counted if x not in ("BEGIN", "COMMIT")])
finally:
    os.environ.pop("VERCEL", None)
    store._shared["conn"].set_trace_callback(None)
check(submit_statements <= 11, "round trips: a submit makes at most 11 SQL statements (it was about 43, then 19)", submit_statements)
check(page_statements <= 3, "round trips: two page loads make at most 3 statements (the nav badge count is cached)", page_statements)
store.reset()
check(len(store.known_vendors([])) == 1, "round trips: reset restores the vendors on file at once, with no per-call check")

# ---- the database cost of each request is reported in the standard Server-Timing header
header = client.post("/api/submit", data={"mode": "sample", "sample": "01_approved_india_clean.json"}, content_type="multipart/form-data").headers.get("Server-Timing", "")
check(header.startswith("db;dur=") and "commit;dur=" in header and "connect;dur=" in header and "statements" in header, "server timing: submit reports what the database cost", header)
store.reset()

# ---- Postgres: leaving a write block must commit but NOT close the shared connection (psycopg's own context manager closes it)
class FakePostgres:
    """Behaves like a psycopg connection where it matters here: its context manager closes it."""
    def __init__(self):
        self.closed, self.log = False, []
    def commit(self): self.log.append("commit")
    def rollback(self): self.log.append("rollback")
    def __enter__(self): return self
    def __exit__(self, *exc): self.closed = True

saved = dict(store._shared)
fake = FakePostgres()
store._shared.update(conn=fake, postgres=True)
try:
    with store.Handle():
        pass
    committed_open = (list(fake.log), fake.closed)
    try:
        with store.Handle():
            raise ValueError("boom")
    except ValueError:
        pass
    rolled_back_open = (list(fake.log), fake.closed)
finally:
    store._shared.update(saved)
check(committed_open == (["commit"], False), "postgres: a successful write block commits and leaves the shared connection open", committed_open)
check(rolled_back_open == (["commit", "rollback"], False), "postgres: a failed write block rolls back and leaves the shared connection open", rolled_back_open)

# ---- the Onboard page: one JSON file tab with the sample chooser and the file picker; nothing is pre-selected
home = client.get("/").get_data(as_text=True)
tab_form = home[home.index('id="tab-sample"'):]
tab_form = tab_form[:tab_form.index("</form>")]
check('data-tab="tab-sample">JSON file<' in home and 'data-tab="tab-json"' not in home, "tab: a single JSON file tab, as before")
check('name="sample"' in tab_form and 'type="file"' in tab_form and 'value="" selected disabled>Select a sample' in tab_form, "tab: the sample chooser and the file picker are together, with no sample pre-selected")
check(client.post("/api/submit", data={"mode": "sample"}, content_type="multipart/form-data").get_json()["error"] == "Select a sample or choose a JSON file first", "tab: submitting with neither a sample nor a file says to choose one")
mine_json = dict(CASE["14_review_shared_mobile_number"], company_name="Uploaded Through The JSON Tab Private Limited", bank_account_name="Uploaded Through The JSON Tab Private Limited")
uploaded = run_web(mode="json", json_file=(io.BytesIO(json.dumps(mine_json).encode()), "mine.json"))["run_id"]
check(run(uploaded)["company"] == "Uploaded Through The JSON Tab Private Limited", "tab: a chosen file is the one that is processed")
check("data.set('mode', 'json')" in open("static/app.js", encoding="utf-8").read(), "tab: the page switches to file mode when a file is chosen")
store.reset()

# ---- serverless mail: a simulated message is stored as sent in one step, and a later message in the same thread is still "Re:"
os.environ["VERCEL"] = "1"
try:
    store.reset()
    thread_run = run_case("14_review_shared_mobile_number")["run_id"]
    client.post(f"/review/{thread_run}/claim", data={"reviewer": "Asha"})
    client.post(f"/review/{thread_run}", data={"reviewer": "Asha", "decision": "Rejected", "note": "not a real company"})
    rows = [row for row in outbox() if row["run_id"] == thread_run]
finally:
    os.environ.pop("VERCEL", None)
check(len(rows) == 2 and all(row["status"] == "sent" and row["transport"] == "simulated" and row["attempts"] == 1 and row["sent_at"] for row in rows), "serverless mail: simulated messages are stored as sent in one step", [r["status"] for r in rows])
check(not rows[0]["subject"].startswith("Re:") and rows[1]["subject"].startswith("Re: ") and rows[0]["thread_id"] == rows[1]["thread_id"], "serverless mail: the second message of a thread is a Re: reply, chosen inside the insert")
store.reset()

# ---- terminal rejections are written for the vendor: they name what disagrees and say what happens next
two = run_pipeline(CASE["19_reject_two_contradictions"], SEED)["vendor_message"]
check(two == "Your application is rejected because some of the details you entered do not agree with each other:\n1. The PAN inside your GSTIN differs from the PAN you gave\n"
      "2. Your PAN is not a company PAN (its 4th letter should be C)\nThis application is now closed. Please correct the details and submit a new application.",
      "vendor message: two contradictions are named in plain words, with what to do next", two)
check("contradict each other" not in two and "1. " in two and "2. " in two, "vendor message: no vague 'the details contradict each other'")
sanction = run_pipeline(CASE["21_reject_sanctions_name_match"], SEED)["vendor_message"]
check(sanction == "Your application is rejected because we are unable to onboard this company.\nThis application is now closed.", "vendor message: a sanctions rejection stays vague and does not invite a new application", sanction)
cancelled = run_pipeline(CASE["23_reject_cancelled_registration"], SEED)["vendor_message"]
check("your tax registration is shown as cancelled or inactive" in cancelled and cancelled.endswith("submit a new application."), "vendor message: a fixable hard stop says why and that a new application is possible", cancelled)

print("ALL PASSED" if not failed else f"FAILED: {failed}")
sys.exit(1 if failed else 0)
