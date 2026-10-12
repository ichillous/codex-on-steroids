# Codex engineering setup

This project uses explicit instructions, native Codex role prompts, a discoverable skill, and a persistent LangGraph runner. Read [the generated project context](project-context.md) alongside current source; setup inventory is a starting point for investigation.

## Entry points

- [Engineering workflow](workflows/engineering.md): scope, source evidence, Graphify, execution, and acceptance review.
- [Task brief](prompts/engineering-task.md): proportional task contract and evidence template.
- [Graphify read-only traversal](references/graphify-read-only.md): bounded existing-graph lookup without extraction or feedback writes.
- [Portable guide](../dev-docs/engineering-automation/portable-guide.md): setup, tailoring, first use, and recovery.
- [Operating guide](../dev-docs/engineering-automation/operating-guide.md): commands, task schema, workers, approvals, and checkpoints.
- [Runner](../tools/engineering/README.md): package and environment ownership.

## A fresh VS Code chat

Open the destination root, reload the window after installation, and start a fresh Codex chat. Ask:

> Use $workspace-engineering for this task. Confirm the project instructions, skill, and engineering MCP tools are available, then inspect the current project context and repository registry. Task: [describe the requested outcome].

The setup is stored in files and does not depend on another chat's history. Existing run state remains in `.engineering-state`; supply the run ID to inspect or resume it. Ordinary prompts do not automatically launch a team. AutoGen Studio is started separately.

Project trust, host settings, native permissions, and actual runtime discovery still apply. A successful configuration parse is not proof that the VS Code extension loaded it. The CLI provides the same coordinator functions when MCP discovery is unavailable.

## Configuration boundaries

`AGENTS.md` routes the agent to this workflow. The workflow, task brief, and references are ordinary Markdown files. `.agents/skills/workspace-engineering/SKILL.md` is the skill. `.codex/agents` contains canonical role prompts, and the SDK reads those prompts explicitly. The installer registers the coordinator in the destination's project `config.toml` and preserves unrelated settings.

Global settings, credentials, third-party skills and servers, editor settings, and hooks belong to the destination environment. This kit does not copy personal configuration, hooks, source graphs, virtual environments, or another project's run state. It supplies a project Graphify skill when absent and can create a dedicated local Graphify environment and destination code graph. Some global tools may be available to workers if their runtime discovers them and effective permissions allow them; verify this instead of assuming it.

The six worker roles request `gpt-6-astra` with `ultra` reasoning. Model and effort compatibility must be checked on the destination machine. The runtime fails explicitly if those settings are unavailable; it does not silently select another model. `config/workflows.yaml` and `config/tools.yaml` document workflow/capability metadata; changing their descriptions alone does not reconfigure the executable worker runtime.

## Graph requirements

Resolve `graphify-out/LATEST.md` and verify its selected local publication. The kit does not include a graph for this project. Record relevant coverage, freshness, query output, and source confirmations. The graph adapter resolves source repository IDs through `tools/engineering/config/repositories.yaml`; unmatched IDs remain an explicit source-identity gap.

Default setup uses `tools/engineering/graphify.ps1` to reuse a compatible Graphify installation or install the pinned package, preserve and consult an existing publication, or prepare a missing code-only AST publication locally. Large projects need explicit source scope. Existing independently owned Graphify skills and publications are preserved. No upstream hooks or semantic provider calls are made by this setup path.

For a remaining graph gap, repair/prepare the publication through an authorized workflow or obtain an explicit exception for the individual task and record `graph_exception`. Code-only setup authorization does not cover semantic provider calls, external transmission, automatic refresh of existing publications, or a permanent graph bypass. For strict read-only work, use the JSON traversal reference instead of the preparation wrapper.

## Maintenance and rollback

Keep the repository registry and selected validation profiles aligned with actual Git roots and inspected build definitions. Re-run bounded onboarding when project structure changes. Preserve any custom task limits, prompts, check definitions, and local modifications.

Stop active jobs and Studio before removing the integration. Use the installer's recorded manifest and backups to review managed changes; preserve unrelated edits and existing Git indexes. Do not delete an existing `.codex` directory or reset the repository as an uninstall shortcut.
