# Agent routing and evidence handoffs

Keep one coordinator responsible for the user outcome, authorized scope, acceptance criteria, ownership, integration, and final evidence. Choose the smallest useful route; separate agents help when their questions are independent or a consequential change benefits from another reviewer. Existing repository instructions, task authorization, and effective host permissions control every route.

This guide adapts selected `ai-agents-architect` and `ai-team-orchestration` principles to the kit's existing roles and runner. It supplies decision guidance; the active host and executable runner establish which tools, roles, limits, and recovery operations actually work.

## Choose the evidence before the tool

| Request | Route and boundary |
|---|---|
| Explain source behavior or assess a source-repository architecture | Consult the designated Graphify publication, then verify relevant source and callers. Use an investigator when a separate read-heavy question helps. Artifact tools are unnecessary when source answers the question. |
| Design or improve an agent system | Assess task decomposition, tool contracts, bounded failures, selective context, observability, and recovery. Use installed architecture/orchestration skills when relevant; their prose does not create native roles or execution guarantees. |
| Implement or debug a scoped change | The coordinator can own a narrow change directly; use the existing implementer role when delegation helps. Select the smallest meaningful check. If installed, claudely can guide proportional planning, focused context, completion checks, and selective review. |
| Explain a shipped artifact, compare packaged versions, or obtain requested runtime evidence | If installed, reverse-engineer-anything guides REA for the supplied named target. Check the host's actual tools and schemas; a skill's version or tool count does not establish runtime availability. Acquiring providers, registering MCP, repairing configuration, and executing a target have separate effects and need task authorization covering them. |
| Run a durable engineering job | Start the configured runner explicitly with its supported task schema, repositories, roles, and registered checks. A skill or role name in a prompt does not start or extend the runner. |

Optional skill folders are installed only when selected. Their absence is not a reason to install them or change global configuration during an unrelated task. REA's artifact graph complements its own observations; it does not replace the project's required Graphify publication or prove runtime execution from static analysis.

## Map responsibilities to existing roles

- **Producer/coordinator (`@ai-team-producer` responsibility alias):** own the brief, decisions, agent assignments, acceptance, and integration. Avoid a second supervisor over the same task or checkout.
- **Dev (`@ai-team-dev` responsibility alias):** use the existing implementer, with investigators and relevant Oracle, UI, or integration specialists for bounded questions. Assign explicit file/checkout ownership; agents may share files even when their context differs.
- **QA/review (`@ai-team-qa` responsibility alias):** use the reviewer and, when relevant, the UI specialist plus declared behavioral checks. Add independent QA when its evidence is useful. These aliases are not registered native agent type IDs.

Keep the destination's selected models, supported tools, native approval controls, and configured worker/revision limits. Interpret three-role team advice as responsibilities, not a requirement to replace the kit's native definitions or supported specialist IDs. Do not introduce fixed tool-count limits, private thought logging, automatic commits/PR merges, or global memory writes.

## Hand off a compact evidence packet

Give each worker the outcome and criteria, explicit scope/allowed actions, owned paths, relevant evidence, expected output, and stopping conditions. Its result should retain:

- Source repository/path and fingerprint, or artifact path/version and digest.
- Observation or Evidence reference, evidence type, command/tool, and actual result.
- Coverage and freshness, inferences, unresolved criteria, and the next check or action.
- Changed/preserved files and active worker/process/approval state when continuation needs them.

Record public tool/results evidence and concise decision explanations. Do not request or store private reasoning. Preserve detailed authorized evidence in its existing task record and return a focused summary; avoid a second competing project-state corpus.

## Recover according to what actually stopped

A conversation handoff restores context; a native transcript resume continues a session; a runner checkpoint restores its recorded state. None alone stops old workers or makes replay safe. Inspect current source, indexes, pending approvals, active processes, and unsettled operations before continuing. The configured runner's reconcile/cancel/ownership rules apply to its jobs; native perspective passes do not gain those guarantees from prose.

A missing tool, disconnected server, unavailable engine, policy rejection, and stale artifact are different gaps. Continue useful supported work, name the blocked observation, and repair only the authorized cause. Do not repeatedly run readiness or provider setup before ordinary analysis.

Use [the operating guide](operating-guide.md) for runner acceptance and recovery procedures, and [the portable guide](portable-guide.md) for installation and route selection.
