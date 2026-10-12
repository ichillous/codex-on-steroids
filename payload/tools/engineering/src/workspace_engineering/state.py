"""Durable operation journal, ownership and human decisions, separate from graph checkpoints."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .util import atomic_json, digest, process_alive, utcnow

TERMINAL = {"completed", "failed", "cancelled", "needs_reconciliation", "incomplete"}


class StateConflict(RuntimeError):
    pass


class Store:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "operations.sqlite"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, task TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}', pid INTEGER, cancel INTEGER NOT NULL DEFAULT 0,
                    created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage TEXT NOT NULL,
                    status TEXT NOT NULL, data TEXT NOT NULL, result TEXT,
                    created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    operation_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS leases (
                    resource TEXT PRIMARY KEY, run_id TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                    status TEXT NOT NULL, event TEXT NOT NULL, decision TEXT, created TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create_run(self, task: dict) -> str:
        run_id = uuid.uuid4().hex
        now = utcnow()
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,status,task,created,updated) VALUES(?,?,?,?,?)",
                       (run_id, "queued", json.dumps(task), now, now))
        atomic_json(self.run_dir(run_id) / "task.json", task)
        return run_id

    def run_dir(self, run_id: str) -> Path:
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("Invalid run ID")
        return self.directory / "runs" / run_id

    def get_run(self, run_id: str) -> dict:
        self.run_dir(run_id)
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(f"Unknown run: {run_id}")
        result = dict(row)
        result["task"] = json.loads(result["task"])
        result["data"] = json.loads(result["data"])
        return result

    def update_run(self, run_id: str, status: str | None = None, **data: Any) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status,data FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            payload = json.loads(row["data"])
            payload.update(data)
            db.execute("UPDATE runs SET status=?,data=?,updated=? WHERE id=?",
                       (status or row["status"], json.dumps(payload, default=str), utcnow(), run_id))

    def claim_run(self, run_id: str) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT pid,status,cancel,data FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            if row["pid"] and process_alive(row["pid"]):
                raise StateConflict(f"Run is already owned by process {row['pid']}")
            if row["cancel"]:
                raise StateConflict("Cancelled runs cannot be resumed; create a new scoped task")
            if row["status"] in {"completed", "incomplete"}:
                raise StateConflict("Finished runs are immutable; create a new task or independent review")
            active = db.execute("SELECT id FROM operations WHERE run_id=? AND status IN ('prepared','running','needs_input','needs_reconciliation')", (run_id,)).fetchall()
            if active:
                raise StateConflict("Unsettled operations require reconciliation: " + ", ".join(r["id"] for r in active))
            data = json.loads(row["data"])
            if data.get("error"):
                db.execute("INSERT INTO events(run_id,kind,payload,created) VALUES(?,?,?,?)", (run_id, "previous_run_error", json.dumps({"error": data["error"]}), utcnow()))
                data["error"] = None
            db.execute("UPDATE runs SET pid=?,status='running',data=?,updated=? WHERE id=?", (os.getpid(), json.dumps(data), utcnow(), run_id))

    def finish_process(self, run_id: str, release: bool) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET pid=NULL,updated=? WHERE id=? AND pid=?", (utcnow(), run_id, os.getpid()))
            if release:
                db.execute("DELETE FROM leases WHERE run_id=?", (run_id,))

    def acquire_paths(self, run_id: str, paths: list[Path]) -> None:
        resources = [os.path.normcase(str(p.resolve())).rstrip("\\/") for p in paths]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT resource,run_id FROM leases").fetchall()
            for path in resources:
                for row in existing:
                    other = row["resource"]
                    overlap = path == other or path.startswith(other + os.sep) or other.startswith(path + os.sep)
                    if overlap and row["run_id"] != run_id:
                        raise StateConflict(f"Checkout overlaps run {row['run_id']}: {other}")
                db.execute("INSERT OR IGNORE INTO leases VALUES(?,?,?)", (path, run_id, utcnow()))

    def cancel(self, run_id: str) -> None:
        self.get_run(run_id)
        with self.connect() as db:
            db.execute("UPDATE runs SET cancel=1,updated=? WHERE id=?", (utcnow(), run_id))

    def cancelled(self, run_id: str) -> bool:
        return bool(self.get_run(run_id)["cancel"])

    def operation(self, operation_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["data"] = json.loads(result["data"])
        result["result"] = json.loads(result["result"]) if result["result"] else None
        return result

    def begin_operation(self, run_id: str, key: str, stage: str, data: dict) -> tuple[str, dict | None]:
        operation_id = digest([run_id, key])[:32]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status,result,data FROM operations WHERE id=?", (operation_id,)).fetchone()
            if row:
                if row["status"] == "completed":
                    return operation_id, json.loads(row["result"])
                if row["status"] != "retry_authorized":
                    raise StateConflict(f"Operation {operation_id} is {row['status']}; reconcile before retry")
                db.execute("INSERT INTO events(run_id,operation_id,kind,payload,created) VALUES(?,?,?,?,?)", (run_id, operation_id, "operation_retry", json.dumps(dict(row)), utcnow()))
                db.execute("UPDATE operations SET status='prepared',data=?,result=NULL,updated=? WHERE id=?", (json.dumps(data), utcnow(), operation_id))
            else:
                now = utcnow()
                db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?,?)",
                           (operation_id, run_id, stage, "prepared", json.dumps(data), None, now, now))
        return operation_id, None

    def update_operation(self, operation_id: str, status: str, result: dict | None = None, **data) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM operations WHERE id=?", (operation_id,)).fetchone()
            if not row:
                raise KeyError(operation_id)
            payload = json.loads(row["data"])
            payload.update(data)
            db.execute("UPDATE operations SET status=?,data=?,result=COALESCE(?,result),updated=? WHERE id=?",
                       (status, json.dumps(payload, default=str), json.dumps(result, default=str) if result is not None else None, utcnow(), operation_id))

    def operations(self, run_id: str) -> list[dict]:
        with self.connect() as db:
            ids = [row["id"] for row in db.execute("SELECT id FROM operations WHERE run_id=? ORDER BY created,id", (run_id,))]
        return [self.operation(x) for x in ids]

    def event(self, run_id: str, operation_id: str | None, event: dict) -> None:
        kind = event.get("type", event.get("kind", "event"))
        with self.connect() as db:
            db.execute("INSERT INTO events(run_id,operation_id,kind,payload,created) VALUES(?,?,?,?,?)",
                       (run_id, operation_id, kind, json.dumps(event, default=str), utcnow()))
        if kind == "approval":
            self.pending_approval(run_id, operation_id, event)

    def pending_approval(self, run_id: str, operation_id: str, event: dict) -> str:
        approval_id = digest([operation_id, event.get("request_id"), event.get("method")])[:32]
        path = Path(event["decision_path"]).resolve()
        if not path.is_relative_to(self.directory / "approvals"):
            raise ValueError("Approval decision path escaped state directory")
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO approvals VALUES(?,?,?,?,?,?,?)",
                       (approval_id, run_id, operation_id, "pending", json.dumps(event, default=str), None, utcnow()))
        self.update_run(run_id, "needs_input", pending_approval=approval_id)
        return approval_id

    def approvals(self, run_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM approvals WHERE run_id=? ORDER BY created", (run_id,)).fetchall()
        return [dict(row) | {"event": json.loads(row["event"])} for row in rows]

    def approve(self, run_id: str, approval_id: str, decision: str) -> None:
        run = self.get_run(run_id)
        if run["cancel"] or not process_alive(run["pid"]):
            raise StateConflict("The worker owner is no longer live; approval cannot be replayed")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM approvals WHERE id=? AND run_id=?", (approval_id, run_id)).fetchone()
            if not row or row["status"] != "pending":
                raise StateConflict("Approval is missing or already decided")
            event = json.loads(row["event"])
            params = event.get("params", {})
            offered = params.get("availableDecisions")
            allowed = [x for x in offered if isinstance(x, str)] if offered else ["accept", "decline", "cancel", "acceptForSession"]
            if decision not in allowed:
                raise ValueError(f"Decision must be one of {allowed}")
            operation = db.execute("SELECT status FROM operations WHERE id=?", (row["operation_id"],)).fetchone()
            if not operation or operation["status"] not in {"running", "needs_input"}:
                raise StateConflict("Native request no longer belongs to an active operation")
            path = Path(event["decision_path"]).resolve()
            if not path.is_relative_to(self.directory / "approvals"):
                raise ValueError("Invalid decision path")
            atomic_json(path, {"decision": decision})
            db.execute("UPDATE approvals SET status='decided',decision=? WHERE id=?", (decision, approval_id))
            remaining = db.execute("SELECT id FROM approvals WHERE run_id=? AND status='pending' ORDER BY created LIMIT 1", (run_id,)).fetchone()
        self.update_run(run_id, "needs_input" if remaining else "running", pending_approval=remaining["id"] if remaining else None)

    def reconcile_retry(self, run_id: str, operation_id: str, acknowledge: bool) -> None:
        run = self.get_run(run_id)
        op = self.operation(operation_id)
        if not acknowledge:
            raise ValueError("Inspect worker and checkout, then provide --acknowledge-risk")
        if not op or op["run_id"] != run_id or op["status"] == "completed":
            raise StateConflict("Operation is missing or completed")
        if process_alive(run["pid"]) or process_alive(op["data"].get("worker_pid")):
            raise StateConflict("The coordinator or worker process may still be alive")
        if run["cancel"]:
            raise StateConflict("Cancelled runs cannot retry; reconcile with abandon, then create a new task")
        self.update_operation(operation_id, "retry_authorized", reconciliation={"action": "retry", "at": utcnow(), "acknowledged": True})
        with self.connect() as db:
            db.execute("UPDATE approvals SET status='expired' WHERE operation_id=? AND status='pending'", (operation_id,))
        self.update_run(run_id, "ready", reconciliation="Retry explicitly authorized after external-state inspection")

    def reconcile_abandon(self, run_id: str, operation_id: str, acknowledge: bool) -> None:
        """Confirm a stopped operation, keep all source edits, and retire its run."""
        run = self.get_run(run_id)
        op = self.operation(operation_id)
        if not acknowledge:
            raise ValueError("Inspect worker and checkout, then provide --acknowledge-risk")
        if not op or op["run_id"] != run_id or op["status"] == "completed":
            raise StateConflict("Operation is missing or completed")
        if process_alive(run["pid"]) or process_alive(op["data"].get("worker_pid")):
            raise StateConflict("The coordinator or worker process may still be alive")
        self.update_operation(operation_id, "abandoned", reconciliation={"action": "abandon", "at": utcnow(), "acknowledged": True})
        with self.connect() as db:
            db.execute("UPDATE approvals SET status='expired' WHERE operation_id=? AND status='pending'", (operation_id,))
            db.execute("UPDATE runs SET cancel=1,status='cancelled',updated=? WHERE id=?", (utcnow(), run_id))
            outstanding = db.execute("SELECT id FROM operations WHERE run_id=? AND status IN ('prepared','running','needs_input','needs_reconciliation')", (run_id,)).fetchall()
            if not outstanding:
                db.execute("DELETE FROM leases WHERE run_id=?", (run_id,))
