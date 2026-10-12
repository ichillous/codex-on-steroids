"""Native Codex workers, preserving Astra/Ultra and actual permission responses."""
from __future__ import annotations
import os
import queue
import threading
import time
import tomllib
from pathlib import Path
from .adapters.codex import ApprovalBridge, RoutedCodexClient, WireObject, bounded_call, client_config, plain
from .adapters.ide import capability_summary

class WorkerRuntime:
    def __init__(self, workspace: Path, state_dir: Path, model="gpt-6-astra", effort="ultra", timeout_seconds=1800):
        self.workspace, self.state_dir = Path(workspace).resolve(), Path(state_dir).resolve()
        self.model, self.effort, self.timeout = model, effort, timeout_seconds

    def role(self, role):
        path = (self.workspace / ".codex/agents" / (role + ".toml")).resolve()
        if not path.is_relative_to(self.workspace / ".codex/agents") or not path.is_file():
            raise ValueError(f"Missing canonical role definition: {role}")
        definition = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        if definition.get("model") != self.model or definition.get("model_reasoning_effort") != self.effort:
            raise ValueError("Canonical role model/effort differs from explicitly requested runtime")
        if not definition.get("developer_instructions"):
            raise ValueError(f"Role has no instructions: {role}")
        return definition, path

    def _probe_client(self, client):
        rpc = lambda method, params: plain(bounded_call(lambda: client.request(method, params, response_model=WireObject)))
        initialized = plain(bounded_call(client.initialize))
        account = plain(bounded_call(client.account_read))
        catalog = plain(bounded_call(lambda: client.model_list(include_hidden=True)))
        model = next((item for item in catalog.get("data", []) if item.get("model") == self.model or item.get("id") == self.model), None)
        efforts = [x.get("reasoningEffort") for x in model.get("supportedReasoningEfforts", [])] if model else []
        effective = rpc("config/read", {"cwd": str(self.workspace), "includeLayers": False}).get("config", {})
        authenticated = account.get("account") is not None or not account.get("requiresOpenaiAuth", True)
        result = {"status": "available" if authenticated and model and self.effort in efforts else "unavailable",
                  "protocol": initialized, "authentication": {"authenticated": authenticated,
                        "type": (account.get("account") or {}).get("type")},
                  "selected_model": self.model, "selected_effort": self.effort,
                  "model_available": model is not None, "supported_efforts": efforts,
                  "effective_config": {k: effective.get(k) for k in ("model", "model_reasoning_effort", "sandbox_mode", "approval_policy")}}
        try:
            mcp = rpc("mcpServerStatus/list", {})
            result["mcp"] = capability_summary(mcp.get("data", []))
        except Exception as exc:
            result["mcp"] = {"status": "unavailable", "error": str(exc)}
        result["limitations"] = ["No model turn executed by this probe.", "MCP tool presence does not prove a project is loaded or a tool action succeeds."]
        return result

    def probe(self):
        client = RoutedCodexClient(client_config(self.workspace), lambda *_: {"decision": "cancel"})
        try:
            client.start()
            return self._probe_client(client)
        finally:
            client.stop_owned_tree()

    def run(self, *, role, prompt, cwd, operation_id, read_only, on_event, cancelled, resume_thread_id=None):
        definition, role_path = self.role(role)
        stopped = threading.Event()
        cancellation = lambda: stopped.is_set() or cancelled()
        bridge = ApprovalBridge(self.state_dir, operation_id, on_event, cancellation, self.timeout)
        client = RoutedCodexClient(client_config(Path(cwd)), bridge)
        result = {"status": "failed", "role": role, "model": self.model, "effort": self.effort, "timeout_seconds": self.timeout}
        events = queue.Queue()
        started_at = time.monotonic()
        thread_id = turn_id = None
        def call(function, timeout=45):
            return bounded_call(function, timeout, cancellation)
        try:
            client.start()
            on_event({"type": "worker_started", "worker_pid": client.worker_pid})
            call(client.initialize)
            sandbox = "read-only" if read_only else "workspace-write"
            params = {"cwd": str(Path(cwd).resolve()), "model": self.model, "sandbox": sandbox,
                      "developerInstructions": definition["developer_instructions"],
                      "config": {"model_reasoning_effort": self.effort, "features.multi_agent": False,
                                 "mcp_servers.workspace-engineering.enabled": False}}
            if resume_thread_id:
                observed = plain(call(lambda: client.thread_read(resume_thread_id)))
                if observed.get("thread", {}).get("status", {}).get("type") != "idle":
                    raise ValueError("Cannot resume a thread that is not confirmed idle")
                started = plain(call(lambda: client.thread_resume(resume_thread_id, params)))
            else:
                started = plain(call(lambda: client.thread_start(params)))
            thread_id = started["thread"]["id"]
            result.update(thread_id=thread_id,
                          effective_config={k: started.get(k) for k in ("model", "reasoningEffort", "sandbox", "approvalPolicy", "approvalsReviewer", "cwd")},
                          instruction_sources=started.get("instructionSources", []), role_source=str(role_path))
            on_event({"type": "thread_started", "thread_id": thread_id, "effective_config": result["effective_config"]})
            if started.get("model") != self.model or started.get("reasoningEffort") != self.effort:
                raise ValueError("Native runtime did not retain the requested model and reasoning effort")
            actual_cwd = started.get("cwd")
            if not actual_cwd or os.path.normcase(str(Path(actual_cwd).resolve())) != os.path.normcase(str(Path(cwd).resolve())):
                raise ValueError("Native runtime returned a different checkout directory")
            actual_sandbox = started.get("sandbox", {}).get("type")
            expected = "readOnly" if read_only else "workspaceWrite"
            if actual_sandbox != expected:
                raise ValueError(f"Native runtime returned sandbox {actual_sandbox}; expected {expected}")
            started_turn = plain(call(lambda: client.turn_start(thread_id, prompt, {"model": self.model, "effort": self.effort})))
            turn_id = started_turn["turn"]["id"]
            result["turn_id"] = turn_id
            on_event({"type": "turn_started", "thread_id": thread_id, "turn_id": turn_id})
            def drain():
                try:
                    while True:
                        notification = client.next_turn_notification(turn_id)
                        events.put((notification.method, plain(notification.payload)))
                        if notification.method == "turn/completed":
                            return
                except BaseException as exc:
                    events.put(("transport_error", exc))
            threading.Thread(target=drain, daemon=True).start()
            messages = {}
            interrupt_time = None
            while True:
                timeout = time.monotonic() - started_at >= self.timeout
                if (cancelled() or timeout) and interrupt_time is None:
                    stopped.set()
                    interrupt_time = time.monotonic()
                    result["termination_reason"] = "timeout" if timeout else "cancelled"
                    bounded_call(lambda: client.turn_interrupt(thread_id, turn_id), timeout=10)
                    on_event({"type": "interrupt_requested", "reason": result["termination_reason"]})
                if interrupt_time and time.monotonic() - interrupt_time > 15:
                    raise TimeoutError("Native interrupt did not settle the turn; inspect the recorded worker")
                try:
                    method, payload = events.get(timeout=0.2)
                except queue.Empty:
                    continue
                if method == "transport_error":
                    raise payload
                # Persist source/tool and public results, never private reasoning.
                if method == "item/completed" and payload.get("item", {}).get("type") == "reasoning":
                    continue
                if method in {"item/completed", "turn/completed", "error", "thread/tokenUsage/updated", "model/rerouted"}:
                    recorded = payload
                    if method == "turn/completed":
                        recorded = dict(payload) | {"turn": dict(payload["turn"]) | {"items": [item for item in payload["turn"].get("items", []) if item.get("type") != "reasoning"]}}
                    on_event({"type": "native_event", "method": method, "payload": recorded})
                if method == "model/rerouted":
                    raise ValueError("Native runtime rerouted the selected model; inspect before continuing")
                if method == "thread/tokenUsage/updated":
                    result["usage"] = payload.get("tokenUsage")
                if method == "item/completed":
                    item = payload.get("item", {})
                    if item.get("type") == "agentMessage":
                        messages[item["id"]] = item
                if method == "turn/completed":
                    turn = payload["turn"]
                    status = turn.get("status")
                    result["status"] = "cancelled" if interrupt_time or status == "interrupted" else status
                    if status == "failed":
                        result["error"] = (turn.get("error") or {}).get("message", "Native turn failed")
                    finals = [item.get("text", "") for item in messages.values() if item.get("phase") == "final_answer"]
                    if not finals:
                        finals = [item.get("text", "") for item in messages.values() if item.get("phase") != "commentary"]
                    result["text"] = "\n".join(finals)
                    break
        except InterruptedError as exc:
            result.update(status="cancelled", error=str(exc))
        except Exception as exc:
            result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            stopped.set()
            client.stop_owned_tree()
            result["duration_seconds"] = round(time.monotonic() - started_at, 3)
            on_event({"type": "worker_stopped", "thread_id": thread_id, "turn_id": turn_id, "status": result["status"]})
        return result
