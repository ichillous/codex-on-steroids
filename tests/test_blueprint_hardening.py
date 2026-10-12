"""Disposable boundary regressions; fake Playwright checks protocol, not rendering."""
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KIT = Path(__file__).resolve().parents[1]
SCRIPTS = KIT / 'modules/blueprint-first/payload/.agents/skills/blueprint-first/scripts'
NODE = shutil.which('node')

# This implements only the calls exercised by the audit. It never opens a real
# browser, executes page JavaScript, installs packages or contacts a provider.
FAKE_PLAYWRIGHT = r"""
const fs = require('fs');
const http = require('http');
module.exports = { chromium: { launch: async () => ({
  version: () => 'controlled-protocol-fixture', close: async () => {},
  newContext: async () => {
    let events = {}, active = '', changed = false, clicked = false, waited = 0;
    const emit = (event, value) => { if (events[event]) events[event](value); };
    const failure = () => !process.env.FAKE_PAGE || active.endsWith('/' + process.env.FAKE_PAGE);
    const ctl = {path:'body > button:nth-of-type(1)', label:'Save', off:false, hardOff:true, pressed:false, noop:null, submit:false};
    return {
      close: async () => { if (clicked && failure() && process.env.FAKE_ERROR === 'close') emit('pageerror', Error('synthetic final error')); },
      newPage: async () => ({
        on: (name, cb) => {events[name]=cb;}, off: (name) => {delete events[name];},
        goto: async (url) => {
          active = url; changed = false;
          if (process.env.FAKE_SERVER_PATH) {
            await new Promise((resolve, reject) => {
              const u = new URL(url);
              http.get({hostname:u.hostname, port:u.port, path:process.env.FAKE_SERVER_PATH}, (r) => {
                let text = ''; r.on('data', (v) => {text += v;});
                r.on('end', () => {fs.writeFileSync(process.env.FAKE_SERVER_RESULT, JSON.stringify({status:r.statusCode, text})); resolve();});
              }).on('error', reject);
            });
          }
        },
        addStyleTag: async () => {}, waitForLoadState: async () => {},
        waitForTimeout: async () => {
          if (clicked && failure() && process.env.FAKE_ERROR === 'delayed' && ++waited === 2) emit('pageerror', Error('synthetic delayed error'));
        },
        screenshot: async (options) => { fs.writeFileSync(options.path, 'synthetic screenshot bytes'); },
        evaluate: async (fn) => {
          if (fn.name === 'measure') return {over:false, words:100, cut:[], badImages:[], links:[], height:100};
          if (fn.name === 'controls') return [ctl];
          if (fn.name === 'fill') return 0;
          if (fn.name === 'signature') return JSON.stringify({url:new URL(active).pathname, text:changed?'Saved sample':'Before sample', hidden:0, marks:'', checks:'', nodes:4});
          throw Error('Unexpected evaluation ' + fn.name);
        },
        locator: () => ({first: () => ({click: async () => {
          changed = true; clicked = true;
          if (process.env.FAKE_MUTATE) fs.appendFileSync(process.env.FAKE_MUTATE, '\n// concurrent synthetic edit');
          if (failure()) {
            if (process.env.FAKE_ERROR === 'click') emit('pageerror', Error('synthetic post-click error'));
            if (process.env.FAKE_ERROR === 'console') emit('console', {type:()=> 'error', text:()=> 'synthetic console error'});
            if (process.env.FAKE_ERROR === 'response') emit('response', {status:()=>500, url:()=>active + '?failed'});
          }
        }})})
      })
    };
  }
})}};
"""


def python(script, *args):
    return subprocess.run([sys.executable, '-B', str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8', timeout=30)


@pytest.fixture
def blueprint(tmp_path):
    root = tmp_path / 'blueprint'
    root.mkdir()
    manifest = {'name': 'Synthetic test', 'summary': 'Synthetic boundary fixture', 'widths': [800],
                'groups': [{'key': 'A', 'title': 'Sample', 'who': 'Reader'}],
                'screens': [{'file': x + '.html', 'group': 'A', 'title': x, 'entry': 'Direct', 'terminal': 'Done'} for x in ['home', 'second']],
                'start': 'home.html'}
    (root / 'blueprint.json').write_text(json.dumps(manifest), encoding='utf-8')
    for page in ['home', 'second']:
        (root / (page + '.html')).write_text('<!doctype html><html><head><title>Sample</title><link rel="stylesheet" href="blueprint.css"></head>'
                                           '<body><h1>Sample experience</h1><p>Enough readable sample words to inspect.</p>'
                                           '<button data-js>Save</button><script src="blueprint.js"></script></body></html>', encoding='utf-8')
    (root / 'blueprint.js').write_text('// sample script', encoding='utf-8')
    (root / 'blueprint.css').write_text('body { color: black; }', encoding='utf-8')
    module = tmp_path / 'node_modules/playwright'
    module.mkdir(parents=True)
    (module / 'index.js').write_text(FAKE_PLAYWRIGHT, encoding='utf-8')
    return root


def browser(root, *args, **environment):
    if NODE is None:
        pytest.skip('Node is unavailable; browser protocol regressions were not run')
    env = dict(os.environ)
    env.update(environment)
    return subprocess.run([NODE, str(SCRIPTS / 'browser_audit.cjs'), str(root), *args], cwd=root.parent,
                          capture_output=True, text=True, encoding='utf-8', env=env, timeout=30)


def report(root):
    return json.loads((root / '_check/browser.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('event', ['click', 'delayed', 'close', 'console', 'response'])
def test_errors_after_actions_and_final_drain_fail(blueprint, event):
    result = browser(blueprint, '--no-shots', FAKE_ERROR=event)
    assert result.returncode == 1, result.stdout + result.stderr
    assert report(blueprint)['fails']
    assert 'Aggregate:' in result.stdout


def test_partial_run_retains_current_failure_and_aggregate_exit(blueprint):
    first = browser(blueprint, '--no-shots', FAKE_ERROR='click', FAKE_PAGE='home.html')
    assert first.returncode == 1
    partial = browser(blueprint, '--no-shots', '--only', 'second')
    assert partial.returncode == 1, partial.stdout + partial.stderr
    assert 'Current run: 0 failures. Aggregate: 1 to fix' in partial.stdout
    assert report(blueprint)['complete']
    assert any('home.html' in f['where'] for f in report(blueprint)['fails'])
    fixed = browser(blueprint, '--no-shots', '--only', 'home')
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr


@pytest.mark.parametrize('changed', ['home.html', 'blueprint.js', 'blueprint.css', 'blueprint.json', 'asset.svg'])
def test_source_changes_invalidate_all_retained_evidence(blueprint, changed):
    assert browser(blueprint, '--no-shots').returncode == 0
    file = blueprint / changed
    file.write_text(file.read_text(encoding='utf-8') + '\n' if file.exists() else '<svg/>', encoding='utf-8')
    partial = browser(blueprint, '--no-shots', '--only', 'second')
    assert partial.returncode == 1, partial.stdout + partial.stderr
    current = report(blueprint)
    assert current['missing'] == ['home']
    assert [p['stem'] for p in current['pages']] == ['second']
    assert not current['complete']


def test_audit_options_invalidate_retained_evidence(blueprint):
    assert browser(blueprint, '--no-shots').returncode == 0
    result = browser(blueprint, '--no-shots', '--no-clicks', '--only', 'second')
    assert result.returncode == 1
    assert report(blueprint)['missing'] == ['home']


def test_source_change_during_audit_cannot_create_reusable_evidence(blueprint):
    result = browser(blueprint, '--no-shots', FAKE_MUTATE=str(blueprint / 'blueprint.js'))
    assert result.returncode == 1
    assert report(blueprint)['evidence'] is None
    assert not report(blueprint)['complete']
    assert python('build_map.py', blueprint).returncode == 0
    assert 'unverified' in (blueprint / 'map.html').read_text(encoding='utf-8')


def test_partial_run_without_prior_evidence_reports_missing_pages(blueprint):
    result = browser(blueprint, '--no-shots', '--only', 'second')
    assert result.returncode == 1
    assert report(blueprint)['missing'] == ['home']


def test_unknown_partial_page_is_rejected_before_audit(blueprint):
    result = browser(blueprint, '--only', 'typo')
    assert result.returncode == 1
    assert not (blueprint / '_check').exists()


def test_map_reuses_only_current_observations_and_bound_screenshots(blueprint):
    assert browser(blueprint).returncode == 0
    assert python('build_map.py', blueprint).returncode == 0
    original = (blueprint / 'map.html').read_text(encoding='utf-8')
    assert 'shows “Saved sample”' in original
    assert 'src="_check/shots/' in original
    shot = blueprint / '_check' / report(blueprint)['pages'][0]['renders'][0]['shot']
    shot.write_bytes(b'replaced screenshot')
    assert python('build_map.py', blueprint).returncode == 0
    assert '_check/' + report(blueprint)['pages'][0]['renders'][0]['shot'] not in (blueprint / 'map.html').read_text(encoding='utf-8')
    (blueprint / 'blueprint.css').write_text('body { color: red; }', encoding='utf-8')
    assert python('build_map.py', blueprint).returncode == 0
    stale = (blueprint / 'map.html').read_text(encoding='utf-8')
    assert 'stale or unbound' in stale
    assert 'shows “Saved sample”' not in stale
    assert 'src="_check/shots/' not in stale


def test_map_never_guesses_screenshots_from_old_filenames(blueprint):
    shots = blueprint / '_check/shots'
    shots.mkdir(parents=True)
    (shots / 'home@800.jpg').write_bytes(b'unbound old screenshot')
    assert python('build_map.py', blueprint).returncode == 0
    assert 'src="_check/shots/' not in (blueprint / 'map.html').read_text(encoding='utf-8')


def junction(link, destination):
    if os.name == 'nt':
        # One native shell, literal paths. Never remove/recurse through junctions.
        escaped_link = str(link).replace("'", "''")
        escaped_destination = str(destination).replace("'", "''")
        result = subprocess.run(['powershell', '-NoProfile', '-Command',
                                 "New-Item -ItemType Junction -Path '%s' -Target '%s' | Out-Null" % (escaped_link, escaped_destination)],
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(destination, target_is_directory=True)


@pytest.mark.parametrize('entry', ['_check', '_check/shots', 'assets'])
def test_junctions_fail_without_external_writes(blueprint, entry):
    outside = blueprint.parent / 'outside'
    outside.mkdir()
    link = blueprint / entry
    link.parent.mkdir(parents=True, exist_ok=True)
    junction(link, outside)
    for script in ['check_blueprint.py', 'build_map.py']:
        checked = python(script, blueprint)
        # _check/shots is only traversed when referenced; the browser preflights it.
        if entry != '_check/shots':
            assert checked.returncode == 1, checked.stdout + checked.stderr
    checked = browser(blueprint)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert not list(outside.iterdir())


@pytest.mark.parametrize('filename', ['../outside.html', './../outside.html', 'assets/./../outside.html', '/outside.html', 'C:\\outside.html'])
def test_manifest_paths_cannot_leave_blueprint(blueprint, filename):
    manifest = json.loads((blueprint / 'blueprint.json').read_text(encoding='utf-8'))
    manifest['screens'][0]['file'] = filename
    (blueprint / 'blueprint.json').write_text(json.dumps(manifest), encoding='utf-8')
    for script in ['check_blueprint.py', 'build_map.py']:
        checked = python(script, blueprint)
        assert checked.returncode == 1, checked.stdout + checked.stderr
    assert browser(blueprint).returncode == 1
    assert not (blueprint / 'map.html').exists()


def test_link_cannot_read_outside_blueprint(blueprint):
    (blueprint / 'home.html').write_text('<html><body><a href="../outside.txt">Outside</a></body></html>', encoding='utf-8')
    (blueprint.parent / 'outside.txt').write_text('private synthetic marker', encoding='utf-8')
    checked = python('check_blueprint.py', blueprint)
    assert checked.returncode == 1
    assert 'Unsafe blueprint path' in checked.stdout
    assert 'private synthetic marker' not in checked.stdout


def test_generated_directory_cannot_hide_a_manifest_page_from_fingerprints(blueprint):
    manifest = json.loads((blueprint / 'blueprint.json').read_text(encoding='utf-8'))
    (blueprint / '_check').mkdir()
    (blueprint / '_check/hidden.html').write_text('<h1>Hidden input</h1>', encoding='utf-8')
    manifest['screens'][0]['file'] = '_check/hidden.html'
    (blueprint / 'blueprint.json').write_text(json.dumps(manifest), encoding='utf-8')
    assert python('check_blueprint.py', blueprint).returncode == 1
    result = browser(blueprint)
    assert result.returncode == 1
    assert 'excluded/generated path' in result.stdout


def test_nested_asset_named_map_is_fingerprinted(blueprint):
    assets = blueprint / 'assets'
    assets.mkdir()
    (assets / 'map.html').write_text('<h1>Nested source</h1>', encoding='utf-8')
    assert browser(blueprint, '--no-shots').returncode == 0
    assert 'assets/map.html' in report(blueprint)['evidence']['files']
    assert python('build_map.py', blueprint).returncode == 0
    assert 'controlled-protocol-fixture' in (blueprint / 'map.html').read_text(encoding='utf-8')


@pytest.mark.parametrize('prefix', ['./', '././'])
def test_safe_dot_segments_keep_assets_links_evidence_and_serving_compatible(blueprint, prefix):
    manifest_path = blueprint / 'blueprint.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for page in manifest['screens']:
        page['file'] = prefix + page['file']
    manifest['start'] = prefix + 'home.html'
    manifest['journeys'] = [{'title': 'Sample journey', 'who': 'Reader', 'steps': [prefix + 'home.html', prefix + 'second.html']}]
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    for page in blueprint.glob('*.html'):
        content = page.read_text(encoding='utf-8').replace('href="blueprint.css"', 'href="' + prefix + 'blueprint.css"')
        content = content.replace('src="blueprint.js"', 'src="' + prefix + 'blueprint.js"')
        if page.name == 'home.html':
            content = content.replace('</body>', '<a href="' + prefix + 'second.html">Next page</a></body>')
        page.write_text(content, encoding='utf-8')
    checked = python('check_blueprint.py', blueprint)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    static = json.loads((blueprint / '_check/static.json').read_text(encoding='utf-8'))
    assert static['pages'][0]['file'] == 'home.html'
    assert static['pages'][0]['out'] == ['second']
    captured = blueprint.parent / 'dot-http-result.json'
    result = browser(blueprint, '--no-shots', FAKE_SERVER_PATH='/' + prefix + 'blueprint.js', FAKE_SERVER_RESULT=str(captured))
    assert result.returncode == 0, result.stdout + result.stderr
    response = json.loads(captured.read_text(encoding='utf-8'))
    assert response['status'] == 200
    assert response['text'] == '// sample script'
    assert [page['stem'] for page in report(blueprint)['pages']] == ['home', 'second']
    assert 'home.html' in report(blueprint)['evidence']['files']
    assert not any(name.startswith('./') for name in report(blueprint)['evidence']['files'])
    partial = browser(blueprint, '--no-shots', '--only', prefix + 'home.html')
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert python('build_map.py', blueprint).returncode == 0
    mapped = (blueprint / 'map.html').read_text(encoding='utf-8')
    assert 'controlled-protocol-fixture' in mapped
    assert 'stale or unbound' not in mapped


def test_server_rejects_encoded_parent_and_sibling_prefix(blueprint):
    outside = blueprint.parent / 'blueprint-neighbor'
    outside.mkdir()
    (outside / 'private.txt').write_text('synthetic neighbor marker', encoding='utf-8')
    captured = blueprint.parent / 'http-result.json'
    result = browser(blueprint, '--no-shots', FAKE_SERVER_PATH='/%2e%2e/blueprint-neighbor/private.txt', FAKE_SERVER_RESULT=str(captured))
    assert result.returncode == 0, result.stdout + result.stderr
    response = json.loads(captured.read_text(encoding='utf-8'))
    assert response['status'] == 403
    assert 'synthetic neighbor marker' not in response['text']


def test_initializer_escapes_html_text_but_preserves_original_json(tmp_path):
    name = '<script>synthetic marker</script> & "quoted"'
    root = tmp_path / 'initialized'
    result = python('init_blueprint.py', root, '--name', name)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((root / 'blueprint.json').read_text(encoding='utf-8'))['name'] == name
    for page in root.glob('*.html'):
        text = page.read_text(encoding='utf-8')
        assert name not in text
        original = (SCRIPTS.parent / 'assets/starter' / page.name).read_text(encoding='utf-8')
        if 'Project Starter' in original:
            assert html.escape(name, quote=True) in text


@pytest.mark.parametrize('output', ['map.html', '_check/static.json', '_check/browser.json'])
def test_linked_output_files_preserve_outside_bytes(blueprint, output):
    outside = blueprint.parent / 'outside.txt'
    outside.write_bytes(b'synthetic original bytes')
    link = blueprint / output
    link.parent.mkdir(parents=True, exist_ok=True)
    os.link(outside, link)
    if output == 'map.html':
        result = python('build_map.py', blueprint)
    elif output.endswith('static.json'):
        result = python('check_blueprint.py', blueprint)
    else:
        result = browser(blueprint)
    assert result.returncode == 1, result.stdout + result.stderr
    assert outside.read_bytes() == b'synthetic original bytes'


def test_selected_root_junction_is_rejected(blueprint):
    link = blueprint.parent / 'linked-root'
    junction(link, blueprint)
    for script in ['check_blueprint.py', 'build_map.py']:
        result = python(script, link)
        assert result.returncode == 1, result.stdout + result.stderr
    assert browser(link).returncode == 1
    assert not (blueprint / '_check').exists()
