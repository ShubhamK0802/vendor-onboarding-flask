# Features

## What the Zamp brief asked for
- Takes a vendor submission by **form** (with document uploads), **JSON file**, or one of **9 built-in samples** (plus 5 corrected versions).
- Runs **rule-based stages** (8, plus an internal repeat-attempts stage when relevant); the Onboard page shows each stage live as it completes.
- Clear outcomes with the reasoning visible: **Approved** (or Already registered), **Pending: Needs review**, **Rejected** (with the reasons, and for mistakes exactly what to correct).
- **Live run view** and **dashboard** with history, status, reasons and CSV export.
- **Edge cases shown by samples:** incomplete form with a wrong document; tax ID wrong for the country; bank holder name nearly matches; identity fields contradict; existing vendor changes its bank account; look-alike characters in a name; a registered company ID with a new name and details; the same name and address with a different company ID. Each fixable one has a **corrected sample** to prove that sending the right data is approved.

## Fraud and quality defences
- Check digits for GSTIN, PAN, IFSC, US routing number, German VAT ID and IBAN.
- **Look-alike defence:** O/0, I/l/1 and similar swaps, hidden characters and mixed alphabets are rejected outright.
- Name comparison with suffix and legal-form handling (Pvt Ltd vs LLP vs LLC).
- **Already onboarded vendors:** an exact repeat is Approved as *already registered* (nothing created); changed details, a changed bank account, or the same ID under a new name go to a reviewer.
- **Same name, different company ID:** with something else in common (phone, email, address, bank account) it goes to a reviewer. The name alone does not.
- Every review note says **what is the same and what differs**.
- Duplicate checks: shared bank account, shared contact, look-alike of an existing vendor.
- **Repeat-attempt defence:** rejected attempts are counted across applications; from the 4th, or when identity details change without being asked, or after a serious earlier rejection, a reviewer decides even if the form is perfect. Rate limit per network address.
- Sanctions (demo list), embargoed bank countries, cancelled registrations, placeholder tax IDs.

## Vendor experience
- Plain messages: "Your application is rejected. We found these problems: 1... Please correct these and submit a new application."
- A vendor who is rejected files a **new application**, checked from scratch (no resubmission link, no pre-fill, nothing carried over). No waiting state, timer or reminder mails.
- The vendor's page shows the live stages, the status, the message and what they sent. It never shows internal findings, flagged-field marks, the repeat-attempts stage or a vendor ID.
- Random submission IDs; reasons never reveal internal records or what matched a sanctions list.

## Reviewer experience
- Queue of cases that need review; **take** / **give back** so two people never work one case.
- Evidence highlights the exact fields behind each finding, with a same/different comparison.
- Download the vendor's uploaded documents.
- Decide: approve, reject, or request more information (closes the application as rejected; the vendor files a new one). The vendor mail is written automatically.

## Communication
- **Outbox and background sender:** queued, then sent (simulated), sent (Brevo), failed or no address.
- One mail thread per application (verdict, then "Re: ..." for a reviewer's outcome).
- Real sending via Brevo only to allow-listed addresses.

## Engineering
- Flask + SQLite + rapidfuzz; gunicorn for hosting; Render blueprint included.
- over 200 automated checks (`python run_tests.py`): every rule, the full workflow, every web route, and the sample PDFs through the form.
- Rules in plain config (`config.py`), no AI in the decision, every finding has a code.
- Form-submission kit (`demo_form_submission/`): sample JSON and four sample PDFs.
- Working rule: test locally, then push, then deploy.

## Not built (and why)
Live in-form validation (the server rules decide), a phone-number format rule per country, real government registries, bank-ownership verification, reading document contents, more countries, expiry tracking, a persistent hosted database. The About page lists the limits with their upgrade paths.
