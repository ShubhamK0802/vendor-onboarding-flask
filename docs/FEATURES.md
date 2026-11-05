# Features

## Process (what the Zamp brief asked for)
- Takes a vendor submission by **form** (with document uploads), **JSON file**, or one of **7 built-in samples**.
- Runs **8 rule-based stages**; the run page shows each stage live as it completes.
- Four clear outcomes: Approved, Pending (Vendor to fix / Needs review), Rejected.
- **Live run view** and **dashboard** with history and CSV export.
- **Edge cases shown by samples** (one clean + six): incomplete form with wrong document; tax ID wrong for the country; name nearly matches bank holder; identity fields contradict; existing vendor changes bank account; look-alike characters in a name.

## Fraud and quality defences
- Check digits for GSTIN, PAN, IFSC, US routing, German VAT, IBAN.
- **Look-alike defence**: O/0, I/l/1 and similar swaps, hidden characters, mixed alphabets: rejected outright.
- Name comparison with suffix and legal-form handling (Pvt Ltd vs LLP vs LLC).
- Duplicate checks: same company, same bank account, shared contact, same ID under a new name, look-alike of an existing vendor.
- Bank-change detection for existing vendors (classic payment-fraud pattern).
- Sanctions (demo list), embargoed bank countries, cancelled registrations, placeholder tax IDs.

## Vendor experience
- Vendor message only on the Onboard page, in plain wording.
- Numbered "Please fix" list; reasons never reveal internal records or what matched a sanctions list.
- **Resubmit** from a fix request: the form is pre-filled (bank account number left out); old run becomes *Replaced*.
- Random submission IDs and a vendor ID for every applicant.

## Reviewer experience
- Queue of cases that need review; **take** / **give back** so two people never work one case.
- Evidence highlights the exact fields behind each finding.
- Download the vendor's uploaded documents.
- Decide: approve, reject, or request information. The vendor mail is written automatically.

## Communication
- **Outbox and background sender**: queued → sent (simulated) / sent (Brevo) / failed / no address.
- One mail thread per application (first mail, then "Re: …").
- Reminder after 3 days; automatic close after 7 days.
- Real sending via Brevo only to allow-listed addresses.

## Engineering
- Flask + SQLite + rapidfuzz; gunicorn for hosting; Render blueprint included.
- 156 automated checks (`python run_tests.py`), including a test that fills the form with the sample PDFs.
- Rules in plain config (`config.py`), no AI in the decision, every finding has a code.
- Form-submission kit (`demo_form_submission/`): sample JSON and four sample PDFs.

## Not built (and why)
Real government registries, bank-ownership verification, reading document contents, more countries, expiry tracking, persistent hosted database. These are listed on the About page as limits, each with the upgrade path.
