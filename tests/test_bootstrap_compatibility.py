"""Offline conditional-lock and interpreter boundaries; no dependency installs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "payload/tools/engineering"
spec = importlib.util.spec_from_file_location("compat_bootstrap", SOURCE / "bootstrap_runtime.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


@pytest.mark.parametrize("minor", [11, 12, 13, 14])
def test_studio_lock_selects_dependencies_for_supported_python(minor):
    versions = bootstrap.locked_versions(SOURCE / "experiments/autogen/requirements.lock", (3, minor))
    assert ("audioop-lts" in versions) == (minor >= 13)
    assert versions["numpy"] == "2.4.6"
    assert len(versions) == (123 if minor >= 13 else 122)
    assert len(bootstrap.locked_versions(SOURCE / "requirements.lock", (3, minor))) == 66


@pytest.mark.parametrize(("operator", "active"), [
    ("==", True), ("!=", False), ("<=", True), (">=", True), ("<", False), (">", False),
])
@pytest.mark.parametrize("quote", ["'", '"'])
def test_supported_marker_comparisons(tmp_path, operator, active, quote):
    lock = tmp_path / "requirements.lock"
    lock.write_text(f"always==1.0\nconditional==2.0; python_version {operator} {quote}3.13{quote}\n")
    versions = bootstrap.locked_versions(lock, (3, 13))
    assert ("conditional" in versions) is active


def test_marker_comparison_is_numeric_and_mutually_exclusive_pins_are_supported(tmp_path):
    lock = tmp_path / "requirements.lock"
    lock.write_text("package==1.0; python_version < '3.9'\npackage==2.0; python_version >= '3.9'\n")
    assert bootstrap.locked_versions(lock, (3, 11)) == {"package": "2.0"}


@pytest.mark.parametrize("line", [
    "package>=1.0", "package==1.*", "package @ https://example.invalid/package.whl",
    "package==1.0; os_name == 'nt'", "package==1.0; python_full_version >= '3.13.0'",
    "package==1.0; python_version >= '3.13' and python_version < '4.0'",
    "package==1.0; python_version in '3.13,3.14'", "package==1.0; python_version ~= '3.13'",
    "package==1.0; python_version >= 3.13", "package==1.0; python_version >= '3.13.0'",
    "package==1.0; python_version >= '3.13\"", "package==1.0; python_version >= '3.13' # ignored",
    "-r additional.txt", "--index-url https://example.invalid/simple",
])
def test_unsupported_lock_syntax_fails_closed(tmp_path, line):
    lock = tmp_path / "requirements.lock"
    lock.write_text("always==1.0\n" + line + "\n")
    with pytest.raises(bootstrap.BootstrapError, match="exact versions"):
        bootstrap.locked_versions(lock, (3, 11))


def test_conflicting_active_pins_fail_closed(tmp_path):
    lock = tmp_path / "requirements.lock"
    lock.write_text("some_package==1.0\nsome-package==2.0; python_version >= '3.11'\n")
    with pytest.raises(bootstrap.BootstrapError, match="conflicting"):
        bootstrap.locked_versions(lock, (3, 11))


@pytest.mark.parametrize("change_source", [False, True])
def test_pip_snapshot_and_readiness_share_active_lock_bytes(tmp_path, monkeypatch, capsys, change_source):
    root = tmp_path / "studio"
    root.mkdir()
    source_lock = root / "requirements.lock"
    original = b'fixture==1.0\naudioop-lts==0.2.2; python_version >= "3.13"\n'
    source_lock.write_bytes(original)
    captured = {}

    def run(argv, cwd):
        if "venv" in argv:
            python = Path(argv[-1]) / "Scripts/python.exe"
            python.parent.mkdir()
            python.write_text("inert fixture")
        elif "--requirement" in argv:
            captured["snapshot"] = Path(argv[-1])
            assert captured["snapshot"] != source_lock
            if change_source:
                source_lock.write_text("fixture==2.0\n")
            assert captured["snapshot"].read_bytes() == original
        elif "-c" in argv:
            assert "sys.version_info[:2] == (3, 11)" in argv[-1]

    monkeypatch.setattr(bootstrap, "python_minor", lambda: (3, 11))
    monkeypatch.setattr(bootstrap, "run", run)
    monkeypatch.setattr(bootstrap, "verify_metadata", lambda env, expected: captured.update(expected=expected))
    monkeypatch.setattr(bootstrap, "verify_runtime", lambda *args: None)
    if change_source:
        with pytest.raises(bootstrap.BootstrapError, match="lock changed"):
            bootstrap.prepare(root, "studio")
        assert "environment ready" not in capsys.readouterr().out
    else:
        bootstrap.prepare(root, "studio")
    assert captured["expected"] == {"fixture": "1.0"}
    assert not captured["snapshot"].exists()


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows target virtual environments")
@pytest.mark.parametrize("kind", ["engineering", "studio"])
@pytest.mark.parametrize("legacy", [False, True])
def test_actual_target_minor_mismatch_is_preserved_before_pip(tmp_path, monkeypatch, capfd, kind, legacy):
    root = tmp_path / "project/tools/engineering"
    if kind == "studio":
        root /= "experiments/autogen"
    root.mkdir(parents=True)
    (root / "requirements.lock").write_text("fixture==1.0\n")
    (root / "bootstrap.ps1").write_text("# fixture\n")
    (root / "pyproject.toml").write_text("# fixture\n")
    env = root / (".venv" if kind == "engineering" else ".venv-studio")
    subprocess.run([sys.executable, "-I", "-B", "-m", "venv", "--without-pip", str(env)],
                   check=True, capture_output=True)
    # A stale declared version cannot override the actual interpreter probe.
    different_minor = 11 if sys.version_info.minor != 11 else 14
    cfg = env / "pyvenv.cfg"
    cfg.write_text("\n".join(f"version = 3.{different_minor}.0" if line.startswith("version =") else line
                             for line in cfg.read_text().splitlines()) + "\n")
    if legacy:
        info = env / "Lib/site-packages/fixture-1.0.dist-info"
        info.mkdir(parents=True)
        (info / "METADATA").write_text("Metadata-Version: 2.1\nName: fixture\nVersion: 1.0\n")
        project = root.parents[1] if kind == "engineering" else root.parents[3]
        manifest = project / ".engineering-state/starter-kit-install.json"
        manifest.parent.mkdir()
        paths = [root / "bootstrap.ps1", root / "requirements.lock"]
        if kind == "engineering":
            paths.append(root / "pyproject.toml")
        manifest.write_text(json.dumps({"files": {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                                 for p in paths}}))
    else:
        (env / bootstrap.MARKER).write_text(json.dumps({"schema_version": 1, "kind": kind, "environment": str(env)}))
    before = tree_hashes(root)
    commands = []
    original_run = bootstrap.run

    def run(argv, cwd):
        commands.append(argv)
        assert "install" not in argv
        original_run(argv, cwd)

    monkeypatch.setattr(bootstrap, "python_minor", lambda: (3, different_minor))
    monkeypatch.setattr(bootstrap, "run", run)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.prepare(root, kind)
    assert "Python minor differs" in capfd.readouterr().err
    assert len(commands) == 1
    assert tree_hashes(root) == before
    assert (env / bootstrap.MARKER).exists() is not legacy
