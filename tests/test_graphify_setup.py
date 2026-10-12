"""Graphify setup safety and real local extraction in disposable projects."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

HELPER = Path(__file__).resolve().parents[1] / "payload/tools/engineering/graphify_setup.py"
spec = importlib.util.spec_from_file_location("starter_graphify_setup", HELPER)
graphify_setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graphify_setup)


def put(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def graph_data(repo="workspace"):
    return {"directed": True, "nodes": [
        {"id": f"{repo}::calc::add", "label": "add", "repo": repo,
         "source_file": "calc.py", "source_location": "L1-L2", "confidence": "EXTRACTED"},
        {"id": f"{repo}::calc::main", "label": "main", "repo": repo,
         "source_file": "calc.py", "source_location": "L4-L5", "confidence": "EXTRACTED"}],
        "links": [{"source": f"{repo}::calc::main", "target": f"{repo}::calc::add", "relation": "calls",
                   "evidence_repo": repo, "source_file": "calc.py", "source_location": "L5", "confidence": "EXTRACTED"}]}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "Project with spaces and 'apostrophe'"
    root.mkdir()
    put(root, "calc.py", "def add(left, right):\n    return left + right\n\ndef main():\n    return add(1, 2)\n")
    put(root, "tools/engineering/config/repositories.yaml", json.dumps({"repositories": {"workspace": {"path": "."}}}))
    return root


@pytest.fixture
def fake_runtime(monkeypatch):
    runtime = {"python": sys.executable, "version": graphify_setup.GRAPHIFY_VERSION,
               "installed": False, "environment": "existing"}
    monkeypatch.setattr(graphify_setup, "ensure_runtime", lambda *args: runtime)
    return runtime


def existing(root, relative="saved/graph.json"):
    graph = put(root, f"graphify-out/{relative}", json.dumps(graph_data()))
    pointer = put(root, "graphify-out/LATEST.md", f"[Current graph JSON]({relative})\n")
    return graph, pointer


def test_reuses_existing_publication_and_meaningful_query(project, fake_runtime, monkeypatch):
    graph, pointer = existing(project)
    bytes_before = pointer.read_bytes(), graph.read_bytes()
    monkeypatch.setattr(graphify_setup, "collect_sources", lambda *_: pytest.fail("Existing graph must not be rebuilt"))
    result = graphify_setup.ensure_graphify(project, queries=["main"])
    assert result["action"] == "reused"
    assert result["consultation"]["matching_nodes"] == 1
    assert result["consultation"]["matches"][0]["label"] == "main"
    assert (pointer.read_bytes(), graph.read_bytes()) == bytes_before


@pytest.mark.parametrize("pointer_text", ["no current graph", "[Current graph JSON](missing/graph.json)",
                                          "[Current graph JSON](https://example.test/graph.json)",
                                          "[Current graph JSON](../outside/graph.json)"])
def test_invalid_existing_pointer_never_installs_or_overwrites(project, monkeypatch, pointer_text):
    pointer = put(project, "graphify-out/LATEST.md", pointer_text)
    monkeypatch.setattr(graphify_setup, "ensure_runtime", lambda *_: pytest.fail("Invalid pointer must fail before installation"))
    with pytest.raises(graphify_setup.SetupError, match="Existing LATEST.md is invalid"):
        graphify_setup.ensure_graphify(project)
    assert pointer.read_text() == pointer_text


def test_checksum_mismatch_preserves_graph(project, fake_runtime):
    graph, pointer = existing(project)
    put(project, "graphify-out/saved/publication.json", '{"graph_sha256":"wrong"}')
    with pytest.raises(graphify_setup.SetupError, match="checksum"):
        graphify_setup.ensure_graphify(project)
    assert pointer.read_text().startswith("[Current")
    assert json.loads(graph.read_text()) == graph_data()


def test_adopts_valid_legacy_graph_without_rewriting_it(project, fake_runtime):
    graph = put(project, "graphify-out/graph.json", json.dumps(graph_data()))
    original = graph.read_bytes()
    result = graphify_setup.ensure_graphify(project)
    assert result["action"] == "adopted-legacy"
    assert graphify_setup.designated_graph(project) == graph
    assert graph.read_bytes() == original


def test_invalid_legacy_graph_fails_without_pointer(project, fake_runtime):
    legacy = put(project, "graphify-out/graph.json", '{"nodes": [], "links": []}')
    with pytest.raises(graphify_setup.SetupError, match="nonempty"):
        graphify_setup.ensure_graphify(project)
    assert legacy.read_text() == '{"nodes": [], "links": []}'
    assert not (project / "graphify-out/LATEST.md").exists()


@pytest.mark.parametrize("relative", ["../outside", "C:\\outside", "/outside", "tools/engineering", "graphify-out", ".codex"])
def test_scope_escape_and_exclusions_fail(project, relative):
    (project / "graphify-out").mkdir(exist_ok=True)
    (project / ".codex").mkdir(exist_ok=True)
    with pytest.raises(graphify_setup.SetupError):
        graphify_setup.collect_sources(project, [relative])


def test_manifest_excludes_tooling_generated_secrets_and_duplicates(project):
    put(project, "src/service.py", "def service():\n    return 1\n")
    for excluded in ["engineering-starter-kit/kit.py", "tools/engineering/runner.py", "graphify-out/generated.py",
                     ".codex/worker.py", ".agents/skill.py", "node_modules/lib.py", "dist/bundle.js",
                     "src/private/data.py", "src/secret.py", "src/service.g.cs", "src/client.min.js"]:
        put(project, excluded, "def excluded():\n    return 1\n")
    put(project, "src/client.py", 'api_key = "secret-value"\ndef client():\n    return 1\n')
    inventory = graphify_setup.collect_sources(project, ["src", "src"])
    assert list(inventory["files"]) == ["src/service.py"]
    assert inventory["supported_files"] == 1
    assert any(item["path"] == "src/client.py" for item in inventory["skipped"])


def test_symlink_scope_and_output_block_without_external_changes(project, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    put(outside, "source.py", "def source():\n    return 1\n")
    link = project / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation unavailable to this user")
    with pytest.raises(graphify_setup.SetupError, match="symlink"):
        graphify_setup.collect_sources(project, ["linked"])
    inventory = graphify_setup.collect_sources(project)
    assert all("linked" not in source for source in inventory["files"])
    (project / "graphify-out").symlink_to(outside, target_is_directory=True)
    with pytest.raises(graphify_setup.SetupError, match="symlink"):
        graphify_setup.ensure_graphify(project)
    assert list(outside.iterdir()) == [outside / "source.py"]


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_windows_junction_scope_and_output_are_rejected(project, tmp_path):
    outside = tmp_path / "outside-junction"
    outside.mkdir()
    put(outside, "sentinel.py", "def sentinel():\n    return 1\n")
    link = project / "linked-junction"
    made = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
    if made.returncode:
        pytest.skip("Junction creation unavailable to this user")
    with pytest.raises(graphify_setup.SetupError, match="junction"):
        graphify_setup.collect_sources(project, ["linked-junction"])
    inventory = graphify_setup.collect_sources(project)
    assert all("linked-junction" not in source for source in inventory["files"])
    made = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(project / "graphify-out"), str(outside)], capture_output=True)
    assert made.returncode == 0
    with pytest.raises(graphify_setup.SetupError, match="junction"):
        graphify_setup.ensure_graphify(project)
    assert list(outside.iterdir()) == [outside / "sentinel.py"]


def test_renamed_copied_distribution_is_excluded(project):
    kit = project / "copy under another name"
    put(kit, "Setup.ps1", "# distribution entry")
    put(kit, "scripts/install.py", "def installer():\n    return 1\n")
    put(kit, "payload/tools/engineering/runner.py", "def runner():\n    return 1\n")
    inventory = graphify_setup.collect_sources(project)
    assert list(inventory["files"]) == ["calc.py"]


def test_large_automatic_scope_stops_but_explicit_directory_is_accepted(project, monkeypatch):
    monkeypatch.setattr(graphify_setup, "MAX_FILES", 2)
    for index in range(3):
        put(project, f"src/module{index}.py", "def action():\n    return 1\n")
    with pytest.raises(graphify_setup.SetupError, match="-GraphifyScope src"):
        graphify_setup.collect_sources(project)
    with pytest.raises(graphify_setup.SetupError, match="explicit relative"):
        graphify_setup.collect_sources(project, ["."])
    inventory = graphify_setup.collect_sources(project, ["src"])
    assert inventory["explicit_narrowing"]
    assert inventory["supported_files"] == 3


def test_word_gate_and_empty_corpus_have_actionable_failure(project, monkeypatch):
    monkeypatch.setattr(graphify_setup, "MAX_WORDS", 2)
    with pytest.raises(graphify_setup.SetupError, match="words"):
        graphify_setup.collect_sources(project)
    (project / "empty").mkdir()
    with pytest.raises(graphify_setup.SetupError, match="No eligible code files"):
        graphify_setup.collect_sources(project, ["empty"])


def test_missing_runtime_installs_pinned_package_into_isolated_project_environment(project, monkeypatch):
    commands = []
    installed = [False]

    def compatible(python, root):
        return installed[0] and ".venv-graphify" in python

    def run(arguments, root, timeout=1800):
        commands.append(arguments)
        if "venv" in arguments:
            Path(arguments[-1]).mkdir(exist_ok=True)
        if "pip" in arguments:
            installed[0] = True
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(graphify_setup, "compatible_python", compatible)
    monkeypatch.setattr(graphify_setup, "run_command", run)
    result = graphify_setup.ensure_runtime(project, sys.executable)
    assert result["installed"]
    assert result["environment"] == "project-local"
    assert commands[0][-2:] == ["venv", str(project / "tools/engineering/.venv-graphify")]
    assert f"graphifyy=={graphify_setup.GRAPHIFY_VERSION}" in commands[1]
    assert "--upgrade" not in commands[1]


def test_existing_incompatible_environment_is_preserved(project, monkeypatch):
    marker = put(project, "tools/engineering/.venv-graphify/user.txt", "preserve")
    monkeypatch.setattr(graphify_setup, "compatible_python", lambda *_: False)
    monkeypatch.setattr(graphify_setup, "run_command", lambda *_: pytest.fail("Do not overwrite existing environment"))
    with pytest.raises(graphify_setup.SetupError, match="incompatible or incomplete"):
        graphify_setup.ensure_runtime(project, sys.executable)
    assert marker.read_text() == "preserve"


def test_owned_incomplete_environment_recovers_after_pip_failure(project, monkeypatch):
    state = {"ready": False, "fail_once": True}
    commands = []

    def run(arguments, root, timeout=1800):
        commands.append(arguments)
        if "pip" in arguments:
            if state["fail_once"]:
                state["fail_once"] = False
                raise graphify_setup.SetupError("Temporary download failure")
            state["ready"] = True
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(graphify_setup, "compatible_python", lambda python, root: state["ready"] and ".venv-graphify" in python)
    monkeypatch.setattr(graphify_setup, "run_command", run)
    with pytest.raises(graphify_setup.SetupError, match="Temporary download failure"):
        graphify_setup.ensure_runtime(project, sys.executable)
    receipt = project / "tools/engineering/.venv-graphify/.starter-kit-graphify.json"
    assert json.loads(receipt.read_text())["status"] == "installing"
    result = graphify_setup.ensure_runtime(project, sys.executable)
    assert result["installed"]
    assert json.loads(receipt.read_text())["status"] == "ready"
    assert len([arguments for arguments in commands if "pip" in arguments]) == 2


def test_invalid_query_does_not_install_or_publish(project, monkeypatch):
    monkeypatch.setattr(graphify_setup, "ensure_runtime", lambda *_: pytest.fail("Invalid query must fail first"))
    with pytest.raises(graphify_setup.SetupError, match="query terms"):
        graphify_setup.ensure_graphify(project, queries=[" "])
    assert not (project / "graphify-out").exists()


def test_build_failure_never_promotes_pointer(project, fake_runtime, monkeypatch):
    monkeypatch.setattr(graphify_setup, "run_command", lambda *_: (_ for _ in ()).throw(graphify_setup.SetupError("fixture build failure")))
    with pytest.raises(graphify_setup.SetupError, match="fixture build failure"):
        graphify_setup.ensure_graphify(project)
    assert not (project / "graphify-out/LATEST.md").exists()
    assert (project / "calc.py").read_text().startswith("def add")


def test_pointer_race_is_detected_and_concurrent_publication_preserved(project, fake_runtime, monkeypatch):
    def worker(arguments, root, timeout=1800):
        publication = Path(arguments[-1])
        put(publication, "graph.json", json.dumps(graph_data()))
        put(project, "graphify-out/LATEST.md", "Concurrent publisher owns this pointer")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(graphify_setup, "run_command", worker)
    with pytest.raises(graphify_setup.SetupError, match="changed during setup"):
        graphify_setup.ensure_graphify(project)
    assert (project / "graphify-out/LATEST.md").read_text() == "Concurrent publisher owns this pointer"


def test_pointer_created_after_check_is_never_overwritten(project, monkeypatch):
    graph = put(project, "graphify-out/new/graph.json", json.dumps(graph_data()))
    pointer = project / "graphify-out/LATEST.md"
    original_link = graphify_setup.os.link

    def concurrent_link(source, target):
        pointer.write_text("Publication created after predecessor check")
        return original_link(source, target)

    monkeypatch.setattr(graphify_setup.os, "link", concurrent_link)
    with pytest.raises(graphify_setup.SetupError, match="changed during setup"):
        graphify_setup.promote(project, graph, None)
    assert pointer.read_text() == "Publication created after predecessor check"


def test_source_change_during_extraction_does_not_promote(project, fake_runtime, monkeypatch):
    def worker(arguments, root, timeout=1800):
        publication = Path(arguments[-1])
        put(publication, "graph.json", json.dumps(graph_data()))
        put(project, "calc.py", "def changed():\n    return 3\n")
        return subprocess.CompletedProcess(arguments, 0, "", "")
    monkeypatch.setattr(graphify_setup, "run_command", worker)
    with pytest.raises(graphify_setup.SetupError, match="Source changed"):
        graphify_setup.ensure_graphify(project)
    assert not (project / "graphify-out/LATEST.md").exists()


def test_missing_edge_endpoints_fail_validation(project):
    data = graph_data()
    data["links"][0]["target"] = "missing"
    graph = put(project, "graphify-out/broken/graph.json", json.dumps(data))
    with pytest.raises(graphify_setup.SetupError, match="missing endpoints"):
        graphify_setup.validate_graph(graph)


def test_graphify_environment_cannot_select_provider_or_output(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_BACKEND", "external-provider")
    monkeypatch.setenv("GRAPHIFY_OUT", "outside-path")
    monkeypatch.setenv("GRAPHIFY_VIZ_NODE_LIMIT", "0")
    environment = graphify_setup.process_env()
    assert not any(key.startswith("GRAPHIFY_") for key in environment)
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"


def test_pip_destination_overrides_are_cleared_but_network_environment_is_preserved(monkeypatch):
    for name in ["PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_USER", "PIP_CONFIG_FILE", "PIP_PYTHON"]:
        monkeypatch.setenv(name, "outside-project")
    monkeypatch.setenv("PIP_INDEX_URL", "https://packages.example.test/simple")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.example.test")
    environment = graphify_setup.process_env()
    assert not any(name in environment for name in ["PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_USER", "PIP_PYTHON"])
    assert environment["PIP_CONFIG_FILE"] == os.devnull
    assert environment["PIP_INDEX_URL"] == "https://packages.example.test/simple"
    assert environment["HTTPS_PROXY"] == "https://proxy.example.test"


def compatible_installed_python():
    supplied = os.environ.get("STARTER_KIT_GRAPHIFY_TEST_PYTHON")
    if supplied:
        return supplied
    if os.name == "nt":
        roaming = os.environ.get("APPDATA")
        if roaming:
            candidate = Path(roaming) / "uv/tools/graphifyy/Scripts/python.exe"
            if candidate.is_file():
                return str(candidate)
    return sys.executable


def test_real_local_ast_publication_is_adapter_compatible_and_reusable(project):
    python = compatible_installed_python()
    if not graphify_setup.compatible_python(python, project):
        pytest.skip("Pinned Graphify is not installed; real test never installs dependencies")
    before = (project / "calc.py").read_bytes()
    result = graphify_setup.ensure_graphify(project, python=python, queries=["add"])
    assert result["action"] == "created"
    assert result["consultation"]["matching_nodes"] >= 1
    graph = Path(result["graph"])
    data = graphify_setup.validate_graph(graph)
    assert any(node.get("repo") == "workspace" and node.get("source_file") == "calc.py" for node in data["nodes"])
    assert all(node["id"].startswith("workspace::") for node in data["nodes"])
    assert all(node.get("_origin") == "ast" for node in data["nodes"])
    metadata = json.loads((graph.parent / "publication.json").read_text())
    assert metadata["graph_sha256"] == graphify_setup.digest(graph.read_bytes())
    assert metadata["semantic_input_tokens"] == metadata["semantic_output_tokens"] == 0
    inventory = json.loads((graph.parent / "source-inventory.json").read_text())
    assert inventory["workspace"]["current"]["calc.py"]["sha256"] == graphify_setup.digest(before)
    assert (graph.parent / "graph.html").is_file()
    assert (graph.parent / "GRAPH_REPORT.md").is_file()
    assert (graph.parent / "REFRESH_REPORT.md").is_file()
    assert (project / "calc.py").read_bytes() == before
    pointer_before = (project / "graphify-out/LATEST.md").read_bytes()
    rerun = graphify_setup.ensure_graphify(project, python=python)
    assert rerun["action"] == "reused"
    assert rerun["graph"] == result["graph"]
    assert (project / "graphify-out/LATEST.md").read_bytes() == pointer_before
    assert result["consultation"]["relationships"]
    assert any(check.get("freshness") == "matched" for check in result["consultation"]["source_checks"])
    assert json.loads((project / ".engineering-state/graphify/last-setup.json").read_text())["action"] == "reused"


def test_real_local_ast_preserves_registered_repository_identity(project):
    python = compatible_installed_python()
    if not graphify_setup.compatible_python(python, project):
        pytest.skip("Pinned Graphify is not installed; real test never installs dependencies")
    (project / "calc.py").unlink()
    for repo in ["backend", "frontend"]:
        put(project, f"{repo}/calc.py", "def shared_name():\n    return 1\n")
    put(project, "tools/engineering/config/repositories.yaml", json.dumps({"repositories": {
        "backend": {"path": "backend"}, "frontend": {"path": "frontend"}}}))
    result = graphify_setup.ensure_graphify(project, python=python)
    graph = graphify_setup.validate_graph(Path(result["graph"]))
    nodes = [node for node in graph["nodes"] if "shared_name" in node.get("label", "")]
    assert {node["repo"] for node in nodes} == {"backend", "frontend"}
    assert len({node["id"] for node in nodes}) == 2
    assert all(node["source_file"] == "calc.py" for node in nodes)


def test_probe_and_real_build_do_not_import_project_graphify_shadow(project):
    python = compatible_installed_python()
    put(project, "graphify.py", "from pathlib import Path\nPath('shadow-executed.txt').write_text('unsafe')\nraise RuntimeError('project shadow executed')\n")
    if not graphify_setup.compatible_python(python, project):
        pytest.skip("Pinned Graphify is not installed; real test never installs dependencies")
    result = graphify_setup.ensure_graphify(project, python=python)
    assert result["action"] == "created"
    assert not (project / "shadow-executed.txt").exists()


def test_real_non_git_empty_registry_gets_honest_workspace_identity(project):
    python = compatible_installed_python()
    if not graphify_setup.compatible_python(python, project):
        pytest.skip("Pinned Graphify is not installed; real test never installs dependencies")
    put(project, "tools/engineering/config/repositories.yaml", '{"repositories": {}}')
    result = graphify_setup.ensure_graphify(project, python=python)
    data = graphify_setup.validate_graph(Path(result["graph"]))
    assert all(node["repo"] == "workspace" for node in data["nodes"])
    metadata = json.loads((Path(result["graph"]).parent / "publication.json").read_text())
    assert metadata["repository_identities"]["workspace"]["registered"] is False
    assert metadata["runner_registry_ready"] is False
    assert all(check["status"] == "unavailable" for check in result["consultation"]["source_checks"])


def test_real_registry_ids_cannot_escape_cache_directory(project):
    python = compatible_installed_python()
    if not graphify_setup.compatible_python(python, project):
        pytest.skip("Pinned Graphify is not installed; real test never installs dependencies")
    put(project, "tools/engineering/config/repositories.yaml", json.dumps({"repositories": {"../unexpected": {"path": "."}}}))
    result = graphify_setup.ensure_graphify(project, python=python)
    graph = graphify_setup.validate_graph(Path(result["graph"]))
    assert all(node["repo"] == "../unexpected" for node in graph["nodes"])
    assert not (project / "graphify-out/unexpected").exists()
    assert not (project / "unexpected").exists()
