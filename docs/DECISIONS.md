# Why the key choices were made

| Choice | Why |
|---|---|
| **Deterministic rules, not AI verdicts** | A payment-fraud control must be repeatable, explainable and auditable. |
| **Pending has an owner** | `Vendor action required` means the vendor must correct evidence; `Needs review` means staff must decide. A status without an owner is not operational. |
| **Corrections are revisions of one application** | Ordinary mistakes do not deserve terminal rejection. Prefill reduces friction, while rerunning every check prevents inherited approval. Old revisions remain in the audit trail. |
| **Rejected means terminal** | Hard stops, two identity contradictions, or a reviewer rejection. This keeps dashboards and vendor communication truthful. |
| **Unknown registry data is “not checked”** | The local registry is a demo fixture. Treating absence from it as proof would create false rejects; treating it as verified would be dishonest. |
| **Bank-risk approval requires independent verification** | Payment diversion often compromises the submitted email or invoice. A bank change or shared account cannot be approved using only the channel that requested it. |
| **Reviewers must take a case** | Ownership avoids conflicting decisions. Only the holder can decide or release it. |
| **Internal notes never reach vendors** | Vendor wording is generated from safe mappings, so reviewer opinions, other-vendor data and screening details do not leak. |
| **Look-alike tricks are terminal** | O/0, I/l/1 substitutions, hidden characters and mixed alphabets are materially different from an ordinary typo. |
| **Fresh attempts after terminal rejection are linked** | From the fourth linked rejected application, an unexplained identity change, or a serious prior rejection, a reviewer decides. Normal corrections do not count as attacks. |
| **Exact repeat is Already registered** | The vendor did nothing wrong, but no duplicate vendor record is created. |
| **Limited country scope** | India, US and Germany are deeply tested; unsupported countries go to review rather than being weakly auto-approved. |
| **Demo mail is simulated and allowlisted** | The interface proves communication and failure handling without sending to fictional or arbitrary addresses. |
