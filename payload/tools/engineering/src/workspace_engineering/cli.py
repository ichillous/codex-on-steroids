"""Explicit, scriptable entry point for engineering runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import load_task


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="workspace-engineering")
    root.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[4])
    root.add_argument("--state-dir", type=Path)
    sub = root.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Inspect installation; --live probes native app-server without a model turn")
    doctor.add_argument("--live", action="store_true")
    for name in ("investigate", "run"):
        entry = sub.add_parser(name)
        entry.add_argument("--task", type=Path, required=True)
        entry.add_argument("--background", action="store_true")
    for name in ("status", "report", "resume", "cancel", "review", "execute", "approve", "reconcile"):
        entry = sub.add_parser(name)
        entry.add_argument("--run", required=True)
        if name in {"resume", "review"}:
            entry.add_argument("--background", action="store_true")
        if name == "approve":
            entry.add_argument("--request", required=True, help="Approval ID displayed by status")
            entry.add_argument("--decision", required=True, help="An exact native decision offered by the request")
        if name == "reconcile":
            entry.add_argument("--operation", help="Required for retry or abandon")
            entry.add_argument("--action", choices=["retry", "abandon", "release"], required=True)
            entry.add_argument("--acknowledge-risk", action="store_true")
    sub.add_parser("mcp", help="Serve the local engineering tools over stdio")
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "mcp":
            from .mcp_server import build_server
            build_server(args.workspace, args.state_dir).run(transport="stdio")
            return 0
        if args.command == "doctor":
            from .doctor import diagnose
            result = diagnose(args.workspace, args.live)
        else:
            from .coordinator import Coordinator
            from .service import EngineeringService
            service = EngineeringService(args.workspace, args.state_dir)
            if args.command in {"investigate", "run"}:
                result = service.start(load_task(args.task, "investigate" if args.command == "investigate" else "implement"), args.background)
            elif args.command == "status":
                result = service.status(args.run)
            elif args.command == "report":
                result = service.report(args.run)
            elif args.command == "cancel":
                result = service.cancel(args.run)
            elif args.command == "review":
                result = service.review(args.run, args.background)
            elif args.command in {"execute", "resume"}:
                result = service.launch(args.run) if getattr(args, "background", False) else Coordinator(args.workspace, service.store).execute(args.run)
            elif args.command == "approve":
                service.store.approve(args.run, args.request, args.decision)
                result = {"run_id": args.run, "approval_id": args.request, "status": "decision_delivered"}
            else:
                if args.action == "release":
                    if args.operation:
                        raise ValueError("Checkout release applies to the whole run, without --operation")
                    service.store.reconcile_release(args.run, args.acknowledge_risk)
                else:
                    if not args.operation:
                        raise ValueError("Retry or abandon requires --operation")
                    reconcile = service.store.reconcile_retry if args.action == "retry" else service.store.reconcile_abandon
                    reconcile(args.run, args.operation, args.acknowledge_risk)
                result = service.status(args.run)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        return 1 if result.get("status") in {"failed", "needs_reconciliation", "incomplete", "cancelled"} else 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "message": "Inspect run status and reconcile any unsettled operations before resume."}), file=sys.stderr)
        return 130
    except Exception as exc:
        print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
