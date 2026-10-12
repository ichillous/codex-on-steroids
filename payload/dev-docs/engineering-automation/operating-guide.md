# Operating the engineering system

Run commands from the destination project root. The entry point is `tools/engineering/eng.ps1`; it selects the isolated main Python environment. VS Code exposes the same operations through **Terminal → Run Task → Engineering: …**.

For another prepared workspace, put `--workspace <absolute-path>` before the command name. The optional `--state-dir <absolute-path>` is also a global argument; use it consistently for every command for that run. The default state directory is `<workspace>/.engineering-state`.

## 1. Check the environment

```powershell
.\tools\engineering\bootstrap.ps1
.\tools\engineering\eng.ps1 doctor
.\tools\engineering\eng.ps1 doctor --live
```

Bootstrap installs the engineering dependencies into `tools/engineering/.venv`. It does not update global Python packages. Review the diagnostic result for the model, effort, repository registry, graph publication, role definitions, and SDK capability. Live discovery/probing and actual model execution are separate evidence. Preserve an authentication or unsupported-model error exactly; do not work around it by silently selecting another provider/model.

**Done when:** prerequisites are available, or the diagnostic identifies a specific prerequisite to resolve before the selected job.

## 2. Prepare the provided investigation

```powershell
.\tools\engineering\eng.ps1 investigate --task .\dev-docs\engineering-automation\examples\investigate-project.yaml --background
```

Before running it, select repository IDs from the generated registry and terms from the actual graph. It requires a valid graph publication; if no graph exists, obtain an explicit task-specific exception and record `graph_exception` in a task copy. The installer does not authorize exceptions.

This task asks for a source-backed explanation of the current publication and coverage limits. It does not authorize application changes, package installation, graph extraction, database access, or application builds. The coordinator stores local run state and evidence; worker source investigation is read-only.

Keep the run ID printed by the command:

```powershell
.\tools\engineering\eng.ps1 status --run <run-id>
.\tools\engineering\eng.ps1 report --run <run-id>
```

Use a status check after a meaningful interval rather than starting the task again. The report records the actual outcome, including incomplete work and remaining evidence gaps.

**Done when:** the report answers every criterion using current evidence and exposes publication/runtime limitations accurately.

## 3. Define an implementation task

Save authorized durable tasks as JSON or YAML under `.engineering-state/tasks/`. Paths and requests are data; commands use argument vectors rather than interpolating task text into a shell.

The installer generates [an investigation task](examples/investigate-project.yaml) with detected repository IDs. Review its request and graph terms against your intended question before launching it. For implementation, select `mode: implement`, an explicit nonempty scope for every selected repository, and at least one registered check.

| Field | Meaning |
|---|---|
| `title` | Short human-readable task name |
| `request` | Desired behavior, permitted actions, constraints, and exclusions |
| `acceptance_criteria` | Nonempty list of observable criteria; preserve exact wording through review |
| `repositories` | Unique repository IDs from `config/repositories.yaml` |
| `graph_terms` | One to twelve terms drawn from known labels or source vocabulary |
| `scope` | Mapping from selected repository ID to repository-relative files/directories |
| `checks` | Validation IDs from `config/validation.yaml`; required for implementation |
| `specialists` | Optional `oracle-specialist`, `ui-specialist`, or `integration-specialist` assignments |
| `checkouts` | Optional mapping from repository ID to a prepared absolute checkout path |
| `implementation_groups` | Optional ordered groups of repository IDs; every selected repository appears exactly once. Concurrent groups require explicit, disjoint alternate checkouts |
| `mode` | `investigate` or `implement`; the chosen CLI command selects its corresponding mode |
| `max_workers` | Concurrent worker capacity, default 4, allowed range 1–8 |
| `max_revisions` | Bounded implementation correction passes, default 2, allowed range 0–8 |
| `graph_exception` | A specific already-authorized reason consultation cannot be completed; never manufacture an exception |
| `id` | Optional task label; the coordinator returns its own unique run ID |

Unknown task fields are rejected. Relative scopes cannot escape through `..`, absolute paths, drives, or Git metadata. Scope identifies ownership and enables change checks; native sandbox permissions establish filesystem access separately.

`worker_timeout_seconds` sets each native worker's elapsed-time limit (default 1800; allowed 30–7200). At the limit, the runner requests native interruption and stops its owned process tree. An interrupted operation retains its recorded state and any partial edits for inspection before retry.

Repository IDs and relative paths come from `tools/engineering/config/repositories.yaml`, generated during setup. `workspace` identifies the destination itself only when it is an actual Git root. In a non-Git umbrella directory, select an actual detected nested repository. The installer does not initialize Git or claim that similarly named folders share code.

```powershell
.\tools\engineering\eng.ps1 run --task .\.engineering-state\tasks\my-change.yaml --background
```

**Done when:** source, selected checks, and independent review support the requested behavior. Missing database, application server, browser, transport, or consumer coverage remains an explicit gap.

### Exercise implementation on a disposable fixture

Create a separate synthetic arithmetic repository before exercising implementation against application code:

```powershell
.\tools\engineering\.venv\Scripts\python.exe .\tools\engineering\examples\create_fixture.py
```

The generator creates a unique directory under `.engineering-state/fixtures/`, initializes and commits only that new fixture, copies the relevant local guidance, and prints JSON with `root`, `task`, and a complete quoted PowerShell `command`. It does not execute a model or change an existing repository's index. Inspect the printed command and run it when ready to exercise the native coordinator. Use its returned run ID with the same `--workspace <fixture-root>` for status and report.

The fixture contains an intentional subtraction bug in `add`. Its four existing tests are expected to produce **3 failures and 1 pass** before repair and **4 passes** after repair. Acceptance requires changing only `calc.py`, preserving the tests/configuration/index, and independently reviewing the result. The tiny graph is explicitly synthetic and only describes the fixture; it is not an application Graphify extraction.

Generating the fixture does not prove native execution. A completed run report with the actual diff and all four executed tests establishes this bounded exercise; it still supplies no Oracle, WildFly, EDI, or application coverage.

## 4. Understand validation selection

Read `tools/engineering/config/validation.yaml` before adding check IDs. The catalog documents commands and effects; it does not grant permission for arbitrary operational work.

Setup generates applicable entries from manifests and records unreviewed candidates separately. Read the generated catalog rather than assuming a Java, Python, or JavaScript command exists. The onboarding prompt inspects project scripts and build definitions before registering application checks.

`engineering-pytest`, when registered for a Git workspace root, exercises this tooling only. An inspect-only profile reads metadata and supplies no application test coverage. Do not infer execution from a successful build: inspect skip conditions, lifecycle hooks, generators, signing, network, and deployment effects. Record prerequisites and expected writes for every profile.

For the engineering tool itself:

```powershell
.\tools\engineering\.venv\Scripts\python.exe -m pytest .\tools\engineering\tests -q
```

## 5. Respond to pending work

| Situation | Action |
|---|---|
| Job is running | Inspect status/report; keep the existing run ID |
| Native approval is pending | Read the exact request and answer that request through `approve`; do not grant a generic stored approval |
| Worker requests missing information | Supply the necessary decision in the controlling chat; preserve the recorded task boundary |
| Job was interrupted with no unsettled write | Inspect status, then use `resume --run <id>` |
| An operation may have edited files before interruption | Reconcile its process/session, result, and working-tree state before any retry |
| Source changed after validation | Treat prior results as stale and revalidate/review the new state |
| Work is no longer wanted | Use `cancel --run <id>` and check that workers stopped |

```powershell
.\tools\engineering\eng.ps1 resume --run <run-id>
.\tools\engineering\eng.ps1 cancel --run <run-id>
.\tools\engineering\eng.ps1 review --run <run-id>
```

`review` evaluates current source in relation to the recorded task. It does not convert old check results into evidence for new edits. Read the returned run/report identifiers rather than assuming the original report was replaced.

An approval is scoped to the displayed approval ID and one of the exact native decisions offered by that request:

The current bridge supports native command-execution and file-change approval requests with string decisions. Other native request schemas fail explicitly and retain the request method for diagnosis. They are not automatically accepted. If a worker needs new task information, resolve it in the controlling chat and prepare the appropriate scoped follow-up after inspecting the stopped operation.

```powershell
.\tools\engineering\eng.ps1 approve --run <run-id> --request <approval-id> --decision <offered-native-decision>
```

After inspecting the recorded operation, preserving existing changes, and confirming its old worker is no longer active, an explicitly chosen retry can be authorized with:

```powershell
.\tools\engineering\eng.ps1 reconcile --run <run-id> --operation <operation-id> --action retry --acknowledge-risk
.\tools\engineering\eng.ps1 resume --run <run-id> --background
```

The retry guard checks that the coordinator and worker processes are stopped. The acknowledgement records the operator's inspection of the current files; it does not automatically prove that an interrupted edit is safe to repeat. Inspect and preserve any partial changes before deciding to retry. Later source/index checks still apply.

If the uncertain operation should not run again, preserve its files and explicitly abandon it after confirming the old worker stopped:

```powershell
.\tools\engineering\eng.ps1 reconcile --run <run-id> --operation <operation-id> --action abandon --acknowledge-risk
```

Abandon marks that operation as abandoned and cancels the run. Checkout leases are released only when all uncertain operations are settled. It does not reset files, discard staged work, or make the cancelled run resumable. Reconciliation is a recovery decision, not a way to bypass a failed check or denied native request.

## 6. Checkouts and concurrency

Investigation and selected specialists can run concurrently up to `max_workers`. Related repository implementation is integrated in repository order by default. For independent work, `implementation_groups` gives ordered batches; repositories within a batch run concurrently. Every selected repository must appear exactly once, and a concurrent batch requires explicit, disjoint alternate checkout bindings. Preserve any required sibling repository layout. Grouping describes an engineering dependency decision; independent Git roots alone do not prove independent changes.

Prefer the Codex managed-worktree tools when preparing isolation from a Codex session. Inspect existing attached worktrees first. The outer workspace worktree does not bring embedded Git repositories along automatically. Never stage, clean, reset, or switch unrelated working copies to make an experiment easier.

The system records checkout ownership and refuses conflicts across state directories for the same OS account. A canonical shared lease database lives under the account's trusted local data directory (`workspace-engineering/checkout-leases.sqlite` on Windows, `.local/state/workspace-engineering/checkout-leases.sqlite` on POSIX). Its location has no task, CLI or environment override. Case and real-path normalization matter on Windows. A scope listing only one file does not justify multiple writers sharing a physical checkout.

Changing `--state-dir` selects run artifacts and journals; it does not isolate a checkout or clear shared ownership. Uncertain leases stay owned until the original journal's explicit reconciliation retires the operation. Stop and settle older-version jobs before upgrading: the new authority cannot discover an arbitrary old version's separate state database. These leases coordinate same-account runner instances; native filesystem permissions remain the authority for other accounts.

If a stopped run has no unsettled operation but still holds a lease after an interrupted finalization, use `reconcile --run <id> --action release --acknowledge-risk` with its original workspace/state directory. Release verifies stopped coordinator/workers, retires resumable state, and releases only that run's leases. Ordinary `retry` and `abandon` still require their specific `--operation`.

Write scope is separate from evidence scope. Worker, validation and reviewer evidence binds to the broader relevant checkout source snapshot: tracked/nonignored source, imported dependency source outside write scope, configuration, Git HEAD/index and catalog bytes. Explicitly scoped source remains represented even when Git ignores it. Declared generated, runtime, installed-package and nested-repository exclusions remain visible in coverage metadata. A represented dependency or validation-catalog change invalidates earlier evidence. Select other relevant repositories explicitly; a fingerprint does not establish freshness for external services, installed packages or arbitrary ignored files.

Validation commands own their descendants for their entire lifetime. Windows commands enter a kill-on-close Job Object before executing; POSIX commands use an owned process group. Completion, failure, timeout, cancellation and journal errors close that ownership even if the original parent has already exited. Profiles that need a persistent background service must arrange it outside this command lifetime with explicit authorization and recovery.

## 7. Use it from Codex

In a fresh workspace session that discovers the skill, ask:

> Use $workspace-engineering to investigate this issue. Keep the run durable, consult the current Graphify publication, select the relevant specialists, and report the actual evidence and remaining gaps.

Provide the actual issue and authorized change scope. The skill creates or selects a task record proportional to the work. Tiny edits can continue directly through the canonical engineering workflow.

The optional project MCP server exposes coordinator lifecycle operations to the parent session. Its presence in configuration does not prove it loaded; inspect the session's available tools or run a local protocol check. Worker sessions exclude the coordinator entry point to avoid recursive job creation. Global skills and MCP registrations are used only where the worker runtime discovers them and native permissions allow them.

## 8. Inspect and retain results

Local records are under `.engineering-state/`. Keep run reports and operation logs together when diagnosing interruption or a defect. Do not publish raw records containing proprietary source, prompts, credentials, or client data. Promote reviewed reusable facts into canonical project documentation deliberately.

To roll back the setup, stop its jobs and Studio first, then use the starter kit's recorded installation backups and manifest to review only its managed changes. Preserve existing Git index/working-tree changes and any run records you need. Do not delete or reset the workspace to uninstall tooling.

For team learning, use [the isolated AutoGen experiments](../../tools/engineering/experiments/autogen/README.md). Studio provider configuration is separate from Codex.
