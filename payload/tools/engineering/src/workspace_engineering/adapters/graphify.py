"""Bounded, non-writing Graphify traversal with current source evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
from urllib.parse import unquote, urlsplit

import yaml

from workspace_engineering.repository_manager import file_sha256


class GraphifyAdapter:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.pointer = self.workspace / "graphify-out/LATEST.md"

    def _repository_root(self, repo: str) -> Path | None:
        """Resolve graph identity through this project's explicit registry."""
        catalog = self.workspace / "tools/engineering/config/repositories.yaml"
        try:
            data = yaml.safe_load(catalog.read_text(encoding="utf-8-sig"))
            repositories = data.get("repositories", {})
            configured = repositories.get(repo)
            if not isinstance(configured, dict):
                return None
            relative = configured.get("path", repo)
            if not isinstance(relative, str) or Path(relative).is_absolute() or PureWindowsPath(relative).drive:
                return None
            root = (self.workspace / relative).resolve()
            return root if root.is_relative_to(self.workspace) else None
        except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
            return None

    def _safe_path(self, parent: Path, value: str) -> Path:
        url = urlsplit(value)
        if url.scheme or url.netloc or PureWindowsPath(value).drive:
            raise ValueError("Graph publication links must be relative local paths")
        target = (parent / unquote(url.path).replace("\\", "/")).resolve()
        if not target.is_relative_to(self.workspace / "graphify-out"):
            raise ValueError("Graph publication link escapes graphify-out")
        return target

    def publication(self) -> dict:
        try:
            content = self.pointer.read_text(encoding="utf-8-sig")
            links = re.findall(r"\[([^\]]+)\]\(([^\s)]+)\)", content)
            # Prefer the explicitly designated current graph; historical links
            # in the same pointer must never become a silent fallback.
            selected = [target for label, target in links if "current" in label.casefold() and urlsplit(target).path.endswith("/graph.json")]
            if not selected:
                selected = [target for label, target in links if "graph json" in label.casefold() and urlsplit(target).path.endswith("graph.json")]
            if len(selected) != 1:
                raise ValueError("LATEST.md must designate exactly one current graph JSON link")
            graph = self._safe_path(self.pointer.parent, selected[0])
            if not graph.is_file():
                raise ValueError(f"Designated graph does not exist: {graph}")
            digest = file_sha256(graph)
            metadata_path = graph.parent / "publication.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig")) if metadata_path.is_file() else {}
            expected = metadata.get("graph_sha256")
            if expected and expected != digest:
                raise ValueError("Designated graph checksum differs from publication.json")
            report = graph.parent / "REFRESH_REPORT.md"
            report_text = report.read_text(encoding="utf-8-sig") if report.is_file() else ""
            return {
                "status": "available", "path": str(graph), "sha256": digest,
                "pointer": str(self.pointer), "pointer_sha256": file_sha256(self.pointer),
                "published_at": metadata.get("published_at"),
                "checksum_verified": bool(expected), "report": str(report) if report.is_file() else None,
                "report_sha256": file_sha256(report) if report.is_file() else None,
                "coverage_notes": report_text[:16000], "coverage_notes_truncated": len(report_text) > 16000,
                "source_freshness": "assessed per returned source; publication date alone is insufficient",
            }
        except (OSError, ValueError, TypeError) as exc:
            return {"status": "blocked", "pointer": str(self.pointer), "error": str(exc)}

    def _source(self, record: dict, inventory: dict) -> dict:
        repo = record.get("evidence_repo") or record.get("repo")
        if not repo:
            repo = str(record.get("id", record.get("source", ""))).split("::", 1)[0]
        source = record.get("source_file")
        result = {"repo": repo, "source_file": source, "source_location": record.get("source_location"),
                  "relationship_verified": False}
        root = self._repository_root(repo) if isinstance(repo, str) else None
        if root is None or not isinstance(source, str) or not source:
            return {**result, "status": "unavailable", "reason": "Missing or unrecognized repository/source identity"}
        # Absolute historical paths are accepted only when they remain inside
        # the recorded repository on this host; alternate-drive paths fail.
        path = (root / source.replace("\\", "/")).resolve()
        if not path.is_relative_to(root.resolve()) or (PureWindowsPath(source).drive and not Path(source).is_absolute()):
            return {**result, "status": "blocked", "reason": "Source path escapes its repository"}
        if not path.is_file():
            return {**result, "status": "missing", "path": str(path)}
        try:
            digest = file_sha256(path)
            relative = path.relative_to(root.resolve()).as_posix()
            expected = inventory.get(repo, {}).get("current", {}).get(relative)
            if isinstance(expected, dict):
                expected = expected.get("sha256")
            freshness = "matched" if expected == digest else "changed" if expected else "unknown"
            anchor = str(record.get("source_location") or "")
            match = re.fullmatch(r"L?(\d+)(?:[-:]L?(\d+))?", anchor)
            lines = []
            anchor_valid = None
            if match:
                start, end = int(match.group(1)), int(match.group(2) or match.group(1))
                if 0 < start <= end:
                    # Stream to avoid loading a multi-megabyte source solely
                    # for a small anchor. Both returned lines and chars are capped.
                    count = 0
                    with path.open(encoding="utf-8", errors="replace") as stream:
                        for count, line in enumerate(stream, 1):
                            if start <= count <= min(end, start + 11):
                                lines.append({"line": count, "text": line.rstrip()[:500]})
                            if count >= end:
                                break
                    anchor_valid = count >= end
                else:
                    anchor_valid = False
            return {**result, "status": "read", "path": str(path), "sha256": digest,
                    "publication_sha256": expected, "freshness": freshness,
                    "anchor_valid": anchor_valid, "excerpt": lines,
                    "note": "Current bytes and anchors checked. A worker must verify the claimed relationship against source."}
        except OSError as exc:
            return {**result, "status": "unavailable", "reason": str(exc)}

    def query(self, terms: list[str], max_nodes: int = 8, max_edges: int = 24) -> dict:
        if not isinstance(terms, list) or not 1 <= len(terms) <= 16 or any(not isinstance(t, str) or not t.strip() or len(t) > 200 for t in terms):
            raise ValueError("Graph query requires 1-16 nonempty terms, each at most 200 characters")
        if not 1 <= max_nodes <= 50 or not 0 <= max_edges <= 200:
            raise ValueError("Graph query limits are 1-50 nodes and 0-200 edges")
        publication = self.publication()
        result = {"publication": publication, "sha256": publication.get("sha256"),
                  "query": {"terms": terms, "max_nodes": max_nodes, "max_edges": max_edges,
                            "mode": "case-insensitive labels and one-hop adjacency"},
                  "matches": [], "edges": [], "source_checks": []}
        if publication["status"] == "blocked":
            return {**result, "status": "blocked", "error": publication["error"]}
        try:
            graph_path = Path(publication["path"])
            raw = graph_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != publication["sha256"]:
                raise ValueError("Graph changed while consultation was starting")
            graph = json.loads(raw)
            nodes_list = graph["nodes"]
            edges = graph.get("links", graph.get("edges", []))
            nodes = {node["id"]: node for node in nodes_list}
            if len(nodes) != len(nodes_list):
                raise ValueError("Graph contains duplicate node identities")
            needles = [term.casefold() for term in terms]
            matches = [node for node in nodes.values() if any(needle in str(node.get("label", "")).casefold() for needle in needles)]
            matches.sort(key=lambda node: (str(node.get("label", "")).casefold() not in needles, str(node["id"])))
            selected = matches[:max_nodes]
            ids = {node["id"] for node in selected}
            adjacent = [edge for edge in edges if edge.get("source") in ids or edge.get("target") in ids]
            selected_edges = adjacent[:max_edges]
            if any(edge.get("source") not in nodes or edge.get("target") not in nodes for edge in selected_edges):
                raise ValueError("Selected graph relationships have missing endpoints")
            node_fields = ("id", "label", "repo", "source_file", "source_location", "confidence", "confidence_score", "_origin", "refreshed_at", "extraction_depth")
            edge_fields = ("source", "target", "relation", "confidence", "confidence_score", "_origin", "evidence_repo", "source_file", "source_location")
            result["matches"] = [{key: node.get(key) for key in node_fields} for node in selected]
            result["edges"] = [{key: edge.get(key) for key in edge_fields} for edge in selected_edges]
            neighbor_ids = {value for edge in selected_edges for value in (edge["source"], edge["target"])} - ids
            result["neighbors"] = [{key: nodes[node_id].get(key) for key in node_fields} for node_id in sorted(neighbor_ids)]
            inventory_path = graph_path.parent / "source-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig")) if inventory_path.is_file() else {}
            seen = set()
            checks = []
            for record in [*selected, *(nodes[node_id] for node_id in sorted(neighbor_ids)), *selected_edges]:
                identity = (record.get("evidence_repo") or record.get("repo") or str(record.get("id", record.get("source", ""))).split("::")[0], record.get("source_file"), record.get("source_location"))
                if identity in seen:
                    continue
                seen.add(identity)
                checks.append(self._source(record, inventory))
            result.update({
                "source_checks": checks, "directed": graph.get("directed"),
                "matching_nodes": len(matches), "matching_edges": len(adjacent),
                "truncated": len(matches) > len(selected) or len(adjacent) > len(selected_edges),
                "status": "limited",
                "limitations": ["Bounded adjacency is navigation, not proof of call direction or absence of other impact.",
                                "Current source hashes and anchors are supplied. A worker must assess consequential relationships and coverage."]
                    + (["No graph labels matched; this does not establish absence of relevant code."] if not matches else [])
                    + (["Graph uses an undirected projection; verify direction in source."] if not graph.get("directed") else []),
            })
            return result
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return {**result, "status": "blocked", "error": str(exc)}
