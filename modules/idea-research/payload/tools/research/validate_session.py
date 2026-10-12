"""Validate local research artifacts without making factual/review claims.

Reads session files and original input; optional --output writes one JSON result.
Zero exit means executed structural checks passed. not_run acceptance checks
remain incomplete. This utility does not browse, run experiments or start agents.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from render_report import LINK, render_document, render_markdown, safe_url

WORKSPACE = Path(__file__).resolve().parents[2]
REQUIRED = [
    "inputs/idea-original.md", "report/summary.md", "report/report.md", "report/report.html", "report/next-steps.md",
    "evidenceandlogic/sources.json", "evidenceandlogic/sources.md", "evidenceandlogic/claims.csv",
    "evidenceandlogic/hypotheses.md", "evidenceandlogic/competitors.md", "evidenceandlogic/users-and-adoption.md",
    "evidenceandlogic/strategy-and-scenarios.md", "evidenceandlogic/assumptions-and-unknowns.md",
    "evidenceandlogic/case-for.md", "evidenceandlogic/case-against.md", "evidenceandlogic/disagreements.md",
    "evidenceandlogic/search-log.md", "evidenceandlogic/decision-record.md",
    "evidenceandlogic/review/independent-review.md", "run/session.json", "run/state.md",
]
SOURCE_FIELDS = {"source_id", "title", "publisher", "source_type", "published_or_updated", "retrieved_at", "version_or_commit", "access_status", "source_family", "locator", "observation"}
CLAIM_FIELDS = ["claim_id", "claim", "origin", "importance", "evidence_type", "assessment", "source_ids", "experiment_ids", "scope_limits", "confidence_basis", "decision_consequence"]
EXPERIMENT_FIELDS = {"experiment_id", "status", "kind", "hypothesis", "linked_claims", "protocol", "environment", "commands", "observations", "result", "limitations", "reproduction"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files_check(workspace: Path, manifest_path: Path) -> dict:
    """Compare only paths actually recorded by the coordinator's baseline."""
    result = {"id": "protected-files-baseline", "status": "not_run", "detail": "No protected-files manifest supplied; unrelated-file preservation was not checked.", "errors": [], "checked_count": 0}
    if not manifest_path.is_file():
        return result
    errors = result["errors"]
    try:
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list) or not manifest["files"]:
            raise ValueError("Protected-files manifest requires a nonempty files array")
        scope = manifest.get("scope", "Scope not stated in manifest")
        seen = set()
        for entry in manifest["files"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"]:
                errors.append("Invalid protected-file entry: nonempty path required")
                continue
            relative = Path(entry["path"])
            target = (workspace / relative).resolve()
            identity = str(target).casefold()
            if relative.is_absolute() or not target.is_relative_to(workspace):
                errors.append(f"Protected-file path is not workspace-relative: {entry['path']}")
                continue
            if identity in seen:
                errors.append(f"Duplicate protected-file path: {entry['path']}")
                continue
            seen.add(identity)
            expected = entry.get("sha256", "")
            if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
                errors.append(f"Invalid baseline SHA-256: {entry['path']}")
                continue
            if not target.is_file():
                errors.append(f"Protected file missing: {entry['path']}")
                continue
            result["checked_count"] += 1
            if hash_file(target) != expected.lower():
                errors.append(f"Protected file changed: {entry['path']}")
        result["manifest_scope"] = scope
        result["manifest_sha256"] = hash_file(manifest_path)
        result["detail"] = f"Compared {result['checked_count']} listed files against recorded SHA-256. Manifest scope: {scope}. No preservation claim is made for excluded, unrecorded or newly created files."
    except (OSError, ValueError, TypeError) as exc:
        errors.append(str(exc))
        result["detail"] = "Could not completely validate the supplied protected-files baseline."
    result["status"] = "fail" if errors else "pass"
    return result


def setup_prefix_check(workspace: Path, backup_dir: Path) -> dict:
    """Check available original-byte backups without inferring absent baselines."""
    result = {"id": "setup-original-prefixes", "status": "not_run", "detail": "No known setup backups supplied; original-prefix preservation was not checked.", "errors": [], "files": []}
    pairs = (("AGENTS.md.original", "AGENTS.md"), ("project-context.md.original", ".codex/project-context.md"))
    for backup_name, relative in pairs:
        backup = backup_dir / backup_name
        if not backup.is_file():
            continue
        target = (workspace / relative).resolve()
        try:
            if not target.is_relative_to(workspace):
                raise ValueError(f"Setup target resolves outside workspace: {relative}")
            before = backup.read_bytes()
            after = target.read_bytes()
            matched = bool(before) and after.startswith(before)
            result["files"].append({"path": relative, "backup": backup_name, "backup_sha256": hashlib.sha256(before).hexdigest(), "current_sha256": hashlib.sha256(after).hexdigest(), "original_bytes": len(before), "prefix_matches": matched})
            if not matched:
                result["errors"].append(f"Original backup is empty or no longer a byte-for-byte prefix: {relative}")
        except (OSError, ValueError) as exc:
            result["errors"].append(str(exc))
    if result["files"] or result["errors"]:
        result["status"] = "fail" if result["errors"] else "pass"
        result["detail"] = f"Checked {len(result['files'])} available setup backups against current file prefixes. This verifies the saved backup bytes; it does not establish provenance for missing or unrecorded backups."
    return result


class HTMLAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.runtime_assets: list[str] = []
        self.meta: dict[str, str] = {}
        self.scripts = 0
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta" and attrs.get("name"):
            self.meta[attrs["name"]] = attrs.get("content", "")
        if tag == "script":
            self.scripts += 1
        for key in ("src", "srcset", "poster", "data"):
            if attrs.get(key):
                self.runtime_assets.append(attrs[key])
        if tag == "link" and attrs.get("href"):
            self.runtime_assets.append(attrs["href"])
        if any(name.lower().startswith("on") for name in attrs):
            self.runtime_assets.append("inline event handler")
        if tag in {"iframe", "object", "embed", "base"}:
            self.runtime_assets.append("active element: " + tag)
        if tag == "style":
            self.in_style = True
        if attrs.get("style") and re.search(r"url\s*\(|@import", attrs["style"], re.I):
            self.runtime_assets.append("CSS resource")

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style and re.search(r"url\s*\(|@import", data, re.I):
            self.runtime_assets.append("CSS resource")


def without_fences(text: str) -> str:
    return re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", text)


def identifier_references(content: str, known_ids: set[str]) -> set[str]:
    """Find authored ID references, excluding code fences and quoted source."""
    content = without_fences(content)
    content = "\n".join(line for line in content.splitlines() if not line.lstrip().startswith(">"))
    prefixes = {"C", "S", "E", "P", "N", "T"}
    for identifier in known_ids:
        match = re.fullmatch(r"([A-Za-z][A-Za-z_-]*)(\d+)", identifier)
        if match:
            prefixes.add(match.group(1))
    pattern = r"(?<![\w-])(?:" + "|".join(re.escape(prefix) for prefix in sorted(prefixes, key=len, reverse=True)) + r")\d+(?![\w-])"
    found = set(re.findall(pattern, content))
    for identifier in known_ids:
        if identifier and re.search(r"(?<![\w-])" + re.escape(identifier) + r"(?![\w-])", content):
            found.add(identifier)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--acceptance", type=Path, help="Optional attributable AC1-AC9 review JSON; defaults to review/acceptance-review.json when present")
    args = parser.parse_args()
    session = args.session.resolve()
    if not session.is_dir() or not session.is_relative_to(WORKSPACE / "Ideas") or session.parent.name != "sessions":
        parser.error("session must be an existing Ideas/<idea>/sessions/<id> directory")
    output = args.output.resolve() if args.output else None
    review_dir = session / "evidenceandlogic/review"
    if output and (not output.is_relative_to(review_dir) or output.suffix.lower() != ".json"):
        parser.error("output must be a .json path inside the selected session's evidenceandlogic/review directory")
    acceptance = args.acceptance.resolve() if args.acceptance else session / "evidenceandlogic/review/acceptance-review.json"
    if not acceptance.is_relative_to(session):
        parser.error("acceptance record must be inside the selected session")
    checks: list[dict] = []

    def add(check_id: str, errors: list[str], detail: str):
        checks.append({"id": check_id, "status": "fail" if errors else "pass", "detail": detail, "errors": errors})

    missing = [name for name in REQUIRED if not (session / name).is_file()]
    empty = []
    for name in REQUIRED:
        path = session / name
        if path.is_file() and (path.stat().st_size == 0 or (path.suffix == ".md" and len(path.read_text(encoding="utf-8-sig").strip()) < 30)):
            empty.append(name)
    agent_results = list((session / "evidenceandlogic/agent-results").glob("*.md"))
    add("required-artifacts", ["Missing: " + name for name in missing] + ["Empty or too short: " + name for name in empty] + ([] if agent_results else ["No attributable agent-result files"]), "Required outputs exist and contain text; meaningfulness still needs review.")

    paths = list(session.rglob("*"))
    escaped = [str(p) for p in paths if not p.resolve().is_relative_to(session)]
    add("path-containment", escaped, "Resolved session artifacts remain inside their session; original input is checked separately.")

    parse_errors = []
    parsed: dict[str, object] = {}
    structured = [session / "run/session.json", session / "evidenceandlogic/sources.json"]
    experiment_files = sorted((session / "evidenceandlogic/experiments").glob("**/record.json"))
    structured += experiment_files
    for path in structured:
        try:
            parsed[str(path)] = read_json(path)
        except (ValueError, OSError) as exc:
            parse_errors.append(f"{path.relative_to(session)}: {exc}")
    claims = []
    try:
        with (session / "evidenceandlogic/claims.csv").open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != CLAIM_FIELDS:
                parse_errors.append("claims.csv columns must match documented order: " + ",".join(CLAIM_FIELDS))
            claims = list(reader)
            if any(None in row or any(v is None for v in row.values()) for row in claims):
                parse_errors.append("claims.csv contains malformed rows")
    except OSError as exc:
        parse_errors.append(str(exc))
    add("structured-parsing", parse_errors, f"Parsed required JSON, {len(experiment_files)} experiment records, and {len(claims)} claim rows.")

    metadata = parsed.get(str(session / "run/session.json"), {})
    if not isinstance(metadata, dict):
        metadata = {}
    hash_errors = []
    try:
        original = Path(metadata["input_path"]).resolve()
        expected = metadata["input_sha256"].lower()
        copied = session / "inputs/idea-original.md"
        if not original.is_relative_to(WORKSPACE):
            hash_errors.append("Original input lies outside the authorized workspace")
        elif hash_file(original) != expected or hash_file(copied) != expected or original.read_bytes() != copied.read_bytes():
            hash_errors.append("Original, copy and recorded SHA-256 do not match")
    except (KeyError, OSError, AttributeError) as exc:
        hash_errors.append(str(exc))
    add("preserved-input", hash_errors, "Original and exact copy match the session SHA-256; unrelated-file preservation requires separate evidence.")
    checks.append(protected_files_check(WORKSPACE, session / "run/protected-files.json"))
    checks.append(setup_prefix_check(WORKSPACE, session / "inputs/setup-backups"))

    source_errors = []
    sources = parsed.get(str(session / "evidenceandlogic/sources.json"), [])
    if not isinstance(sources, list) or not sources:
        source_errors.append("sources.json must be a nonempty array")
        sources = []
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            source_errors.append("Non-object source record")
            continue
        sid = source.get("source_id", "")
        if not isinstance(sid, str) or not sid or sid in source_ids:
            source_errors.append(f"Missing, invalid or duplicate source ID: {sid}")
        else:
            source_ids.add(sid)
        absent = SOURCE_FIELDS - source.keys()
        if absent:
            source_errors.append(f"{sid} missing fields: {sorted(absent)}")
        if not source.get("url") and not source.get("local_path"):
            source_errors.append(f"{sid} needs url or local_path")
        if source.get("url") and urlsplit(source["url"]).scheme not in {"http", "https"}:
            source_errors.append(f"{sid} has a non-http(s) public URL")
        if source.get("local_path"):
            local = (session / source["local_path"]).resolve()
            if not local.is_relative_to(session) or not local.exists():
                source_errors.append(f"{sid} local_path does not resolve inside session: {source['local_path']}")
        for field in ("title", "publisher", "source_type", "retrieved_at", "access_status", "source_family", "locator", "observation"):
            if not source.get(field):
                source_errors.append(f"{sid} has empty {field}")
    add("source-records", source_errors, f"Checked fields, unique IDs and local paths for {len(sources)} sources; URL truth/access is a research-review responsibility.")

    claim_ids = {row.get("claim_id", "") for row in claims}
    claim_errors = []
    if not claims or "" in claim_ids or len(claim_ids) != len(claims):
        claim_errors.append("Claims must be nonempty and have unique, nonempty IDs")
    experiments = [parsed.get(str(path), {}) for path in experiment_files]
    experiment_ids = {record.get("experiment_id", "") for record in experiments if isinstance(record, dict)}
    for row in claims:
        cid = row.get("claim_id", "")
        if row.get("assessment") not in {"supported", "contradicted", "mixed", "unverified"}:
            claim_errors.append(f"{cid}: invalid assessment")
        for field, known in (("source_ids", source_ids), ("experiment_ids", experiment_ids)):
            for identifier in (row.get(field) or "").split(";"):
                if identifier.strip() and identifier.strip() not in known:
                    claim_errors.append(f"{cid}: unresolved {field} reference {identifier.strip()}")
        for field in ("claim", "origin", "importance", "evidence_type", "scope_limits", "confidence_basis", "decision_consequence"):
            if not row.get(field):
                claim_errors.append(f"{cid}: empty {field}")
        if row.get("assessment") != "unverified" and not row.get("source_ids") and not row.get("experiment_ids"):
            claim_errors.append(f"{cid}: assessed claim has no source or experiment")
    add("claim-records-and-references", claim_errors, "Claim fields, assessments and source/experiment references resolve.")

    experiment_errors = []
    if not experiment_files:
        experiment_errors.append("No experiment records; save executed records or justified not_run protocols")
    if "" in experiment_ids or len(experiment_ids) != len(experiments):
        experiment_errors.append("Experiment IDs missing or duplicate")
    for record in experiments:
        if not isinstance(record, dict):
            experiment_errors.append("Non-object experiment record")
            continue
        eid = record.get("experiment_id", "")
        absent = EXPERIMENT_FIELDS - record.keys()
        if absent:
            experiment_errors.append(f"{eid} missing fields {sorted(absent)}")
        if record.get("status") not in {"executed", "partial", "not_run"}:
            experiment_errors.append(f"{eid}: use executed, partial or not_run")
        if not isinstance(record.get("linked_claims"), list):
            experiment_errors.append(f"{eid}: linked_claims must be an array")
        else:
            for cid in record["linked_claims"]:
                if cid not in claim_ids:
                    experiment_errors.append(f"{eid}: unresolved claim {cid}")
        if record.get("status") == "executed" and (not record.get("commands") or not record.get("observations")):
            experiment_errors.append(f"{eid}: executed experiment needs commands and observations")
        if record.get("status") == "not_run" and not (record.get("reason") or record.get("limitations")):
            experiment_errors.append(f"{eid}: not_run requires a reason or limitations")
        for field in ("kind", "hypothesis", "protocol", "environment", "result", "limitations", "reproduction"):
            if not record.get(field):
                experiment_errors.append(f"{eid}: empty {field}")
    add("experiment-records", experiment_errors, "Statuses and required fields are explicit; this does not independently reproduce results.")

    authored = [session / name for name in REQUIRED if name.endswith(".md") and not name.startswith("inputs/")]
    authored += agent_results + list((session / "evidenceandlogic/experiments").glob("**/*.md"))
    authored += [p for p in (session / "evidenceandlogic/review").glob("*.md") if p not in authored]
    authored = [p for p in authored if p.exists()]
    reference_errors = []
    known_ids = source_ids | claim_ids | experiment_ids
    for path in authored:
        content = without_fences(path.read_text(encoding="utf-8-sig"))
        for identifier in identifier_references(content, known_ids):
            if identifier not in known_ids:
                reference_errors.append(f"{path.relative_to(session)}: unknown ID {identifier}")
        if re.fullmatch(r"(?is)\s*(?:#.*\n\s*)?(?:TODO|TBD|PLACEHOLDER|INSERT CONTENT HERE)[.!]?\s*", content):
            reference_errors.append(f"{path.relative_to(session)}: placeholder content")
    add("document-identifiers-and-content", reference_errors, "Registered IDs and numeric C/S/E/P/N/T or registered-prefix references resolve in authored text; code fences and block quotations are excluded. Empty-placeholder checks supplement human content review.")

    link_errors = []
    def inspect_link(path: Path, target: str):
        target = target.strip().removeprefix("<").removesuffix(">")
        parsed_url = urlsplit(target)
        if parsed_url.scheme in {"http", "https", "mailto"}:
            return
        if safe_url(target) is None:
            link_errors.append(f"{path.relative_to(session)}: unsafe or nonportable link {target}")
            return
        resolved = (path.parent / unquote(parsed_url.path)).resolve() if parsed_url.path else path
        # Companions are session-local. Workflow/input context may link within workspace.
        if not resolved.is_relative_to(WORKSPACE) or not resolved.exists():
            link_errors.append(f"{path.relative_to(session)}: missing/outside-workspace link {target}")
            return
        if parsed_url.fragment and resolved.is_file() and resolved.suffix in {".md", ".html"}:
            if resolved.suffix == ".md":
                _, headings = render_markdown(resolved.read_text(encoding="utf-8-sig"))
                anchors = {anchor for _, anchor, _ in headings}
            else:
                audit = HTMLAudit()
                audit.feed(resolved.read_text(encoding="utf-8-sig"))
                anchors = audit.ids
            if unquote(parsed_url.fragment) not in anchors:
                link_errors.append(f"{path.relative_to(session)}: missing fragment {target}")
    for path in authored:
        for match in LINK.finditer(without_fences(path.read_text(encoding="utf-8-sig"))):
            inspect_link(path, match.group(2))
    html_path = session / "report/report.html"
    html_audit = HTMLAudit()
    if html_path.exists():
        html_audit.feed(html_path.read_text(encoding="utf-8-sig"))
        for target in html_audit.links:
            inspect_link(html_path, target)
    add("local-links", sorted(set(link_errors)), "Authored Markdown and HTML links resolve to existing workspace companions/fragments; external links are not fetched.")
    add("offline-assets", html_audit.runtime_assets + (["Script tags present"] if html_audit.scripts else []) + ([] if html_path.exists() else ["HTML missing"]), "No scripts, active embeds, CSS resource imports or runtime asset dependencies are permitted in this renderer's output.")

    render_errors = []
    report_path = session / "report/report.md"
    if report_path.exists() and html_path.exists():
        raw = report_path.read_bytes()
        expected_html = render_document(raw.decode("utf-8-sig"), report_path.name, hashlib.sha256(raw).hexdigest())
        if html_path.read_text(encoding="utf-8") != expected_html:
            render_errors.append("HTML does not match current Markdown rendered with this tool; regenerate")
    else:
        render_errors.append("Report Markdown or HTML missing")
    add("markdown-html-agreement", render_errors, "Full HTML equals deterministic rendering of current substantive Markdown, with matching SHA-256.")

    state_errors = []
    if metadata.get("session_id") != session.name:
        state_errors.append("Session ID differs from folder")
    if metadata.get("status") not in {"in_progress", "complete", "incomplete", "blocked"}:
        state_errors.append("Invalid session status")
    for field in ("created_at", "timezone", "input_path", "input_sha256", "route", "model", "next_resume_action"):
        if not metadata.get(field):
            state_errors.append(f"Missing metadata: {field}")
    for field in ("workers", "completed_checks", "blocked_items"):
        if not isinstance(metadata.get(field), list):
            state_errors.append(f"{field} must be an array")
    idea_index = session.parent.parent / "README.md"
    if not idea_index.exists():
        state_errors.append("Idea README index missing")
    elif session.name not in idea_index.read_text(encoding="utf-8-sig"):
        state_errors.append("Idea README does not reference this session")
    add("state-and-index", state_errors, "State fields and idea-index reference exist; latest-attempt/completed-pointer accuracy requires acceptance review.")

    acceptance_checks = []
    if acceptance.exists():
        try:
            review = read_json(acceptance)
            items = review.get("criteria", [])
            by_id = {item["id"]: item for item in items}
            for number in range(1, 10):
                cid = f"AC{number}"
                item = by_id.get(cid, {"id": cid, "status": "not_run", "detail": "No attributable acceptance assessment supplied"})
                item = dict(item)
                if item.get("status") not in {"pass", "fail", "not_run"}:
                    item["status"] = "fail"
                    item["detail"] = "Invalid acceptance status"
                if item.get("status") == "pass" and (not item.get("evidence") or not item.get("detail")):
                    item["status"] = "fail"
                    item["detail"] = "A passed acceptance criterion requires evidence paths and a concrete basis"
                for evidence in item.get("evidence", []):
                    evidence_path = (session / evidence).resolve()
                    if not evidence_path.is_relative_to(WORKSPACE) or not evidence_path.exists():
                        item["status"] = "fail"
                        item["detail"] = f"Acceptance evidence missing/outside workspace: {evidence}"
                item["origin"] = str(acceptance.relative_to(session))
                acceptance_checks.append(item)
            if not review.get("reviewer") or not review.get("reviewed_at"):
                add("acceptance-attribution", ["Acceptance record requires reviewer and reviewed_at"], "Acceptance attribution is recorded, not independently proven by JSON.")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            add("acceptance-parsing", [str(exc)], "Unable to import acceptance review")
    if not acceptance_checks:
        acceptance_checks = [{"id": f"AC{n}", "status": "not_run", "detail": "Requires attributable acceptance review; structural checks do not establish this criterion"} for n in range(1, 10)]
    failures = sum(c["status"] == "fail" for c in checks)
    result = {
        "schema_version": 1, "validated_at": datetime.now(timezone.utc).isoformat(), "session": str(session),
        "structural_status": "fail" if failures else "pass", "checks": checks,
        "acceptance_criteria": acceptance_checks,
        "acceptance_status": "complete" if all(c["status"] == "pass" for c in acceptance_checks) and not failures else "incomplete",
        "limitations": ["Does not establish source truth, agent independence or experiment reproducibility by itself.", "Visual browser inspection, statistical interpretation and decision quality require attributable review.", "External citations are not fetched; preservation covers only supplied baseline paths and available setup backups, excluding unrecorded files.", "Markdown renderer supports the documented subset, not every CommonMark extension."],
    }
    if output:
        if output == acceptance or output in structured:
            parser.error("output cannot overwrite acceptance or research input records")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if failures or any(c["status"] == "fail" for c in acceptance_checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
