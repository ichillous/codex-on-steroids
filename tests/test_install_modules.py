"""Optional packages use the same ownership, conflict and rollback contract."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
import install
import onboarding


@pytest.fixture
def package(tmp_path):
    kit = tmp_path / "kit"
    files = {
        "payload/.vscode/tasks.json": '{"version":"2.0.0","tasks":[]}',
        "payload/.agents/skills/graphify/SKILL.md": "Base graph skill\n",
        "payload/.agents/skills/workspace-engineering/SKILL.md": "Base engineering skill\n",
        "payload/tools/engineering/README.md": "Base tools\n",
        "modules/idea-research/payload/.agents/skills/idea-research/SKILL.md": "Research skill\n",
        "modules/idea-research/payload/.codex/workflows/idea-research.md": "Research workflow\n",
        "modules/idea-research/payload/dev-docs/idea-research/operating-guide.md": "Research guide\n",
        "modules/idea-research/payload/tools/research/init_session.py": "# Research source\n",
        "modules/blueprint-first/payload/.agents/skills/blueprint-first/SKILL.md": "Blueprint skill\n",
        "modules/blueprint-first/payload/.agents/skills/blueprint-first/scripts/check_blueprint.py": "# Blueprint source\n",
    }
    for name, text in files.items():
        target = kit / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    project = tmp_path / "project with apostrophe's and spaces"
    project.mkdir()
    return project, kit


def planned(package, modules=()):
    project, kit = package
    inventory = onboarding.discover(project, kit)
    plan = onboarding.static_plan(inventory)
    return install.plan_install(project, kit, inventory, plan, modules)


def installed(package, modules=(), name="first"):
    project, _ = package
    return install.apply(project, planned(package, modules), project / ".engineering-state/setup" / name)


def state(project):
    return json.loads((project / install.STATE).read_bytes())


def test_default_excludes_modules_and_their_routes(package):
    project, _ = package
    installed(package)
    assert state(project)["modules"] == []
    assert not (project / ".agents/skills/idea-research").exists()
    assert not (project / ".agents/skills/blueprint-first").exists()
    assert not (project / "tools/research").exists()
    assert b"## Idea research" not in (project / "AGENTS.md").read_bytes()
    assert b"## Blueprint planning" not in (project / "AGENTS.md").read_bytes()
    assert b"/Ideas/" not in (project / ".gitignore").read_bytes()


def test_opt_in_modules_share_receipt_routing_and_rollback(package):
    project, _ = package
    (project / "AGENTS.md").write_bytes(b"Owner's existing instructions\r\n")
    (project / ".gitignore").write_bytes(b"owner-output/\r\n")
    receipt = installed(package, ["idea-research", "blueprint-first", "idea-research"])
    assert state(project)["modules"] == ["blueprint-first", "idea-research"]
    assert (project / "tools/research/init_session.py").is_file()
    assert (project / ".agents/skills/blueprint-first/scripts/check_blueprint.py").is_file()
    agents = (project / "AGENTS.md").read_bytes()
    assert agents.startswith(b"Owner's existing instructions\r\n")
    assert agents.count(install.BEGIN.encode()) == 1
    assert b"## Idea research" in agents and b"## Blueprint planning" in agents
    assert b"owner-approval gate" in agents and b"already supplied in the active session" in agents
    assert b"do not automatically start agents" in agents
    ignored = (project / ".gitignore").read_bytes()
    assert ignored.startswith(b"owner-output/\r\n")
    assert b"/Ideas/*/sessions/" in ignored and b"/Ideas/INDEX.md" in ignored
    assert b"/blueprint/_check/" in ignored
    receipt_paths = {c["path"] for c in json.loads(receipt.read_bytes())["changes"]}
    assert "tools/research/init_session.py" in receipt_paths
    assert ".agents/skills/blueprint-first/scripts/check_blueprint.py" in receipt_paths
    install.rollback(project, receipt)
    assert (project / "AGENTS.md").read_bytes() == b"Owner's existing instructions\r\n"
    assert (project / ".gitignore").read_bytes() == b"owner-output/\r\n"
    assert not (project / "tools/research/init_session.py").exists()
    assert not (project / ".agents/skills/blueprint-first/SKILL.md").exists()
    assert not (project / install.STATE).exists()


def test_incremental_opt_in_and_unflagged_rerun_preserve_ownership(package):
    project, _ = package
    installed(package)
    research_receipt = installed(package, ["idea-research"], "research")
    research_files = {name for name in state(project)["files"] if "idea-research" in name or name.startswith("tools/research/")}
    blueprint_receipt = installed(package, ["blueprint-first"], "blueprint")
    assert research_files <= set(state(project)["files"])
    assert state(project)["modules"] == ["blueprint-first", "idea-research"]
    assert planned(package) == []
    install.rollback(project, blueprint_receipt)
    assert state(project)["modules"] == ["idea-research"]
    assert planned(package) == []
    assert (project / "tools/research/init_session.py").is_file()
    assert not (project / ".agents/skills/blueprint-first/SKILL.md").exists()
    install.rollback(project, research_receipt)
    assert state(project)["modules"] == []


def test_unflagged_rerun_updates_previously_selected_module(package):
    project, kit = package
    installed(package, ["idea-research"])
    source = kit / "modules/idea-research/payload/tools/research/init_session.py"
    source.write_text("# Updated reviewed research source\n")
    changes = planned(package)
    assert "tools/research/init_session.py" in {change["path"] for change in changes}
    install.apply(project, changes, project / ".engineering-state/setup/update")
    assert (project / "tools/research/init_session.py").read_bytes() == source.read_bytes()
    assert state(project)["modules"] == ["idea-research"]


def test_legacy_base_manifest_can_add_module_and_rerun(package):
    project, _ = package
    installed(package)
    legacy = state(project)
    legacy.pop("modules")
    (project / install.STATE).write_bytes(install.encoded(legacy))
    receipt = installed(package, ["idea-research"], "from-legacy")
    assert state(project)["modules"] == ["idea-research"]
    assert planned(package) == []
    install.rollback(project, receipt)
    assert (project / install.STATE).read_bytes() == install.encoded(legacy)
    assert not (project / "tools/research/init_session.py").exists()


def test_full_rollback_then_reinstall_accepts_empty_owned_directories(package):
    project, _ = package
    receipt = installed(package, ["idea-research", "blueprint-first"])
    install.rollback(project, receipt)
    assert (project / ".agents/skills/blueprint-first/scripts").is_dir()
    installed(package, ["idea-research", "blueprint-first"], "reinstall")
    assert (project / ".agents/skills/graphify/SKILL.md").is_file()
    assert (project / ".agents/skills/blueprint-first/scripts/check_blueprint.py").is_file()
    assert planned(package) == []


def test_optional_rollback_then_reselect_accepts_empty_owned_directories(package):
    project, _ = package
    installed(package)
    receipt = installed(package, ["blueprint-first"], "opt-in")
    install.rollback(project, receipt)
    assert state(project)["modules"] == []
    assert (project / ".agents/skills/blueprint-first/scripts").is_dir()
    installed(package, ["blueprint-first"], "reselect")
    assert state(project)["modules"] == ["blueprint-first"]
    assert (project / ".agents/skills/blueprint-first/scripts/check_blueprint.py").is_file()
    assert planned(package) == []


@pytest.mark.parametrize("relative", [".codex/workflows/idea-research.md", "dev-docs/idea-research/operating-guide.md"])
def test_unowned_module_workflow_or_guide_conflict_precedes_all_writes(package, relative):
    project, _ = package
    custom = project / relative
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"Existing owner's policy\r\n")
    with pytest.raises(install.Conflict, match="Existing file differs"):
        planned(package, ["idea-research"])
    assert custom.read_bytes() == b"Existing owner's policy\r\n"
    assert not (project / "AGENTS.md").exists()
    assert not (project / install.STATE).exists()


@pytest.mark.parametrize("skill", ["graphify", "workspace-engineering", "idea-research", "blueprint-first"])
def test_independent_skill_folder_is_preserved_without_partial_overlay(package, skill):
    project, _ = package
    folder = project / ".agents/skills" / skill
    folder.mkdir(parents=True)
    original = b"Owner's complete independent skill\n"
    (folder / "SKILL.md").write_bytes(original)
    (folder / "owner-data.txt").write_text("Keep this\n")
    receipt = installed(package, ["idea-research", "blueprint-first"])
    prefix = f".agents/skills/{skill}/"
    assert not any(name.startswith(prefix) for name in state(project)["files"])
    assert not (folder / "scripts/check_blueprint.py").exists()
    assert (folder / "SKILL.md").read_bytes() == original
    install.rollback(project, receipt)
    assert (folder / "SKILL.md").read_bytes() == original
    assert (folder / "owner-data.txt").read_text() == "Keep this\n"


def test_incomplete_independent_skill_fails_without_mixing_owners(package):
    project, _ = package
    folder = project / ".agents/skills/blueprint-first"
    folder.mkdir(parents=True)
    (folder / "owner-data.txt").write_text("Keep this\n")
    with pytest.raises(install.Conflict, match="Independent skill folder is incomplete"):
        planned(package, ["blueprint-first"])
    assert not (folder / "SKILL.md").exists()
    assert not (project / "AGENTS.md").exists()


def test_owned_module_edits_block_unflagged_rerun_and_rollback(package):
    project, _ = package
    receipt = installed(package, ["idea-research"])
    path = project / "tools/research/init_session.py"
    path.write_bytes(b"# Owner's later changes\n")
    with pytest.raises(install.Conflict, match="Existing file differs"):
        planned(package)
    before = (project / "AGENTS.md").read_bytes()
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(project, receipt)
    assert path.read_bytes() == b"# Owner's later changes\n"
    assert (project / "AGENTS.md").read_bytes() == before


@pytest.mark.parametrize("name", ["unknown", "../idea-research", "C:/outside"])
def test_unknown_module_does_not_select_arbitrary_payload(package, name):
    with pytest.raises(install.Conflict, match="known optional modules"):
        planned(package, [name])


def test_invalid_persisted_selection_is_not_treated_as_package_authority(package):
    project, _ = package
    installed(package)
    manifest = state(project)
    manifest["modules"] = ["../outside"]
    (project / install.STATE).write_bytes(install.encoded(manifest))
    with pytest.raises(install.Conflict, match="unsupported optional modules"):
        planned(package)


def test_missing_previously_selected_package_fails_without_dropping_ownership(package):
    project, kit = package
    installed(package, ["idea-research"])
    root = kit / "modules/idea-research/payload"
    root.rename(root.with_name("retained-payload"))
    before = (project / install.STATE).read_bytes()
    with pytest.raises(install.Conflict, match="Package payload is missing"):
        planned(package)
    assert (project / install.STATE).read_bytes() == before


def test_module_cannot_overlap_base_payload(package):
    _, kit = package
    source = kit / "modules/idea-research/payload/tools/engineering/README.md"
    source.parent.mkdir(parents=True)
    source.write_text("Attempted base overlay\n")
    with pytest.raises(install.Conflict, match="overlaps another package file"):
        planned(package, ["idea-research"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction package contract")
def test_module_payload_junction_is_rejected_before_destination_writes(package):
    project, kit = package
    source = kit / "modules/idea-research/payload"
    retained = source.with_name("retained-payload")
    source.rename(retained)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(source), str(retained)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(install.Conflict, match="symlink or junction"):
        planned(package, ["idea-research"])
    assert not (project / "AGENTS.md").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction package contract")
def test_module_internal_directory_junction_is_rejected(package):
    project, kit = package
    source = kit / "modules/idea-research/payload/tools/linked"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(source), str(kit / "payload/tools")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(install.Conflict, match="symlink or junction"):
        planned(package, ["idea-research"])
    assert not (project / "AGENTS.md").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction destination contract")
def test_module_destination_directory_junction_is_rejected_without_writes(package):
    project, _ = package
    (project / "tools").mkdir()
    outside = project.parent / "retained independent destination"
    outside.mkdir()
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(project / "tools/research"), str(outside)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(install.Conflict, match="symlink or junction"):
        planned(package, ["idea-research"])
    assert list(outside.iterdir()) == []
    assert not (project / "AGENTS.md").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction project-root contract")
def test_python_cli_rejects_project_root_junction_before_analysis(package, monkeypatch):
    project, kit = package
    linked = project.parent / "project junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(linked), str(project)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    monkeypatch.setattr(install, "KIT", kit)
    with pytest.raises(SystemExit) as stopped:
        install.main(["--project-root", str(linked), "--static", "--module", "idea-research"])
    assert stopped.value.code == 2
    assert not (project / ".engineering-state").exists()


@pytest.mark.skipif(not shutil.which("powershell.exe"), reason="Windows PowerShell required")
def test_powershell_modules_array_becomes_repeatable_python_arguments(tmp_path):
    kit = tmp_path / "copied kit"
    (kit / "scripts").mkdir(parents=True)
    shutil.copyfile(KIT / "Setup.ps1", kit / "Setup.ps1")
    (kit / "scripts/install.py").write_text(
        "import json,pathlib,sys\n"
        "p=pathlib.Path(sys.argv[sys.argv.index('--project-root')+1])\n"
        "(p/'setup-args.json').write_text(json.dumps(sys.argv[1:]))\n"
    )
    project = tmp_path / "destination with apostrophe's"
    project.mkdir()
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = f"& {quote(kit / 'Setup.ps1')} -ProjectRoot {quote(project)} -Python {quote(sys.executable)} -Static -SkipDependencies -Modules @('idea-research','blueprint-first')"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    args = json.loads((project / "setup-args.json").read_text())
    assert args.count("--module") == 2
    assert [args[i + 1] for i, item in enumerate(args) if item == "--module"] == ["idea-research", "blueprint-first"]
    assert "--static" in args
    assert "Dependencies and Graphify preparation were explicitly skipped" in result.stdout


def test_python_cli_module_plan_only_is_non_installing(package, monkeypatch):
    project, kit = package
    monkeypatch.setattr(install, "KIT", kit)
    assert install.main(["--project-root", str(project), "--static", "--plan-only", "--module", "idea-research", "--module", "blueprint-first"]) == 0
    assert not (project / "AGENTS.md").exists()
    assert not (project / install.STATE).exists()
    outputs = list((project / ".engineering-state/setup").glob("*/planned-files.json"))
    assert len(outputs) == 1
    planned_paths = {item["path"] for item in json.loads(outputs[0].read_bytes())}
    assert "tools/research/init_session.py" in planned_paths
    assert ".agents/skills/blueprint-first/SKILL.md" in planned_paths
