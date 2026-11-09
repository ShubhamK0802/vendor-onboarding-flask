# Workflow: one application, one decision

This is the canonical business flow. The validation-stage diagram is secondary: it explains how evidence is checked, while this diagram explains what happens to a real application.

## 1. End-to-end lifecycle

```mermaid
flowchart TD
    A[Vendor submits form and documents] --> B[Run every applicable check]
    B --> C{What did the evidence show?}
    C -->|clear| AP[Approved]
    C -->|uncertain, duplicate risk or changed details| NR[Pending: Needs review]
    C -->|anything wrong or missing, hard stop, 2 contradictions| RJ[Rejected: closed]
    NR --> TAKE[Reviewer takes the case]
    TAKE --> DEC{Decision}
    DEC -->|approve| AP
    DEC -->|reject or request information| RJ
    RJ --> NEW[Vendor corrects the details and files a NEW application]
    NEW --> B
    AP --> MSG[Communicate outcome]
    NR --> MSG
    RJ --> MSG
```


Every application is decided once. Pending means only that a reviewer must decide. A rejected application is closed, and the vendor files a new one that starts from scratch.

## 2. Validation pipeline

```mermaid
flowchart LR
    S1[Completeness] --> S2[Country] --> S3[Formats] --> S4[Documents]
    S4 --> S5[Identity] --> S6[Name match] --> S7[Verification] --> S8[Duplicates]
    S8 --> S9[Repeat applications after a rejection, staff only] --> D[Decision]
```

The vendor sees the first eight stages live. Staff see evidence and the internal attempt control. Unknown demo-registry records are marked “not checked”; file type signatures are checked, but document contents are not read.

## 3. Reject, then apply again

```mermaid
sequenceDiagram
    participant V as Vendor
    participant S as System
    V->>S: Submit application A
    S-->>V: Rejected + numbered problems + "submit a new application"
    V->>S: Correct the details, submit application B
    S->>S: Run every check from the beginning
    S-->>V: Approved, needs review, or rejected
```

No approval is inherited and nothing from application A is reused, not even its documents. Staff see that B follows A.


## 4. Reviewer and bank-risk controls

```mermaid
flowchart TD
    Q[Needs-review queue] --> T[Reviewer takes case]
    T --> E[Read findings, comparisons and documents]
    E --> R{Bank change or shared account?}
    R -->|no| D[Approve, request information, or reject]
    R -->|yes| IV[Independent callback or bank confirmation]
    IV --> D
    D -->|request information| V[Closed as rejected: vendor files a new application]
```

The server blocks approval of a bank-change/shared-account case until an independent verification method is recorded. The reviewer's note remains internal; the vendor receives safe text generated from the findings.

## 5. Repeat applications after a rejection

Only earlier **rejected** applications count. Applications are linked by company ID, bank account, phone, email, near-identical name or reused file within 30 days. A clean fourth linked application, an unrequested identity change, or a serious earlier rejection goes to a reviewer.


## 6. Communication

Every verdict is written to an outbox before sending. Each application has its own message thread, retries are recorded, and real delivery is allowlisted. The vendor never receives internal reviewer notes, other-vendor details, vendor IDs or the reason a sanctions screen matched.

## 7. Pages

| Page | Purpose |
|---|---|
| Onboard vendor | Submit, watch stages, read the outcome, apply again if rejected |
| Reviewer desk | Queue, claim/release, evidence, independent verification, decision |
| Dashboard | Status/owner metrics, history, details, CSV export |
| Messages | Outbox, delivery state and application threads |
| About | Rules, scope, limits and upgrade path |
