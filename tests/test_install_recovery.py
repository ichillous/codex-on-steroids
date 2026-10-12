"""Hard-stop rollback and concurrent-edit preservation in disposable projects."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install.py"
spec = importlib.util.spec_from_file_location("install_recovery", SCRIPT)
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


def test_abrupt_process_exit_rolls_back_applied_paths_and_skips_untouched_paths(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "a.txt").write_bytes(b"old a")
    (project / "c.txt").write_bytes(b"old c")
    output = project / ".engineering-state/setup/interrupted"
    code = f"""
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location('install', {str(SCRIPT)!r})
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
project = Path({str(project)!r})
original = installer.atomic_write
def interrupted(path, data):
    original(path, data)
    if path == project / 'a.txt':
        os._exit(73)
installer.atomic_write = interrupted
installer.apply(project, [
    {{'path': 'a.txt', 'before': b'old a', 'after': b'new a'}},
    {{'path': 'b.txt', 'before': None, 'after': b'new b'}},
    {{'path': 'c.txt', 'before': b'old c', 'after': b'new c'}},
], Path({str(output)!r}))
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 73, result.stdout + result.stderr
    receipt = output / "receipt.json"
    assert json.loads(receipt.read_bytes())["status"] == "prepared"
    assert (project / "a.txt").read_bytes() == b"new a"
    assert not (project / "b.txt").exists()
    install.rollback(project, receipt)
    assert (project / "a.txt").read_bytes() == b"old a"
    assert (project / "c.txt").read_bytes() == b"old c"
    assert not (project / "b.txt").exists()
    assert json.loads(receipt.read_bytes())["status"] == "rolled_back"
    install.rollback(project, receipt)  # Safe repeated recovery.


def test_unknown_partial_state_blocks_all_restores_and_preserves_later_work(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    changes = [{"path": name, "before": None, "after": b"installed"} for name in ("a.txt", "b.txt")]
    receipt = install.apply(project, changes, project / ".engineering-state/setup/initial")
    data = json.loads(receipt.read_bytes())
    data["status"] = "prepared"
    receipt.write_text(json.dumps(data))
    (project / "b.txt").write_bytes(b"later owner edit")
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(project, receipt)
    assert (project / "a.txt").read_bytes() == b"installed"
    assert (project / "b.txt").read_bytes() == b"later owner edit"


def test_change_during_rollback_is_preserved_by_recheck(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    for name in ("a.txt", "b.txt"):
        (project / name).write_bytes(b"before")
    changes = [{"path": name, "before": b"before", "after": b"after"} for name in ("a.txt", "b.txt")]
    receipt = install.apply(project, changes, project / ".engineering-state/setup/initial")
    write = install.atomic_write

    def racing_writer(path, data):
        write(path, data)
        if path == project / "b.txt":
            (project / "a.txt").write_bytes(b"concurrent owner edit")

    monkeypatch.setattr(install, "atomic_write", racing_writer)
    with pytest.raises(install.Conflict, match="preserves later edits"):
        install.rollback(project, receipt)
    assert (project / "a.txt").read_bytes() == b"concurrent owner edit"
    assert (project / "b.txt").read_bytes() == b"before"


def test_corrupt_backup_cannot_restore_new_bytes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "a.txt").write_bytes(b"before")
    receipt = install.apply(project, [{"path": "a.txt", "before": b"before", "after": b"after"}],
                            project / ".engineering-state/setup/initial")
    (receipt.parent / "backup/a.txt").write_bytes(b"changed backup")
    with pytest.raises(install.Conflict, match="Backup hash"):
        install.rollback(project, receipt)
    assert (project / "a.txt").read_bytes() == b"after"
