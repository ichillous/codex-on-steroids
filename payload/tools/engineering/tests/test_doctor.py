import json

from workspace_engineering.doctor import diagnose


def test_doctor_does_not_disclose_existing_mcp_credentials(tmp_path):
    config = tmp_path / ".codex/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        'model = "gpt-6-astra"\n'
        '[mcp_servers.existing]\n'
        'command = "example"\n'
        '[mcp_servers.existing.env]\n'
        'API_KEY = "synthetic-secret-value"\n', encoding="utf-8"
    )
    result = diagnose(tmp_path)
    details = result["checks"]["project_config"]
    assert details["status"] == "passed"
    assert details["result"]["mcp_servers"] == ["existing"]
    assert "synthetic-secret-value" not in json.dumps(result)
    assert result["checks"]["graph_publication"]["status"] == "failed"
