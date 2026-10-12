# Portable kit verification

## Graphify setup addition — October 12, 2026

The current kit installs/reuses pinned Graphify tooling and prepares a missing real code-only publication during default setup. The September 28 results below describe the earlier kit, which only detected Graphify evidence; its missing-graph setup behavior is historical and is superseded by this addition.

- Full installer/discovery/Graphify/wrapper suite: **90 passed, 1 skipped, 6 passing subtests**, in 28.61 seconds. Tests run with `python -B -m pytest engineering-starter-kit/tests -q -p no:cacheprovider`, using the existing engineering test environment and a disposable temporary base directory. The skip concerns Windows symlink creation permissions; the separate Windows junction test passed.
- Graphify-specific tests: **35 passed, 1 skipped**. Real local AST fixtures verify source hashes, publication reuse, registered repository identities with identical symbol names, and an explicitly unregistered non-Git workspace identity. Additional checks cover package bootstrap/retry, Python shadowing, pip destination settings, scope limits, source changes, invalid/legacy publications, and competing pointer creation.
- A fresh disposable Windows Git project ran the actual copied `graphify.ps1` wrapper. With an incompatible pre-existing Python Graphify version, it created `.venv-graphify`, downloaded `graphifyy==0.9.73`, and used its AST/build/report/export APIs. The publication contained **4 nodes and 4 directed edges**; a `Service` query returned **2 matching nodes and 3 adjacent relationships**. This made no semantic/model/provider call. `pip check` reported no broken requirements.
- The fresh-install check deliberately supplied `PIP_TARGET`, `PIP_PREFIX`, `PIP_ROOT`, and `PIP_USER` overrides. Installation remained inside the project environment and the external test destination was not created.
- A second actual wrapper invocation reused the installed runtime and publication. Every file hash under the disposable project's `graphify-out` remained unchanged. The current coordinator `GraphifyAdapter.query` loaded that publication, verified its checksum, and returned three source checks with **matched** freshness. These checks establish tooling compatibility and source identity, not application runtime acceptance.
- Real PowerShell control-flow fixtures verify that default setup calls Graphify before the engineering/Studio bootstrap stages, passes relative scopes and interpreter paths containing spaces/apostrophes, propagates Graphify failures, and defers preparation under `-PlanOnly` or `-SkipDependencies`. Other environment bootstraps were stubbed in these fixtures; the new full default onboarding/LangGraph/Studio path was not rerun against a real application.
- Independent source review found no unresolved blocking issue after correcting AST origin preservation, partial installation recovery, isolated child execution, pip destination control, and atomic no-clobber publication. The existing workspace publication pointer was preserved.

The reviewed and tested helper SHA-256 is `6d826426cc16ac463aa5b2ded143cd602b32164c528b29e3d569b9268bb4c478`; its tests are `20b96fde6eee22be6611f500148370b5c07362a8d12c6c712c0b9a498ed929b9`. `Setup.ps1` is `3032852c9183c95f991559e3b8d43a0e8b3ab8c60f2138a728a243b38132f6aa`; `scripts/install.py` is `bec6211aa6d21485ac09ab10d8926b082b0763f25e8bab9955fa02150ce69837`. Compare these bytes before reusing these results as current evidence.

Default extraction covers eligible source code only. It preserves existing publications without silently refreshing their scope, requires explicit narrowing above 500 eligible files or two million source words, and cannot create an AST graph for a project with no eligible code/symbols. HTML visualization is limited to 5,000 nodes and uses Graphify's external visualization asset when opened; JSON retains the full graph. Browser rendering, semantic document/image extraction, and the absence of every possible sensitive literal were not established by these checks. Actual process evidence remains in disposable validation artifacts; no live application job or production environment was exercised.

## Historical verification — September 28, 2026

Verified on Windows x64 with Python 3.14 on September 28, 2026 (local date). These results describe this kit revision and temporary synthetic projects. They do not establish application behavior in an arbitrary destination.

## Acceptance evidence

| Requested outcome | Implementation and observed evidence |
|---|---|
| A complete folder that can be copied into other projects | Full payload contains the Codex guidance and six roles, discoverable skill, eleven VS Code tasks, LangGraph runner and tests, AutoGen lab, dependency pins, and guides. Relocation test copied the kit to another path and installed into a separate Git root. |
| One PowerShell setup command | `Setup.ps1` resolves its containing project independently of terminal cwd, runs analysis and installation, then bootstraps both dedicated environments. Real Windows process tests cover spaces and apostrophes in paths. |
| Run a prompt that analyzes and tailors the destination | Actual Codex CLI onboarding returned schema-valid model output in a temporary Python repository. The final source-sampling run cited `inventory.py` and `tests/test_inventory.py`, described direct subtraction and its boundary cases, selected the observed pytest profile, and recorded uncertainty. |
| Preserve existing project configuration | Tests cover existing TOML values, JSONC comments and trailing commas, conflicting task/MCP entries, owned and unowned instruction sections, repeated installation, edited-file conflicts, source changes during analysis, and rollback preserving later edits. |
| Adapt across Windows repository layouts | Discovery tests cover Python, Maven, JavaScript, real nested Git roots, invalid `.git` markers, parent-repository subdirectories, non-Git folders, source sampling, and junction exclusion. Only verified Git roots enter the coordinator registry. |
| Usable installed runner connection | Real stdio MCP initialization using the generated destination configuration exposed all seven engineering tools. Destination repository, role, validation, config and workflow checks passed. A generated synthetic pytest profile executed one test successfully. |

## Automated checks

- Installer/discovery suite: **49 passed**, plus **6 passing subtests**, in 23.70 seconds.
- Full packaged runner suite: **70 passed, 1 skipped**, in 108.75 seconds. The skip concerns a colon in a filename, which Windows forbids. The test harness explicitly imported packaged source and passed its path to MCP subprocesses. Two plugin rewrite warnings came from the harness import order.
- Packaged Python syntax, TOML/YAML/JSON parsing, PowerShell parsing, and local documentation-link checks passed. Generated context/example paths and the optional graph pointer were accounted for explicitly.
- The native PowerShell wrapper installed configuration from a copied kit in a different location. Static rerun made no configuration changes. Conflict and rollback checks used synthetic projects only.
- A dedicated engineering environment was created in the live fixture from the dependency lock; editable package installation and `pip check` passed.
- The full default `Setup.ps1` completed with exit code 0, including a fresh model analysis and both isolated dependency environments. Studio's dependency verification reported no broken requirements.
- AutoGen lab checks: **3 passed**. The installed Studio served its health endpoint, reported version **0.4.2.2**, and served the HTML UI with HTTP 200 on loopback. The owned server process was stopped afterward; this made **zero provider/model calls**.
- Installed `eng.ps1 doctor` was launched from a different working directory and selected the correct destination root.
- Actual default setup with source sampling returned model-derived context. Onboarding did not execute the synthetic application tests; the separate verification step explicitly ran the generated profile afterward and observed **1 passed, 0 skipped**.

## Missing Graphify evidence was reported accurately

The temporary destination had no graph. Its doctor returned exit code 1 with `graph_publication: failed`; all other recorded structural checks passed. Setup did not create a graph, change the result to green, or add a blanket graph exception. A destination needs its own publication or an explicitly accepted, task-specific source fallback before graph-dependent jobs.

For building the kit, the source workspace publication pointer selected `graphify-out/refresh-2026-09-27/graph.json`. A bounded query for `Mandatory Graphify consultation` returned one node and eight adjacent relationships. The workflow source confirmed the consultation and source-verification requirements. A query for `workspace_engineering` returned no matches. The publication predates the runner, so graph evidence for packaging was limited and runner decisions used current source. No graph publication was refreshed or replaced.

## Preservation

The deliverable was added under `engineering-starter-kit`; the original workspace implementation remains in place. A hash comparison of 74 protected original artifacts found no changes at the recorded check. That set included original `.codex`, `.agents`, VS Code configuration, engineering source/docs/config, the outer Git index, root instructions, the graph pointer, and the user Codex config. No original application builds, deployments, migrations, staging, resets, or source edits were performed.

## Practical limits

- Fresh VS Code UI discovery was not exercised. The installed MCP transport was exercised directly. Reload the window and verify skill/tool discovery in a new trusted project session.
- The real onboarding run used a synthetic Python project. Java/JavaScript discovery and profile generation have fixture coverage; no real Java/JavaScript application was built or tested.
- Source sampling is bounded and incomplete by design. Model-generated project context is a reviewable analysis snapshot.
- The Python minimum is declared as 3.11; installation was executed with 3.14 on Windows x64. Other interpreter and machine combinations remain untested.
- AutoGen provider/model calls and paid external APIs were not exercised. Studio requires its own compatible provider configuration for experiments.
- Worker roles retain GPT-6 Astra / ultra. Runtime availability is account-dependent; the onboarding `-Model` flag does not reconfigure worker roles.
- No private/global tools or hooks are copied. Existing tools remain subject to their native discovery, authentication, trust and permissions.
- A final independent review found no new blocking correctness or preservation issue. Its remaining dependency-installation condition was resolved by the successful full setup and Studio checks above.

## Local reproduction

Run the kit tests in an environment containing pytest, then review the resulting generated context and catalog in a disposable Git project:

```powershell
python -B -m pytest .\engineering-starter-kit\tests -q -p no:cacheprovider
.\engineering-starter-kit\Setup.ps1 -ProjectRoot 'C:\Projects\Disposable Example'
```

The installer saves the actual prompt, inventory, model result, planned files, backups and receipt under the destination's `.engineering-state/setup/`. Model failures retain their diagnostics and stop installation. Rerunning without `-Static` performs a new model analysis and can intentionally update generated context.
