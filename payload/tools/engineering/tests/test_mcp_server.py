"""Real MCP stdio exchange against a subprocess; no model turns or app builds."""

import json
from pathlib import Path
import subprocess
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from workspace_engineering.state import Store


def _server(workspace: Path, state: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-B", "-m", "workspace_engineering", "--workspace", str(workspace),
              "--state-dir", str(state), "mcp"],
        cwd=workspace,
    )


def _payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(item.text for item in result.content if item.type == "text"))


def test_stdio_initializes_lists_seven_tools_and_keeps_serving_after_unknown_run(tmp_path):
    workspace = Path(__file__).resolve().parents[3]

    async def exchange():
        with anyio.fail_after(45):
            async with stdio_client(_server(workspace, tmp_path / "state")) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=25) as session:
                    initialized = await session.initialize()
                    assert initialized.server_info.name == "workspace-engineering"
                    available = await session.list_tools()
                    assert {tool.name for tool in available.tools} == {
                        "engineering_start", "engineering_status", "engineering_resume",
                        "engineering_cancel", "engineering_report", "engineering_review", "engineering_doctor",
                    }
                    missing = await session.call_tool("engineering_status", {"run_id": "0" * 32})
                    assert missing.is_error
                    assert "Unknown run" in " ".join(item.text for item in missing.content if item.type == "text")
                    diagnostic = await session.call_tool("engineering_doctor", {"live": False})
                    assert not diagnostic.is_error
                    result = _payload(diagnostic)
                    assert result["workspace"] == str(workspace)
                    assert result["live_requested"] is False
                    assert "codex_app_server" not in result["checks"]
                    assert result["packages"]["mcp"] == "2.2.0"
                    assert result["checks"]["roles"]["status"] == "passed"

    anyio.run(exchange)


def test_stdio_resume_of_uncertain_worker_preserves_staged_work_and_does_not_dispatch(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("existing user work\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "unrelated.txt"], check=True, capture_output=True)
    original_index = (tmp_path / ".git/index").read_bytes()
    state = tmp_path / ".engineering-state"
    store = Store(state)
    run_id = store.create_run({"title": "Interrupted fixture"})
    operation_id, _ = store.begin_operation(run_id, "implement:0", "implement", {})
    store.update_operation(operation_id, "needs_reconciliation")
    store.update_run(run_id, "needs_reconciliation")

    async def exchange():
        with anyio.fail_after(30):
            async with stdio_client(_server(tmp_path, state)) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=15) as session:
                    await session.initialize()
                    status = _payload(await session.call_tool("engineering_status", {"run_id": run_id}))
                    assert status["requires_reconciliation"] is True
                    blocked = await session.call_tool("engineering_resume", {"run_id": run_id})
                    assert blocked.is_error
                    assert "Reconcile unsettled operations" in " ".join(
                        item.text for item in blocked.content if item.type == "text"
                    )

    anyio.run(exchange)
    assert unrelated.read_text(encoding="utf-8") == "existing user work\n"
    assert (tmp_path / ".git/index").read_bytes() == original_index
    assert Store(state).operation(operation_id)["status"] == "needs_reconciliation"
    assert not (store.run_dir(run_id) / "coordinator.log").exists()
