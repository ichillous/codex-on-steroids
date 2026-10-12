# The kit

Everything a blueprint page is made of, and what the scripts expect. Pages are plain HTML files that open straight from disk: no build step, no framework, no network.

## Contents

1. The manifest, `blueprint.json`
2. The page skeleton
3. Making pages respond: the runtime attributes
4. The stylesheet's vocabulary
5. The scripts and what they write
6. Conventions that prevent rework

## 1. The manifest

```json
{
  "name": "Corner Bakery Pre-orders",
  "summary": "Customers order bread for pickup tomorrow; the counter bakes to the list.",
  "today": "Thursday, October 8, 2026",
  "start": "menu.html",
  "widths": [1440, 390],
  "groups": [
    { "key": "A", "title": "Customer, on a phone", "who": "Customer" },
    { "key": "M", "title": "Text messages we send", "who": "Customer" },
    { "key": "P", "title": "Paper and spoken words", "who": "Counter staff" }
  ],
  "screens": [
    { "file": "menu.html", "group": "A", "title": "Tomorrow's bake", "kind": "screen" },
    { "file": "sms-ready.html", "group": "M", "title": "Text: order ready", "kind": "message",
      "entry": "Sent when the counter marks the order ready" },
    { "file": "slip.html", "group": "P", "title": "Printed order slip", "kind": "document", "widths": [816] }
  ],
  "journeys": [
    { "title": "A customer orders a loaf and collects it", "who": "Customer",
      "steps": ["menu", "order", { "offstage": "A text arrives" }, "sms-placed", "order-status"] }
  ],
  "assumptions": [
    { "decision": "No customer accounts: an order is found by the link in its text.",
      "because": "A password would cost more orders than it protects." }
  ],
  "retired": [
    { "text": "5:00 PM", "why": "order cut-off moved to 6:00 PM", "except": ["history.html"] }
  ]
}
```

| Field | Meaning |
|---|---|
| `today` | The one date all sample data is set on. Pages that show a later moment say so in their title. |
| `start` | Where a first-time person begins. Reachability is measured from here. |
| `widths` | Widths to render at. The first is the main one; buttons are pressed at that width. |
| `groups` | Lettered groups, usually one per role or surface. Order here is order on the map. |
| `screens[].kind` | `screen`, `message`, `document`, `spoken`, `offstage` or `reference`. Only a `screen` must have a way out and working buttons. |
| `screens[].entry` | How people arrive when no page links here: "Sent the moment an order is placed", "The staff tablet opens on this page". Without it, an unlinked page fails the check. |
| `screens[].terminal` | Why a screen has no way out, when that is truly intended. |
| `screens[].widths` | Overrides the default for this page, e.g. a printed page or a wall display at one fixed size. |
| `journeys[].steps` | File names without `.html`, in order. `{ "offstage": "…" }` is a step that happens elsewhere. Two neighbouring page steps must really be linked, or the check fails. |
| `assumptions` | Decisions made on the owner's behalf, each with its reason. |
| `retired` | Wording that must no longer appear anywhere. Plain text, or `re:` followed by a regular expression. `except` lists pages allowed to keep it. |

Page codes (A1, A2, B1) are worked out from group and order. Do not write them into file names or links.

## 2. The page skeleton

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your order</title>
<link rel="stylesheet" href="blueprint.css">
</head>
<body data-state="step=form" data-variants="step=form|placed; stock=in|soldout">
  …the page…
<script src="blueprint.js"></script>
</body>
</html>
```

Every page has a `<title>`, links `blueprint.css`, and loads `blueprint.js` last. Links between pages are ordinary relative links: `<a href="order.html">`. A link may carry state to the page it opens: `<a href="order-status.html?status=ready">`.

## 3. Making pages respond

State is a small set of named values, such as `step=form` or `status=ready`. It starts from `data-state` on `<body>`, is overridden by the page address (`?status=ready`), and changes when a control is pressed. Elements show or hide according to it.

| Attribute | On | Effect |
|---|---|---|
| `data-state="step=form; viewer=visitor"` | `<body>` | Starting state. |
| `data-variants="status=placed\|ready\|cancelled"` | `<body>` | The states worth reviewing. The first option is the default. Each one gets rendered, screenshotted and offered in the review bar. Separate several keys with `;`. |
| `data-keep="viewer"` | `<body>` | Carry these keys along when a link is followed, so "signed in" stays signed in across pages. |
| `data-when="step=form"` | any element | Shown only while the condition holds. |
| `data-set="step=sent"` | a button, link without `href`, or `<form>` | Pressing it (or submitting the form) sets state. Several: `"step=sent; saved=on"`. Clear a key with `"asking="`. |
| `data-toggle="saved"` | a button | Switches a key on and off, and keeps `aria-pressed` right. |
| `data-flash="Link copied."` | a button or `<form>` | Shows a short status message. |
| `data-off-when="!email"` | a button | Unavailable while the condition holds. |
| `data-bind="email"` | a field | The field's value is kept in state, so other elements can react to it. |
| `data-text="email"` | any element | Its text follows a state value; write a sensible fallback inside it. |
| `aria-pressed="false"` | a `data-set` button | Declares a choice (a tab, a filter chip). The runtime marks the current one. |

Conditions: `key` (has a value), `!key`, `key=a`, `key!=a`, `key=a|b`, and several joined with ` & `.

A form and its result on one page:

```html
<form class="stack" data-when="step=form" data-set="step=sent">
  <div class="field">
    <label class="label" for="q-email">Email address</label>
    <input class="input" id="q-email" type="email" required data-bind="email">
  </div>
  <button class="btn pri" type="submit">Send</button>
</form>
<div class="note ok" data-when="step=sent" role="status">
  Sent. We reply to <span data-text="email">your address</span> within [SUPPORT RESPONSE TIME].
</div>
```

A confirmation before something final:

```html
<button class="btn danger" type="button" data-when="!asking" data-set="asking=on">Cancel order</button>
<div class="note bad" data-when="asking">
  Cancel order 0412? You can cancel free until 6:00 PM today.
  <button class="btn danger" type="button" data-set="status=cancelled; asking=">Yes, cancel it</button>
  <button class="btn" type="button" data-set="asking=">Keep my order</button>
</div>
```

Three more attributes tell the checks and the map what you intended:

- `data-does="Opens the refund form"` on a link or button: a sentence for the map when the effect is not obvious from the label.
- `data-noop="Already the current plan"` on a button that rightly does nothing here.
- `data-js` on a button wired by the page's own `<script>`. The browser audit still presses it and fails it if nothing happens.

For behavior the attributes cannot express (a running clock, a computed total), add a `<script>` after `blueprint.js` and use `blueprint.state`, `blueprint.set("key=value")` and `blueprint.flash("…")`. Keep it small; the blueprint shows what happens, it does not implement it.

Use buttons with `type="button"` unless the button submits a form that has `data-set`. A plain form submit reloads the page and loses the state.

Do not use the browser's own alert or confirm boxes. Their wording cannot be designed, and the audit warns about them.

## 4. The stylesheet's vocabulary

`blueprint.css` starts neutral. Change the tokens at the top to match the product; add new patterns to the file, not to a page.

| Purpose | Classes |
|---|---|
| Layout | `wrap` (`narrow`), `sec`, `stack` (`tight`, `loose`), `row` (`between`, `end`, `top`), `grow`, `cols`, `split` with `main` and `side` |
| Type | `h1`–`h3` elements, `eyebrow`, `lede`, `mut`, `sub`, `sm`, `b`, `num` |
| Controls | `btn` (`pri`, `quiet`, `danger`, `block`, `off`), `chip`, `link` |
| Forms | `field`, `label`, `input`, `select`, `textarea`, `hint`, `err`, `check` |
| Surfaces | `hdr`, `brand`, `nav`, `foot`, `card`, `note` (`ok`, `warn`, `bad`, `info`), `badge` (same four), `tbl-wrap` + `tbl`, `kv`, `toast` |
| Page kinds | `message` with `message-h` and `message-b`; `doc`; `spoken` with `line` (`them`); `offstage` |

A wide table goes inside `tbl-wrap` so it scrolls within itself on a phone instead of pushing the page sideways.

## 5. The scripts

All take the blueprint folder as their argument. Where `python3` is not a command (some Windows setups), use `python`.

| Script | Needs | Does | Writes |
|---|---|---|---|
| `init_blueprint.py <dir> --name "…" --summary "…"` | Python 3 | Copies the kit and four example pages into a missing or empty folder; refuses linked destinations and file overwrites. The examples fail the check until replaced or removed. | the folder |
| `check_blueprint.py <dir>` | Python 3 | Manifest against files, links, anchors, buttons that do nothing, unreachable pages, dead ends, journeys, filler text, retired wording, unlabelled fields, duplicate ids. Lists open decisions. Exit 1 on any `FAIL`. | `_check/static.json` |
| `browser_audit.cjs <dir>` | Node, Playwright | Opens every page at every width and variant: script errors, missing files, sideways overflow, cut-off text, blank renders. Presses every button from a fresh load, follows buttons that a press reveals, records what each press shows. Options: `--only a,b`, `--no-clicks`, `--no-shots`, `--widths 1440,390`. Exit 1 on problems, 3 if no browser. | `_check/browser.json`, `_check/shots/*.jpg` |
| `build_map.py <dir>` | Python 3 | Builds the map from the pages and the two result files. | `map.html` |

Screenshots are named `page@width.jpg` and `page@width~variant.jpg`. Look at them.

The audit presses only what it can see. A button that no variant and no press ever reveals is reported as never visible: add a variant that shows it.

## 6. Conventions that prevent rework

- **File names are stable words**, never codes: `order-status.html`, not `A3.html`. Inserting a page then changes no link.
- **One fact, one wording.** State each rule once on a reference page and copy that wording wherever it appears, so a change can be found by searching.
- **Shared chrome is the same on every page of a group.** Plain HTML has no includes, so a header copied to forty pages is forty edits when the navigation changes. For more than a dozen pages, write them with a small generator script kept in `_gen/` inside the blueprint folder (shared header, footer and sidebar as functions, one call per page) and re-run it. Files and folders whose names start with `_` are ignored by the checks.
- **Variants over duplicate pages.** A page that differs by role or status is one file with `data-variants`, not three files that drift apart.
- **Separate pages for separate moments.** A dialog that asks a real question, a step of a multi-step flow, a message: each is its own page or its own state, so the map can show it.
- **Rebuild the map last**, after the checks, every time.
