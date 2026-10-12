# Adapting the blueprint to the project

The method is the same everywhere: find every moment where a person meets the thing, write that moment down exactly, link the moments in the order people live them, and check that nothing is missing. What changes from project to project is which kinds of touchpoint carry the weight.

## Where the touchpoints are

| Project | Mostly made of | Easy to forget |
|---|---|---|
| App or website | `screen` pages, with `message` pages for everything sent | The staff and operator side; the emails; the phone width |
| Service business (clinic, salon, repair shop, restaurant) | `spoken` scripts, `document` pages (forms, signs, receipts), a few `screen` pages for booking | What staff say when it goes wrong; the sign on the door; the reminder text |
| Physical product | `document` pages (the box, the quick-start card, the label), `screen` pages for setup, `message` pages for order and delivery | The return; the warranty claim; the first minute out of the box |
| Event or campaign | `message` pages in sequence, a registration `screen`, `document` pages (ticket, badge, signage, run sheet), `spoken` for the door and the stage | The day-after message; the waitlist; the "it is cancelled" plan |
| Internal process or operations | `document` pages (the form, the checklist, the report), `screen` pages for the tool, `spoken` for the hand-over | Who approves; what happens when the approver is away; the audit trail |
| API, command-line tool, data pipeline | `screen` pages showing the exact terminal transcript or request and response for each call, `document` pages for the docs, `message` pages for alerts | Every error message; the first-run experience; the alert at 3 AM and what it tells the person to do |
| Content (course, publication, documentation site) | `screen` pages for each template with real content, `message` pages for the sequence sent around it | The empty search; the paywall; the unsubscribe |
| Hardware or a space (kiosk, shop fit-out, exhibit) | `document` pages for signs and labels, `screen` pages for any display, `spoken` for staff | What a display shows when it is offline; the sign for "out of order" |

For a terminal or API touchpoint, make the page a `screen` whose content is the exact output in a `<pre>` block, with links for "what the person does next" (the next command, the error case, the docs page). The words a tool prints are copy and deserve the same care as a button label.

For a `spoken` page, write both sides of the exchange and the branches: what the person might say, and what is said back in each case.

For anything this project does not control, write an `offstage` page that says what happens there, who owns it, and how the person comes back. It keeps the journey honest about the parts nobody on this project can design.

## How much blueprint

| The idea | A reasonable blueprint |
|---|---|
| Change the wording of one message | That message page and any page quoting it; the retired wording added to the manifest. Minutes. |
| Add one feature to an existing product | The feature's own pages, the pages that set it up, and an edit to each existing page the ripple list reaches. Often 5 to 20 pages touched. |
| A new product with two or three roles | Commonly 40 to 150 pages once messages, states, the back office and reference pages are counted. The first pass finds perhaps two thirds; the sweep finds the rest. |
| A service or event with no software | Commonly 15 to 50 pages: mostly documents, messages and spoken scripts. |

When blueprinting a change to something that exists and has no blueprint yet, do not blueprint the whole existing product first. Make pages for what the change touches, mark pages that stand in for existing screens as such in their title, and let the blueprint grow with each later change.

## When the owner already has a prototype or a design

Treat it as the first group, not as a reference to imitate from scratch. Bring its pages into the folder in their existing look, set the stylesheet's tokens to match, then do the inventory and build what is missing around it. Say in the hand-over what you kept and what you changed.
