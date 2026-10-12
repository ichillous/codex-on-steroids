#!/usr/bin/env python3
"""Check a blueprint folder without opening a browser. Standard library only.

    python3 check_blueprint.py <blueprint-dir> [--json] [--quiet]

Reads blueprint.json and every page, then reports
  FAIL  things that make the blueprint wrong or incomplete (exit code 1)
  WARN  things to look at
  OPEN  decisions left for the owner, written on the pages in [CAPITALS IN BRACKETS]
and writes the full result, including the link graph, to <blueprint-dir>/_check/static.json.

What it catches: pages missing from the manifest and manifest entries without a page, links to
nowhere, buttons that do nothing, pages nothing leads to, screens with no way out, journeys whose
steps are not actually linked, filler text, wording that was retired, fields without a label,
and starter pages that were never replaced.
"""
import json
import re
import sys
from collections import OrderedDict, defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True
from blueprint_safety import blueprint_root, canonical_relative, contained, local_reference, source_files

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
KINDS = ('screen', 'message', 'document', 'spoken', 'offstage', 'reference')
GENERATED = {'map.html'}
OPEN_RE = re.compile(r"\[[A-Z][A-Z0-9 %/&'’.,:+-]{2,}\]")
FILLER = [
    (re.compile(r'lorem ipsum', re.I), 'filler text'),
    (re.compile(r'\b(TODO|TBD|FIXME|XXX)\b'), 'unfinished marker'),
    (re.compile(r'\{\{[^}]*\}\}'), 'unfilled template field'),
    (re.compile(r'\b(placeholder text|button text|heading goes here|your text here|insert .{0,20} here)\b', re.I), 'filler text'),
]
COPY_ATTRS = ('alt', 'placeholder', 'aria-label', 'title', 'value', 'data-flash', 'data-does', 'content')
EXTERNAL = re.compile(r'^([a-z][a-z0-9+.-]*:|//)', re.I)


class Page(HTMLParser):
    """One pass over a page, collecting what the checks need."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []            # open elements: [tag, attrs]
        self.title = ''
        self.h1 = []
        self.ids = []
        self.links = []            # {href, label}
        self.controls = []         # {label, live, effect, why}
        self.fields = []           # {id, type, labelled}
        self.label_for = set()
        self.text = []
        self.attr_copy = []
        self.comments = []
        self.body = {}
        self.stylesheets = []
        self.scripts = []
        self.assets = []
        self.inline_style = 0
        self.images_no_alt = 0
        self._capture = []         # open link/button records gathering their text

    # -- helpers
    def _inside(self, *tags):
        return any(t in tags for t, _ in self.stack)

    def _form(self):
        for t, a in reversed(self.stack):
            if t == 'form':
                return a
        return None

    def handle_starttag(self, tag, attrs):
        a = OrderedDict((k, (v if v is not None else '')) for k, v in attrs)
        self.assets.extend(a[key] for key in ('src', 'poster') if a.get(key))
        if tag not in VOID:
            self.stack.append([tag, a])
        if 'id' in a and a['id']:
            self.ids.append(a['id'])
        if tag == 'body':
            self.body = a
        if tag == 'link' and 'stylesheet' in a.get('rel', ''):
            self.stylesheets.append(a.get('href', ''))
        if tag == 'script' and a.get('src'):
            self.scripts.append(a['src'])
        if tag == 'img' and 'alt' not in a:
            self.images_no_alt += 1
        if tag == 'label' and a.get('for'):
            self.label_for.add(a['for'])
        if not self._inside('script', 'style') or tag in ('script', 'style'):
            for k in COPY_ATTRS:
                if a.get(k) and not (tag == 'meta' and k == 'content' and a.get('name') == 'viewport'):
                    if k == 'value' and tag == 'input' and a.get('type', 'text') not in ('submit', 'button', 'reset'):
                        continue
                    self.attr_copy.append(a[k])

        hidden_ui = 'data-blueprint-ui' in a
        if tag == 'a' and not hidden_ui:
            if 'href' in a and a['href'].strip() not in ('',):
                rec = {'href': a['href'].strip(), 'label': a.get('aria-label', ''), 'does': a.get('data-does', ''), '_t': []}
                self.links.append(rec)
                self._capture.append((len(self.stack), rec))
            else:
                self._control(tag, a)
        elif tag == 'button' or a.get('role') == 'button' or (tag == 'input' and a.get('type') in ('button', 'submit', 'reset')):
            if not hidden_ui:
                self._control(tag, a)
        elif tag in ('input', 'select', 'textarea') and a.get('type') != 'hidden':
            labelled = bool(a.get('aria-label') or a.get('aria-labelledby') or self._inside('label'))
            self.fields.append({'id': a.get('id', ''), 'type': a.get('type', tag), 'labelled': labelled})

    def _control(self, tag, a):
        effect, live, why = [], False, ''
        if 'data-set' in a:
            effect.append('sets ' + a['data-set'].replace(';', ',')); live = True
        if 'data-toggle' in a:
            effect.append('switches ' + a['data-toggle'] + ' on and off'); live = True
        if 'data-flash' in a:
            effect.append('says “' + a['data-flash'] + '”'); live = True
        if a.get('onclick') or 'data-js' in a:
            effect.append('runs the page’s own script'); live = True
        if 'disabled' in a or a.get('aria-disabled') == 'true':
            effect.append('shown unavailable'); live = True
        if 'data-off-when' in a:
            effect.append('unavailable while ' + a['data-off-when'])
        if 'data-noop' in a:
            effect.append('does nothing here: ' + (a['data-noop'] or 'no reason given')); live = True
        btype = a.get('type', 'submit' if tag == 'button' else '')
        form = self._form()
        if not live and form is not None and btype in ('submit', ''):
            if 'data-set' in form:
                effect.append('sends the form: sets ' + form['data-set'].replace(';', ',')); live = True
            elif form.get('onsubmit') or 'data-js' in form:
                effect.append('sends the form to the page’s own script'); live = True
            else:
                why = 'it submits a form that goes nowhere (give the <form> a data-set)'
        if not live and not why:
            why = 'pressing it does nothing (add data-set, data-toggle, data-flash, an href, or data-noop="why")'
        label = a.get('aria-label') or (a.get('value', '') if tag == 'input' else '')
        rec = {'label': label, 'live': live, 'effect': '; '.join(effect), 'why': why, 'does': a.get('data-does', ''), '_t': []}
        self.controls.append(rec)
        if tag not in VOID:
            self._capture.append((len(self.stack), rec))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):       # tolerate unclosed inner tags
            if self.stack[i][0] == tag:
                depth = i + 1
                while self._capture and self._capture[-1][0] >= depth:
                    _, rec = self._capture.pop()
                    words = ' '.join(''.join(rec.pop('_t')).split())
                    if not rec['label']:
                        rec['label'] = words
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self._inside('style'):
            self.inline_style += len(data)
            return
        if self._inside('script'):
            return
        if self._inside('title'):
            self.title += data
            return
        if not self._inside('body'):
            return
        self.text.append(data)
        if self._inside('h1'):
            self.h1.append(data)
        for _, rec in self._capture:
            rec['_t'].append(data)

    def handle_comment(self, data):
        self.comments.append(data)

    def finish(self):
        for _, rec in self._capture:
            words = ' '.join(''.join(rec.pop('_t', [])).split())
            if not rec['label']:
                rec['label'] = words
        self._capture = []
        for rec in self.links + self.controls:
            rec.pop('_t', None)
        for f in self.fields:
            if f['id'] and f['id'] in self.label_for:
                f['labelled'] = True
        self.title = ' '.join(self.title.split())
        self.visible = ' '.join(' '.join(self.text).split())
        self.copy = self.visible + ' \n ' + ' \n '.join(self.attr_copy)


def stem_of(name):
    name = str(name).split('#')[0].split('?')[0]
    if name:
        name = canonical_relative(name)
    return name[:-5] if name.endswith('.html') else name


def analyze(root):
    try:
        root = blueprint_root(root)
        before = source_files(root)
        result = _analyze(root)
        for page in result.get('pages', []):
            if page['exists'] and canonical_relative(page['file']) not in before:
                return {'fatal': 'A manifest page is inside an excluded/generated path: ' + page['file']}
        if source_files(root) != before:
            return {'fatal': 'Blueprint source changed during the static check; rerun it.'}
        result['source_files'] = before
        return result
    except (ValueError, OSError) as exc:
        return {'fatal': str(exc)}


def _analyze(root):
    """Return the full analysis of a blueprint folder as a dict."""
    root = Path(root)
    fails, warns = [], []

    def fail(where, msg):
        fails.append({'where': where, 'what': msg})

    def warn(where, msg):
        warns.append({'where': where, 'what': msg})

    mpath = contained(root, 'blueprint.json')
    if not mpath.exists():
        return {'fatal': 'No blueprint.json in %s. Start one with init_blueprint.py.' % root}
    try:
        man = json.loads(mpath.read_text(encoding='utf-8'))
    except Exception as e:  # noqa: BLE001
        return {'fatal': 'blueprint.json does not parse: %s' % e}

    groups = OrderedDict((g.get('key', '?'), g) for g in man.get('groups', []))
    screens = man.get('screens', [])
    pages = OrderedDict()
    counters = defaultdict(int)
    seen = set()
    for s in screens:
        f = canonical_relative(s.get('file', ''))
        st = stem_of(f)
        if not f.endswith('.html'):
            fail('blueprint.json', 'screen "%s": file names end in .html' % f); continue
        if st in seen:
            fail('blueprint.json', '%s is listed twice' % f); continue
        seen.add(st)
        g = s.get('group', '')
        if g not in groups:
            fail('blueprint.json', '%s: group "%s" is not in groups' % (f, g))
        kind = s.get('kind', 'screen')
        if kind not in KINDS:
            fail('blueprint.json', '%s: kind "%s" is not one of %s' % (f, kind, ', '.join(KINDS)))
        counters[g] += 1
        pages[st] = {'stem': st, 'file': f, 'code': '%s%d' % (g, counters[g]), 'group': g, 'title': s.get('title', st),
                     'kind': kind, 'entry': s.get('entry', ''), 'terminal': s.get('terminal', ''),
                     'widths': s.get('widths'), 'exists': contained(root, f).is_file()}

    on_disk = sorted(p.name for p in root.glob('*.html') if p.name not in GENERATED and not p.name.startswith('_'))
    for name in on_disk:
        if stem_of(name) not in pages:
            fail(name, 'this page is not listed in blueprint.json (add it to screens, or delete it)')
    if not pages:
        fail('blueprint.json', 'no screens listed')

    start = stem_of(man.get('start') or (screens[0].get('file') if screens else ''))
    if start and start not in pages:
        fail('blueprint.json', 'start "%s" is not a listed screen' % man.get('start'))

    if man.get('name', '') in ('', 'Project Starter', 'Untitled blueprint'):
        warn('blueprint.json', 'the blueprint still has the starter name')
    if man.get('summary', '').startswith('One sentence:') or not man.get('summary'):
        warn('blueprint.json', 'summary is not written yet')

    retired = []
    for r in man.get('retired', []):
        text = r.get('text', '') if isinstance(r, dict) else str(r)
        if not text:
            continue
        rx = re.compile(text[3:], re.I) if text.startswith('re:') else re.compile(re.escape(text), re.I)
        ex = set(stem_of(x) for x in (r.get('except', []) if isinstance(r, dict) else []))
        retired.append((text, rx, r.get('why', '') if isinstance(r, dict) else '', ex))

    open_decisions = defaultdict(list)
    for st, p in pages.items():
        if not p['exists']:
            fail(p['file'], 'listed in blueprint.json but the file does not exist')
            p.update(links=[], controls=[], out=[], external=[], variants='', text_len=0)
            continue
        doc = Page()
        try:
            doc.feed(contained(root, p['file']).read_text(encoding='utf-8'))
            doc.close()
        except Exception as e:  # noqa: BLE001
            fail(p['file'], 'could not be read as HTML: %s' % e)
        doc.finish()
        p['ids'] = set(doc.ids)
        p['variants'] = doc.body.get('data-variants', '')
        p['state'] = doc.body.get('data-state', '')
        p['text_len'] = len(doc.visible)
        where = '%s %s' % (p['code'], p['file'])

        if any('starter page' in c.lower() for c in doc.comments):
            fail(where, 'still a starter page: replace it with a real one, or remove it and its manifest entry')
        if not doc.title:
            fail(where, 'no <title>')
        if not doc.h1 and p['kind'] in ('screen', 'reference'):
            warn(where, 'no main heading (h1)')
        dupes = sorted(set(i for i in doc.ids if doc.ids.count(i) > 1))
        if dupes:
            fail(where, 'the same id is used twice: %s' % ', '.join(dupes[:6]))
        if not any('blueprint.css' in h for h in doc.stylesheets):
            warn(where, 'does not link blueprint.css, so it is outside the shared design system')
        if doc.inline_style > 1500:
            warn(where, 'carries %d characters of its own CSS; move patterns into blueprint.css' % doc.inline_style)
        needs_runtime = bool(doc.body.get('data-state') or doc.body.get('data-variants')) or any(
            c['effect'] and ('sets ' in c['effect'] or 'switches' in c['effect'] or 'says' in c['effect']) for c in doc.controls)
        if needs_runtime and not any('blueprint.js' in s for s in doc.scripts):
            fail(where, 'uses data-set / data-when but does not load blueprint.js, so nothing will respond')
        elif not any('blueprint.js' in s for s in doc.scripts):
            warn(where, 'does not load blueprint.js, so its open decisions are not highlighted and it has no link back to the map')
        if doc.images_no_alt:
            warn(where, '%d image(s) without alt text' % doc.images_no_alt)
        unl = [f for f in doc.fields if not f['labelled']]
        if unl:
            fail(where, '%d field(s) without a label: %s' % (len(unl), ', '.join((f['id'] or f['type']) for f in unl[:6])))
        if p['kind'] == 'screen' and len(doc.visible) < 40:
            warn(where, 'almost no words on this page')

        for rx, what in FILLER:
            m = rx.search(doc.copy)
            if m:
                fail(where, '%s: “%s”' % (what, m.group(0)[:60]))
        for text, rx, why, ex in retired:
            if st in ex:
                continue
            m = rx.search(doc.copy)
            if m:
                at = max(0, m.start() - 40)
                fail(where, 'retired wording “%s” is still here%s: …%s…' % (
                    text, (' (' + why + ')') if why else '', doc.copy[at:m.end() + 30].replace('\n', ' ').strip()))
        for m in OPEN_RE.finditer(doc.copy):
            if p['code'] not in open_decisions[m.group(0)]:
                open_decisions[m.group(0)].append(p['code'])

        for reference in doc.stylesheets + doc.scripts + doc.assets:
            local_reference(root, reference)

        links, external = [], []
        for l in doc.links:
            href = l['href']
            label = l['label'] or '(no words)'
            if not l['label']:
                fail(where, 'a link with no words (to %s)' % href)
            if href in ('#', '#!') or href.lower().startswith('javascript:'):
                fail(where, 'link “%s” leads nowhere (%s)' % (label, href)); continue
            if EXTERNAL.match(href):
                external.append({'label': label, 'href': href}); continue
            local_reference(root, href)
            target, _, frag = href.partition('#')
            target = target.split('?')[0]
            if target:
                target = canonical_relative(target)
            links.append({'label': label, 'to': stem_of(target) if target else st, 'file': target or p['file'],
                          'frag': frag, 'does': l.get('does', '')})
        p['links'], p['external'] = links, external
        p['controls'] = doc.controls
        if p['kind'] == 'screen':
            for c in doc.controls:
                if not c['live']:
                    fail(where, 'button “%s”: %s' % (c['label'] or '(no words)', c['why']))
                if not c['label']:
                    fail(where, 'a button with no words')

    # links resolve
    for st, p in pages.items():
        where = '%s %s' % (p['code'], p['file'])
        for l in p.get('links', []):
            if l['file'] in GENERATED:
                l['to'] = None; continue
            if l['to'] not in pages:
                if contained(root, l['file']).is_file() and not l['file'].endswith('.html'):
                    l['to'] = None; continue      # a download or an image
                fail(where, 'link “%s” goes to %s, which does not exist' % (l['label'], l['file'])); l['to'] = None; continue
            if l['frag'] and pages[l['to']].get('exists') and l['frag'] not in pages[l['to']].get('ids', set()):
                fail(where, 'link “%s” points at #%s, which is not on %s' % (l['label'], l['frag'], pages[l['to']]['file']))
        p['out'] = sorted(set(l['to'] for l in p.get('links', []) if l['to'] and l['to'] != st))

    inbound = defaultdict(set)
    for st, p in pages.items():
        for t in p.get('out', []):
            inbound[t].add(st)
    for st, p in pages.items():
        p['in'] = sorted(inbound[st], key=lambda s: list(pages).index(s))

    # everything can be reached
    roots = [s for s in ([start] if start in pages else [])] + [s for s, p in pages.items() if p['entry']]
    reached, queue = set(roots), list(roots)
    while queue:
        for t in pages[queue.pop()].get('out', []):
            if t not in reached:
                reached.add(t); queue.append(t)
    for st, p in pages.items():
        where = '%s %s' % (p['code'], p['file'])
        if st not in reached and p['exists']:
            if p['in']:
                fail(where, 'cannot be reached from the start: only %s link here, and nothing leads to them' % ', '.join(pages[s]['code'] for s in p['in']))
            else:
                fail(where, 'nothing links here. Link to it from the screen that leads to it, or say how people arrive with "entry" in blueprint.json')
        if p['kind'] == 'screen' and p['exists'] and not p.get('out') and not p['terminal']:
            if not any(c['live'] for c in p.get('controls', [])):
                fail(where, 'a dead end: no link and no working button. Give the person a next step, or explain with "terminal" in blueprint.json')
            else:
                warn(where, 'no link leaves this screen')

    # journeys
    journeys = []
    on_journey = set()
    for j in man.get('journeys', []):
        title = j.get('title', 'Untitled journey')
        steps, prev, problems = [], None, []
        for s in j.get('steps', []):
            if isinstance(s, dict):
                steps.append({'offstage': s.get('offstage', '')}); prev = None; continue
            st = stem_of(s)
            if st not in pages:
                fail('journey “%s”' % title, 'step "%s" is not a listed screen' % s); problems.append(s); prev = None; continue
            on_journey.add(st)
            linked = prev is None or prev == st or st in pages[prev].get('out', [])
            if not linked:
                fail('journey “%s”' % title, 'no link from %s %s to %s %s' % (pages[prev]['code'], pages[prev]['title'], pages[st]['code'], pages[st]['title']))
            steps.append({'stem': st, 'code': pages[st]['code'], 'title': pages[st]['title'], 'linked': linked})
            prev = st
        journeys.append({'title': title, 'who': j.get('who', ''), 'steps': steps})
    if not journeys:
        warn('blueprint.json', 'no journeys yet: write at least one end-to-end path per role')
    off = [p['code'] for s, p in pages.items() if p['kind'] == 'screen' and s not in on_journey]
    if journeys and off:
        warn('journeys', '%d screen(s) are on no journey: %s' % (len(off), ', '.join(off[:30]) + (' …' if len(off) > 30 else '')))

    for p in pages.values():
        p.pop('ids', None)
    kinds = defaultdict(int)
    for p in pages.values():
        kinds[p['kind']] += 1
    return {
        'name': man.get('name', ''), 'summary': man.get('summary', ''), 'today': man.get('today', ''), 'start': start,
        'widths': man.get('widths') or [1440, 390],
        'groups': [{'key': k, 'title': g.get('title', ''), 'who': g.get('who', '')} for k, g in groups.items()],
        'pages': list(pages.values()), 'journeys': journeys, 'assumptions': man.get('assumptions', []),
        'open': [{'text': k, 'on': v} for k, v in sorted(open_decisions.items())],
        'fails': fails, 'warns': warns,
        'counts': {'pages': len(pages), 'kinds': dict(kinds),
                   'links': sum(len(p.get('links', [])) for p in pages.values()),
                   'controls': sum(len(p.get('controls', [])) for p in pages.values()),
                   'journeys': len(journeys), 'open': len(open_decisions)},
    }


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        print(__doc__); return 2
    root = Path(args[0])
    res = analyze(root)
    if 'fatal' in res:
        print('FAIL  ' + res['fatal']); return 1
    try:
        out = contained(root, '_check')
        destination = contained(root, '_check/static.json')
        out.mkdir(exist_ok=True)
        contained(root, '_check/static.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    except (ValueError, OSError) as exc:
        print('FAIL  ' + str(exc)); return 1
    if '--json' in argv:
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 1 if res['fails'] else 0
    c = res['counts']
    kinds = ', '.join('%d %s' % (n, k) for k, n in sorted(c['kinds'].items()))
    print('%s: %d pages (%s), %d links, %d buttons, %d journey%s' % (res['name'] or 'Blueprint', c['pages'], kinds, c['links'], c['controls'], c['journeys'], '' if c['journeys'] == 1 else 's'))
    if '--quiet' not in argv:
        for g in res['groups']:
            mine = [p for p in res['pages'] if p['group'] == g['key']]
            print('  %s  %-44s %3d' % (g['key'], g['title'][:44], len(mine)))
    for f in res['fails']:
        print('FAIL  %s: %s' % (f['where'], f['what']))
    for w in res['warns']:
        print('WARN  %s: %s' % (w['where'], w['what']))
    for o in res['open']:
        print('OPEN  %s  on %s' % (o['text'], ', '.join(o['on'])))
    print('%d to fix, %d to look at, %d open decision(s) for the owner.' % (len(res['fails']), len(res['warns']), len(res['open'])))
    if not res['fails']:
        print('Static check clean. This does not prove the pages look right: run browser_audit.cjs, or open them.')
    return 1 if res['fails'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
