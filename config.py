RULE_VERSION = "3.0"

REQUIRED_FIELDS = [
    "company_name", "entity_type", "country", "email", "mobile",
    "address", "tax_id", "bank_account_name", "bank_account_number", "bank_code",
]

REQUIRED_BY_COUNTRY = {
    "IN": ["pan"],
    "US": [],
}

SUPPORTED_COUNTRIES = ["IN", "US", "DE"]

REQUIRED_DOCS = ["tax_document", "registration"]
BANK_PROOF_DOCS = ["voided_cheque", "passbook"]
ALLOWED_FILE_TYPES = ["pdf", "png", "jpg", "jpeg"]

PAN_HOLDER_CODES = {
    "company": ["C"],
    "sole_proprietor": ["P"],
    "partnership": ["F"],
    "llp": ["F"],
    "trust": ["T"],
}

SUFFIX_WORDS = {
    "private", "pvt", "limited", "ltd", "llp", "company", "co",
    "corp", "corporation", "inc", "llc", "group", "and",
    "gmbh", "ag", "ug", "kg", "ohg", "mbh",  # German company forms
}

NAME_REVIEW_THRESHOLD = 80
STRICT_SUFFIX_MATCH = False

LEGAL_FORMS = {"llp": "llp", "llc": "llc", "inc": "inc", "corp": "corp", "corporation": "corp", "gmbh": "gmbh", "ag": "ag", "ug": "ug", "kg": "kg", "ohg": "ohg"}

REASON_LABELS = {
    "MISSING_FIELD": "A required field is empty",
    "UNSUPPORTED_COUNTRY": "Country not supported yet",
    "BAD_PAN_FORMAT": "PAN is not in the right format",
    "BAD_GSTIN_FORMAT": "GSTIN is not in the right format",
    "BAD_GSTIN_CHECKSUM": "GSTIN fails its check character (likely a typo)",
    "BAD_EIN_FORMAT": "EIN is not in the right format",
    "BAD_IFSC_FORMAT": "IFSC code is not in the right format",
    "BAD_ROUTING_FORMAT": "Routing number is not in the right format",
    "BAD_ROUTING_CHECKSUM": "Routing number fails its checksum (likely a typo)",
    "BAD_EMAIL_FORMAT": "Email address looks invalid",
    "MISSING_DOCUMENT": "A required document is missing",
    "MISSING_BANK_PROOF": "Bank proof (cheque or passbook) is missing",
    "MALFORMED_DOCUMENT": "A document's details are unreadable",
    "BAD_FILE_TYPE": "A document is not a PDF, PNG or JPG",
    "EMPTY_FILE": "A document file is empty",
    "WRONG_SLOT": "A document was uploaded in the wrong slot",
    "GSTIN_PAN_MISMATCH": "GSTIN and PAN do not match",
    "PAN_ENTITY_MISMATCH": "PAN type does not fit the entity type",
    "ID_COUNTRY_MISMATCH": "Tax ID does not belong to the stated country",
    "LEGAL_FORM_DIFFERENCE": "Legal form differs (for example LLP vs LLC)",
    "SUFFIX_DIFFERENCE": "Company name differs only in its suffix",
    "NAME_NEAR_MISS": "Company and bank holder names are similar, not identical",
    "SOLE_PROP_NAME_REVIEW": "Sole proprietor: holder name differs from company name",
    "NAME_MISMATCH": "Company and bank holder names do not match",
    "DUPLICATE_KEY_NEW_NAME": "Same company ID already known under a different name",
    "DUPLICATE_BANK_ACCOUNT": "Bank account already used by another vendor",
    "SHARED_CONTACT": "Contact details shared with another vendor",
    "EXISTING_VENDOR": "Company is already an onboarded vendor",
    "BAD_VAT_FORMAT": "German VAT ID is not DE plus 9 digits",
    "BAD_VAT_CHECKSUM": "German VAT ID fails its check digit (likely a typo)",
    "BAD_IBAN_FORMAT": "IBAN is not in the right format",
    "BAD_IBAN_CHECKSUM": "IBAN fails its checksum (likely a typo)",
    "BAD_BIC_FORMAT": "BIC / SWIFT code is not in the right format",
    "BANK_COUNTRY_DIFFERS": "Bank is in a different country than the company",
    "NAME_NON_LATIN": "A name is not in Latin letters, so it cannot be compared",
    "BANK_DETAILS_CHANGED": "Bank account differs from the one on file",
}

FIELD_LABELS = {
    "company_name": "Company name",
    "bank_account_name": "Bank account holder",
    "tax_id": "Tax ID",
    "pan": "PAN",
    "entity_type": "Entity type",
    "country": "Country",
    "bank_account_number": "Bank account",
    "bank_code": "Bank code",
    "mobile": "Mobile",
    "email": "Email",
}

NAME_FIELDS = ["company_name", "bank_account_name"]

EVIDENCE_FIELDS = {
    "NAME_NEAR_MISS": NAME_FIELDS,
    "NAME_MISMATCH": NAME_FIELDS,
    "SUFFIX_DIFFERENCE": NAME_FIELDS,
    "LEGAL_FORM_DIFFERENCE": NAME_FIELDS,
    "SOLE_PROP_NAME_REVIEW": NAME_FIELDS + ["entity_type"],
    "GSTIN_PAN_MISMATCH": ["tax_id", "pan"],
    "PAN_ENTITY_MISMATCH": ["pan", "entity_type"],
    "ID_COUNTRY_MISMATCH": ["country", "tax_id"],
    "UNSUPPORTED_COUNTRY": ["country"],
    "DUPLICATE_BANK_ACCOUNT": ["bank_account_number", "bank_code"],
    "DUPLICATE_KEY_NEW_NAME": ["company_name", "tax_id", "pan"],
    "SHARED_CONTACT": ["mobile", "email"],
    "EXISTING_VENDOR": ["company_name", "pan", "tax_id"],
    "BANK_COUNTRY_DIFFERS": ["bank_account_number", "bank_code"],
    "NAME_NON_LATIN": NAME_FIELDS,
    "BANK_DETAILS_CHANGED": ["bank_account_number", "bank_code"],
}
# Finding severity: FIX = vendor can fix it, REVIEW = needs human judgment, RED = identity red flag
FIX, REVIEW, RED = 1, 2, 3

# Vendors already onboarded before this system started: the duplicate check compares every submission against them.
VENDORS_ON_FILE = [{
    "company_key": "PQRSX5678L",
    "company_name": "Orion Traders Private Limited",
    "bank_account_number": "60200345678912",
    "mobile": "9000011111",
    "email": "orion@orion.example",
}]

# Reviewer desk: these findings put money at risk, so such runs are shown first (a red-flag finding does too).
HIGH_PRIORITY_CODES = {"DUPLICATE_BANK_ACCOUNT", "BANK_DETAILS_CHANGED", "DUPLICATE_KEY_NEW_NAME", "BANK_COUNTRY_DIFFERS"}

# The two reasons a run can be Pending (status names shown everywhere).
NEEDS_REVIEW = "Needs review"
VENDOR_TO_FIX = "Vendor to fix"
