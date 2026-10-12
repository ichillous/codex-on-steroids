"""Prepare dedicated toolkit environments using isolated Python and checked ownership.

This helper runs under -I. It uses only the standard library before installing
reviewed toolkit dependencies; application modules and pip configuration are
never used to decide installation destinations.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


MARKER = ".starter-kit-environment.json"
NETWORK_PIP_SETTINGS = frozenset({
    "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST", "PIP_CERT",
    "PIP_CLIENT_CERT", "PIP_PROXY", "PIP_TIMEOUT", "PIP_RETRIES",
})


class BootstrapError(ValueError):
    pass


def safe_path(path: Path) -> Path:
    """Reject all existing links/reparse points before using absolute paths."""
    path = path.absolute()
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BootstrapError("Environment preparation refuses symlinks and junctions")
    return path


def process_env() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith("PYTHON")
                   and (not key.upper().startswith("PIP_") or key.upper() in NETWORK_PIP_SETTINGS)}
    environment.update(PIP_CONFIG_FILE=os.devnull, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return environment


def verify_environment_paths(environment: Path) -> None:
    # pip may update any package already present, so checking just Scripts and
    # site-packages would miss a junction nested inside an installed package.
    for current, directories, files in os.walk(environment, followlinks=False):
        for name in directories + files:
            safe_path(Path(current) / name)


def run(arguments: list[str], cwd: Path) -> None:
    result = subprocess.run(arguments, cwd=cwd, env=process_env(), shell=False, timeout=1800)
    if result.returncode:
        # Arguments/environment can include credential-bearing package indexes.
        raise BootstrapError(f"Isolated environment command failed (exit {result.returncode})")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_versions(lock: Path) -> dict[str, str]:
    expected = {}
    for line in safe_path(lock).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s;]+)", line.strip())
        if not match:
            raise BootstrapError("Bootstrap requires a reviewed lock containing exact versions")
        expected[normalized(match[1])] = match[2]
    if not expected:
        raise BootstrapError("The dependency lock is empty")
    return expected


def verify_metadata(environment: Path, expected: dict[str, str]) -> None:
    cfg = safe_path(environment / "pyvenv.cfg")
    if not cfg.is_file() or not re.search(r"(?im)^include-system-site-packages\s*=\s*false\s*$", cfg.read_text()):
        raise BootstrapError("A dedicated virtual environment without system site packages is required")
    site = safe_path(environment / "Lib/site-packages")
    if not site.is_dir():
        raise BootstrapError("The dedicated environment has no installed site packages")
    # Inspect metadata as data before executing an existing environment.
    versions = {}
    for distribution in importlib.metadata.distributions(path=[str(site)]):
        name = distribution.metadata.get("Name", "")
        versions[normalized(name)] = distribution.version
    missing = sorted(name for name, version in expected.items() if versions.get(name) != version)
    if missing:
        raise BootstrapError("Environment does not match the locked dependencies: " + ", ".join(missing))


def verify_runtime(python: Path, environment: Path, root: Path, kind: str) -> None:
    code = (
        "import sys; from pathlib import Path; "
        f"assert Path(sys.prefix).resolve() == Path({str(environment)!r}).resolve(); "
        "assert sys.prefix != sys.base_prefix; import pip; "
        "assert Path(pip.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); "
    )
    if kind == "engineering":
        code += ("import workspace_engineering,langgraph.graph,openai_codex,mcp,yaml,pydantic; "
                 f"assert Path(workspace_engineering.__file__).resolve().is_relative_to(Path({str(root / 'src')!r}).resolve())")
    else:
        code += "import autogenstudio,autogen_core,autogen_agentchat,autogen_ext.models.openai"
    run([str(safe_path(python)), "-I", "-B", "-c", code], root)
    run([str(python), "-I", "-B", "-m", "pip", "check"], root)


def prior_install_owns(root: Path, kind: str) -> bool:
    project = root.parents[1] if kind == "engineering" else root.parents[3]
    try:
        manifest = json.loads(safe_path(project / ".engineering-state/starter-kit-install.json").read_bytes())
        paths = [root / "bootstrap.ps1", root / "requirements.lock"]
        if kind == "engineering":
            paths.append(root / "pyproject.toml")
        return all(manifest["files"].get(path.relative_to(project).as_posix())
                   == hashlib.sha256(safe_path(path).read_bytes()).hexdigest() for path in paths)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def prepare(root: Path, kind: str) -> Path:
    root = safe_path(root)
    environment = safe_path(root / (".venv" if kind == "engineering" else ".venv-studio"))
    python = safe_path(environment / "Scripts/python.exe")
    lock = safe_path(root / "requirements.lock")
    expected = locked_versions(lock)
    marker = safe_path(environment / MARKER)
    identity = {"schema_version": 1, "kind": kind, "environment": str(environment)}
    if environment.exists():
        verify_environment_paths(environment)
        if not marker.is_file():
            # Earlier versions lacked markers. Only reuse a demonstrably ready
            # toolkit environment, without installing or adopting anything.
            if prior_install_owns(root, kind):
                try:
                    verify_metadata(environment, expected)
                    verify_runtime(python, environment, root, kind)
                    print("Reused verified legacy toolkit environment without modifying it.")
                    return python
                except (BootstrapError, OSError, subprocess.SubprocessError) as exc:
                    raise BootstrapError("Existing unowned environment is not ready; preserved it. Inspect it and move it aside explicitly before retrying setup.") from exc
            raise BootstrapError("Existing environment has no matching toolkit ownership; preserved it. Inspect it and move it aside explicitly before retrying setup.")
        if json.loads(marker.read_bytes()) != identity:
            raise BootstrapError("Existing environment ownership does not match; preserved it")
    else:
        environment.mkdir()
        # Exclusive creation keeps another environment owner from being adopted.
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(identity, stream)
    if not python.is_file():
        run([sys.executable, "-I", "-B", "-m", "venv", str(environment)], root)
    safe_path(python)
    # Confirm a real venv and genuine pip before any pip install. Application
    # pip.py cannot satisfy this probe or turn failed bootstrap into success.
    probe = ("import sys; from pathlib import Path; "
             f"assert Path(sys.prefix).resolve() == Path({str(environment)!r}).resolve(); "
             "assert sys.prefix != sys.base_prefix; import pip; "
             "assert Path(pip.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())")
    run([str(python), "-I", "-B", "-c", probe], root)
    run([str(python), "-I", "-B", "-m", "pip", "install", "--no-user", "--requirement", str(lock)], root)
    if kind == "engineering":
        run([str(python), "-I", "-B", "-m", "pip", "install", "--no-user", "--no-deps", "--editable", str(root)], root)
    verify_metadata(environment, expected)
    verify_runtime(python, environment, root, kind)
    print(f"{kind.capitalize()} environment ready.")
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("engineering", "studio"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.kind)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BootstrapError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Bootstrap stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
