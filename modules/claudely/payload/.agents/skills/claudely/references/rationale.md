# Research rationale and compatibility

Research access date: **2026-10-12**. This skill expresses original workflow guidance adapted from primary sources. Mutable documentation describes the fetched contract, not every installed client. Vendor advice and case studies support the design; they do not prove a measured improvement in Codex or modify its underlying model.

## Practices selected

| Practice | Primary evidence | Adaptation and limit |
|---|---|---|
| Observable checks and proportional planning | [Claude Code best practices](https://code.claude.com/docs/en/best-practices) | Select a meaningful check and use planning for uncertainty; do not add approval gates or automatic commits |
| Focused reproduction and incremental changes | [Claude common workflows](https://code.claude.com/docs/en/common-workflows) | Match project conventions and verify the reported behavior; avoid tests that only mirror implementation |
| Context loaded on demand | [Anthropic context engineering, 2025-09-29](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Retain references and compact decisions; retrieval and notes also have costs |
| Concise persistent instructions | [Claude instruction and memory guidance](https://code.claude.com/docs/en/memory) | Use the existing Codex instruction route; do not import auto-memory permissions or Claude syntax |
| Investigation and review in separate contexts | [Claude subagents](https://code.claude.com/docs/en/sub-agents), [review guidance](https://code.claude.com/docs/en/best-practices) | Delegate when valuable and supported; request material findings, allow none, and state context/isolation limits |
| Behavior-preserving clarity pass | [Anthropic's public code-simplifier prompt](https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/code-simplifier/agents/code-simplifier.md) | Refine only authorized touched code; retain project conventions and behavior, omit its fixed model/style choices |
| Incremental completion and handoffs | [Long-running harness, 2025-11-26](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Retain state and unmet criteria; do not copy broad initialization, feature expansion, or Git operations |
| Complexity justified by outcomes | [Building effective agents, 2024-12-19](https://www.anthropic.com/engineering/building-effective-agents) | Keep the procedure small; additional agents, notes, and checks cost time and tokens |

## Native Codex mapping

- **Discovery:** `.agents/skills/claudely/SKILL.md` supplies `name` and `description`; its body loads when selected. UI metadata is in `agents/openai.yaml`. Normal implicit selection remains enabled; explicit invocation uses `$claudely` or the host's skill picker. [Codex skills](https://learn.chatgpt.com/docs/build-skills)
- **Instructions:** Follow the applicable `AGENTS.override.md`/`AGENTS.md` chain and configured project route. `CLAUDE.md` is not a default filename in that documented chain. [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- **Delegation:** Use the collaboration API exposed in the active session. Codex supports subagents; custom definitions use Codex TOML rather than Claude agent Markdown. Separate contexts inherit the host's live permission controls and do not establish independent checkout ownership. [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- **Hooks:** Current Codex documentation supports native lifecycle hooks with reviewed, hash-bound trust. A prompt instruction to check the work is not such a hook. This skill does not install, configure, trust, or fire handlers. [Codex hooks](https://learn.chatgpt.com/docs/hooks), [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- **Recovery:** Codex supports session resume and worktrees, but worktrees require Git and transcript resume is not proof of safe replay of unsettled operations. This skill does not create worktrees or restore files. [Codex worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees), [non-interactive resume](https://learn.chatgpt.com/docs/non-interactive-mode)

Prompt guidance, native mechanisms, executable runner behavior, and observed validation are separate evidence layers. Preserve the current task's authorization and the runner's own requirements when using any of them.

## Evidence limits and future evaluation

Anthropic's [March 2026 application harness case study](https://www.anthropic.com/engineering/harness-design-long-running-apps) reports a solo example at 20 minutes/$9 and a full harness at six hours/$200, with expanded feature scope. It does not establish an identical-scope comparison or Codex benefit. Model-specific reset behavior changed within that work, so this skill requires no forced resets.

Structural validation can establish frontmatter and packaging correctness. Scoped forward tests can show how an agent handled the supplied tasks. Fresh-session discovery and implicit selection require an actual client observation. None alone establishes better productivity, fewer defects across projects, or model self-improvement. A meaningful later comparison would use equivalent tasks, source state, scope, and acceptance criteria, and record criterion completion, rework, preserved user work, runtime, and tool/agent overhead.
