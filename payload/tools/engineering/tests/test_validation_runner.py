from pathlib import Path
import subprocess
import sys
import time

import pytest
import yaml

from workspace_engineering.validation_runner import ValidationRunner, parse_test_counts


@pytest.fixture
def workspace(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "repositories.yaml").write_text(yaml.safe_dump({"repositories": {"workspace": {"path": "."}}}))
    return tmp_path


def runner(root, **spec):
    check = {"repo": "workspace", "cwd": ".", "argv": [sys.executable, "-c", "print('ok')"],
             "timeout_seconds": 5, "kind": "command", **spec}
    path = root / "validation.yaml"
    path.write_text(yaml.safe_dump({"checks": {"fixture": check}}))
    return ValidationRunner(root, path)


def test_runs_exact_arguments_without_shell_and_records_evidence(workspace):
    special = "a & echo shell-must-not-run; $(false)"
    engine = runner(workspace, argv=[sys.executable, "-c", "import sys; print(sys.argv[1])", special], effects=["log only"])
    result = engine.run("fixture", workspace, workspace / "logs")
    assert result["status"] == "passed"
    assert Path(result["log"]).read_text().strip() == special
    assert result["test_counts"]["known"] is False
    assert result["effects"] == ["log only"]
    assert result["exit_code"] == 0 and result["log_sha256"]


def test_unknown_check_and_cwd_escape_are_rejected(workspace):
    engine = runner(workspace)
    with pytest.raises(ValueError, match="Unknown"):
        engine.run("arbitrary-shell-command", workspace, workspace / "logs")
    engine = runner(workspace, cwd="..")
    with pytest.raises(ValueError, match="escapes"):
        engine.run("fixture", workspace, workspace / "logs")


def test_successful_command_without_tests_is_skipped(workspace):
    engine = runner(workspace, kind="test", parser="maven", argv=[sys.executable, "-c", "print('Tests are skipped. BUILD SUCCESS')"])
    result = engine.run("fixture", workspace, workspace / "logs")
    assert result["status"] == "skipped"
    assert result["exit_code"] == 0
    assert result["test_counts"]["run"] == 0


def test_real_pytest_failure_is_not_reported_as_pass(workspace):
    (workspace / "test_fixture.py").write_text("def test_fails():\n    assert False\n")
    engine = runner(workspace, kind="test", parser="pytest", argv=[sys.executable, "-m", "pytest", "test_fixture.py", "-q", "-p", "no:cacheprovider"])
    result = engine.run("fixture", workspace, workspace / "logs")
    assert result["status"] == "failed"
    assert result["test_counts"]["failed"] == 1


def test_stale_surefire_reports_do_not_count_as_executed_tests(workspace):
    report = workspace / "target/surefire-reports/TEST-old.xml"
    report.parent.mkdir(parents=True)
    report.write_text('<testsuite tests="40" failures="0" errors="0" skipped="0"/>')
    engine = runner(workspace, kind="test", parser="maven", reports=["target/surefire-reports/TEST-*.xml"])
    result = engine.run("fixture", workspace, workspace / "logs")
    assert result["status"] == "skipped"
    assert result["fresh_reports"] == []


def test_fresh_junit_evidence_exposes_failure_with_zero_exit(workspace):
    code = 'from pathlib import Path; p=Path("target/TEST-result.xml"); p.parent.mkdir(exist_ok=True); p.write_text(\'<testsuite tests="2" failures="1" errors="0" skipped="0"/>\')'
    engine = runner(workspace, kind="test", reports=["target/TEST-*.xml"], argv=[sys.executable, "-c", code])
    result = engine.run("fixture", workspace, workspace / "logs")
    assert result["status"] == "failed"
    assert result["exit_code"] == 0
    assert result["test_counts"]["failed"] == 1


@pytest.mark.parametrize("mode", ["timeout", "cancel"])
def test_timeout_and_cancellation_stop_spawned_process_tree(workspace, mode):
    marker = workspace / "child-survived.txt"
    child_code = f'import time; from pathlib import Path; time.sleep(1.8); Path({str(marker)!r}).write_text("leak")'
    parent_code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child_code!r}]); time.sleep(30)"
    engine = runner(workspace, timeout_seconds=0.4 if mode == "timeout" else 10,
                    argv=[sys.executable, "-c", parent_code])
    started = time.monotonic()
    result = engine.run("fixture", workspace, workspace / "logs",
                        cancel=(lambda: time.monotonic() - started > 0.4) if mode == "cancel" else None)
    assert result["status"] == ("failed" if mode == "timeout" else "cancelled")
    assert ("Timed out" if mode == "timeout" else "Cancellation") in result["reason"]
    time.sleep(2)
    assert not marker.exists()


def test_cancellation_is_distinct_and_missing_executable_unavailable(workspace):
    engine = runner(workspace)
    result = engine.run("fixture", workspace, workspace / "logs", cancel=lambda: True)
    assert result["status"] == "cancelled" and result["log"] is None
    engine = runner(workspace, argv=["nonexistent-engineering-test-program-123"])
    assert engine.run("fixture", workspace, workspace / "logs")["status"] == "unavailable"


def test_pytest_counts_include_skips_without_claiming_execution():
    counts = parse_test_counts("==== 3 passed, 2 skipped, 1 xfailed in 1.00s ====", "pytest")
    assert counts["run"] == 6 and counts["skipped"] == 3 and counts["passed"] == 3


def test_start_callback_receives_owned_child_pid(workspace):
    captured = []
    engine = runner(workspace)
    result = engine.run("fixture", workspace, workspace / "logs", on_start=captured.append)
    assert captured == [result["pid"]]
    assert result["status"] == "passed"


def test_start_callback_failure_stops_spawned_process_tree(workspace):
    marker = workspace / "callback-child-survived.txt"
    child_code = f'import time; from pathlib import Path; time.sleep(1.8); Path({str(marker)!r}).write_text("leak")'
    parent_code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child_code!r}]); time.sleep(30)"
    engine = runner(workspace, argv=[sys.executable, "-c", parent_code])

    def fail_journal(pid):
        assert isinstance(pid, int) and pid > 0
        time.sleep(0.25)
        raise RuntimeError("journal unavailable")

    with pytest.raises(RuntimeError, match="journal unavailable"):
        engine.run("fixture", workspace, workspace / "logs", on_start=fail_journal)
    time.sleep(2)
    assert not marker.exists()
