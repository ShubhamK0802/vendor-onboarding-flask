RULE_VERSION = "6.0"

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
    "EXISTING_VENDOR": "Already-onboarded vendor changed its details",
    "DUPLICATE_APPLICATION": "Already onboarded with exactly these details",
    "PLACEHOLDER_TAX_ID": "Tax ID is a placeholder, not a real number",
    "REGISTRY_CANCELLED": "Tax registration is cancelled or inactive",
    "REGISTRY_NAME_MISMATCH": "Company name differs from the tax registry",
    "REGISTRY_NOT_FOUND": "German VAT ID is not registered",
    "SANCTIONS_MATCH": "Name matches the sanctions watchlist",
    "SANCTIONS_POSSIBLE": "Name is close to a sanctions watchlist entry",
    "EMBARGOED_BANK_COUNTRY": "Bank is in an embargoed country",
    "LOOKALIKE_CHARACTERS": "Look-alike characters in an ID or number (O for 0, I or l for 1)",
    "HIDDEN_CHARACTERS": "Hidden characters, or letters of another alphabet mixed into a word",
    "LOOKALIKE_NAME": "Names that differ only in look-alike characters",
    "LOOKALIKE_OF_EXISTING_VENDOR": "Name looks like an onboarded vendor's name",
    "BAD_ACCOUNT_FORMAT": "Bank account number is not in the right format",
    "BAD_VAT_FORMAT": "German VAT ID is not DE plus 9 digits",
    "BAD_VAT_CHECKSUM": "German VAT ID fails its check digit (likely a typo)",
    "BAD_IBAN_FORMAT": "IBAN is not in the right format",
    "BAD_IBAN_CHECKSUM": "IBAN fails its checksum (likely a typo)",
    "BAD_BIC_FORMAT": "BIC / SWIFT code is not in the right format",
    "BANK_COUNTRY_DIFFERS": "Bank is in a different country than the company",
    "NAME_NON_LATIN": "A name is not in Latin letters, so it cannot be compared",
    "BANK_DETAILS_CHANGED": "Bank account differs from the one on file",
    "REPEATED_ATTEMPTS": "Many earlier attempts by the same applicant",
    "IDENTITY_CHANGED_BETWEEN_ATTEMPTS": "Identity details changed between attempts, without being asked",
    "SERIOUS_EARLIER_REJECTION": "An earlier attempt was stopped for a serious reason",
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

DOC_LABELS = {"tax_document": "Tax document", "registration": "Registration document", "voided_cheque": "Voided cheque", "passbook": "Passbook page"}

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
    "EXISTING_VENDOR": ["company_name", "pan", "tax_id", "mobile", "email"],
    "DUPLICATE_APPLICATION": ["company_name", "pan", "tax_id"],
    "PLACEHOLDER_TAX_ID": ["tax_id"],
    "REGISTRY_CANCELLED": ["company_name", "tax_id"],
    "REGISTRY_NAME_MISMATCH": ["company_name", "tax_id"],
    "REGISTRY_NOT_FOUND": ["tax_id"],
    "SANCTIONS_MATCH": NAME_FIELDS,
    "SANCTIONS_POSSIBLE": NAME_FIELDS,
    "EMBARGOED_BANK_COUNTRY": ["bank_account_number", "bank_code"],
    "LOOKALIKE_CHARACTERS": ["tax_id", "pan", "bank_account_number", "bank_code"],
    "HIDDEN_CHARACTERS": ["tax_id", "pan", "bank_account_number", "bank_code", "company_name", "bank_account_name"],
    "LOOKALIKE_NAME": NAME_FIELDS,
    "LOOKALIKE_OF_EXISTING_VENDOR": ["company_name"],
    "BAD_ACCOUNT_FORMAT": ["bank_account_number"],
    "BANK_COUNTRY_DIFFERS": ["bank_account_number", "bank_code"],
    "NAME_NON_LATIN": NAME_FIELDS,
    "BANK_DETAILS_CHANGED": ["bank_account_number", "bank_code"],
    "IDENTITY_CHANGED_BETWEEN_ATTEMPTS": ["company_name", "tax_id", "pan", "bank_account_number"],
    # format errors: the vendor is asked to correct exactly these fields (so changing them on the next attempt is expected)
    "BAD_PAN_FORMAT": ["pan"], "BAD_GSTIN_FORMAT": ["tax_id"], "BAD_GSTIN_CHECKSUM": ["tax_id"], "BAD_EIN_FORMAT": ["tax_id"],
    "BAD_VAT_FORMAT": ["tax_id"], "BAD_VAT_CHECKSUM": ["tax_id"], "BAD_IFSC_FORMAT": ["bank_code"], "BAD_ROUTING_FORMAT": ["bank_code"],
    "BAD_ROUTING_CHECKSUM": ["bank_code"], "BAD_IBAN_FORMAT": ["bank_account_number"], "BAD_IBAN_CHECKSUM": ["bank_account_number"],
    "BAD_BIC_FORMAT": ["bank_code"],
}
# Finding severity: FIX = vendor can fix it, REVIEW = needs human judgment, RED = identity red flag
FIX, REVIEW, RED = 1, 2, 3

# The only reason a run is Pending: a person must decide (status name shown everywhere).
NEEDS_REVIEW = "Needs review"

# Vendors already onboarded before this system started: the duplicate check compares every submission against them.
VENDORS_ON_FILE = [{
    "company_key": "PQRSX5678L",
    "company_name": "Orion Traders Private Limited",
    "bank_account_number": "60200345678912",
    "mobile": "9000011111",
    "email": "orion@orion.example",
    "address": "5 Residency Road, Pune, Maharashtra 411001",
    "country": "IN",
}]

# ---- When is a run Rejected? (the status definitions, in code)
# Rejected = this application cannot be approved as submitted. The vendor is told why (and, for mistakes and gaps, exactly what to correct) and files a
# NEW application: nothing is pending on the vendor's side, so there is no waiting state and no timer. It is reached by:
#   1. a finding that rejects on its own (below), with the reason the VENDOR is told (never a fraud accusation);
#   2. two or more identity contradictions at once, which a typo cannot explain;
#   3. only mistakes or gaps the vendor can correct (the message lists them);
#   4. a reviewer's decision (including asking for more information: the vendor then files a new application).
REJECT_ON_ITS_OWN = {
    "DUPLICATE_APPLICATION": "your company is already onboarded with exactly these details",
    "SANCTIONS_MATCH": "we are unable to onboard this company",  # deliberately vague: never tell a listed party what matched
    "EMBARGOED_BANK_COUNTRY": "we cannot make payments to a bank in that country",
    "REGISTRY_CANCELLED": "your tax registration is shown as cancelled or inactive",
    "PLACEHOLDER_TAX_ID": "the tax ID is a placeholder, not a real registration number",
    # Look-alike tricks are rejected outright (no "please correct it"): honest typos are rarely made only of look-alike swaps.
    "LOOKALIKE_CHARACTERS": "some of the details you gave contain characters that look like other letters or digits (for example O and 0)",
    "HIDDEN_CHARACTERS": "some of the details you gave contain hidden characters, or letters from another alphabet mixed into a word",
    "LOOKALIKE_NAME": "two names you gave look identical but are spelled with look-alike characters (for example a zero for an o)",
    "LOOKALIKE_OF_EXISTING_VENDOR": "your company name could not be accepted",
}
# Countries under comprehensive sanctions (simplified: a real deployment uses the current official lists).
EMBARGOED_COUNTRIES = {"KP", "IR", "SY", "CU"}
# Repeat attempts: a vendor whose application is sent back files a NEW application. Applications are linked by a shared identifier, a near-identical
# name or a re-used file. From the 4th linked attempt, or when an identity field changes that nobody asked to be changed, a person decides.
ATTEMPTS_BEFORE_REVIEW = 3  # earlier linked attempts allowed before the next one goes to a reviewer
ATTEMPT_WINDOW_DAYS = 30
NAME_LINK_SCORE = 92  # company names this similar (0-100) count as the same applicant
RATE_LIMIT_PER_HOUR = 30  # submissions per source (IP address) per hour

# What a vendor is told when a REVIEWER decides. Worked out from what the checks found, so the reviewer types nothing,
# and nothing about other vendors or our internal records is revealed.
VENDOR_REASONS = {
    "DUPLICATE_BANK_ACCOUNT": "we could not verify the bank account details you gave",
    "BANK_DETAILS_CHANGED": "we could not verify the change to your bank account",
    "DUPLICATE_KEY_NEW_NAME": "we could not match your company name to its tax registration",
    "EXISTING_VENDOR": "we could not verify the changes to your company details",
    "SHARED_CONTACT": "we could not verify your contact details",
    "SOLE_PROP_NAME_REVIEW": "we could not match the bank account holder to your business",
    "UNSUPPORTED_COUNTRY": "we do not yet onboard vendors from your country",
    "NAME_NON_LATIN": "we could not compare the names you gave",
    "BANK_COUNTRY_DIFFERS": "your bank is in a different country than your company",
    "SANCTIONS_POSSIBLE": "we are unable to onboard this company",
    "REPEATED_ATTEMPTS": "we could not verify the details you gave",
    "IDENTITY_CHANGED_BETWEEN_ATTEMPTS": "we could not verify the details you gave",
    "SERIOUS_EARLIER_REJECTION": "we are unable to onboard this company",
}
VENDOR_DOCUMENTS = {
    "DUPLICATE_BANK_ACCOUNT": "a bank letter or cancelled cheque showing your company name and account number",
    "BANK_DETAILS_CHANGED": "a letter on your bank's letterhead confirming the new account",
    "DUPLICATE_KEY_NEW_NAME": "your company registration certificate showing your current legal name",
    "EXISTING_VENDOR": "your company registration certificate or a letter describing what changed",
    "SHARED_CONTACT": "a phone number or email that belongs only to your company",
    "SOLE_PROP_NAME_REVIEW": "a document showing that you own the business and hold the bank account",
    "UNSUPPORTED_COUNTRY": "your company registration and tax registration documents",
    "NAME_NON_LATIN": "your registration certificate and a bank letter with the names in Latin letters",
    "BANK_COUNTRY_DIFFERS": "a bank letter confirming the account and why it is held in another country",
    "SANCTIONS_POSSIBLE": "your company registration certificate and details of its owners",
    "REPEATED_ATTEMPTS": "your company registration certificate and a bank letter showing your company name and account number",
    "IDENTITY_CHANGED_BETWEEN_ATTEMPTS": "your company registration certificate and a bank letter showing your company name and account number",
    "SERIOUS_EARLIER_REJECTION": "your company registration certificate and details of its owners",
}
