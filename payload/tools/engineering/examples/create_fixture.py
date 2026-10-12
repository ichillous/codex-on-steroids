"""Create a disposable, explicitly synthetic live engineering smoke fixture.

The generator never calls a model. It creates a new independent Git repository
under .engineering-state/fixtures, commits its initial synthetic files, and
prints the command for a human-authorized coordinator run. No existing checkout
is moved, staged, reset, or deleted.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROLES = ("investigator", "implementer", "reviewer", "oracle-specialist", "ui-specialist", "integration-specialist")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_fixture(workspace: Path, output_parent: Path | None = None) -> dict:
    workspace = workspace.resolve()
    launcher = workspace / "tools/engineering/eng.ps1"
    copies = [Path(".codex/agents") / f"{role}.toml" for role in ROLES]
    copies += [Path(value) for value in (
        ".codex/workflows/engineering.md", ".codex/prompts/engineering-task.md",
        ".codex/references/graphify-read-only.md", "tools/engineering/config/workflows.yaml",
        "tools/engineering/config/tools.yaml",
    )]
    missing = [str(path) for path in [launcher, *(workspace / name for name in copies)] if not path.is_file()]
    if missing:
        raise ValueError("Fixture prerequisites missing: " + ", ".join(missing))
    if shutil.which("git") is None:
        raise ValueError("Git must be available to initialize an independent fixture")
    parent = (output_parent or workspace / ".engineering-state/fixtures").resolve()
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="arithmetic-", dir=parent)).resolve()
    # Only the new, unique fixture receives copied local instructions. Global
    # credentials/model settings remain owned by the actual Codex installation.
    for relative in copies:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workspace / relative, target)
    (root / "AGENTS.md").write_text(
        "# Synthetic engineering acceptance fixture\n\n"
        "This directory is a newly created, independent Git repository containing artificial Python code. "
        "It is separate from the destination application. Only the `workspace` repository identity exists here.\n\n"
        "Read `.codex/workflows/engineering.md`; apply its evidence, preservation, and validation principles "
        "to this small fixture. References there to application repositories and production systems describe "
        "the source workspace, not dependencies of this fixture. No such systems need to be read or contacted.\n\n"
        "Resolve the local `graphify-out/LATEST.md`. Its graph is explicitly SYNTHETIC and only describes "
        "`calc.py` and `test_calc.py`. Verify its tiny source anchors locally.\n\n"
        "Fix only the supplied arithmetic defect under the task's path scope. Preserve the existing test cases, "
        "configuration, instructions, publication, and Git index. Run the registered fixture-pytest check. "
        "Do not install packages, change another repository, recursively delegate, commit, publish, or contact a database.\n",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(".engineering-state/\n__pycache__/\n.pytest_cache/\n.venv/\n", encoding="utf-8")
    (root / "calc.py").write_text(
        '"""Synthetic arithmetic example for coordinator acceptance testing."""\n\n'
        "def add(a: int, b: int) -> int:\n"
        '    """Return the arithmetic sum of two integers."""\n'
        "    return a - b\n",
        encoding="utf-8",
    )
    (root / "test_calc.py").write_text(
        "import pytest\n\nfrom calc import add\n\n"
        '@pytest.mark.parametrize("a,b,expected", [(2, 3, 5), (-2, -3, -5), (-2, 5, 3), (0, 0, 0)])\n'
        "def test_add_returns_arithmetic_sum(a, b, expected):\n"
        "    assert add(a, b) == expected\n",
        encoding="utf-8",
    )
    # JSON is a YAML subset, so these catalogs need no generator dependencies.
    write_json(root / "tools/engineering/config/repositories.yaml", {
        "version": 1, "repositories": {"workspace": {"path": ".", "instructions": ["AGENTS.md", ".codex/workflows/engineering.md"],
        "toolchain": "Active isolated engineering Python with pytest", "dependencies": [], "applications": ["synthetic arithmetic fixture"],
        "snapshot_excludes": ["graphify-out"]}},
    })
    write_json(root / "tools/engineering/config/validation.yaml", {
        "version": 1, "checks": {"fixture-pytest": {
            "repo": "workspace", "kind": "test", "automatic": True, "cwd": ".",
            "argv": ["{python}", "-B", "-m", "pytest", "test_calc.py", "-q", "-p", "no:cacheprovider"],
            "timeout_seconds": 60, "parser": "pytest", "requires": ["calc.py", "test_calc.py"],
            "effects": ["Execute four synthetic arithmetic cases", "Write the coordinator validation log"],
            "source": ["test_calc.py"], "notes": ["Synthetic smoke evidence only; no application coverage or model execution is implied."]}}})
    publication = root / "graphify-out/synthetic-fixture"
    graph = {
        "directed": True, "multigraph": False, "graph": {"synthetic": True, "purpose": "Disposable arithmetic acceptance fixture"},
        "nodes": [
            {"id": "workspace::fixture_add", "label": "Synthetic add arithmetic function", "repo": "workspace", "source_file": "calc.py", "source_location": "L3-L5", "_origin": "synthetic_fixture", "confidence": "EXTRACTED"},
            {"id": "workspace::fixture_tests", "label": "Synthetic arithmetic regression tests", "repo": "workspace", "source_file": "test_calc.py", "source_location": "L5-L7", "_origin": "synthetic_fixture", "confidence": "EXTRACTED"},
        ],
        "links": [{"source": "workspace::fixture_tests", "target": "workspace::fixture_add", "relation": "tests",
                   "confidence": "EXTRACTED", "_origin": "synthetic_fixture", "evidence_repo": "workspace",
                   "source_file": "test_calc.py", "source_location": "L5-L7"}],
    }
    write_json(publication / "graph.json", graph)
    write_json(publication / "publication.json", {
        "published_at": datetime.now(timezone.utc).isoformat(), "graph_sha256": checksum(publication / "graph.json"),
        "status": "synthetic_fixture", "synthetic": True,
    })
    write_json(publication / "source-inventory.json", {"workspace": {"current": {name: checksum(root / name) for name in ("calc.py", "test_calc.py")}}})
    (publication / "REFRESH_REPORT.md").write_text(
        "# SYNTHETIC fixture graph\n\nTwo nodes and one test relationship cover only the newly generated "
        "calc.py/test_calc.py fixture. This is handcrafted synthetic evidence, not Graphify extraction "
        "or application architecture. Current source hashes describe the initial buggy baseline. "
        "A successful repair makes calc.py freshness stale; verify the changed source directly.\n",
        encoding="utf-8",
    )
    (root / "graphify-out/LATEST.md").write_text(
        "# SYNTHETIC fixture publication\n\n[Current combined graph JSON](synthetic-fixture/graph.json)\n\n"
        "Handcrafted evidence only for this disposable arithmetic task. See synthetic-fixture/REFRESH_REPORT.md.\n",
        encoding="utf-8",
    )
    task_path = root / "task.json"
    write_json(task_path, {
        "title": "Repair the synthetic integer addition fixture", "mode": "implement",
        "request": "Fix the arithmetic defect in calc.py so add returns a + b. Preserve the existing regression cases and all configuration/instructions/graph files. This is an authorized disposable synthetic fixture; run fixture-pytest and independently review its source, test counts, and diff. Do not change or inspect the original application's source.",
        "acceptance_criteria": ["add returns the arithmetic sum for the supplied positive, negative, mixed-sign and zero integer cases.",
                                "fixture-pytest passes with all four existing cases executed and no skips.",
                                "Only calc.py changes; the existing test cases, configuration and Git index remain unchanged."],
        "repositories": ["workspace"], "scope": {"workspace": ["calc.py", "test_calc.py"]},
        "graph_terms": ["Synthetic add arithmetic function", "Synthetic arithmetic regression tests"],
        "checks": ["fixture-pytest"], "max_workers": 2, "max_revisions": 1,
    })
    # Git operations below target only the mkdtemp-created fixture. Disabling
    # templates, hooks and signing avoids inheriting unrelated user automation.
    subprocess.run(["git", "init", "--quiet", "--initial-branch=fixture", "--template=", str(root)], check=True, capture_output=True)
    git = ["git", "-C", str(root), "-c", f"core.hooksPath={root / '.git/fixture-hooks'}",
           "-c", "commit.gpgsign=false", "-c", "user.name=Engineering Fixture",
           "-c", "user.email=engineering-fixture@example.invalid"]
    subprocess.run([*git, "add", "--all"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "--quiet", "--no-verify", "-m", "Initial synthetic arithmetic fixture"], check=True, capture_output=True)
    quoted = lambda path: "'" + str(path).replace("'", "''") + "'"
    return {
        "root": str(root), "task": str(task_path), "synthetic": True, "models_called": False,
        "expected_initial_tests": "3 failed, 1 passed", "expected_repaired_tests": "4 passed",
        "command": f"& {quoted(launcher)} --workspace {quoted(root)} run --task {quoted(task_path)}",
        "argv": [str(launcher), "--workspace", str(root), "run", "--task", str(task_path)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-parent", type=Path, help="Parent for a NEW unique fixture; existing folders are never reused")
    args = parser.parse_args()
    print(json.dumps(create_fixture(args.workspace, args.output_parent), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
