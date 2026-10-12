# Research record schemas

UTF-8 is used throughout; CSV writers should quote fields containing commas/newlines. JSON may use `null` for genuinely unknown dates/versions. An unknown value needs its scope/consequence in the observation or limits. Stable IDs are assigned by the coordinator; `S01`, `C01`, `E01` are recommended. Preserve IDs across revisions within one session and retain old assessments in the review history.

## Sources: `evidenceandlogic/sources.json`

A JSON array. Each object has:

| Field | Meaning |
|---|---|
| `source_id` | Unique stable ID |
| `title`, `publisher` | Human title and original author/publisher |
| `url` or `local_path` | Canonical public http(s) URL, or session-relative retained evidence path; at least one is required |
| `source_type` | Official docs, source, issue, paper, observation, vendor claim, community report, etc. |
| `published_or_updated` | Known date, or null with unknown noted |
| `retrieved_at` | Actual timestamp with offset |
| `version_or_commit` | Relevant version/commit, or null with limit explained |
| `access_status` | `opened`, `inspected_local`, `inaccessible`, `snippet_only`, or another precise status |
| `source_family` | Original evidentiary origin; derivatives share a family |
| `locator` | Exact section/page/line, issue comment, API field, file/commit |
| `observation` | Concise relevant observation, support/contradiction and limits |

`sources.md` supplies a readable index with matching IDs and links. Use simple headings `## S01` when linking to `sources.md#s01`. The source index does not make an inaccessible source verified.

## Claims: `evidenceandlogic/claims.csv`

Exact column order:

```csv
claim_id,claim,origin,importance,evidence_type,assessment,source_ids,experiment_ids,scope_limits,confidence_basis,decision_consequence
```

`origin` identifies the input claim, researcher inference, or new observation. `importance` states the decision consequence or priority. `evidence_type` distinguishes fact, inference, assumption and unknown (with methods when useful). `assessment` is `supported`, `contradicted`, `mixed`, or `unverified`. Multiple IDs use semicolons, such as `S01;S02`. Empty source/experiment lists are allowed for unverified claims; other assessed claims need evidence. Scope/version limits and confidence basis are mandatory. The validator checks references, not whether the cited source proves the claim.

## Experiments: `evidenceandlogic/experiments/<id-or-name>/record.json`

Required fields: `experiment_id`, `status`, `kind`, `hypothesis`, `linked_claims` (array), `protocol`, `environment`, `commands`, `observations`, `result`, `limitations`, `reproduction`.

- `status`: `executed`, `partial`, or `not_run`. A proposed test is `not_run` with a concrete `reason` or `limitations`; it is never an executed success.
- `kind`: source inspection, synthetic fixture, mocked integration, technical smoke test, proxy measurement, actual harness integration, or repeated effectiveness trial. State exact scope.
- `protocol`: hypothesis, baseline/treatment, controlled variables, measures, success/failure interpretation, expected writes/network/dependencies and stopping rule, recorded before execution. Structured object or a preserved protocol path with concise description is acceptable.
- `environment`: OS/runtime/dependency versions or commits, harness/model/settings, sample size, seeds where available and clock basis. State unknowns.
- `commands`: exact commands with cwd/effects; `observations`: actual outputs, errors, elapsed time and artifacts. Arrays or structured objects are preferred; `not_run` may use empty arrays.
- `result`: observed conclusion or explicit untested status. `limitations`: sample, measurement, detection limits, proxy boundaries, or why blocked. `reproduction`: exact script/command and dependency requirements. Resolve local artifact links in companion Markdown.

Additional fields such as `started_at`, `finished_at`, `scripts`, `log_paths`, `metrics`, `reason`, `versions`, `expected_writes`, and `network_effects` are encouraged where useful. Do not claim an exact compaction diff from a recall proxy, zero latency from an underpowered test, or demand from a technical result.

## Decision: `evidenceandlogic/decision-record.md`

State one outcome (`PROCEED TO NEXT TEST`, `PIVOT`, `STOP`, `INSUFFICIENT EVIDENCE`), next investment, decisive claim IDs, strongest opposing evidence, assumptions, unresolved questions, confidence basis and what new evidence would change the recommendation. Link the sources/experiments. Explain original and revised numerical criteria separately.

## Session: `run/session.json`

Required working fields: `session_id`, `idea_name`, `created_at`, `timezone`, `input_path`, `input_sha256`, `scope`, `route`, `route_reason`, `model`, `workers` (array), `completed_checks` (array), `blocked_items` (array), `next_resume_action`, `status`.

Record actual `tools`, effective effort, run IDs when available, graph status/exception, status reason, milestone/completion timestamps and selected limits. Worker entries identify the actual native ID, assignment, owned outputs, start/end/status, model inheritance or verified selection, and evidence. Use `in_progress`, `complete`, `incomplete`, `blocked` with a reason. Initial empty worker/check arrays are accurate only before work. Native route notes do not imply a durable coordinator run.

`run/state.md` gives a readable current checkpoint: completed milestones, active/uncertain operations, unresolved blockers, ownership, files to read and next safe action. Update both records after meaningful milestones and before handoff.

## Independent review and acceptance

The reviewer saves an attributable `independent-review.md` with round, reviewed artifacts/hashes, findings, evidence and criterion statuses. The coordinator may summarize actual outcomes in `acceptance-review.json`:

```json
{
  "reviewer": "actual agent identity; distinguish coordinator compilation",
  "reviewed_at": "actual ISO timestamp with offset",
  "criteria": [
    {
      "id": "AC1",
      "status": "pass",
      "detail": "Concrete evidence-based assessment, including limits",
      "evidence": ["evidenceandlogic/agent-results/setup-result.md", "run/doctor-live.json"]
    }
  ]
}
```

Include all AC1-AC9; missing ones remain `not_run`. Allowed statuses are `pass`, `fail`, `not_run`. A pass needs existing evidence paths and a concrete detail. Workspace-relative evidence can be reached with relative `..` segments when necessary, but outputs must stay inside the session. Record visual check status and limitation explicitly within AC8. Assertions in this JSON remain attributable assessments; their presence is not independent proof.

`validation-results.json` is generated: `schema_version`, `validated_at`, `session`, `structural_status`, `checks` array, `acceptance_criteria`, `acceptance_status`, and `limitations`. Each structural check has `id`, `status`, `detail`, `errors`. Its final state must correspond to final report/records. A later change requires rerunning affected checks and possibly review.

## Standard session layout

```text
Ideas/<safe-name>/README.md
Ideas/<safe-name>/sessions/<timestamp_random>/
  inputs/idea-original.md
  report/summary.md
  report/report.md
  report/report.html
  report/next-steps.md
  evidenceandlogic/sources.json
  evidenceandlogic/sources.md
  evidenceandlogic/claims.csv
  evidenceandlogic/hypotheses.md
  evidenceandlogic/competitors.md
  evidenceandlogic/users-and-adoption.md
  evidenceandlogic/strategy-and-scenarios.md
  evidenceandlogic/assumptions-and-unknowns.md
  evidenceandlogic/case-for.md
  evidenceandlogic/case-against.md
  evidenceandlogic/disagreements.md
  evidenceandlogic/search-log.md
  evidenceandlogic/decision-record.md
  evidenceandlogic/experiments/<experiment>/record.json
  evidenceandlogic/agent-results/<assignment>.md
  evidenceandlogic/review/independent-review.md
  evidenceandlogic/review/acceptance-review.json
  evidenceandlogic/review/validation-results.json
  run/session.json
  run/state.md
```

Save real explanations and justified not-applicable results, not empty filler. Keep report/evidence separation. Original input, diagnostics and raw relevant evidence retain provenance. Do not save private internal chain-of-thought, secrets, or unrelated transcripts.
