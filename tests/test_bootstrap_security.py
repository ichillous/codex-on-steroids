"""Bootstrap boundaries; isolated fake packages and disposable no-pip environments.

No test downloads dependencies or invokes a model. Real subprocess checks stop
at genuine pip absence, before an install command can run.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1]
SOURCE = KIT / "payload/tools/engineering"
spec = importlib.util.spec_from_file_location("kit_bootstrap", SOURCE / "bootstrap_runtime.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def fixture_root(tmp_path, kind="engineering"):
    root = tmp_path / "project/tools/engineering"
    root.mkdir(parents=True)
    shutil.copyfile(SOURCE / "bootstrap_runtime.py", root / "bootstrap_runtime.py")
    if kind == "studio":
        root = root / "experiments/autogen"
        root.mkdir(parents=True)
        source = SOURCE / "experiments/autogen"
    else:
        source = SOURCE
    shutil.copyfile(source / "bootstrap.ps1", root / "bootstrap.ps1")
    (root / "requirements.lock").write_text("fixture-package==1.2.3\n")
    (root / "pyproject.toml").write_text("# fixture\n")
    return root


def owned(root, kind="engineering"):
    env = root / (".venv" if kind == "engineering" else ".venv-studio")
    env.mkdir(exist_ok=True)
    (env / bootstrap.MARKER).write_text(json.dumps({
        "schema_version": 1, "kind": kind, "environment": str(env),
    }))
    return env


def test_pip_destinations_and_startup_injection_cannot_reach_child(monkeypatch, tmp_path):
    hostile = {"PIP_TARGET": "elsewhere", "PIP_PREFIX": "elsewhere", "PIP_ROOT": "elsewhere",
               "PIP_USER": "yes", "PIP_CONFIG_FILE": "elsewhere", "PIP_PYTHON": "elsewhere",
               "PIP_REQUIREMENT": "unreviewed.txt", "PIP_CONSTRAINT": "unreviewed.txt", "PIP_NO_DEPS": "1",
               "PIP_REQUIRE_HASHES": "1", "PIP_DRY_RUN": "1", "PYTHONPATH": "elsewhere",
               "PYTHONHOME": "elsewhere", "PYTHONSTARTUP": "elsewhere"}
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("PIP_INDEX_URL", "https://packages.example.invalid/simple")
    monkeypatch.setenv("PIP_NO_INDEX", "1")
    monkeypatch.setenv("PIP_FIND_LINKS", str(tmp_path / "offline wheels"))
    captured = {}

    def run(argv, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(bootstrap.subprocess, "run", run)
    bootstrap.run([sys.executable, "-I", "-B", "-c", "pass"], tmp_path)
    assert captured["shell"] is False
    assert captured["env"]["PIP_CONFIG_FILE"] == os.devnull
    assert captured["env"]["PIP_INDEX_URL"] == "https://packages.example.invalid/simple"
    assert all(key not in captured["env"] for key in hostile if key != "PIP_CONFIG_FILE")
    spec = importlib.util.spec_from_file_location("graphify_bootstrap_security", SOURCE / "graphify_setup.py")
    graphify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(graphify)
    assert bootstrap.NETWORK_PIP_SETTINGS == graphify.NETWORK_PIP_SETTINGS
    assert all(key not in graphify.process_env() for key in hostile if key != "PIP_CONFIG_FILE")
    assert graphify.process_env()["PIP_INDEX_URL"] == captured["env"]["PIP_INDEX_URL"]
    for environment in (captured["env"], graphify.process_env()):
        assert environment["PIP_NO_INDEX"] == "1"
        assert environment["PIP_FIND_LINKS"] == str(tmp_path / "offline wheels")


def test_owned_bootstrap_uses_isolated_commands_and_readiness_checks(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    commands, checks = [], []

    def run(argv, cwd):
        commands.append(argv)
        if "venv" in argv:
            python = Path(argv[-1]) / "Scripts/python.exe"
            python.parent.mkdir()
            python.write_text("inert")

    monkeypatch.setattr(bootstrap, "run", run)
    monkeypatch.setattr(bootstrap, "verify_metadata", lambda *args: checks.append("metadata"))
    monkeypatch.setattr(bootstrap, "verify_runtime", lambda *args: checks.append("runtime"))
    bootstrap.prepare(root, "engineering")
    assert checks == ["metadata", "runtime"]
    assert commands and all(argv[1:3] == ["-I", "-B"] for argv in commands)
    assert all("--no-user" in argv for argv in commands if "install" in argv)
    assert json.loads((root / ".venv" / bootstrap.MARKER).read_text())["kind"] == "engineering"


@pytest.mark.parametrize("kind", ["engineering", "studio"])
def test_unowned_environment_is_preserved_without_executing_it(tmp_path, monkeypatch, kind):
    root = fixture_root(tmp_path, kind)
    env = root / (".venv" if kind == "engineering" else ".venv-studio")
    env.mkdir()
    marker = env / "owner.txt"
    marker.write_text("original")
    monkeypatch.setattr(bootstrap, "run", lambda *args: pytest.fail("Unowned environment executed"))
    with pytest.raises(bootstrap.BootstrapError, match="ownership"):
        bootstrap.prepare(root, kind)
    assert marker.read_text() == "original"
    assert not (env / bootstrap.MARKER).exists()


def test_owned_incomplete_environment_can_retry(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    env = owned(root)
    calls = []

    def fail(argv, cwd):
        calls.append(argv)
        raise bootstrap.BootstrapError("interrupted fixture")

    monkeypatch.setattr(bootstrap, "run", fail)
    for _ in range(2):
        with pytest.raises(bootstrap.BootstrapError, match="interrupted fixture"):
            bootstrap.prepare(root, "engineering")
    assert len(calls) == 2
    assert (env / bootstrap.MARKER).is_file()


def test_complete_verified_legacy_environment_reused_without_pip_or_adoption(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    env = root / ".venv"
    env.mkdir()
    project = root.parents[1]
    manifest = project / ".engineering-state/starter-kit-install.json"
    manifest.parent.mkdir()
    paths = [root / "bootstrap.ps1", root / "requirements.lock", root / "pyproject.toml"]
    manifest.write_text(json.dumps({"files": {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}))
    checks = []
    monkeypatch.setattr(bootstrap, "run", lambda *args: pytest.fail("No legacy install command"))
    monkeypatch.setattr(bootstrap, "verify_metadata", lambda *args: checks.append("metadata"))
    monkeypatch.setattr(bootstrap, "verify_runtime", lambda *args: checks.append("runtime"))
    bootstrap.prepare(root, "engineering")
    assert checks == ["metadata", "runtime"]
    assert not (env / bootstrap.MARKER).exists()


def test_locked_metadata_is_checked_without_importing_packages(tmp_path):
    env = tmp_path / "env"
    site = env / "Lib/site-packages"
    info = site / "fixture_package-1.2.3.dist-info"
    info.mkdir(parents=True)
    (env / "pyvenv.cfg").write_text("include-system-site-packages = false\n")
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: fixture-package\nVersion: 1.2.3\n")
    (site / "fixture_package.py").write_text("raise AssertionError('Never import to inspect metadata')")
    bootstrap.verify_metadata(env, {"fixture-package": "1.2.3"})
    with pytest.raises(bootstrap.BootstrapError, match="locked dependencies"):
        bootstrap.verify_metadata(env, {"fixture-package": "2.0"})


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell bootstrap")
@pytest.mark.parametrize("kind", ["engineering", "studio"])
def test_actual_bootstrap_does_not_execute_local_pip_or_python_startup(tmp_path, kind):
    root = fixture_root(tmp_path, kind)
    env = owned(root, kind)
    subprocess.run([sys.executable, "-I", "-B", "-m", "venv", "--without-pip", str(env)], check=True, capture_output=True)
    sentinel = tmp_path / "must-not-exist.txt"
    code = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('wrong module executed')\n"
    for filename in ("pip.py", "sitecustomize.py", "venv.py"):
        (root / filename).write_text(code)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root)
    environment["PIP_TARGET"] = str(tmp_path / "wrong-target")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(root / "bootstrap.ps1"), "-Python", sys.executable],
                            cwd=root, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "No module named 'pip'" in result.stderr
    assert not sentinel.exists()
    assert not (tmp_path / "wrong-target").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
@pytest.mark.parametrize("relative", [".venv", ".venv/Lib/site-packages/fixture"])
def test_linked_environment_or_package_is_rejected_before_execution(tmp_path, monkeypatch, relative):
    root = fixture_root(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    link = root / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    # cmd is used only for Windows junction creation; no deletion or moving.
    result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(external)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    monkeypatch.setattr(bootstrap, "run", lambda *args: pytest.fail("Linked environment executed"))
    with pytest.raises(bootstrap.BootstrapError, match="junction"):
        bootstrap.prepare(root, "engineering")
    assert list(external.iterdir()) == []
