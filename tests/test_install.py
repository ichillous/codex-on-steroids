from pathlib import Path
import json
import re
import subprocess
import sys
import tomllib

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import install
import onboarding


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "Project with spaces"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    (root / "pyproject.toml").write_text('[project]\nname="example"\nversion="0.1.0"\n[tool.pytest.ini_options]\ntestpaths=["tests"]\n')
    return root


def plans(project):
    inventory = onboarding.discover(project, install.KIT)
    plan = onboarding.static_plan(inventory)
    return inventory, plan


def test_install_rerun_and_rollback_preserve_user_files(project):
    (project / "AGENTS.md").write_bytes(b"User instructions\r\n")
    (project / ".gitignore").write_bytes(b"user-generated/\r\n")
    (project / ".codex").mkdir()
    original_config = b'# personal comment\r\nmodel = "existing-model"\r\napproval_policy = "on-request"\r\n[mcp_servers.other]\r\ncommand = "existing"\r\n'
    (project / ".codex/config.toml").write_bytes(original_config)
    (project / ".vscode").mkdir()
    original_tasks = b'{\n// Keep this comment, including punctuation ,\n"version":"2.0.0",\n"tasks":[{"label":"User task","type":"process","command":"echo"},],\n}\n'
    (project / ".vscode/tasks.json").write_bytes(original_tasks)
    index = project / ".git/index"
    index_before = index.read_bytes() if index.exists() else None
    inventory, plan = plans(project)
    changes = install.plan_install(project, install.KIT, inventory, plan)
    receipt = install.apply(project, changes, project / ".engineering-state/setup/test-install")
    assert (project / ".codex/config.toml").read_bytes().startswith(original_config)
    assert b"Keep this comment" in (project / ".vscode/tasks.json").read_bytes()
    assert (index.read_bytes() if index.exists() else None) == index_before
    assert install.plan_install(project, install.KIT, inventory, plan) == []
    registry = json.loads((project / "tools/engineering/config/repositories.yaml").read_bytes())
    assert registry["repositories"]["workspace"]["path"] == "."
    mcp = tomllib.loads((project / ".codex/config.toml").read_text())["mcp_servers"]["workspace-engineering"]
    assert mcp["args"][-2] == str(project)
    assert Path(mcp["command"]).is_relative_to(project)
    install.rollback(project, receipt)
    assert (project / ".codex/config.toml").read_bytes() == original_config
    assert (project / ".vscode/tasks.json").read_bytes() == original_tasks
    assert (project / "AGENTS.md").read_bytes() == b"User instructions\r\n"
    assert not (project / ".agents/skills/workspace-engineering/SKILL.md").exists()


def test_conflict_is_detected_before_any_configuration_write(project):
    (project / ".codex/workflows").mkdir(parents=True)
    custom = project / ".codex/workflows/engineering.md"
    custom.write_text("Existing policy")
    inventory, plan = plans(project)
    with pytest.raises(install.Conflict, match="Existing file differs"):
        install.plan_install(project, install.KIT, inventory, plan)
    assert custom.read_text() == "Existing policy"
    assert not (project / ".agents").exists()


def test_user_edits_to_owned_file_block_replacement(project):
    inventory, plan = plans(project)
    install.apply(project, install.plan_install(project, install.KIT, inventory, plan), project / ".engineering-state/setup/initial")
    role = project / ".codex/agents/reviewer.toml"
    role.write_text(role.read_text() + "\n# Local change\n")
    with pytest.raises(install.Conflict):
        install.plan_install(project, install.KIT, inventory, plan)


def test_rollback_does_not_remove_later_edits(project):
    inventory, plan = plans(project)
    receipt = install.apply(project, install.plan_install(project, install.KIT, inventory, plan), project / ".engineering-state/setup/initial")
    context = project / ".codex/project-context.md"
    context.write_text("User revised context")
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(project, receipt)
    assert context.read_text() == "User revised context"
    assert (project / ".agents/skills/workspace-engineering/SKILL.md").exists()


@pytest.mark.parametrize("text", [
    '{"tasks":[]}',
    '{"tasks":[],}',
    '{/*x*/"tasks":[{"label":"a","command":"http://localhost"},/* tail , */],}',
    '{"tasks":[{"label":"a"} // tail\n]}',
    '{"tasks":[{"label":"a"}],"inputs":[],"presentation":{"echo":true}}',
    '{"version":"2.0.0"/* comment , */}',
    '{"version":"2.0.0",/* comma , */}',
])
def test_jsonc_comments_trailing_commas_and_rerun(text):
    incoming = {"tasks": [{"label": "new", "type": "process", "command": "powershell.exe"}], "inputs": [{"id": "new-input", "type": "promptString"}]}
    first = install.merge_tasks(text.encode(), incoming)
    parsed = json.loads(install.jsonc_mask(first.decode()))
    assert parsed["tasks"][-1]["label"] == "new"
    assert install.merge_tasks(first, incoming) == first


def test_existing_mcp_configuration_conflict_preserves_bytes(project):
    original = b'[mcp_servers.workspace-engineering]\ncommand="custom"\n'
    with pytest.raises(install.Conflict, match="differs"):
        install.mcp_config(project, original)


def test_unowned_marker_does_not_overwrite_existing_instructions(project):
    original = (install.BEGIN + "\nUser customized instructions\n" + install.END).encode()
    (project / "AGENTS.md").write_bytes(original)
    inventory, plan = plans(project)
    with pytest.raises(install.Conflict, match="ownership record"):
        install.plan_install(project, install.KIT, inventory, plan)
    assert (project / "AGENTS.md").read_bytes() == original


def test_no_git_does_not_register_fake_checkout(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"app","scripts":{"test":"echo hi"}}')
    inventory, plan = plans(tmp_path)
    registry, validation = install.catalogs(inventory, plan)
    assert registry["repositories"] == {}
    assert validation["checks"] == {}


def test_payload_has_no_machine_secrets_or_venvs():
    roots = [install.KIT / "payload", *sorted((install.KIT / "modules").glob("*/payload"))]
    for root in roots:
        names = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
        assert names
        assert not any(x in name.split("/") for name in names for x in (".venv", ".venv-studio", ".venv-graphify", "__pycache__", "auth.json", "hooks.json", ".engineering-state"))
        for name in names:
            text = (root / name).read_text(encoding="utf-8-sig")
            assert not re.search(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]+", text)


def test_script_path_argument_does_not_depend_on_cwd(project, tmp_path):
    process = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(install.KIT / "Setup.ps1"), "-ProjectRoot", str(project), "-Python", sys.executable, "-Static", "-SkipDependencies"], cwd=tmp_path, capture_output=True, text=True, timeout=90)
    assert process.returncode == 0, process.stdout + process.stderr
    assert (project / ".codex/project-context.md").is_file()
    assert "Dependencies and Graphify preparation were explicitly skipped" in process.stdout


def test_existing_graphify_skill_is_preserved_and_unowned(project):
    skill = project / ".agents/skills/graphify/SKILL.md"
    skill.parent.mkdir(parents=True)
    original = b"---\nname: graphify\n---\nExisting project skill\n"
    skill.write_bytes(original)
    inventory, plan = plans(project)
    changes = install.plan_install(project, install.KIT, inventory, plan)
    assert not any(c["path"].startswith(".agents/skills/graphify/") for c in changes)
    receipt = install.apply(project, changes, project / ".engineering-state/setup/graphify-existing")
    assert skill.read_bytes() == original
    install.rollback(project, receipt)
    assert skill.read_bytes() == original


def test_missing_graphify_skill_and_environment_ignore_are_installed(project):
    inventory, plan = plans(project)
    receipt = install.apply(project, install.plan_install(project, install.KIT, inventory, plan), project / ".engineering-state/setup/graphify-new")
    skill = project / ".agents/skills/graphify/SKILL.md"
    assert skill.is_file()
    assert (project / "tools/engineering/graphify.ps1").is_file()
    assert b"/tools/engineering/.venv-graphify/" in (project / ".gitignore").read_bytes()
    assert b"Consult the publication selected by" in (project / "AGENTS.md").read_bytes()
    install.rollback(project, receipt)
    assert not skill.exists()
