"""Exercise the shipped REA instructions without registering or calling REA."""
import hashlib
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

MODULE = "reverse-engineer-anything"
SKILL = f".agents/skills/{MODULE}"
PAYLOAD = KIT / "modules" / MODULE / "payload"


@pytest.fixture
def destination(tmp_path):
    project = tmp_path / "owner's source project"
    (project / ".codex").mkdir(parents=True)
    (project / "AGENTS.md").write_bytes(b"Owner's existing instructions\r\n")
    (project / ".gitignore").write_bytes(b"owner-output/\r\n")
    (project / "source.txt").write_bytes(b"Unrelated source bytes\x00\r\n")
    (project / ".codex/config.toml").write_bytes(b'owner_setting = "preserve"\r\n')
    return project


def planned(project, modules=()):
    inventory = onboarding.discover(project, KIT)
    return install.plan_install(project, KIT, inventory, onboarding.static_plan(inventory), modules)


def installed(project, modules=(), name="install"):
    return install.apply(project, planned(project, modules), project / ".engineering-state/setup" / name)


def state(project):
    return json.loads((project / install.STATE).read_bytes())


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_default_installs_routing_guide_without_optional_rea(destination):
    installed(destination)
    assert MODULE not in state(destination)["modules"]
    assert not (destination / SKILL).exists()
    assert b"## Artifact investigation" not in (destination / "AGENTS.md").read_bytes()
    assert (destination / "dev-docs/engineering-automation/agent-routing.md").is_file()


def test_real_rea_payload_install_repeat_rollback_and_reinstall(destination):
    before = files(destination)
    bundled = install.payload_files(KIT, "modules/reverse-engineer-anything/payload")
    receipt = installed(destination, [MODULE, MODULE])
    assert state(destination)["modules"] == [MODULE]
    for relative, content in bundled.items():
        assert (destination / relative).read_bytes() == content
    assert b"## Artifact investigation" in (destination / "AGENTS.md").read_bytes()
    assert (destination / "source.txt").read_bytes() == before["source.txt"]
    config = (destination / ".codex/config.toml").read_bytes()
    assert config.startswith(before[".codex/config.toml"])
    assert b"mcp_servers.rea" not in config
    assert planned(destination, [MODULE]) == []
    assert planned(destination) == []
    install.rollback(destination, receipt)
    for relative, content in before.items():
        assert (destination / relative).read_bytes() == content
    assert not any((destination / relative).exists() for relative in bundled)
    assert not (destination / install.STATE).exists()
    installed(destination, [MODULE], "reinstall")
    assert planned(destination) == []


def test_rea_addition_coexists_with_other_modules_and_rolls_back_independently(destination):
    installed(destination, ["claudely", "idea-research", "blueprint-first"], "existing")
    before = files(destination)
    receipt = installed(destination, [MODULE], "rea-addition")
    assert state(destination)["modules"] == sorted(install.MODULES)
    assert planned(destination) == []
    assert (destination / ".agents/skills/claudely/SKILL.md").is_file()
    install.rollback(destination, receipt)
    assert state(destination)["modules"] == ["blueprint-first", "claudely", "idea-research"]
    assert planned(destination) == []
    assert not (destination / SKILL / "SKILL.md").exists()
    for relative, content in before.items():
        assert (destination / relative).read_bytes() == content


def test_complete_independent_rea_skill_gets_no_support_or_attribution_overlay(destination):
    folder = destination / SKILL
    (folder / "references").mkdir(parents=True)
    (folder / "SKILL.md").write_bytes(b"Owner's independent REA procedure\r\n")
    (folder / "references/owner.txt").write_bytes(b"Owner reference\n")
    before = files(folder)
    receipt = installed(destination, [MODULE])
    assert files(folder) == before
    assert not any(name.startswith(SKILL + "/") for name in state(destination)["files"])
    assert planned(destination) == []
    install.rollback(destination, receipt)
    assert files(folder) == before


def test_owned_rea_edit_blocks_repeat_and_rollback_without_other_writes(destination):
    receipt = installed(destination, [MODULE])
    target = destination / SKILL / "references/evidence-workflows.md"
    target.write_bytes(target.read_bytes() + b"\nOwner's later change\n")
    before = files(destination)
    with pytest.raises(install.Conflict, match="Existing file differs"):
        planned(destination)
    assert files(destination) == before
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(destination, receipt)
    assert files(destination) == before


def test_rea_provenance_binds_seven_files_and_exact_distributed_license():
    folder = PAYLOAD / SKILL
    record = json.loads((folder / "SOURCE.json").read_bytes())
    assert len(record["skill_files"]) == 7
    for relative, digest in record["skill_files"].items():
        assert hashlib.sha256((folder / relative).read_bytes()).hexdigest() == digest
    license_bytes = (folder / "LICENSE").read_bytes()
    assert hashlib.sha256(license_bytes).hexdigest() == record["license"]["sha256"]
    assert b"Copyright (c) 2026 morluto" in license_bytes


@pytest.mark.skipif(not shutil.which("powershell.exe"), reason="Windows PowerShell required")
def test_powershell_accepts_rea_and_claudely_selection(tmp_path):
    copied = tmp_path / "copied kit"
    (copied / "scripts").mkdir(parents=True)
    shutil.copyfile(KIT / "Setup.ps1", copied / "Setup.ps1")
    (copied / "scripts/install.py").write_text(
        "import json,pathlib,sys\n"
        "p=pathlib.Path(sys.argv[sys.argv.index('--project-root')+1])\n"
        "(p/'args.json').write_text(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    project = tmp_path / "destination's path"
    project.mkdir()
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = (
        f"& {quote(copied / 'Setup.ps1')} -ProjectRoot {quote(project)} -Python {quote(sys.executable)} "
        "-Modules @('claudely','reverse-engineer-anything') -Static -SkipDependencies -SkipStudio"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    arguments = json.loads((project / "args.json").read_text())
    selected = [arguments[i + 1] for i, value in enumerate(arguments) if value == "--module"]
    assert selected == ["claudely", MODULE]
    assert "--static" in arguments
    assert "Dependencies and Graphify preparation were explicitly skipped" in result.stdout
