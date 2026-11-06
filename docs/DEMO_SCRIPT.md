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
| **1:00 to 1:30 Workflow** | Tab 2: WORKFLOW.md, scroll the first two diagrams | "Every application has one clear owner. Clean evidence is approved. A correctable gap stays pending with the vendor. Uncertain or high-risk evidence stays pending with a reviewer. Only a hard stop, two contradictions, or a reviewer rejection is terminal." |
| **1:30 to 2:15 Happy path** | Tab 1. Sample tab, choose **01 clean vendor**, Submit | "First, a clean vendor. Watch the stages appear live on the right as each one runs. All pass. Approved. The vendor gets a plain message. And if the same vendor applies again with nothing new..." (submit 01 again) "...it says already registered: nothing is created twice." |
| **2:15 to 3:10 Edge case 1: incomplete form** | Choose **02 incomplete form, wrong document**, Submit; click **Correct application** | "This is not a rejection. It is pending with the vendor, with a numbered list and a prefilled correction form. Existing documents are retained, the correction becomes a new revision of the same application, and every check runs again." |
| **3:10 to 3:50 Edge case 2: look-alike** | Choose **07 look-alike characters**, Submit | "A subtler one: the bank account holder is spelled Gl0bex with a zero. It looks like Globex. A typo is rarely made only of look-alike swaps, so this is rejected outright, and the vendor is told neutrally. Names like 34square are still fine, because I only compare names with each other." |
| **3:50 to 4:30 Review case** | Choose **08 registered company, new name and details**, Submit; then open **Reviewer desk** | "Third: a company that is already onboarded applies again with the same tax ID but a new name, bank account and phone. This is the classic payment-fraud pattern, so a person decides. The vendor only sees 'under review'. On the reviewer desk I see what is the same and what differs." (point at the note) "I take it, give a reason, and approve." (click Take, type reason, Approve) |
| **4:30 to 4:50 Dashboard and messages** | **Dashboard**, then **Messages** | "The dashboard shows every run: history, status, reasons. Messages shows what the vendor was sent, one thread per application. Mail is simulated here, the fake addresses make that safe, but the outbox and sender are real." |
| **4:50 to 5:00 Close** | Dashboard or About page | "Limits, stated openly: the registry and sanctions list are demo data, document contents are not read, and this demo has no staff authentication. Next I would plug in real registries, bank ownership verification and production access controls." |

## Edge cases available (pick up to three; the video needs at least one)
| Sample | Result | Why it matters |
|---|---|---|
| 02, then 02b | Vendor action required; corrected is Approved | Incomplete forms and wrong documents, and that the correction loop works |
| 03, then 03b | Vendor action required; corrected is Approved | Tax ID wrong for the stated country |
| 04, then 04b | Vendor action required; corrected is Approved | Bank holder name nearly matches the company |
| 05, then 05b | Rejected (contradictions); corrected is Approved | Cross-checking fields |
| 06 | Needs review | Existing vendor changes its bank account |
| 07 | Rejected outright | Look-alike characters |
| 08 | Needs review | Registered ID, new name and details |
| 09 | Needs review | Same name and address, different company ID |

Order matters: **submit 01 first** (06, 08 and 09 compare against Apex Global once it is approved).

## Recording tips
- Use any screen recorder; no editing needed. Windows: **Xbox Game Bar** (Win+G) or **OBS Studio** (free) or **Loom**. Record the browser window and your mic.
- Talk over the screen at a calm pace; pause while the stages run so the viewer sees them.
- If you run over, drop the look-alike case first, then the dashboard detail.
- Check the final length is **under 5:00** before submitting.
- Send the coordinator two links: the live process and the video.
