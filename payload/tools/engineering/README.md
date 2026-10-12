# Workspace engineering

Run durable engineering tasks from VS Code or PowerShell using LangGraph, Codex workers, Graphify evidence, declared validation commands, and independent review.

## Start here

From the destination project root after starter-kit setup:

```powershell
.\tools\engineering\bootstrap.ps1
.\tools\engineering\eng.ps1 doctor
.\tools\engineering\eng.ps1 doctor --live
.\tools\engineering\eng.ps1 investigate --task .\dev-docs\engineering-automation\examples\investigate-project.yaml --background
```

Keep the returned run ID and inspect `status --run <id>` and `report --run <id>`. Model-backed commands use the authenticated Codex runtime and account capacity. `doctor --live` probes the SDK runtime; a subsequent worker run establishes model execution.

In VS Code, use **Terminal → Run Task → Engineering: Doctor**, then **Engineering: Investigate task**. Existing editor settings remain independent of these tasks. Read the generated project context and validation catalog first. The investigation example needs a real graph or an explicitly authorized exception for that task. The workspace skill is available as `$workspace-engineering` in a session that discovers project skills.

For a separate synthetic implementation exercise, run `.\tools\engineering\.venv\Scripts\python.exe .\tools\engineering\examples\create_fixture.py`. It creates a new disposable Git repository and prints the exact coordinator command. See the operating guide for its expected failing baseline and completion criteria.

## Guides

- [Operating guide](../../dev-docs/engineering-automation/operating-guide.md): task schema, commands, approvals, recovery, validation, and VS Code use.
- [Architecture](../../dev-docs/engineering-automation/architecture.md): component ownership, worker roles, evidence, and persistence.
- [Troubleshooting](../../dev-docs/engineering-automation/troubleshooting.md): diagnose runtime, model, graph, checkout, and recovery problems.
- [Portable setup guide](../../dev-docs/engineering-automation/portable-guide.md): adapting this setup, graph requirements, and verification limits.
- [AutoGen experiments](experiments/autogen/README.md): isolated Studio, bounded team export, and transcript comparison.
- [Canonical engineering procedure](../../.codex/workflows/engineering.md): repository guidance and acceptance requirements.

## Ownership

| Location | Purpose |
|---|---|
| `src/workspace_engineering/` | Executable coordinator, SDK adapter, repository manager, evidence, checks, and reports |
| `config/repositories.yaml` | Actual repository identities and paths |
| `config/validation.yaml` | Check IDs, commands, prerequisites, and effects |
| `config/workflows.yaml` | Workflow/default metadata |
| `config/tools.yaml` | Capability descriptions; runtime availability is probed separately |
| `../../.codex/agents/` | Canonical native and SDK worker prompts |
| `../../.engineering-state/` | Ignored local checkpoints, operation records, run reports, and Studio data |

The main Python environment is `.venv`. Studio has its own `.venv-studio` inside `experiments/autogen`. `graphify.ps1` reuses a compatible Graphify interpreter or installs the pinned package in `.venv-graphify`, then consults an existing publication or creates a missing code-only AST graph. It accepts `-Scope`, `-Query`, and `-GraphifyPython`; existing publications are preserved. These environments do not upgrade globally installed packages.

## Validation

```powershell
.\tools\engineering\.venv\Scripts\python.exe -m pytest .\tools\engineering\tests -q
```

Use the run report for actual runtime outcomes. A configured role, available model, or successful synthetic test does not establish that an application change works. The engineering tests exercise the tooling; application validation is selected per task through the catalog.
