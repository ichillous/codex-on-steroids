"""Install the shipped claudely skill under the real preservation contract."""
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

SKILL = ".agents/skills/claudely"
PAYLOAD = KIT / "modules/claudely/payload"


@pytest.fixture
def destination(tmp_path):
    project = tmp_path / "owner's existing project"
    project.mkdir()
    (project / "AGENTS.md").write_bytes(b"Owner's instructions\r\n")
    (project / ".gitignore").write_bytes(b"owner-output/\r\n")
    (project / "owner.txt").write_bytes(b"Existing unrelated destination bytes\x00\r\n")
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


def test_default_install_does_not_enable_claudely(destination):
    installed(destination)
    assert "claudely" not in state(destination)["modules"]
    assert not (destination / SKILL).exists()
    assert b"## Claudely" not in (destination / "AGENTS.md").read_bytes()


def test_shipped_claudely_install_repeat_and_rollback_preserve_destination(destination):
    before = files(destination)
    bundled = install.payload_files(KIT, "modules/claudely/payload")
    assert f"{SKILL}/SKILL.md" in bundled
    receipt = installed(destination, ["claudely", "claudely"])
    assert state(destination)["modules"] == ["claudely"]
    for relative, content in bundled.items():
        assert (destination / relative).read_bytes() == content
    assert b"## Claudely" in (destination / "AGENTS.md").read_bytes()
    assert (destination / "AGENTS.md").read_bytes().startswith(before["AGENTS.md"])
    assert (destination / "owner.txt").read_bytes() == before["owner.txt"]
    assert planned(destination, ["claudely"]) == []
    assert planned(destination) == []
    install.rollback(destination, receipt)
    for relative, content in before.items():
        assert (destination / relative).read_bytes() == content
    assert not (destination / install.STATE).exists()
    assert not any((destination / relative).exists() for relative in bundled)
    # Rollback can leave empty folders; a subsequent real install accepts them.
    installed(destination, ["claudely"], "reinstall")
    assert planned(destination) == []


def test_incremental_claudely_receipt_removes_only_that_addition(destination):
    installed(destination, ["idea-research"], "base")
    previous = files(destination)
    receipt = installed(destination, ["claudely"], "claudely")
    assert state(destination)["modules"] == ["claudely", "idea-research"]
    assert planned(destination) == []
    install.rollback(destination, receipt)
    assert state(destination)["modules"] == ["idea-research"]
    assert planned(destination) == []
    assert not (destination / SKILL / "SKILL.md").exists()
    for relative, content in previous.items():
        assert (destination / relative).read_bytes() == content


def test_independent_claudely_folder_is_preserved_without_overlay(destination):
    folder = destination / SKILL
    (folder / "references").mkdir(parents=True)
    (folder / "SKILL.md").write_bytes(b"Owner's independent claudely skill\r\n")
    (folder / "references/owner.txt").write_bytes(b"Owner's reference\n")
    before = files(folder)
    receipt = installed(destination, ["claudely"])
    assert files(folder) == before
    assert not any(name.startswith(SKILL + "/") for name in state(destination)["files"])
    assert planned(destination) == []
    install.rollback(destination, receipt)
    assert files(folder) == before


def test_modified_owned_claudely_blocks_update_and_rollback_without_partial_writes(destination):
    receipt = installed(destination, ["claudely"])
    path = destination / SKILL / "SKILL.md"
    path.write_bytes(path.read_bytes() + b"\nOwner's later adjustment\n")
    before = files(destination)
    with pytest.raises(install.Conflict, match="Existing file differs"):
        planned(destination)
    assert files(destination) == before
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(destination, receipt)
    assert files(destination) == before


def test_claudely_powershell_selection_uses_supported_installer_argument(tmp_path):
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
        f"& {quote(copied / 'Setup.ps1')} -ProjectRoot {quote(project)} "
        f"-Python {quote(sys.executable)} -Modules claudely -Static -SkipDependencies -SkipStudio"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    arguments = json.loads((project / "args.json").read_text())
    assert arguments[arguments.index("--module") + 1] == "claudely"
    assert "--static" in arguments
    assert "Dependencies and Graphify preparation were explicitly skipped" in result.stdout
