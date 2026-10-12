"""Focused rendering-safety checks and an isolated session-allocation fixture."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import init_session
from init_session import safe_name
from render_report import inline, render_document, render_markdown, safe_url
from validate_session import HTMLAudit, identifier_references, protected_files_check, setup_prefix_check


def main() -> int:
    checks = []
    text = """# Offline fixture

## Evidence

Plain content with **strong** and `code`.

| Claim | Evidence |
|---|---|
| C01 | [S01](../evidenceandlogic/sources.md#s01) |
| E01 | [Experiment](../evidenceandlogic/experiments/E01/record.json) |

<script>alert('unsafe')</script>

[Bad](javascript:alert) [Good](https://example.org/source)

## Evidence

- First useful point
- Second useful point

```text
<iframe src="https://example.org/"></iframe>
```
"""
    digest = hashlib.sha256(text.encode()).hexdigest()
    result = render_document(text, "fixture.md", digest)
    audit = HTMLAudit()
    audit.feed(result)
    assert audit.scripts == 0 and not audit.runtime_assets
    checks.append("Raw HTML and fenced HTML escaped; no scripts or runtime assets")
    assert "javascript:" not in result and "https://example.org/source" in audit.links
    assert safe_url("//evil.example/resource") is None
    assert safe_url("file:///C:/private.txt") is None
    assert safe_url("data:text/html,test") is None
    assert safe_url("C:\\private.txt") is None
    checks.append("Unsafe schemes/absolute paths rejected; public citation retained")
    assert "<table>" in result and '<th scope="col">' in result
    assert "evidence" in audit.ids and "evidence-2" in audit.ids
    assert "../evidenceandlogic/sources.md#s01" in audit.links
    assert audit.meta["report-source-sha256"] == digest
    assert result == render_document(text, "fixture.md", digest)
    checks.append("Tables, distinct heading IDs, relative evidence links and deterministic hash rendering")
    assert inline('<img src=x onerror="bad">') == '&lt;img src=x onerror=&quot;bad&quot;&gt;'
    assert "&quot;" in inline('[quote](https://example.org/?q="x")')
    checks.append("Text and link attribute quotes escaped")
    assert safe_name('Idea: A/B?') == 'Idea- A-B-'
    for reserved in ("CON", "nul.txt", "COM1", "", "..."):
        try:
            safe_name(reserved)
        except ValueError:
            continue
        raise AssertionError("Accepted unsafe Windows name: " + reserved)
    checks.append("Windows reserved/empty names rejected; unsafe filename characters normalized")
    hostile = HTMLAudit()
    hostile.feed('<style>@import "https://example.org/a.css";</style><script>1</script><img src="https://example.org/a.png"><p onclick="bad">x</p>')
    assert hostile.scripts == 1 and len(hostile.runtime_assets) == 3
    checks.append("Asset audit detects CSS import, external image, inline handler and script")
    known = {"C01", "E01", "P01", "N02", "T03", "DOC-001", "custom_source"}
    references = identifier_references("C01 P01 N02 T03 DOC-001 custom_source N99 DOC-999\n> P999 quoted source\n```text\nT999 raw source\n```", known)
    assert references == {"C01", "P01", "N02", "T03", "DOC-001", "custom_source", "N99", "DOC-999"}
    assert references - known == {"N99", "DOC-999"}
    checks.append("P/N/T, registered numeric families and custom IDs checked; fenced/quoted source excluded")
    tools_root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="session-fixture-", dir=tools_root) as scratch:
        fixture = Path(scratch).resolve()
        assert fixture.is_relative_to(tools_root)
        original = fixture / "fixture.md"
        original.write_bytes(b"# Synthetic input\r\nPreserve these exact bytes.\r\n")
        before = original.read_bytes()
        allocated = []
        with patch.object(init_session, "WORKSPACE", fixture):
            for _ in range(2):
                output = io.StringIO()
                with patch("sys.argv", ["init_session.py", str(original), "--name", "Synthetic fixture"]), contextlib.redirect_stdout(output):
                    assert init_session.main() == 0
                record = json.loads(output.getvalue())
                allocated.append(Path(record["session"]))
                assert (allocated[-1] / "inputs/idea-original.md").read_bytes() == before
                assert record["input_sha256"] == hashlib.sha256(before).hexdigest()
                assert not record["index_changed"]
                assert json.loads((allocated[-1] / "run/session.json").read_text())["graph_exception"] is None
        assert allocated[0] != allocated[1] and all(p.is_dir() for p in allocated)
        assert original.read_bytes() == before
        manifest = fixture / "protected-files.json"
        manifest.write_text(json.dumps({"scope": "One synthetic fixture file; others excluded", "files": [{"path": "fixture.md", "sha256": hashlib.sha256(before).hexdigest()}]}), encoding="utf-8")
        protected = protected_files_check(fixture, manifest)
        assert protected["status"] == "pass" and protected["checked_count"] == 1
        original.write_bytes(before + b"Changed")
        assert protected_files_check(fixture, manifest)["status"] == "fail"
        original.unlink()
        assert protected_files_check(fixture, manifest)["status"] == "fail"
        manifest.unlink()
        assert protected_files_check(fixture, manifest)["status"] == "not_run"
        backups = fixture / "backups"
        backups.mkdir()
        assert setup_prefix_check(fixture, backups)["status"] == "not_run"
        (backups / "AGENTS.md.original").write_bytes(b"Original instructions\r\n")
        (fixture / "AGENTS.md").write_bytes(b"Original instructions\r\nAdded instructions\n")
        prefix = setup_prefix_check(fixture, backups)
        assert prefix["status"] == "pass" and len(prefix["files"]) == 1
        (fixture / "AGENTS.md").write_bytes(b"Changed original instructions\r\n")
        assert setup_prefix_check(fixture, backups)["status"] == "fail"
        assert fixture.is_relative_to(tools_root)  # checked before TemporaryDirectory's recursive cleanup
    checks.append("Actual initializer creates two distinct isolated sessions, preserves bytes/hash and leaves graph exception/index unset")
    checks.append("Baseline and prefix checks detect changed/missing originals; absent optional evidence stays not_run")
    for check in checks:
        print("PASS: " + check)
    print(f"{len(checks)} focused checks passed; filesystem fixture stayed beneath tools/research and was removed; no browser/network/model calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
