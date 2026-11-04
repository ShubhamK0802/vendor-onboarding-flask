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
submits again; samples no longer collide with each other (only 10 and 13 reuse Apex on purpose, so run 01 first).

**Files:** `checks.py` rules · `decide.py` verdict · `store.py` SQLite · `app.py` routes · `templates/` pages · `static/` CSS and live-view JS.

**Verification:** `registry.json` (simulated tax registry) and `sanctions.json` (fictional watchlist) are demo data written by `python samples.py`; set `VIES_LIVE=1` to check German VAT IDs against the real EU VIES service.

**IDs:** a submission ID is a random code per submission; a vendor ID (V + country + 6 letters/digits, e.g. VIN7A3D49) is issued to every applicant on its first submission and stays the same for all of that company's later submissions and corrected resubmissions.
