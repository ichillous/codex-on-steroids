---
name: claudely
description: Apply selected Claude Code work habits to Codex coding tasks with observable completion checks, focused context, proportional planning, and scoped review. Use for substantive implementation, debugging, refactoring, and review, or when explicitly invoking claudely.
---

# Claudely

Improve the working procedure using practices researched from Claude Code. Follow the user's intent, authorized scope, and controlling repository instructions. This skill supplements existing engineering workflows; where they require Graphify, consult the designated publication and verify consequential findings in current source. A missing or limited graph does not grant a fallback exception.

## Start with the result and its check

Identify the requested observable behavior, exclusions, affected boundary, and smallest meaningful completion check. Use existing checks when suitable. For a bug, reproduce the reported trigger before editing when practical; add a regression when it verifies meaningful behavior. For a UI change, check the relevant user flow and visual result where the task permits. Inspect a command's prerequisites and effects before running it.

Keep evidence distinct: source inspection, a structural validator, a synthetic test, local runtime behavior, and deployed behavior prove different things. Record the command or observation and its actual result. An unrun check remains a gap.

## Choose the amount of exploration and planning

- **Clear, narrow change:** read the target and relevant callers or conventions, implement, then run the focused check. Formal planning adds little to a typo or an obvious local fix.
- **Uncertain or broad change:** investigate the decisive behavior first, then make a short plan naming affected files, invariants, compatibility, failure cases, and verification. Trace shared contracts and consumers before choosing the change boundary.
- **Long task:** work in coherent, testable increments against the agreed criteria. Preserve remaining work explicitly; do not expand the product spec or declare completion from partial progress.

Resolve consequential ambiguity before dependent work while continuing useful independent work. Routine steps already authorized do not need another approval ceremony. Continue the current task through user steering and context compaction.

## Keep context focused

Use targeted search, source symbols, file paths, and compact findings. Load detailed documentation when it answers the current question; retain references instead of repeatedly pasting whole files. Keep durable rules in the project's existing instruction route and occasional procedures in skills. Do not create a competing instruction corpus or write global memory as a side effect.

Delegate independent, read-heavy investigations when they save time or context and supported tools are available. Give each worker its question, inputs, allowed actions, owned paths, expected evidence, and stopping conditions. Separate model context does not imply separate files or enforced read-only access; prevent overlapping writers and preserve staged, unstaged, and untracked work.

## Build, check, and refine within scope

Implement a coherent change, run the relevant check, read its result, and resolve failures within the task's limits. Address the cause of a failing check; do not weaken requirements or suppress errors to produce a pass. Continue permitted independent work when a required observation is unavailable and report exactly what remains unverified.

Make one bounded clarity pass over the authorized changed scope when it helps: remove duplication introduced by the change and prefer readable code consistent with the project. Preserve behavior and interfaces; avoid unrelated cleanup or speculative abstractions. Rerun affected checks after a meaningful refinement.

Use independent review when the change is consequential, spans shared contracts, or involved lengthy unattended work. Give the reviewer the outcome, criteria, current diff/source, constraints, and check evidence. Ask for material defects or requirement gaps with a trigger, consequence, location, and confidence; **no material findings is a valid result**. Do not demand extra findings or chase optional style preferences. Follow existing review limits and preserve unresolved issues.

Use a fresh reviewer context when the runtime supports it; otherwise describe inherited context honestly. If delegation is unavailable, perform a clearly labeled second perspective pass when useful. A review is evidence to assess, not an automatic completion guarantee.

## Continue and finish with evidence

For work spanning sessions or needing recovery, retain a compact handoff in the existing authorized task record: intent and exclusions; criteria and unresolved status; changed paths and preserved edits; decisions and evidence locations; actual checks; active workers/processes or approvals; and the next step. Reconcile current files and active operations before resuming; notes or transcript resume alone do not make replay safe. Keep short tasks in the conversation when a durable artifact adds no value.

Report the user outcome, changed scope, actual checks, unresolved criteria, and relevant evidence limits. This is prompt guidance, not a runtime gate. Codex has native hooks in supported versions, but this skill installs no hooks, worktrees, providers, model overrides, commits, or global configuration. Runner guarantees depend on the actual configured runner and observed execution.

For task-specific examples or a handoff/review format, read [examples.md](references/examples.md). For provenance, native compatibility, or evaluating changes to this skill, read [rationale.md](references/rationale.md); these references do not need to be loaded for every coding task.
