# Spoken demo script

Hi, I’m Shubham. I chose PS-02, vendor onboarding.

The real problem is not just validating a form. It is creating a process where every application has a clear status, a clear owner, and a safe next step—without letting bad bank details slip into payments.

My happy path is simple. A vendor submits company, tax, bank and document information. Eight visible checks run: completeness, country rules, formats, documents, identity, name match, verification and duplicates. If the evidence is clean, the application is approved.

There is only one pending status: Needs review, meaning a person or independent evidence must settle it. Everything else is decided once. If the vendor got something wrong or left something out, the application is Rejected and closed, the message says why in plain words, and the vendor files a new application that is checked from scratch.

I’ll start with sample 01. You can see each stage complete, then Approved. If I submit exactly the same vendor again, it says Already registered and creates nothing twice.

Now sample 02 is incomplete and has a document declared in the wrong slot. The result is Rejected, with a numbered list of exactly what to fix. Nothing stays open and nothing is carried over: the vendor corrects the form and submits a new application, and all checks run again. No approval is inherited.

Sample 03 shows a US company with an Indian GSTIN. It is rejected, and the message says the tax ID does not fit the country. Sample 05 contains two identity contradictions, and the message names both of them in plain words.

The most important payment-fraud case is sample 06. First I onboard sample 01; then sample 06 changes that vendor’s bank account. It cannot be auto-approved. A reviewer must take the case, compare what is the same and different, and verify outside the submitted channel. The server blocks approval until the reviewer records either a trusted-contact callback or independent bank confirmation.

The reviewer can also request information. That closes the application as rejected, and the vendor gets a safe list of evidence to send in a new application. The reviewer’s internal note never reaches the vendor.

The dashboard shows how many cases were approved, sent to review or rejected, plus who owns the next action. The Messages page proves that every outcome is queued, retried and kept in its own thread.

The controls are deterministic and versioned; no AI makes the approval decision. Registry and sanctions data are demo fixtures, unknown registrations are honestly marked not checked, and files are type-signature checked but their content is not authenticated. Production upgrades would be real registries, bank ownership verification, malware/document checks, staff authentication, roles and CSRF protection.

That is the process: a workable happy path, reject then apply again, independent review for payment risk, and clear communication at every step.
