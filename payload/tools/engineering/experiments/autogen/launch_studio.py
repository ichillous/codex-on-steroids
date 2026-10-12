"""Launch one local Studio process with workspace-owned state and no global CLI env file."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    workspace = Path(__file__).resolve().parents[4]
    state = workspace / ".engineering-state" / "studio"
    state.mkdir(parents=True, exist_ok=True)
    os.environ["AUTOGENSTUDIO_APPDIR"] = str(state)
    os.environ["AUTOGENSTUDIO_HOST"] = "127.0.0.1"
    os.environ["AUTOGENSTUDIO_PORT"] = str(args.port)
    # Prevent a pre-existing shell URI from redirecting local experiment storage.
    os.environ["AUTOGENSTUDIO_DATABASE_URI"] = "sqlite:///" + (state / "studio.sqlite").as_posix()
    os.environ["AUTOGENSTUDIO_API_DOCS"] = "False"
    import uvicorn

    print(f"Studio: http://127.0.0.1:{args.port}; state: {state}; Ctrl+C stops this process", flush=True)
    uvicorn.run("autogenstudio.web.app:app", host="127.0.0.1", port=args.port, workers=1, reload=False)


if __name__ == "__main__":
    main()
