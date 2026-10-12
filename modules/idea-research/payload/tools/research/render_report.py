"""Render this project's Markdown report subset to escaped, standalone HTML.

Standard library only. Raw HTML is displayed as text, never interpreted. Links
are limited to http(s), mailto and relative targets. No scripts or remote assets.
Supported: headings, paragraphs, fenced code, flat lists, blockquotes, pipe
tables, emphasis, inline code and inline Markdown links. Not full CommonMark.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
from pathlib import Path
from urllib.parse import urlsplit

WORKSPACE = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[([^\]\n]+)\]\((<[^>\n]+>|[^)\n]+)\)")
TOKEN = re.compile(r"(`+)(.+?)\1|\[([^\]\n]+)\]\((<[^>\n]+>|[^)\n]+)\)|\*\*(.+?)\*\*|(?<!\*)\*([^*\n]+)\*(?!\*)")


def safe_url(value: str) -> str | None:
    value = value.strip().removeprefix("<").removesuffix(">")
    if not value or any(ord(c) < 32 for c in value) or value.startswith(("//", "\\", "/")):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return None
    return value


def inline(value: str) -> str:
    parts: list[str] = []
    pos = 0
    for match in TOKEN.finditer(value):
        parts.append(html.escape(value[pos:match.start()]))
        if match.group(1):
            parts.append("<code>" + html.escape(match.group(2)) + "</code>")
        elif match.group(3):
            url = safe_url(match.group(4))
            label = html.escape(match.group(3))
            parts.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>' if url else label)
        elif match.group(5):
            parts.append("<strong>" + inline(match.group(5)) + "</strong>")
        else:
            parts.append("<em>" + html.escape(match.group(6)) + "</em>")
        pos = match.end()
    parts.append(html.escape(value[pos:]))
    return "".join(parts)


def slug(text: str) -> str:
    return re.sub(r"[^\w-]+", "-", re.sub(r"[`*_]", "", text).lower()).strip("-") or "section"


def cells(line: str) -> list[str]:
    # Escaped pipes remain cell content; unescaped pipes delimit columns.
    return [x.strip().replace("\\|", "|") for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def is_table_rule(line: str) -> bool:
    row = cells(line)
    return "|" in line and bool(row) and all(re.fullmatch(r":?-{3,}:?", x) for x in row)


def render_markdown(markdown: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = markdown.splitlines()
    out: list[str] = []
    headings: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        fence = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            delimiter = fence.group(1)
            block = []
            i += 1
            while i < len(lines) and not re.match(r"^\s*" + re.escape(delimiter) + r"\s*$", lines[i]):
                block.append(lines[i])
                i += 1
            out.append("<pre><code>" + html.escape("\n".join(block)) + "</code></pre>")
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            base = slug(title)
            seen[base] = seen.get(base, 0) + 1
            anchor = base if seen[base] == 1 else f"{base}-{seen[base]}"
            headings.append((level, anchor, title))
            out.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            i += 1
            continue
        if i + 1 < len(lines) and "|" in line and is_table_rule(lines[i + 1]):
            headers = cells(line)
            rows = []
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row = cells(lines[i])
                row += [""] * max(0, len(headers) - len(row))
                rows.append("<tr>" + "".join("<td>" + inline(c) + "</td>" for c in row) + "</tr>")
                i += 1
            out.append('<div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable evidence table"><table><thead><tr>' + "".join('<th scope="col">' + inline(c) + "</th>" for c in headers) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
            continue
        item = re.match(r"^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$", line)
        if item:
            tag = "ol" if item.group(2) else "ul"
            rows = []
            while i < len(lines):
                current = re.match(r"^\s*(?:([-+*])|(\d+)[.)])\s+(.+)$", lines[i])
                if not current or bool(current.group(2)) != (tag == "ol"):
                    break
                rows.append("<li>" + inline(current.group(3)) + "</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(rows) + f"</{tag}>")
            continue
        if line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].removeprefix(">").lstrip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(quote)) + "</p></blockquote>")
            continue
        if re.fullmatch(r"\s*(?:-{3,}|\*{3,}|_{3,})\s*", line):
            out.append("<hr>")
            i += 1
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            if re.match(r"^\s*(?:#{1,6}\s|`{3,}|~{3,}|>|[-+*]\s|\d+[.)]\s)", lines[i]):
                break
            if i + 1 < len(lines) and is_table_rule(lines[i + 1]):
                break
            paragraph.append(lines[i])
            i += 1
        out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(out), headings


STYLE = """
:root{color-scheme:light;--ink:#172b37;--muted:#4c606d;--line:#ced8df;--accent:#075e65;--paper:#fff;--wash:#f2f6f7}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--wash);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:#075f91;text-decoration-thickness:.08em;text-underline-offset:.15em;overflow-wrap:anywhere}a:focus-visible,.table-wrap:focus-visible{outline:3px solid #b35900;outline-offset:3px}
.skip{position:absolute;left:1rem;top:-5rem;background:#fff;padding:.5rem}.skip:focus{top:1rem}
.masthead{background:#113743;color:#fff;padding:1.5rem max(1.5rem,calc((100vw - 1340px)/2));border-bottom:5px solid #3db6a3}.masthead p{margin:0}.masthead strong{font-size:1.15rem}.masthead .sub{color:#d6e7ed;font-size:.9rem}
.layout{max-width:1400px;margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:2rem;padding:2rem}
nav{align-self:start;position:sticky;top:1rem;max-height:calc(100vh - 2rem);overflow:auto;font-size:.88rem;padding:.8rem}nav h2{font-size:1rem;margin:.2rem 0 .8rem}nav ul{list-style:none;margin:0;padding:0}nav li{margin:.4rem 0}nav .level-3{padding-left:.8rem}nav a{color:var(--ink)}
main{min-width:0;background:var(--paper);padding:clamp(1.2rem,3vw,3.5rem);box-shadow:0 2px 12px #1737440a;border:1px solid var(--line);border-radius:8px}h1,h2,h3,h4{line-height:1.25;scroll-margin-top:1rem}h1{font-size:clamp(1.8rem,3vw,2.6rem);margin-top:0;letter-spacing:-.03em}h2{font-size:1.55rem;margin-top:2.6rem;border-top:1px solid var(--line);padding-top:1.25rem}h3{font-size:1.17rem;margin-top:1.8rem}p,li{max-width:85ch}li{margin:.4rem 0}strong{font-weight:700}
code{background:#edf2f5;padding:.1em .3em;border-radius:3px;font:.88em/1.5 ui-monospace,Consolas,monospace;overflow-wrap:anywhere}pre{background:#edf2f5;padding:1rem;overflow:auto;border:1px solid var(--line);border-radius:5px;white-space:pre-wrap;word-break:break-word}pre code{padding:0;background:none}
.table-wrap{max-width:100%;overflow-x:auto;margin:1.25rem 0;border:1px solid var(--line);border-radius:5px}table{border-collapse:collapse;min-width:560px;width:100%;font-size:.89rem;line-height:1.5}th,td{text-align:left;vertical-align:top;padding:.7rem .8rem;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:#e4eef1;color:#133b48}tr:last-child td{border-bottom:0}tr:nth-child(even) td{background:#f8fafb}blockquote{border-left:4px solid #258b85;margin:1.3rem 0;padding:.1rem 1rem;background:#f0f7f6}hr{border:0;border-top:1px solid var(--line);margin:2rem 0}footer{max-width:1400px;margin:0 auto;padding:0 2rem 2rem;color:var(--muted);font-size:.85rem}
@media(max-width:850px){.layout{grid-template-columns:1fr;padding:1rem;gap:1rem}nav{position:static;max-height:none;background:#fff;border:1px solid var(--line);border-radius:6px;padding:1rem}nav ul{columns:2}nav li{break-inside:avoid}main{padding:1.3rem}.masthead{padding:1.25rem}body{font-size:16px}}
@media(max-width:480px){nav ul{columns:1}.layout{padding:.65rem}main{padding:1.05rem}h2{font-size:1.35rem}td,th{padding:.55rem}table{font-size:.84rem}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{body{background:#fff;font-size:10pt;line-height:1.4}.masthead{background:#fff;color:#172b37;padding:0;border:0}.masthead .sub{color:#4c606d}.layout{display:block;padding:0}nav,.skip{display:none}main{border:0;box-shadow:none;padding:0}h1{font-size:22pt}h2{font-size:16pt;break-after:avoid}h3{break-after:avoid}table{min-width:0;font-size:8pt}thead{display:table-header-group}tr{break-inside:avoid}pre{white-space:pre-wrap}.table-wrap{overflow:visible;border:0}a{color:#173744}footer{padding:1rem 0}p{orphans:3;widows:3}}
"""


def render_document(markdown: str, source_name: str, digest: str) -> str:
    body, headings = render_markdown(markdown)
    title = next((t for n, _, t in headings if n == 1), "Idea research report")
    toc = "".join(f'<li class="level-{n}"><a href="#{anchor}">{html.escape(t)}</a></li>' for n, anchor, t in headings if n in {2, 3})
    if not toc:
        toc = "".join(f'<li><a href="#{anchor}">{html.escape(t)}</a></li>' for _, anchor, t in headings)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="report-source-sha256" content="{digest}"><meta name="report-source" content="{html.escape(source_name, quote=True)}">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>
<a class="skip" href="#report">Skip to report</a><header class="masthead"><p><strong>Idea research</strong></p><p class="sub">Offline report · evidence and next decisions</p></header>
<div class="layout"><nav aria-label="Contents"><h2>Contents</h2><ul>{toc}</ul></nav><main id="report">{body}</main></div>
<footer>All report content is embedded. Companion evidence links use the surrounding session folders; public citations open online. Source: {html.escape(source_name)}.</footer>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = (args.output or source.with_suffix(".html")).resolve()
    if not source.is_relative_to(WORKSPACE) or not output.is_relative_to(WORKSPACE):
        parser.error("source and output must remain within this workspace")
    if source.suffix.lower() != ".md" or output.suffix.lower() != ".html":
        parser.error("expected a .md source and .html output")
    if source.parent != output.parent:
        parser.error("source and output must share a directory to preserve relative evidence links")
    raw = source.read_bytes()
    result = render_document(raw.decode("utf-8-sig"), source.name, hashlib.sha256(raw).hexdigest())
    output.write_text(result, encoding="utf-8", newline="\n")
    print(f"Rendered {source} -> {output}; {len(raw)} source bytes; no runtime assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
