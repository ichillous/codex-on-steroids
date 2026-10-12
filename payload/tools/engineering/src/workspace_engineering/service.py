"""Shared job entry points for the CLI and local MCP server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .coordinator import Coordinator
from .models import Task
from .reporting import write_report
from .state import StateConflict, Store
from .util import process_alive


class EngineeringService:
    def __init__(self, workspace: Path, state_dir: Path | None = None):
        self.workspace = workspace.resolve()
        self.store = Store(state_dir or self.workspace / ".engineering-state")

    def start(self, task: Task, background: bool = True) -> dict:
        coordinator = Coordinator(self.workspace, self.store)
        run_id = coordinator.create(task)
        if background:
            return self.launch(run_id)
        return coordinator.execute(run_id)

    def launch(self, run_id: str) -> dict:
        run = self.store.get_run(run_id)
        if run["status"] in {"completed", "incomplete", "cancelled"}:
            raise StateConflict("Finished runs are immutable; create a new task or independent review")
        if process_alive(run["pid"]):
            raise StateConflict("Run already has a live coordinator")
        unsettled = [op["id"] for op in self.store.operations(run_id)
                     if op["status"] not in {"completed", "retry_authorized"}]
        if unsettled:
            raise StateConflict("Reconcile unsettled operations before resume: " + ", ".join(unsettled))
        log = self.store.run_dir(run_id) / "coordinator.log"
        args = [sys.executable, "-B", "-m", "workspace_engineering", "--workspace", str(self.workspace),
                "--state-dir", str(self.store.directory), "execute", "--run", run_id]
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with log.open("ab") as output:
            child = subprocess.Popen(args, cwd=self.workspace, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, **kwargs)
        # The child atomically claims ownership. Do not overwrite its final state here.
        self.store.event(run_id, None, {"type": "coordinator_launched", "pid": child.pid})
        return {"run_id": run_id, "status": "dispatched", "launcher_pid": child.pid, "log": str(log)}

    def status(self, run_id: str) -> dict:
        run = self.store.get_run(run_id)
        operations = self.store.operations(run_id)
        alive = process_alive(run["pid"])
        compact = [{"id": op["id"], "stage": op["stage"], "status": op["status"], "updated": op["updated"],
                    "data": {k: op["data"][k] for k in ("role", "repository", "check", "worker_pid", "thread_id", "turn_id", "reconciliation") if k in op["data"]},
                    "result_status": (op.get("result") or {}).get("status")} for op in operations]
        outcome = run["data"].get("result", {})
        return {"run_id": run_id, "status": run["status"], "coordinator_alive": alive,
                "requires_reconciliation": not alive and any(x["status"] in {"prepared", "running", "needs_input", "needs_reconciliation"} for x in operations),
                "cancel_requested": bool(run["cancel"]), "task": run["task"],
                "error": run["data"].get("error"), "outcome": outcome.get("outcome"),
                "review": outcome.get("review", {}).get("result"), "report_directory": str(self.store.run_dir(run_id)),
                "operations": compact, "approvals": self.store.approvals(run_id)}

    def cancel(self, run_id: str) -> dict:
        run = self.store.get_run(run_id)
        if run["status"] == "completed":
            return {"run_id": run_id, "status": "completed", "message": "Already completed"}
        self.store.cancel(run_id)
        if not process_alive(run["pid"]):
            unsettled = any(op["status"] in {"prepared", "running", "needs_input", "needs_reconciliation"} for op in self.store.operations(run_id))
            self.store.update_run(run_id, "needs_reconciliation" if unsettled else "cancelled")
            if not unsettled:
                self.store.finish_process(run_id, release=True)
        return self.status(run_id)

    def review(self, run_id: str, background: bool = True) -> dict:
        original = self.store.get_run(run_id)
        if process_alive(original["pid"]):
            raise StateConflict("Wait for the active run before requesting independent review")
        if any(x["status"] in {"prepared", "running", "needs_input", "needs_reconciliation"} for x in self.store.operations(run_id)):
            raise StateConflict("Reconcile unsettled workers before independent review")
        raw = dict(original["task"])
        raw.update(mode="investigate", checks=[], implementation_groups=[], max_revisions=0,
                   title=("Review: " + raw["title"])[:200],
                   request=raw["request"] + "\nIndependently review the current source and previous run artifacts at "
                   + str(self.store.run_dir(run_id)) + ". Compare source fingerprints before using previous check results. Do not implement.")
        return self.start(Task.model_validate(raw), background)

    def report(self, run_id: str) -> dict:
        return write_report(self.store, run_id)
