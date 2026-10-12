from pathlib import Path
import subprocess

import pytest
import yaml

from workspace_engineering.repository_manager import RepositoryManager, RepositoryError, paths_overlap


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


@pytest.fixture
def workspace(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "main.txt").write_text("baseline\n")
    git(tmp_path, "add", "main.txt")
    git(tmp_path, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
    config = tmp_path / "repositories.yaml"
    config.write_text(yaml.safe_dump({"repositories": {"workspace": {"path": "."}}}))
    return tmp_path, config


def test_snapshot_tracks_source_bytes_untracked_and_preserves_index(workspace):
    root, config = workspace
    manager = RepositoryManager(root, config)
    before = manager.snapshot("workspace", ["main.txt", "new.txt"])
    (root / "main.txt").write_text("changed\n")
    (root / "new.txt").write_text("untracked\n")
    after = manager.snapshot("workspace", ["main.txt", "new.txt"])
    assert before["fingerprint"] != after["fingerprint"]
    assert before["index_sha256"] == after["index_sha256"]
    assert after["files"]["new.txt"]["sha256"]
    assert manager.inventory(["workspace"])["repositories"]["workspace"]["dirty"]
    assert "main.txt" in manager.diff("workspace")["unstaged"]["text"]


def test_outside_and_nested_repository_scope_rejected(workspace):
    root, config = workspace
    child = root / "backend"
    child.mkdir()
    git(child, "init", "-q")
    (child / "file.txt").write_text("child")
    config.write_text(yaml.safe_dump({"repositories": {"workspace": {"path": "."}, "backend": {"path": "backend"}}}))
    manager = RepositoryManager(root, config)
    with pytest.raises(RepositoryError, match="escapes"):
        manager.snapshot("workspace", ["../outside.txt"])
    with pytest.raises(RepositoryError, match="another Git root"):
        manager.snapshot("workspace", ["backend/file.txt"])
    outer = manager.snapshot("workspace")
    assert not any(path.startswith("backend/") for path in outer["files"])
    assert manager.resolve("backend") == child


def test_runtime_output_does_not_invalidate_scoped_source(workspace):
    root, config = workspace
    manager = RepositoryManager(root, config)
    before = manager.snapshot("workspace")
    for name in (".engineering-state/run.json", "nested/target/generated.txt", ".venv/installed.py"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("runtime")
    assert before["fingerprint"] == manager.snapshot("workspace")["fingerprint"]


def test_external_checkout_binding_requires_shared_history(workspace, tmp_path_factory):
    root, config = workspace
    clone = tmp_path_factory.mktemp("clone")
    subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True, capture_output=True)
    assert RepositoryManager(root, config, {"workspace": str(clone)}).resolve("workspace") == clone
    unrelated = tmp_path_factory.mktemp("unrelated")
    git(unrelated, "init", "-q")
    with pytest.raises(RepositoryError, match="shared Git history"):
        RepositoryManager(root, config, {"workspace": str(unrelated)}).resolve("workspace")


def test_actual_root_and_unknown_identity_fail(workspace):
    root, config = workspace
    (root / "plain").mkdir()
    config.write_text(yaml.safe_dump({"repositories": {"plain": {"path": "plain"}}}))
    manager = RepositoryManager(root, config)
    with pytest.raises(RepositoryError, match="actual Git root"):
        manager.resolve("plain")
    with pytest.raises(RepositoryError, match="Unknown"):
        manager.inventory(["typo"])


def test_git_metadata_scope_is_rejected_regardless_of_case(workspace):
    root, config = workspace
    with pytest.raises(RepositoryError, match="reserved"):
        RepositoryManager(root, config).snapshot("workspace", [".GIT/index"])


def test_ownership_resolves_parent_and_sibling_paths(tmp_path):
    assert paths_overlap(tmp_path / "a", tmp_path / "a/b")
    assert paths_overlap(tmp_path / "a/../b", tmp_path / "b")
    assert not paths_overlap(tmp_path / "a", tmp_path / "abc")


def test_scoped_ignored_new_file_is_hashed(workspace):
    root, config = workspace
    (root / ".gitignore").write_text("private-note.txt\n")
    (root / "private-note.txt").write_text("explicitly scoped")
    data = RepositoryManager(root, config).snapshot("workspace", ["private-note.txt"])
    assert data["files"]["private-note.txt"]["sha256"]


def test_diff_scope_excludes_unrelated_changes(workspace):
    root, config = workspace
    (root / "other.txt").write_text("baseline")
    git(root, "add", "other.txt")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "second fixture")
    (root / "main.txt").write_text("selected change")
    (root / "other.txt").write_text("unrelated change")
    result = RepositoryManager(root, config).diff("workspace", ["main.txt"])
    assert "selected change" in result["unstaged"]["text"]
    assert "unrelated change" not in result["unstaged"]["text"]


def test_pathspec_magic_is_treated_as_literal(workspace):
    root, config = workspace
    if __import__("os").name == "nt":
        pytest.skip("Windows forbids ':' in a file name")
    (root / ":(glob)*").write_text("literal")
    data = RepositoryManager(root, config).snapshot("workspace", [":(glob)*"])
    assert list(data["files"]) == [":(glob)*"]
