"""Sensitive evidence, isolated startup, and shell-free launcher regressions."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


onboarding = load("onboarding_security", KIT / "scripts/onboarding.py")
graphify = load("graphify_security", KIT / "payload/tools/engineering/graphify_setup.py")


def put(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def test_all_evidence_classes_are_screened_before_parsing_persistence_or_prompt(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    fixtures = {
        "requirements.txt": "--index-url https://fixture-user:private-index-marker@packages.example.invalid/simple\npytest\n",
        "package.json": json.dumps({"scripts": {"test": 'API_KEY="package-script-marker" python -m pytest'}}),
        "pyproject.toml": '[project]\nname="demo"\n[tool.demo]\n"api_key" = "toml-marker"\n',
        "AGENTS.md": 'Example configuration: {"client_secret": "instruction-marker"}',
        "AGENTS.override.md": 'Example configuration: {"api_key": "override-marker"}',
        "README.md": "Authorization: Bearer readme-marker-1234",
        "calc.py": 'options = {"api_key": "quoted-key-marker"}\n',
        "tests/test_calc.py": 'options = {"password": "test-marker"}\n',
        "graphify-out/LATEST.md": '[Current graph JSON](saved/graph.json)\nhttps://user:pointer-marker@example.invalid',
    }
    before = {name: put(project, name, contents).read_bytes() for name, contents in fixtures.items()}
    put(project, "safe.py", "def add(a, b):\n    return a + b\n")
    inventory = onboarding.discover(project, KIT)
    assert inventory["evidence_files"] == ["safe.py"]
    assert inventory["validation_candidates"] == []
    assert inventory["repositories"][0]["apps"] == []
    assert all(any(name in warning for warning in inventory["warnings"]) for name in fixtures)
    assert all((project / name).read_bytes() == data for name, data in before.items())
    out = tmp_path / "output"
    monkeypatch.setattr(onboarding, "resolve_codex", lambda *args: (_ for _ in ()).throw(FileNotFoundError("offline fixture")))
    with pytest.raises(RuntimeError):
        onboarding.tailor(project, inventory, out)
    saved = (out / "inventory.json").read_text() + (out / "setup-prompt.md").read_text()
    for marker in ("private-index-marker", "package-script-marker", "toml-marker", "instruction-marker",
                   "readme-marker-1234", "quoted-key-marker", "test-marker", "pointer-marker", "override-marker"):
        assert marker not in saved


def test_safe_override_instructions_are_available_as_screened_evidence(tmp_path):
    put(tmp_path, "AGENTS.override.md", "Inspect build definitions before running checks.")
    inventory = onboarding.discover(tmp_path, KIT)
    assert inventory["evidence_files"] == ["AGENTS.override.md"]
    assert inventory["repositories"][0]["instructions"] == ["AGENTS.override.md"]
    assert "Inspect build definitions" in onboarding.prepare_prompt(tmp_path, inventory)


def test_model_argv_disables_unscreened_native_instruction_loading(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    put(project, "AGENTS.md", 'API_KEY="base-instruction-private-marker"')
    put(project, "AGENTS.override.md", 'API_KEY="override-private-marker"')
    inventory = onboarding.discover(project, KIT)
    plan = onboarding.static_plan(inventory)
    plan["mode"] = "model"
    output = tmp_path / "output"
    captured = {}

    class Process:
        returncode = 0

        def __init__(self, argv, **kwargs):
            captured.update(argv=argv, kwargs=kwargs)
            overrides = [argv[index + 1] for index, value in enumerate(argv) if value == "-c"]
            # Codex's automatic document loader runs before the submitted
            # prompt. The subprocess must explicitly disable that loading.
            assert overrides.count("project_doc_max_bytes=0") == 1

        def communicate(self, input, timeout):
            captured["prompt"] = input.decode()
            (output / "setup-result.json").write_text(json.dumps(plan))

    monkeypatch.setattr(onboarding, "resolve_codex", lambda *args: ["fixture-native-codex.exe"])
    monkeypatch.setattr(onboarding.subprocess, "Popen", Process)
    assert onboarding.tailor(project, inventory, output) == plan
    saved = (output / "inventory.json").read_text() + (output / "setup-prompt.md").read_text()
    for marker in ("base-instruction-private-marker", "override-private-marker"):
        assert marker not in saved + captured["prompt"]
    assert captured["argv"][captured["argv"].index("--sandbox") + 1] == "read-only"
    assert "--model" not in captured["argv"]
    assert "--ask-for-approval" not in captured["argv"]


def test_credential_after_excerpt_limit_still_excludes_whole_file(tmp_path):
    put(tmp_path, "README.md", "Ordinary context.\n" * 600 + '\n{"api_key":"later-marker"}')
    inventory = onboarding.discover(tmp_path, KIT)
    assert "README.md" not in inventory["evidence_files"]
    assert "later-marker" not in onboarding.prepare_prompt(tmp_path, inventory)


def test_prompt_rejects_unscreened_excerpts(tmp_path):
    inventory = onboarding.discover(tmp_path, KIT)
    inventory["evidence"].append({"path": "fake.py", "excerpt": 'API_KEY="fixture-marker"'})
    with pytest.raises(ValueError, match="sensitive content"):
        onboarding.prepare_prompt(tmp_path, inventory)


@pytest.mark.parametrize("text", [
    '{"api_key":"quoted-marker"}', "{'client_secret': 'python-marker'}",
    'OPENAI_API_KEY=unquoted-marker', 'Authorization: Bearer marker12345',
    'url="https://user:credential@example.invalid/simple"',
    json.dumps({"scripts": {"test": 'API_KEY="escaped-marker" run-tests'}}),
])
def test_graphify_and_onboarding_detectors_have_same_sensitive_boundaries(tmp_path, text):
    assert onboarding.LITERAL_CREDENTIAL.pattern == graphify.LITERAL_CREDENTIAL.pattern
    assert onboarding.LITERAL_CREDENTIAL.search(text)
    put(tmp_path, "service.py", text)
    put(tmp_path, "safe.py", "def worker():\n    return 1\n")
    selection = graphify.collect_sources(tmp_path)
    assert set(selection["files"]) == {"safe.py"}
    assert any(entry["path"] == "service.py" for entry in selection["skipped"])


def test_resolver_unwraps_literal_native_forwarder_without_execution(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    native = put(tmp_path, "native cli's directory/codex-native.exe", "inert resolver fixture")
    wrapper = native.with_name("codex.cmd")
    for ending in ("", "\nexit /b %errorlevel%\n"):
        wrapper.write_text(f'@echo off\n"{native}" %*' + ending)
        assert onboarding.resolve_codex(str(wrapper), project) == [str(native)]


@pytest.mark.parametrize("shape", [
    '@echo off\n"{native}" %* & echo unexpected', '@echo off\ncall "{native}" %*',
    '@echo off\n"%USERPROFILE%/codex.exe" %*', '@echo off\n"codex.exe" %*',
    '@echo off\n"{native}" --extra %*', '@echo off\n"{project_native}" %*',
])
def test_resolver_rejects_nonliteral_or_project_native_forwarders(tmp_path, shape):
    native = put(tmp_path, "external/codex.exe", "inert")
    project_native = put(tmp_path, "project/bin/codex.exe", "inert")
    wrapper = put(tmp_path, "external/codex.cmd", shape.format(native=native, project_native=project_native))
    with pytest.raises(ValueError):
        onboarding.resolve_codex(str(wrapper), tmp_path / "project")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell setup")
def test_actual_setup_ignores_repository_python_modules_and_startup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    marker = tmp_path / "must-not-execute.txt"
    for name in ("json.py", "onboarding.py", "sitecustomize.py"):
        put(project, name, f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n")
    put(project, "package.json", '{"name":"fixture"}')
    result = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(KIT / "Setup.ps1"),
                             "-ProjectRoot", str(project), "-Python", sys.executable, "-Static", "-PlanOnly"],
                            cwd=project, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()
