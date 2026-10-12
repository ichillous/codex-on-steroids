# Audit fixes and recovery behavior

The October 12, 2026 audit identified 15 reproducible problems in setup, durable execution and the optional blueprint tools. This revision addresses all 15 with regression coverage. The table connects each original finding to the resulting behavior; [VERIFICATION.md](VERIFICATION.md) records the checks and their limits.

| Finding | Resulting behavior | Regression coverage |
|---|---|---|
| F01: project Python modules or pip settings could redirect bootstrap | Setup and bootstrap use isolated Python startup. A shared helper controls pip settings, checks environment ownership and verifies genuine package readiness. Unverified or linked environments are preserved and rejected. Explicit offline package sources remain supported. | `test_bootstrap_security.py`, `test_graphify_setup.py` |
| F02: sensitive literals could enter onboarding evidence | Every evidence class is screened before excerpts are retained or a prompt is prepared. Matching files are omitted with a reason. Onboarding disables Codex's automatic project instruction discovery and supplies screened instruction excerpts. | `test_onboarding_security.py` |
| F03: validation could remain accepted after an imported helper changed | Evidence snapshots cover broader checkout source and configuration independently of permitted edits. Represented dependency or catalog changes invalidate worker, validation and review evidence. | `test_coordinator.py`, `test_repository_manager.py` |
| F04: different state directories could claim the same checkout | Journals share a canonical checkout lease authority for the current operating-system account. Identical and overlapping checkout paths cannot gain competing ownership through a different `--state-dir`. | `test_state.py`, `test_coordinator.py` |
| F05: default setup rejected a literal native Codex launcher | A narrowly validated `.cmd`/`.bat` forwarder resolves directly to its outside-project native executable. Wrapper text is never executed to discover the target. | `test_onboarding_security.py`, `test_onboarding.py` |
| F06: retried approvals reused expired identities | Persisted requests and the approval bridge share typed request ID, method, thread and turn correlation. A recovered operation can receive its own decision. | `test_state.py`, `test_worker_runtime.py` |
| F07: `./file` scope caused a false violation | Valid scopes are normalized to repository-relative physical identity before edits and evidence are compared. Equivalent safe dot-relative paths also work in blueprint inputs. | `test_repository_manager.py`, `test_coordinator.py`, `test_blueprint_hardening.py` |
| F08: a prepared receipt could not recover a partial install | Rollback classifies every target against recorded before/after states, restores known applied writes, leaves unwritten targets alone and preserves unknown edits. Each target is checked again before mutation. | `test_install_recovery.py` |
| F09: a validation child survived an exited parent | Windows checks enter an owned Job Object before execution; closing it stops descendants even after the parent exits. POSIX checks use an owned process group. Cleanup also runs when journaling fails and when a check completes normally. | `test_validation_runner.py` |
| F10: malformed reviewer output could become completion | Worker and persisted result objects pass strict nested schemas. Unsupported severities, duplicate JSON keys or criteria, extra fields, missing reviewer criteria and blank evidence are rejected. | `test_coordinator.py`, `test_worker_runtime.py` |
| F11: errors after clicking were omitted | Browser errors are drained after navigation, replay and actions, during a defined settling window and before final context closure. | `test_blueprint_hardening.py`; real synthetic Chromium fixtures |
| F12: a partial audit exited successfully despite aggregate failures | Output distinguishes current observations from aggregate verification. Retained failures or missing coverage for the current blueprint produce a nonzero exit. | `test_blueprint_hardening.py` |
| F13: maps and screenshots could reuse obsolete verification | Browser records bind to source/assets, auditor/helper bytes and selected options. Maps recheck those fingerprints and screenshot hashes; stale or legacy evidence is unverified. | `test_blueprint_hardening.py` |
| F14: blueprint tools could follow links outside their root | Shared path checks contain manifest reads, generated reports, maps, screenshots and served assets. Escaping paths, links, Windows reparse points and hard-linked files are rejected. The HTTP server serves only captured source and the generated map. | `test_blueprint_hardening.py`; actual Windows junction/hard-link fixtures |
| F15: project names could inject HTML | Initializer names are HTML-escaped in generated pages while their original JSON string is retained. | `test_blueprint_hardening.py` |

Test filenames in the table refer to [installer/module tests](tests) or [packaged runtime tests](payload/tools/engineering/tests).

## Upgrade and recovery

Before upgrading a destination installation, stop and reconcile its existing runner jobs using their original tooling and journals. The shared lease authority protects updated same-account runners; it cannot discover arbitrary old-version journals elsewhere. Earlier scoped evidence fingerprints intentionally do not qualify as current broader snapshots. After settling old operations, start a new task for current evidence.

Preserve `.engineering-state` and the account's shared lease database. Inspect status, active processes and current edits before retrying or abandoning an operation. A stopped run with no unsettled operation can explicitly release its leases through `reconcile --run <run-id> --action release --acknowledge-risk`; this retires resumable state and refuses active ownership. See the [operating guide](payload/dev-docs/engineering-automation/operating-guide.md) for the complete commands.

Bootstrap reuses a marked environment that belongs to the selected tooling directory. A compatible earlier kit environment can be reused without mutation only when ownership, dependency inputs and runtime readiness are verified. Unmarked, incomplete or linked environments are preserved for deliberate recovery. Dependency environments and graph publications are outside configuration-receipt rollback.

Validation commands own their descendants only for the check's lifetime. A command that starts a background service must use a separately authorized service lifetime rather than leave that service running after validation.

## Evidence boundaries

Sensitive-literal screening reduces exposure for the tested patterns; it is not a proof that arbitrary source contains no private information. Omitted project instruction files are excluded from the setup prompt. Native account configuration, model selection, user-configured instructions, trust and permission settings remain authoritative and are outside this file-screening contract. Setup is a model analysis with read-only native restrictions, not an operating-system sandbox for arbitrary private files.

Checkout snapshots cover represented source, configuration and Git/catalog identities. Generated/runtime files, installed packages, unselected or nested repositories, external services and arbitrary ignored files have explicit coverage limits. Select relevant repositories and checks for each task; a matching fingerprint alone does not establish application or production acceptance.

Blueprint checks cover their declared pages, options and bounded interactions. The browser settling window is finite. A clean audit does not establish every asynchronous behavior, business state, accessibility requirement or visual decision. The owner still reviews the experience and approves implementation.

The regression suite uses local disposable fixtures. Real Chrome checks exercise synthetic pages; coordinator fixtures use controlled worker responses. No live production job or AutoGen provider comparison was performed for this hardening revision. The checked-in Windows CI matrix supplies repeatable verification; published workflow runs are separate evidence from local results.
