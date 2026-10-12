"""Offline checks for exports and evidence accounting; makes no model requests."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compare_runs import summarize
from generate_teams import build_components


class ExperimentsTests(unittest.TestCase):
    def test_exports_round_trip_without_credentials_or_tools(self):
        from autogen_agentchat.teams import RoundRobinGroupChat

        async def check():
            components = await build_components("test-fixture", {
                "vision": False, "function_calling": False, "json_output": False,
                "structured_output": False, "family": "unknown",
            })
            self.assertEqual(set(components), {"single-agent", "analyst-reviewer"})
            for name, component in components.items():
                self.assertNotIn('"api_key"', json.dumps(component))
                with patch.dict(os.environ, {"OPENAI_API_KEY": "TEST-ONLY-NO-NETWORK"}):
                    loaded = RoundRobinGroupChat.load_component(component)
                self.assertEqual(len(loaded._participants), 1 if name == "single-agent" else 2)
                self.assertEqual(component["config"]["max_turns"], 1 if name == "single-agent" else 4)
                for participant in loaded._participants:
                    self.assertFalse(participant._tools)
                    await participant._model_client.close()
        asyncio.run(check())

    def test_missing_token_usage_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"messages": [{"source": "user", "content": "task"},
                {"source": "analyst", "content": "answer"}], "stop_reason": "limit"}), encoding="utf-8")
            result = summarize(path)
            self.assertIsNone(result["prompt_tokens"])
            self.assertFalse(result["usage_complete"])

    def test_measured_usage_is_aggregated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"messages": [
                {"source": "analyst", "models_usage": {"prompt_tokens": 9, "completion_tokens": 3}},
                {"source": "reviewer", "content": "caught wrong citation", "models_usage": {"prompt_tokens": 12, "completion_tokens": 4}}]}), encoding="utf-8")
            result = summarize(path)
            self.assertEqual(result["prompt_tokens"], 21)
            self.assertEqual(result["completion_tokens"], 7)
            self.assertEqual(result["reviewer_messages"], ["caught wrong citation"])


if __name__ == "__main__":
    unittest.main()
