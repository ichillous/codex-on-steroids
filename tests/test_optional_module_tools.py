"""Exercise shipped optional utilities with disposable synthetic inputs."""
from pathlib import Path
import json
import shutil
import subprocess
import sys


KIT = Path(__file__).resolve().parents[1]
BLUEPRINT = KIT / "modules/blueprint-first/payload/.agents/skills/blueprint-first"
RESEARCH = KIT / "modules/idea-research/payload/tools/research"


def run_python(script, *arguments):
    return subprocess.run(
        [sys.executable, "-B", str(script), *map(str, arguments)],
        capture_output=True, text=True, timeout=60,
    )


def test_research_rendering_and_input_preservation_self_check(tmp_path):
    # Run a relocated copy so the source bundle remains read-only.
    tools = tmp_path / "destination/tools/research"
    shutil.copytree(RESEARCH, tools)
    result = run_python(tools / "self_check.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Raw HTML and fenced HTML escaped" in result.stdout
    assert "preserves bytes/hash" in result.stdout
    assert "no browser/network/model calls" in result.stdout
    assert not list(tools.glob("session-fixture-*"))


def test_blueprint_starter_is_reviewable_and_cannot_pass_as_finished(tmp_path):
    target = tmp_path / "experience"
    initialized = run_python(BLUEPRINT / "scripts/init_blueprint.py", target,
                             "--name", "Synthetic experience")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    manifest = json.loads((target / "blueprint.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "Synthetic experience"
    checked = run_python(BLUEPRINT / "scripts/check_blueprint.py", target)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    report = json.loads((target / "_check/static.json").read_text(encoding="utf-8"))
    assert report["fails"], "Unmodified starter pages must remain incomplete."
    assert "still a starter page" in checked.stdout
    mapped = run_python(BLUEPRINT / "scripts/build_map.py", target)
    assert mapped.returncode == 0, mapped.stdout + mapped.stderr
    assert "Synthetic experience" in (target / "map.html").read_text(encoding="utf-8")


def test_blueprint_initializer_preserves_existing_page_without_manifest(tmp_path):
    target = tmp_path / "existing experience"
    target.mkdir()
    existing = target / "home.html"
    before = b"<!doctype html>\r\nExisting owner-authored experience\r\n"
    existing.write_bytes(before)
    result = run_python(BLUEPRINT / "scripts/init_blueprint.py", target)
    assert result.returncode != 0
    assert existing.read_bytes() == before
    assert not (target / "blueprint.json").exists()
