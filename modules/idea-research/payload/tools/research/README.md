# Local research tools

Standard library only; see the [operating guide](../../dev-docs/idea-research/operating-guide.md) and [schemas](../../dev-docs/idea-research/schemas.md).

- `init_session.py`: atomic new session, byte copy/hash and initial state; no research execution or completed-index update.
- `render_report.py`: escaped Markdown subset to standalone offline HTML; source/output share a directory.
- `validate_session.py`: structural records/hash/links/offline checks, plus imported attributable AC review; zero exit does not imply acceptance completion.
- `self_check.py`: focused in-memory checks of HTML escaping, unsafe-link blocking, tables/TOC, deterministic rendering, Windows name handling, and HTML runtime-asset detection; an isolated temporary fixture also exercises exact input preservation and distinct session allocation. It makes no network or model calls and removes only its verified temporary fixture under `tools/research/`.

All command writes stay inside this workspace; validation output must stay inside its selected session's `evidenceandlogic/review/` directory. Utilities do not initialize Git, install packages, change settings, browse sources, execute experiments, or publish. Run with the existing engineering Python environment; use `--help` for exact arguments. Browser inspection remains a separate observed check.

When supplied, `run/protected-files.json` is compared against current workspace files using its `files` array of `{path, sha256}` and retained `scope`. Preservation applies only to listed paths. Available original AGENTS/project-context backups under `inputs/setup-backups/` are also compared with current file prefixes. Missing optional baselines/backups are `not_run`, never inferred preservation passes. Authored ID checks include registered IDs, numeric C/S/E/P/N/T and numeric families derived from registered IDs; fenced code and block quotations are excluded from ID scanning.
