"""Native worker control tests with a fake SDK; no model/provider requests."""

import json
from pathlib import Path
import queue
import sys
import threading
import tomllib
from types import SimpleNamespace

import pytest

from workspace_engineering.adapters.codex import (
    ApprovalBridge,
    RoutedCodexClient,
    bounded_call,
    client_config,
)
from workspace_engineering.worker_runtime import WorkerRuntime


APPROVAL = "item/commandExecution/requestApproval"


def test_native_approval_waits_for_its_correlated_artifact_and_cannot_replay(tmp_path):
    events = []

    def decide(event):
        events.append(event)
        path = Path(event["decision_path"])
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"decision": "decline"}), encoding="utf-8")

    bridge = ApprovalBridge(tmp_path, "operation-A", decide, lambda: False, timeout=1)
    params = {"threadId": "thread-A", "turnId": "turn-A", "availableDecisions": ["accept", "decline"]}
    assert bridge(17, APPROVAL, params) == {"decision": "decline"}
    assert events[0]["request_id"] == 17
    assert events[0]["params"] == params
    assert Path(events[0]["decision_path"]).is_relative_to(tmp_path / "approvals")
    with pytest.raises(RuntimeError, match="cannot be replayed"):
        bridge(17, APPROVAL, params)


def test_approval_correlation_distinguishes_rpc_id_type_thread_turn_and_operation(tmp_path):
    paths = []

    def decide(event):
        paths.append(event["decision_path"])
        return {"decision": "decline"}

    for operation, request_id, thread_id, turn_id in (
        ("one", 7, "t", "u"), ("one", "7", "t", "u"),
        ("one", 7, "different", "u"), ("one", 7, "t", "different"),
        ("two", 7, "t", "u"),
    ):
        bridge = ApprovalBridge(tmp_path, operation, decide, lambda: False)
        bridge(request_id, APPROVAL, {"threadId": thread_id, "turnId": turn_id})
    assert len(set(paths)) == 5


@pytest.mark.parametrize("cancelled,timeout", [(True, 5), (False, 0)])
def test_approval_never_accepts_without_a_decision(tmp_path, cancelled, timeout):
    events = []
    bridge = ApprovalBridge(tmp_path, "one", events.append, lambda: cancelled, timeout=timeout)
    assert bridge(1, APPROVAL, {}) == {"decision": "cancel"}
    assert len(events) == 1
    assert not Path(events[0]["decision_path"]).exists()


def test_approval_rejects_decisions_not_offered_by_native_request(tmp_path):
    bridge = ApprovalBridge(tmp_path, "one", lambda event: {"decision": "acceptForSession"}, lambda: False)
    with pytest.raises(ValueError, match="offered native"):
        bridge(1, APPROVAL, {"availableDecisions": ["accept", "decline"]})


def test_unknown_native_request_fails_without_permissive_sdk_fallback(tmp_path):
    events = []
    bridge = ApprovalBridge(tmp_path, "one", events.append, lambda: False)
    with pytest.raises(RuntimeError, match="Unsupported native request"):
        bridge("request", "item/tool/requestUserInput", {"questions": []})
    assert events == [{"type": "unsupported_native_request", "request_id": "request", "method": "item/tool/requestUserInput"}]
    client = RoutedCodexClient(client_config(tmp_path), bridge)
    assert client._approval_handler("unknown", {}) == {"decision": "cancel"}


def test_client_passes_exact_native_rpc_request_to_bridge(tmp_path):
    seen = []

    def bridge(*args):
        seen.append(args)
        return {"decision": "decline"}

    client = RoutedCodexClient(client_config(tmp_path), bridge)
    assert client._handle_server_request({"id": "rpc-001", "method": APPROVAL, "params": {"turnId": "turn-1"}}) == {"decision": "decline"}
    assert seen == [("rpc-001", APPROVAL, {"turnId": "turn-1"})]


def test_disabled_coordinator_override_has_valid_transport_without_project_config(tmp_path):
    config = client_config(tmp_path)
    # Parse the exact native --config expressions rather than searching text.
    merged = tomllib.loads("\n".join(config.config_overrides))
    server = merged["mcp_servers"]["workspace-engineering"]
    assert server == {"command": sys.executable, "args": [], "enabled": False}
    assert merged["features"]["multi_agent"] is False


def test_bounded_rpc_wait_can_be_cancelled_without_waiting_for_reply():
    release = threading.Event()
    try:
        with pytest.raises(InterruptedError, match="cancelled"):
            bounded_call(lambda: release.wait(1), timeout=1, cancelled=lambda: True)
    finally:
        release.set()


class FakeClient:
    def __init__(self, events=(), started=None):
        self.worker_pid = 12345
        self.notifications = queue.Queue()
        for method, payload in events:
            self.notifications.put(SimpleNamespace(method=method, payload=payload))
        self.started = started or {
            "thread": {"id": "thread-1"}, "model": "gpt-6-astra", "reasoningEffort": "ultra",
            "sandbox": {"type": "readOnly"}, "approvalPolicy": "on-request",
        }
        self.turns = []
        self.interrupts = []
        self.closed = False

    def start(self):
        pass

    def initialize(self):
        return {}

    def thread_start(self, params):
        self.thread_params = params
        return {"cwd": params["cwd"], **self.started}

    def turn_start(self, thread_id, prompt, params):
        self.turns.append((thread_id, prompt, params))
        return {"turn": {"id": "turn-1"}}

    def next_turn_notification(self, turn_id):
        return self.notifications.get(timeout=3)

    def turn_interrupt(self, thread_id, turn_id):
        self.interrupts.append((thread_id, turn_id))
        self.notifications.put(SimpleNamespace(method="turn/completed", payload={"turn": {"id": turn_id, "status": "interrupted"}}))
        return {}

    def stop_owned_tree(self):
        self.closed = True


def run_fake(tmp_path, monkeypatch, client, *, on_event=None, cancelled=lambda: False, timeout=2):
    roles = tmp_path / ".codex/agents"
    roles.mkdir(parents=True, exist_ok=True)
    (roles / "investigator.toml").write_text(
        'name="investigator"\nmodel="gpt-6-astra"\nmodel_reasoning_effort="ultra"\ndeveloper_instructions="Inspect the assigned fixture."\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("workspace_engineering.worker_runtime.RoutedCodexClient", lambda *args: client)
    events = []

    def record(event):
        events.append(event)
        if on_event:
            on_event(event)

    result = WorkerRuntime(tmp_path, tmp_path / "state", timeout_seconds=timeout).run(
        role="investigator", prompt="Synthetic test only", cwd=tmp_path, operation_id="operation-1",
        read_only=True, on_event=record, cancelled=cancelled,
    )
    assert client.closed
    return result, events


@pytest.mark.parametrize("field,value", [("model", "other"), ("reasoningEffort", "high"), ("sandbox", {"type": "dangerFullAccess"}), ("cwd", "/other-checkout")])
def test_effective_native_model_effort_sandbox_and_checkout_are_verified_before_turn(tmp_path, monkeypatch, field, value):
    client = FakeClient()
    client.started[field] = value
    result, _ = run_fake(tmp_path, monkeypatch, client)
    assert result["status"] == "failed"
    assert not client.turns


def test_completed_notifications_produce_final_answer_and_measured_usage(tmp_path, monkeypatch):
    usage = {"total": {"inputTokens": 50, "outputTokens": 12}}
    client = FakeClient([
        ("item/completed", {"item": {"type": "agentMessage", "id": "comment", "phase": "commentary", "text": "Working"}}),
        ("thread/tokenUsage/updated", {"tokenUsage": usage}),
        ("item/completed", {"item": {"type": "agentMessage", "id": "answer", "phase": "final_answer", "text": '{"summary":"done"}'}}),
        ("turn/completed", {"turn": {"id": "turn-1", "status": "completed"}}),
    ])
    result, _ = run_fake(tmp_path, monkeypatch, client)
    assert result["status"] == "completed"
    assert result["text"] == '{"summary":"done"}'
    assert result["usage"] == usage
    assert client.turns[0][2] == {"model": "gpt-6-astra", "effort": "ultra"}


def test_cancellation_interrupts_actual_turn_and_never_reports_completion(tmp_path, monkeypatch):
    cancel = threading.Event()
    client = FakeClient()
    result, events = run_fake(
        tmp_path, monkeypatch, client,
        on_event=lambda event: cancel.set() if event["type"] == "turn_started" else None,
        cancelled=cancel.is_set,
    )
    assert result["status"] == "cancelled"
    assert client.interrupts == [("thread-1", "turn-1")]
    assert any(event["type"] == "interrupt_requested" for event in events)


def test_native_reroute_is_failure_instead_of_silent_model_substitution(tmp_path, monkeypatch):
    client = FakeClient([("model/rerouted", {"fromModel": "gpt-6-astra", "toModel": "other"})])
    result, _ = run_fake(tmp_path, monkeypatch, client)
    assert result["status"] == "failed"
    assert "rerouted" in result["error"]


def test_idle_turn_timeout_requests_native_interrupt(tmp_path, monkeypatch):
    client = FakeClient()
    result, events = run_fake(tmp_path, monkeypatch, client, timeout=0.05)
    assert result["status"] == "cancelled"
    assert client.interrupts == [("thread-1", "turn-1")]
    assert any(event["type"] == "interrupt_requested" and event["reason"] == "timeout" for event in events)


def test_completed_reasoning_content_is_not_persisted_as_run_evidence(tmp_path, monkeypatch):
    client = FakeClient([
        ("item/completed", {"item": {"type": "reasoning", "id": "reason", "content": ["PRIVATE-SENTINEL"], "summary": ["SUMMARY-SENTINEL"]}}),
        ("item/completed", {"item": {"type": "agentMessage", "id": "answer", "phase": "final_answer", "text": "result"}}),
        ("turn/completed", {"turn": {"id": "turn-1", "status": "completed", "items": [
            {"type": "reasoning", "id": "embedded", "content": ["EMBEDDED-PRIVATE-SENTINEL"], "summary": []},
        ]}}),
    ])
    result, events = run_fake(tmp_path, monkeypatch, client)
    assert result["status"] == "completed"
    assert "PRIVATE-SENTINEL" not in json.dumps(events)
    assert "SUMMARY-SENTINEL" not in json.dumps(events)
