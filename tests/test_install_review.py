"""Adversarial installer checks using disposable directories only."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import pytest


KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
spec = importlib.util.spec_from_file_location("starter_install_review", KIT / "scripts/install.py")
install = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(install)
onboarding = install.onboarding


def git_init(root):
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet", "--template=", str(root)], check=True, capture_output=True)


def minimal_kit(tmp_path):
    kit = tmp_path / "kit"
    payload = kit / "payload"
    (payload / ".vscode").mkdir(parents=True)
    (payload / ".vscode/tasks.json").write_text(json.dumps({
        "version": "2.0.0", "tasks": [{"label": "Engineering: Review", "type": "process", "command": "python", "args": ["-B"]}],
        "inputs": [{"id": "engineeringTask", "type": "promptString", "description": "Task"}],
    }))
    (payload / "tools/engineering").mkdir(parents=True)
    (payload / "tools/engineering/README.md").write_text("fixture toolkit\n")
    return kit


def prepare(project, kit):
    inventory = onboarding.discover(project, kit)
    return inventory, onboarding.static_plan(inventory)


@pytest.mark.parametrize("old", [
    b'{\r\n // preserve comment\r\n "version":"2.0.0",\r\n "tasks":[{"label":"Mine","command":"echo","args":["x ] , } // literal /* text"]}, /* tail */],\r\n}',
    b'{"version":"2.0.0", // preserve comment\n}',
    b'\xef\xbb\xbf{ /* preserve comment */ "version":"2.0.0", "tasks": [ /* empty list */ ], "inputs": [],}',
    b'{"version":"2.0.0","tasks":[{"label":"Mine","command":"C:\\\\path\\\\script.exe"}],"inputs":[{"id":"mine","type":"promptString"}]}',
])
def test_jsonc_comments_literals_trailing_commas_and_idempotence(old):
    incoming = {"version": "2.0.0", "tasks": [{"label": "Engineering: Review", "command": "python"}],
                "inputs": [{"id": "engineeringTask", "type": "promptString"}]}
    original = json.loads(install.jsonc_mask(old.decode("utf-8-sig")))
    merged = install.merge_tasks(old, incoming)
    parsed = json.loads(install.jsonc_mask(merged.decode("utf-8-sig")))
    for task in original.get("tasks", []):
        assert task in parsed["tasks"]
    for value in original.get("inputs", []):
        assert value in parsed["inputs"]
    if b"preserve comment" in old:
        assert b"preserve comment" in merged
    assert merged.startswith(b"\xef\xbb\xbf") == old.startswith(b"\xef\xbb\xbf")
    assert install.merge_tasks(merged, incoming) == merged


def test_jsonc_conflicting_label_is_not_overwritten():
    old = b'{"tasks":[{"label":"Engineering: Review","command":"my-custom-command"}]}'
    with pytest.raises(install.Conflict, match="conflicts"):
        install.merge_tasks(old, {"tasks": [{"label": "Engineering: Review", "command": "python"}]})


def test_toml_append_preserves_existing_bytes_and_new_destination(tmp_path):
    project = tmp_path / "destination with spaces and apostrophe's"
    project.mkdir()
    old = b'# retained owner comment\r\nmodel="custom-existing"\r\n[mcp_servers.other]\r\ncommand="another"\r\nenv={FAKE_TOKEN="not-a-real-secret"}\r\n'
    new = install.mcp_config(project, old)
    assert new.startswith(old)
    parsed = tomllib.loads(new.decode())
    assert parsed["model"] == "custom-existing"
    assert parsed["mcp_servers"]["other"]["env"]["FAKE_TOKEN"] == "not-a-real-secret"
    configured = parsed["mcp_servers"]["workspace-engineering"]
    assert configured["command"] == str(project / "tools/engineering/.venv/Scripts/python.exe")
    assert configured["args"][-2:] == [str(project), "mcp"]
    assert install.mcp_config(project, new) == new


def test_toml_conflict_does_not_modify_existing_file(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    path = root / ".codex/config.toml"
    path.parent.mkdir()
    data = b'[mcp_servers.workspace-engineering]\ncommand="existing-owner"\n'
    path.write_bytes(data)
    with pytest.raises(install.Conflict, match="differs"):
        install.mcp_config(root, path.read_bytes())
    assert path.read_bytes() == data


def test_non_git_containers_and_invalid_git_markers_are_not_registered(tmp_path):
    project = tmp_path / "plain"
    project.mkdir()
    for relative in ("services/api", "tools/api"):
        git_init(project / relative)
        (project / relative / "package.json").write_text('{"name":"fixture","scripts":{"test":"never-execute"}}')
    invalid = project / "invalid"
    invalid.mkdir()
    (invalid / ".git").write_text("invalid Git pointer\n")
    inventory, plan = prepare(project, tmp_path / "kit")
    registry, _ = install.catalogs(inventory, plan)
    assert len(registry["repositories"]) == 2
    assert {v["path"] for v in registry["repositories"].values()} == {"services/api", "tools/api"}
    assert "workspace" not in registry["repositories"]


def test_subfolder_of_git_root_is_not_registered_as_its_own_repo(tmp_path):
    git_init(tmp_path / "parent")
    selected = tmp_path / "parent/subfolder"
    selected.mkdir()
    (selected / "package.json").write_text('{"name":"fixture"}')
    inventory, plan = prepare(selected, tmp_path / "kit")
    registry, _ = install.catalogs(inventory, plan)
    assert registry["repositories"] == {}


def test_source_change_during_tailoring_blocks_installation(tmp_path, monkeypatch):
    project = tmp_path / "project"
    git_init(project)
    manifest = project / "package.json"
    manifest.write_text('{"name":"before"}')
    kit = minimal_kit(tmp_path)
    monkeypatch.setattr(install, "KIT", kit)

    def tailor(root, inventory, output, **kwargs):
        result = onboarding.static_plan(inventory)
        result["mode"] = "model"
        manifest.write_text('{"name":"changed-during-analysis"}')
        return result

    monkeypatch.setattr(onboarding, "tailor", tailor)
    with pytest.raises(install.Conflict, match="Source changed"):
        install.main(["--project-root", str(project)])
    assert not (project / ".codex/config.toml").exists()
    assert not (project / "AGENTS.md").exists()
    assert manifest.read_text() == '{"name":"changed-during-analysis"}'


def test_managed_section_edits_are_preserved_on_rerun(tmp_path):
    project = tmp_path / "project"
    git_init(project)
    kit = minimal_kit(tmp_path)
    inventory, plan = prepare(project, kit)
    changes = install.plan_install(project, kit, inventory, plan)
    install.apply(project, changes, project / ".engineering-state/setup/first")
    agents = project / "AGENTS.md"
    edited = agents.read_bytes().replace(b"## Engineering workflow", b"## Owner's revised engineering workflow")
    agents.write_bytes(edited)
    inventory, plan = prepare(project, kit)
    with pytest.raises(install.Conflict, match="locally edited"):
        install.plan_install(project, kit, inventory, plan)
    assert agents.read_bytes() == edited


def test_rollback_refuses_later_edits_before_restoring_any_file(tmp_path):
    project = tmp_path / "project"
    git_init(project)
    kit = minimal_kit(tmp_path)
    inventory, plan = prepare(project, kit)
    changes = install.plan_install(project, kit, inventory, plan)
    receipt = install.apply(project, changes, project / ".engineering-state/setup/first")
    (project / "tools/engineering/README.md").write_text("owner's later work\n")
    current = {change["path"]: (project / change["path"]).read_bytes() for change in changes}
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(project, receipt)
    assert current == {name: (project / name).read_bytes() for name in current}


def test_first_repeat_install_is_idempotent(tmp_path):
    project = tmp_path / "project"
    git_init(project)
    (project / "package.json").write_text('{"name":"fixture"}')
    kit = minimal_kit(tmp_path)
    inventory, plan = prepare(project, kit)
    install.apply(project, install.plan_install(project, kit, inventory, plan), project / ".engineering-state/setup/first")
    repeated_inventory, repeated_plan = prepare(project, kit)
    repeated = install.plan_install(project, kit, repeated_inventory, repeated_plan)
    assert repeated == [], [item["path"] for item in repeated]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell contract")
def test_native_powershell_setup_handles_spaces_and_apostrophes(tmp_path):
    project = tmp_path / "project with apostrophe's"
    git_init(project)
    (project / "package.json").write_text('{"name":"fixture"}')
    command = [shutil.which("powershell.exe"), "-NoProfile", "-File", str(KIT / "Setup.ps1"),
               "-ProjectRoot", str(project), "-Python", sys.executable, "-Static", "-PlanOnly", "-SkipDependencies"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Plan saved:" in result.stdout
    assert not (project / ".codex/config.toml").exists()
    assert not (project / "tools/engineering/.venv").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell contract")
def test_relocated_kit_installs_destination_paths_without_dependencies(tmp_path):
    relocated = tmp_path / "portable kit's copy"
    shutil.copytree(KIT, relocated, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    project = tmp_path / "different destination's repo"
    git_init(project)
    (project / "package.json").write_text('{"name":"relocated-fixture"}')
    command = [shutil.which("powershell.exe"), "-NoProfile", "-File", str(relocated / "Setup.ps1"),
               "-ProjectRoot", str(project), "-Python", sys.executable, "-Static", "-SkipDependencies"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    config = tomllib.loads((project / ".codex/config.toml").read_text())
    server = config["mcp_servers"]["workspace-engineering"]
    assert server["command"] == str(project / "tools/engineering/.venv/Scripts/python.exe")
    assert server["args"][-2:] == [str(project), "mcp"]
    assert (project / "tools/engineering/src/workspace_engineering/coordinator.py").is_file()
    assert not (project / "tools/engineering/.venv").exists()
    assert (project / "package.json").read_text() == '{"name":"relocated-fixture"}'
