# Portable engineering setup

This starter kit brings the engineering workflow, six Codex roles, a project skill, VS Code tasks, LangGraph persistence, Graphify consultation, and an isolated AutoGen lab to a Windows project. The setup command inventories the destination and runs a repository-specific onboarding prompt; review the generated context and validation catalog before your first implementation task.

## 1. Install and tailor

Copy the entire `engineering-starter-kit` folder into the root of the destination project and follow its top-level README. The default destination is the kit folder's parent; an explicit destination can also be selected. Run the PowerShell setup command from that README.

The installer copies source and templates, recreates local Python environments from their lockfiles, registers project integration, and gathers a bounded inventory. It detects Git roots and manifests, then supplies the onboarding prompt with the destination context so that it can inspect real instructions, applications, scripts, and checks. No repository architecture is inferred solely from folder names.

The onboarding prompt should leave a concise project context with source anchors, an accurate repository registry, and validation profiles whose effects have been inspected. An unavailable model, blocked configuration, missing Git root, missing graph, or unanswered project question remains visible. Successful copying or dependency installation is not proof that the onboarding model completed or that the application was tested.

The kit includes source, lockfiles, and tests. It excludes credentials, global settings, hooks, virtual environments, run logs, database contents, source graphs, and application source from its origin project. Existing project files must be merged or reported as conflicts according to the installer's recorded plan and backup policy.

The repository also carries optional `idea-research` and `blueprint-first` modules. Select either or both with `Setup.ps1 -Modules idea-research,blueprint-first`; add `-ProjectRoot` for a centrally stored kit. Existing selections are retained on later reruns. These source bundles use the same safe file installation, backups and rollback as the engineering base. Setup does not install the blueprint browser audit's Node/Playwright/browser prerequisites.

After selecting `idea-research`, explicitly use `$idea-research` and read `dev-docs/idea-research/operating-guide.md`. Its assignment templates and standard-library utilities support evidence-led research sessions; native worker dispatch and interrupted-session recovery remain explicit/manual. After selecting `blueprint-first`, explicitly use `$blueprint-first` to review journeys, states and touchpoints. Its owner must approve the blueprint before implementation. Neither skill automatically starts the engineering coordinator.

## 2. Check the result

Read `.codex/project-context.md`, `tools/engineering/config/repositories.yaml`, and `tools/engineering/config/validation.yaml`. Confirm that each repository path identifies the intended Git root, and that each selected check's cwd, prerequisites, arguments, and effects fit this project.

From the destination root:

```powershell
.\tools\engineering\eng.ps1 doctor
.\tools\engineering\eng.ps1 doctor --live
```

The normal doctor reports local files, dependency versions, repository discovery, and graph status. The live probe checks native SDK authentication and model availability without a model turn. Neither command executes application tests. Missing graph data is a meaningful prerequisite gap even when dependency installation succeeded.

Python 3.11 or newer is declared by the package. The dependency locks are for Windows; a version declaration is not proof that every supported Python version and machine has compatible wheels. Keep exact pip errors if dependency installation fails, and use a compatible interpreter rather than modifying global packages.

## 3. Use a new Codex chat

Open the destination root in VS Code, reload once after setup, and start a new Codex chat. Paste:

```text
Use $workspace-engineering for this task. Confirm the project instructions,
skill and engineering MCP tools are available. Read the generated project
context and registry, verify consequential assumptions against source, and
select relevant specialists and validation.

Task: [describe the requested feature, defect, investigation, or review]
```

New chats use persistent project files but do not inherit prior conversation history. Model-backed runs consume the authenticated account's capacity. The default team uses Astra Ultra, up to four workers, and at most two correction rounds. Model support and effective sandbox behavior are verified by the worker runtime. Global tools and skills are available only if that runtime discovers them.

The generated `dev-docs/engineering-automation/examples/investigate-project.yaml` is a starting task. Review it before execution. The CLI and VS Code tasks expose the same job lifecycle:

```powershell
.\tools\engineering\eng.ps1 investigate --task .\dev-docs\engineering-automation\examples\investigate-project.yaml --background
.\tools\engineering\eng.ps1 status --run <run-id>
.\tools\engineering\eng.ps1 report --run <run-id>
```

## 4. Handle Graphify honestly

Default setup prepares Graphify after installing project configuration. It reuses a compatible Graphify interpreter or installs the pinned package in `tools/engineering/.venv-graphify`, and supplies a project Graphify skill when absent. It preserves and consults an existing valid `graphify-out/LATEST.md`; without a publication it performs local code-only AST extraction, records source hashes/provenance, validates graph endpoints and publishes a real destination graph. A valid legacy `graphify-out/graph.json` can be adopted; an invalid existing pointer is preserved and reported as an error.

Retry preparation with `tools/engineering/graphify.ps1`; query verified labels with `-Query '<symbol>'`. Initial extraction of large projects needs relative source scopes via `-Scope 'backend/src','frontend/src'`, or setup's `-GraphifyScope`. Existing publications are not automatically refreshed. Sensitive files, dependencies, generated outputs, links and installed kit tooling are excluded; documents/images and runtime behavior remain outside the default AST graph. Projects with no supported code/symbols report a gap. `-SkipDependencies` skips Graphify preparation as well as environment downloads.

The adapter queries labels and one-hop relationships, records bounds and confidence, and verifies accessible source hashes and anchors. Its `repo` identities must match registered repository IDs. Unknown identities, missing files, and unmatched labels are explicit evidence limits. A publication date alone does not prove current coverage.

When graph preparation is unavailable or its scope is insufficient, establish the required publication through an authorized workflow or obtain explicit source-fallback authorization for the particular task. Save the actual authorized reason and scope in that task's `graph_exception`. Never fill the field merely because setup found no graph. A synthetic graph is used only inside disposable tests and is labeled as synthetic; it is never a replacement for project evidence.

## 5. Resume and recover

Keep each run ID. Check status and reports before resuming. If an operation is unsettled, inspect the native process/session, recorded baseline, current diffs, and Git index before deciding whether retry is safe. A checkpoint does not stop a worker or undo partial edits.

See [the operating guide](operating-guide.md) for exact approval, cancel, reconcile, and resume commands. Never delete state or locks to force a second writer. Preserve native approvals; role instructions and task scopes do not create OS isolation.

## 6. Experiment with AutoGen

Use [the AutoGen lab](../../tools/engineering/experiments/autogen/README.md) to compare one analyst with a bounded analyst/reviewer team. Studio has its own environment and uses local project state. It does not import Codex authentication or Astra Ultra settings. Choose a compatible API model explicitly and supply its credentials through normal process environment management.

The included component checks and Studio startup smoke test make no model calls. A successful import or health response does not prove a provider connection or that the extra agent improved the answer.

## 7. Keep the project tailored

Revisit context and profiles when repository roots, dependencies, test commands, or deployment behavior change. Register only checks whose effects and result interpretation you understand. Build success, script inspection, skipped tests, and observed application tests are different evidence.

Use [the architecture guide](architecture.md) for component ownership and [troubleshooting](troubleshooting.md) for configuration, graph, recovery, and provider gaps. Prefer improving a concrete missing capability over copying unrelated personal tooling into the project.
