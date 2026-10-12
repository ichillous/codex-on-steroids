"""Local stdio tools. Workers disable this server to prevent nested orchestration."""

from pathlib import Path
from functools import wraps

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .models import Task
from .service import EngineeringService
from .state import StateConflict


def expected_errors(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, KeyError, StateConflict) as exc:
            raise ToolError(str(exc)) from exc
    return call


def build_server(workspace: Path, state_dir: Path | None = None) -> MCPServer:
    service = EngineeringService(workspace, state_dir)
    server = MCPServer("workspace-engineering", version="0.1.0",
                       instructions="Start only user-authorized scoped engineering work. Inspect status for native approvals. Completed checks do not alone establish acceptance.")

    @server.tool()
    @expected_errors
    def engineering_start(task: dict) -> dict:
        """Start an authorized JSON task in the background; return run ID and log location."""
        return service.start(Task.model_validate(task))

    @server.tool()
    @expected_errors
    def engineering_status(run_id: str) -> dict:
        """Read run state, operations, source/check evidence and pending native requests."""
        return service.status(run_id)

    @server.tool()
    @expected_errors
    def engineering_resume(run_id: str) -> dict:
        """Resume checkpointed work only after unsettled operations have been reconciled."""
        return service.launch(run_id)

    @server.tool()
    @expected_errors
    def engineering_cancel(run_id: str) -> dict:
        """Request cancellation; active workers interrupt at the next cancellation poll."""
        return service.cancel(run_id)

    @server.tool()
    @expected_errors
    def engineering_report(run_id: str) -> dict:
        """Write local JSON, Markdown and offline HTML reports and return their paths."""
        return service.report(run_id)

    @server.tool()
    @expected_errors
    def engineering_review(run_id: str) -> dict:
        """Start a fresh read-only review of a stopped run and current source."""
        return service.review(run_id)

    @server.tool()
    @expected_errors
    def engineering_doctor(live: bool = False) -> dict:
        """Inspect installation and optionally native protocol/auth/model availability without a model turn."""
        from .doctor import diagnose
        return diagnose(workspace, live)

    # Decisions and uncertain-operation retries stay explicit at the CLI. Model
    # workers must not approve their own native requests through another tool.
    return server
