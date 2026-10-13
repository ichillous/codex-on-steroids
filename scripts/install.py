"""Install the portable engineering kit without replacing unrelated project settings.

Standard library only: analysis and conflict checks work before dependency installation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
import tempfile
import tomllib
from uuid import uuid4

# Load the trusted sibling explicitly: isolated Python intentionally excludes
# the current directory and PYTHONPATH from module lookup.
_onboarding_spec = importlib.util.spec_from_file_location(
    "starter_kit_onboarding", Path(__file__).resolve().with_name("onboarding.py"))
onboarding = importlib.util.module_from_spec(_onboarding_spec)
_onboarding_spec.loader.exec_module(onboarding)

KIT = Path(__file__).resolve().parents[1]
STATE = ".engineering-state/starter-kit-install.json"
BEGIN = "<!-- BEGIN engineering-starter-kit -->"
END = "<!-- END engineering-starter-kit -->"
MODULES = ("idea-research", "blueprint-first", "claudely", "reverse-engineer-anything")


class Conflict(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def is_link_or_junction(path: Path) -> bool:
    try:
        # stat() follows a Windows junction and loses its reparse attribute.
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except FileNotFoundError:
        return False


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or PureWindowsPath(relative).drive or ".." in rel.parts:
        raise Conflict(f"Path escapes target project: {relative}")
    target = root / rel
    for part in [target, *target.parents]:
        if part == root.parent:
            break
        if is_link_or_junction(part):
            raise Conflict(f"Refusing to write through a symlink or junction: {part}")
    if not target.resolve().is_relative_to(root):
        raise Conflict(f"Path escapes target project: {relative}")
    return target


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".kit-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def jsonc_mask(text: str) -> str:
    """Blank comments/trailing commas while retaining character offsets and strings."""
    chars = list(text)
    i = 0
    quoted = False
    while i < len(chars):
        if quoted:
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == '"':
                quoted = False
        elif text[i] == '"':
            quoted = True
        elif text[i:i+2] == "//":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            chars[i:end] = " " * (end-i)
            i = end
            continue
        elif text[i:i+2] == "/*":
            end = text.find("*/", i+2)
            if end < 0:
                raise Conflict("Unterminated JSONC comment")
            chars[i:end+2] = " " * (end+2-i)
            i = end+2
            continue
        i += 1
    masked = "".join(chars)
    # Only commas outside strings can be JSONC trailing commas.
    quoted = False
    i = 0
    while i < len(chars):
        if quoted:
            if masked[i] == "\\":
                i += 2
                continue
            if masked[i] == '"':
                quoted = False
        elif masked[i] == '"':
            quoted = True
        elif masked[i] == ",":
            j = i + 1
            while j < len(chars) and masked[j].isspace():
                j += 1
            if j < len(chars) and masked[j] in "]}":
                chars[i] = " "
        i += 1
    return "".join(chars)


def jsonc_members(text: str):
    masked = jsonc_mask(text)
    decoder = json.JSONDecoder()
    parsed = json.loads(masked)
    if not isinstance(parsed, dict):
        raise Conflict("VS Code tasks must be a JSON object")
    i = masked.index("{") + 1
    spans = {}
    while True:
        while masked[i].isspace() or masked[i] == ",":
            i += 1
        if masked[i] == "}":
            return parsed, spans, i
        key, end = decoder.raw_decode(masked, i)
        if key in spans:
            raise Conflict(f"Duplicate JSONC key: {key}")
        i = end
        while masked[i].isspace():
            i += 1
        if masked[i] != ":":
            raise Conflict("Invalid JSONC object")
        i += 1
        while masked[i].isspace():
            i += 1
        _, end = decoder.raw_decode(masked, i)
        spans[key] = (i, end)
        i = end


def merge_tasks(old: bytes | None, incoming: dict) -> bytes:
    if old is None:
        return encoded(incoming)
    text = old.decode("utf-8-sig")
    current, spans, closing = jsonc_members(text)
    edits = []
    absent = {}
    for name, key in (("tasks", "label"), ("inputs", "id")):
        values = current.get(name, [])
        if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
            raise Conflict(f"VS Code {name} must be a list of objects")
        indexed = {v.get(key): v for v in values}
        if len(indexed) != len(values):
            raise Conflict(f"Duplicate VS Code {name} identifiers")
        additions = []
        for value in incoming.get(name, []):
            if value[key] in indexed:
                if indexed[value[key]] != value:
                    raise Conflict(f"Existing VS Code {name} entry conflicts: {value[key]}")
            else:
                additions.append(value)
        if not additions:
            continue
        if name not in spans:
            absent[name] = additions
            continue
        start, end = spans[name]
        body = "\n" + ",\n".join(json.dumps(v, indent=2) for v in additions) + "\n"
        for fragment in (body, "," + body):
            try:
                json.loads(jsonc_mask(text[:end-1] + fragment + text[end-1:]))
                edits.append((end-1, fragment))
                break
            except json.JSONDecodeError:
                continue
        else:
            raise Conflict(f"Could not safely append VS Code {name}")
    if absent:
        # A top-level trailing comma is valid JSONC; normalize only by adding
        # content after it, or add one when the existing object lacks one.
        # Comments can follow the comma, so test both insertions with parser.
        fragments = [("" if not current else ",") + "\n" + ",\n".join(json.dumps(k)+": "+json.dumps(v, indent=2) for k,v in absent.items()) + "\n"]
        if current:
            fragments.insert(0, "\n" + ",\n".join(json.dumps(k)+": "+json.dumps(v, indent=2) for k,v in absent.items()) + "\n")
        for fragment in fragments:
            try:
                json.loads(jsonc_mask(text[:closing] + fragment + text[closing:]))
                edits.append((closing, fragment))
                break
            except json.JSONDecodeError:
                continue
        else:
            raise Conflict("Could not safely append VS Code task properties")
    for offset, fragment in sorted(edits, reverse=True):
        text = text[:offset] + fragment + text[offset:]
    json.loads(jsonc_mask(text))
    prefix = b"\xef\xbb\xbf" if old.startswith(b"\xef\xbb\xbf") else b""
    return prefix + text.encode("utf-8")


def merge_marker(old: bytes | None, body: str, begin=BEGIN, end=END) -> bytes:
    raw = old or b""
    start, stop = begin.encode(), end.encode()
    block = start + b"\n" + body.strip().encode("utf-8") + b"\n" + stop
    if start in raw or stop in raw:
        if raw.count(start) != 1 or raw.count(stop) != 1 or raw.index(start) > raw.index(stop):
            raise Conflict("Malformed starter-kit managed section")
        return raw[:raw.index(start)] + block + raw[raw.index(stop)+len(stop):]
    return raw + (b"\n\n" if raw else b"") + block + b"\n"


def mcp_config(project: Path, old: bytes | None) -> bytes:
    value = {"command": str(project / "tools/engineering/.venv/Scripts/python.exe"),
             "args": ["-B", "-m", "workspace_engineering", "--workspace", str(project), "mcp"],
             "startup_timeout_sec": 30, "tool_timeout_sec": 120}
    raw = old or b""
    current = tomllib.loads(raw.decode("utf-8-sig"))
    existing = current.get("mcp_servers", {}).get("workspace-engineering")
    if existing is not None:
        if existing != value:
            raise Conflict("Existing mcp_servers.workspace-engineering differs; preserve it and resolve the name/path conflict before setup")
        return raw
    block = "[mcp_servers.workspace-engineering]\n" + "\n".join(f"{key} = {json.dumps(val, ensure_ascii=False)}" for key, val in value.items())
    merged = raw + (b"\n\n" if raw else b"") + block.encode("utf-8") + b"\n"
    tomllib.loads(merged.decode("utf-8-sig"))
    return merged


def catalogs(inventory: dict, plan: dict) -> tuple[dict, dict]:
    repositories = {}
    for repo in inventory["repositories"]:
        if not repo.get("git"):
            continue
        repositories[repo["id"]] = {
            "path": repo["path"], "instructions": sorted(set([Path(p).relative_to(repo["path"]).as_posix() for p in repo.get("instructions", [])] + (["AGENTS.md", ".codex/workflows/engineering.md"] if repo["path"] == "." else []))),
            "toolchain": "; ".join(sorted({app["kind"] + ": " + json.dumps(app.get("toolchain", {}), sort_keys=True) for app in repo.get("apps", [])})) or "Inspect repository source and tooling",
            "dependencies": [], "applications": sorted({Path(app["path"]).relative_to(repo["path"]).as_posix() for app in repo.get("apps", [])}),
        }
    registry = {"version": 1, "snapshot_excludes": ["target", "build", "dist", "node-target", "graphify-out", "engineering-starter-kit"], "repositories": repositories}
    checks = {}
    candidates = {c["id"]: c for c in inventory["validation_candidates"]}
    for choice in plan["validation_choices"]:
        c = candidates[choice["candidate_id"]]
        if c["repo"] not in repositories:
            continue
        repo_path = Path(repositories[c["repo"]]["path"])
        source = Path(c["source"]).relative_to(repo_path).as_posix()
        spec = {"repo": c["repo"], "cwd": c["cwd"], "automatic": False, "enabled": True,
                "source": [c["source"]], "requires": [source], "timeout_seconds": 600,
                "notes": [choice["rationale"], "Selected during onboarding; inspect current build definitions before explicitly choosing this check. Setup does not execute it."]}
        if c["profile"] == "python-pytest":
            spec.update(kind="test", parser="pytest", argv=["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider"], effects=["Executes repository tests, plugins and fixtures; may write test outputs"])
            spec["notes"].append("Uses engineering Python; install this project's reviewed test dependencies into that environment or adapt argv to its own environment before running.")
        elif c["profile"] == "maven-test":
            spec.update(kind="test", parser="maven", argv=["mvn.cmd", "-o", "-B", "test"], reports=["**/target/surefire-reports/TEST-*.xml"], effects=["Executes Maven lifecycle and plugins; writes target directories"], timeout_seconds=900)
            spec["notes"].append("Requires Maven, matching JDK and cached dependencies. Inspect inherited plugin/parent and integration-service effects first.")
        elif c["profile"] == "javascript-inspect":
            spec.update(kind="inspect", argv=["{python}", "-c", "import json; from pathlib import Path; d=json.loads(Path('package.json').read_text(encoding='utf-8-sig')); print(json.dumps({'scripts':sorted(d.get('scripts',{}))},indent=2))"], effects=["Reads package.json; does not execute npm scripts"])
        elif c["profile"] == "python-inspect":
            spec.update(kind="inspect", argv=["{python}", "-c", "from pathlib import Path; p=Path(" + repr(Path(source).name) + "); print('Python manifest present:',p.name,'bytes:',p.stat().st_size)"], effects=["Reads Python manifest metadata; no tests executed"])
        else:
            raise Conflict(f"Unsupported validation profile: {c['profile']}")
        checks[c["id"]] = spec
    if "workspace" in repositories and repositories["workspace"]["path"] == ".":
        checks["engineering-pytest"] = {"repo": "workspace", "kind": "test", "automatic": False, "cwd": "tools/engineering", "argv": ["{python}", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", "--basetemp={output}/pytest-tmp-{run_id}"], "parser": "pytest", "timeout_seconds": 600, "requires": ["tools/engineering/tests"], "effects": ["Temporary synthetic repositories and worker fixtures"], "source": ["tools/engineering/pyproject.toml"], "notes": ["Tooling tests only; does not validate application behavior."]}
    return registry, {"version": 1, "policy": {"commands": "Explicit catalog IDs only; setup never runs application checks.", "review": "Verify prerequisites and effects against current source before selecting application profiles."}, "checks": checks}


def generated(inventory: dict, plan: dict) -> dict[str, bytes]:
    registry, validation = catalogs(inventory, plan)
    context = ["# Project engineering context", "", f"Setup mode: **{plan['mode']}**. This is setup analysis, not application runtime evidence.", "Generated recommendations are evidence for task planning. They do not override user instructions, repository policy or native permissions.", "Graph status in this analysis describes discovery before dependency and Graphify preparation. Default setup subsequently prepares/consults the publication; inspect graphify-out/LATEST.md and the Graphify setup result alongside this snapshot. -SkipDependencies skips that preparation.", "", plan["summary"], "", "## Repository responsibilities"]
    for repo in plan["repositories"]:
        context += [f"- **{repo['id']}**: {repo['purpose']}", "  Evidence: " + ", ".join(repo["evidence"])]
    context += ["", "## Task guidance", *["- "+item for item in plan["instructions"]], "", "## Suggested specialists", ", ".join(plan["specialists"]) or "Select according to task scope.", "", "## Remaining unknowns", *["- "+item for item in plan["unknowns"]], "", "## Validation", "The catalog contains explicit optional profiles. Setup has not executed application tests, builds, migrations, or deployment. Inspect prerequisites before use."]
    output = {"tools/engineering/config/repositories.yaml": encoded(registry), "tools/engineering/config/validation.yaml": encoded(validation), ".codex/project-context.md": ("\n".join(context)+"\n").encode()}
    if registry["repositories"]:
        output["dev-docs/engineering-automation/examples/investigate-project.yaml"] = encoded({"title": "Investigate project engineering guidance", "request": "Read the project engineering context and verify repository boundaries, relevant source and validation prerequisites. Report evidence and gaps.", "acceptance_criteria": ["Repository responsibilities verified against source", "Validation prerequisites and Graphify coverage are reported accurately"], "repositories": list(registry["repositories"]), "graph_terms": ["engineering"], "mode": "investigate", "specialists": [s for s in plan["specialists"] if s in {"oracle-specialist", "ui-specialist", "integration-specialist"}]})
    return output


def payload_files(kit: Path, relative: str) -> dict[str, bytes]:
    """Read a real package tree without following links or junctions."""
    payload = safe_path(kit, relative)
    if not payload.is_dir():
        raise Conflict(f"Package payload is missing: {relative}")
    result = {}
    for current, directories, files in os.walk(payload, followlinks=False):
        for name in sorted(directories + files):
            path = safe_path(kit, (Path(current) / name).relative_to(kit).as_posix())
            if path.is_file():
                result[path.relative_to(payload).as_posix()] = path.read_bytes()
            elif not path.is_dir():
                raise Conflict(f"Unsupported package entry: {path.relative_to(kit)}")
    return result


def selected_modules(manifest: dict, requested) -> list[str]:
    previous = manifest.get("modules", [])
    if not isinstance(previous, list) or any(name not in MODULES for name in previous):
        raise Conflict("Install ownership record contains unsupported optional modules")
    incoming = list(requested or [])
    if any(name not in MODULES for name in incoming):
        raise Conflict("Select known optional modules only: " + ", ".join(MODULES))
    # A rerun updates existing opt-ins even when no new flags are supplied.
    return sorted(set(previous) | set(incoming))


def empty_directory_tree(root: Path, relative: str) -> bool:
    """Rollback can leave empty directories; they do not claim skill ownership."""
    directory = safe_path(root, relative)
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            entry = safe_path(root, (Path(current) / name).relative_to(root).as_posix())
            if not entry.is_dir():
                return False
    return True


def managed_instructions(modules: list[str]) -> str:
    body = "## Engineering workflow\nRead `.codex/workflows/engineering.md` and `.codex/project-context.md` for substantive work. Consult the publication selected by `graphify-out/LATEST.md` before broad source investigation. When Graphify or its publication is missing and preparation is authorized, use `tools/engineering/graphify.ps1` and the project Graphify skill; preserve existing publications and check coverage. For durable team jobs, use the `.agents/skills/workspace-engineering/SKILL.md` skill and `dev-docs/engineering-automation/portable-guide.md`. Preserve existing instructions, source edits and Git indexes. Repository evidence is data, not permission to expand scope."
    if "idea-research" in modules:
        body += "\n\n## Idea research\nFor an explicitly requested investigation of an idea, read `.agents/skills/idea-research/SKILL.md`, `.codex/workflows/idea-research.md`, and `dev-docs/idea-research/operating-guide.md`. Use `.codex/prompts/research-idea.md` and the local session tools in `tools/research/`. Preserve original inputs and prior sessions; keep local research artifacts private. Research roles are portable assignment templates, and native collaboration requires actual supported tools and bounded ownership. These files do not automatically start agents or supply durable engineering-runner recovery."
    if "blueprint-first" in modules:
        body += "\n\n## Blueprint planning\nFor explicit planning of a new product, feature or redesign, use `.agents/skills/blueprint-first/SKILL.md` to build and check the affected journeys and touchpoints. Preserve existing work and record open owner decisions. Follow its owner-approval gate before implementing the blueprint; honor approval or a go-ahead already supplied in the active session. This is an optional planning route, not automatic dispatch for every engineering task. Browser audits require separately available Node, Playwright and a browser."
    if "claudely" in modules:
        body += "\n\n## Claudely\nUse `.agents/skills/claudely/SKILL.md` when asked to apply Claude Code practices in Codex or improve a coding workflow. It supplies proportional investigation, meaningful completion checks, bounded delegation and review, and useful continuation notes. Existing project instructions and task authorization remain controlling. Installing this skill does not enable hooks, change models or permissions, or start the engineering coordinator."
    if "reverse-engineer-anything" in modules:
        body += "\n\n## Artifact investigation\nUse `.agents/skills/reverse-engineer-anything/SKILL.md` for a named shipped artifact, decompilation question, or requested runtime evidence. Ordinary source-repository analysis uses the existing engineering route. This module installs instructions only; it does not register REA MCP, acquire tools or engines, or authorize target execution. Use the active host's actual tool inventory and schemas, preserve artifact identity and evidence limits, and handle an observed connection blocker within the task's authorization."
    return body


def managed_ignores(modules: list[str]) -> str:
    body = "/.engineering-state/\n/tools/engineering/.venv/\n/tools/engineering/.venv-graphify/\n/tools/engineering/experiments/autogen/.venv-studio/\n**/__pycache__/\n**/.pytest_cache/"
    if "idea-research" in modules:
        body += "\n# Local copied inputs, research evidence and generated result index\n/Ideas/*/sessions/\n/Ideas/INDEX.md"
    if "blueprint-first" in modules:
        body += "\n# Default blueprint diagnostics and browser screenshots\n/blueprint/_check/"
    return body


def plan_install(project: Path, kit: Path, inventory: dict, plan: dict, modules=None) -> list[dict]:
    manifest_path = safe_path(project, STATE)
    manifest = json.loads(manifest_path.read_bytes()) if manifest_path.exists() else {"files": {}}
    active_modules = selected_modules(manifest, modules)
    desired = payload_files(kit, "payload")
    for module in active_modules:
        extra = payload_files(kit, f"modules/{module}/payload")
        overlap = set(desired) & set(extra)
        if overlap:
            raise Conflict(f"Optional module overlaps another package file: {module}: {sorted(overlap)[0]}")
        desired.update(extra)
    # Independently installed skills retain their entire folder and ownership.
    # Never mix our supporting scripts into another owner's skill implementation.
    skill_roots = {"/".join(name.split("/")[:3]) for name in desired if name.startswith(".agents/skills/")}
    for skill_root in sorted(skill_roots):
        owned = any(name.startswith(skill_root + "/") for name in manifest.get("files", {}))
        existing = safe_path(project, skill_root)
        if not owned and existing.exists():
            if not existing.is_dir():
                raise Conflict(f"Independent skill folder is incomplete or not a directory: {skill_root}")
            if safe_path(project, skill_root + "/SKILL.md").is_file():
                desired = {name: value for name, value in desired.items() if not name.startswith(skill_root + "/")}
            elif not empty_directory_tree(project, skill_root):
                raise Conflict(f"Independent skill folder is incomplete or not a directory: {skill_root}")
    tasks = json.loads(desired.pop(".vscode/tasks.json"))
    desired.update(generated(inventory, plan))
    merges = {"AGENTS.md": lambda old: merge_marker(old, managed_instructions(active_modules)),
              ".gitignore": lambda old: merge_marker(old, managed_ignores(active_modules), "# BEGIN engineering-starter-kit", "# END engineering-starter-kit"),
              ".codex/config.toml": lambda old: mcp_config(project, old),
              ".vscode/tasks.json": lambda old: merge_tasks(old, tasks)}
    changes = []
    for name in sorted(set(desired) | set(merges)):
        path = safe_path(project, name)
        if path.exists() and not path.is_file():
            raise Conflict(f"Target file is a directory: {name}")
        old = path.read_bytes() if path.exists() else None
        if name in merges:
            # Managed instruction sections are replaceable only if they still
            # match our last installed section; additions elsewhere survive.
            if old is not None and name in ("AGENTS.md", ".gitignore"):
                begin, end = (BEGIN, END) if name == "AGENTS.md" else ("# BEGIN engineering-starter-kit", "# END engineering-starter-kit")
                if begin.encode() in old and end.encode() in old:
                    section = old[old.index(begin.encode()):old.index(end.encode())+len(end)]
                    known = manifest.get("sections", {}).get(name)
                    if known and sha(section) != known:
                        raise Conflict(f"Managed section was locally edited: {name}")
            new = merges[name](old)
            if old is not None and name in ("AGENTS.md", ".gitignore") and not manifest.get("sections", {}).get(name):
                begin, end = (BEGIN, END) if name == "AGENTS.md" else ("# BEGIN engineering-starter-kit", "# END engineering-starter-kit")
                if begin.encode() in old:
                    existing_section = old[old.index(begin.encode()):old.index(end.encode())+len(end)]
                    incoming_section = new[new.index(begin.encode()):new.index(end.encode())+len(end)]
                    if existing_section != incoming_section:
                        raise Conflict(f"Existing managed section has no matching ownership record: {name}")
        else:
            new = desired[name]
            if old is not None and old != new and manifest.get("files", {}).get(name) != sha(old):
                raise Conflict(f"Existing file differs and is not an unmodified kit-owned file: {name}")
        changes.append({"path": name, "before": old, "after": new})
    owned = {"version": 1, "modules": active_modules, "files": {c["path"]: sha(c["after"]) for c in changes}, "sections": {}}
    for c in changes:
        if c["path"] in ("AGENTS.md", ".gitignore"):
            begin, end = (BEGIN, END) if c["path"] == "AGENTS.md" else ("# BEGIN engineering-starter-kit", "# END engineering-starter-kit")
            raw = c["after"]
            owned["sections"][c["path"]] = sha(raw[raw.index(begin.encode()):raw.index(end.encode())+len(end)])
    changes.append({"path": STATE, "before": manifest_path.read_bytes() if manifest_path.exists() else None, "after": encoded(owned)})
    return [c for c in changes if c["before"] != c["after"]]


def apply(project: Path, changes: list[dict], output: Path) -> Path:
    # Backups and a complete write receipt precede all project configuration writes.
    receipt = {"project_root": str(project), "status": "prepared", "changes": []}
    for change in changes:
        path = safe_path(project, change["path"])
        now = path.read_bytes() if path.exists() else None
        if now != change["before"]:
            raise Conflict(f"Target changed after planning: {change['path']}")
        backup = None
        if change["before"] is not None:
            backup = "backup/" + change["path"]
            atomic_write(safe_path(output, backup), change["before"])
        receipt["changes"].append({"path": change["path"], "before_sha256": sha(change["before"]) if change["before"] is not None else None, "after_sha256": sha(change["after"]), "backup": backup})
    receipt_path = output / "receipt.json"
    atomic_write(receipt_path, encoded(receipt))
    done = []
    try:
        for change in changes:
            path = safe_path(project, change["path"])
            current = path.read_bytes() if path.exists() else None
            if current != change["before"]:
                raise Conflict(f"Target changed during installation: {change['path']}")
            atomic_write(path, change["after"])
            done.append(change)
    except BaseException:
        for change in reversed(done):
            path = safe_path(project, change["path"])
            if path.exists() and path.read_bytes() == change["after"]:
                if change["before"] is None:
                    path.unlink()
                else:
                    atomic_write(path, change["before"])
        receipt["status"] = "failed"
        atomic_write(receipt_path, encoded(receipt))
        raise
    receipt["status"] = "installed"
    atomic_write(receipt_path, encoded(receipt))
    return receipt_path


def rollback(project: Path, receipt_path: Path) -> None:
    project = project.resolve()
    receipt_path = safe_path(project, receipt_path.absolute().relative_to(project).as_posix())
    if not receipt_path.is_relative_to(project / ".engineering-state/setup"):
        raise Conflict("Rollback receipt must be inside this project's .engineering-state/setup directory")
    receipt = json.loads(receipt_path.read_bytes())
    if Path(receipt["project_root"]).resolve() != project:
        raise Conflict("Receipt belongs to another project")
    changes = receipt["changes"]
    restores = []
    seen = set()
    for change in changes:
        if change["path"] in seen:
            raise Conflict("Rollback receipt contains duplicate paths")
        seen.add(change["path"])
        path = safe_path(project, change["path"])
        current = path.read_bytes() if path.is_file() else None
        current_sha = sha(current) if current is not None else None
        if path.exists() and not path.is_file():
            raise Conflict(f"Rollback preserves later edits; file changed: {change['path']}")
        # A prepared receipt records planned writes. A hard stop can leave a
        # mixture of applied and untouched paths, including absent new files.
        if current_sha == change["before_sha256"]:
            continue
        if current_sha != change["after_sha256"]:
            raise Conflict(f"Rollback preserves later edits; file changed: {change['path']}")
        original = safe_path(receipt_path.parent, change["backup"]).read_bytes() if change["backup"] else None
        if (sha(original) if original is not None else None) != change["before_sha256"]:
            raise Conflict(f"Backup hash differs: {change['path']}")
        restores.append((change["path"], current, original))
    for relative, expected, original in reversed(restores):
        path = safe_path(project, relative)
        # Repeat the comparison immediately before each mutation. Unknown
        # concurrent edits remain intact; repeating rollback safely resumes.
        if not path.is_file() or path.read_bytes() != expected:
            raise Conflict(f"Rollback preserves later edits; file changed: {relative}")
        if original is None:
            path.unlink()
        else:
            atomic_write(path, original)
    receipt["status"] = "rolled_back"
    atomic_write(receipt_path, encoded(receipt))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=KIT.parent)
    parser.add_argument("--static", action="store_true", help="Explicit manifest-only setup; do not call Codex")
    parser.add_argument("--plan-only", action="store_true", help="Save setup analysis and planned file list without installing")
    parser.add_argument("--model")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--module", action="append", choices=MODULES, default=[], help="Opt in to a module; repeat to select multiple. Previous selections remain installed on rerun.")
    parser.add_argument("--rollback", type=Path)
    args = parser.parse_args(argv)
    supplied = args.project_root.absolute()
    linked = any(is_link_or_junction(p) for p in [supplied, *supplied.parents])
    project = supplied.resolve()
    if not project.is_dir() or linked or project == KIT or project.is_relative_to(KIT):
        parser.error("Project root must be an existing real directory outside the starter kit")
    if args.rollback:
        rollback(project, args.rollback)
        print("Configuration rollback complete. Environments and setup evidence are retained.")
        return 0
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = safe_path(project, ".engineering-state/setup/" + run_name)
    inventory = onboarding.discover(project, KIT)
    output.mkdir(parents=True)
    atomic_write(output / "inventory.json", encoded(inventory))
    atomic_write(output / "setup-prompt.md", onboarding.prepare_prompt(project, inventory).encode("utf-8"))
    print(f"Setup evidence: {output}", flush=True)
    try:
        plan = onboarding.static_plan(inventory) if args.static else onboarding.tailor(project, inventory, output, codex=args.codex, model=args.model, timeout=args.timeout)
    except (ValueError, OSError, RuntimeError) as exc:
        atomic_write(output / "setup-error.json", encoded({"status": "failed", "stage": "analysis", "error": str(exc)}))
        raise
    atomic_write(output / "tailoring.json", encoded(plan))
    # Configuration must correspond to the evidence actually analyzed.
    for evidence in inventory.get("evidence", []):
        source = safe_path(project, evidence["path"])
        if not source.is_file() or sha(source.read_bytes()) != evidence["sha256"]:
            raise Conflict(f"Source changed during setup analysis: {evidence['path']}; rerun setup")
    changes = plan_install(project, KIT, inventory, plan, args.module)
    atomic_write(output / "planned-files.json", encoded([{"path": c["path"], "action": "create" if c["before"] is None else "update"} for c in changes]))
    if args.plan_only:
        print(f"Plan saved: {len(changes)} file changes; no project configuration installed.")
        return 0
    receipt = apply(project, changes, output)
    print(f"Installed {len(changes)} changed files. Analysis mode: {plan['mode']}. Receipt: {receipt}")
    print("Existing permissions, hooks, secrets, global configuration and application source were preserved.")
    if not any(r.get("git") for r in inventory["repositories"]):
        print("No Git repositories found. Instructions are installed; coordinator jobs require an actual Git repository and a setup rerun.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
