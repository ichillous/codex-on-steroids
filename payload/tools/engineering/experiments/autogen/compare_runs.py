"""Summarize AutoGen TaskResult JSON files; quality and acceptance remain human judgments."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def summarize(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    data = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise ValueError(f"{path}: expected TaskResult JSON with a messages array")
    messages = data["messages"]
    if any(not isinstance(item, dict) for item in messages):
        raise ValueError(f"{path}: every message must be an object")
    turns = Counter(str(item.get("source", "unknown")) for item in messages)
    model_messages = [item for item in messages if item.get("source") not in ("user", "system")]
    usage = [item.get("models_usage") for item in model_messages]
    complete_usage = bool(usage) and all(
        isinstance(item, dict) and all(isinstance(item.get(field), int) for field in ("prompt_tokens", "completion_tokens"))
        for item in usage
    )
    return {
        "file": str(path.resolve()),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "message_count": len(messages),
        "turns_by_source": dict(turns),
        "stop_reason": data.get("stop_reason"),
        "usage_complete": complete_usage,
        "prompt_tokens": sum(item["prompt_tokens"] for item in usage) if complete_usage else None,
        "completion_tokens": sum(item["completion_tokens"] for item in usage) if complete_usage else None,
        "reviewer_messages": [item.get("content") for item in messages if item.get("source") == "reviewer"],
        "quality_assessment": "Review correctness, citations, unsupported claims, and reviewer contribution against the same evidence packet.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps({"runs": [summarize(path) for path in args.results]}, indent=2))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
