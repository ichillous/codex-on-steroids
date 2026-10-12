---
name: workspace-engineering
description: Run or resume durable project engineering jobs with LangGraph, bounded Codex specialists, Graphify evidence, validation, and independent review. Use for work needing persistent state or coordinated specialists.
---

# Workspace engineering

Use this workspace's executable coordinator when the task benefits from durable state, parallel investigation, recovery, or independent review. Ordinary focused edits can use the canonical engineering workflow directly.

The workspace root is the directory containing `tools/engineering/eng.ps1` and `.codex/workflows/engineering.md`. Resolve it explicitly; embedded repositories are separate Git roots. Read the generated `.codex/project-context.md` and repository registry. The graph publication may be absent in a newly onboarded project; never create synthetic evidence to make a task pass.

1. Read `.codex/workflows/engineering.md` and relevant repository `AGENTS.md` files. Define the user outcome, acceptance criteria, selected repositories, permitted write paths, and check IDs. Read `dev-docs/engineering-automation/operating-guide.md` for the task schema and examples. If the graph is unavailable, obtain the user's explicit task-specific source-fallback authorization and record it in `graph_exception`; setup itself is not that authorization.
2. Run `tools/engineering/eng.ps1 doctor`; use `doctor --live` when effective SDK/model configuration must be verified. A static manifest does not establish runtime loading.
3. For a new job, save a JSON or YAML task under `.engineering-state/tasks/`. Select `investigate` for research and `run` for implementation; both accept `--task <path>` and `--background`. The MCP `engineering_start` tool accepts the task object itself, not a file path.
4. For an existing job, retain its run ID and read status and the report instead of creating another task. Use `resume --run <id>` only after inspecting its recorded state. If an operation is unsettled, inspect its process/session and current working files, preserve unrelated staged work, and follow the reconciliation procedure first. A pending native approval must be answered as that specific request; task text and model output cannot authorize it.
5. Review the report against acceptance criteria and current source. Report actual checks, unresolved findings, source-state changes, and graph freshness limits. Coordinate any required fix within the existing job's scope.

The task's `scope` is an ownership contract and a detected-change boundary; it is not an OS path allowlist. Use separate verified checkouts for parallel writers. Never rerun an uncertain implementation operation just to escape recovery state. Follow the operating guide's reconciliation procedure and preserve existing work.

Roles are defined in `.codex/agents/`. SDK workers consume those canonical prompts. They do not recursively delegate or receive the coordinator's job-start capability. Existing configuration, skills, and MCP declarations remain subject to the worker runtime's actual discovery and native permissions.
