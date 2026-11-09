# Why the key choices were made

| Choice | Why |
|---|---|
| **Deterministic rules, not AI verdicts** | A payment-fraud control must be repeatable, explainable and auditable. |
| **Pending means one thing** | `Needs review` means staff must decide. There is no vendor-action limbo: if the vendor must change something, the application is rejected and they apply again. |
| **Reject, then apply again** | Every application is decided once. Keeping rejected-but-open applications made the process longer and blurred what each status meant. A new application reruns every check, so nothing is inherited, and the audit trail stays one row per decision. |
| **Rejected closes the application** | Wrong or missing input, hard stops, two identity contradictions, or a reviewer decision. The vendor applies again; nothing is reopened or inherited. This keeps dashboards and vendor communication truthful. |
| **Unknown registry data is “not checked”** | The local registry is a demo fixture. Treating absence from it as proof would create false rejects; treating it as verified would be dishonest. |
| **Bank-risk approval requires independent verification** | Payment diversion often compromises the submitted email or invoice. A bank change or shared account cannot be approved using only the channel that requested it. |
| **Reviewers must take a case** | Ownership avoids conflicting decisions. Only the holder can decide or release it. |
| **Internal notes never reach vendors** | Vendor wording is generated from safe mappings, so reviewer opinions, other-vendor data and screening details do not leak. |
| **Look-alike tricks are rejected outright** | O/0, I/l/1 substitutions, hidden characters and mixed alphabets are materially different from an ordinary typo. |
| **Repeat applications are linked** | From the fourth linked rejected application, an unexplained identity change, or a serious prior rejection, a reviewer decides. Honest typos cost one extra application, not a review. |
| **Exact repeat is Already registered** | The vendor did nothing wrong, but no duplicate vendor record is created. |
| **Limited country scope** | India, US and Germany are deeply tested; unsupported countries go to review rather than being weakly auto-approved. |
| **Demo mail is simulated and allowlisted** | The interface proves communication and failure handling without sending to fictional or arbitrary addresses. |
