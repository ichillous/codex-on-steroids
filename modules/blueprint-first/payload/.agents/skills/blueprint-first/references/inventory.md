# Taking inventory

Do this before writing any page. The aim is a list of touchpoints that is complete because it was derived, not because someone remembered everything. Each link in the chain produces the next, and each cross-check at the end exposes pages nobody asked for but somebody will need.

Write the result into `blueprint.json` (`references/kit.md` has the format). Keep working notes wherever is convenient; the manifest and the reference pages are what lasts.

## The chain

**1. Who touches this.** List every kind of person and system, not only the customer. Look for:

- the person it is for, and anyone who acts for them (a parent, an assistant, a carer)
- people at different stages: a stranger, a first-timer, a regular, someone who left
- everyone on the providing side: staff by job, managers, the owner, finance, support
- whoever runs the whole thing (the operator's back office)
- outsiders it depends on: a payment provider, a courier, a regulator, a partner
- people who must never get in, and what they see when they try

**2. What each is trying to get done.** One line per goal, in their words: "enroll my two children", "know how many loaves to bake", "get my money back". Include the dull goals (change my address, leave) and the ones only the providing side has (approve, correct, refund, report).

**3. Where it happens.** The surfaces: a public page, a signed-in area, a staff tool, an inbox, a phone's lock screen, a printed sheet, a counter, a wall display, a phone call. A goal often crosses several, and each crossing is a place where things get dropped.

**4. The things, and the states they move through.** Name the objects the project keeps track of (an order, an application, a booking, a membership, a shipment). For each, write its states in order, who moves it from one to the next, and what each party sees and receives at each state. This table becomes a reference page and is the single best source of missing touchpoints.

**5. The rules.** Each one as a single sentence, with who decided it: price and fees, who may see or do what, limits, deadlines, what happens when time runs out. Mark each as decided by the owner, assumed by you (goes into `assumptions`), or open (goes on the pages in `[BRACKETS]`).

**6. The journeys.** For each goal, the path from the first moment to done, as a list of touchpoints. Include the steps that happen elsewhere: "an email arrives", "the school decides", "the customer walks in". Write the unhappy version of the important ones too: it is declined, it is full, the payment fails, they change their mind.

**7. The touchpoints.** Read them off the journeys. One row each: a stable file name, a title, its kind, its group, how people arrive, where they can go next, and what states it has. Group by who uses them and give each group a letter.

## Cross-checks

Run these over the inventory before building, and again during the sweep. Every "no" is a missing page, state or rule.

| Check | Question |
|---|---|
| Role by goal | Does every role have a journey for every goal it has? |
| State by audience | For every state of every thing, is there a touchpoint showing it to each party who cares? |
| State by message | For every change of state, is someone told? Is that message a page? |
| Rule by place | Is every rule visible wherever a person would run into it? |
| Arrivals | For every page, is there a real way to arrive (a link, or an entry from outside)? |
| Departures | From every page, is the next step obvious, including "undo" and "go back"? |
| Both sides | For everything a customer can send, is there the place where staff receive and answer it? |
| First and last | Is there a first-time version (nothing here yet) and an ending (cancel, leave, close, delete)? |
| Surface | Does each touchpoint exist on the surface where the person actually is at that moment? |

## Reference pages worth having

Make these `reference` pages early; they keep the screens consistent and the owner reads them first.

- **Who can do what**: actions down the side, roles across the top.
- **States**: one table per thing, as in step 4, with the exact badge wording used on screens.
- **Rules**: each rule once, and who decided it.
- **Messages we send**: every message, what triggers it, who gets it, and a link to its page.
- **Design system sheet**, once there are more than a dozen pages: every component in every state on one page, with working controls, so a pattern is fixed once and judged once.

When a screen and a reference page disagree, one of them is wrong; fix it and keep them the same.
