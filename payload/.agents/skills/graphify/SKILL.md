---
name: graphify
description: Prepare and consult this project's Graphify knowledge graph. Use for /graphify or questions about repository architecture, symbols, relationships, and impact.
---

# Project Graphify

Read the project's `AGENTS.md`, `.codex/workflows/engineering.md`, and `.codex/references/graphify-read-only.md`. Resolve the workspace containing `tools/engineering/graphify.ps1`; embedded repositories retain separate identities. This project skill wraps the starter kit's pinned Graphify setup and local publication reader.

1. For authorized setup or a missing publication, run `tools/engineering/graphify.ps1` from PowerShell. It reuses a compatible installation or installs Graphify in a dedicated project environment, preserves an existing valid publication, and otherwise creates a real code-only AST graph. It does not use a semantic provider or install hooks. A large project needs a source scope, for example `tools/engineering/graphify.ps1 -Scope 'backend/src','frontend/src'`. Preserve the original requested scope and report exclusions; do not silently narrow it.
2. Read `graphify-out/LATEST.md`, the selected report and provenance. Check whether its source scope includes the current task. A setup graph covers code only; documents, images and runtime behavior are outside its proof.
3. Consult verified graph labels with `tools/engineering/graphify.ps1 -Query '<symbol or terms>'`. Record actual query results, coverage, source identity, freshness and confidence. An unmatched label is a coverage gap, not evidence that code or callers are absent. Refine once with verified vocabulary where useful.
4. Verify consequential relationships against current source and report remaining uncertainty. Do not claim adjacency proves call direction, runtime behavior or acceptance. Coordinator jobs also consult the selected publication through their own adapter.
5. Existing publications are reused rather than refreshed automatically. For an authorized scoped refresh or semantic document/image extraction, follow the installed upstream Graphify package's documented workflow with explicit scope and data flow. Preserve the prior publication and update `LATEST.md` only after validating the replacement. Do not select another provider merely because an environment key exists.

For a strict read-only request, use the in-memory JSON recipe in `.codex/references/graphify-read-only.md`; do not call the preparation wrapper, install packages, create a publication, or write feedback. If required evidence is unavailable, report the gap and continue only work permitted by the controlling request. An explicit task-specific `graph_exception` is recorded only when that source fallback has actually been authorized.

Default setup consumes code locally through `graphifyy`; it excludes sensitive files, dependency/generated folders, links and installed kit tooling. No semantic API key is needed. Set `-GraphifyPython '<existing-python.exe>'` to select a compatible external installation without changing it. Do not modify global settings, credentials, Git indexes, existing hooks or another project's graph.
