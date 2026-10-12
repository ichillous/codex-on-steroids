"""Create a new, collision-safe idea session and preserve its input bytes.

No research runs, no Git action, no graph exception, no completed-result pointer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WORKSPACE = Path(__file__).resolve().parents[2]


def safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).strip(" .")
    name = re.sub(r"\s+", " ", name)[:100].rstrip(" .")
    if not name or re.fullmatch(r"(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name):
        raise ValueError("choose a nonempty Windows-safe idea name")
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--name", help="original display name; folder is sanitized")
    parser.add_argument("--timezone", help="IANA zone, e.g. America/New_York; defaults to OS local zone")
    args = parser.parse_args()
    source = args.input.resolve()
    if not source.is_file() or not source.is_relative_to(WORKSPACE):
        parser.error("input must be an existing file inside this workspace")
    display = args.name or source.stem
    try:
        folder = safe_name(display)
        current = datetime.now(ZoneInfo(args.timezone)) if args.timezone else datetime.now().astimezone()
    except (ValueError, ZoneInfoNotFoundError) as exc:
        parser.error(str(exc))
    idea = WORKSPACE / "Ideas" / folder
    sessions = (idea / "sessions").resolve()
    if not sessions.is_relative_to(WORKSPACE / "Ideas"):
        parser.error("resolved output escaped Ideas")
    sessions.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        session_id = current.strftime("%Y-%m-%d_%H%M%S%z") + "_" + secrets.token_hex(4)
        session = sessions / session_id
        try:
            session.mkdir(exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        parser.error("could not allocate a unique session directory")
    for name in ("inputs", "report", "evidenceandlogic/experiments", "evidenceandlogic/agent-results", "evidenceandlogic/review", "run"):
        (session / name).mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with (session / "inputs" / "idea-original.md").open("xb") as dest:
        dest.write(raw)
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise RuntimeError("input changed during initialization; preserve this partial session and reconcile")
    metadata = {
        "session_id": session_id, "idea_name": display, "created_at": current.isoformat(),
        "timezone": args.timezone or str(current.tzinfo), "input_path": str(source),
        "input_sha256": digest, "status": "in_progress", "status_reason": "Input preserved; research not started",
        "scope": "Not framed yet", "route": "not_selected", "route_reason": "Verify tools and schema before selection",
        "model": "not_verified", "tools": [], "workers": [], "run_ids": [],
        "graph_status": "not_checked", "graph_exception": None, "completed_checks": [], "blocked_items": [],
        "next_resume_action": "Read workflow, frame brief and acceptance criteria, inspect actual tools/model/graph; reconcile any active work before continuing",
    }
    (session / "run" / "session.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (session / "run" / "state.md").write_text(f"# Session state\n\nCreated {current.isoformat()}. Input preserved and hash verified.\n\nStatus: in_progress. Research and tool verification have not run. No workers are registered.\n\nNext: {metadata['next_resume_action']}.\n\nThe coordinator must update the idea index to identify this latest attempt. No completed-result pointer was changed by initialization.\n", encoding="utf-8")
    print(json.dumps({"session_id": session_id, "session": str(session), "input_sha256": digest, "status": "in_progress", "index_changed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
