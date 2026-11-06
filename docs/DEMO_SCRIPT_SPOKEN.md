# Spoken demo script

Hi, I’m Shubham. I chose PS-02, vendor onboarding.

The real problem is not just validating a form. It is creating a process where every application has a clear status, a clear owner, and a safe next step—without letting bad bank details slip into payments.

My happy path is simple. A vendor submits company, tax, bank and document information. Eight visible checks run: completeness, country rules, formats, documents, identity, name match, verification and duplicates. If the evidence is clean, the application is approved.

There are two kinds of pending status. Vendor action required means the problem is correctable. Needs review means only a person or independent evidence can settle it. Rejected is terminal and is reserved for hard stops, two identity contradictions, or a reviewer rejection.

I’ll start with sample 01. You can see each stage complete, then Approved. If I submit exactly the same vendor again, it says Already registered and creates nothing twice.

Now sample 02 is incomplete and has a document declared in the wrong slot. The result is Pending: Vendor action required—not rejected. The vendor gets a numbered list. Correct application opens the same application with fields prefilled and existing documents retained. The correction is a new revision, and all checks run again. No approval is inherited.

Sample 03 shows a US company with an Indian GSTIN. One contradiction may be a mistake, so it stays open for correction. Sample 05 contains two identity contradictions, which a single typo cannot explain, so that case is terminally rejected.

The most important payment-fraud case is sample 06. First I onboard sample 01; then sample 06 changes that vendor’s bank account. It cannot be auto-approved. A reviewer must take the case, compare what is the same and different, and verify outside the submitted channel. The server blocks approval until the reviewer records either a trusted-contact callback or independent bank confirmation.

The reviewer can also request information. That does not close the case. It moves the same application back to Vendor action required, and the vendor gets a safe list of evidence to provide. The reviewer’s internal note never reaches the vendor.

The dashboard shows how many cases were approved, returned to the vendor, sent to review or terminally rejected, plus who owns the next action. The Messages page proves that every outcome is queued, retried and kept in one thread per application.

The controls are deterministic and versioned; no AI makes the approval decision. Registry and sanctions data are demo fixtures, unknown registrations are honestly marked not checked, and files are type-signature checked but their content is not authenticated. Production upgrades would be real registries, bank ownership verification, malware/document checks, staff authentication, roles and CSRF protection.

That is the process: a workable happy path, controlled corrections, independent review for payment risk, terminal rejection only when justified, and clear communication at every step.
