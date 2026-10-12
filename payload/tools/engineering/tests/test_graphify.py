import hashlib
import json
from pathlib import Path

import pytest

from workspace_engineering.adapters.graphify import GraphifyAdapter


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def graph_workspace(tmp_path):
    registry = tmp_path / "tools/engineering/config/repositories.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"repositories": {"workspace": {"path": "."}, "backend": {"path": "backend"}, "shared": {"path": "shared"}}}))
    publication = tmp_path / "graphify-out/datestamp"
    publication.mkdir(parents=True)
    source = tmp_path / "backend/Same.java"
    source.parent.mkdir()
    source.write_text("first\nsource relationship\nthird\n")
    other = tmp_path / "shared/Same.java"
    other.parent.mkdir()
    other.write_text("different repo\n")
    data = {"directed": False, "nodes": [
        {"id": "backend::a", "label": "Service", "repo": "backend", "source_file": "Same.java", "source_location": "L2"},
        {"id": "shared::b", "label": "Legacy", "repo": "shared", "source_file": "Same.java", "source_location": "L1"},
    ], "links": [{"source": "backend::a", "target": "shared::b", "relation": "uses", "confidence": "INFERRED",
                   "evidence_repo": "backend", "source_file": "Same.java", "source_location": "L2"}]}
    (publication / "graph.json").write_text(json.dumps(data))
    (publication / "publication.json").write_text(json.dumps({"graph_sha256": sha(publication / "graph.json"), "published_at": "fixture"}))
    (publication / "source-inventory.json").write_text(json.dumps({"backend": {"current": {"Same.java": sha(source)}}, "shared": {"current": {"Same.java": sha(other)}}}))
    (publication / "REFRESH_REPORT.md").write_text("Fixture coverage only.\n")
    (tmp_path / "graphify-out/LATEST.md").write_text("[Current combined graph JSON](datestamp/graph.json)\n[Historical graph](old/graph.json)\n")
    return tmp_path, publication


def test_bounded_query_keeps_repo_identity_confidence_and_current_source(graph_workspace):
    root, publication = graph_workspace
    before = {str(path): sha(path) for path in root.rglob("*") if path.is_file()}
    result = GraphifyAdapter(root).query(["Service"], max_nodes=1, max_edges=1)
    assert result["status"] == "limited"
    assert result["matches"][0]["id"] == "backend::a"
    assert result["edges"][0]["confidence"] == "INFERRED"
    assert {check["repo"] for check in result["source_checks"]} == {"backend", "shared"}
    assert all(check["freshness"] == "matched" for check in result["source_checks"])
    assert result["source_checks"][0]["excerpt"] == [{"line": 2, "text": "source relationship"}]
    assert before == {str(path): sha(path) for path in root.rglob("*") if path.is_file()}


def test_stale_source_is_reported(graph_workspace):
    root, _ = graph_workspace
    (root / "backend/Same.java").write_text("changed\n")
    result = GraphifyAdapter(root).query(["Service"])
    check = next(check for check in result["source_checks"] if check["repo"] == "backend")
    assert check["freshness"] == "changed"
    assert check["anchor_valid"] is False


def test_no_match_is_limited_and_never_proves_absence(graph_workspace):
    root, _ = graph_workspace
    result = GraphifyAdapter(root).query(["UnknownSymbol"])
    assert result["status"] == "limited"
    assert result["matching_nodes"] == 0
    assert any("does not establish" in note for note in result["limitations"])


@pytest.mark.parametrize("target", ["../../outside/graph.json", "https://example.invalid/graph.json", "C:/outside/graph.json"])
def test_publication_cannot_escape_local_graph_directory(graph_workspace, target):
    root, _ = graph_workspace
    (root / "graphify-out/LATEST.md").write_text(f"[Current graph JSON]({target})")
    assert GraphifyAdapter(root).publication()["status"] == "blocked"


def test_changed_graph_checksum_blocks_consultation(graph_workspace):
    root, publication = graph_workspace
    with (publication / "graph.json").open("a") as stream:
        stream.write(" ")
    assert GraphifyAdapter(root).query(["Service"])["status"] == "blocked"


def test_untrusted_source_anchor_cannot_escape_repository(graph_workspace):
    root, publication = graph_workspace
    graph = json.loads((publication / "graph.json").read_text())
    graph["nodes"][0]["source_file"] = "../shared/Same.java"
    (publication / "graph.json").write_text(json.dumps(graph))
    (publication / "publication.json").unlink()
    result = GraphifyAdapter(root).query(["Service"])
    assert result["source_checks"][0]["status"] == "blocked"


def test_query_limits_are_explicit(graph_workspace):
    root, _ = graph_workspace
    adapter = GraphifyAdapter(root)
    with pytest.raises(ValueError):
        adapter.query([])
    with pytest.raises(ValueError):
        adapter.query(["Service"], max_edges=201)
    result = adapter.query(["Service"], max_edges=0)
    assert result["edges"] == [] and result["truncated"]


def test_custom_repository_id_resolves_registered_nested_path(tmp_path):
    root = tmp_path / "services/api"
    root.mkdir(parents=True)
    source = root / "handler.py"
    source.write_text("def handle(): pass\n")
    registry = tmp_path / "tools/engineering/config/repositories.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"repositories": {"api-service": {"path": "services/api"}}}))
    result = GraphifyAdapter(tmp_path)._source(
        {"repo": "api-service", "source_file": "handler.py", "source_location": "L1"},
        {"api-service": {"current": {"handler.py": sha(source)}}},
    )
    assert result["status"] == "read"
    assert Path(result["path"]) == source
    assert result["freshness"] == "matched"


@pytest.mark.parametrize("relative", ["../outside", "C:/outside", "C:outside"])
def test_registry_source_path_cannot_escape_workspace(tmp_path, relative):
    registry = tmp_path / "tools/engineering/config/repositories.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"repositories": {"external": {"path": relative}}}))
    result = GraphifyAdapter(tmp_path)._source({"repo": "external", "source_file": "secret.txt"}, {})
    assert result["status"] == "unavailable"
    assert "path" not in result


def test_unknown_graph_repository_is_not_inferred_from_directory_name(tmp_path):
    (tmp_path / "unregistered").mkdir()
    (tmp_path / "unregistered/source.py").write_text("private data\n")
    registry = tmp_path / "tools/engineering/config/repositories.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"repositories": {"workspace": {"path": "."}}}))
    result = GraphifyAdapter(tmp_path)._source({"repo": "unregistered", "source_file": "source.py"}, {})
    assert result["status"] == "unavailable"
    assert "excerpt" not in result
