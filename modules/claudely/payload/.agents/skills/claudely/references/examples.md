# Choosing a useful amount of process

These are examples to adapt to the task, not mandatory sequences or permission grants.

| Request | Useful action | Completion evidence |
|---|---|---|
| Fix a misspelled visible label | Inspect the string's application and localization context, edit the intended value, check the diff | The correct value in the correct place; a targeted render or localization check if needed |
| Login fails after session expiration | Trace the existing session/refresh flow, reproduce expiration, change the cause, run the relevant regression | Observed expected behavior for expiration, with command/output or permitted user-flow observation |
| Change a shared API response | Trace callers, permissions, error/transaction behavior, older consumers, and relevant graph evidence; plan compatibility and checks | Criteria mapped to source and affected consumer checks; explicit coverage gaps |
| A test fails intermittently | Record the trigger and failure, inspect the responsible boundary and environment, select a meaningful reproduction | Actual failure/success observations and remaining uncertainty; no invented pass from a single favorable run |
| Review a broad change | Assign a read-only reviewer if supported; supply criteria, diff/source, and actual check evidence | Concrete material findings or no material findings; correct attribution to fresh or inherited context |
| Continue work after compaction | Recover intent and the task record, inspect current files and active operations, continue the next unmet criterion | Preserved scope and work; reconciled current state; actual new evidence |

## A small working brief

Use a few lines in the conversation unless a durable document is useful and authorized:

```text
Outcome: the requested behavior and why it matters.
Boundary: affected application/contracts and excluded work.
Evidence needed: decisive source/runtime observation; graph requirement if applicable.
Check: smallest meaningful expected result and known prerequisites/effects.
Open decision: only consequential uncertainty that changes dependent work.
```

## Review assignment

```text
Check the stated outcome and criteria against the current change and check evidence.
Read only within the assigned scope; do not edit files or alter the Git index.
Flag material correctness, compatibility, or requirement gaps with a concrete
trigger/path, consequence, source location, evidence, and confidence.
No material findings is valid. Keep optional style suggestions separate.
State any missing evidence or inherited-context limitation.
```

An assignment is a behavioral contract, not a sandbox. The coordinator still owns integration and must assess findings against source and task scope. Use actual supported collaboration tools, with bounded ownership and the existing project's agent/review limits. Do not copy Claude-specific tool names or agent YAML.

## Compact continuation record

```text
Outcome/exclusions:
Criteria: passed, failed, not_run, or unresolved, each with its evidence.
Current paths/state: changed files, preserved edits, selected graph and limits.
Decisions: brief reason and source/evidence reference.
Checks: exact command or observation, result, and what it proves.
Active operations: workers, processes, pending approvals, uncertain effects.
Next step: next unmet criterion and the action to resolve it.
```

Do not write secrets or real customer payloads into this record. On recovery, compare the record with current files and runtime state; uncertain external actions require reconciliation before replay. A check that did not run cannot be marked passed.
