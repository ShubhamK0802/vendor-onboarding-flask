"""The demo vendors. CASES is the full test matrix (every rule has a case); only the six SAMPLES below are shown in the app.
`python samples.py` writes the six sample files, the demo registry and the demo watchlist.

Sample files:        sample_inputs/*.json
Demo tax registry:   registry.json   (SIMULATED: a real deployment calls the tax authorities)
Demo watchlist:      sanctions.json  (FICTIONAL names: a real deployment screens against the official OFAC / EU / UN lists)
"""
import copy
import json
import os

from checks import german_vat_check_digit, gstin_check_char
from config import VENDORS_ON_FILE
from normalize import normalize_id

DEMO_WATCHLIST = ["Northern Star Arms Trading", "Red Falcon Shipping", "Zarya Oilfield Logistics", "Meridian Gulf Petrochemicals"]


def docs(prefix, cheque=True):
    def one(kind, size, slot):
        return {"filename": f"{prefix}_{kind}.pdf", "file_type": "pdf", "size_bytes": size, "declared_type": slot}
    return {"tax_document": one("tax", 184320, "tax_document"), "registration": one("registration", 220160, "registration"),
            "voided_cheque": one("cheque", 98304, "voided_cheque") if cheque else None, "passbook": None}


def gstin_for(pan, state="27"):
    return state + pan + "1Z" + gstin_check_char(state + pan + "1Z")


def make_iban(country, bban):
    """ISO 13616: the 2 check digits come from mod 97 over the account part, then the country letters, then 00."""
    digits = "".join(str(int(ch, 36)) for ch in bban + country) + "00"
    return f"{country}{98 - int(digits) % 97:02d}{bban}"


def indian(name, pan, account, mobile=None, email=None, address="12 MG Road, Bengaluru, Karnataka 560001", entity="company", holder=None, state="27", ifsc="HDFC0001234"):
    slug = name.split()[0].lower()
    return {"company_name": name, "entity_type": entity, "country": "IN", "email": email or f"accounts@{slug}.example", "mobile": mobile or "98" + account[-8:],
            "address": address, "tax_id": gstin_for(pan, state), "pan": pan, "bank_account_name": holder or name, "bank_account_number": account,
            "bank_code": ifsc, "website": f"https://www.{slug}.example", "documents": docs(slug)}


def american(name, ein, account, mobile="2125550143", routing="021000021"):
    slug = name.split()[0].lower()
    return {"company_name": name, "entity_type": "company", "country": "US", "email": f"ap@{slug}.example", "mobile": mobile,
            "address": "250 Hudson Street, New York, NY 10013", "tax_id": ein, "pan": None, "bank_account_name": name, "bank_account_number": account,
            "bank_code": routing, "website": f"https://www.{slug}.example", "documents": docs(slug)}


def german(name, base8, bban, bic, holder=None, iban=None, swap=False):
    """base8 is the 8 digits after DE; swap=True transposes two of them after the check digit was computed (a typing slip)."""
    check = german_vat_check_digit(base8)
    typed = base8[:2] + base8[3] + base8[2] + base8[4:] if swap else base8
    slug = name.split()[0].lower().replace("ü", "ue")
    return {"company_name": name, "entity_type": "company", "country": "DE", "email": f"ap@{slug}.example", "mobile": "+4915112345" + base8[:3],
            "address": "Hafenstrasse 12, 20457 Hamburg", "tax_id": f"DE{typed}{check}", "pan": None, "bank_account_name": holder or name,
            "bank_account_number": iban or make_iban("DE", bban), "bank_code": bic, "website": f"https://www.{slug}.example", "documents": docs(slug)}


# ---- kept for the tests: one Indian company that is "on file" once it has been approved
INDIA = indian("Apex Global Private Limited", "ABCCA1234D", "50100234567891", mobile="9876501234", email="accounts@apexglobal.example")
INDIA["tax_id"] = "29ABCCA1234D1Z6"  # a Karnataka registration (state 29)
ORION = VENDORS_ON_FILE[0]
APEX = {"company_key": "ABCCA1234D", "company_name": INDIA["company_name"], "bank_account_number": INDIA["bank_account_number"],
        "mobile": INDIA["mobile"], "email": INDIA["email"], "address": INDIA["address"]}
SEED = [ORION]


def fresh(d, name, pan, account, mobile=None, email=None, us=False):
    """Give a company its own identity (used by the tests)."""
    slug = name.split()[0].lower()
    d.update(company_name=name, bank_account_name=name, bank_account_number=account, mobile=mobile or "98" + account[-8:], email=email or f"ap@{slug}.example")
    if us:
        d["tax_id"] = pan
    else:
        d.update(pan=pan, tax_id=gstin_for(pan))
    return d


def short_tax_id(d):
    d["tax_id"] = d["tax_id"][:13]


def edit(data, **changes):
    data = copy.deepcopy(data)
    data.update(changes)
    return data


def wrong_slot():
    d = indian("Delta Pumps Private Limited", "DELCP3456L", "72000123456702")
    d["documents"]["registration"]["declared_type"] = "tax_document"  # an incorporation certificate uploaded into the tax-document slot
    return d


def incomplete_form():
    """No email, no tax ID, no bank proof, and the registration certificate uploaded in the tax-document slot."""
    d = wrong_slot()
    d.update(email="", tax_id="")
    d["documents"]["voided_cheque"] = None
    return d


def demo_form_vendor():
    """The vendor in demo_form_submission/: a clean Indian company, approved when its form is filled in and its four PDFs are uploaded."""
    return indian("Horizon Textiles Private Limited", "HORCH7421J", "83000123456715", mobile="9822012345", email="accounts@horizontextiles.example",
                  address="Plot 21, Industrial Estate, Pune, Maharashtra 411019", ifsc="ICIC0001234")


# (file name, submission, vendors already known to the system, expected status, expected reason, demo-registry override)
CASES = [
    # ---------------- Approved: nothing wrong
    ("01_approved_india_clean", INDIA, SEED, "Approved", None, None),
    ("02_approved_us_clean", american("Brightwave Supplies LLC", "84-2736195", "4400123987"), SEED, "Approved", None, None),
    ("03_approved_germany_umlaut_names", german("Müller Söhne GmbH", "27184635", "120300000000202051", "BYLADEM1001", holder="Mueller Soehne GmbH"), SEED, "Approved", None, None),
    # ---------------- Rejected: only mistakes or gaps the vendor can correct (the message lists them; the vendor files a new application)
    ("04_fix_us_ein_dropped_zero", american("Pioneer Packaging LLC", "42958371", "5100234567", mobile="3125550101"), SEED, "Rejected", None, None),
    ("05_fix_wrong_document_in_slot", wrong_slot(), SEED, "Rejected", None, None),
    ("06_fix_german_vat_typo", german("Rheinblick Maschinen GmbH", "47382915", "100000000123456789", "MARKDEF1100", swap=True), SEED, "Rejected", None, None),
    ("07_fix_us_company_with_indian_gstin", edit(american("Redwood Supply LLC", "x", "4400555111", mobile="3105550188"), tax_id=gstin_for("RDWCS6789L", "29")), SEED, "Rejected", None, None),
    ("08_fix_third_party_bank_account", indian("Greenfield Agro Private Limited", "GRECG4567M", "73000123456703", holder="Sharma & Associates Chartered Accountants"), SEED, "Rejected", None, None),
    ("09_fix_near_miss_name", indian("Lumina Global Private Limited", "LUMCG5678N", "74000123456704", holder="Lumina Globe Private Limited"), SEED, "Rejected", None, None),
    ("10_fix_trade_name_not_legal_name", indian("Sundara Silks", "SUNCT4567M", "75000123456705"), SEED, "Rejected", None, {"name": "Sundara Textiles Private Limited"}),
    # ---------------- Pending: Needs review (only our staff can settle it)
    ("11_review_existing_vendor_changes_bank_account", edit(INDIA, bank_account_number="60100987654321"), SEED + [APEX], "Pending", "Needs review", None),
    ("12_review_bank_account_shared_with_another_vendor", indian("Harbor Freight Private Limited", "HARCF6789P", ORION["bank_account_number"]), SEED, "Pending", "Needs review", None),
    ("13_review_company_id_under_new_name", edit(INDIA, company_name="Apex Holdings", bank_account_name="Apex Holdings"), SEED + [APEX], "Pending", "Needs review", None),
    ("14_review_shared_mobile_number", indian("Quill Stationers Private Limited", "QUICS0123T", "78000123456708", mobile=ORION["mobile"]), SEED, "Pending", "Needs review", None),
    ("15_review_sole_proprietor_personal_account", indian("Kumar Hardware Traders", "RAJPK4821H", "76000123456706", entity="sole_proprietor", holder="Rajesh Kumar"), SEED, "Pending", "Needs review", None),
    ("16_review_unsupported_country", edit(indian("Atlas Metals Private Limited", "ATLCM7890Q", "75000123456709"), country="BR"), SEED, "Pending", "Needs review", None),
    ("17_review_german_company_foreign_bank", german("Kraftwerk Tools GmbH", "31987654", "", "WESTGB2LXXX", iban="GB82WEST12345698765432"), SEED, "Pending", "Needs review", None),
    ("18_review_possible_sanctions_match", indian("Northern Star Arm Trading Limited", "NORCN3456R", "77000123456707"), SEED, "Pending", "Needs review", None),
    # ---------------- Rejected: cannot be approved as submitted, and a correction or a review would not change that
    ("19_reject_two_contradictions", edit(indian("Cobalt Tools Private Limited", "COBCT9012S", "79000123456711"), pan="ZZZZZ9999Z"), SEED, "Rejected", None, None),
    ("20_reject_duplicate_application", INDIA, SEED + [APEX], "Rejected", None, None),
    ("21_reject_sanctions_name_match", indian("Northern Star Arms Trading Limited", "NORCN3457R", "80000123456712"), SEED, "Rejected", None, None),
    ("22_reject_embargoed_bank_country", german("Hansa Bauteile GmbH", "58261937", "", "BKMTIRTHXXX", iban=make_iban("IR", "0120000000012345678901")), SEED, "Rejected", None, None),
    ("23_reject_cancelled_registration", indian("Orbit Exports Private Limited", "ORBCO5612S", "81000123456713"), SEED, "Rejected", None, {"status": "cancelled"}),
    ("24_reject_placeholder_tax_id", american("Summit Tools LLC", "12-3456789", "6600123987", mobile="4155550177"), SEED, "Rejected", None, None),
    ("25_fix_incomplete_form_with_wrong_document", incomplete_form(), SEED, "Rejected", None, None),
    ("27_approved_form_demo_vendor", demo_form_vendor(), SEED, "Approved", None, None),
    # ---------------- the corrected versions of the edge-case samples (what the vendor sends after being told what is wrong)
    ("28_corrected_incomplete_form", indian("Delta Pumps Private Limited", "DELCP3456L", "72000123456702"), SEED, "Approved", None, None),
    ("29_corrected_tax_id_for_country", american("Redwood Supply LLC", "61-4827395", "4400555111", mobile="3105550188"), SEED, "Approved", None, None),
    ("30_corrected_bank_holder_name", indian("Lumina Global Private Limited", "LUMCG5678N", "74000123456704"), SEED, "Approved", None, None),
    ("31_corrected_identity_fields", indian("Cobalt Tools Private Limited", "COBCT9012S", "79000123456711"), SEED, "Approved", None, None),
    ("32_corrected_lookalike_name", indian("Globex Foods Private Limited", "GLOCF4567G", "82000123456714"), SEED, "Approved", None, None),
    ("26_reject_lookalike_name", indian("Globex Foods Private Limited", "GLOCF4567G", "82000123456714", holder="Gl0bex Foods Private Limited"), SEED, "Rejected", None, None),
]


# The samples in the app: one clean vendor and six edge cases: five named in the Zamp brief (or its payment-fraud risk) and one look-alike trick.
# (sample file, the case in CASES it is written from)
SAMPLES = [
    ("01_approved_india_clean", "01_approved_india_clean"),                                                 # the happy path
    ("02_edge_incomplete_form_wrong_document", "25_fix_incomplete_form_with_wrong_document"),               # "incomplete forms", "the wrong documents": a numbered list of what to send
    ("03_edge_tax_id_wrong_for_country", "07_fix_us_company_with_indian_gstin"),                            # "the tax ID format is wrong for the country they claim"
    ("04_edge_name_nearly_matches_bank_account", "09_fix_near_miss_name"),                                  # "the name doesn't match the bank account": sent back; the vendor files a new application
    ("05_edge_identity_fields_contradict", "19_reject_two_contradictions"),                                 # "subtle inconsistencies when you cross-reference the fields": rejected
    ("06_edge_existing_vendor_changes_bank_account", "11_review_existing_vendor_changes_bank_account"),     # "payment fraud": a reviewer must verify it; submit 01 first
    ("07_edge_lookalike_characters_in_name", "26_reject_lookalike_name"),                                   # "Gl0bex" against "Globex": a zero for an o: rejected outright
]


# The corrected version of each edge case a vendor can fix, so you can see that sending the right data works.
# 06 has none: an existing vendor changing its bank account can only be settled by a reviewer, whatever the vendor sends.
# 07 is the exception to "approved": alone it is approved, but after 07 was rejected for look-alike characters the new application goes to a reviewer.
CORRECTED = [
    ("02b_corrected_incomplete_form_completed", "28_corrected_incomplete_form"),
    ("03b_corrected_tax_id_for_country", "29_corrected_tax_id_for_country"),
    ("04b_corrected_bank_holder_name_matches", "30_corrected_bank_holder_name"),
    ("05b_corrected_identity_fields_consistent", "31_corrected_identity_fields"),
    ("07b_corrected_lookalike_name_spelled_right", "32_corrected_lookalike_name"),
]


def write_samples():
    os.makedirs("sample_inputs", exist_ok=True)
    for name in os.listdir("sample_inputs"):
        os.remove(os.path.join("sample_inputs", name))
    by_name = {case[0]: case for case in CASES}
    for file_name, case_name in SAMPLES + CORRECTED:
        with open(f"sample_inputs/{file_name}.json", "w", encoding="utf-8") as handle:
            json.dump(by_name[case_name][1], handle, indent=2)
    registry = {"_note": "SIMULATED tax registry for the demo. A real deployment calls the tax authorities (GST portal, IRS TIN matching, EU VIES).", "IN": {}, "US": {}, "DE": {}}
    for name, data, history, status, reason, override in CASES:
        key = normalize_id(data.get("tax_id"))
        if data["country"] in ("IN", "US", "DE") and key and (override or key not in registry[data["country"]]):
            registry[data["country"]][key] = {"status": "active", "name": data["company_name"], **(override or {})}
    with open("registry.json", "w", encoding="utf-8") as handle:
        json.dump(registry, handle, indent=2, ensure_ascii=False)
    with open("sanctions.json", "w", encoding="utf-8") as handle:
        json.dump({"_note": "FICTIONAL demo watchlist. A real deployment screens against the official OFAC, EU and UN lists.", "names": DEMO_WATCHLIST}, handle, indent=2)


if __name__ == "__main__":
    write_samples()
    print(f"{len(SAMPLES)} samples + {len(CORRECTED)} corrected versions, registry.json and sanctions.json written")
