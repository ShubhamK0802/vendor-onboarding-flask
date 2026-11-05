# Rule book: vendor onboarding (rules v6.0)

Every decision is made by fixed rules in code (`checks.py`, `decide.py`, `config.py`). No AI decides. The same submission always gets the same answer, and every finding names the rule that raised it.

## 1. The three outcomes

| Status | Meaning | Who acts next |
|---|---|---|
| **Approved** | No findings. A vendor ID is issued (internal: the vendor never sees it). | Nobody |
| **Approved: Already registered** | An exact repeat of an onboarded vendor (nothing new). Nothing is created; the vendor is told it is already registered. | Nobody |
| **Pending: Needs review** | A case that needs human judgment. The vendor is told it is under review. | Reviewer |
| **Rejected** | This application cannot be approved as submitted: a rule rejects it, or it only has mistakes or gaps the vendor can correct. The vendor is told why (for mistakes and gaps, exactly what to correct). | Nobody. The vendor files a **new application** |

## 2. Finding levels

| Level | Name | Meaning |
|---|---|---|
| 1 | FIX | The vendor can fix it |
| 2 | REVIEW | Needs a person's judgment |
| 3 | RED | Identity contradiction (one is probably a typo; two at once are not) |

## 3. The decision rule (in order)

1. No findings → **Approved**. Only `DUPLICATE_APPLICATION` → **Approved: Already registered**.
2. Any "rejects on its own" finding (section 6), **or** two or more RED findings → **Rejected**.
3. Any REVIEW finding (including a repeat-attempt finding, section 5.9) → **Pending: Needs review**.
4. Otherwise (only things the vendor can correct: a typo, a missing field or document) → **Rejected**, and the message lists exactly what to correct.

There is no waiting state, no timer and no reminder: nothing is pending on the vendor's side. A corrected form is a new application, checked from scratch.

## 4. The stages (run in this order; stage 9 is internal and runs only when the applicant is not already onboarded and has earlier rejected attempts)

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
| `DUPLICATE_APPLICATION` | (outcome) | Same company, exactly the same details: **Approved, already registered** |
| `SAME_NAME_DIFFERENT_COMPANY_ID` | REVIEW | Same name (92% or more) and the same phone, email, address or bank account as an onboarded vendor, but a different company ID. The name alone is not enough |
| `EXISTING_VENDOR` | REVIEW | Same company, contact or address changed |
| `BANK_DETAILS_CHANGED` | REVIEW | Same company, different bank account (classic payment-fraud pattern) |
| `DUPLICATE_KEY_NEW_NAME` | REVIEW | Same company ID under a different name |
| `DUPLICATE_BANK_ACCOUNT` | REVIEW | Bank account belongs to another company |
| `SHARED_CONTACT` | REVIEW | Phone or email belongs to another company |
| `LOOKALIKE_OF_EXISTING_VENDOR` | REVIEW → rejects | Name differs from an existing vendor only by look-alike characters |

The review findings here (`EXISTING_VENDOR`, `BANK_DETAILS_CHANGED`, `DUPLICATE_KEY_NEW_NAME`, `SAME_NAME_DIFFERENT_COMPANY_ID`) each carry a note for the reviewer saying **what is the same and what differs**, for example "Same: company ID, email. Different: company name (Apex Global to Apex Holdings); bank account (****7891 to ****4321); phone; address." The vendor is only told "under review".

### 5.9 Repeat attempts (against earlier applications, not vendors on file)
An earlier application counts as the same applicant when it shares a company ID, bank account, phone or email, has a company name 92% or more similar, or has a byte-identical uploaded file, and was made in the last 30 days. **Only rejected earlier applications are attempts** (the vendor was turned away and tried again). An approved one, an 'already registered' one, or one still waiting for a reviewer is not an attempt, and a company that is already onboarded skips this stage entirely: the duplicate check covers it. The stage is internal: it is recorded and shown to staff (reviewer desk, dashboard detail) but never shown to the vendor.

| Finding | Level | Trigger |
|---|---|---|
| `REPEATED_ATTEMPTS` | REVIEW | 3 or more earlier linked attempts: the 4th goes to a reviewer, even if it is perfect |
| `IDENTITY_CHANGED_BETWEEN_ATTEMPTS` | REVIEW | Bank account, tax ID, PAN or company name differs from an earlier attempt and nobody asked for that change (fields the earlier attempt flagged may change) |
| `SERIOUS_EARLIER_REJECTION` | REVIEW | An earlier linked attempt was stopped for a serious reason (sanctions, look-alike, placeholder ID, embargo, cancelled registration) |

The vendor is only told "under review", never why. The vendor's own page also hides the findings table, the flagged-field marks and the vendor ID. A reviewer sees the finding text. **Rate limit:** more than 30 submissions per hour from one network address are refused. **Ceiling:** an applicant who changes every identifier and has real identities behind each is not linked; the fix is real registry and bank verification (a production upgrade).

## 6. Rejected on its own (no "please fix", straight to Rejected)

| Code | What the vendor is told |
|---|---|
| `SANCTIONS_MATCH` | We are unable to onboard this company (deliberately vague) |
| `EMBARGOED_BANK_COUNTRY` | We cannot make payments to a bank in that country |
| `REGISTRY_CANCELLED` | Your tax registration is shown as cancelled or inactive |
| `PLACEHOLDER_TAX_ID` | The tax ID is a placeholder, not a real number |
| `LOOKALIKE_CHARACTERS` | Some details contain characters that look like other letters or digits |
| `HIDDEN_CHARACTERS` | Some details contain hidden characters or mixed alphabets |
| `LOOKALIKE_NAME` | Two names look identical but use look-alike characters |
| `LOOKALIKE_OF_EXISTING_VENDOR` | Your company name could not be accepted |

**Look-alike folding:** `0/O→o`, `1/I→l`, `5→s`, `8→b`, `2→z`, `6→g`. Honest typos are rarely made only of look-alike swaps, so these are rejected rather than sent back. Other rejection routes: two RED findings at once; a reviewer's decision.

The vendor is never told what matched a sanctions list, which other vendor was involved, or anything from our internal records.

## 7. What the vendor is told

| Outcome | Message |
|---|---|
| Approved | "Your application is approved." |
| Needs review | "Your application is under review. We will reach back to you if anything is needed." |
| Already registered | "You are already registered with us. No new application is needed." |
| Rejected: only mistakes or gaps | "Your application is rejected. We found these problems:" then a numbered list (for example "Tax ID is missing", "The file in the Registration document field is a different document: upload your registration document there"), then "Please correct these and submit a new application." |
| Rejected: a rule | "Your application is rejected because <safe reason>. If this was a mistake, submit a new application." |

**Reviewer decisions:** Approve gives *Approved by reviewer*; Reject gives *Rejected by reviewer* with a reason worked out from the findings; **Request more info** closes the application as *Rejected: information needed* and tells the vendor which documents to send, after which the vendor files a new application. A reviewer's decision produces the same wording automatically, built from what the checks found (`VENDOR_REASONS`, `VENDOR_DOCUMENTS`); the reviewer types nothing. All messages for one application go in the same mail thread ("Re: …").

## 8. IDs
- **Submission ID**: random 8 hex characters (cannot be guessed or forged in sequence).
- **Vendor ID**: `V` + country code + 6 hex, for example `VIN3FA9C2`. Issued to every applicant, one per applicant. Internal: shown to staff (reviewer desk, dashboard, CSV), never to the vendor.

## 9. Known limits
Registry and sanctions are demo data. Bank-account ownership is not verified with a bank. Document contents are not read, so a forged document of the right type passes that stage. India, US and Germany only; one bank account per submission. No document expiry tracking. Mail is simulated unless Brevo is configured. SQLite resets on free hosting. The form has no live in-field validation and there is no phone-number format rule per country (the server rules decide).
