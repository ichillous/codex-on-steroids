# Blueprint first module

Turn an idea into a walkable specification before implementing it. This optional module adds the complete `blueprint-first` skill: guidance for roles, journeys, states, screens and other touchpoints; a linked HTML starter; Python structure and map utilities; and an optional browser audit.

Enable it with `-Modules blueprint-first` when running the starter kit's `Setup.ps1`. The full skill folder is installed under the destination workspace's `.agents/skills/blueprint-first/`. Start with [SKILL.md](payload/.agents/skills/blueprint-first/SKILL.md) and its linked references. Paths in the skill resolve relative to that folder.

The Python utilities use the standard library. The browser audit additionally requires Node.js, an available Playwright package (`playwright`, `playwright-core`, or `@playwright/test`), and a runnable browser. Setup does not install those optional browser dependencies. Without them, retain the static results and report browser verification as not run. An actual browser audit can open pages, press controls, and save screenshots; a source or syntax check cannot establish those outcomes.

Generated `blueprint/` pages are local planning artifacts. The initializer requires a missing or empty destination, refuses linked destinations, and preserves existing files. The starter pages and sample identities are synthetic, and the structure check deliberately fails until the sample pages are replaced or removed. Open owner decisions stay in brackets, chosen assumptions are recorded, and production implementation begins only after the owner approves the blueprint or otherwise explicitly authorizes proceeding. Adding this module does not itself create a blueprint or approve one.
