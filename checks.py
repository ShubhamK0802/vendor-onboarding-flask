import re
import unicodedata
from collections import namedtuple

from rapidfuzz import fuzz

from config import (
    ALLOWED_FILE_TYPES, BANK_PROOF_DOCS, FIX, LEGAL_FORMS, NAME_REVIEW_THRESHOLD, PAN_HOLDER_CODES, RED,
    REQUIRED_BY_COUNTRY, REQUIRED_DOCS, REQUIRED_FIELDS, REVIEW, STRICT_SUFFIX_MATCH, SUPPORTED_COUNTRIES,
)
from normalize import clean_value, core_name, normalize_id, normalize_name


def make_finding(code, level, message):
    return {"code": code, "level": level, "message": message}


def make_result(stage, findings, skipped_reason=None, note=None):
    status = "skipped" if skipped_reason else "flagged" if findings else "pass"
    return {"stage": stage, "status": status, "findings": findings, "note": skipped_reason or note}


def label(slot):
    return slot.replace("_", " ")


# ---- 1. completeness and 2. country routing -------------------------------------------------

def check_completeness(submission):
    required = REQUIRED_FIELDS + REQUIRED_BY_COUNTRY.get(normalize_id(submission.get("country")), [])
    return make_result("completeness", [
        make_finding("MISSING_FIELD", FIX, f"Missing required field: {label(f)}")
        for f in required if clean_value(submission.get(f)) is None
    ])


def check_country(submission):
    country = normalize_id(submission.get("country"))
    if country is None:
        return make_result("country_routing", [], skipped_reason="Country missing; see completeness")
    if country not in SUPPORTED_COUNTRIES:
        message = f"Country {country} is not supported yet; a reviewer will handle this submission"
        return make_result("country_routing", [make_finding("UNSUPPORTED_COUNTRY", REVIEW, message)])
    return make_result("country_routing", [])


# ---- 3. format checks: one rule per (country, field). Adding a country = adding rows here -------

GSTIN_PATTERN = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
EIN_PATTERN = re.compile(r"[0-9]{9}")
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ROUTING_WEIGHTS = [3, 7, 1, 3, 7, 1, 3, 7, 1]
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
CORPNUM_PATTERN = re.compile(r"[0-9]{13}")  # Japan: 1 check digit + 12-digit base number
ZENGIN_PATTERN = re.compile(r"[0-9]{7}")  # Japan: 4-digit bank code + 3-digit branch code


def gstin_check_char(first14):
    total = 0
    for position, char in enumerate(first14):
        product = GSTIN_CHARS.index(char) * (1 if position % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def gstin_checksum(value):
    if value[14] != gstin_check_char(value[:14]):
        return "BAD_GSTIN_CHECKSUM", "GSTIN check character does not match; please re-check for a typo"


def routing_checksum(value):
    if sum(int(d) * w for d, w in zip(value, ROUTING_WEIGHTS)) % 10:
        return "BAD_ROUTING_CHECKSUM", "Routing number check failed; please re-check for a typo"


def corp_number_check_digit(base12):
    """Japan's National Tax Agency method: 9 - (weighted digit sum mod 9); weights 1,2,1,2... counted from the right."""
    return 9 - sum(int(d) * (1 if i % 2 == 0 else 2) for i, d in enumerate(reversed(base12))) % 9


def corp_number_checksum(value):
    if int(value[0]) != corp_number_check_digit(value[1:]):
        return "BAD_CORPNUM_CHECKSUM", "The corporate number's check digit does not match; please re-check for a typo"


Rule = namedtuple("Rule", "country field pattern code message extra", defaults=(None,))
FORMATS = [
    Rule("IN", "pan", re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]"), "BAD_PAN_FORMAT",
         "PAN must be 5 letters, 4 digits, 1 letter (example: ABCDE1234F)"),
    Rule("IN", "tax_id", GSTIN_PATTERN, "BAD_GSTIN_FORMAT",
         "GSTIN must be 15 characters: 2-digit state code, 10-character PAN, then 3 more characters (14th is Z)", gstin_checksum),
    Rule("US", "tax_id", EIN_PATTERN, "BAD_EIN_FORMAT", "EIN must be 9 digits (example: 12-3456789)"),
    Rule("IN", "bank_code", re.compile(r"[A-Z]{4}0[A-Z0-9]{6}"), "BAD_IFSC_FORMAT",
         "IFSC must be 11 characters: 4 letters, the digit 0, then 6 letters or digits (example: HDFC0001234)"),
    Rule("US", "bank_code", EIN_PATTERN, "BAD_ROUTING_FORMAT", "Routing number must be 9 digits", routing_checksum),
    Rule("JP", "tax_id", CORPNUM_PATTERN, "BAD_CORPNUM_FORMAT", "Japanese corporate number (hojin bango) must be 13 digits", corp_number_checksum),
    Rule("JP", "bank_code", ZENGIN_PATTERN, "BAD_ZENGIN_FORMAT", "Japanese bank code must be 7 digits: 4-digit bank code then 3-digit branch code"),
]
ZERO_DROPPED = ("BAD_EIN_FORMAT", "BAD_ROUTING_FORMAT")  # Excel often drops a leading zero


def check_formats(submission):
    country, findings = normalize_id(submission.get("country")), []
    for rule in FORMATS:
        value = normalize_id(submission.get(rule.field))
        if rule.country != country or value is None:
            continue
        if not rule.pattern.fullmatch(value):
            hint = ". It has 8 digits; a leading zero may have been dropped" if rule.code in ZERO_DROPPED and value.isdigit() and len(value) == 8 else ""
            findings.append(make_finding(rule.code, FIX, rule.message + hint))
        elif rule.extra and (bad := rule.extra(value)):
            findings.append(make_finding(bad[0], FIX, bad[1]))
    email = clean_value(submission.get("email"))
    if email and not EMAIL_PATTERN.fullmatch(email):
        findings.append(make_finding("BAD_EMAIL_FORMAT", FIX, "Email address looks invalid (example: name@company.com)"))
    return make_result("format_checks", findings)


# ---- 4. documents -------------------------------------------------------------------------------

def check_documents(submission):
    documents = submission.get("documents")
    documents = documents if isinstance(documents, dict) else {}
    findings = [make_finding("MISSING_DOCUMENT", FIX, f"Missing document: {label(slot)}") for slot in REQUIRED_DOCS if not documents.get(slot)]
    if not any(documents.get(slot) for slot in BANK_PROOF_DOCS):
        findings.append(make_finding("MISSING_BANK_PROOF", FIX, "Missing bank proof: upload a voided cheque or a passbook page"))
    for slot, doc in documents.items():
        if not doc:
            continue
        if not isinstance(doc, dict):
            findings.append(make_finding("MALFORMED_DOCUMENT", FIX, f"{label(slot)}: document details are unreadable; please upload again"))
            continue
        file_type = str(doc.get("file_type", "")).lower().lstrip(".")
        if file_type not in ALLOWED_FILE_TYPES:
            findings.append(make_finding("BAD_FILE_TYPE", FIX, f"{label(slot)}: file type '{file_type}' is not allowed; upload a PDF, PNG or JPG"))
        if not doc.get("size_bytes"):
            findings.append(make_finding("EMPTY_FILE", FIX, f"{label(slot)}: file is empty; please upload again"))
        if doc.get("declared_type") != slot:
            findings.append(make_finding("WRONG_SLOT", FIX, f"{label(slot)}: this file is marked as '{doc.get('declared_type')}', which does not match this slot"))
    return make_result("documents", findings)


TAX_ID_KINDS = {"IN": (GSTIN_PATTERN, "an Indian GSTIN"), "US": (EIN_PATTERN, "a US EIN"), "JP": (CORPNUM_PATTERN, "a Japanese corporate number")}


# ---- 5. identity cross-checks -------------------------------------------------------------------

def check_identity(submission):
    country, tax_id = normalize_id(submission.get("country")), normalize_id(submission.get("tax_id"))
    pan, entity = normalize_id(submission.get("pan")), clean_value(submission.get("entity_type"))
    findings = []
    if country == "IN" and tax_id and pan and len(tax_id) == 15 and tax_id[2:12] != pan:
        findings.append(make_finding("GSTIN_PAN_MISMATCH", RED, "The PAN inside the GSTIN does not match the PAN provided"))
    allowed = PAN_HOLDER_CODES.get((entity or "").lower().replace(" ", "_"))
    if country == "IN" and pan and len(pan) == 10 and allowed and pan[3] not in allowed:
        findings.append(make_finding("PAN_ENTITY_MISMATCH", RED, f"The PAN's 4th character '{pan[3]}' does not fit the entity type '{entity}'"))
    for other, (pattern, kind) in TAX_ID_KINDS.items():  # a tax ID that is valid in ANOTHER supported country contradicts the claimed country
        if country in SUPPORTED_COUNTRIES and tax_id and other != country and pattern.fullmatch(tax_id):
            findings.append(make_finding("ID_COUNTRY_MISMATCH", RED, f"The tax ID looks like {kind}, but the country is {country}"))
            break
    return make_result("identity_checks", findings)


# ---- 6. name match ------------------------------------------------------------------------------

def legal_forms(full_name):
    return {LEGAL_FORMS[word] for word in full_name.split() if word in LEGAL_FORMS}


def non_latin(text):
    return any(ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN") for ch in text)


def check_name_match(submission):
    company, holder = core_name(submission.get("company_name")), core_name(submission.get("bank_account_name"))
    if not company or not holder:
        return make_result("name_match", [], skipped_reason="Company name or account holder name missing; see completeness")
    if non_latin(submission["company_name"]) or non_latin(submission["bank_account_name"]):  # e.g. kanji vs katakana: not comparable by spelling
        return make_result("name_match", [make_finding("NAME_NON_LATIN", REVIEW, "A name is not written in Latin letters, so it cannot be compared reliably; a reviewer will confirm")])
    full_company, full_holder = normalize_name(submission["company_name"]), normalize_name(submission["bank_account_name"])
    if company == holder:
        if legal_forms(full_company) != legal_forms(full_holder):
            return make_result("name_match", [make_finding("LEGAL_FORM_DIFFERENCE", REVIEW,
                "Company name and bank account holder name differ in legal form (for example LLP vs Private Limited); a reviewer will confirm")])
        if full_company == full_holder:
            return make_result("name_match", [])
        note = "Names match; only the suffix spelling differs"
        if STRICT_SUFFIX_MATCH:
            return make_result("name_match", [make_finding("SUFFIX_DIFFERENCE", REVIEW,
                "Company name and bank account holder name differ in the company suffix; a reviewer will confirm")], note=note)
        return make_result("name_match", [], note=note)
    score = fuzz.token_sort_ratio(company, holder)
    if score >= NAME_REVIEW_THRESHOLD:
        return make_result("name_match", [make_finding("NAME_NEAR_MISS", REVIEW,
            f"Company name and bank account holder name are similar but not identical ({score:.0f}% similar); a reviewer will confirm")])
    if (clean_value(submission.get("entity_type")) or "").lower().replace(" ", "_") == "sole_proprietor":
        return make_result("name_match", [make_finding("SOLE_PROP_NAME_REVIEW", REVIEW,
            "Account holder name differs from the business name; for a sole proprietor this can be the owner's own name, so a reviewer will confirm")])
    return make_result("name_match", [make_finding("NAME_MISMATCH", RED, "Bank account holder name does not match the company name")])


# ---- 7. duplicates ------------------------------------------------------------------------------

def company_key(submission):
    country = normalize_id(submission.get("country"))
    return normalize_id(submission.get("pan")) if country == "IN" else normalize_id(submission.get("tax_id")) if country in ("US", "JP") else None


def check_duplicates(submission, existing_vendors):
    key = company_key(submission)
    if key is None:
        return make_result("duplicate_check", [], skipped_reason="No company key available; see earlier stages")
    name, account = core_name(submission.get("company_name")), normalize_id(submission.get("bank_account_number"))
    mobile, email = normalize_id(submission.get("mobile")), (clean_value(submission.get("email")) or "").lower()
    found = {}
    for vendor in existing_vendors:
        if vendor.get("company_key") == key:  # the company is already onboarded: never auto-approve, a human confirms what changed
            if core_name(vendor.get("company_name")) != name:
                found["DUPLICATE_KEY_NEW_NAME"] = make_finding("DUPLICATE_KEY_NEW_NAME", REVIEW, "This company ID is already registered under a different name; a reviewer will confirm")
            else:
                found["EXISTING_VENDOR"] = make_finding("EXISTING_VENDOR", REVIEW, "This company is already an onboarded vendor; a reviewer will confirm what is being updated")
            if account and normalize_id(vendor.get("bank_account_number")) != account:
                found["BANK_DETAILS_CHANGED"] = make_finding("BANK_DETAILS_CHANGED", REVIEW, "The bank account differs from the one on file for this vendor; a reviewer will verify it by calling a known number")
            continue
        if account and normalize_id(vendor.get("bank_account_number")) == account:
            found["DUPLICATE_BANK_ACCOUNT"] = make_finding("DUPLICATE_BANK_ACCOUNT", REVIEW, "This bank account is already registered to a different company; a reviewer will confirm")
        if (mobile and normalize_id(vendor.get("mobile")) == mobile) or (email and (clean_value(vendor.get("email")) or "").lower() == email):
            found["SHARED_CONTACT"] = make_finding("SHARED_CONTACT", REVIEW, "A phone number or email is shared with a different company; a reviewer will confirm")
    return make_result("duplicate_check", list(found.values()))
