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


def test_same_checkout_ownership_is_shared_across_state_directories(tmp_path):
    first, second = Store(tmp_path / "state-one"), Store(tmp_path / "state-two")
    one, two = first.create_run({}), second.create_run({})
    first.claim_run(one)
    second.claim_run(two)
    checkout = tmp_path / "checkout"
    first.acquire_paths(one, [checkout])
    for path in [checkout, checkout / "nested", checkout.parent]:
        with pytest.raises(StateConflict, match="overlaps"):
            second.acquire_paths(two, [path])
    # The shared authority does not over-lock similarly named siblings.
    second.acquire_paths(two, [tmp_path / "checkout-other"])
    first.finish_process(one, release=True)
    second.acquire_paths(two, [checkout])


def test_uncertain_owner_is_not_stolen_and_retry_keeps_shared_lease(tmp_path):
    first, second = Store(tmp_path / "first"), Store(tmp_path / "second")
    one, two = first.create_run({}), second.create_run({})
    path = tmp_path / "checkout"
    first.claim_run(one)
    first.acquire_paths(one, [path])
    operation, _ = first.begin_operation(one, "implement", "implement", {})
    first.finish_process(one, release=False)
    with pytest.raises(StateConflict, match="overlaps"):
        second.acquire_paths(two, [path])
    first.reconcile_retry(one, operation, True)
    with pytest.raises(StateConflict, match="overlaps"):
        second.acquire_paths(two, [path])
    reopened = Store(first.directory)
    reopened.claim_run(one)
    reopened.acquire_paths(one, [path])
    reopened.begin_operation(one, "implement", "implement", {})
    reopened.finish_process(one, release=False)
    reopened.reconcile_abandon(one, operation, True)
    second.acquire_paths(two, [path])


def test_shared_checkout_acquisition_is_atomic_for_concurrent_stores(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    stores = [Store(tmp_path / str(i)) for i in range(2)]
    runs = [store.create_run({}) for store in stores]
    def acquire(index):
        barrier.wait(timeout=10)
        try:
            stores[index].acquire_paths(runs[index], [tmp_path / "checkout"])
            return "owned"
        except StateConflict:
            return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, [0, 1]))
    assert sorted(results) == ["blocked", "owned"]


def test_state_readers_do_not_create_shared_authority(tmp_path, isolated_checkout_lease_authority):
    store = Store(tmp_path / "state")
    run = store.create_run({})
    store.get_run(run)
    store.finish_process(run, release=True)
    assert not isolated_checkout_lease_authority.exists()


def test_retried_native_approval_has_new_identity_and_retains_expired_request(tmp_path):
    from workspace_engineering.adapters.codex import ApprovalBridge
    store = Store(tmp_path)
    run = store.create_run({})
    op, _ = store.begin_operation(run, "worker", "implement", {})
    store.update_operation(op, "running")
    old_event = {}
    def pending(event):
        old_event.update(event)
        store.pending_approval(run, op, event)
    old_bridge = ApprovalBridge(tmp_path, op, pending, lambda: True)
    assert old_bridge(7, "item/commandExecution/requestApproval", {"threadId": "old", "turnId": "turn"}) == {"decision": "cancel"}
    store.reconcile_retry(run, op, True)
    store.claim_run(run)
    store.begin_operation(run, "worker", "implement", {})
    store.update_operation(op, "running")
    def decline(event):
        approval = store.pending_approval(run, op, event)
        store.approve(run, approval, "decline")
    new_bridge = ApprovalBridge(tmp_path, op, decline, lambda: False, timeout=1)
    assert new_bridge(7, "item/commandExecution/requestApproval", {"threadId": "new", "turnId": "turn"}) == {"decision": "decline"}
    approvals = store.approvals(run)
    assert len(approvals) == 2
    assert {a["status"] for a in approvals} == {"expired", "decided"}
    assert len({a["event"]["decision_path"] for a in approvals}) == 2
    with pytest.raises(StateConflict, match="already used"):
        store.pending_approval(run, op, old_event)


def test_durable_approval_correlation_covers_native_id_type_thread_turn_and_method(tmp_path):
    from workspace_engineering.adapters.codex import ApprovalBridge
    store = Store(tmp_path)
    run = store.create_run({})
    op, _ = store.begin_operation(run, "worker", "implement", {})
    ids = []
    def record(event):
        ids.append(store.pending_approval(run, op, event))
        return {"decision": "decline"}
    for request, thread, turn, method in [
        (7, "t", "u", "commandExecution"), ("7", "t", "u", "commandExecution"),
        (7, "different", "u", "commandExecution"), (7, "t", "different", "commandExecution"),
        (7, "t", "u", "fileChange"),
    ]:
        bridge = ApprovalBridge(tmp_path, op, record, lambda: False)
        bridge(request, f"item/{method}/requestApproval", {"threadId": thread, "turnId": turn})
    assert len(set(ids)) == 5


def test_shared_leases_are_bound_to_journal_even_with_same_run_id(tmp_path, monkeypatch):
    class FixedID:
        hex = "a" * 32
    monkeypatch.setattr("workspace_engineering.state.uuid.uuid4", lambda: FixedID())
    first, second = Store(tmp_path / "first"), Store(tmp_path / "second")
    one, two = first.create_run({}), second.create_run({})
    assert one == two
    first.acquire_paths(one, [tmp_path / "checkout"])
    with pytest.raises(StateConflict, match="overlaps"):
        second.acquire_paths(two, [tmp_path / "checkout"])
    second.finish_process(two, release=True)
    with pytest.raises(StateConflict, match="overlaps"):
        second.acquire_paths(two, [tmp_path / "checkout"])
    first.finish_process(one, release=True)
    second.acquire_paths(two, [tmp_path / "checkout"])


def test_failed_multi_path_acquisition_does_not_partially_claim_resources(tmp_path):
    first, second, third = [Store(tmp_path / name) for name in ("one", "two", "three")]
    one, two, three = [store.create_run({}) for store in (first, second, third)]
    occupied, available = tmp_path / "occupied", tmp_path / "available"
    first.acquire_paths(one, [occupied])
    with pytest.raises(StateConflict):
        second.acquire_paths(two, [available, occupied])
    third.acquire_paths(three, [available])


def test_checkout_lease_uses_resolved_path_and_windows_case_identity(tmp_path):
    first, second = Store(tmp_path / "one"), Store(tmp_path / "two")
    one, two = first.create_run({}), second.create_run({})
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    first.acquire_paths(one, [checkout])
    alias = tmp_path / "sibling" / ".." / "checkout"
    if os.name == "nt":
        alias = Path(str(alias).upper())
    with pytest.raises(StateConflict, match="overlaps"):
        second.acquire_paths(two, [alias])


def test_explicit_release_recovers_completed_run_after_crash_without_replaying(tmp_path):
    from workspace_engineering.cli import main
    first, second = Store(tmp_path / "first"), Store(tmp_path / "second")
    one, two = first.create_run({}), second.create_run({})
    checkout = tmp_path / "checkout"
    first.acquire_paths(one, [checkout])
    operation, _ = first.begin_operation(one, "worker", "implement", {})
    first.update_operation(operation, "completed", {"source": "preserved"})
    first.update_run(one, "completed")
    with pytest.raises(ValueError, match="acknowledge"):
        first.reconcile_release(one, False)
    with pytest.raises(StateConflict, match="overlaps"):
        second.acquire_paths(two, [checkout])
    assert main(["--workspace", str(tmp_path), "--state-dir", str(first.directory),
                 "reconcile", "--run", one, "--action", "release", "--acknowledge-risk"]) == 0
    second.acquire_paths(two, [checkout])
    assert first.get_run(one)["status"] == "completed"
    assert first.operation(operation)["result"] == {"source": "preserved"}


def test_explicit_release_refuses_live_and_uncertain_operations(tmp_path):
    store = Store(tmp_path / "state")
    run = store.create_run({})
    store.claim_run(run)
    store.acquire_paths(run, [tmp_path / "checkout"])
    with pytest.raises(StateConflict, match="alive"):
        store.reconcile_release(run, True)
    operation, _ = store.begin_operation(run, "worker", "implement", {})
    store.finish_process(run, release=False)
    with pytest.raises(StateConflict, match="unsettled"):
        store.reconcile_release(run, True)
    store.reconcile_retry(run, operation, True)
    store.reconcile_release(run, True)
    with pytest.raises(StateConflict, match="Cancelled"):
        store.claim_run(run)
