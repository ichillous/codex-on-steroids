"""Real SQLite + LangGraph + Git + subprocess validation with explicit fake model turns."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from workspace_engineering.coordinator import Coordinator
from workspace_engineering.models import Task
from workspace_engineering.repository_manager import RepositoryManager
from workspace_engineering.state import StateConflict, Store
from workspace_engineering.validation_runner import ValidationRunner


class FixtureGraph:
    def query(self, terms):
        return {"status": "limited", "query": terms, "notes": ["Synthetic test graph; no application coverage"]}


class FakeRuntime:
    def __init__(self, mutation=None, failure=None, verdict="pass"):
        self.calls = []
        self.mutation = mutation
        self.failure = failure
        self.verdict = verdict

    def run(self, **kwargs):
        self.calls.append(kwargs)
        packet = json.loads(kwargs["prompt"].split("Task packet:\n")[1])
        if self.failure and self.failure(packet, kwargs):
            raise RuntimeError("Simulated uncertain dispatch")
        if self.mutation:
            self.mutation(packet, kwargs)
        return {"status": "completed", "thread_id": "fake-test-thread", "turn_id": str(len(self.calls)),
                "text": json.dumps({"summary": "Synthetic model result for integration tests", "findings": [],
                                   "acceptance": [{"criterion": x, "status": "met", "evidence": "fixture source and actual registered command"}
                                                  for x in packet["task"]["acceptance_criteria"]], "verdict": self.verdict})}


def test_parallel_original_checkouts_rejected_when_ids_differ_from_paths(tmp_path):
    paths = {"api-service": "services/api", "web-client": "apps/web"}
    for relative in paths.values():
        subprocess.run(["git", "init", "-q", str(tmp_path / relative)], check=True, capture_output=True)
    registry = tmp_path / "tools/engineering/config/repositories.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(yaml.safe_dump({"repositories": {key: {"path": value} for key, value in paths.items()}}))
    checks = registry.with_name("validation.yaml")
    checks.write_text(yaml.safe_dump({"checks": {"api-check": {"repo": "api-service", "cwd": ".", "kind": "command", "argv": [sys.executable, "-c", "pass"]}}}))
    task = Task(title="Parallel fixture", request="Fixture only", acceptance_criteria=["unchanged"],
                repositories=list(paths), graph_terms=["fixture"], mode="implement",
                scope={key: ["."] for key in paths}, checks=["api-check"],
                checkouts={key: str(tmp_path / value) for key, value in paths.items()},
                implementation_groups=[list(paths)])
    coordinator = Coordinator(tmp_path, runtime=FakeRuntime())
    with pytest.raises(ValueError, match="not the main source checkouts"):
        coordinator.create(task)


@pytest.fixture
def setup(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "calc.py").write_text("def add(a, b): return a - b\n")
    (tmp_path / "untouched.txt").write_text("preserve\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "calc.py", "untouched.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "baseline"], check=True, capture_output=True)
    repo_config = tmp_path / "tools/engineering/config/repositories.yaml"
    repo_config.parent.mkdir(parents=True)
    repo_config.write_text(yaml.safe_dump({"repositories": {"workspace": {"path": "."}}}))
    checks = tmp_path / "checks.yaml"
    checks.write_text(yaml.safe_dump({"checks": {"fixture": {"repo": "workspace", "cwd": ".", "kind": "command", "timeout_seconds": 10,
                            "argv": [sys.executable, "-B", "-c", "from calc import add; assert add(2, 3) == 5; print('behavior verified')"]}}}))
    repos = RepositoryManager(tmp_path, repo_config)
    runner = ValidationRunner(tmp_path, checks)
    task = Task(title="Fix addition", request="Fix scoped fixture addition", acceptance_criteria=["add(2,3) returns 5"],
                repositories=["workspace"], graph_terms=["add"], scope={"workspace": ["calc.py"]}, checks=["fixture"], mode="implement")
    def coordinator(runtime):
        return Coordinator(tmp_path, runtime=runtime, repositories=repos, graphify=FixtureGraph(), validation=runner)
    return tmp_path, task, coordinator


def fix(packet, kwargs):
    if packet["stage"] == "implement":
        (kwargs["cwd"] / "calc.py").write_text("def add(a, b): return a + b\n")


def test_real_graph_executes_review_and_binds_checks_to_final_source(setup):
    root, task, factory = setup
    runtime = FakeRuntime(mutation=fix)
    coordinator = factory(runtime)
    initial = coordinator.repositories.snapshot("workspace")
    run = coordinator.create(task)
    result = coordinator.execute(run)
    assert result["status"] == "completed", result["data"]
    assert [json.loads(x["prompt"].split("Task packet:\n")[1])["stage"] for x in runtime.calls] == ["investigate", "plan", "implement", "review"]
    assert result["data"]["result"]["validations"][0]["status"] == "passed"
    assert coordinator.repositories.snapshot("workspace")["index_sha256"] == initial["index_sha256"]
    assert (root / "untouched.txt").read_text() == "preserve\n"
    assert (coordinator.store.run_dir(run) / "report.html").exists()
    with pytest.raises(StateConflict, match="immutable"):
        coordinator.execute(run)


def test_failed_validation_never_becomes_completion_and_revision_is_bounded(setup):
    _, task, factory = setup
    task.max_revisions = 1
    runtime = FakeRuntime()
    coordinator = factory(runtime)
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "incomplete"
    assert len([x for x in runtime.calls if x["role"] == "implementer"]) == 2
    assert result["data"]["result"]["validations"][0]["status"] == "failed"


def test_crash_blocks_replay_until_reconciled_then_uses_checkpoint(setup):
    _, task, factory = setup
    failed = False
    def once(packet, kwargs):
        nonlocal failed
        if packet["stage"] == "implement" and not failed:
            failed = True
            return True
        return False
    runtime = FakeRuntime(mutation=fix, failure=once)
    coordinator = factory(runtime)
    run = coordinator.create(task)
    result = coordinator.execute(run)
    assert result["status"] == "needs_reconciliation"
    with pytest.raises(StateConflict, match="Unsettled"):
        factory(runtime).execute(run)
    uncertain = [op for op in coordinator.store.operations(run) if op["status"] == "needs_reconciliation"][0]
    coordinator.store.reconcile_retry(run, uncertain["id"], True)
    result = factory(runtime).execute(run)
    assert result["status"] == "completed", result["data"]
    stages = [json.loads(x["prompt"].split("Task packet:\n")[1])["stage"] for x in runtime.calls]
    assert stages.count("investigate") == 1 and stages.count("plan") == 1


def test_out_of_scope_worker_changes_pause_without_resetting_edits(setup):
    root, task, factory = setup
    def bad(packet, kwargs):
        if packet["stage"] == "implement":
            (root / "untouched.txt").write_text("unexpected\n")
    coordinator = factory(FakeRuntime(mutation=bad))
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "needs_reconciliation"
    assert "outside assigned scope" in result["data"]["error"]
    assert (root / "untouched.txt").read_text() == "unexpected\n"


def test_source_changed_during_review_cannot_pass(setup):
    root, task, factory = setup
    def mutate(packet, kwargs):
        fix(packet, kwargs)
        if packet["stage"] == "review":
            (root / "calc.py").write_text("def add(a,b): return 0\n")
    coordinator = factory(FakeRuntime(mutation=mutate))
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "needs_reconciliation"
    assert "changing source" in result["data"]["error"]


def test_scope_and_parallel_groups_reject_ambiguous_ownership():
    base = dict(title="test", request="test", acceptance_criteria=["x"], repositories=["workspace"], graph_terms=["x"], checks=["check"], mode="implement")
    with pytest.raises(ValueError, match="escape"):
        Task(**base, scope={"workspace": ["../escape"]})
    with pytest.raises(ValueError, match="exactly once"):
        Task(**base, scope={"workspace": ["file"]}, implementation_groups=[["workspace"], ["workspace"]])


def test_dependency_outside_write_scope_invalidates_completed_check(setup):
    root, task, factory = setup
    (root / "helper.py").write_text("def add(a,b): return a+b\n")
    def mutation(packet, kwargs):
        if packet["stage"] == "implement":
            (root / "calc.py").write_text("from helper import add\n")
        if packet["stage"] == "review":
            (root / "helper.py").write_text("def add(a,b): return a-b\n")
    coordinator = factory(FakeRuntime(mutation=mutation))
    run_id = coordinator.create(task)
    result = coordinator.execute(run_id)
    assert result["status"] == "needs_reconciliation"
    assert "changing source" in result["data"]["error"]
    validation = next(op for op in coordinator.store.operations(run_id) if op["stage"] == "validate")
    assert validation["result"]["status"] == "passed"
    assert "helper.py" in validation["result"]["source_snapshots"]["workspace"]["files"]
    # Execute the same genuine subprocess check: its historical pass is stale.
    assert coordinator.validation.run("fixture", root, root / ".engineering-state/recheck")["status"] == "failed"


@pytest.mark.parametrize("spelling", ["./calc.py", ".\\calc.py", "calc.py/"])
def test_scope_is_normalized_before_any_worker_receives_it(setup, spelling):
    _, task, factory = setup
    task.scope = {"workspace": [spelling]}
    # Assignment validation occurs when creating/loading Task, as for a JSON task.
    task = Task.model_validate(task.model_dump())
    runtime = FakeRuntime(mutation=fix)
    coordinator = factory(runtime)
    run = coordinator.create(task)
    assert coordinator.store.get_run(run)["task"]["scope"] == {"workspace": ["calc.py"]}
    result = coordinator.execute(run)
    assert result["status"] == "completed", result["data"]


def test_windows_case_identity_allows_only_the_selected_file(setup):
    if sys.platform != "win32":
        pytest.skip("Windows case-insensitive file identity")
    _, task, factory = setup
    task.scope = {"workspace": ["CALC.PY"]}
    coordinator = factory(FakeRuntime(mutation=fix))
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "completed", result["data"]


def test_external_validation_catalog_change_invalidates_review(setup, tmp_path_factory):
    root, task, factory = setup
    coordinator = factory(FakeRuntime())
    checks = tmp_path_factory.mktemp("external-catalog") / "checks.yaml"
    checks.write_bytes(coordinator.validation.config_path.read_bytes())
    coordinator.validation = ValidationRunner(root, checks)
    def mutation(packet, kwargs):
        fix(packet, kwargs)
        if packet["stage"] == "review":
            catalog = yaml.safe_load(checks.read_text())
            catalog["checks"]["fixture"]["argv"] = [sys.executable, "-c", "raise SystemExit(1)"]
            checks.write_text(yaml.safe_dump(catalog))
    coordinator.runtime = FakeRuntime(mutation=mutation)
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "needs_reconciliation"
    assert "changing source" in result["data"]["error"]


def test_custom_state_directory_inside_checkout_is_not_source(setup):
    root, task, factory = setup
    coordinator = factory(FakeRuntime(mutation=fix))
    coordinator.store = Store(root / "run-artifacts")
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "completed", result["data"]


@pytest.mark.parametrize("change", [
    lambda value: value["findings"].append({"severity": "critical", "detail": "must stop", "source": "calc.py:1"}),
    lambda value: value["acceptance"].append(dict(value["acceptance"][0])),
    lambda value: value["acceptance"][0].update(status=True),
    lambda value: value["acceptance"][0].update(evidence=" "),
    lambda value: value["acceptance"][0].update(criterion="made-up criterion"),
    lambda value: value.update(acceptance=[]),
])
def test_malformed_reviewer_result_cannot_complete_a_real_run(setup, change):
    class MalformedReview(FakeRuntime):
        def run(self, **kwargs):
            response = super().run(**kwargs)
            if kwargs["role"] == "reviewer":
                value = json.loads(response["text"])
                change(value)
                response["text"] = json.dumps(value)
            return response
    root, task, factory = setup
    coordinator = factory(MalformedReview(mutation=fix))
    result = coordinator.execute(coordinator.create(task))
    assert result["status"] == "needs_reconciliation", result["data"]
    assert (root / "calc.py").read_text() == "def add(a, b): return a + b\n"


def test_parser_rejects_duplicate_json_fields_and_malformed_records():
    from workspace_engineering.coordinator import parse_result
    valid = {"summary": "reviewed", "findings": [], "acceptance": [{"criterion": "x", "status": "met", "evidence": "actual check"}], "verdict": "pass"}
    for malformed in [dict(valid, findings=["all good"]), dict(valid, verdict="completed"),
                      dict(valid, summary=42), dict(valid, extra="ignored"),
                      dict(valid, acceptance=[{"criterion": "x", "status": "met"}])]:
        with pytest.raises(ValueError):
            parse_result(json.dumps(malformed))
    with pytest.raises(ValueError):
        parse_result('{"summary":"bad","summary":"good","findings":[],"acceptance":[],"verdict":"pass"}')
    assert parse_result(json.dumps(valid), ["x"], require_all=True) == valid


def test_state_directory_cannot_exclude_an_entire_checkout(setup):
    root, task, factory = setup
    coordinator = factory(FakeRuntime())
    coordinator.store = Store(root)
    task.mode = "investigate"
    task.scope = {}
    with pytest.raises(ValueError, match="cannot contain"):
        coordinator.create(task)
