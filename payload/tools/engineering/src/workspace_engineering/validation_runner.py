"""Run explicit reviewed validation profiles without a command shell."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Callable
from uuid import uuid4
import xml.etree.ElementTree as ET

import yaml

from workspace_engineering.repository_manager import RepositoryManager, file_sha256
from workspace_engineering.process_tree import OwnedProcessTree


def parse_test_counts(output: str, parser: str) -> dict:
    """Unknown counts remain unknown; a zero exit code is not test evidence."""
    counts = {"run": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
              "known": False, "source": "log"}
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    if parser == "pytest":
        summary = next((line for line in reversed(output.splitlines())
                        if re.search(r"\b\d+ (?:passed|failed|skipped|errors?|xfailed|xpassed)\b", line)), "")
        values = {key: int(value) for value, key in re.findall(r"\b(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)\b", summary)}
        if values:
            counts.update({"passed": values.get("passed", 0), "failed": values.get("failed", 0),
                           "skipped": values.get("skipped", 0) + values.get("xfailed", 0),
                           "errors": values.get("error", 0) + values.get("errors", 0),
                           "known": True})
            counts["run"] = sum(values.values())
        elif "no tests ran" in output or "collected 0 items" in output:
            counts["known"] = True
    elif parser == "maven":
        if "Tests are skipped" in output or "No tests to run" in output:
            counts["known"] = True
        # Individual suites and reactor summaries are duplicated in Maven logs.
        # Actual counts come from fresh Surefire XML, never summed log lines.
    return counts


class ValidationRunner:
    def __init__(self, workspace: Path, config_path: Path | None = None):
        self.workspace = Path(workspace).resolve()
        self.config_path = Path(config_path) if config_path else self.workspace / "tools/engineering/config/validation.yaml"
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(self.config, dict) or not isinstance(self.config.get("checks"), dict):
            raise ValueError("Validation catalog requires a checks mapping")

    def catalog(self) -> dict:
        return json.loads(json.dumps(self.config))

    @staticmethod
    def _reports(cwd: Path, patterns: list[str]) -> dict:
        reports = {}
        for pattern in patterns:
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                raise ValueError("Validation report pattern escapes checkout")
            for path in cwd.glob(pattern):
                if path.is_file() and path.resolve().is_relative_to(cwd):
                    stat = path.stat()
                    reports[str(path)] = (stat.st_mtime_ns, stat.st_size, file_sha256(path))
        return reports

    @staticmethod
    def _junit_counts(paths: list[Path]) -> dict:
        counts = {"run": 0, "passed": 0, "failed": 0, "errors": 0,
                  "skipped": 0, "known": bool(paths), "source": "fresh JUnit XML"}
        for path in paths:
            # JUnit reports are locally produced, but still parsed as data.
            # ElementTree does not load external DTDs or execute entities.
            root = ET.parse(path).getroot()
            suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
            for suite in suites:
                for key, attribute in (("run", "tests"), ("failed", "failures"), ("errors", "errors"), ("skipped", "skipped")):
                    counts[key] += int(suite.attrib.get(attribute, 0))
        counts["passed"] = max(0, counts["run"] - counts["failed"] - counts["errors"] - counts["skipped"])
        return counts

    def run(self, check_id: str, checkout: Path, output_dir: Path,
            cancel: Callable[[], bool] | None = None,
            on_start: Callable[[int], None] | None = None) -> dict:
        if check_id not in self.config["checks"]:
            raise ValueError(f"Unknown validation check: {check_id}")
        spec = self.config["checks"][check_id]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", check_id):
            raise ValueError("Validation IDs must be filesystem-safe identifiers")
        root = Path(checkout).resolve()
        operation_id = uuid4().hex[:12]
        output_dir = Path(output_dir).resolve()
        values = {"python": sys.executable, "workspace": str(self.workspace), "checkout": str(root),
                  "output": str(output_dir), "run_id": operation_id}
        raw_argv = spec.get("argv")
        if not isinstance(raw_argv, list) or not raw_argv or any(not isinstance(arg, str) for arg in raw_argv):
            raise ValueError(f"Validation {check_id} requires a nonempty argv list")
        argv = list(raw_argv)
        for key, value in values.items():
            argv = [arg.replace("{" + key + "}", value) for arg in argv]
        if any("\x00" in arg for arg in argv):
            raise ValueError("Validation arguments cannot contain NUL bytes")
        cwd = (root / spec.get("cwd", ".")).resolve()
        if not cwd.is_relative_to(root):
            raise ValueError("Validation working directory escapes checkout")
        result = {"check_id": check_id, "repo_id": spec.get("repo"), "kind": spec.get("kind", "command"),
                  "status": "unavailable", "argv": argv, "cwd": str(cwd), "exit_code": None,
                  "test_counts": parse_test_counts("", ""), "log": None,
                  "effects": spec.get("effects", []), "notes": list(spec.get("notes", [])),
                  "source": spec.get("source", []), "started_at": datetime.now(timezone.utc).isoformat()}
        if not spec.get("enabled", True):
            return {**result, "status": "skipped", "reason": spec.get("disabled_reason", "Profile disabled in catalog")}
        if cancel and cancel():
            return {**result, "status": "cancelled", "reason": "Cancelled before command start"}
        if not cwd.is_dir():
            return {**result, "reason": f"Working directory missing: {cwd}"}
        if spec.get("repo"):
            repository_config = self.config_path.with_name("repositories.yaml")
            manager = RepositoryManager(self.workspace,
                                        repository_config if repository_config.is_file() else None,
                                        checkouts={spec["repo"]: str(root)})
            manager.resolve(spec["repo"])
        for name in spec.get("requires", []):
            path = (root / name).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Validation prerequisite escapes checkout")
            if not path.exists():
                return {**result, "reason": f"Required path missing: {path}"}
        executable = shutil.which(argv[0])
        if not executable:
            return {**result, "reason": f"Executable not available: {argv[0]}"}
        argv[0] = executable
        result["argv"] = argv
        timeout = float(spec.get("timeout_seconds", 600))
        if not 0 < timeout <= 7200:
            raise ValueError("Validation timeout must be positive and at most 7200 seconds")
        patterns = spec.get("reports", [])
        before = self._reports(cwd, patterns)
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / f"{check_id}-{operation_id}.log"
        result["log"] = str(log_path)
        started = time.monotonic()
        process = None
        tree = None
        reason = None
        status = None
        try:
            with log_path.open("wb") as stream:
                environment = os.environ.copy()
                environment["PYTHONUNBUFFERED"] = "1"
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                tree = OwnedProcessTree()
                process = tree.start(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, shell=False, env=environment)
                result["pid"] = process.pid
                if on_start is not None:
                    # Persist the child identity before polling so recovery can
                    # refuse a duplicate build while the original is alive.
                    # Any callback exception takes the same process-tree cleanup
                    # path as an interrupted runner.
                    on_start(process.pid)
                while process.poll() is None:
                    if cancel and cancel():
                        status, reason = "cancelled", "Cancellation requested; spawned process tree stopped"
                        tree.stop()
                        break
                    if time.monotonic() - started >= timeout:
                        status, reason = "failed", f"Timed out after {timeout:g} seconds; spawned process tree stopped"
                        tree.stop()
                        break
                    if log_path.stat().st_size > 32 * 1024 * 1024:
                        status, reason = "failed", "Validation exceeded the 32 MiB log limit; spawned process tree stopped"
                        tree.stop()
                        break
                    time.sleep(0.05)
                result["exit_code"] = process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            if tree is not None:
                tree.stop()
            status, reason = "unavailable", str(exc)
        except BaseException:
            if tree is not None:
                tree.stop()
            raise
        finally:
            if tree is not None:
                tree.close()
        output = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        counts = parse_test_counts(output, spec.get("parser", ""))
        after = self._reports(cwd, patterns)
        fresh = [Path(path) for path, fingerprint in after.items() if before.get(path) != fingerprint]
        if fresh:
            try:
                counts = self._junit_counts(fresh)
            except (ET.ParseError, ValueError, OSError) as exc:
                status, reason = "failed", f"Could not read fresh test evidence: {exc}"
        if status is None:
            if result["exit_code"] == 0:
                status = "passed"
                if spec.get("kind") == "test" and (not counts["known"] or counts["run"] - counts["skipped"] <= 0):
                    status, reason = "skipped", "Command succeeded, but no executed tests were verified"
                elif counts["failed"] or counts["errors"]:
                    status, reason = "failed", "Test evidence contains failures despite successful command exit"
            elif spec.get("parser") == "pytest" and result["exit_code"] == 5:
                status, reason = "skipped", "Pytest collected no tests"
            else:
                status, reason = "failed", "Command returned a nonzero exit code"
        result.update({"status": status, "reason": reason, "test_counts": counts,
                       "duration_seconds": round(time.monotonic() - started, 3),
                       "log_sha256": file_sha256(log_path) if log_path.exists() else None,
                       "log_tail": output[-8000:], "fresh_reports": [str(path) for path in fresh]})
        return result
