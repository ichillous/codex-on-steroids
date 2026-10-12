#!/usr/bin/env python3
"""Build map.html: the whole blueprint on one page, nothing folded away. Standard library only.

    python3 build_map.py <blueprint-dir>

The map is generated from the pages themselves, so it cannot drift from them. It shows
  - every page by group, as a strip of codes, so the size and shape are visible at a glance
  - every journey from blueprint.json, step by step, with steps that happen elsewhere marked
  - the open decisions found on the pages and the decisions made on the owner's behalf
  - a card for every page: how people arrive, everything that can be pressed, and where each press leads
Run check_blueprint.py first (and browser_audit.cjs if a browser is available): the map uses their
results for problems, button outcomes and thumbnails. Rebuild it after every change.
"""
import html
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.dont_write_bytecode = True      # leave the skill folder as it was installed
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_blueprint import analyze  # noqa: E402

KIND_WORD = {'screen': 'Screen', 'message': 'Message', 'document': 'Document', 'spoken': 'Spoken',
             'offstage': 'Outside this project', 'reference': 'Reference'}
CSS = """
:root{--bg:#f4f3ef;--panel:#fff;--ink:#1b1d1c;--mut:#59635d;--line:#d8d5cc;--acc:#1f5f4a;--soft:#e3efe9;--amber:#8a5a00;--amber-soft:#fbefd2;--bad:#a3301f;--bad-soft:#f9e1dc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:400 14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
a{color:var(--acc)}h1,h2,h3,p,ul,ol{margin:0}ul,ol{padding:0;list-style:none}
.page{padding:28px 32px 80px;display:flex;flex-direction:column;gap:36px}
h1{font:400 40px/1.1 Georgia,serif}h2{font:400 26px/1.2 Georgia,serif}h3{font:600 15px/1.35 system-ui,sans-serif}
.lede{font-size:17px;color:var(--mut);max-width:90ch}.mut{color:var(--mut)}.sm{font-size:13px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.stack{display:flex;flex-direction:column;gap:12px}
.btn{display:inline-block;padding:9px 16px;border-radius:9px;background:var(--acc);color:#fff;font-weight:600;text-decoration:none}
.stat{padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}.stat b{display:block;font:400 26px/1 Georgia,serif}
.code{display:inline-block;min-width:34px;padding:1px 6px;border-radius:6px;background:var(--ink);color:#fff;font:700 12px/1.6 ui-monospace,Menlo,monospace;text-align:center;text-decoration:none}
.chip{display:inline-flex;gap:6px;align-items:center;padding:3px 9px 3px 3px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);text-decoration:none;font-size:13px}
.chip.off{padding:3px 9px;border:1px dashed var(--amber);background:var(--amber-soft);color:var(--amber);font-style:italic}
.chip.broken{border-color:var(--bad);background:var(--bad-soft)}
.arrow{color:var(--mut)}
.strip{display:grid;grid-template-columns:minmax(180px,260px) 1fr;gap:8px 16px;align-items:start;padding:10px 0;border-top:1px solid var(--line)}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px}
.box{padding:16px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
.box.amber{border-color:var(--amber);background:var(--amber-soft)}.box.bad{border-color:var(--bad);background:var(--bad-soft)}
.box li{padding:6px 0;border-top:1px solid rgba(0,0,0,.08)}.box li:first-child{border-top:0}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px;align-items:start}
.card{border:1px solid var(--line);border-radius:12px;background:var(--panel);overflow:hidden}
.card img{display:block;width:100%;height:210px;object-fit:cover;object-position:top;border-bottom:1px solid var(--line);background:#e9e7e0}
.card .in{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.card h3 a{color:var(--ink);text-decoration:none}
.kind{font:700 10px/1.6 system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.press li{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:8px;padding:4px 0;border-top:1px solid #eeece6;font-size:13px}
.press li b{font-weight:600}.press .to{color:var(--mut)}.press .bad{color:var(--bad);font-weight:700}
.amberword{color:var(--amber);font-style:italic}
mark{background:#ffe08a;padding:0 3px;border-radius:4px;font-weight:600}
"""


def e(s):
    return html.escape(str(s), quote=True)


def build(root):
    root = Path(root)
    res = analyze(root)
    if 'fatal' in res:
        print('FAIL  ' + res['fatal']); return 1
    browser = None
    bpath = root / '_check' / 'browser.json'
    if bpath.exists():
        try:
            browser = json.loads(bpath.read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001
            browser = None
    pages = OrderedDict((p['stem'], p) for p in res['pages'])
    bpages = {p['stem']: p for p in (browser or {}).get('pages', [])}

    def ref(stem, words=True):
        p = pages[stem]
        return '<a class="chip" href="#%s"><span class="code">%s</span>%s</a>' % (e(stem), e(p['code']), e(p['title']) if words else '')

    def code(stem):
        return '<a class="code" href="#%s" title="%s">%s</a>' % (e(stem), e(pages[stem]['title']), e(pages[stem]['code']))

    c = res['counts']
    start = pages.get(res['start'])
    head = ['<header class="stack">',
            '<p class="kind">Blueprint map · built from the pages, so it always matches them</p>',
            '<h1>%s</h1>' % e(res['name'] or 'Blueprint'),
            '<p class="lede">%s</p>' % e(res['summary'])]
    if res['today']:
        head.append('<p class="mut">Sample data is set on %s.</p>' % e(res['today']))
    stats = [('Pages', c['pages']), ('Links', c['links']), ('Buttons', c['controls']), ('Journeys', c['journeys']),
             ('Open decisions', c['open']), ('To fix', len(res['fails']) + len((browser or {}).get('fails', [])))]
    head.append('<div class="row">%s%s</div>' % (
        ''.join('<div class="stat"><b>%s</b>%s</div>' % (n, e(k)) for k, n in stats),
        ('<a class="btn" href="%s">Start at %s %s →</a>' % (e(start['file']), e(start['code']), e(start['title']))) if start else ''))
    if browser:
        bc = browser['counts']
        head.append('<p class="mut sm">Opened in %s: %d renders, %d buttons pressed (%d went to another page, %d changed the page, %d did nothing%s).</p>' % (
            e(browser.get('browser', 'a browser')), bc['renders'], bc['presses'], bc['navigates'], bc['changes'], bc['nothing'],
            (', %d never became visible' % bc['unreached']) if bc.get('unreached') else ''))
    else:
        head.append('<p class="mut sm">Not yet opened in a browser: what buttons do is read from the page source, not observed.</p>')
    head.append('</header>')

    # every page at a glance
    over = ['<section class="stack"><h2>Every page</h2>']
    for g in res['groups']:
        mine = [p for p in res['pages'] if p['group'] == g['key']]
        over.append('<div class="strip"><div><h3>%s · %s</h3><p class="mut sm">%s · %d page%s</p></div><div class="row">%s</div></div>' % (
            e(g['key']), e(g['title']), e(g['who']), len(mine), '' if len(mine) == 1 else 's', ''.join(ref(p['stem']) for p in mine)))
    over.append('</section>')

    # journeys
    jr = ['<section class="stack"><h2>Journeys, end to end</h2>',
          '<p class="mut">Each chip is a page; follow them in order. <span class="amberword">Amber steps happen somewhere else</span>: a message arriving, another person acting, a system this project does not control.</p>']
    for j in res['journeys']:
        bits = []
        for s in j['steps']:
            if 'offstage' in s:
                bits.append('<span class="chip off">%s</span>' % e(s['offstage']))
            else:
                bits.append('<a class="chip%s" href="#%s"><span class="code">%s</span>%s</a>' % ('' if s['linked'] else ' broken', e(s['stem']), e(s['code']), e(s['title'])))
        jr.append('<div class="box stack"><h3>%s%s</h3><div class="row">%s</div></div>' % (
            e(j['title']), (' <span class="mut">· %s</span>' % e(j['who'])) if j['who'] else '', '<span class="arrow">→</span>'.join(bits)))
    if not res['journeys']:
        jr.append('<div class="box bad">No journeys are written yet. Add them to blueprint.json.</div>')
    jr.append('</section>')

    # decisions
    dec = ['<section class="stack"><h2>Decisions</h2><div class="two">']
    dec.append('<div class="box amber stack"><h3>Open: only the owner can settle these</h3><ul>%s</ul></div>' % (
        ''.join('<li><mark>%s</mark> on %s</li>' % (e(o['text']), ' '.join(code_by(res, pages, x) for x in o['on'])) for o in res['open'])
        or '<li>None written on the pages.</li>'))
    dec.append('<div class="box stack"><h3>Made on the owner’s behalf: confirm or change</h3><ul>%s</ul></div>' % (
        ''.join('<li><b>%s</b><br><span class="mut">%s</span></li>' % (e(a.get('decision', '')), e(a.get('because', ''))) for a in res['assumptions'])
        or '<li>None recorded in blueprint.json.</li>'))
    dec.append('</div></section>')

    # problems
    prob = []
    allfails = [('', f) for f in res['fails']] + [('In the browser: ', f) for f in (browser or {}).get('fails', [])]
    if allfails:
        prob.append('<section class="stack"><h2>To fix</h2><div class="box bad"><ul>%s</ul></div></section>' % ''.join(
            '<li><b>%s%s</b>: %s</li>' % (e(pre), e(f['where']), e(f['what'])) for pre, f in allfails))

    # cards
    body = []
    for g in res['groups']:
        mine = [p for p in res['pages'] if p['group'] == g['key']]
        if not mine:
            continue
        screens = [p for p in mine if p['kind'] == 'screen']
        chrome = set()
        if len(screens) >= 3:
            tally = Counter()
            for p in screens:
                for key in set((l['label'], l['to']) for l in p.get('links', []) if l['to']):
                    tally[key] += 1
            chrome = set(k for k, n in tally.items() if n >= max(3, round(len(screens) * 0.7)))
        body.append('<section class="stack"><h2>%s · %s <span class="mut">· %s</span></h2>' % (e(g['key']), e(g['title']), e(g['who'])))
        if chrome:
            body.append('<p class="mut">On every screen of this group, so not repeated on the cards: %s</p>' % ' '.join(
                '<span class="chip" style="padding-left:9px">%s → %s</span>' % (e(lbl), code(to)) for lbl, to in sorted(chrome, key=lambda k: list(pages).index(k[1]))))
        body.append('<div class="cards">')
        for p in mine:
            bp = bpages.get(p['stem'], {})
            shot = next((r['shot'] for r in bp.get('renders', []) if r.get('shot') and not r.get('variant')), None)
            if not shot:          # an earlier run may have left a screenshot even if the latest one took none
                w = (p.get('widths') or (res['widths'] if p['kind'] in ('screen', 'message') else res['widths'][:1]))[0]
                guess = 'shots/%s@%s.jpg' % (p['stem'], w)
                shot = guess if (root / '_check' / guess).exists() else None
            card = ['<article class="card" id="%s">' % e(p['stem'])]
            if shot and (root / '_check' / shot).exists():
                card.append('<a href="%s"><img loading="lazy" src="_check/%s" alt="Screenshot of %s"></a>' % (e(p['file']), e(shot), e(p['title'])))
            card.append('<div class="in"><p class="kind">%s</p><h3><span class="code">%s</span> <a href="%s">%s</a></h3>' % (
                e(KIND_WORD.get(p['kind'], p['kind'])), e(p['code']), e(p['file']), e(p['title'])))
            if p.get('variants'):
                vs = []
                for part in p['variants'].split(';'):
                    k, _, opts = part.partition('=')
                    for o in [x.strip() for x in opts.split('|') if x.strip()]:
                        vs.append('<a class="chip" style="padding-left:9px" href="%s?%s=%s">%s: %s</a>' % (e(p['file']), e(k.strip()), e(o), e(k.strip()), e(o)))
                card.append('<div class="row">%s</div>' % ''.join(vs))
            arrive = ' '.join(code(s) for s in p.get('in', []))
            if p['entry']:
                arrive = (arrive + ' ' if arrive else '') + '<span class="amberword">%s</span>' % e(p['entry'])
            card.append('<p class="sm"><span class="mut">Arrive from</span> %s</p>' % (arrive or '<span class="press"><span class="bad">nowhere</span></span>'))
            rows, seen = [], set()
            for l in p.get('links', []):
                if (l['label'], l['to']) in chrome:
                    continue
                key = ('l', l['label'], l['to'], l['file'])
                if key in seen:
                    continue
                seen.add(key)
                if l['to']:
                    rows.append('<li><b>%s</b><span class="to">→ %s %s</span></li>' % (e(l['label']), code(l['to']), e(l.get('does') or pages[l['to']]['title'])))
                else:
                    rows.append('<li><b>%s</b><span class="to">→ %s</span></li>' % (e(l['label']), e(l['file'])))
            for x in p.get('external', []):
                rows.append('<li><b>%s</b><span class="to amberword">leaves to %s</span></li>' % (e(x['label']), e(x['href'][:60])))
            seen_c = set()
            for ctl in p.get('controls', []):
                if ctl['label'] in seen_c:
                    continue
                seen_c.add(ctl['label'])
                seenout = sorted([b for b in bp.get('controls', []) if b['label'] == ctl['label'][:70]], key=lambda b: (b['outcome'] in ('already selected', 'unavailable'), len(b.get('after', []))))
                what = ctl.get('does') or ctl['effect'] or ''
                if not ctl['live'] and p['kind'] == 'screen':
                    what = '<span class="bad">does nothing</span>'
                else:
                    what = e(what)
                if seenout:
                    o = seenout[0]
                    if o['outcome'] == 'navigates':
                        tgt = o['to'][:-5] if o['to'] and o['to'].endswith('.html') else o['to']
                        what += ' · goes to %s' % (code(tgt) if tgt in pages else e(o['to']))
                    elif o['outcome'] == 'nothing':
                        what += ' · <span class="bad">pressed: nothing happened</span>'
                    elif o['outcome'] == 'browser dialog':
                        what += ' · opens a browser dialog box'
                    elif o['outcome'] == 'unavailable':
                        what += ' · pressed: stays unavailable'
                    elif o.get('shows'):
                        what = 'shows “%s”' % e(o['shows'])
                    else:
                        what += ' · pressed: page changed'
                    if o.get('after'):
                        what += ' <span class="mut">(shown after “%s”)</span>' % e('”, “'.join(o['after']))
                rows.append('<li><b>%s</b><span class="to">%s</span></li>' % (e(ctl['label'] or '(no words)'), what))
            if rows:
                card.append('<ul class="press">%s</ul>' % ''.join(rows))
            else:
                card.append('<p class="sm mut">Nothing to press%s.</p>' % (': ' + e(p['terminal']) if p['terminal'] else ''))
            card.append('</div></article>')
            body.append(''.join(card))
        body.append('</div></section>')

    out = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
           '<title>Map · %s</title>\n<style>%s</style>\n</head>\n<body>\n<div class="page">\n%s\n</div>\n</body>\n</html>\n') % (
        e(res['name'] or 'Blueprint'), CSS, '\n'.join(head + over + jr + dec + prob + body))
    (root / 'map.html').write_text(out, encoding='utf-8')
    print('map.html written: %d pages, %d journey(s), %d open decision(s)%s' % (
        c['pages'], c['journeys'], c['open'], '' if browser else ' (no browser results yet, so no thumbnails or observed button outcomes)'))
    return 0


def code_by(res, pages, code_text):
    for p in res['pages']:
        if p['code'] == code_text:
            return '<a class="code" href="#%s" title="%s">%s</a>' % (e(p['stem']), e(p['title']), e(p['code']))
    return e(code_text)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(build(sys.argv[1]))
