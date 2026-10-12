# Engineering automation troubleshooting

Start with the exact run ID, status, and report. Preserve the first error and the recorded source state. A retry is useful when it resolves a known problem; it is dangerous when it creates a second uncertain writer.

## Main environment or package missing

Run `tools/engineering/bootstrap.ps1`, then `tools/engineering/eng.ps1 doctor`. Use the explicit environment Python in `tools/engineering/.venv/Scripts/python.exe`. A successful global `pip install` does not establish the contents of this isolated environment.

For Studio, use its separate `experiments/autogen/bootstrap.ps1`. Do not fix a Studio dependency by upgrading the main runtime or globally installed Graphify dependencies.

## SDK authentication, model, or effort error

Run `eng.ps1 doctor --live` and keep the returned error. The configured engineering roles request `gpt-6-astra` and `ultra`; support is checked against the runtime, rather than inferred from a TOML file. Use the normal Codex sign-in interface if authentication is required. Do not read or copy credential-store contents into reports.

SDK workers have their own sessions and use the SDK's runtime. A model or tool that works in an existing VS Code conversation is not automatically verified in that process. No silent fallback model is configured.

## Role or skill not visible

Check that VS Code opened the workspace root and that the session permits project configuration. Native agent definitions are in `.codex/agents`; the skill is `.agents/skills/workspace-engineering/SKILL.md`. Reload/start a fresh session when discovery occurred before file creation. `doctor` parses the local files; actual IDE discovery still needs the running session's evidence.

The SDK reads the canonical role prompts explicitly. That is separate from native subagent discovery. Do not register duplicate role prompts in global configuration to hide a project-loading problem.

## Graph query has no matches or stale coverage

For missing Graphify tooling or a missing publication, run `tools/engineering/graphify.ps1` under authorized setup. It can install the pinned package in its own environment and prepare a code-only graph. If it requests a large-project scope, retry with `-Scope 'relative/source/path'`; existing publications are preserved. An invalid existing pointer must be repaired explicitly. Use `-GraphifyPython '<existing-python.exe>'` for a compatible external installation. A dependency download, empty source corpus or extraction failure leaves an actionable error rather than a placeholder publication.

Inspect `graphify-out/LATEST.md` and the selected publication's report. Check the run's actual terms and bounded output. Refine once using verified source vocabulary. Continue source investigation with the coverage limitation recorded. Missing edges do not establish absence of impact.

The new engineering tooling may not appear in a publication created before these files. Do not repoint `LATEST.md`, rewrite historical graphs, install Graphify, or trigger a full rebuild merely to remove that limitation. Follow the canonical maintenance procedure for an authorized refresh.

## Checkout locked or a run needs reconciliation

Read the recorded owner and operation before starting anything. Check whether the coordinator and underlying worker are alive and whether a completed result exists. Inspect current diffs and the original baseline. Keep existing edits intact.

Cancellation requests must reach the actual worker. A dead parent process does not by itself establish that its descendants stopped. Use reconciliation only after inspecting the evidence and confirming the old operation is quiescent. Choose `retry` only after deciding whether partial edits can safely be repeated; the acknowledgement is an operator decision, not an automatic source-safety proof. Use `abandon` to preserve the files and cancel the uncertain run when work should not be replayed. Do not delete the SQLite database or lock record to force a new writer.

## Check passes but tests did not run

Read the captured output and the validation result classification. Some repository POMs skip tests; an offline Maven invocation may also lack cached prerequisites. A script-listing check only establishes the available script definitions. Neither result is application behavior verification.

Choose a check that actually exercises the changed behavior, or report the exact environment gap. Do not remove assertions, weaken completion criteria, or silently mark missing runtime coverage as satisfied.

## Source changed after a check or review

The stored fingerprint no longer describes the current source. Determine whether the change came from a worker, build generator, editor, or another process. Inspect it before continuing. Revalidate affected behavior against the final source. Preserve unrelated changes rather than resetting the checkout to a stored fingerprint.

## AutoGen Studio starts but model execution fails

The Studio launcher uses `127.0.0.1`, one process, and `.engineering-state/studio` for data. It does not configure an API model. Generated teams use the installed OpenAI Chat Completions client and omit credentials; configure a compatible model explicitly and provide the normal runtime environment variable only to the Studio process.

Codex authentication and `ultra` reasoning are not imported into AutoGen. An AutoGen component passing an offline schema/round-trip test proves serialization, not a working model call. Do not replace the model with another provider merely because a key is present.

If port 8081 is already occupied, run `studio.ps1 -Port 8082` and use the reported URL. Stop the foreground server with Ctrl+C. The smoke check owns and stops its test process, and saves its results under `.engineering-state/studio`.

## When a report can claim completion

Every acceptance criterion must have concrete supporting source/check/runtime evidence, required checks must succeed with the intended coverage, and blocking review findings must be resolved. A synthetic tooling fixture can validate recovery or orchestration; it cannot prove Oracle, WildFly, browser, EDI, or customer deployment behavior.
