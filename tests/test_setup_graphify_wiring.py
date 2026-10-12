"""Real PowerShell setup control-flow checks with disposable, offline stubs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not shutil.which("powershell.exe"), reason="Windows PowerShell required")


def fixture_setup(tmp_path, graph_exit=0):
    project = tmp_path / "Project's source with spaces"
    project.mkdir()
    kit = tmp_path / "Toolkit's copied kit"
    (kit / "scripts").mkdir(parents=True)
    shutil.copyfile(KIT / "Setup.ps1", kit / "Setup.ps1")
    (kit / "scripts/install.py").write_text(
        "import pathlib,sys\n"
        "p=pathlib.Path(sys.argv[sys.argv.index('--project-root')+1])\n"
        "with (p/'order.txt').open('a') as f: f.write('install\\n')\n"
    )
    engineering = project / "tools/engineering"
    studio = engineering / "experiments/autogen"
    studio.mkdir(parents=True)
    (engineering / "graphify_setup.py").write_text(
        "import json,pathlib,sys\n"
        "p=pathlib.Path(sys.argv[sys.argv.index('--project-root')+1])\n"
        "(p/'graph-args.json').write_text(json.dumps(sys.argv[1:]))\n"
        "with (p/'order.txt').open('a') as f: f.write('graphify\\n')\n"
        f"sys.exit({graph_exit})\n"
    )
    (engineering / "bootstrap.ps1").write_text(
        "param([string]$Python,[switch]$SkipDoctor)\n"
        "Add-Content -LiteralPath (Join-Path $PSScriptRoot '../../order.txt') -Value 'engineering'\nexit 0\n"
    )
    (studio / "bootstrap.ps1").write_text(
        "param([string]$Python)\n"
        "Add-Content -LiteralPath (Join-Path $PSScriptRoot '../../../../order.txt') -Value 'studio'\nexit 0\n"
    )
    return project, kit


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_setup(project, kit, extra=""):
    command = f"& {ps_literal(kit / 'Setup.ps1')} -ProjectRoot {ps_literal(project)} -Python {ps_literal(sys.executable)} -Static {extra}"
    return subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=60)


def test_default_prepares_graph_before_other_environments_with_exact_scopes(tmp_path):
    project, kit = fixture_setup(tmp_path)
    result = run_setup(project, kit, f"-GraphifyPython {ps_literal(sys.executable)} -GraphifyScope @('src with spaces','tests')")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project / "order.txt").read_text().splitlines() == ["install", "graphify", "engineering", "studio"]
    assert json.loads((project / "graph-args.json").read_text()) == [
        "--project-root", str(project), "--python", sys.executable,
        "--scope", "src with spaces", "--scope", "tests",
    ]


@pytest.mark.parametrize("flag", ["-PlanOnly", "-SkipDependencies"])
def test_explicit_deferred_modes_do_not_prepare_graph_or_bootstrap(tmp_path, flag):
    project, kit = fixture_setup(tmp_path)
    result = run_setup(project, kit, flag)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (project / "order.txt").read_text().splitlines() == ["install"]
    assert not (project / "graph-args.json").exists()


def test_graph_failure_stops_setup_before_other_environments(tmp_path):
    project, kit = fixture_setup(tmp_path, graph_exit=1)
    result = run_setup(project, kit)
    assert result.returncode != 0
    assert "Graphify preparation failed" in result.stdout + result.stderr
    assert (project / "order.txt").read_text().splitlines() == ["install", "graphify"]
