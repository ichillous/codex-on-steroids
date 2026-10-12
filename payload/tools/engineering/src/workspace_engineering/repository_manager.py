"""Read-only Git identity, source snapshots, and checkout ownership.

No method stages, resets, creates, moves, or deletes a checkout. A coordinator
must obtain isolated checkouts through the host's managed worktree interface.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import yaml


class RepositoryError(ValueError):
    """Repository identity or a source boundary could not be established."""


def _canonical(path: Path | str) -> str:
    return os.path.normcase(str(Path(path).resolve())).rstrip("/\\")


def paths_overlap(a: Path | str, b: Path | str) -> bool:
    """True for identical or ancestor paths, including resolved junctions."""
    left, right = _canonical(a), _canonical(b)
    try:
        return os.path.commonpath([left, right]) in (left, right)
    except ValueError:  # Different Windows drives.
        return False


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> bytes:
    try:
        process = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false", "-C", str(root), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryError(f"Git unavailable for {root}: {exc}") from exc
    if check and process.returncode:
        detail = process.stderr.decode("utf-8", "replace").strip()[:2000]
        raise RepositoryError(f"Git {' '.join(args[:2])} failed in {root}: {detail}")
    return process.stdout if process.returncode == 0 else b""


class RepositoryManager:
    def __init__(self, workspace: Path, config_path: Path | None = None,
                 checkouts: dict[str, str] | None = None):
        self.workspace = Path(workspace).resolve()
        self.config_path = config_path or self.workspace / "tools/engineering/config/repositories.yaml"
        data = yaml.safe_load(Path(self.config_path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("repositories"), dict):
            raise RepositoryError("Repository catalog requires a repositories mapping")
        self.config = data
        self.repositories = data["repositories"]
        self.checkouts = dict(checkouts or {})
        unknown = set(self.checkouts) - set(self.repositories)
        if unknown:
            raise RepositoryError(f"Unknown checkout bindings: {sorted(unknown)}")

    def _configured_root(self, repo_id: str) -> Path:
        if repo_id not in self.repositories:
            raise RepositoryError(f"Unknown repository: {repo_id}")
        relative = self.repositories[repo_id].get("path", repo_id)
        root = (self.workspace / relative).resolve()
        if not root.is_relative_to(self.workspace):
            raise RepositoryError(f"Configured repository escapes workspace: {repo_id}")
        return root

    @staticmethod
    def _actual_root(root: Path) -> Path:
        actual = _git(root, "rev-parse", "--show-toplevel").decode("utf-8", "replace").strip()
        if not actual or _canonical(actual) != _canonical(root):
            raise RepositoryError(f"Expected an actual Git root at {root}; found {actual or 'none'}")
        return root

    @staticmethod
    def _common_dir(root: Path) -> Path:
        value = _git(root, "rev-parse", "--git-common-dir").decode().strip()
        return (root / value).resolve()

    def resolve(self, repo_id: str) -> Path:
        original = self._actual_root(self._configured_root(repo_id))
        if repo_id not in self.checkouts:
            return original
        target = self._actual_root(Path(self.checkouts[repo_id]).resolve())
        if self._common_dir(original) == self._common_dir(target):
            return target
        # A clone must contain the original current commit. Do not trust a
        # directory name or an arbitrary caller-supplied repository label.
        head = _git(original, "rev-parse", "--verify", "HEAD", check=False).decode().strip()
        commit = _git(target, "rev-parse", "--verify", f"{head}^{{commit}}", check=False).decode().strip() if head else ""
        if not head or commit != head:
            raise RepositoryError(f"Checkout binding for {repo_id} has no verified shared Git history")
        return target

    def inventory(self, repo_ids: list[str] | None = None) -> dict:
        requested = repo_ids if repo_ids is not None else list(self.repositories)
        unknown = set(requested) - set(self.repositories)
        if unknown:
            raise RepositoryError(f"Unknown repositories: {sorted(unknown)}")
        records = {}
        for repo_id in requested:
            config = self.repositories[repo_id]
            try:
                root = self.resolve(repo_id)
                head = _git(root, "rev-parse", "--verify", "HEAD", check=False).decode().strip() or None
                status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
                records[repo_id] = {
                    "status": "available", "root": str(root), "head": head,
                    "branch": _git(root, "symbolic-ref", "--short", "HEAD", check=False).decode().strip() or None,
                    "working_tree_status_sha256": hashlib.sha256(status).hexdigest(),
                    "dirty": bool(status), "instructions": config.get("instructions", []),
                    "toolchain": config.get("toolchain"), "dependencies": config.get("dependencies", []),
                    "applications": config.get("applications", []),
                    "external_binding": repo_id in self.checkouts,
                }
            except RepositoryError as exc:
                records[repo_id] = {"status": "unavailable", "error": str(exc), "root": str(self._configured_root(repo_id))}
        return {"workspace": str(self.workspace), "repositories": records,
                "status": "available" if all(v["status"] == "available" for v in records.values()) else "limited"}

    def _excluded(self, root: Path, relative: str, repo_id: str, *, explicit: bool = False) -> bool:
        parts = Path(relative).parts
        hard = {".git", ".engineering-state", ".venv", ".venv-studio", "__pycache__", ".pytest_cache", "node_modules", "target", "dist", "node-target"}
        if any(part.casefold() in hard for part in parts):
            return True
        if not explicit:
            exclusions = self.config.get("snapshot_excludes", []) + self.repositories[repo_id].get("snapshot_excludes", [])
            if any(relative == item or relative.startswith(item.rstrip("/") + "/") for item in exclusions):
                return True
        # The outer workspace must not claim a nested repository's files.
        for other_id in self.repositories:
            if other_id == repo_id:
                continue
            configured = (root / self.repositories[other_id].get("path", other_id)).resolve() if repo_id == "workspace" else self._configured_root(other_id)
            candidate = (root / relative).resolve()
            if configured != root and configured.is_relative_to(root) and candidate.is_relative_to(configured):
                return True
        return False

    @staticmethod
    def _owned_path(root: Path, value: str) -> Path:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise RepositoryError("A source scope must be a nonempty path")
        candidate = (root / value).resolve()
        if not candidate.is_relative_to(root):
            raise RepositoryError(f"Source path escapes repository: {value}")
        current = candidate if candidate.is_dir() else candidate.parent
        while current != root:
            if (current / ".git").exists():
                raise RepositoryError(f"Source path crosses another Git root: {value}")
            current = current.parent
        return candidate

    def snapshot(self, repo_id: str, paths: list[str] | None = None) -> dict:
        root = self.resolve(repo_id)
        # Use literal pathspecs: a task path beginning ':' is never Git syntax.
        scopes = paths if paths is not None else []
        for value in scopes:
            self._owned_path(root, value)
            if self._excluded(root, value.replace("\\", "/"), repo_id, explicit=True):
                raise RepositoryError(f"Source scope is reserved or belongs to a nested repository: {value}")
        argv = ["--literal-pathspecs", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        if scopes:
            argv += ["--", *scopes]
        raw = _git(root, *argv)
        names = {name.decode("utf-8", "surrogateescape").rstrip("/") for name in raw.split(b"\x00") if name}
        if scopes:
            for value in scopes:
                candidate = self._owned_path(root, value)
                if not candidate.is_dir():
                    names.add(candidate.relative_to(root).as_posix())
                    continue
                for directory, folders, files in os.walk(candidate, followlinks=False):
                    here = Path(directory)
                    folders[:] = [name for name in folders if not self._excluded(root, (here / name).relative_to(root).as_posix(), repo_id, explicit=True)]
                    for name in files:
                        names.add((here / name).relative_to(root).as_posix())
        files = {}
        for name in sorted(names):
            if self._excluded(root, name, repo_id, explicit=bool(scopes)):
                continue
            candidate = self._owned_path(root, name)
            if candidate.is_dir():
                # Unregistered nested repositories must be visible errors.
                if (candidate / ".git").exists():
                    raise RepositoryError(f"Unregistered nested repository in source: {name}")
                continue
            if candidate.is_file():
                before = candidate.stat()
                digest = file_sha256(candidate)
                after = candidate.stat()
                if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                    raise RepositoryError(f"Source changed while hashing: {name}")
                original_path = root / name
                files[name] = {"sha256": digest, "size": after.st_size,
                               "mode": after.st_mode & 0o777,
                               "symlink_target": os.readlink(original_path) if original_path.is_symlink() else None}
            else:
                files[name] = {"sha256": None, "status": "missing"}
        index_name = _git(root, "rev-parse", "--git-path", "index").decode().strip()
        index = (root / index_name).resolve()
        payload: dict[str, Any] = {
            "repo_id": repo_id, "root": str(root),
            "head": _git(root, "rev-parse", "--verify", "HEAD", check=False).decode().strip() or None,
            "index_sha256": file_sha256(index) if index.is_file() else None,
            "files": files, "scope": scopes or None,
        }
        payload["fingerprint"] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        payload["file_count"] = len(files)
        payload["notes"] = ["Current bytes include scoped untracked files; runtime/dependency paths and embedded repositories are excluded.",
                            "Index is read and hashed without refreshing or changing it."]
        return payload

    def diff(self, repo_id: str, paths: list[str] | None = None) -> dict:
        root = self.resolve(repo_id)
        for value in paths or []:
            self._owned_path(root, value)
            if self._excluded(root, value.replace("\\", "/"), repo_id, explicit=True):
                raise RepositoryError(f"Diff scope is reserved or belongs to a nested repository: {value}")
        pathspec = ["--", *paths] if paths else []
        result = {"repo_id": repo_id, "root": str(root), "limit_chars_per_section": 32000, "scope": paths}
        for name, flags in (("unstaged", []), ("staged", ["--cached"])):
            output = _git(root, "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--ignore-submodules=all", *flags, *pathspec).decode("utf-8", "replace")
            result[name] = {"text": output[:32000], "truncated": len(output) > 32000,
                            "sha256": hashlib.sha256(output.encode()).hexdigest()}
        untracked = _git(root, "--literal-pathspecs", "ls-files", "--others", "--exclude-standard", "-z", *pathspec).decode("utf-8", "replace").split("\x00")
        untracked = [name for name in untracked if name and not self._excluded(root, name, repo_id)]
        result["untracked"] = untracked[:200]
        result["untracked_truncated"] = len(untracked) > 200
        result["notes"] = ["Untracked contents appear in source snapshots; Git diff covers tracked changes."]
        return result
