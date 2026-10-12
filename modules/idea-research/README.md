# Idea research module

Decide whether an idea deserves its next bounded investment. This optional module adds an evidence-led research workflow, six portable worker assignment templates, report and record templates, and four Python utilities for preserving inputs, allocating sessions, rendering offline reports, and checking artifact structure.

Enable it with `-Modules idea-research` when running the starter kit's `Setup.ps1`. The files are installed under the destination workspace's `.agents/`, `.codex/`, `dev-docs/`, and `tools/research/` directories. The base engineering workflow and Graphify remain available. See the installed [operating guide](payload/dev-docs/idea-research/operating-guide.md), [skill](payload/.agents/skills/idea-research/SKILL.md), and [future invocation](payload/.codex/prompts/research-idea.md).

The tools use Python 3.11+ and the standard library. They do not install dependencies, call a model, start workers, execute experiments, or publish results. Native research workers must be invoked through tools the host actually supports and assigned bounded ownership. These role files do not register native agent types or engineering-coordinator specialist IDs, and a saved native session requires manual reconciliation before continuation.

Graphify's scope and freshness must fit each investigation. A code-only AST graph may not cover the idea document or external research. Source fallback requires a current task-specific authorized exception; a previous session's exception is not reusable permission. Structural validation passing does not establish claim truth, independent review, browser readability, or completion of AC1–AC9.

Only reusable source, templates, and synthetic examples are distributed. Actual inputs, absolute input paths, sessions, diagnostics, and worker results remain local artifacts. Review and sanitize them before any separately authorized publication.
