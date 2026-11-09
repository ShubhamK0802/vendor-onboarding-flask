# Features

## Zamp brief coverage

- Runnable vendor form with PDF/PNG/JPG uploads, JSON upload, and nine demo scenarios.
- Eight visible validation stages plus an internal repeat-attempt stage when relevant.
- Clear Approved, Needs review and Rejected outcomes with reasons and the next owner.
- Reject, then apply again: wrong input is rejected with plain reasons, and the vendor files a new application that is checked from scratch.
- Reviewer queue with search, sort, claim/release, evidence, documents and audited decisions.
- Dashboard with metrics, history, reasons, waiting owner and CSV export.
- Automatic vendor communication through an outbox, including failures and one thread per application.

## Fraud and quality controls

- GSTIN, PAN, IFSC, EIN/routing, VAT, IBAN and BIC format/checksum controls.
- Cross-field identity consistency and normalized legal-name comparison.
- Look-alike, hidden-character and mixed-alphabet detection.
- Demo registry, sanctions, embargo and placeholder-ID screening with honest “not checked” states.
- Duplicate vendor, company ID, bank account, phone, email and changed-detail checks.
- Same/different evidence for reviewers, with bank account numbers masked.
- Bank change/shared-account approval requires an independently recorded callback or bank confirmation.
- Repeat applications after a rejection are linked for staff; a fourth in 30 days goes to a reviewer.
- Random run IDs, upload-size limit, file-signature checks and network submission rate limiting.

## Communication and privacy

- Vendors see their status, submitted data and safe next steps—not vendor IDs, other vendors, internal findings, reviewer notes, or attempt controls.
- Rejections list the problems in plain words and say to submit a new application.
- Reviewer information requests close the application as rejected and state which evidence to send in a new one.
- Mail is queued before sending, retried three times, simulated by default, and allowlisted for real delivery.

## Deliberate demo limits

- No staff login, roles or CSRF protection.
- Demo registries/watchlist; automatic bank ownership is unavailable.
- Files are stored and type-signature checked, but document content, authenticity and expiry are not validated.
- India, US and Germany only; unsupported countries go to review.
- SQLite and in-memory live progress are single-instance choices.
