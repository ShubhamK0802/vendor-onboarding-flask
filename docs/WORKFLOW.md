# Workflow: from submission to approval

Diagrams use Mermaid (they render on GitHub, in VS Code with a Mermaid extension, or open `overview.html` in a browser).

## 1. End to end

```mermaid
flowchart TD
    A[Vendor submits form or JSON] --> B[Pipeline: 9 stages]
    B --> C{Decision rule}
    C -->|no findings| D[Approved + vendor ID]
    C -->|only fixable findings| E[Pending: Waiting for vendor]
    C -->|needs judgment| F[Pending: Needs review]
    C -->|rejects on its own / 2 red flags| G[Rejected]
    E -->|vendor files a new application within 7 days| A
    E -->|no reply in 7 days| G
    E -->|3 days, no reply| R[Reminder mail]
    F --> H[Reviewer takes the case]
    H -->|approve| D
    H -->|reject| G
    H -->|ask for info| E
    D --> M[Mail to vendor]
    E --> M
    F --> M
    G --> M
```

## 2. The pipeline

```mermaid
flowchart LR
    S1[1 Completeness] --> S2[2 Country routing] --> S3[3 Format checks] --> S4[4 Documents]
    S4 --> S5[5 Identity checks] --> S6[6 Name match] --> S7[7 Verification] --> S8[8 Duplicate check]
    S8 --> S9[9 Repeat attempts] --> D[Decision]
```

Each stage shows live on the run page as it completes. A stage that cannot run (for example country not supported) is shown as skipped, with the reason.

## 3. A new application after a fix request

```mermaid
sequenceDiagram
    participant V as Vendor
    participant S as System
    participant R as Reviewer
    V->>S: Application A
    S-->>V: Waiting for vendor: please fix 1..n (mail)
    V->>S: New application B (nothing pre-filled, nothing carried over)
    S->>S: Check B from scratch, then count linked earlier attempts
    alt clean and fewer than 4 attempts, no unasked identity change
        S-->>V: Approved
    else 4th attempt or identity changed or earlier serious rejection
        S->>R: Needs review (attempts shown)
        S-->>V: Under review
    end
    S->>S: Mark A as Replaced
```

Attempts are linked by company ID, bank account, phone, email, a near-identical company name, or the same uploaded file, within 30 days. A change to a field the earlier attempt flagged is expected and not an identity change.

## 4. Reviewer desk

```mermaid
flowchart TD
    Q[Queue: Needs review] --> T[Take: claimed by one reviewer]
    T --> V[Read findings, evidence, documents]
    V --> X{Decide}
    X -->|Approve| AP[Approved + vendor ID]
    X -->|Reject| RJ[Rejected]
    X -->|Request info| RI[Pending: Waiting for vendor]
    V -->|Give back| Q
```

Rules: only one reviewer can hold a case; only the holder can decide or give it back. The vendor mail is built automatically from the findings.

## 5. Mail

```mermaid
flowchart LR
    E[Decision made] --> O[Outbox: queued]
    O --> W[Background sender]
    W -->|demo mode| SIM["Sent (simulated)"]
    W -->|Brevo configured + allowlisted| BR["Sent (real)"]
    W -->|error| F[Failed]
    O -->|no address| N[No address]
```

One thread per application: first mail "Your vendor application (id)", later ones "Re: …". All mail is visible on the Messages page.

## 6. Pages

| Page | Purpose |
|---|---|
| Onboard vendor | Form, JSON upload, or sample; live stages; vendor message |
| Run page | One submission: stages, findings, evidence, documents |
| Review desk | Queue, take, decide |
| Dashboard | Counts, history table, export CSV |
| Messages | Outbox: every mail and its state |
| About | Rules, limits, why these countries |
