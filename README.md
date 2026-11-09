# Vendor Onboarding Checker (Flask)

A working PS-02 vendor-onboarding process for the Zamp AI Solutions Analyst case study. A vendor submits a form and documents; visible, deterministic checks lead to **Approved**, **Pending: Vendor action required**, **Pending: Needs review**, or terminal **Rejected**. Every outcome has a clear owner and next action.

```text
pip install -r requirements.txt
python app.py            # http://localhost:5000
python run_tests.py      # rules, workflow, mail and web routes
```

## Happy path and exceptions

Nine stages run in order: completeness, country routing, formats, documents, identity, name match, verification, duplicates, and repeat attempts when relevant.

| Outcome | Meaning and next step |
|---|---|
| **Approved** | All applicable checks passed. An exact repeat is **Already registered** and creates nothing new. |
| **Pending: Vendor action required** | A correctable gap or one likely mistake. The same application stays open; the vendor sees a numbered list, corrects a prefilled form, and all checks rerun. |
| **Pending: Needs review** | Evidence is inconclusive or depends on an internal record or independent verification. A reviewer takes the case. |
| **Rejected** | Terminal: a hard-stop rule, two identity contradictions, or reviewer rejection. |

For bank changes and bank accounts shared across vendors, approval is blocked until the reviewer records an independent callback or bank confirmation. Reviewer notes remain internal. Vendor messages are generated from safe reason and document mappings.

Full rules: [docs/RULE_BOOK.md](docs/RULE_BOOK.md). Canonical flow: [docs/WORKFLOW.md](docs/WORKFLOW.md). Design choices: [docs/DECISIONS.md](docs/DECISIONS.md).

## Demo samples

| Sample | Expected result |
|---|---|
| 01 clean vendor | Approved. Submit it a second time: Already registered (the happy path) |
| 02 incomplete form, wrong document | Vendor action required, with a numbered list; use **Correct application** (edge case 1) |
| 03 US company with an Indian GSTIN | Vendor action required: one contradiction may be a typo (edge case 2) |
| 05 two identity contradictions | Rejected: two at once cannot be a typo (edge case 3) |
| 06 existing vendor changes its bank account | Needs review; independent verification required to approve. Submit 01 first (edge case 4, the payment-fraud case) |

The app offers only these five samples: the happy path and the edge cases the demo video talks about. The larger rule matrix lives in the tests (`samples.CASES`).

`demo_form_submission/` contains a clean form payload and four fictional PDFs.

## Scope and honest limits

The process supports India, the US and Germany. Registry and sanctions data are demo fixtures; unknown registrations are labelled **not checked**, never falsely claimed as verified. Uploaded PDF/PNG/JPG signatures are checked, but document contents and authenticity are not. Bank ownership is not checked automatically. The demo has no staff authentication or CSRF protection, uses SQLite, and holds live progress in memory. These are production-hardening items, not hidden capabilities.

Mail uses a durable outbox. It is simulated unless Brevo is configured, and real mail is restricted to `MAIL_ALLOWLIST`. German VAT can use VIES with `VIES_LIVE=1`.
