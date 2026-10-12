"""Environment checks without model turns, credentials, builds or migrations."""

from __future__ import annotations

import importlib.metadata
import sys
import tomllib
from pathlib import Path

import yaml


def diagnose(workspace: Path, live: bool = False) -> dict:
    from .adapters.graphify import GraphifyAdapter
    from .repository_manager import RepositoryManager
    from .validation_runner import ValidationRunner
    result = {"workspace": str(workspace.resolve()), "python": sys.executable, "python_version": sys.version,
              "packages": {}, "checks": {}, "live_requested": live}
    for package in ("langgraph", "langgraph-checkpoint-sqlite", "openai-codex", "mcp"):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = "missing"
    def check(name, action):
        try:
            observed = action()
            failed = isinstance(observed, dict) and observed.get("status") in {"failed", "blocked", "unavailable", "unsupported"}
            result["checks"][name] = {"status": "failed" if failed else "passed", "result": observed}
        except Exception as exc:
            result["checks"][name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    check("repositories", lambda: RepositoryManager(workspace).inventory())
    check("graph_publication", lambda: GraphifyAdapter(workspace).publication())
    check("validation_catalog", lambda: ValidationRunner(workspace).catalog())
    def project_config():
        data = tomllib.loads((workspace / ".codex/config.toml").read_text(encoding="utf-8-sig"))
        # Existing project MCP environment values can contain credentials.
        # Diagnose registration without echoing configuration or env contents.
        return {"parsed": True, "keys": sorted(data),
                "mcp_servers": sorted(data.get("mcp_servers", {})),
                "model": data.get("model"),
                "model_reasoning_effort": data.get("model_reasoning_effort"),
                "sandbox_mode": data.get("sandbox_mode")}
    check("project_config", project_config)
    def roles():
        required = ["investigator", "implementer", "reviewer", "oracle-specialist", "ui-specialist", "integration-specialist"]
        found = {}
        for role in required:
            data = tomllib.loads((workspace / f".codex/agents/{role}.toml").read_text(encoding="utf-8-sig"))
            if not data.get("developer_instructions") or data.get("name") != role:
                raise ValueError(f"Invalid role: {role}")
            found[role] = {key: data.get(key) for key in ("model", "model_reasoning_effort", "sandbox_mode")}
        return found
    check("roles", roles)
    check("workflow_catalog", lambda: yaml.safe_load((workspace / "tools/engineering/config/workflows.yaml").read_text(encoding="utf-8")))
    if live:
        from .worker_runtime import WorkerRuntime
        check("codex_app_server", lambda: WorkerRuntime(workspace, workspace / ".engineering-state").probe())
    result["status"] = "failed" if any(x["status"] == "failed" for x in result["checks"].values()) or "missing" in result["packages"].values() else "checked"
    result["limitations"] = ["Configuration presence is not proof of VS Code discovery or tool-server availability.",
                             "No model turn or application build is executed by doctor."]
    return result
