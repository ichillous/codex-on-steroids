from __future__ import annotations

import html
import json
from pathlib import Path

from .state import Store
from .util import atomic_json


def write_report(store: Store, run_id: str) -> dict:
    run = store.get_run(run_id)
    operations = store.operations(run_id)
    report = {"run": run, "operations": operations, "approvals": store.approvals(run_id)}
    directory = store.run_dir(run_id)
    atomic_json(directory / "report.json", report)
    lines = [f"# {run['task']['title']}", "", f"Run: `{run_id}`", f"Status: **{run['status']}**", "",
             "## Requested outcome", "", run["task"]["request"], "", "## Acceptance criteria", ""]
    lines.extend(f"- {criterion}" for criterion in run["task"]["acceptance_criteria"])
    lines.extend(["", "## Execution evidence", "", "| Stage | Status | Operation |", "|---|---|---|"])
    lines.extend(f"| {op['stage']} | {op['status']} | `{op['id']}` |" for op in operations)
    lines.extend(["", "## Result and limitations", "", "```json", json.dumps(run["data"], indent=2, default=str), "```", ""])
    markdown = "\n".join(lines)
    (directory / "report.md").write_text(markdown, encoding="utf-8")
    page = "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Engineering run</title><style>body{font:16px system-ui;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#17212b;background:#f7f9fb}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:1.5rem;border:1px solid #ccd5df;border-radius:8px}h1{font-size:1.6rem}</style><h1>Engineering run</h1><pre>" + html.escape(markdown) + "</pre></html>"
    (directory / "report.html").write_text(page, encoding="utf-8")
    return {"json": str(directory / "report.json"), "markdown": str(directory / "report.md"), "html": str(directory / "report.html")}
