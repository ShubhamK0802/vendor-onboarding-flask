# Why the key choices were made

| Choice | Why |
|---|---|
| **Fixed rules, no AI deciding** | Every outcome can be explained and repeated exactly; a payment-fraud control must be auditable. |
| **Companies only** | A sole proprietor often banks in their own name, and partnerships and trusts have their own rules. Supporting one type well beats supporting five loosely; the PAN of a company always has C as its 4th letter. |
| **India, US, Germany** | India is the home market, the US the largest foreign one, and Germany brings EU rules (IBAN, VAT) that differ from both. Other countries go to a reviewer. |
| **Three outcomes: Approved, Pending (review), Rejected** | Zamp asks for approved, pending or rejected. Pending means only a person can decide. Nothing is pending on the vendor, so there is no waiting state. |
| **Mistakes and gaps are Rejected, with a list of what to correct** | The vendor can do nothing to an existing application, so "pending" would be untrue. They file a new one. |
| **No resubmission link or pre-fill** | A link between applications is a loophole: it lets a fraudster probe the rules and inherit trust. Each application is checked from scratch. |
| **Attempts are counted anyway** | A fraudster can still file new applications. Counting rejected attempts (the 4th goes to a reviewer, or when identity changes unasked) closes the loop without a link. Applications under review are not attempts: the vendor learned nothing from them. |
| **Look-alike characters are rejected, not sent back** | Honest typos are rarely made only of O-for-0 swaps. Names like 34square or add360 are fine: names are only compared with each other. |
| **Exact repeat of an onboarded vendor is "already registered"** | The vendor did nothing wrong. Nothing is created, so it cannot duplicate payments. |
| **Same name alone is not a flag** | Many unrelated companies share a name. With something else in common and a different company ID, a person decides. |
| **Vendor ID hidden from vendors** | It is the system's own key; showing it helps nobody and could leak. |
| **Internal findings hidden on the vendor's page** | A vendor who sees which fraud check tripped can learn to avoid it. Staff see everything. |
| **Review notes say what is the same and what differs** | It makes a review a one-minute job instead of an investigation. |
| **Simulated mail, outbox and background sender** | The demo vendors' addresses are fake. The outbox shows exactly what a real service would send, and real sending is limited to an allow-list. |
| **Registry and sanctions are demo data** | Real services plug in at the same place (tax authorities, OFAC/EU/UN lists). Stated openly as a limit. |
| **Test locally, then push, then deploy** | Hosting problems (an overlapping deploy, a locked database) cost far more time than any code change. |
