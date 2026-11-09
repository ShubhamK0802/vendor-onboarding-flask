# 5-minute demo video: script, shot list and checklist

**What Zamp asks for:** a 5-minute (maximum) screen recording. "Show the happy path running live, then run at least one edge case. Narrate what's happening and why." They also say: no editing needed, **no slides**, "just you, your screen, and your process running."

So the intro, tech stack and workflow are **spoken while the real pages are on screen** (the GitHub docs page and the app's About page), not shown as slides.

Live app: https://vendor-onboarding-checker.onrender.com  ·  Code and docs: https://github.com/ShubhamK0802/vendor-onboarding-flask

## Before you press record (10 minutes)
1. **Wake the app** a minute early: open the live link and wait for the page. The free host sleeps and the first visit can take about a minute.
2. Click **Demo tools → Reset demo data** (bottom of any page) so History starts empty.
3. Open three browser tabs, in this order:
   1. the **Onboard vendor** page (the app),
   2. the **workflow** page: https://github.com/ShubhamK0802/vendor-onboarding-flask/blob/main/docs/WORKFLOW.md (the diagrams render there),
   3. the app's **About** page.
4. Browser zoom 110 to 125 percent, 1080p screen, close notifications, mic test. Enter your own name for the Reviewer desk in advance (it remembers it).
5. Rehearse once with the stopwatch. If the live app hangs, run it on your laptop instead (`python app.py`, then `http://localhost:5000`); everything works the same.
6. **Do not show** keys, emails of real people, or your reviewer name field with anything private.

## Timeline (5:00 total)

| Time | On screen | What you say |
|---|---|---|
| **0:00 to 0:30 Intro** | Onboard vendor page | "Hi, I'm Shubham. I picked problem statement 2, vendor onboarding. When a company wants to be paid, someone has to check its tax ID, bank details and documents. Mistakes cause payment fraud or compliance problems. I built a process that takes a vendor submission and gives a clear status: approved, pending, or rejected, with the reasoning visible, and it tells the vendor what is needed." |
| **0:30 to 1:00 Tech stack** | Stay on the app, or GitHub repo page | "It is a Flask app with SQLite and a few Python libraries: rapidfuzz for name matching. It runs on Render. The decisions are made by fixed rules, not by an AI, because a fraud control must be explainable and repeatable. I used AI, Claude Code, to build it fast and to generate the test cases. over 200 automated checks run locally before every deploy." |
| **1:00 to 1:30 Workflow** | Tab 2: WORKFLOW.md, scroll the first two diagrams | "Every application has one clear owner. Clean evidence is approved. Wrong or missing input is rejected, and the vendor applies again. Uncertain or high-risk evidence is pending with a reviewer, and that is the only pending status." |
| **1:30 to 2:15 Happy path** | Tab 1. JSON file tab, choose **01 clean vendor**, Submit | "First, a clean vendor. Watch the stages appear live on the right as each one runs. All pass. Approved. The vendor gets a plain message. And if the same vendor applies again with nothing new..." (submit 01 again) "...it says already registered: nothing is created twice." |
| **2:15 to 3:10 Edge case 1: incomplete form** | Choose **02 incomplete form, wrong document**, Submit | "Wrong input is rejected, not parked. The vendor gets a numbered list in plain words and is told to submit a new application. The new one is checked from scratch and nothing is inherited." |
| **3:10 to 3:50 Edge cases 2 and 3: identity contradictions** | Choose **03 tax ID belongs to another country**, Submit; then **05 two identity contradictions**, Submit | "A US company with an Indian GSTIN. The message says the tax ID does not fit the country and invites a new application. Sample 05 has two identity contradictions, and the message names both." |
| **3:50 to 4:30 Edge case 4: bank-account change** | Submit **01** first, then choose **06 existing vendor changes bank account**, Submit; open **Reviewer desk** | "The most important payment-fraud case. An onboarded vendor suddenly changes its bank account. It cannot be auto-approved. A reviewer takes the case, sees what is the same and what differs, and the server blocks approval until the reviewer records a trusted-contact callback or independent bank confirmation." |
| **4:30 to 4:50 Dashboard and messages** | **Dashboard**, then **Messages** | "The dashboard shows every run: history, status, reasons. Messages shows what the vendor was sent, one thread per application. Mail is simulated here, the fake addresses make that safe, but the outbox and sender are real." |
| **4:50 to 5:00 Close** | Dashboard or About page | "Limits, stated openly: the registry and sanctions list are demo data, document contents are not read, and this demo has no staff authentication. Next I would plug in real registries, bank ownership verification and production access controls." |

## Samples in the app (01 plus the edge cases the video talks about)
| Sample | Result | Why it matters |
|---|---|---|
| 01, submitted twice | Approved, then Already registered | The happy path, plus the exact-repeat case |
| 02 (edge case 1) | Rejected, with a list of what to fix | Incomplete forms and wrong documents; the vendor applies again |
| 02b, 03b, 05b | Approved, each after its rejected sample | A rejected vendor applies again with the right data: a new application, a new row on the dashboard, the old rejection stays |
| 03 (edge case 2) | Rejected | Tax ID wrong for the stated country (one contradiction) |
| 05 (edge case 3) | Rejected | Two identity contradictions at once |
| 06 (edge case 4) | Needs review | An existing vendor changes its bank account |

Order matters: **submit 01 first** (06 compares against Apex Global once it is approved).

## Recording tips
- Use any screen recorder; no editing needed. Windows: **Xbox Game Bar** (Win+G) or **OBS Studio** (free) or **Loom**. Record the browser window and your mic.
- Talk over the screen at a calm pace; pause while the stages run so the viewer sees them.
- If you run over, drop the look-alike case first, then the dashboard detail.
- Check the final length is **under 5:00** before submitting.
- Send the coordinator two links: the live process and the video.
