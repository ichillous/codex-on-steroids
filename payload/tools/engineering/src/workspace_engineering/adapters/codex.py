"""Pinned Codex SDK transport with explicit native approval routing.

The SDK's default handler accepts approvals. This adapter always replaces it.
One small pinned override preserves the exact JSON-RPC request ID, which the
SDK's public two-argument approval callback omits. No credentials are read here.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import sys
from pathlib import Path

from openai_codex.client import CodexClient, CodexConfig
from pydantic import BaseModel, ConfigDict

from ..util import digest


class WireObject(BaseModel):
    model_config = ConfigDict(extra="allow")


def plain(value):
    return value.model_dump(mode="json", by_alias=True) if hasattr(value, "model_dump") else value


def bounded_call(function, timeout=30.0, cancelled=lambda: False):
    """Bound waiting without putting an unbounded SDK read on the main thread."""
    output = queue.Queue(maxsize=1)
    def run():
        try:
            output.put((True, function()))
        except BaseException as exc:
            output.put((False, exc))
    threading.Thread(target=run, daemon=True).start()
    deadline = time.monotonic() + timeout
    while True:
        if cancelled():
            raise InterruptedError("Codex operation cancelled")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Codex RPC exceeded {timeout:g} seconds")
        try:
            ok, value = output.get(timeout=min(0.2, remaining))
        except queue.Empty:
            continue
        if ok:
            return value
        raise value


class ApprovalBridge:
    def __init__(self, state_dir: Path, operation_id: str, on_event, cancelled, timeout=1800):
        self.directory = state_dir / "approvals" / digest(operation_id)
        self.operation_id = operation_id
        self.on_event = on_event
        self.cancelled = cancelled
        self.timeout = timeout

    def __call__(self, request_id, method, params):
        params = params or {}
        if method not in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
            # Unknown native input/permission schemas require a new adapter, not
            # an invented acceptance response or the SDK's permissive fallback.
            self.on_event({"type": "unsupported_native_request", "request_id": request_id, "method": method})
            raise RuntimeError(f"Unsupported native request: {method}; inspect the run")
        identity = [type(request_id).__name__, request_id, params.get("threadId"), params.get("turnId")]
        path = self.directory / (digest(identity) + ".json")
        if path.exists():
            raise RuntimeError("Existing decision artifact cannot be replayed for a new native request")
        offered = params.get("availableDecisions") or ["accept", "acceptForSession", "decline", "cancel"]
        allowed = [value for value in offered if isinstance(value, str)]
        event = {"type": "approval", "operation_id": self.operation_id, "request_id": request_id,
                 "method": method, "params": params, "decision_path": str(path)}
        direct = self.on_event(event)
        deadline = time.monotonic() + self.timeout
        while True:
            if self.cancelled() or time.monotonic() >= deadline:
                return {"decision": "cancel"}
            decision = direct
            if decision is None and path.is_file():
                decision = json.loads(path.read_text(encoding="utf-8"))
            if decision is not None:
                if not isinstance(decision, dict) or set(decision) != {"decision"} or decision["decision"] not in allowed:
                    raise ValueError("Decision must match an offered native string decision")
                return decision
            time.sleep(0.2)


class RoutedCodexClient(CodexClient):
    def __init__(self, config: CodexConfig, bridge):
        super().__init__(config, approval_handler=lambda *_: {"decision": "cancel"})
        self.bridge = bridge

    def _handle_server_request(self, msg):
        return self.bridge(msg["id"], msg["method"], msg.get("params"))

    @property
    def worker_pid(self):
        return self._proc.pid if self._proc else None

    def stop_owned_tree(self):
        # The SDK owns this actual process object; never kill a caller-supplied PID.
        import os
        import subprocess
        process = self._proc
        if process is not None and process.poll() is None and os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        self.close()


def client_config(cwd: Path) -> CodexConfig:
    # A disabled entry still needs a valid transport. Isolated repositories may
    # have no parent project declaration to merge with this override.
    disabled_coordinator = 'mcp_servers.workspace-engineering={command=' + json.dumps(sys.executable) + ',args=[],enabled=false}'
    return CodexConfig(cwd=str(cwd), client_name="workspace_engineering", client_title="Workspace Engineering",
                       config_overrides=("features.multi_agent=false", disabled_coordinator))
