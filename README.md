# Vendor Onboarding Checker (version 3, Flask)

```
pip install -r requirements.txt
python app.py            # http://localhost:5000
python run_tests.py      # all checks: rules, workflow, and every web route
```

Hosting: `gunicorn app:app --workers 1 --threads 4` (see `Procfile`). Keep one worker: live-run progress is held in memory.

**Countries:** India, US, Germany (other countries go to a reviewer; more are a rule-table change, see About).

**What changed from version 2 (Streamlit):** Flask + plain HTML/CSS/JS; no "waiting on" label or speed slider; history starts empty
(only the vendors already on file exist, for the duplicate check); a vendor that is already onboarded is never auto-approved when it
submits again; seven samples: one clean vendor and six edge cases, five taken from the Zamp brief (incomplete form with a wrong document, tax ID wrong for the country, name nearly matches the bank account, identity fields contradict, an existing vendor changes its bank account) plus a look-alike name (Gl0bex for Globex). Submit 01 before 06. The Messages page lists what a mail service would send to vendors (simulated).

**Files:** `checks.py` rules · `decide.py` verdict · `store.py` SQLite · `app.py` routes · `templates/` pages · `static/` CSS and live-view JS.

**Verification:** `registry.json` (simulated tax registry) and `sanctions.json` (fictional watchlist) are demo data written by `python samples.py`; set `VIES_LIVE=1` to check German VAT IDs against the real EU VIES service.

**IDs:** a submission ID is a random code per submission; a vendor ID (V + country + 6 letters/digits, e.g. VIN7A3D49) is issued to every applicant on its first submission and stays the same for all of that company's later applications.

**Mail:** messages are queued in an outbox and sent by a background worker (`mailer.py`). Sending is simulated unless `BREVO_API_KEY` and `MAIL_FROM` are set, and even then only to addresses in `MAIL_ALLOWLIST` (comma separated): a public copy of the app can never email strangers. `MAIL_WORKER=0` switches the worker off.
