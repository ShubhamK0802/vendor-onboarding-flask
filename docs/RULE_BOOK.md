# Rule book (version 7.0)

This document is the plain-English contract for the code. `config.py`, `checks.py` and `decide.py` are the executable source of truth.

## 1. Outcomes

| Outcome | When | Owner / next action |
|---|---|---|
| **Approved** | No findings | Complete |
| **Approved: Already registered** | Exact repeat of an onboarded vendor | Complete; create nothing new |
| **Pending: Vendor action required** | Only FIX findings, or one RED contradiction without a hard stop | Vendor corrects the same application |
| **Pending: Needs review** | At least one REVIEW finding and no terminal condition | Reviewer takes and decides |
| **Rejected** | Hard-stop code, two or more RED contradictions, or reviewer rejection | Terminal |

Decision order matters:

1. No findings → Approved.
2. Only `DUPLICATE_APPLICATION` → Approved: Already registered.
3. A hard-stop code or at least two RED findings → Rejected.
4. Any REVIEW finding → Pending: Needs review.
5. Otherwise → Pending: Vendor action required.

## 2. Finding levels

- **FIX:** missing data, bad format, missing/invalid file, or close name mismatch. The vendor can repair it.
- **REVIEW:** evidence is inconclusive, refers to an onboarded vendor, or needs independent confirmation.
- **RED:** a cross-field identity contradiction. One may be a mistake; two together are terminal.

## 3. Stages

1. **Completeness:** company name, country, email, mobile, address, tax ID, bank holder, account and bank code; PAN for India.
2. **Country:** India, US and Germany route to country rules. Unsupported countries go to review.
3. **Formats:** GSTIN/PAN/IFSC, EIN/routing, VAT/IBAN/BIC, email, website and account formats/checksums.
4. **Documents:** tax and registration documents plus cheque/passbook; PDF/PNG/JPG extension and file signature; non-empty file; declared slot.
5. **Identity:** country encoded in the tax/bank ID, GSTIN/PAN consistency and company PAN type.
6. **Name match:** normalized legal names, common suffixes and umlaut transliteration; non-Latin names go to review.
7. **Verification:** demo tax registry, fictional sanctions list, embargoed bank country and placeholder IDs. Unknown demo-registry entries are explicitly “not checked.”
8. **Duplicates:** existing company ID/name/details, changed bank details, shared bank/contact and look-alike existing vendor.
9. **Fresh attempts (staff only):** terminally rejected linked applications within 30 days. Normal revisions are excluded.

## 4. Correctable findings (FIX)

Examples include missing fields/documents, invalid checksums or lengths, unsupported file type, file signature mismatch, wrong declared document slot, near-match bank-holder name, and legal-form difference. The vendor message lists each correction and links to a prefilled form.

A correction:

- keeps the application ID;
- creates a new immutable revision;
- retains old documents unless replaced;
- reruns every check;
- supersedes the old actionable revision;
- remains in the same message thread.

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

## 8. Fresh-attempt control

Only terminally rejected applications count. Links may be company ID, bank account, phone, email, near-identical name or a reused file. From the fourth linked application, a clean result still needs review. A serious earlier rejection or an identity field changed without being requested also triggers review. Pending corrections, pending review and approved applications do not count.

## 9. Vendor communication

| State | Vendor wording |
|---|---|
| Approved | “Your application is approved.” |
| Already registered | “You are already registered with us. No new application is needed.” |
| Vendor action | Numbered correction list, then “continue this application.” |
| Needs review | “Your application is under review…” |
| Terminal rejection | Safe reason only; no screening mechanics or other-vendor data |
| Reviewer requests information | Required evidence list plus **Correct application** |

Reviewer-written notes never appear on the vendor page or in vendor mail. All messages use one thread per application.

## 10. Demo boundaries

- Registry/watchlist data are fixtures; VIES is optional.
- Document bytes and type signatures are checked, not document meaning or authenticity.
- Bank ownership is not available automatically.
- No authentication, role-based access, malware scanning, CSRF defence or encrypted object storage.
- SQLite and in-memory progress are suitable for a one-instance case-study demo, not production scale.
