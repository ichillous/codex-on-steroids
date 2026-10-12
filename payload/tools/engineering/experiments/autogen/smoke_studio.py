"""Start local Studio, check health/version/UI, then stop the owned process; no model calls."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main() -> None:
    script = Path(__file__).resolve()
    state = script.parents[4] / ".engineering-state" / "studio"
    state.mkdir(parents=True, exist_ok=True)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    result = {"model_calls": 0, "host": "127.0.0.1", "port": port, "checks": {}, "process_stopped": False}
    log = state / "smoke.log"
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, str(script.with_name("launch_studio.py")), "--port", str(port)],
            stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 45
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Studio exited with {process.returncode}; inspect {log}")
                try:
                    with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                        health = json.load(response)
                    if health.get("status") is not True:
                        raise RuntimeError("Studio health did not report true")
                    result["checks"]["health"] = True
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"Studio startup exceeded 45 seconds; inspect {log}")
                    time.sleep(0.25)
            with opener.open(f"http://127.0.0.1:{port}/api/version", timeout=5) as response:
                version = json.load(response)
            result["checks"]["version"] = version["data"]["version"]
            with opener.open(f"http://127.0.0.1:{port}/", timeout=5) as response:
                html = response.read().decode("utf-8")
                if response.status != 200 or "<html" not in html.lower():
                    raise RuntimeError("Studio did not serve its HTML UI")
            result["checks"]["ui_http_200"] = True
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            result["process_stopped"] = process.poll() is not None
            (state / "smoke-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
