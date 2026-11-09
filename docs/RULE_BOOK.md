# Rule book (version 8.0)

This document is the plain-English contract for the code. `config.py`, `checks.py` and `decide.py` are the executable source of truth.

## 1. Outcomes

| Outcome | When | Owner / next action |
|---|---|---|
| **Approved** | No findings | Complete |
| **Approved: Already registered** | Exact repeat of an onboarded vendor | Complete; create nothing new |
| **Pending: Needs review** | At least one REVIEW finding and no rejecting condition | Reviewer takes and decides |
| **Rejected** | Any wrong or missing input (FIX findings), a hard-stop code, two or more RED contradictions, or a reviewer decision | Closed. The vendor may file a new application, checked from scratch |

Decision order matters:

1. No findings → Approved.
2. Only `DUPLICATE_APPLICATION` → Approved: Already registered.
3. A hard-stop code or at least two RED findings → Rejected (no new application is invited for sanctions, embargo or look-alike-of-existing-vendor).
4. Any REVIEW finding → Pending: Needs review.
5. Otherwise (only FIX or one RED finding) → Rejected, with the problems listed and an invitation to submit a new application.

## 2. Finding levels

- **FIX:** missing data, bad format, missing/invalid file, or close name mismatch. The application is rejected and the vendor repairs it in a new application.
- **REVIEW:** evidence is inconclusive, refers to an onboarded vendor, or needs independent confirmation.
- **RED:** a cross-field identity contradiction. One is listed as a problem; two together are named as contradictions. Either way the application is rejected.

## 3. Stages

1. **Completeness:** company name, country, email, mobile, address, tax ID, bank holder, account and bank code; PAN for India.
2. **Country:** India, US and Germany route to country rules. Unsupported countries go to review.
3. **Formats:** GSTIN/PAN/IFSC, EIN/routing, VAT/IBAN/BIC, email, website and account formats/checksums.
4. **Documents:** tax and registration documents plus cheque/passbook; PDF/PNG/JPG extension and file signature; non-empty file; declared slot.
5. **Identity:** country encoded in the tax/bank ID, GSTIN/PAN consistency and company PAN type.
6. **Name match:** normalized legal names, common suffixes and umlaut transliteration; non-Latin names go to review.
7. **Verification:** demo tax registry, fictional sanctions list, embargoed bank country and placeholder IDs. Unknown demo-registry entries are explicitly “not checked.”
8. **Duplicates:** existing company ID/name/details, changed bank details, shared bank/contact and look-alike existing vendor.
9. **Repeat applications (staff only):** earlier rejected applications of the same company within 30 days.

## 4. Wrong or missing input (FIX)

Examples include missing fields/documents, invalid checksums or lengths, unsupported file type, file signature mismatch, wrong declared document slot, near-match bank-holder name, and legal-form difference. The application is rejected and closed. The vendor message lists each problem in plain words and says to submit a new application.

A new application:

- is a separate submission with its own ID and message thread;
- runs every check from scratch; nothing is inherited from the rejected one;
- is linked to earlier rejected applications for staff only, by company ID, bank account, phone, email, near-identical name or a reused file.

## 5. Review findings (REVIEW)

Examples:

- unsupported country or non-Latin name;
- foreign bank for the declared company country;
- possible sanctions match;
- existing vendor changes bank/contact/address;
- same company ID under a new name;
- same name plus another shared attribute under a different ID;
- shared bank account, phone or email;
- clean fourth application after three linked terminal rejections;
- identity changed after a terminal rejection without being requested;
- serious prior rejection.

Reviewers must claim a case. Only the holder can approve, reject, request information or release it. A reason is mandatory.

For `BANK_DETAILS_CHANGED` and `DUPLICATE_BANK_ACCOUNT`, approval is blocked until the reviewer records either:

- callback to a trusted contact obtained independently of the submitted change; or
- independent bank confirmation.

Requesting information changes the current owner to the vendor and keeps the same application open.

## 6. Terminal hard stops

These reject on their own:

- exact sanctions/watchlist match;
- embargoed bank country;
- cancelled tax registration;
- placeholder tax ID;
- look-alike character manipulation in names, IDs, routing/account values;
- hidden characters or mixed alphabets inside a word;
- look-alike name of an existing vendor.

Two RED identity contradictions also reject—for example, a tax ID from another country plus a PAN that contradicts the GSTIN.

## 7. Duplicate and existing-vendor logic

- Exact same onboarded vendor/details → Already registered.
- Same company ID, changed bank account → Needs review plus independent verification to approve.
- Same company ID, changed contact/address → Needs review.
- Same company ID, different company name → Needs review with same/different comparison.
- Different company ID, very similar name and another shared attribute → Needs review.
- Same name alone → not enough to flag.

Approved vendors join the comparison set. Vendor IDs are internal and never shown to vendors.

## 8. Repeat-application control

Only rejected applications count. From the fourth linked application in 30 days, a clean result still needs review. A serious earlier rejection or an identity field changed without being asked for also triggers review. Pending and approved applications do not count.


## 9. Vendor communication

| State | Vendor wording |
|---|---|
| Approved | “Your application is approved.” |
| Already registered | “You are already registered with us. No new application is needed.” |
| Needs review | “Your application is under review…” |
| Rejected | Plain reasons or the numbered problem list, then “This application is now closed. Please correct the details and submit a new application.” Sanctions and embargo rejections say nothing more and invite no new application. No screening mechanics or other-vendor data |
| Reviewer requests information | Closed as rejected: the required evidence list, then “Please submit a new application with them.” |

Reviewer-written notes never appear on the vendor page or in vendor mail. Each application has its own message thread.

## 10. Demo boundaries

- Registry/watchlist data are fixtures; VIES is optional.
- Document bytes and type signatures are checked, not document meaning or authenticity.
- Bank ownership is not available automatically.
- No authentication, role-based access, malware scanning, CSRF defence or encrypted object storage.
- SQLite and in-memory progress are suitable for a one-instance case-study demo, not production scale.
