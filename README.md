# Vendor Onboarding Checker (Flask)

A vendor submits their details and documents; fixed rules decide **Approved**, **Pending: Needs review** or **Rejected**, and the vendor is told what is needed. Built for the Zamp "AI Solutions Analyst" case study (PS-02). No AI makes the decision: every outcome can be explained line by line and repeated exactly.

```
pip install -r requirements.txt
python app.py            # http://localhost:5000
python run_tests.py      # every rule, the workflow and every web route
```

## How it decides
Nine stages run in order (the live run view shows each as it happens): completeness, country routing, format checks, documents, identity checks, name match, verification, duplicate check, and repeat attempts (internal, shown to staff only).

| Outcome | Meaning |
|---|---|
| **Approved** | Nothing wrong. A vendor ID is issued (internal: the vendor never sees it). |
| **Approved: Already registered** | An exact repeat of an onboarded vendor. Nothing new is created. |
| **Pending: Needs review** | Only a person can decide (changed details, same name with a different company ID, shared bank account or contact, 4th attempt...). |
| **Rejected** | A rule rejects it, or it only has mistakes or gaps. The vendor gets the exact list of what to correct and files a **new application**. |

There is no waiting state, timer or reminder mail. Full rules: [docs/RULE_BOOK.md](docs/RULE_BOOK.md). Diagrams: [docs/WORKFLOW.md](docs/WORKFLOW.md). Features: [docs/FEATURES.md](docs/FEATURES.md). Why the key choices were made: [docs/DECISIONS.md](docs/DECISIONS.md).

**Countries:** India, US, Germany (other countries go to a reviewer; more are a rule-table change, see About).

## Samples (Onboard vendor page)
Submit the edge case, then its corrected version. Submit **01** first for 06, 08 and 09 (they compare against Apex Global, which is on file once 01 is approved).

| Sample | Result |
|---|---|
| 01 clean vendor | Approved (submit it twice: Approved, already registered) |
| 02 incomplete form, wrong document | Rejected, with what to correct. **02b** corrected: Approved |
| 03 tax ID wrong for the country | Rejected. **03b**: Approved |
| 04 bank holder name nearly matches | Rejected. **04b**: Approved |
| 05 identity fields contradict | Rejected. **05b**: Approved |
| 06 existing vendor changes its bank account | Needs review |
| 07 look-alike characters in a name (Gl0bex) | Rejected outright. **07b**: Approved alone, Needs review if 07 came first |
| 08 registered company ID, new name and details | Needs review, with a same/different comparison |
| 09 same name and address, different company ID | Needs review, with a same/different comparison |

`demo_form_submission/` has a clean vendor as JSON plus four sample PDFs to upload through the form.

## Files
`checks.py` rules · `decide.py` verdict · `config.py` rule tables and wording · `store.py` SQLite · `mailer.py` outbox and sender · `app.py` routes · `templates/` pages · `static/` CSS and live-view JS · `samples.py` demo data and test cases · `run_tests.py` all checks.

## Hosting
`gunicorn app:app --workers 1 --threads 4` (see `render.yaml`). Keep one worker: live-run progress is held in memory. Set `DB_PATH` to choose the database file (`render.yaml` uses `:memory:` on the free host, so data resets on restart). Always run `python run_tests.py` locally before pushing.

**Verification data:** `registry.json` (simulated tax registry) and `sanctions.json` (fictional watchlist) are demo data written by `python samples.py`; set `VIES_LIVE=1` to check German VAT IDs against the real EU VIES service.

**Mail:** messages are queued in an outbox and sent by a background worker (`mailer.py`). Sending is simulated unless `BREVO_API_KEY` and `MAIL_FROM` are set, and even then only to addresses in `MAIL_ALLOWLIST` (comma separated): a public copy of the app can never email strangers. `MAIL_WORKER=0` switches the worker off.

## Known limits
Registry and sanctions are demo data; bank-account ownership is not verified; document contents are not read; India, US and Germany only; no document expiry tracking; mail is simulated unless Brevo is configured; the free host resets data when it restarts. The About page lists each with its upgrade path.
