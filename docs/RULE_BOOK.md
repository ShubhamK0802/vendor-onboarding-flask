# Rule book: vendor onboarding (rules v6.0)

Every decision is made by fixed rules in code (`checks.py`, `decide.py`, `config.py`). No AI decides. The same submission always gets the same answer, and every finding names the rule that raised it.

## 1. The four outcomes

| Status | Meaning | Who acts next |
|---|---|---|
| **Approved** | No findings. A vendor ID is issued. | Nobody |
| **Pending: Waiting for vendor** | Only things the vendor can correct (typo, missing field or document). The vendor gets a numbered list. | Vendor, within 7 days |
| **Pending: Needs review** | A case that needs human judgment. The vendor is told it is under review. | Reviewer |
| **Rejected** | Cannot be approved as submitted; a correction or a review would not change that. The vendor is told the reason. | Nobody (vendor may start a new application) |
| *Replaced* | Final state of a waiting application when the same applicant files a new one. Nothing is carried over. | Nobody |

## 2. Finding levels

| Level | Name | Meaning |
|---|---|---|
| 1 | FIX | The vendor can fix it |
| 2 | REVIEW | Needs a person's judgment |
| 3 | RED | Identity contradiction (one is probably a typo; two at once are not) |

## 3. The decision rule (in order)

1. No findings → **Approved**.
2. Any "rejects on its own" finding (section 6), **or** two or more RED findings → **Rejected**.
3. Any REVIEW finding (including a repeat-attempt finding, section 5.9) → **Pending: Needs review**.
4. Otherwise → **Pending: Waiting for vendor**.

## 4. The nine stages (run in this order)

| # | Stage | What it checks |
|---|---|---|
| 1 | Completeness | Every required field is filled in |
| 2 | Country routing | Country is India, US or Germany; anything else goes to a reviewer |
| 3 | Format checks | Shape and check digits of IDs, bank codes, account numbers, email |
| 4 | Documents | Required documents present, right type, not empty, right slot |
| 5 | Identity checks | The IDs agree with each other and with the country |
| 6 | Name match | Company name against bank account holder name |
| 7 | Verification | Registry, sanctions, embargo, placeholder IDs |
| 8 | Duplicate check | Against vendors already onboarded |
| 9 | Repeat attempts | Earlier applications by the same applicant |

## 5. Rules by stage

### 5.1 Completeness
- Required for all: company name, entity type, country, email, mobile, address, tax ID, bank account holder, bank account number, bank code.
- India also requires PAN.
- Missing → `MISSING_FIELD` (FIX).

### 5.2 Country routing
- Supported: **IN, US, DE**. Others → `UNSUPPORTED_COUNTRY` (REVIEW).
- Why these three: India (the home market), the US (largest foreign market) and Germany (the EU, with IBAN/VAT rules that differ from both).

### 5.3 Format checks
| Country | Tax ID | Other IDs | Bank |
|---|---|---|---|
| India | GSTIN: 15 characters with check character (`BAD_GSTIN_FORMAT`, `BAD_GSTIN_CHECKSUM`) | PAN: `AAAAA9999A` (`BAD_PAN_FORMAT`) | IFSC: 4 letters, `0`, 6 characters (`BAD_IFSC_FORMAT`); account number length/digits (`BAD_ACCOUNT_FORMAT`) |
| US | EIN: 9 digits (`BAD_EIN_FORMAT`) | | Routing: 9 digits plus checksum (`BAD_ROUTING_FORMAT`, `BAD_ROUTING_CHECKSUM`); account number (`BAD_ACCOUNT_FORMAT`) |
| Germany | VAT ID: `DE` + 9 digits plus check digit (`BAD_VAT_FORMAT`, `BAD_VAT_CHECKSUM`) | | IBAN with checksum (`BAD_IBAN_FORMAT`, `BAD_IBAN_CHECKSUM`); BIC (`BAD_BIC_FORMAT`) |

- Email must look valid (`BAD_EMAIL_FORMAT`).
- A format failure is FIX (an honest typo) **unless** the value fails only because of look-alike characters or hidden characters (section 6).

### 5.4 Documents
- Required: **tax document** and **registration document**, plus **bank proof** (voided cheque *or* passbook page).
- Allowed types: PDF, PNG, JPG.
- Findings (all FIX): `MISSING_DOCUMENT`, `MISSING_BANK_PROOF`, `MALFORMED_DOCUMENT`, `BAD_FILE_TYPE`, `EMPTY_FILE`, `WRONG_SLOT`.
- **Limit:** the file's contents are not read. Only the slot, the type and "not empty" are checked. The file is stored so a reviewer can download it.

### 5.5 Identity checks
| Finding | Level | Trigger |
|---|---|---|
| `GSTIN_PAN_MISMATCH` | RED | The PAN inside the GSTIN differs from the PAN given |
| `PAN_ENTITY_MISMATCH` | RED | PAN 4th letter does not fit entity type (company C, individual P, partnership/LLP F, trust T) |
| `ID_COUNTRY_MISMATCH` | RED | The tax ID is shaped like another country's ID |
| `BANK_COUNTRY_DIFFERS` | REVIEW | German company with an IBAN from another country |

### 5.6 Name match (company name vs bank account holder)
Names are compared after removing company suffixes (Private, Pvt, Limited, Ltd, LLP, Inc, LLC, Corp, GmbH, AG, and so on) and ignoring case and punctuation. Checked in this order:

| Order | Finding | Level | Trigger |
|---|---|---|---|
| 1 | `HIDDEN_CHARACTERS` | REVIEW → rejects | Invisible characters or mixed alphabets inside a word |
| 2 | `NAME_NON_LATIN` | REVIEW | A name is not in Latin letters |
| 3 | `LOOKALIKE_NAME` | REVIEW → rejects | Names differ only in look-alike characters (`Gl0bex` / `Globex`) |
| 4 | `LEGAL_FORM_DIFFERENCE` | FIX | Different legal form (LLP vs LLC) |
| 5 | `SUFFIX_DIFFERENCE` | REVIEW | Same name, different suffix |
| 6 | `NAME_NEAR_MISS` | FIX | Similarity 80 or more but not identical |
| 7 | `SOLE_PROP_NAME_REVIEW` | REVIEW | Sole proprietor: holder differs from company |
| 8 | `NAME_MISMATCH` | RED | Names clearly different |

Identical names pass. Names such as *34square* or *add360* are fine: only two names are compared with each other, never a name against a pattern.

### 5.7 Verification
| Finding | Level | Trigger |
|---|---|---|
| `PLACEHOLDER_TAX_ID` | REVIEW → rejects | Tax ID is a placeholder (all same digit, long runs, 123456789) |
| `REGISTRY_NOT_FOUND` | FIX | German VAT ID not registered |
| `REGISTRY_CANCELLED` | REVIEW → rejects | Registration cancelled or inactive |
| `REGISTRY_NAME_MISMATCH` | RED | Name differs from the registered name |
| `SANCTIONS_MATCH` | REVIEW → rejects | Name matches the sanctions list |
| `SANCTIONS_POSSIBLE` | REVIEW | Name is close to a listed name |
| `EMBARGOED_BANK_COUNTRY` | REVIEW → rejects | Bank in KP, IR, SY or CU |

Registry and sanctions are **demo data** (`registry.json`, `sanctions.json`, fictional). German VAT can optionally use the live EU VIES service with `VIES_LIVE=1`.

### 5.8 Duplicate check (against vendors on file)
| Finding | Level | Trigger |
|---|---|---|
| `DUPLICATE_APPLICATION` | REVIEW → rejects | Same company, exactly the same details |
| `EXISTING_VENDOR` | REVIEW | Same company, contact or address changed |
| `BANK_DETAILS_CHANGED` | REVIEW | Same company, different bank account (classic payment-fraud pattern) |
| `DUPLICATE_KEY_NEW_NAME` | REVIEW | Same company ID under a different name |
| `DUPLICATE_BANK_ACCOUNT` | REVIEW | Bank account belongs to another company |
| `SHARED_CONTACT` | REVIEW | Phone or email belongs to another company |
| `LOOKALIKE_OF_EXISTING_VENDOR` | REVIEW → rejects | Name differs from an existing vendor only by look-alike characters |

### 5.9 Repeat attempts (against earlier applications, not vendors on file)
An earlier application counts as the same applicant when it shares a company ID, bank account, phone or email, has a company name 92% or more similar, or has a byte-identical uploaded file, and was made in the last 30 days. Approved ones are not attempts (the duplicate check handles them).

| Finding | Level | Trigger |
|---|---|---|
| `REPEATED_ATTEMPTS` | REVIEW | 3 or more earlier linked attempts: the 4th goes to a reviewer, even if it is perfect |
| `IDENTITY_CHANGED_BETWEEN_ATTEMPTS` | REVIEW | Bank account, tax ID, PAN or company name differs from an earlier attempt and nobody asked for that change (fields the earlier attempt flagged may change) |
| `SERIOUS_EARLIER_REJECTION` | REVIEW | An earlier linked attempt was stopped for a serious reason (sanctions, look-alike, placeholder ID, embargo, cancelled registration) |

The vendor is only told "under review", never why. A reviewer sees the finding text. **Rate limit:** more than 30 submissions per hour from one network address are refused. **Ceiling:** an applicant who changes every identifier and has real identities behind each is not linked; the fix is real registry and bank verification (a production upgrade).

## 6. Rejected on its own (no "please fix", straight to Rejected)

| Code | What the vendor is told |
|---|---|
| `DUPLICATE_APPLICATION` | Your company is already onboarded with exactly these details |
| `SANCTIONS_MATCH` | We are unable to onboard this company (deliberately vague) |
| `EMBARGOED_BANK_COUNTRY` | We cannot make payments to a bank in that country |
| `REGISTRY_CANCELLED` | Your tax registration is shown as cancelled or inactive |
| `PLACEHOLDER_TAX_ID` | The tax ID is a placeholder, not a real number |
| `LOOKALIKE_CHARACTERS` | Some details contain characters that look like other letters or digits |
| `HIDDEN_CHARACTERS` | Some details contain hidden characters or mixed alphabets |
| `LOOKALIKE_NAME` | Two names look identical but use look-alike characters |
| `LOOKALIKE_OF_EXISTING_VENDOR` | Your company name could not be accepted |

**Look-alike folding:** `0/O→o`, `1/I→l`, `5→s`, `8→b`, `2→z`, `6→g`. Honest typos are rarely made only of look-alike swaps, so these are rejected rather than sent back. Other rejection routes: two RED findings at once; no reply within 7 days; a reviewer's decision.

The vendor is never told what matched a sanctions list, which other vendor was involved, or anything from our internal records.

## 7. Time rules
- Fix requests close after **7 days** with no reply (`Rejected`).
- A reminder is sent after **3 days**.
- A vendor who is sent back files a **new application**. It is checked from scratch (no pre-fill, nothing inherited); the earlier waiting application becomes *Replaced*.

## 8. What the vendor is told

| Outcome | Message |
|---|---|
| Approved | "Your application is approved." |
| Needs review | "Your application is under review. We will reach back to you if anything is needed." |
| Waiting for vendor | "Please fix:" then a numbered list |
| Rejected | "Your application is rejected because …" |

A reviewer's decision produces the same wording automatically, built from what the checks found (`VENDOR_REASONS`, `VENDOR_DOCUMENTS`); the reviewer types nothing. All messages for one application go in the same mail thread ("Re: …").

## 9. IDs
- **Submission ID**: random 8 hex characters (cannot be guessed or forged in sequence).
- **Vendor ID**: `V` + country code + 6 hex, for example `VIN3FA9C2`. Issued to every applicant, one per applicant.

## 10. Known limits
Registry and sanctions are demo data. Bank-account ownership is not verified with a bank. Document contents are not read, so a forged document of the right type passes that stage. India, US and Germany only; one bank account per submission. No document expiry tracking. Mail is simulated unless Brevo is configured. SQLite resets on free hosting.
