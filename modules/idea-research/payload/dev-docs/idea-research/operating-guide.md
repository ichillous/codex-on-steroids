# Operating idea research

This workspace investigates open-source AI ideas for Codex users and saves auditable local decisions. Start with [the workflow](../../.codex/workflows/idea-research.md), [record schemas](schemas.md), and [the future invocation](../../.codex/prompts/research-idea.md).

## What is installed

| Location | Purpose |
|---|---|
| `.codex/workflows/idea-research.md` | Decision process, evidence standards, delegation, acceptance and recovery |
| `.agents/skills/idea-research/SKILL.md` | Concise skill entry point, discoverable when the host supports project skills or explicitly read |
| `.codex/prompts/research-idea.md` | Short future invocation |
| `.codex/research-roles/` | Six portable assignment templates plus ownership envelope |
| `dev-docs/idea-research/templates/` | Report, source, claim, experiment, decision, session and review examples |
| `tools/research/` | Python standard-library session initializer, offline renderer, structural validator and focused self-check |

These files do not register native agents, tools, hooks, or a slash command. They leave the engineering runner, model/provider settings, authentication, and global configuration intact. No new package is required. Use the existing `tools/engineering/.venv/Scripts/python.exe` or another verified Python 3.11+ interpreter.

## Verify the execution route for each session

Inspect the destination workspace's actual Git state, repository registry, validation catalog, task schema, configured model/effort, and supported tools before selecting a route. The engineering coordinator requires a nonempty repository list and accepts only its documented engineering specialist IDs; the research assignment templates do not add new IDs. Use the coordinator only when its prerequisites, task fields, permissions, and recovery behavior fit the work. Installing this module does not launch it or register research workers.

When the current task authorizes native collaboration, use supported worker tools with bounded ownership and retain actual worker identities and attributable outputs. Save diagnostics inside the current session. Authentication or tool discovery alone does not establish worker execution. Do not claim an engineering-coordinator run ID unless a coordinator actually created one.

Consult Graphify and verify consequential findings in current source. The starter kit creates a code-only AST publication; that graph may not cover an idea document, external research, or all relevant repositories. Record exact scope, freshness, query results, and any gap. A source-fallback exception must be authorized for the current task and recorded in its session; a previous session's exception or setup diagnostics do not transfer automatically.

## Start a future session

Read the workflow and frame the permitted effects first. Commands below run from the destination workspace root where the module was installed:

```powershell
& .\tools\engineering\.venv\Scripts\python.exe .\tools\research\init_session.py 'Ideas\Example — Idea Document.md' --name 'Example'
```

The example requires a real input at that path. The initializer creates an atomic directory with timestamp/random suffix, copies exact input bytes, hashes the original and copy, and writes initial state. It refuses inputs outside the workspace and never overwrites an existing session. It does not start research, grant Graphify fallback, install dependencies, create Git state, or mark a result complete. The command uses the OS-local zone for metadata; add `--timezone <IANA-zone>` when a specific zone is required. If that IANA timezone is unavailable in the interpreter, it fails clearly.

Research sessions are local working artifacts. The initializer retains the original input's absolute path and exact bytes; diagnostics and evidence may contain private information. Keep actual `Ideas/` contents, session records, inputs, and diagnostic logs out of a public repository unless separately authorized and reviewed for privacy. The distributed templates and examples are synthetic and are not completed research evidence.

Read the printed path and use that session throughout. Update the idea README with a latest-attempt entry without changing the latest completed result. Record the actual execution route/model, tools and workers after verification. Follow the exact standard layout in the workflow; templates are examples to adapt, not evidence.

**Done when:** original/copy/hash match, the brief and next decision are framed, permitted writes are assigned, route has been exercised by useful work, and the session index/state identify the active attempt.

## Render and validate

```powershell
& .\tools\engineering\.venv\Scripts\python.exe .\tools\research\render_report.py '<session>\report\report.md' --output '<session>\report\report.html'
& .\tools\engineering\.venv\Scripts\python.exe .\tools\research\validate_session.py --session '<absolute-session>' --output '<session>\evidenceandlogic\review\validation-results.json'
```

Replace `<session>` with the actual path. Renderer input and output must share a directory so relative evidence links remain valid. It embeds all substantive report content, escaped text, TOC and CSS. It supports headings, paragraphs, fenced code, flat lists, blockquotes, pipe tables, bold/italic, inline code and inline links. It is a deliberately small subset of CommonMark: do not rely on raw HTML, images, nested lists, reference-style links, footnotes or task-list widgets. Raw HTML is displayed as text. Public links open online; local companion Markdown/JSON/CSV files remain separate.

The validator reads research records and original input. Its only optional write is the selected JSON output inside the same session's `evidenceandlogic/review/` directory. It checks required/nonempty files, containment, input bytes/hash, structured parsing, source/claim/experiment references, explicit `not_run` protocols, authored-document links, HTML equality to Markdown rendering, script/asset absence, and state/index basics. It does not fetch external URLs, repeat experiments, infer real worker independence, or establish source truth. It permits explicit unknown dates and versions when recorded honestly.

Exit `0` means the executed checks did not fail. **It does not mean AC1-AC9 are complete.** The output separately records `structural_status`, `acceptance_status`, and `acceptance_criteria`. Without an attributable acceptance record all nine criteria remain `not_run`. Save human assessments in `evidenceandlogic/review/acceptance-review.json` using the schema; the validator imports them and verifies evidence paths. It does not transform them into independently proven facts.

Open `report/report.html` in an available browser at a desktop width and a narrow width, inspect tables/navigation/readability, and save what was actually observed. Inspect offline assets separately. A blocked browser leaves visual verification `not_run` with its exact limitation. Do not infer visual success from HTML parsing.

**Done when:** structural checks pass, independent review resolves or discloses substantive findings, AC1-AC9 have attributable statuses, report/summary/next steps agree, and browser limitations are explicit.

## Resume and finish

For native collaboration, read `run/session.json`, `run/state.md`, recent results, current artifacts and active worker/process state. Reconcile an uncertain experiment or writer before rerunning it. There is no native durable-engine resume guarantee: saved project files support a manual continuation after current state is checked. Retain an actual coordinator run ID if that route was used and follow its documented recovery instead.

When requirements remain, mark `incomplete` or `blocked` with reason and next action. When review and validation support completion, set `complete`, record the actual timestamp and reason, and advance the idea README's latest completed result. A completed investigation may recommend INSUFFICIENT EVIDENCE. Never replace a verdict's uncertainty with a misleading completion claim.

Use a new dated session for a substantive refresh. Preserve prior sessions and explain changes in decisive evidence/conclusions. No publication or external communication is part of this workflow unless separately authorized.
