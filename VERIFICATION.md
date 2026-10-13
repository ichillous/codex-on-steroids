# Portable kit verification

## REA module and agent routing — October 13, 2026

The optional `reverse-engineer-anything` module preserves seven local skill/reference files and adds the exact upstream MIT license plus a source manifest inside the installed skill folder. The source pin is morluto/rea `a56f7bb668ab23fec8d33f7af353ac7ed2fe1895`, the gitHead recorded for npm 6.4.0. Six references match that source exactly; the entrypoint matches its documented metadata/version-pin generation transformations. Local installation origin and npm tarball parity were not established. The new base routing guide maps producer/dev/QA responsibilities to existing roles and separates source/artifact evidence, native capabilities, and durable-runner recovery.

- Focused REA, claudely, optional-module and recovery checks: **44 passed**, in 18.86 seconds. Seven new REA tests exercise the shipped payload, default exclusion, repeat selection/idempotence, coexistence with all three older modules, independent folder preservation without attribution overlays, edited owned-file conflicts, receipt rollback/reinstall, provenance hashes, and PowerShell module forwarding.
- Full installer suite: **242 passed, 1 skipped, 6 passing subtests**, in 66.03 seconds, using Windows x64, Python 3.14.7 and pytest 9.1.1. The skip is `test_graphify_setup.py:136`, where Windows symlink creation is unavailable. Command: `python -B -m pytest tests -q -p no:cacheprovider -rs` from the kit root. These package checks do not establish REA behavior.
- Seven actual relocated `Setup.ps1` calls used `-Static -SkipDependencies -SkipStudio` in a disposable non-Git destination. Claudely installed in **80 changed files**; the incremental REA addition made **11 changes**; an unflagged repeat made **zero changes**. Incremental rollback removed REA including its attribution, retained all four claudely hashes, and permitted reinstallation. Final rollback restored all five original synthetic owner files byte for byte. No model, REA, provider, download, target-execution or bootstrap call was made by the smoke.
- Local and packaged REA originals matched across **7/7 files**, and claudely remained unchanged across **4/4 files**. License identity is 1064 bytes, SHA-256 `798f9e4d18e49b30bf2f12696c8ced73dc4e1413da375a333d01281543a1ea8b`. Literal module/guide local links, Python syntax, and `git diff --check` passed. Existing source/index baselines and the limited Jano publication were preserved.

This addition installs instructions and attribution only. REA MCP registration, engines, tool availability, native runtime evidence and fresh-host discovery remain separate prerequisites or untested outcomes. The packaged runner and AutoGen suites were not rerun because their source/configuration did not change. No global architecture/team skill was copied, and no native roles, models, tools, policies, approval settings, memory behavior or runner schema were changed.

## Claudely module — October 12, 2026

The optional `claudely` module supplies the same four skill files as the researched workspace skill: entrypoint, UI metadata, examples, and source rationale. It uses the existing module installer and receipt rollback without changing their preservation algorithms. Installation alone does not establish native skill routing or measured improvement in Codex.

- Focused claudely, optional-module and install-recovery suite: **37 passed**, in 15.97 seconds. Six new cases use the shipped payload to verify default exclusion, byte-exact installation, selection retention and repeat idempotence, independent skill preservation without partial overlays, refusal to overwrite locally edited owned files, incremental/full rollback and reinstall, and PowerShell argument forwarding.
- Full installer suite: **235 passed, 1 skipped, 6 passing subtests**, in 77.95 seconds. Run with `python -B -m pytest tests -q -p no:cacheprovider` from the toolkit root, using an existing environment containing pytest. This check used Windows x64, Python 3.14.7 and pytest 9.1.1. The packaged runner and separate AutoGen suites were not rerun for this skill addition.
- Seven actual relocated `Setup.ps1` calls used a disposable non-Git project and paths with spaces and an apostrophe. Static configuration-only setup installed the base, added claudely in six file changes, repeated without module flags with **zero changed files**, rolled back the incremental addition, reinstalled it, then rolled back both additions and the base. All five original instruction, ignore, application and project-configuration files were restored byte for byte. Model calls, downloads, Graphify preparation and environment bootstrap were skipped explicitly using `-Static -SkipDependencies -SkipStudio`.
- Live and packaged skill contents matched byte for byte across all four files; the module's literal local Markdown links resolved. Unrelated baseline files and the kit's Git index stayed unchanged. `git diff --check` passed. The pre-existing Jano graph does not represent these targets; consultation was limited and no publication was refreshed.

Fresh-host/client discovery, implicit selection, native hook events, and productivity gains remain untested by these package checks. The module configures no hooks, providers, permissions, models, global instructions, worktrees, or durable runner. Receipt rollback retains setup evidence/environments, may leave empty directories, and refuses to replace later edits. Preserve the actual incremental receipt to remove just that addition.

## Audit hardening — October 12, 2026

This revision implements the 15 findings documented in [HARDENING.md](HARDENING.md). The results below concern the integrated kit on Windows x64 with Python 3.14.7. The older sections are historical records; their source hashes do not describe the hardened revision.

| Check | Observed result |
|---|---|
| Integrated installer, Graphify, optional modules and packaged runner/MCP suite | **290 passed, 2 skipped, 6 passing subtests**, in 332.07 seconds. |
| Final bootstrap/Graphify slice after preserving explicit offline pip settings | **51 passed, 1 skipped**, in 17.23 seconds; 10 relevant input hashes were stable throughout. This overlaps the integrated suite and is not an additional 51 unique tests. |
| AutoGen export and usage-accounting component checks | **3 passed**, in 2.49 seconds, using the existing separate Studio environment and the current packaged test source. No provider/model calls. |
| Actual PowerShell install, rerun, receipt rollback and reinstall | Both optional modules installed into a disposable Git project. Initial install made 118 changes and managed 117 files; rerun made zero changes. Rollback restored all eight original fixture files and removed created managed paths. Reinstall passed. Staged index, unstaged application source, untracked notes and owner configuration were preserved. |
| Actual current browser auditor in headless Chrome | With existing Node 24.21.0 and a temporary Playwright 1.64.0 SDK, Chromium 155 rendered a synthetic page at two widths and recorded two screenshots plus a visible button transition. The clean page exited zero. A page throwing 100 ms after a click exited one and recorded the error. The current map builder accepted the fresh clean artifact. |
| Source review | An independent reviewer inspected all 15 fixes, integrated source, recovery behavior and attributable fixture evidence. No unresolved blocking finding remained. |

The integrated suite started before the final small offline-pip-policy follow-up; the final affected slice verifies that follow-up against the integrated source. The two full-suite skips were unavailable Windows symlink creation and a colon-containing filename that Windows forbids. Actual Windows junction and hard-link cases passed. Controlled worker responses exercise the real local coordinator/checkpoint/Git code without a model call. Tests redirect shared lease authority into disposable directories rather than mutate the account's live lease database.

Python, JSON, TOML, YAML, SVG, PowerShell and JavaScript parsing passed. Literal documentation links resolve apart from four paths deliberately generated or supplied in a destination project: project context, the example task and two graph-pointer references. Publication review found no personal home/workspace paths, personal contact information or credential-token matches in the reusable source. Synthetic credential markers remain in regression fixtures. Local inputs, journals, detailed logs, browser profiles and environments are outside the published kit.

The 47 protected original workspace artifacts, including the designated Graphify pointer, were preserved. That publication covers a different project: consultation was **limited**, with no matching toolkit symbols. Fixes were verified in current source and disposable fixtures; no graph publication was replaced.

The [CI workflow](.github/workflows/verify.yml) runs the same core suite on Windows with Python 3.11 and 3.14 plus isolated AutoGen readiness and component checks. Workflow configuration and observed hosted results are separate evidence; see the hosted follow-up below.

These checks did not run a new paid onboarding turn, a live production engineering job, an AutoGen provider experiment or a complete owner-approved product blueprint. Browser fixtures establish the auditor's bounded interaction/error behavior, not production visual quality or comprehensive business-state coverage. The local static setup lifecycle deliberately skipped dependency downloads; hosted CI provides the fresh installation evidence described below. A compatible prior kit environment is reused without mutation only after ownership/dependency/runtime verification.

### Hosted CI and Studio compatibility follow-up

The [initial hosted run](https://github.com/ichillous/codex-on-steroids/actions/runs/38311034247) checked hardening commit `b6afd56afd6ad04eb73a3f053f94a110880580a3` on fresh Windows environments. Both Python 3.11 and 3.14 installed the core lock, passed `pip check`, and passed **291 tests, 1 skip and 6 subtests**. Durations were 160.70 and 164.89 seconds respectively. The remaining skip is the colon-containing filename Windows forbids; Windows symlink tests executed in CI. Python 3.14 also installed the Studio lock and passed its three component checks.

That run exposed two older Studio pins incompatible with Python 3.11: `audioop-lts==0.2.2` requires Python 3.13+, and `numpy==2.5.3` requires 3.12+. The corrected lock selects the audio backport only for Python 3.13+ and pins NumPy 2.4.6 across the supported minors. Bootstrap now evaluates a bounded set of single `python_version` comparisons, rejects conflicting active pins, and checks the target interpreter's actual minor before installation. Pip and readiness use a shared snapshot of lock bytes; a changed source lock prevents a readiness claim.

The integrated follow-up slice passed **89 tests, 1 existing symlink skip**, in 16.17 seconds, with six input hashes stable through execution. Four local preservation cases executed real disposable venv interpreters with deliberately stale `pyvenv.cfg` declarations and a simulated different selected minor; they verify rejection and preservation, rather than successful installation on four local interpreters. Primary package-index metadata confirms compatible active pins, dependency closure and Windows x64 wheels for both locks on Python 3.11–3.14. Metadata is separate from installation evidence.

The follow-up CI step additionally runs Studio `pip check` and isolated imports of Studio, AutoGen Core, AgentChat and the OpenAI adapter before its component tests. Consult the [published workflow runs](https://github.com/ichillous/codex-on-steroids/actions/workflows/verify.yml) for the final fresh-install outcomes. No provider/model experiment is part of these checks.

Selected SHA-256 bindings for the delivered source, including the locally tested compatibility follow-up:

| File | SHA-256 |
|---|---|
| `Setup.ps1` | `97a29480c5b7608d0048a77b09bd96f63b1634628681d3fae171fc92f7af3f9b` |
| `scripts/install.py` | `17256018bbefef5e39bf41e4289cd33e3a317fee1ade643b3fd68baa24372e5c` |
| `scripts/onboarding.py` | `4d45dfaa5683804caaa2fb85f0350a27078695d4b7faed844148ee00d2a73c13` |
| `payload/tools/engineering/bootstrap_runtime.py` | `4b95fd33deaf773dd6106fa0dcc00f289e6363ec2d868fc3e566ef535cc2f289` |
| Studio `requirements.lock` | `3cc192f06d2208794582236c4fc260136e104b3cfc74e5b036d16abd9a9cc265` |
| `payload/tools/engineering/graphify_setup.py` | `5fee85b1fe549a22abe9f401b2d2242b74ba4d0503285b0133c1cdbed21c2653` |
| `workspace_engineering/coordinator.py` | `dfa7cce3e59094af145be70e1d7eeaa6dffe7f0d9b5d18463a718365c49ea39f` |
| `workspace_engineering/state.py` | `a54b86c26ade0ff725a2319cc4ab324f3b424d02124629ca4fae3f6c60ae8f05` |
| `workspace_engineering/process_tree.py` | `7aa80d25e5f4d6f3696a29e99deb586333ac3fa20778f4875869774e31986daa` |
| `workspace_engineering/validation_runner.py` | `1a46873396696a3ca6cc5571b506b5d3cfb30a6e794fdead0d4eb9b286d7ddec` |
| Blueprint `browser_audit.cjs` | `88b9afc365ae25fbdb7c8fb400f53878c960a76a1b27194e543cb746fa71adaa` |
| Blueprint `blueprint_safety.cjs` | `19f48f0af837515a7212a927ce5357abcbe1b138f0bb15a5e1aa8c2927b4a333` |

Runtime files above are under `payload/tools/engineering/src/`; blueprint scripts are under `modules/blueprint-first/payload/.agents/skills/blueprint-first/scripts/`; the Studio lock is under `payload/tools/engineering/experiments/autogen/`. The initial 290-test run and 51-test slice used bootstrap helper hash `7360ee0a32bf98bc7b48829722315979631625cfc9dc73e50c285c77eb75a32a`; the 89-test follow-up binds its current hash above. Compare exact bytes before reusing these results. Full logs and complete source manifests remain in local disposable validation artifacts.

## Optional research and blueprint modules — October 12, 2026

This revision adds opt-in source bundles for `idea-research` and `blueprint-first`. The core engineering/Graphify installation remains the default. `Setup.ps1 -Modules idea-research,blueprint-first` forwards repeatable installer selections, and the ownership manifest retains previous selections on reruns. Module files use the same conflict detection, backups, receipts and rollback as the base payload.

- Full installer/discovery/Graphify/wrapper/module suite: **120 passed, 1 skipped, 6 passing subtests**, in 28.84 seconds. Run with the existing engineering test environment using `python -B -m pytest tests -q -p no:cacheprovider --basetemp <disposable-directory>` from the toolkit root. The skip concerns Windows symlink creation permissions; the real Windows junction cases passed.
- New optional-installer cases cover default exclusion, opt-in installation, persisted selections, independently owned skills, unowned and edited-file conflicts, unknown module IDs, missing packages, payload overlap, linked package/destination/project roots, rollback and subsequent reinstall. Windows link detection now uses `lstat()` so junction attributes are inspected before following the destination.
- A real copied-kit PowerShell check used a disposable Git project and paths containing spaces and an apostrophe. Five actual `Setup.ps1` invocations installed both modules with `-Static -SkipDependencies`, reran without module flags, rolled back the latest receipt and initial installation, then reinstalled both modules. The rerun retained both selections and 23 skill/tool file hashes. Original owner instructions were restored by rollback; application bytes and the Git index were preserved. This made **zero model calls and zero dependency downloads**.
- The installed research `self_check.py` passed **nine focused checks**, including escaped offline HTML, unsafe-link rejection, deterministic rendering, exact input preservation, distinct session allocation, and explicitly unset graph exceptions/completion state. It exercised synthetic local inputs only, with no research workers or external investigation.
- Three utility tests exercise relocated research tools and the actual packaged blueprint initializer/checker/map. Untouched starter pages deliberately fail the structure check; map generation succeeds. Initializing into a folder with an existing page but no manifest fails while preserving its bytes. Additional direct fixtures covered all seven starter-file collisions and Windows junction destinations/ancestors.
- The module payloads contain **24 research files and 17 blueprint files**, plus their module READMEs. Python syntax, JSON parsing and JavaScript syntax checks passed. All 17 literal module-document links resolve against the combined installed payload. Historical session/workspace details were generalized; actual input/session files, diagnostics, environments and graphs were excluded. Privacy review applies to the reusable source being published.
- The workspace's designated Graphify publication covers another project. Bounded queries returned no module/installer matches, so consultation was **limited** and consequential packaging decisions were checked in current source. The existing publication pointer and the 42 protected source/workflow/guide files remained unchanged.

Reviewed installer SHA-256: `12f9534a27b9d31c1da2d5e6d7027730efbdee3a552b282d7a0d8cd2dd119884`; `Setup.ps1`: `d46b682a3a53ad03cae5f6a27a0962378ca622d10d812f7fe24e681213dbc479`; module installer tests: `617818cbba331d72f12793e0e267096a10723e0182e26a9e5ad5265af35da639`; utility tests: `43cd6f1f411ad4cc0a997e8e3b6b0b62ccf4f1fe176ecb3dcf334a317441db7f`; blueprint initializer: `f1c20facf23b11c625e728c65e8dbbe9818b162ce4dccf2112ddc8eff1401f8d`. Compare these bytes before reusing the evidence.

The optional browser audit was syntax-checked but not executed against a browser. No complete research investigation, native research-worker dispatch, owner-approved product blueprint, or production engineering job was exercised. Structural utility checks do not establish research acceptance or visual quality. Node, Playwright and browser dependencies remain separately supplied prerequisites for that optional audit. Research inputs, absolute input paths and reports generated later can contain private information and need their own review before publication.

## Graphify setup addition — October 12, 2026

The Graphify addition installs/reuses pinned tooling and prepares a missing real code-only publication during default setup. These results describe its verification before the optional modules above were added. The September 28 results below describe the earlier kit, which only detected Graphify evidence; its missing-graph setup behavior is historical and is superseded by this addition.

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
