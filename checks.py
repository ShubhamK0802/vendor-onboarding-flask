import json
import os
import re
import unicodedata
import urllib.request
from collections import namedtuple

from rapidfuzz import fuzz

from config import (
    ALLOWED_FILE_TYPES, BANK_PROOF_DOCS, FIX, LEGAL_FORMS, NAME_REVIEW_THRESHOLD, PAN_HOLDER_CODES, RED,
    REQUIRED_BY_COUNTRY, REQUIRED_DOCS, REQUIRED_FIELDS, REVIEW, STRICT_SUFFIX_MATCH, SUPPORTED_COUNTRIES, EMBARGOED_COUNTRIES,
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
        make_finding("MISSING_FIELD", FIX, f"Enter your {label(f)}")
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


# ---- look-alike characters: O for 0, I or l for 1, letters of another alphabet, invisible characters ----------
# Names are only ever compared WITH EACH OTHER, so honest names with digits (34square, add360) are never flagged:
# a pair is only suspicious when the two spellings differ but become identical once look-alikes are folded together.
TO_DIGIT = {"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"}  # letters that look like a digit
TO_LETTER = {"0": "O", "1": "IL", "5": "S", "8": "B", "2": "Z", "6": "G"}  # digits that look like a letter
FOLD = str.maketrans({"0": "o", "O": "o", "1": "l", "I": "l", "5": "s", "8": "b", "2": "z", "6": "g"})


def hidden_characters(text):
    return any(unicodedata.category(ch) in ("Cf", "Cc") for ch in text)


def mixed_alphabets(text):
    """A word that mixes Latin letters with letters of another alphabet (a Cyrillic 'a' inside 'Apex'): a classic spoofing trick."""
    for word in text.split():
        scripts = {unicodedata.name(ch, "").startswith("LATIN") for ch in word if ch.isalpha()}
        if len(scripts) == 2:
            return True
    return False


def lookalike_only(value, shape):
    """True when the value breaks its shape ONLY through look-alike characters. Shape: D digit, L letter, A letter or digit, anything else must match;
    "D*" means digits of any length. A value of the wrong length is a plain mistake, not a look-alike."""
    slots = "D" * len(value) if shape == "D*" else shape
    if len(value) != len(slots):
        return False
    swapped = False
    for ch, slot in zip(value, slots):
        if slot == "A":
            if not (ch.isascii() and ch.isalnum()):
                return False
        elif (slot == "D" and ch.isascii() and ch.isdigit()) or (slot == "L" and ch.isascii() and ch.isalpha()) or ch == slot:
            continue
        elif (slot == "D" or slot.isdigit()) and TO_DIGIT.get(ch) in ("1", "2", "5", "6", "8", "0") and (slot == "D" or TO_DIGIT[ch] == slot):
            swapped = True
        elif (slot == "L" or slot.isalpha()) and slot != "A" and ch in TO_LETTER and (slot == "L" or slot in TO_LETTER[ch]):
            swapped = True
        else:
            return False
    return swapped


def lookalike(first, second):
    """Two names that differ only in look-alike characters (g00gle / google). Identical names, or names that differ in other ways, are not."""
    a, b = core_name(first or ""), core_name(second or "")
    return bool(a and b) and a != b and core_name(first.translate(FOLD)) == core_name(second.translate(FOLD))


# ---- 3. format checks: one rule per (country, field). Adding a country = adding rows here -------

GSTIN_PATTERN = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
EIN_PATTERN = re.compile(r"[0-9]{9}")
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ROUTING_WEIGHTS = [3, 7, 1, 3, 7, 1, 3, 7, 1]
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
VAT_DE_PATTERN = re.compile(r"DE[0-9]{9}")
IBAN_PATTERN = re.compile(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}")  # one shape for every IBAN country
BIC_PATTERN = re.compile(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?")


def gstin_check_char(first14):
    total = 0
    for position, char in enumerate(first14):
        product = GSTIN_CHARS.index(char) * (1 if position % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def gstin_checksum(value):
    if value[14] != gstin_check_char(value[:14]):
        return "BAD_GSTIN_CHECKSUM", "GSTIN check character is wrong: re-check it"


def routing_checksum(value):
    if sum(int(d) * w for d, w in zip(value, ROUTING_WEIGHTS)) % 10:
        return "BAD_ROUTING_CHECKSUM", "Routing number check failed: re-check it"


def german_vat_check_digit(base8):
    """ISO 7064 MOD 11,10 over the 8 digits after "DE"; the 9th digit is the check digit."""
    product = 10
    for digit in base8:
        total = (int(digit) + product) % 10 or 10
        product = (2 * total) % 11
    return (11 - product) % 10


def german_vat_checksum(value):
    if int(value[-1]) != german_vat_check_digit(value[2:-1]):
        return "BAD_VAT_CHECKSUM", "VAT ID check digit is wrong: re-check it"


def iban_checksum(value):
    """ISO 13616 mod-97, shared by every IBAN country; a German IBAN is also exactly 22 characters."""
    if value.startswith("DE") and not value[2:].isdigit():
        if all(ch.isdigit() or ch in TO_DIGIT for ch in value[2:]):
            return "LOOKALIKE_CHARACTERS", "The IBAN contains characters that look like digits (for example O and 0)"
        return "BAD_IBAN_FORMAT", "A German IBAN is DE plus 20 digits"
    if value.startswith("DE") and len(value) != 22:
        return "BAD_IBAN_FORMAT", f"A German IBAN has 22 characters, yours has {len(value)}"
    if int("".join(str(int(ch, 36)) for ch in value[4:] + value[:4])) % 97 != 1:
        return "BAD_IBAN_CHECKSUM", "IBAN checksum is wrong: re-check it"


Rule = namedtuple("Rule", "country field pattern code message extra shape", defaults=(None, None))
FORMATS = [
    Rule("IN", "pan", re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]"), "BAD_PAN_FORMAT", "PAN must look like ABCDE1234F", None, "LLLLLDDDDL"),
    Rule("IN", "tax_id", GSTIN_PATTERN, "BAD_GSTIN_FORMAT", "GSTIN must be 15 characters (example 29ABCDE1234F1Z5)", gstin_checksum, "DDLLLLLDDDDLAZA"),
    Rule("US", "tax_id", EIN_PATTERN, "BAD_EIN_FORMAT", "EIN must be 9 digits (example 12-3456789)", None, "DDDDDDDDD"),
    Rule("IN", "bank_code", re.compile(r"[A-Z]{4}0[A-Z0-9]{6}"), "BAD_IFSC_FORMAT", "IFSC must look like HDFC0001234", None, "LLLL0AAAAAA"),
    Rule("US", "bank_code", EIN_PATTERN, "BAD_ROUTING_FORMAT", "Routing number must be 9 digits", routing_checksum, "DDDDDDDDD"),
    Rule("IN", "bank_account_number", re.compile(r"[0-9]{9,18}"), "BAD_ACCOUNT_FORMAT", "Bank account number must be 9 to 18 digits", None, "D*"),
    Rule("US", "bank_account_number", re.compile(r"[0-9]{4,17}"), "BAD_ACCOUNT_FORMAT", "Bank account number must be 4 to 17 digits", None, "D*"),
    Rule("DE", "tax_id", VAT_DE_PATTERN, "BAD_VAT_FORMAT", "German VAT ID must be DE plus 9 digits", german_vat_checksum, "DEDDDDDDDDD"),
    Rule("DE", "bank_account_number", IBAN_PATTERN, "BAD_IBAN_FORMAT", "Enter the account as an IBAN", iban_checksum),
    Rule("DE", "bank_code", BIC_PATTERN, "BAD_BIC_FORMAT", "BIC must be 8 or 11 characters (example COBADEFFXXX)"),
]
ZERO_DROPPED = ("BAD_EIN_FORMAT", "BAD_ROUTING_FORMAT")  # Excel often drops a leading zero


def check_formats(submission):
    country, findings, flagged = normalize_id(submission.get("country")), [], set()
    for field in ("tax_id", "pan", "bank_account_number", "bank_code"):  # an ID with invisible or non-ASCII characters is never an honest typo
        raw = str(submission.get(field) or "")
        if hidden_characters(raw) or not raw.isascii():
            findings.append(make_finding("HIDDEN_CHARACTERS", REVIEW, f"The {label(field)} contains hidden or non-ASCII characters"))
            flagged.add(field)
    for rule in FORMATS:
        value = normalize_id(submission.get(rule.field))
        if rule.country != country or value is None or rule.field in flagged:
            continue
        if not rule.pattern.fullmatch(value):
            if rule.shape and lookalike_only(value, rule.shape):
                findings.append(make_finding("LOOKALIKE_CHARACTERS", REVIEW, f"The {label(rule.field)} contains characters that look like other letters or digits (for example O and 0)"))
                continue
            hint = " (8 digits: a leading zero may be missing)" if rule.code in ZERO_DROPPED and value.isdigit() and len(value) == 8 else ""
            findings.append(make_finding(rule.code, FIX, rule.message + hint))
        elif rule.extra and (bad := rule.extra(value)):
            findings.append(make_finding(bad[0], FIX, bad[1]))
    email = clean_value(submission.get("email"))
    if email and not EMAIL_PATTERN.fullmatch(email):
        findings.append(make_finding("BAD_EMAIL_FORMAT", FIX, "Enter a valid email address"))
    return make_result("format_checks", findings)


# ---- 4. documents -------------------------------------------------------------------------------

def check_documents(submission):
    documents = submission.get("documents")
    documents = documents if isinstance(documents, dict) else {}
    findings = [make_finding("MISSING_DOCUMENT", FIX, f"Upload the {label(slot)}") for slot in REQUIRED_DOCS if not documents.get(slot)]
    if not any(documents.get(slot) for slot in BANK_PROOF_DOCS):
        findings.append(make_finding("MISSING_BANK_PROOF", FIX, "Upload a voided cheque or passbook page"))
    for slot, doc in documents.items():
        if not doc:
            continue
        if not isinstance(doc, dict):
            findings.append(make_finding("MALFORMED_DOCUMENT", FIX, f"Upload the {label(slot)} again (unreadable)"))
            continue
        file_type = str(doc.get("file_type", "")).lower().lstrip(".")
        if file_type not in ALLOWED_FILE_TYPES:
            findings.append(make_finding("BAD_FILE_TYPE", FIX, f"{label(slot).capitalize()} must be a PDF, PNG or JPG"))
        if not doc.get("size_bytes"):
            findings.append(make_finding("EMPTY_FILE", FIX, f"{label(slot).capitalize()} file is empty: upload it again"))
        if doc.get("declared_type") != slot:
            findings.append(make_finding("WRONG_SLOT", FIX, f"The {label(slot)} is the wrong document type: upload the right one"))
    return make_result("documents", findings)


TAX_ID_KINDS = {"IN": (GSTIN_PATTERN, "an Indian GSTIN"), "US": (EIN_PATTERN, "a US EIN"), "DE": (VAT_DE_PATTERN, "a German VAT ID")}


# ---- 5. identity cross-checks -------------------------------------------------------------------

def check_identity(submission):
    country, tax_id = normalize_id(submission.get("country")), normalize_id(submission.get("tax_id"))
    pan, entity = normalize_id(submission.get("pan")), clean_value(submission.get("entity_type"))
    findings = []
    if country == "IN" and tax_id and pan and len(tax_id) == 15 and tax_id[2:12] != pan:
        findings.append(make_finding("GSTIN_PAN_MISMATCH", RED, "The PAN inside your GSTIN differs from the PAN you gave"))
    allowed = PAN_HOLDER_CODES.get((entity or "").lower().replace(" ", "_"))
    if country == "IN" and pan and len(pan) == 10 and allowed and pan[3] not in allowed:
        findings.append(make_finding("PAN_ENTITY_MISMATCH", RED, "Your PAN type does not fit your entity type"))
    for other, (pattern, kind) in TAX_ID_KINDS.items():  # a tax ID that is valid in ANOTHER supported country contradicts the claimed country
        if country in SUPPORTED_COUNTRIES and tax_id and other != country and pattern.fullmatch(tax_id):
            findings.append(make_finding("ID_COUNTRY_MISMATCH", RED, f"The tax ID looks like {kind}: check the country"))
            break
    iban = normalize_id(submission.get("bank_account_number"))
    if country == "DE" and iban and IBAN_PATTERN.fullmatch(iban) and iban[:2] != "DE":  # bank country is advisory: a company can bank abroad, but a human confirms
        findings.append(make_finding("BANK_COUNTRY_DIFFERS", REVIEW, f"The IBAN is from {iban[:2]} but the company is registered in Germany; a reviewer will confirm"))
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
    if any(hidden_characters(text) or mixed_alphabets(text) for text in (submission["company_name"], submission["bank_account_name"])):
        return make_result("name_match", [make_finding("HIDDEN_CHARACTERS", REVIEW, "A name contains hidden characters, or mixes alphabets inside one word")])
    if non_latin(submission["company_name"]) or non_latin(submission["bank_account_name"]):  # e.g. kanji vs katakana: not comparable by spelling
        return make_result("name_match", [make_finding("NAME_NON_LATIN", REVIEW, "A name is not written in Latin letters, so it cannot be compared reliably; a reviewer will confirm")])
    if lookalike(submission["company_name"], submission["bank_account_name"]):
        return make_result("name_match", [make_finding("LOOKALIKE_NAME", REVIEW, "The company name and the account holder differ only in look-alike characters (for example 0 for o)")])
    full_company, full_holder = normalize_name(submission["company_name"]), normalize_name(submission["bank_account_name"])
    if company == holder:
        if legal_forms(full_company) != legal_forms(full_holder):
            return make_result("name_match", [make_finding("LEGAL_FORM_DIFFERENCE", FIX, "Account holder and company differ in legal form (e.g. LLP vs Pvt Ltd): make them match")])
        if full_company == full_holder:
            return make_result("name_match", [])
        note = "Names match; only the suffix spelling differs"
        if STRICT_SUFFIX_MATCH:
            return make_result("name_match", [make_finding("SUFFIX_DIFFERENCE", REVIEW,
                "Company name and bank account holder name differ in the company suffix; a reviewer will confirm")], note=note)
        return make_result("name_match", [], note=note)
    score = fuzz.token_sort_ratio(company, holder)
    if score >= NAME_REVIEW_THRESHOLD:  # a typo, or a lookalike name (a known fraud tactic): the vendor corrects it once; the same finding twice rejects
        return make_result("name_match", [make_finding("NAME_NEAR_MISS", FIX, "Make the account holder name match your company name exactly")])
    if (clean_value(submission.get("entity_type")) or "").lower().replace(" ", "_") == "sole_proprietor":
        return make_result("name_match", [make_finding("SOLE_PROP_NAME_REVIEW", REVIEW,
            "Account holder name differs from the business name; for a sole proprietor this can be the owner's own name, so a reviewer will confirm")])
    return make_result("name_match", [make_finding("NAME_MISMATCH", RED, "Use a bank account in your company's name, or attach a signed authorisation letter")])


# ---- 7. verification: is the company real, listed, or placeholder? ---------------------------------

def _load(name):
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


# DEMO DATA, written by samples.py. A real deployment replaces these two lookups with the tax authorities and the official sanctions lists.
REGISTRY, WATCHLIST = _load("registry.json"), _load("sanctions.json")


def vies_lookup(vat_id):
    """The EU's own VAT check (free). Only used when VIES_LIVE=1; None means it could not be reached, which never blocks a vendor."""
    try:
        with urllib.request.urlopen(f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{vat_id[:2]}/vat/{vat_id[2:]}", timeout=5) as reply:
            return {"valid": bool(json.load(reply).get("isValid"))}
    except Exception:
        return None


def longest_run(digits):
    """The longest stretch counting up or down by one (123456789 is 9)."""
    best = up = down = 1
    for before, after in zip(digits, digits[1:]):
        step = int(after) - int(before)
        up = up + 1 if step == 1 else 1
        down = down + 1 if step == -1 else 1
        best = max(best, up, down)
    return best


def is_placeholder(digits):
    """All the same digit, or a run of 7+ up or down: nobody has a real registration number like that."""
    return len(set(digits)) == 1 or longest_run(digits) >= 7


def check_verification(submission):
    country, tax_id = normalize_id(submission.get("country")), normalize_id(submission.get("tax_id"))
    company, findings, notes = submission.get("company_name") or "", [], []

    digits = re.sub(r"\D", "", tax_id or "") if country in ("US", "DE") else ""
    if len(digits) >= 8 and is_placeholder(digits):
        findings.append(make_finding("PLACEHOLDER_TAX_ID", REVIEW, "The tax ID is a placeholder, not a real registration number"))

    if country == "DE" and tax_id and VAT_DE_PATTERN.fullmatch(tax_id) and os.environ.get("VIES_LIVE") == "1":
        found = vies_lookup(tax_id)
        if found is None:
            notes.append("EU VAT check unavailable: not checked")
        elif not found["valid"]:
            findings.append(make_finding("REGISTRY_NOT_FOUND", FIX, "This German VAT ID is not registered: check the number"))
    elif tax_id and country in REGISTRY:
        record = REGISTRY[country].get(tax_id)
        if record is None:
            notes.append("no registry record (demo registry): not checked")
        elif record.get("status") != "active":
            findings.append(make_finding("REGISTRY_CANCELLED", REVIEW, "The tax registration is cancelled or inactive"))
        elif company and lookalike(company, record.get("name")):
            findings.append(make_finding("LOOKALIKE_NAME", REVIEW, "The company name differs from the tax registry only in look-alike characters"))
        elif core_name(record.get("name")) and company and fuzz.token_sort_ratio(core_name(record["name"]), core_name(company)) < 85:
            findings.append(make_finding("REGISTRY_NAME_MISMATCH", RED, "Your company name differs from the tax registry: use the registered legal name"))

    names = [n for n in (company, submission.get("bank_account_name")) if n]
    exact = near = False
    for listed in WATCHLIST.get("names", []):
        for name in names:
            if core_name(name) == core_name(listed) or lookalike(name, listed):  # a look-alike spelling of a listed name is evasion, not a different company
                exact = True
            elif fuzz.token_sort_ratio(core_name(name), core_name(listed)) >= 85:
                near = True
    if exact:
        findings.append(make_finding("SANCTIONS_MATCH", REVIEW, "The name matches the sanctions watchlist"))
    elif near:
        findings.append(make_finding("SANCTIONS_POSSIBLE", REVIEW, "The name is close to a sanctions watchlist entry; compliance should confirm"))

    iban, bic = normalize_id(submission.get("bank_account_number")) or "", normalize_id(submission.get("bank_code")) or ""
    bank_countries = ([iban[:2]] if IBAN_PATTERN.fullmatch(iban) else []) + ([bic[4:6]] if BIC_PATTERN.fullmatch(bic) else [])
    if any(code in EMBARGOED_COUNTRIES for code in bank_countries):
        findings.append(make_finding("EMBARGOED_BANK_COUNTRY", REVIEW, "The bank is in an embargoed country"))

    return make_result("verification", findings, note="; ".join(notes) or None)


# ---- 8. duplicates ------------------------------------------------------------------------------

def company_key(submission):
    country = normalize_id(submission.get("country"))
    return normalize_id(submission.get("pan")) if country == "IN" else normalize_id(submission.get("tax_id")) if country in ("US", "DE") else None


def same(first, second):
    return (normalize_name(first) or "") == (normalize_name(second) or "")


def check_duplicates(submission, existing_vendors):
    key = company_key(submission)
    if key is None:
        return make_result("duplicate_check", [], skipped_reason="No company key available; see earlier stages")
    name, account = core_name(submission.get("company_name")), normalize_id(submission.get("bank_account_number"))
    mobile, email, address = normalize_id(submission.get("mobile")), (clean_value(submission.get("email")) or "").lower(), submission.get("address")
    found = {}
    for vendor in existing_vendors:
        if vendor.get("company_key") == key:  # this company is already onboarded: what is different decides what happens
            if core_name(vendor.get("company_name")) != name:
                found["DUPLICATE_KEY_NEW_NAME"] = make_finding("DUPLICATE_KEY_NEW_NAME", REVIEW, "This company ID is already registered under a different name; a reviewer will confirm")
                continue
            changed = False
            if account and normalize_id(vendor.get("bank_account_number")) != account:  # the classic payment-fraud pattern: only a call to the number on file can settle it
                found["BANK_DETAILS_CHANGED"] = make_finding("BANK_DETAILS_CHANGED", REVIEW, "The bank account differs from the one on file for this vendor; a reviewer will verify it by calling a known number")
                changed = True
            if (mobile and vendor.get("mobile") and normalize_id(vendor["mobile"]) != mobile) or (email and vendor.get("email") and vendor["email"].lower() != email) \
                    or (address and vendor.get("address") and not same(vendor["address"], address)):
                found["EXISTING_VENDOR"] = make_finding("EXISTING_VENDOR", REVIEW, "This company is already onboarded and its contact details or address changed; a reviewer will confirm the update")
                changed = True
            if not changed:
                found["DUPLICATE_APPLICATION"] = make_finding("DUPLICATE_APPLICATION", REVIEW, "This company is already onboarded with exactly these details")
            continue
        if lookalike(submission.get("company_name"), vendor.get("company_name")):
            found["LOOKALIKE_OF_EXISTING_VENDOR"] = make_finding("LOOKALIKE_OF_EXISTING_VENDOR", REVIEW, "The company name differs from an onboarded vendor's name only in look-alike characters")
        if account and normalize_id(vendor.get("bank_account_number")) == account:
            found["DUPLICATE_BANK_ACCOUNT"] = make_finding("DUPLICATE_BANK_ACCOUNT", REVIEW, "This bank account is already registered to a different company; a reviewer will confirm")
        if (mobile and normalize_id(vendor.get("mobile")) == mobile) or (email and (clean_value(vendor.get("email")) or "").lower() == email):
            found["SHARED_CONTACT"] = make_finding("SHARED_CONTACT", REVIEW, "A phone number or email is shared with a different company; a reviewer will confirm")
    return make_result("duplicate_check", list(found.values()))
