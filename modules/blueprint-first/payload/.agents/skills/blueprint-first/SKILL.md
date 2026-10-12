---
name: blueprint-first
description: Use BEFORE implementing any idea in any industry, whether a new product, feature, redesign, service, campaign, event or process. Turns the idea into a complete, walkable blueprint first (every role, every screen or other touchpoint, every button and where it leads, every word, every state), checks it mechanically for dead ends, sweeps it for what is missing, builds a map of the whole thing, and hands over the decisions to confirm before any real work starts. Trigger on "build", "add", "redesign", "I have an idea", "let us make", "plan this out", "every button, every click", or any request to start implementing something that has no approved blueprint yet. Skip only for fixes, typos and refactors that change nothing a person sees or does.
---

# Blueprint first

Before anything is implemented, turn the idea into a blueprint: a folder of plain linked pages, one for every thing a person will see, read, press, receive or be told, with the real words on it. Check it mechanically, sweep it for gaps, and hand it to the owner with the decisions only they can make. Implementation starts when they say go.

The reason is cost. An idea arrives as its happy path, and most of the work hides around it: the second role, the empty list, the email, the refund, the day the clocks change. A gap found on a page costs a minute. The same gap found in a build costs a rewrite, and one found by a customer costs trust. A blueprint puts everything in view at once, so it can be judged while changing it is still free.

Paths in this file are relative to this skill's folder; run the scripts by their full path from wherever the project is. The owner is whoever asked for the work.

## Size it first

| The idea is | Do |
|---|---|
| A fix, typo or refactor that changes nothing a person sees or does | No blueprint. Say so in one line and carry on. |
| A change or addition to something that exists | Blueprint the new touchpoints and every existing one the change ripples into (step 6). Read what exists first. If the project already has a blueprint folder, extend it. |
| Something new | The full blueprint. |

Depth scales with the idea. The passes below do not get skipped; on a small change each one is simply short.

## What a blueprint is

A folder, `blueprint/` in the project unless the owner names another place, kept apart from production code. It changes nothing real.

```
blueprint/
  blueprint.json   the manifest: groups, pages, journeys, decisions made, retired wording
  blueprint.css    the one design system every page uses
  blueprint.js     a small runtime that makes plain pages respond to presses
  *.html           one page per touchpoint
  map.html         generated: the whole blueprint on one page
  _check/          generated: check results and screenshots
```

A page is a touchpoint, and a touchpoint is not only a screen:

| Kind | What it is |
|---|---|
| `screen` | Something on a device that a person looks at and presses |
| `message` | An email, text, notification or letter, shown as the recipient sees it |
| `document` | Anything printed, downloaded, signed, posted on a wall or stuck on a box |
| `spoken` | The words someone says: a call script, a counter exchange, a door greeting |
| `offstage` | A step in a system or with a person this project does not control |
| `reference` | What no single page can hold: roles, states, rules, the catalog of messages |

This is what makes the method work for a clinic, a bakery, an API or a conference as well as for an app. `references/adapting.md` shows how touchpoints map when the project has few or no screens.

## The work

Seven steps. If your environment has a task list or plan tool, put them on it, so the owner can see where things stand.

### 1. Read what exists

Read everything the owner gave you and everything already there: an earlier prototype, the current product, notes, rules already decided. Keep what they made and improve it; do not restart their work in your own taste. If they pointed at an example to follow, read it and list what it does: the blueprint should cover that ground, and the hand-over should say where it goes further or differs. If the blueprint folder already holds pages or generator scripts from an earlier session, continue from them.

Ask a question only when a wrong guess would waste the whole blueprint (who the roles are, what is in scope). Everything else, decide, record as a decision made (step 7), and keep moving. The owner would rather correct a finished page than answer twenty questions about an empty one.

### 2. Take inventory before drawing anything

Work down this chain and write the result into `blueprint.json`: who touches this → what each of them is trying to get done → where it happens → what things exist and what states they move through → what rules apply → the journeys from start to done → the list of touchpoints those journeys need. `references/inventory.md` has the method and the cross-checks that expose missing pages.

Group the touchpoints by who uses them, give each group a letter, and write at least one journey per role. Pages get codes from their group and order (A1, A2, B1). File names are plain stable words (`order-status.html`); the code lives only in the manifest, so adding a page never breaks a link.

### 3. Start the folder

```
python3 scripts/init_blueprint.py <project>/blueprint --name "Name" --summary "One sentence"
```

This copies the kit and four small example pages; the check fails until each example is replaced or removed, so none can be left in by accident. `references/kit.md` documents the manifest, the page skeleton, the runtime attributes and the stylesheet's vocabulary; read it before writing the first page. If the product already has a look, set the stylesheet's tokens to match it. Patterns go into `blueprint.css` once and are used everywhere, because one stylesheet is what keeps a hundred pages reading as one product. This skill governs completeness; for visual craft, use the project's design system or a design skill alongside it.

### 4. Build group by group

Write each page as it would really appear, then wire everything on it:

- **Real words.** Every heading, label, hint, error, button and message is final-quality copy the owner could approve as it stands. Filler text hides exactly the decisions a blueprint exists to surface.
- **Every control does its thing.** A link goes to a real page. A button changes the page in front of the person: the form becomes its confirmation, the confirm prompt appears, the status flips. Show the outcome; never describe it ("this would open a dialog").
- **Every state is reachable.** If a page looks different by role, status or time, declare the variants on the page so each one can be opened, checked and screenshotted.
- **Offstage steps are still touchpoints.** If the flow passes through an email, a payment provider, a person's decision or a walk to the counter, give it a page: the email as received, the hand-off as a labelled `offstage` board.
- **One world of sample data.** One cast of invented people and organizations, one "today" (set it in the manifest), and numbers that agree with each other on every page. Work figures out rather than guessing them: totals, dates, weekdays, schedules, anything with a formula. Check that the domain logic holds, since plausible-looking samples can be impossible (a pickup slot outside opening hours, a delivery promised on a public holiday, a discount larger than the price).

After the first group, run step 5 and tell the owner where `map.html` is. Showing work early lets them redirect before the other groups are built on a wrong assumption.

### 5. Check, look, fix

```
python3 scripts/check_blueprint.py <blueprint>     # structure, links, dead buttons, dead ends, journeys, wording
node    scripts/browser_audit.cjs  <blueprint>     # opens every page, presses every button, screenshots
python3 scripts/build_map.py       <blueprint>     # rebuilds map.html from the pages and the results
```

Run all three after every batch of pages and again at the end. Fix every `FAIL`; read every `WARN`. Then open the screenshots in `_check/shots/` and look at them, the phone-width ones included. The scripts prove that nothing is broken, which is different from proving that it looks right or reads well, and only looking does that.

If no browser is available, the audit exits with `NO BROWSER` and says how to get one. Carry on with the static check, and say plainly in the hand-over that pages were not opened or pressed. Never report a check you did not run.

### 6. Sweep for what is missing, and ripple every change

A first pass covers what the idea mentioned. Go through `references/sweep.md` against every group and add what is missing: the states, the failures, the messages, the back office, the documents, the small screen. Expect the blueprint to grow by a third or more; that growth is the point of the pass. Then run step 5 again.

When a rule or a fact changes (a price, a time, a name, what is free), every page that states it must change. Add the old wording to `retired` in the manifest and the check will list every page still carrying it. When a feature is added, design both sides of it (the thing itself and whatever sets it up or controls it), then visit every existing place that should now mention it: navigation, setup, pricing, help, permissions, settings, messages, empty states, the reference pages.

### 7. Hand over, and wait

Rebuild the map, then report in this shape:

```
<One line: what the blueprint covers, how many pages, and where to start (map.html).>

| Group | What it covers | Pages |

What I checked: <which scripts ran and their results; what you looked at by eye>
What I did not check: <anything skipped or unavailable, plainly>

Decisions I made that you should confirm
- <decision>: <why>            (the same list as "assumptions" in blueprint.json)

Left open for you, shown in [BRACKETS] on the pages
- <what>, <which pages>

Sample values to verify before real use: <computed or invented figures>
```

Then stop. Do not start implementing until the owner approves the blueprint or tells you to go ahead. If they ask for changes or leave notes on pages, answer each one specifically, make the changes in the blueprint, run step 5, and report what changed. If nobody is there to answer, finish the blueprint, leave the report, and stop at the gate.

## Two habits that keep a blueprint honest

**Write open decisions in brackets; do not invent them.** Some things only the owner can settle: a price, a fee, legal wording, a response time, a contact address, a launch date. Write these on the page as `[CAPITALS IN BRACKETS]`, for example `[PLATFORM FEE %]`. The runtime highlights them and the check and the map collect them. An invented value reads as decided and gets built. Where an open decision gates behavior, also design what happens until it is settled; usually the dependent action is unavailable and says why.

**Record what you decided on the owner's behalf.** Anything you chose that they might have chosen differently (who can see what, when money moves, what a role may do, a default) goes into `assumptions` in the manifest as a decision and its reason. The map shows the list and the hand-over repeats it. Decisions buried in pages are found late; decisions on a list get confirmed in one read.

## After the go

The blueprint is now the specification. Build in the order of the journeys, so that something works end to end early. Each page is the acceptance test for its touchpoint: same words, same states, same destinations. Each journey is an end-to-end test. Anything still in brackets gets settled first, or is built so that whatever depends on it stays unavailable and says why. When the build has to differ from the blueprint, change the blueprint too, so it stays the one place that shows the whole thing.

## Files in this skill

- `references/inventory.md` — step 2 in detail: the chain from roles to touchpoints, and the cross-checks.
- `references/kit.md` — the manifest, page skeleton, runtime attributes, stylesheet vocabulary and scripts. Read before writing pages.
- `references/sweep.md` — the gap checklist for step 6, and the ripple list for changes.
- `references/adapting.md` — projects with few or no screens, and how much blueprint each size of idea deserves.
- `scripts/` — `init_blueprint.py`, `check_blueprint.py`, `build_map.py` (Python 3, no packages) and `browser_audit.cjs` (Node with Playwright; uses an installed Chrome or Edge if Playwright has no browser of its own).
- `assets/starter/` — what `init_blueprint.py` copies.
