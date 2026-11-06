# Workflow: one application, one clear owner

This is the canonical business flow. The validation-stage diagram is secondary: it explains how evidence is checked, while this diagram explains what happens to a real application.

## 1. End-to-end lifecycle

```mermaid
flowchart TD
    A[Vendor submits form and documents] --> B[Run every applicable check]
    B --> C{What did the evidence show?}
    C -->|clear| AP[Approved]
    C -->|correctable gap or one likely mistake| VA[Pending: Vendor action required]
    C -->|uncertain, duplicate risk or changed details| NR[Pending: Needs review]
    C -->|hard stop or 2 contradictions| RJ[Rejected: terminal]
    VA --> FIX[Vendor opens prefilled application and corrects it]
    FIX --> REV[Save a new revision under the same application ID]
    REV --> B
    NR --> TAKE[Reviewer takes the case]
    TAKE --> DEC{Decision}
    DEC -->|approve| AP
    DEC -->|request information| VA
    DEC -->|reject| RJ
    AP --> MSG[Communicate outcome]
    VA --> MSG
    NR --> MSG
    RJ --> MSG
```

The owner is always visible: vendor, reviewer, or nobody because the case is complete.

## 2. Validation pipeline

```mermaid
flowchart LR
    S1[Completeness] --> S2[Country] --> S3[Formats] --> S4[Documents]
    S4 --> S5[Identity] --> S6[Name match] --> S7[Verification] --> S8[Duplicates]
    S8 --> S9[Fresh attempts after terminal rejection, staff only] --> D[Decision]
```

The vendor sees the first eight stages live. Staff see evidence and the internal attempt control. Unknown demo-registry records are marked “not checked”; file type signatures are checked, but document contents are not read.

## 3. Correction loop

```mermaid
sequenceDiagram
    participant V as Vendor
    participant S as System
    V->>S: Submit application A, revision 1
    S-->>V: Pending: vendor action required + numbered corrections
    V->>S: Open Correct application
    S-->>V: Prefilled fields and retained documents
    V->>S: Submit revision 2
    S->>S: Rerun every check from the beginning
    S-->>V: Approved, still pending, needs review, or rejected
```

No approval is inherited. Old revisions remain in the audit trail, while only the latest revision is actionable. Corrections do not count as fresh attempts.

## 4. Reviewer and bank-risk controls

```mermaid
flowchart TD
    Q[Needs-review queue] --> T[Reviewer takes case]
    T --> E[Read findings, comparisons and documents]
    E --> R{Bank change or shared account?}
    R -->|no| D[Approve, request information, or reject]
    R -->|yes| IV[Independent callback or bank confirmation]
    IV --> D
    D -->|request information| V[Vendor action required: same application]
```

The server blocks approval of a bank-change/shared-account case until an independent verification method is recorded. The reviewer's note remains internal; the vendor receives safe text generated from the findings.

## 5. Fresh applications after terminal rejection

Only earlier **terminally rejected** applications count. Applications are linked by company ID, bank account, phone, email, near-identical name or reused file within 30 days. A clean fourth linked application, an unrequested identity change, or a serious earlier rejection goes to a reviewer. This control is separate from the normal correction loop.

## 6. Communication

Every verdict is written to an outbox before sending. Messages are grouped by application ID, retries are recorded, and real delivery is allowlisted. The vendor never receives internal reviewer notes, other-vendor details, vendor IDs or the reason a sanctions screen matched.

## 7. Pages

| Page | Purpose |
|---|---|
| Onboard vendor | Submit, watch stages, read the outcome, correct an open application |
| Reviewer desk | Queue, claim/release, evidence, independent verification, decision |
| Dashboard | Status/owner metrics, history, details, CSV export |
| Messages | Outbox, delivery state and application threads |
| About | Rules, scope, limits and upgrade path |
