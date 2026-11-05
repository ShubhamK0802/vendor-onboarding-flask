# Workflow: from submission to decision

Diagrams use Mermaid (they render on GitHub, in VS Code with a Mermaid extension, or open `overview.html` in a browser).

## 1. End to end

```mermaid
flowchart TD
    A[Vendor submits form, JSON or sample] --> B[Pipeline: 8 stages + repeat attempts when relevant]
    B --> C{Decision rule}
    C -->|no findings| D[Approved]
    C -->|exact repeat of an onboarded vendor| AR[Approved: Already registered]
    C -->|needs a person to decide| F[Pending: Needs review]
    C -->|a rule rejects it / 2 red flags| G[Rejected]
    C -->|only mistakes or gaps the vendor can correct| G
    G -->|vendor corrects and files a new application| A
    F --> H[Reviewer takes the case]
    H -->|approve| D
    H -->|reject| G
    H -->|request more info| G
    D --> M[Mail to vendor]
    AR --> M
    F --> M
    G --> M
```

## 2. The pipeline

```mermaid
flowchart LR
    S1[1 Completeness] --> S2[2 Country routing] --> S3[3 Format checks] --> S4[4 Documents]
    S4 --> S5[5 Identity checks] --> S6[6 Name match] --> S7[7 Verification] --> S8[8 Duplicate check]
    S8 --> S9[9 Repeat attempts: staff only, when relevant] --> D[Decision]
```

Each stage shows live on the Onboard page as it completes. A stage that cannot run is shown as skipped, with the reason (for example "tax ID not in the demo registry, not checked"). Stage 9 is recorded for staff and never shown to the vendor; it only runs when the applicant is not already onboarded and has earlier rejected applications.

## 3. An applicant who is already onboarded, and look-alikes of one

```mermaid
flowchart TD
    A[New application] --> B{Company ID already onboarded?}
    B -->|yes| C{What differs?}
    C -->|nothing| D[Approved: Already registered, nothing created]
    C -->|company name| E[Needs review: same ID, different name]
    C -->|bank account| F[Needs review: bank change, verify by calling the number on file]
    C -->|contact or address| G[Needs review: details changed]
    B -->|no| H{Name 92 percent or more like an onboarded vendor?}
    H -->|yes, and phone, email, address or bank account also match| I[Needs review: same name, different company ID]
    H -->|no| J[Other checks continue: a shared bank account or contact still goes to review]
```

Every one of these review notes tells the reviewer **what is the same and what differs**, for example "Same: company ID, email. Different: company name (Apex Global to Apex Holdings); bank account (****7891 to ****4321)".

## 4. A new application after a rejection

```mermaid
sequenceDiagram
    participant V as Vendor
    participant S as System
    participant R as Reviewer
    V->>S: Application A
    S-->>V: Rejected. We found these problems 1..n. Please correct and submit a new application (mail)
    V->>S: New application B (nothing pre-filled, nothing carried over)
    S->>S: Check B from scratch, then count earlier REJECTED attempts by the same applicant
    alt clean, fewer than 4 attempts, no unasked identity change
        S-->>V: Approved
    else 4th attempt, identity changed without being asked, or an earlier serious rejection
        S->>R: Needs review (attempts shown to staff)
        S-->>V: Under review (never says why)
    end
```

Attempts are linked by company ID, bank account, phone, email, a near-identical company name, or the same uploaded file, within 30 days. Only **rejected** earlier applications count. A change to a field the earlier attempt flagged is expected and is not an identity change. More than 30 submissions an hour from one network address are refused.

## 5. Reviewer desk

```mermaid
flowchart TD
    Q[Queue: Needs review] --> T[Take: claimed by one reviewer]
    T --> V[Read findings, same and different comparison, documents]
    V --> X{Decide}
    X -->|Approve| AP[Approved]
    X -->|Reject| RJ[Rejected, reason built from the findings]
    X -->|Request more info| RI[Rejected: vendor told what to send and files a new application]
    V -->|Give back| Q
```

Only one reviewer can hold a case; only the holder can decide or give it back. The vendor mail is built automatically from the findings: the reviewer types nothing and nothing internal reaches the vendor.

## 6. Mail

```mermaid
flowchart LR
    E[Decision made] --> O[Outbox: queued]
    O --> W[Background sender]
    W -->|demo mode| SIM["Sent (simulated)"]
    W -->|Brevo configured and allowlisted| BR["Sent (real)"]
    W -->|error, retried 3 times| F[Failed]
    O -->|no address| N[No address]
```

One thread per application: the verdict first, then a reviewer's outcome as "Re: ...". All mail is visible on the Messages page.

## 7. What each person sees

| | Vendor (Onboard page) | Staff (Reviewer desk, Dashboard detail) |
|---|---|---|
| Live stages | Yes (without repeat attempts) | Yes, all recorded stages |
| Vendor message | Yes | No (shown only on the vendor page) |
| Findings table and same/different comparison | No | Yes |
| Flagged-field marks | No | Yes |
| Vendor ID | No | Yes |
| Uploaded documents | Names only | Download |

## 8. Pages

| Page | Purpose |
|---|---|
| Onboard vendor | Form, JSON upload, or sample; live stages; the vendor's message |
| Reviewer desk | Queue, take, decide |
| Dashboard | Counts, history, filters, detail for staff, export CSV |
| Messages | Outbox: every mail and its state |
| About | Statuses, rules, limits, why these countries |
