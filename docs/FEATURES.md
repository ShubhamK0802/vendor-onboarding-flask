# Features

## Process (what the Zamp brief asked for)
- Takes a vendor submission by **form** (with document uploads), **JSON file**, or one of **7 built-in samples**.
- Runs **9 rule-based stages**; the run page shows each stage live as it completes.
- Four clear outcomes: Approved, Pending (Waiting for vendor / Needs review), Rejected.
- **Live run view** and **dashboard** with history and CSV export.
- **Edge cases shown by samples** (one clean + six): incomplete form with wrong document; tax ID wrong for the country; name nearly matches bank holder; identity fields contradict; existing vendor changes bank account; look-alike characters in a name. Each fixable one has a **corrected sample** to prove that sending the right data is approved.

## Fraud and quality defences
- Check digits for GSTIN, PAN, IFSC, US routing, German VAT, IBAN.
- **Look-alike defence**: O/0, I/l/1 and similar swaps, hidden characters, mixed alphabets: rejected outright.
- Name comparison with suffix and legal-form handling (Pvt Ltd vs LLP vs LLC).
- Duplicate checks: same company, same bank account, shared contact, same ID under a new name, look-alike of an existing vendor.
- Bank-change detection for existing vendors (classic payment-fraud pattern).
- **Repeat-attempt defence**: attempts are counted across applications; from the 4th, or when identity details change without being asked, a reviewer decides, even if the form is perfect. Rate limit per network.
- Sanctions (demo list), embargoed bank countries, cancelled registrations, placeholder tax IDs.

## Vendor experience
- Vendor message only on the Onboard page, in plain wording.
- Numbered "Please fix" list; reasons never reveal internal records or what matched a sanctions list.
- A vendor who is sent back files a **new application**, checked from scratch: no resubmission link, no pre-fill, nothing carried over. The earlier waiting one becomes *Replaced*.
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
- 168 automated checks (`python run_tests.py`), including a test that fills the form with the sample PDFs.
- Rules in plain config (`config.py`), no AI in the decision, every finding has a code.
- Form-submission kit (`demo_form_submission/`): sample JSON and four sample PDFs.

## Not built (and why)
Real government registries, bank-ownership verification, reading document contents, more countries, expiry tracking, persistent hosted database. These are listed on the About page as limits, each with the upgrade path.
