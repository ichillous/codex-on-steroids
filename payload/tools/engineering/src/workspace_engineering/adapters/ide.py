"""Interpret observed native MCP capabilities without pretending a declaration is live."""


def capability_summary(servers: list[dict]) -> dict:
    result = {}
    for server in servers:
        name = server.get("name", "unknown")
        tools = server.get("tools") or {}
        names = list(tools) if isinstance(tools, dict) else [t.get("name") for t in tools if isinstance(t, dict)]
        result[name] = {"tools": names, "tool_count": len(names),
                        "status": "tools_observed" if names else "no_tools_observed"}
    return result
