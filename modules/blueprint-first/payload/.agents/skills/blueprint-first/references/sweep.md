# The sweep

Run this after the first complete pass, and again after any large addition. Take one section at a time and walk every group against it. Add what is missing, wire it into the pages that lead to it, then run the checks again.

Not every line applies to every project. For each line, either the blueprint has it, or you can say in a sentence why this project does not need it.

## Flows

- Every multi-step flow shows each step, its success, and its failure.
- The person can go back, cancel, and leave partway. If leaving loses work, they are warned in designed words.
- A flow that can be resumed later shows what "later" looks like.
- Anything that waits on someone else has a waiting state, and says what is happening and how long it usually takes.
- Anything that can expire (a link, a code, an offer, a held place) shows the expired version.
- No button describes an outcome instead of showing it.

## Lists and collections

- Empty (nothing yet, with the first action), one item, many, and filtered down to nothing (with a way to clear the filter).
- What happens when there are too many: paging, search, or grouping.
- Each row leads somewhere, or says why it does not.

## Forms

- Every field has a label, and a hint where the answer is not obvious. Required and optional are marked one way throughout.
- The exact words of each validation message.
- What the person sees after sending, and whether they can edit afterwards.
- Unsaved changes: how they know, and what happens if they leave.

## Actions that cannot be taken back

- A confirmation in plain words that names the thing and the consequence.
- An undo or a recovery window where one is possible, and the wording when it is not.

## States and lifecycles

- A table for each thing that has a lifecycle: states, who moves them, what each party sees and receives.
- The same state uses the same word and the same badge everywhere it appears.
- The awkward states exist: declined, waitlisted, on hold, suspended, overdue, partially done.

## Roles and access

- A who-can-do-what table, and a page per role that differs meaningfully from the others.
- Joining: invitation, acceptance, first sign-in. Leaving: removal, handing over ownership.
- What someone sees when they reach a page they are not allowed to see.
- Limits on what the operator's own staff can see of customers' private records, and how that access is recorded.

## Accounts, if there are any

- Create, confirm, sign in, sign out, forgot, change email and password, a second step if the stakes need one, delete.
- Signed-out and signed-in versions of shared pages.
- What a new account looks like before it has anything in it.

## Messages

- Every email, text, notification and letter has a page showing sender, subject, exact words, and where its button lands.
- A catalog page lists them all with their triggers.
- Every change of state that matters to someone sends them something.
- Marketing-type messages have a working way to stop them, and the page that confirms it.

## Money, if any changes hands

- What is free and what is charged, stated once and identically everywhere.
- Price, fees and taxes shown before commitment; the receipt after.
- A failed payment, a refund, a partial refund, a dispute.
- When the money is actually taken, and when the provider is paid.
- Statements and records for both sides.
- The hand-off to the payment provider as an `offstage` page.

## Documents

- Anything printed, downloaded, exported or signed: receipts, statements, tickets, labels, sign-in sheets, certificates, contracts.

## Trust and law

- Terms, privacy, and any consent wording, as pages with their structure and section headings. The legal text itself stays in `[BRACKETS]` for whoever is qualified to write it.
- A plain-language statement of who can see what, wherever people enter sensitive information.
- Age limits, and how the product treats people it must not have as account holders.

## Help and the other side of the counter

- Help, contact, report a problem.
- Where each of those lands for staff, and how they answer.
- The operator's back office: approvals, moderation, corrections, settings, a record of who did what.
- A view of whether the system itself is working.

## Other surfaces and conditions

- Phone width for every screen someone might open on a phone, including its menu.
- Print, where people will print.
- Displays nobody can touch (a wall screen, a kiosk in attract mode).
- No connection, an error, not found, closed for maintenance.

## Time

- What changes at deadlines, renewals, term or season boundaries.
- Time zones and clock changes.
- What yesterday's and next month's version of a dated page looks like.

## Words and sample data

- One name per thing, used everywhere. A button says what will happen.
- Dates, times, money and counts written one way.
- One cast, one "today", and numbers that add up. Recompute any total you changed.
- Nothing invented that only the owner can decide.

## The map and the references

- `map.html` rebuilt and read through once from the top.
- Every journey still links end to end.
- Reference pages still agree with the screens.

---

# The ripple list

Use this when something changes after pages exist.

**A rule or fact changed** (a price, a time, a name, a limit, what is free):

1. Put the old wording in `retired` in `blueprint.json`, with the reason.
2. Run the check. It lists every page still carrying the old wording.
3. Fix each one. Look also for the same fact said in different words, which no check can find: search the folder for the nearby nouns.
4. Update the rules reference page and any message that quotes the fact.
5. If the change removes a reason for a page to exist, remove the page and its links too.

**A feature was added:**

1. Design both sides: the thing people use, and whatever sets it up, switches it on, or controls it.
2. Then visit each of these and add the feature where it belongs: navigation and menus; setup or onboarding; the page that explains the product; pricing; help; the who-can-do-what table; settings and notifications; the message catalog; empty states; the back office; the reference pages; the journeys in the manifest.
3. Run the checks and rebuild the map.

**A page was removed or renamed:** the check reports every link that now goes nowhere. Fix those, then the journeys.
