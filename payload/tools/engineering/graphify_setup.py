"""Install/reuse Graphify and prepare a local code-only publication when missing.

The orchestration path uses only the standard library. Graphify runs in a
separate compatible interpreter; no CLI detection, semantic extraction, model,
provider, repository script, or application command is invoked.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
from uuid import uuid4

GRAPHIFY_VERSION = "0.9.73"
MAX_FILES = 500
MAX_WORDS = 2_000_000
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_HTML_NODES = 5000
# Deliberately omit configuration/credential formats and preprocessors. Only
# these local structural extractors are eligible for automatic initial setup.
CODE_SUFFIXES = frozenset("""
 .py .ts .tsx .mts .cts .js .jsx .mjs .cjs .go .rs .java .groovy .gradle
 .cpp .cc .cxx .c .h .hpp .cu .cuh .metal .rb .rake .swift .kt .kts .cs
 .scala .php .lua .luau .zig .ps1 .psm1 .ex .exs .m .mm .ml .mli .jl
 .vue .svelte .astro .dart .v .sv .svh .sql .r .pas .pp .dpr .dpk .lpr
 .inc .sh .bash .cls .trigger .lisp .cl .lsp .asd .sol .erl .hrl .escript
 .vb .cbl .cob .cobol .cpy
""".split())
EXCLUDED_DIRS = frozenset("""
 .git .hg .svn .venv venv env node_modules bower_components vendor
 __pycache__ .pytest_cache .mypy_cache .ruff_cache .tox .nox .cache .gradle
 target dist build coverage .next .nuxt .output .turbo .engineering-state
 .codex .agents .idea .vscode .secrets secrets credentials .ssh .aws .gnupg
 .gcloud graphify-out engineering-starter-kit .venv-graphify
""".split())
SENSITIVE_NAME = re.compile(
    r"(?i)(?:^|[._-])(?:credentials?|secrets?|tokens?|passwords?|passwd|"
    r"private|payloads?|fixtures?|snapshots?|generated|bundles?|min|lock)(?:$|[._-])"
)
LITERAL_CREDENTIAL = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|private[_-]?key)"
    r"\s*[:=]\s*['\"][^'\"\r\n]+['\"]|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


class SetupError(ValueError):
    """An actionable failure that preserves the previous publication."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def linked(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def safe_path(root: Path, relative: str) -> Path:
    """Reject traversal and links before resolving a project-contained path."""
    parts = Path(relative.replace("\\", "/"))
    if parts.is_absolute() or PureWindowsPath(relative).drive or ".." in parts.parts:
        raise SetupError(f"Path must be relative and remain inside the project: {relative}")
    target = root / parts
    for ancestor in [target, *target.parents]:
        if ancestor == root.parent:
            break
        if linked(ancestor):
            raise SetupError(f"Refusing a symlink or junction: {ancestor}")
    if not target.resolve().is_relative_to(root):
        raise SetupError(f"Path escapes the project: {relative}")
    return target


def atomic_write(root: Path, path: Path, data: bytes) -> None:
    safe_path(root, path.relative_to(root).as_posix())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".graphify-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(root, path.relative_to(root).as_posix())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_graph(path: Path) -> dict:
    try:
        graph = json.loads(path.read_text(encoding="utf-8-sig"))
        nodes = graph["nodes"]
        edges = graph.get("links", graph.get("edges", []))
        if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
            raise SetupError("Graph must contain a nonempty nodes list and a relationships list")
        ids = [node["id"] for node in nodes]
        if any(not isinstance(node_id, str) or not node_id for node_id in ids) or len(set(ids)) != len(ids):
            raise SetupError("Graph contains invalid or duplicate node identities")
        node_ids = set(ids)
        if any(edge["source"] not in node_ids or edge["target"] not in node_ids for edge in edges):
            raise SetupError("Graph contains relationships with missing endpoints")
        return graph
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SetupError(f"Invalid graph {path}: {exc}") from exc


def designated_graph(root: Path) -> Path | None:
    pointer = safe_path(root, "graphify-out/LATEST.md")
    if not pointer.exists():
        return None
    try:
        text = pointer.read_text(encoding="utf-8-sig")
        links = re.findall(r"\[([^\]]+)\]\(([^\s)]+)\)", text)
        selected = [value for label, value in links
                    if "current" in label.casefold() and urlsplit(value).path.endswith("/graph.json")]
        if not selected:
            selected = [value for label, value in links
                        if "graph json" in label.casefold() and urlsplit(value).path.endswith("graph.json")]
        if len(selected) != 1:
            raise SetupError("LATEST.md must designate exactly one current graph JSON link")
        url = urlsplit(selected[0])
        if url.scheme or url.netloc or PureWindowsPath(selected[0]).drive:
            raise SetupError("LATEST.md graph link must be a relative local path")
        relative = "graphify-out/" + unquote(url.path).replace("\\", "/")
        graph = safe_path(root, relative)
        if not graph.is_file():
            raise SetupError(f"Designated graph does not exist: {graph}")
        validate_graph(graph)
        metadata_path = safe_path(root, (graph.parent / "publication.json").relative_to(root).as_posix())
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            expected = metadata.get("graph_sha256")
            if expected and expected != digest(graph.read_bytes()):
                raise SetupError("Designated graph checksum differs from publication.json")
        return graph
    except (OSError, ValueError, TypeError) as exc:
        raise SetupError(f"Existing LATEST.md is invalid; preserve and repair it explicitly: {exc}") from exc


def collect_sources(root: Path, scopes: list[str] | None = None) -> dict:
    selections = scopes or ["."]
    starts = []
    for scope in selections:
        start = safe_path(root, scope)
        if not start.is_dir():
            raise SetupError(f"Graphify scope must be an existing relative directory: {scope}")
        relative = start.relative_to(root)
        if any(part.casefold() in EXCLUDED_DIRS for part in relative.parts) or "tools/engineering" in relative.as_posix().casefold():
            raise SetupError(f"Graphify scope is excluded tooling, generated output, or sensitive data: {scope}")
        starts.append(start)
    narrowed = bool(scopes) and all(start != root for start in starts)
    records, skipped, visited = {}, [], set()
    words = 0
    for start in starts:
        for current, directories, filenames in os.walk(start, followlinks=False):
            folder = Path(current)
            rel_folder = folder.relative_to(root)
            if linked(folder):
                directories[:] = []
                continue
            directories[:] = sorted(name for name in directories
                if name.casefold() not in EXCLUDED_DIRS and not name.startswith(".")
                and not SENSITIVE_NAME.search(name) and not linked(folder / name)
                and (rel_folder / name).as_posix().casefold() != "tools/engineering"
                and not ((folder / name / "Setup.ps1").is_file()
                         and (folder / name / "scripts/install.py").is_file()
                         and (folder / name / "payload/tools/engineering").is_dir()))
            for name in sorted(filenames):
                path = folder / name
                relative = path.relative_to(root).as_posix()
                if relative in visited:
                    continue
                visited.add(relative)
                if path.suffix.casefold() not in CODE_SUFFIXES:
                    continue
                if (name.startswith(".") or SENSITIVE_NAME.search(name)
                        or name.casefold().endswith((".d.ts", ".g.cs", ".designer.cs")) or linked(path)):
                    skipped.append({"path": relative, "reason": "excluded name, generated file, or link"})
                    continue
                safe_path(root, relative)
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    raise SetupError(f"Source exceeds the {MAX_SOURCE_BYTES}-byte safety cap: {relative}; narrow --scope or inspect it separately")
                raw = path.read_bytes()
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    skipped.append({"path": relative, "reason": "not UTF-8 source"})
                    continue
                if "\x00" in text or LITERAL_CREDENTIAL.search(text):
                    skipped.append({"path": relative, "reason": "binary data or possible literal credential"})
                    continue
                count = len(text.split())
                words += count
                records[relative] = {"sha256": digest(raw), "bytes": len(raw), "words": count}
                if not narrowed and (len(records) > MAX_FILES or words > MAX_WORDS):
                    raise SetupError(
                        f"Automatic Graphify scope exceeds {MAX_FILES} supported files or {MAX_WORDS:,} words. "
                        "Rerun setup with explicit relative --scope <source-directory> (PowerShell: -GraphifyScope src); "
                        "repeat the option for deliberately selected directories. No publication was changed."
                    )
    if not records:
        raise SetupError("No eligible code files were found. Supply --scope <source-directory>; this setup does not create placeholder graphs or analyze documents semantically.")
    return {"scopes": [start.relative_to(root).as_posix() for start in starts],
            "explicit_narrowing": narrowed, "files": dict(sorted(records.items())),
            "supported_files": len(records), "total_words": words, "skipped": skipped,
            "excluded_directories": sorted(EXCLUDED_DIRS), "eligible_suffixes": sorted(CODE_SUFFIXES)}


def process_env() -> dict:
    # All invoked APIs are local. Remove Graphify overrides so environment
    # settings cannot choose alternate providers, caches, or output locations.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GRAPHIFY_")}
    # pip destination overrides must never redirect installation outside the
    # project environment. Disable pip config files while preserving explicit
    # index/proxy environment settings for the user's network.
    for key in list(environment):
        if key.upper() in {"PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PIP_ROOT", "PIP_PYTHON", "PIP_CONFIG_FILE"}:
            environment.pop(key)
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1"})
    return environment


def run_command(arguments: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(arguments, cwd=cwd, env=process_env(), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(f"Graphify command could not complete: {exc}") from exc
    if result.returncode:
        raise SetupError(f"Graphify command failed ({result.returncode}): {(result.stderr or result.stdout)[-2500:]}")
    return result


def compatible_python(python: str, root: Path) -> bool:
    code = (
        "from importlib.metadata import version; "
        f"assert version('graphifyy') == '{GRAPHIFY_VERSION}'; "
        "from graphify.extract import extract; from graphify.build import build; "
        "from graphify.export import to_json,to_html; from graphify.report import generate; "
        "from graphify.cluster import cluster"
    )
    try:
        run_command([python, "-I", "-B", "-c", code], root, timeout=60)
        return True
    except SetupError:
        return False


def ensure_runtime(root: Path, python: str | None = None) -> dict:
    executable = python or sys.executable
    candidates = [executable]
    command = shutil.which("graphify")
    if python is None and command and not Path(command).resolve().is_relative_to(root):
        directory = Path(command).resolve().parent
        candidates.extend(str(directory / name) for name in ("python.exe", "python", "python3"))
    uv = shutil.which("uv")
    if python is None and uv and not Path(uv).resolve().is_relative_to(root):
        try:
            tool_root = Path(run_command([uv, "tool", "dir"], root, timeout=20).stdout.strip())
            candidates.append(str(tool_root / "graphifyy" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")))
        except SetupError:
            pass
    local = safe_path(root, "tools/engineering/.venv-graphify")
    local_python = local / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    candidates.append(str(local_python))
    for candidate in dict.fromkeys(candidates):
        if compatible_python(candidate, root):
            return {"python": candidate, "version": GRAPHIFY_VERSION, "installed": False,
                    "environment": "project-local" if Path(candidate) == local_python else "existing"}
    ownership = local / ".starter-kit-graphify.json"
    if local.exists():
        try:
            receipt = json.loads(safe_path(root, ownership.relative_to(root).as_posix()).read_text())
        except (OSError, ValueError):
            receipt = {}
        if receipt.get("owner") != "engineering-starter-kit" or receipt.get("version") != GRAPHIFY_VERSION or receipt.get("status") not in {"creating", "installing"}:
            raise SetupError(f"Existing local Graphify environment is incompatible or incomplete: {local}. Preserve it and resolve the conflict explicitly; it was not overwritten.")
    else:
        local.mkdir(parents=True, exist_ok=False)
        atomic_write(root, ownership, encode({"owner": "engineering-starter-kit", "version": GRAPHIFY_VERSION, "status": "creating"}))
    run_command([executable, "-I", "-B", "-m", "venv", str(local)], root)
    safe_path(root, local.relative_to(root).as_posix())
    atomic_write(root, ownership, encode({"owner": "engineering-starter-kit", "version": GRAPHIFY_VERSION, "status": "installing"}))
    run_command([str(local_python), "-I", "-B", "-m", "pip", "install", "--disable-pip-version-check", "--no-user", f"graphifyy=={GRAPHIFY_VERSION}"], root)
    if not compatible_python(str(local_python), root):
        raise SetupError("Graphify installation completed but the pinned local API check failed")
    atomic_write(root, ownership, encode({"owner": "engineering-starter-kit", "version": GRAPHIFY_VERSION, "status": "ready"}))
    return {"python": str(local_python), "version": GRAPHIFY_VERSION, "installed": True, "environment": "project-local"}


def read_registry(root: Path, allow_fallback: bool = True) -> list[tuple[str, Path]]:
    path = safe_path(root, "tools/engineering/config/repositories.yaml")
    try:
        text = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text)
        except ValueError:
            import yaml  # available in the verified Graphify environment
            data = yaml.safe_load(text)
        repositories = data["repositories"]
        result = []
        for name, specification in repositories.items():
            if not isinstance(name, str) or not name or "::" in name:
                raise SetupError("Repository identities must be nonempty strings without ::")
            repository = safe_path(root, specification["path"])
            if not repository.is_dir():
                raise SetupError(f"Registered repository does not exist: {name}")
            result.append((name, repository))
        if not result and allow_fallback:
            # Non-Git destinations still have useful source. This identity is
            # explicit in graph metadata, but cannot imply runner readiness.
            result = [("workspace", root)]
        return sorted(result, key=lambda item: (-len(item[1].parts), item[0]))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SetupError(f"Graphify needs the installed repository registry: {exc}") from exc


def verify_sources(root: Path, inventory: dict) -> None:
    for relative, record in inventory["files"].items():
        path = safe_path(root, relative)
        if not path.is_file() or digest(path.read_bytes()) != record["sha256"]:
            raise SetupError(f"Source changed during Graphify preparation: {relative}; rerun without concurrent source edits")


def build_local(root: Path, publication: Path) -> None:
    """Worker in the pinned interpreter: Graphify AST/build/report/export APIs."""
    from graphify.extract import extract
    from graphify.build import build
    from graphify.cluster import cluster, cohesion_score
    from graphify.export import to_json, to_html
    from graphify.report import generate

    inventory = json.loads((publication / "source-input.json").read_text(encoding="utf-8"))
    verify_sources(root, inventory)
    registry = read_registry(root)
    grouped, source_inventory, extractions = {}, {}, []
    for relative, record in inventory["files"].items():
        path = safe_path(root, relative)
        selected = next(((name, folder) for name, folder in registry if path.is_relative_to(folder)), None)
        if selected is None:
            raise SetupError(f"Eligible source is outside the registered repositories: {relative}; narrow --scope to registered source")
        name, folder = selected
        grouped.setdefault(name, {"root": folder, "paths": []})["paths"].append(path)
        source_inventory.setdefault(name, {"current": {}})["current"][path.relative_to(folder).as_posix()] = record
    omissions = {}
    for repo, specification in sorted(grouped.items()):
        # Repository IDs are logical identifiers, never output path segments.
        # A custom registry can use slashes or drive-like text safely here.
        cache = publication / "ast-cache" / digest(repo.encode("utf-8"))[:16]
        extraction = extract(specification["paths"], root=specification["root"], cache_root=cache, parallel=False)
        ids = {node["id"]: f"{repo}::{node['id']}" for node in extraction.get("nodes", [])}
        for node in extraction.get("nodes", []):
            node["id"] = ids[node["id"]]
            node.update({"repo": repo, "extraction_tool": "graphify-local-ast", "extraction_depth": "ast"})
            # Graphify's build passes key AST identity behavior on this marker.
            # Retaining it prevents same-label symbols in separate repos from
            # being mistaken for semantic duplicates and silently collapsed.
            node.setdefault("_origin", "ast")
            node.setdefault("confidence", "EXTRACTED")
        for edge in extraction.get("edges", []):
            edge["source"] = ids.get(edge["source"], f"{repo}::{edge['source']}")
            edge["target"] = ids.get(edge["target"], f"{repo}::{edge['target']}")
            edge.update({"evidence_repo": repo, "extraction_tool": "graphify-local-ast"})
        for hyperedge in extraction.get("hyperedges", []):
            for key in ("members", "nodes", "node_ids"):
                if isinstance(hyperedge.get(key), list):
                    hyperedge[key] = [ids.get(member, f"{repo}::{member}") for member in hyperedge[key]]
        omissions[repo] = {key: value for key, value in extraction.items()
                          if key in {"failed_sources", "failed_files", "unsupported_sources", "warnings", "errors", "ast_failed_sources", "ast_unsupported_sources"}}
        extractions.append(extraction)
    if not any(item.get("nodes") for item in extractions):
        raise SetupError("Graphify AST extraction returned zero nodes; no publication pointer was created")
    graph = build(extractions, directed=True, dedup=False, root=None)
    communities = cluster(graph)
    scores = {key: cohesion_score(graph, members) for key, members in communities.items()}
    labels = {key: f"Code group {index + 1}" for index, key in enumerate(sorted(communities))}
    if not to_json(graph, communities, str(publication / "graph.json"), force=False, community_labels=labels):
        raise SetupError("Graphify refused the JSON export; no pointer was changed")
    validate_graph(publication / "graph.json")
    visual_graph, visual_communities = graph, communities
    if graph.number_of_nodes() > MAX_HTML_NODES:
        selected = set(sorted(graph.nodes)[:MAX_HTML_NODES])
        visual_graph = graph.subgraph(selected).copy()
        visual_communities = {key: [node for node in members if node in selected]
                              for key, members in communities.items() if any(node in selected for node in members)}
    if not to_html(visual_graph, visual_communities, str(publication / "graph.html"), community_labels=labels, node_limit=MAX_HTML_NODES):
        raise SetupError("Graphify refused the HTML export; no pointer was changed")
    report = generate(graph, communities, scores, labels, [], [],
                      {"total_files": inventory["supported_files"], "total_words": inventory["total_words"],
                       "warning": "Initial local code-only navigation graph. Documents, excluded files and runtime behavior are outside coverage."},
                      {"input_tokens": 0, "output_tokens": 0}, str(root))
    atomic_write(root, publication / "GRAPH_REPORT.md", report.encode("utf-8"))
    atomic_write(root, publication / "source-inventory.json", encode(source_inventory))
    atomic_write(root, publication / "extraction-notes.json", encode({"repositories": omissions,
        "html": {"represented_nodes": visual_graph.number_of_nodes(), "total_nodes": graph.number_of_nodes(),
                 "truncated": visual_graph.number_of_nodes() < graph.number_of_nodes(),
                 "external_asset": "Graphify HTML loads vis-network from unpkg when opened; generation makes no request"}}))
    registered = dict(read_registry(root, allow_fallback=False))
    identities = {name: {"path": folder.relative_to(root).as_posix(), "registered": name in registered}
                  for name, folder in registry}
    atomic_write(root, publication / "repository-identities.json", encode(identities))
    verify_sources(root, inventory)


def validate_queries(queries: list[str] | None) -> None:
    if queries and (any(not term.strip() or len(term) > 200 for term in queries) or len(queries) > 16):
        raise SetupError("Graph consultation accepts 1-16 nonempty query terms, at most 200 characters each")


def consult(root: Path, graph_path: Path, queries: list[str] | None = None) -> dict:
    graph = validate_graph(graph_path)
    nodes = sorted(graph["nodes"], key=lambda node: str(node["id"]))
    terms = queries or [str(next((node["label"] for node in nodes if node.get("label")), nodes[0]["id"]))[:200]]
    validate_queries(terms)
    matches = [node for node in nodes if any(term.casefold() in str(node.get("label", "")).casefold() for term in terms)]
    selected = matches[:8]
    selected_ids = {node["id"] for node in selected}
    edges = graph.get("links", graph.get("edges", []))
    adjacent = [edge for edge in edges if edge["source"] in selected_ids or edge["target"] in selected_ids]
    checks = []
    try:
        registry = dict(read_registry(root, allow_fallback=False))
        inventory_path = safe_path(root, (graph_path.parent / "source-inventory.json").relative_to(root).as_posix())
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig")) if inventory_path.is_file() else {}
        seen = set()
        for record in [*selected, *adjacent[:24]]:
            repo = record.get("evidence_repo") or record.get("repo")
            relative = record.get("source_file")
            identity = (repo, relative)
            if identity in seen:
                continue
            seen.add(identity)
            check = {"repo": repo, "source_file": relative, "relationship_verified": False}
            repository = registry.get(repo)
            if repository is None or not isinstance(relative, str) or not relative:
                checks.append({**check, "status": "unavailable", "reason": "Unregistered source identity"})
                continue
            path = safe_path(root, (repository.relative_to(root) / relative).as_posix())
            if not path.is_relative_to(repository) or not path.is_file():
                checks.append({**check, "status": "unavailable", "reason": "Missing or out-of-repository source"})
                continue
            current = digest(path.read_bytes())
            expected = inventory.get(repo, {}).get("current", {}).get(relative)
            expected = expected.get("sha256") if isinstance(expected, dict) else expected
            checks.append({**check, "status": "read", "sha256": current, "publication_sha256": expected,
                           "freshness": "matched" if current == expected else "changed" if expected else "unknown"})
    except (OSError, ValueError, ImportError) as exc:
        checks.append({"status": "unavailable", "reason": str(exc)})
    fields = ("id", "label", "repo", "source_file", "source_location", "confidence", "_origin")
    edge_fields = ("source", "target", "relation", "confidence", "confidence_score", "evidence_repo", "source_file", "source_location", "_origin")
    return {"status": "limited", "query_terms": terms, "matching_nodes": len(matches),
            "matches": [{key: node.get(key) for key in fields} for node in selected],
            "relationships": [{key: edge.get(key) for key in edge_fields} for edge in adjacent[:24]],
            "matching_edges": len(adjacent), "source_checks": checks,
            "nodes": len(nodes), "edges": len(graph.get("links", graph.get("edges", []))),
            "limitations": ["Initial/sample label consultation establishes graph readability; assess task coverage, freshness and consequential relationships against current source.",
                            "The local AST graph excludes documents, sensitive/generated files, external services and application runtime evidence."]}


def promote(root: Path, graph: Path, expected_pointer: bytes | None) -> None:
    pointer = safe_path(root, "graphify-out/LATEST.md")
    current = pointer.read_bytes() if pointer.exists() else None
    if current != expected_pointer:
        raise SetupError("LATEST.md changed during setup; the concurrent publication was preserved")
    if expected_pointer is not None:
        raise SetupError("Setup only creates a missing publication pointer; replacing an existing pointer requires explicit maintenance")
    relative = graph.relative_to(pointer.parent).as_posix()
    text = ("# Current Graphify publication\n\n"
            f"[Current graph JSON]({relative})\n\n"
            "Prepared or adopted by engineering setup. Consult the publication report and source provenance; "
            "a readable graph does not establish task coverage or runtime behavior.\n")
    # A fully written temporary file is atomically linked to the previously
    # missing pointer. Unlike os.replace, this cannot overwrite a publication
    # that appears after the predecessor check (including another publisher).
    fd, temporary = tempfile.mkstemp(prefix=".graphify-pointer-", dir=pointer.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(root, pointer.relative_to(root).as_posix())
        try:
            os.link(temporary, pointer)
        except FileExistsError as exc:
            raise SetupError("LATEST.md changed during setup; the concurrent publication was preserved") from exc
        except OSError as exc:
            raise SetupError(f"Atomic publication requires local hard-link support; LATEST.md was not replaced: {exc}") from exc
    finally:
        os.unlink(temporary)


def ensure_graphify(project_root: Path, scopes: list[str] | None = None,
                    python: str | None = None, queries: list[str] | None = None) -> dict:
    validate_queries(queries)
    original = Path(project_root).absolute()
    if not original.is_dir() or linked(original):
        raise SetupError("Project root must be an existing real directory")
    root = original.resolve()
    safe_path(root, ".engineering-state/graphify/last-setup.json")
    graph = designated_graph(root)
    legacy = safe_path(root, "graphify-out/graph.json")
    action = "reused"
    if graph is None and legacy.exists():
        validate_graph(legacy)
        graph, action = legacy, "adopted-legacy"
    inventory = collect_sources(root, scopes) if graph is None else None
    runtime = ensure_runtime(root, python)
    if graph is None:
        output = safe_path(root, "graphify-out")
        output.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("starter-kit-%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
        publication = safe_path(root, f"graphify-out/{name}")
        publication.mkdir(exist_ok=False)
        atomic_write(root, publication / "source-input.json", encode(inventory))
        run_command([runtime["python"], "-I", "-B", str(Path(__file__).resolve()), "--project-root", str(root), "--build-publication", str(publication)], root)
        graph = publication / "graph.json"
        data = validate_graph(graph)
        verify_sources(root, inventory)
        timestamp = datetime.now(timezone.utc).isoformat()
        report = (f"# Initial Graphify publication\n\nPublished: {timestamp}\n\n"
                  f"Graphify: {GRAPHIFY_VERSION}; local deterministic AST extraction, directed build, clustering, report and HTML export.\n\n"
                  f"Scope: {', '.join(inventory['scopes'])}. Eligible files: {inventory['supported_files']}; words: {inventory['total_words']:,}. "
                  f"Graph: {len(data['nodes'])} nodes, {len(data.get('links', data.get('edges', [])))} edges.\n\n"
                  "Provider/model/semantic calls: zero. Document requirements and excluded source are outside coverage. "
                  "Confidence labels distinguish extracted and inferred relationships; workers must verify consequential relationships. "
                  "Source hashes are recorded in source-inventory.json; extraction notes record available failure information.\n")
        atomic_write(root, publication / "REFRESH_REPORT.md", report.encode("utf-8"))
        identity_path = publication / "repository-identities.json"
        identities = json.loads(identity_path.read_text()) if identity_path.is_file() else {}
        metadata = {"published_at": timestamp, "graph_sha256": digest(graph.read_bytes()),
                    "graphify_version": GRAPHIFY_VERSION, "mode": "local-code-only-ast", "runtime": runtime,
                    "source_scopes": inventory["scopes"], "source_files": inventory["supported_files"],
                    "repository_identities": identities,
                    "runner_registry_ready": bool(identities) and all(item["registered"] for item in identities.values()),
                    "semantic_input_tokens": 0, "semantic_output_tokens": 0,
                    "artifacts": {path.name: digest(path.read_bytes()) for path in publication.iterdir() if path.is_file()}}
        atomic_write(root, publication / "publication.json", encode(metadata))
        # Missing at entry is the only accepted predecessor. A pointer appearing
        # while extraction runs belongs to its publisher and must be preserved.
        promote(root, graph, None)
        action = "created"
    elif action == "adopted-legacy":
        promote(root, graph, None)
    result = {"status": "ready", "action": action, "runtime": runtime,
            "graph": str(graph), "graph_sha256": digest(graph.read_bytes()),
            "pointer": str(root / "graphify-out/LATEST.md"), "consultation": consult(root, graph, queries)}
    summary = safe_path(root, ".engineering-state/graphify/last-setup.json")
    atomic_write(root, summary, encode(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--python", help="Existing Python to check; incompatible versions use a new project-local environment")
    parser.add_argument("--scope", action="append", help="Repeatable relative source directory; required to deliberately narrow a large corpus")
    parser.add_argument("--query", action="append", help="Repeatable meaningful graph label term; setup defaults to an actual sample label")
    parser.add_argument("--build-publication", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.build_publication:
            root = args.project_root.resolve()
            publication = safe_path(root, args.build_publication.relative_to(root).as_posix())
            if publication.parent != root / "graphify-out" or not publication.name.startswith("starter-kit-"):
                raise SetupError("Internal publication must be a unique starter-kit directory beneath graphify-out")
            build_local(root, publication)
        else:
            print(json.dumps(ensure_graphify(args.project_root, args.scope, args.python, args.query), indent=2))
        return 0
    except (SetupError, OSError, ValueError) as exc:
        print(f"Graphify setup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
