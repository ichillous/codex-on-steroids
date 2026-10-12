import os
from pathlib import Path

import pytest

from workspace_engineering.state import StateConflict, Store


def test_operations_survive_restart_and_require_explicit_reconciliation(tmp_path):
    store = Store(tmp_path)
    run = store.create_run({"title": "fixture"})
    op, cached = store.begin_operation(run, "implement:0", "implement", {})
    assert cached is None
    reopened = Store(tmp_path)
    with pytest.raises(StateConflict, match="Unsettled"):
        reopened.claim_run(run)
    with pytest.raises(ValueError, match="acknowledge"):
        reopened.reconcile_retry(run, op, False)
    reopened.reconcile_retry(run, op, True)
    assert reopened.begin_operation(run, "implement:0", "implement", {}) == (op, None)
    reopened.update_operation(op, "completed", {"result": "done"})
    assert Store(tmp_path).begin_operation(run, "implement:0", "implement", {}) == (op, {"result": "done"})


def test_live_coordinator_and_checkout_overlap_block_competing_writers(tmp_path):
    store = Store(tmp_path / "state")
    one = store.create_run({})
    two = store.create_run({})
    store.claim_run(one)
    with pytest.raises(StateConflict, match="already owned"):
        store.claim_run(one)
    store.acquire_paths(one, [tmp_path / "workspace"])
    with pytest.raises(StateConflict, match="overlaps"):
        store.acquire_paths(two, [tmp_path / "workspace/backend"])
    store.finish_process(one, release=True)
    store.acquire_paths(two, [tmp_path / "workspace/backend"])


def test_live_worker_prevents_retry_even_after_coordinator_stops(tmp_path):
    store = Store(tmp_path)
    run = store.create_run({})
    op, _ = store.begin_operation(run, "key", "implement", {"worker_pid": os.getpid()})
    with pytest.raises(StateConflict, match="still be alive"):
        store.reconcile_retry(run, op, True)


def test_approvals_are_bound_to_live_operation_and_native_offered_decisions(tmp_path):
    store = Store(tmp_path)
    run = store.create_run({})
    store.claim_run(run)
    op, _ = store.begin_operation(run, "key", "implement", {})
    store.update_operation(op, "running")
    decision_path = tmp_path / "approvals/op/request.json"
    request = store.pending_approval(run, op, {"request_id": 7, "method": "item/commandExecution/requestApproval",
                   "decision_path": str(decision_path), "params": {"availableDecisions": ["accept", "decline"]}})
    with pytest.raises(ValueError, match="one of"):
        store.approve(run, request, "acceptForSession")
    assert not decision_path.exists()
    store.approve(run, request, "accept")
    assert decision_path.read_text().strip().endswith("}")
    with pytest.raises(StateConflict, match="already decided"):
        store.approve(run, request, "accept")


def test_cancelled_owner_cannot_accept_old_approval(tmp_path):
    store = Store(tmp_path)
    run = store.create_run({})
    store.claim_run(run)
    op, _ = store.begin_operation(run, "key", "implement", {})
    store.update_operation(op, "running")
    request = store.pending_approval(run, op, {"request_id": "x", "method": "approval", "decision_path": str(tmp_path / "approvals/x.json")})
    store.cancel(run)
    with pytest.raises(StateConflict, match="no longer live"):
        store.approve(run, request, "accept")


def test_completed_runs_cannot_be_reexecuted(tmp_path):
    store = Store(tmp_path)
    run = store.create_run({})
    store.update_run(run, "completed")
    with pytest.raises(StateConflict, match="immutable"):
        store.claim_run(run)


def test_abandon_releases_stopped_run_ownership_and_preserves_files(tmp_path):
    store = Store(tmp_path / "state")
    run = store.create_run({})
    next_run = store.create_run({})
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    source = checkout / "source.txt"
    source.write_text("keep uncertain edits")
    store.acquire_paths(run, [checkout])
    op, _ = store.begin_operation(run, "key", "implement", {})
    store.cancel(run)
    with pytest.raises(StateConflict, match="cannot retry"):
        store.reconcile_retry(run, op, True)
    store.reconcile_abandon(run, op, True)
    store.acquire_paths(next_run, [checkout])
    assert source.read_text() == "keep uncertain edits"
    assert store.get_run(run)["status"] == "cancelled"
