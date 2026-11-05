# Demo video: ready-to-speak script (about 4:20 of talking, under 5:00 with the clicks)

Read the plain text out loud. Lines in **[brackets]** are things you do on screen, not words to say.
About 570 words at a calm pace. Before recording: wake the live app, click **Reset demo data**, open the app, the GitHub workflow page and keep the About page ready (see `DEMO_SCRIPT.md`).

---

## 1. Intro (0:00 to 0:30) [app on screen]

Hi, I'm Shubham. I chose problem statement two: vendor onboarding.

Before a company can be paid, someone has to check its tax ID, its bank details and its documents. When that goes wrong, you get payment fraud or compliance trouble.

So I built a process that takes a vendor submission and gives a clear answer: approved, pending review, or rejected. It shows its reasoning, and it tells the vendor exactly what to do next.

## 2. Tech stack (0:30 to 1:00)

It's a Flask web app with a SQLite database, and a small library called rapidfuzz for comparing names. It's hosted on Render.

One deliberate choice: the decisions come from fixed rules, not from an AI, because a fraud control has to be explainable and give the same answer every time.

I used AI, Claude Code, to build it fast and to generate test cases. Over two hundred automated checks run before every release.

## 3. Workflow (1:00 to 1:35) [switch to the GitHub workflow page, scroll the first two diagrams]

Here's the workflow. Each submission runs through up to nine stages. Are the fields complete? Is the country supported? Are the IDs and bank codes valid? Are the right documents there? Do the IDs agree with each other? Does the company name match the bank account holder? Does a registry and sanctions list check out? And is this company already on file?

There are three outcomes. Approved. Pending review, when only a person can decide. Or rejected, with the exact list of what to fix.

## 4. Happy path (1:35 to 2:15) [back to the app. Sample tab, pick 01, Submit]

First, a clean vendor. **[Submit]**

You can see each stage run live on the right, and they all pass. Approved, with a plain message to the vendor.

Now the same vendor applies again, with nothing new. **[Submit 01 again]**

It says: you're already registered. Nothing is created twice, so there's no duplicate vendor to pay.

## 5. Edge case 1: an incomplete form (2:15 to 3:10) [pick 02, Submit]

Now an edge case: an incomplete form. No email, no tax ID, no bank proof, and a document in the wrong slot. **[Submit]**

It's rejected, and the message says exactly what's missing and where to upload, in plain words. **[pause so they can read it]**

Now the corrected version. **[pick 02b, Submit]** Approved.

A fix goes in as a new application and is checked from scratch. That's deliberate. A link between the old and the new application would let a fraudster keep adjusting until the rules pass.

## 6. Edge case 2: look-alike characters (3:10 to 3:40) [pick 07, Submit]

A subtler case. The account holder is Globex, but spelled with a zero instead of the letter o. **[Submit]**

Honest typos are rarely made only of look-alike swaps, so this is rejected outright. And names like 34square still pass, because I only compare names with each other.

## 7. Review case (3:40 to 4:25) [pick 08, Submit, then open Reviewer desk]

Last case. A company that's already registered applies again with the same tax ID, but a new name, bank account and phone number. That's the classic payment-fraud pattern, so a person decides. **[Submit]**

The vendor only sees: under review.

On the reviewer desk I get a note. Same company ID and email. Different name, bank account and phone. **[click Take, type a reason, click Approve]**

I take it, give my reason, and approve. The vendor is told automatically.

## 8. Dashboard and messages (4:25 to 4:45) [Dashboard, then Messages]

The dashboard shows every run with its status and reasons. Messages shows what each vendor was sent, one thread per application. The mail is simulated because the addresses are fake, but the outbox is real.

## 9. Close (4:45 to 5:00)

The limits, honestly. The registry and sanctions list are demo data, document contents aren't read, and it covers India, the US and Germany.

Next, I'd connect real registries and a bank verification service. Thanks for watching.

---

### If you run over 5:00
Drop section 6 (look-alike) first. Then shorten section 8 to one sentence.

### If the live app is slow or stuck
Run it on your laptop (`python app.py`, then `http://localhost:5000`). Everything behaves the same. Say nothing about it; just record that.
