#!/usr/bin/env node
/* Open every blueprint page in a real browser, look at it, and press every button once.

     node browser_audit.cjs <blueprint-dir> [--only stem,stem] [--no-clicks] [--no-shots] [--widths 1440,390]

   For each page, at each width and in each declared variant, it records script errors, files that
   failed to load, sideways overflow, text cut off by its box, blank renders and links that broke
   after the runtime rewrote them, and saves a screenshot to <blueprint-dir>/_check/shots/.
   Then, at the first width, it reloads the page for every button, presses it, and records whether
   the press went to another page, changed this one, or did nothing. Buttons revealed by a press
   (a confirmation, the next step) are pressed too. Buttons that never become visible are listed.

   Results: <blueprint-dir>/_check/browser.json. Exit 0 clean, 1 problems found, 3 no browser available.
   A --only run retains earlier pages only when sources and options match. Missing coverage fails.
   Errors are observed through 300 ms settling windows after loads/actions and a final drain;
   later timers, unvisited states and production behavior remain outside this bounded check.

   Use Node 20+ and a compatible Playwright (playwright, playwright-core or @playwright/test, installed in the project,
   beside this script, or globally). It uses Playwright's own browser if one is installed, otherwise an
   installed Chrome or Edge, otherwise the binary named by BLUEPRINT_CHROME. */
'use strict';
const fs = require('fs');
const http = require('http');
const path = require('path');
const { execSync } = require('child_process');
const { blueprintRoot, contained, digest, sourceFiles, equal } = require('./blueprint_safety.cjs');
const SETTLE_MS = 300;

const argv = process.argv.slice(2);
const dirArg = argv.find((a) => !a.startsWith('--'));
if (!dirArg) { console.log('usage: node browser_audit.cjs <blueprint-dir> [--only a,b] [--no-clicks] [--no-shots] [--widths 1440,390]'); process.exit(2); }
const root = blueprintRoot(dirArg);
const opt = (name) => { const i = argv.indexOf(name); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : null; };
const ONLY = (opt('--only') || '').split(',').map((s) => s.trim().replace(/\.html$/, '')).filter(Boolean);
const NO_CLICKS = argv.includes('--no-clicks');
const NO_SHOTS = argv.includes('--no-shots');

function loadPlaywright() {
  const from = [process.cwd(), root, __dirname];
  const names = ['playwright', 'playwright-core', '@playwright/test'];
  for (const n of names) {
    try { return require(require.resolve(n, { paths: from })); } catch (e) { /* next */ }
    try { return require(n); } catch (e) { /* next */ }
  }
  try {
    const g = execSync('npm root -g', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
    for (const n of names) { try { return require(path.join(g, n)); } catch (e) { /* next */ } }
  } catch (e) { /* no npm */ }
  return null;
}
async function launch(pw) {
  const tries = [{}, { channel: 'chrome' }, { channel: 'msedge' }];
  const known = [process.env.BLUEPRINT_CHROME, '/opt/pw-browsers/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  for (const p of known) if (p && fs.existsSync(p) && fs.statSync(p).isFile()) tries.push({ executablePath: p });
  let last = null;
  for (const t of tries) { try { return await pw.chromium.launch(t); } catch (e) { last = e; } }
  throw last;
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.gif': 'image/gif',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.pdf': 'application/pdf', '.ico': 'image/x-icon' };
let servedSources = new Set();
const server = http.createServer((req, res) => {
  let file;
  try {
    const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\//, '');
    file = contained(root, rel);
    if (rel !== 'map.html' && !servedSources.has(rel.replace(/\\/g, '/'))) throw new Error('not a blueprint source');
    if (!fs.statSync(file).isFile()) throw new Error('not a file');
  } catch (e) { res.writeHead(e.code === 'ENOENT' ? 404 : 403); res.end('not available'); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'content-type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream', 'cache-control': 'no-store' });
    res.end(data);
  });
});

/* ---- code that runs inside the page ---- */
const IN_PAGE = {
  measure: () => {
    const doc = document.documentElement, vw = window.innerWidth;
    const over = doc.scrollWidth > vw + 1;
    const wide = [], cut = [];
    const say = (el) => (el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '') +
      ' “' + (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40) + '”');
    // sticks out: its box passes the window edge, or its contents spill out of a box that does not clip them
    const sticksOut = (el, r) => r.width > 0 && (r.right > vw + 1 ||
      (el.scrollWidth > el.clientWidth + 1 && r.left + el.scrollWidth > vw + 1 && getComputedStyle(el).overflowX === 'visible'));
    for (const el of document.body.querySelectorAll('*')) {
      if (el.closest('[data-blueprint-ui]') || el.hidden) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      if (over && wide.length < 3 && sticksOut(el, r) && ![...el.children].some((c) => sticksOut(c, c.getBoundingClientRect()))) wide.push(say(el));
      if (cut.length < 3 && el.children.length === 0 && el.scrollWidth > el.clientWidth + 1 && (el.innerText || '').trim()) {
        const cs = getComputedStyle(el);
        if (cs.overflowX === 'hidden' || cs.overflowX === 'clip') cut.push(say(el));
      }
    }
    const links = [...document.querySelectorAll('a[href]')].filter((a) => !a.closest('[data-blueprint-ui]'))
      .map((a) => ({ label: (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 60), href: a.href }));
    const badImages = [...document.images].filter((i) => i.complete && !i.naturalWidth).map((i) => i.getAttribute('src'));
    return { over, wide, cut, links, badImages, height: Math.ceil(doc.scrollHeight), words: (document.body.innerText || '').trim().length };
  },
  controls: (all) => {
    const sel = 'button, [role="button"], input[type="button"], input[type="submit"], summary, a:not([href]), [data-set], [data-toggle], [data-flash]';
    const pathOf = (el) => {
      const parts = [];
      for (let n = el; n && n !== document.body; n = n.parentElement) {
        let i = 1; for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
        parts.unshift(n.tagName.toLowerCase() + ':nth-of-type(' + i + ')');
      }
      return 'body > ' + parts.join(' > ');
    };
    return [...document.querySelectorAll(sel)].filter((el) => {
      if (el.tagName === 'FORM' || el.closest('[data-blueprint-ui]')) return false;
      if (all) return true;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
    }).map((el) => ({
      path: pathOf(el),
      label: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 70) || '(no words)',
      off: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
      hardOff: !el.hasAttribute('data-off-when'),
      pressed: el.getAttribute('aria-pressed') === 'true',
      noop: el.getAttribute('data-noop'),
      submit: (el.tagName === 'BUTTON' && (el.type === 'submit')) || (el.tagName === 'INPUT' && el.type === 'submit'),
    }));
  },
  fill: (path) => {       // put sample answers into the empty fields a button depends on
    const el = path ? document.querySelector(path) : null;
    const scope = (el && el.closest('form')) || document;
    let n = 0;
    const fire = (f) => { f.dispatchEvent(new Event('input', { bubbles: true })); f.dispatchEvent(new Event('change', { bubbles: true })); };
    for (const f of scope.querySelectorAll('input, select, textarea')) {
      const r = f.getBoundingClientRect();
      if (!r.width || f.disabled || f.readOnly) continue;
      if (f.tagName === 'SELECT') { if (!f.value && f.options.length > 1) { f.selectedIndex = 1; fire(f); n++; } continue; }
      if (f.type === 'checkbox') { if (!f.checked && (f.required || f.hasAttribute('data-bind'))) { f.checked = true; fire(f); n++; } continue; }
      if (f.type === 'radio') { if (f.required && !scope.querySelector('input[type=radio][name="' + f.name + '"]:checked')) { f.checked = true; fire(f); n++; } continue; }
      if (['hidden', 'submit', 'button', 'reset', 'file', 'range', 'color'].includes(f.type) || f.value) continue;
      f.value = { email: 'sam@example.com', number: '1', tel: '5550100', url: 'https://example.com', date: '2030-01-15', time: '10:00', password: 'Sample-pass-1234' }[f.type] || 'Sample';
      fire(f); n++;
    }
    return n;
  },
  signature: () => JSON.stringify({
    url: location.pathname + location.search + location.hash,
    text: document.body.innerText,
    hidden: document.querySelectorAll('[hidden]').length,
    marks: [...document.querySelectorAll('[aria-pressed],[aria-expanded],[aria-selected],[aria-disabled],details')].map((e) =>
      [e.getAttribute('aria-pressed'), e.getAttribute('aria-expanded'), e.getAttribute('aria-selected'), e.getAttribute('aria-disabled'), e.open === true].join('')).join('|'),
    checks: [...document.querySelectorAll('input[type=checkbox],input[type=radio]')].map((e) => (e.checked ? 1 : 0)).join(''),
    nodes: document.body.querySelectorAll('*').length,
  }),
};

function variantsOf(html) {
  const body = (html.match(/<body\b[^>]*>/i) || [''])[0];
  const m = body.match(/data-variants\s*=\s*"([^"]*)"/i) || body.match(/data-variants\s*=\s*'([^']*)'/i);
  const out = [''];
  if (!m) return out;
  for (const part of m[1].split(';')) {
    const i = part.indexOf('='); if (i < 0) continue;
    const key = part.slice(0, i).trim();
    part.slice(i + 1).split('|').map((s) => s.trim()).filter(Boolean).slice(1).forEach((v) => out.push(key + '=' + v));
  }
  return out;
}

(async () => {
  let man;
  try { man = JSON.parse(fs.readFileSync(contained(root, 'blueprint.json'), 'utf8')); }
  catch (e) { console.log('FAIL  cannot read blueprint.json in ' + root + ': ' + e.message); process.exit(1); }
  const widthsAll = (opt('--widths') || '').split(',').filter(Boolean).map(Number);
  const defWidths = widthsAll.length ? widthsAll : (Array.isArray(man.widths) && man.widths.length ? man.widths : [1440, 390]);
  const validWidths = (ws) => Array.isArray(ws) && ws.length && ws.every((w) => Number.isInteger(w) && w > 0 && w <= 10000);
  if (!validWidths(defWidths)) throw new Error('Widths must be positive integers up to 10000.');
  const groupCount = {};
  const allScreens = (man.screens || []).map((s) => {
    contained(root, s.file);
    if (s.widths && !validWidths(s.widths)) throw new Error('Invalid screen widths: ' + s.file);
    groupCount[s.group] = (groupCount[s.group] || 0) + 1;
    return Object.assign({}, s, { stem: String(s.file).replace(/\.html$/, ''), code: s.group + groupCount[s.group], kind: s.kind || 'screen' });
  });
  if (!allScreens.length || new Set(allScreens.map((s) => s.stem)).size !== allScreens.length) throw new Error('List distinct blueprint screens before auditing.');
  if (ONLY.some((stem) => !allScreens.some((s) => s.stem === stem))) throw new Error('--only names a page absent from the manifest.');
  const screens = allScreens.filter((s) => !ONLY.length || ONLY.includes(s.stem));
  const outFile = contained(root, '_check/browser.json');
  const shotsDir = contained(root, '_check/shots');
  const evidence = { version: 1, files: sourceFiles(root), auditor: digest(__filename), helper: digest(path.join(__dirname, 'blueprint_safety.cjs')),
    options: { widths: defWidths, clicks: !NO_CLICKS, shots: !NO_SHOTS, settle_ms: SETTLE_MS } };
  for (const s of allScreens) {
    if (fs.existsSync(contained(root, s.file)) && !Object.prototype.hasOwnProperty.call(evidence.files, s.file.replace(/\\/g, '/'))) throw new Error('Manifest page uses an excluded/generated path: ' + s.file);
  }
  servedSources = new Set(Object.keys(evidence.files));
  const pw = loadPlaywright();
  if (!pw) {
    console.log('NO BROWSER  Playwright is not installed where this script can find it.');
    console.log('  Install it in the project (npm i -D playwright) or globally (npm i -g playwright). With Chrome or Edge already installed,');
    console.log('  playwright-core is enough and downloads nothing. Until then the browser checks are NOT done: say so in the report.');
    process.exit(3);
  }
  let browser;
  try { browser = await launch(pw); }
  catch (e) {
    console.log('NO BROWSER  Playwright is installed but no browser could start: ' + String(e.message || e).split('\n')[0]);
    console.log('  Run "npx playwright install chromium", or set BLUEPRINT_CHROME to a Chrome or Edge binary. The browser checks are NOT done.');
    process.exit(3);
  }
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = 'http://127.0.0.1:' + server.address().port + '/';
  fs.mkdirSync(contained(root, '_check/shots'), { recursive: true });
  const fails = [], warns = [], pagesOut = [];
  const counts = { renders: 0, presses: 0, navigates: 0, changes: 0, nothing: 0, unavailable: 0, unreached: 0 };

  for (const s of screens) {
    const file = contained(root, s.file);
    const where = s.code + ' ' + s.file;
    const rec = { stem: s.stem, code: s.code, renders: [], controls: [] };
    pagesOut.push(rec);
    if (!fs.existsSync(file)) { fails.push({ where, what: 'file does not exist' }); continue; }
    const variants = variantsOf(fs.readFileSync(file, 'utf8'));
    const widths = Array.isArray(s.widths) && s.widths.length ? s.widths : (['screen', 'message'].includes(s.kind) ? defWidths : [defWidths[0]]);
    const everything = new Map(), pressedPaths = new Set();      // every button in the page, and the ones we reached

    for (const w of widths) for (const v of variants) {
      const ctx = await browser.newContext({ viewport: { width: w, height: w < 700 ? 844 : 900 }, reducedMotion: 'reduce' });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push('script error: ' + String(e.message || e).slice(0, 160)));
      page.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text().slice(0, 160)); });
      page.on('response', (r) => { if (r.status() >= 400 && r.url().startsWith(base)) errors.push('did not load: ' + r.url().slice(base.length)); });
      const url = base + s.file + (v ? '?' + v : '');
      const tag = '@' + w + (v ? '~' + v.replace(/[^\w-]+/g, '-') : '');
      const at = where + ' ' + tag;
      const drain = (stage) => {
        [...new Set(errors.splice(0))].filter((e) => !/favicon/.test(e)).forEach((e) => fails.push({ where: at, what: stage + ': ' + e }));
      };
      const settle = async (stage) => { await page.waitForTimeout(SETTLE_MS); drain(stage); };
      let m = null;
      try {
        await page.goto(url, { waitUntil: 'load', timeout: 20000 });
        await page.addStyleTag({ content: '[data-blueprint-ui]{display:none!important}' });
        await settle('initial render');
        m = await page.evaluate(IN_PAGE.measure);
      } catch (e) { fails.push({ where: at, what: 'did not open: ' + String(e.message || e).split('\n')[0].slice(0, 160) }); }
      counts.renders++;
      drain('initial render');
      if (m) {
        if (m.over) fails.push({ where: at, what: 'wider than the window, so it scrolls sideways' + (m.wide.length ? ': ' + m.wide.join(', ') : '') });
        if (m.words < 20) fails.push({ where: at, what: 'renders almost empty (' + m.words + ' characters of text)' });
        m.cut.forEach((c) => warns.push({ where: at, what: 'text is cut off by its box: ' + c }));
        m.badImages.forEach((src) => fails.push({ where: at, what: 'image did not load: ' + src }));
        for (const l of m.links) {
          if (!l.href.startsWith(base)) continue;
          const target = decodeURIComponent(l.href.slice(base.length).split(/[?#]/)[0]);
          if (target && target !== 'map.html' && !fs.existsSync(contained(root, target))) fails.push({ where: at, what: 'link “' + l.label + '” goes to ' + target + ', which does not exist' });
        }
        let shot = null;
        if (!NO_SHOTS) {
          shot = encodeURIComponent(s.stem) + tag + '.jpg';
          try { await page.screenshot({ path: contained(root, '_check/shots/' + shot), fullPage: true, type: 'jpeg', quality: 72 }); } catch (e) { shot = null; }
        }
        rec.renders.push({ width: w, variant: v, height: m.height, overflow: m.over, shot: shot ? 'shots/' + shot : null, shot_sha256: shot ? digest(contained(root, '_check/shots/' + shot)) : null });
      }

      /* Press every button once, each from a fresh load. A press that changes the page may reveal
         more buttons (a confirmation, the next step of a form); those are pressed too, by replaying
         the presses that reveal them, up to three presses deep. */
      if (m && !NO_CLICKS && w === widths[0]) {
        const prepare = async (c) => {        // returns a note, or false if the button stays unavailable
          if (c.off) {
            await page.evaluate(IN_PAGE.fill, null);
            const still = await page.evaluate((p) => { const el = document.querySelector(p); return !el || el.disabled === true || el.getAttribute('aria-disabled') === 'true'; }, c.path);
            return still ? false : 'becomes available once the fields are filled';
          }
          if (c.submit) { const n = await page.evaluate(IN_PAGE.fill, c.path); return n ? 'pressed after filling ' + n + ' field' + (n === 1 ? '' : 's') : ''; }
          return '';
        };
        let first = [];
        try { first = await page.evaluate(IN_PAGE.controls, false); (await page.evaluate(IN_PAGE.controls, true)).forEach((c) => everything.set(c.path, c.label)); } catch (e) { /* page went away */ }
        const queue = first.map((c) => ({ seq: [], c }));
        const done = new Set();
        let budget = 60;
        while (queue.length && budget-- > 0) {
          const { seq, c } = queue.shift();
          if (done.has(c.path)) continue;
          done.add(c.path); pressedPaths.add(c.path);
          const out = { label: c.label, variant: v, after: seq.map((x) => x.label), outcome: '', to: null, note: '', shows: '' };
          rec.controls.push(out);
          counts.presses++;
          let onDialog = null;
          try {
            await page.goto(url, { waitUntil: 'load', timeout: 20000 });
            await settle('reload before ' + c.label);
            let dialog = null;
            onDialog = (d) => { dialog = d.type(); d.dismiss().catch(() => {}); };
            page.on('dialog', onDialog);
            for (const step of seq) { await prepare(step); await page.locator(step.path).first().click({ timeout: 2500 }); await settle('replay ' + step.label); }
            const visibleBefore = (await page.evaluate(IN_PAGE.controls, false)).map((x) => x.path);
            const note = await prepare(c);
            if (note === false) {
              out.outcome = 'unavailable'; out.note = 'stays unavailable even with every field filled'; counts.unavailable++; page.off('dialog', onDialog);
              if (!c.hardOff) warns.push({ where, what: 'button “' + c.label + '” stays unavailable even with every field filled; check the condition that switches it on' });
              continue;
            }
            out.note = note;
            const before = await page.evaluate(IN_PAGE.signature);
            await page.locator(c.path).first().click({ timeout: 2500 });
            await settle('press ' + c.label);
            await page.waitForLoadState('load').catch(() => {});
            await settle('navigation after ' + c.label);
            const after = await page.evaluate(IN_PAGE.signature);
            page.off('dialog', onDialog);
            const bUrl = JSON.parse(before).url.split(/[?#]/)[0], aUrl = JSON.parse(after).url.split(/[?#]/)[0];
            const tail = (seq.length ? ' (after “' + seq.map((x) => x.label).join('”, “') + '”)' : '') + (v ? ' ~' + v : '');
            if (dialog) { out.outcome = 'browser dialog'; counts.changes++; warns.push({ where, what: 'button “' + c.label + '” opens a browser ' + dialog + ' box, which cannot carry designed wording; show that message on the page instead' }); }
            else if (aUrl !== bUrl) { out.outcome = 'navigates'; out.to = aUrl.replace(/^\//, ''); counts.navigates++; }
            else if (after !== before) {
              out.outcome = 'changes'; counts.changes++;
              const had = new Set(JSON.parse(before).text.split('\n').map((t) => t.trim()));
              const fresh = JSON.parse(after).text.split('\n').map((t) => t.trim()).filter((t) => t.length > 2 && !had.has(t));
              if (fresh.length) out.shows = fresh.slice(0, 2).join(' / ').replace(/\s+/g, ' ').slice(0, 110);
              if (seq.length < 2) for (const r of await page.evaluate(IN_PAGE.controls, false)) if (!visibleBefore.includes(r.path) && !done.has(r.path)) queue.push({ seq: seq.concat([c]), c: r });
            }
            else if (c.pressed) { out.outcome = 'already selected'; counts.changes++; }
            else if (c.noop !== null) { out.outcome = 'nothing, by design'; out.note = c.noop || ''; counts.changes++; }
            else { out.outcome = 'nothing'; counts.nothing++; fails.push({ where: where + tail, what: 'button “' + c.label + '” was pressed and nothing happened' }); }
          } catch (e) {
            out.outcome = 'could not be pressed';
            fails.push({ where, what: 'button “' + c.label + '” could not be pressed: ' + String(e.message || e).split('\n')[0].slice(0, 140) });
          } finally {
            if (onDialog) page.off('dialog', onDialog);
            await settle('after control ' + c.label);
          }
        }
        if (queue.length) warns.push({ where, what: 'more than 60 buttons on this page; ' + queue.length + ' were not pressed' });
      }
      await settle('final observation');
      await ctx.close();
      drain('context close');
    }
    if (!NO_CLICKS) {
      const missed = [...everything].filter(([p]) => !pressedPaths.has(p)).map(([, label]) => '“' + label + '”');
      rec.unreached = missed.length;
      if (missed.length) { counts.unreached += missed.length; warns.push({ where, what: missed.length + ' button(s) never became visible, so they were not pressed: ' + missed.slice(0, 6).join(', ') + (missed.length > 6 ? ' …' : '') + '. Add a variant that shows them.' }); }
    }
  }
  const version = browser.version();
  await browser.close();
  server.close();

  const fold = (list) => {
    const seen = new Map();
    for (const f of list) {
      const m = f.where.match(/^(\S+ \S+) (@\S+)$/);
      const key = (m ? m[1] : f.where) + '\u0000' + f.what;
      if (!seen.has(key)) seen.set(key, { where: m ? m[1] : f.where, what: f.what, at: [] });
      if (m) seen.get(key).at.push(m[2]);
    }
    return [...seen.values()].map((f) => ({ where: f.where + (f.at.length ? ' ' + (f.at.length > 3 ? f.at.slice(0, 3).join(' ') + ' and ' + (f.at.length - 3) + ' more' : f.at.join(' ')) : ''), what: f.what }));
  };
  const foldedFails = fold(fails), foldedWarns = fold(warns);
  fails.length = 0; foldedFails.forEach((f) => fails.push(f));
  warns.length = 0; foldedWarns.forEach((f) => warns.push(f));
  const result = { browser: 'Chromium ' + version, widths: defWidths, evidence, counts, pages: pagesOut, fails: [...fails], warns: [...warns] };
  const order = allScreens.map((s) => s.stem);
  if (ONLY.length && fs.existsSync(outFile)) {
    try {
      const old = JSON.parse(fs.readFileSync(contained(root, '_check/browser.json'), 'utf8'));
      if (equal(old.evidence, evidence)) {
        const mine = new Set(screens.map((p) => p.stem)), myCodes = screens.map((p) => p.code + ' ');
        const keep = (list) => (list || []).filter((f) => f.where !== 'coverage' && !myCodes.some((c) => f.where.startsWith(c)));
        result.pages = (old.pages || []).filter((p) => !mine.has(p.stem) && order.includes(p.stem)).concat(pagesOut).sort((a, b) => order.indexOf(a.stem) - order.indexOf(b.stem));
        result.fails = keep(old.fails).concat(fails);
        result.warns = keep(old.warns).concat(warns);
      } else {
        result.warns.push({ where: 'coverage', what: 'Previous browser evidence is stale or has different audit options; earlier pages were discarded.' });
      }
    } catch (e) { result.warns.push({ where: 'coverage', what: 'Previous browser evidence could not be read; earlier pages were discarded.' }); }
  }
  result.missing = order.filter((stem) => !result.pages.some((p) => p.stem === stem));
  if (result.missing.length) result.fails.push({ where: 'coverage', what: 'Pages have no current browser evidence: ' + result.missing.join(', ') });
  if (!equal(evidence.files, sourceFiles(root))) {
    result.fails.push({ where: 'coverage', what: 'Blueprint source changed during the audit; rerun all pages.' });
    result.evidence = null; // an interrupted/moving-source run is never reusable
  }
  result.complete = !result.missing.length && !!result.evidence;
  const all = result.pages.flatMap((p) => p.controls), n = (o) => all.filter((c) => c.outcome === o).length;
  result.counts = { renders: result.pages.reduce((t, p) => t + p.renders.length, 0), presses: all.length, navigates: n('navigates'), nothing: n('nothing'),
    unavailable: n('unavailable'), unreached: result.pages.reduce((t, p) => t + (p.unreached || 0), 0) };
  result.counts.changes = all.length - result.counts.navigates - result.counts.nothing - result.counts.unavailable - n('could not be pressed');
  fs.writeFileSync(contained(root, '_check/browser.json'), JSON.stringify(result, null, 1));
  console.log((man.name || 'Blueprint') + ': ' + pagesOut.length + (pagesOut.length === 1 ? ' page' : ' pages') + ' opened, ' + counts.renders + ' renders, ' + counts.presses + ' buttons pressed (' +
    counts.navigates + ' went to another page, ' + counts.changes + ' changed the page, ' + counts.unavailable + ' unavailable, ' + counts.nothing + ' did nothing' + (counts.unreached ? '; ' + counts.unreached + ' never became visible' : '') + ')');
  result.fails.forEach((f) => console.log('FAIL  ' + f.where + ': ' + f.what));
  result.warns.forEach((f) => console.log('WARN  ' + f.where + ': ' + f.what));
  console.log('Current run: ' + fails.length + ' failures. Aggregate: ' + result.fails.length + ' to fix, ' + result.warns.length + ' to look at.' + (NO_SHOTS ? '' : ' Screenshots are in ' + path.join(dirArg, '_check', 'shots') + ' — look at them; a clean run does not mean the pages look right.'));
  process.exit(result.fails.length ? 1 : 0);
})().catch((e) => { console.log('FAIL  the audit itself crashed: ' + (e && e.stack || e)); try { server.close(); } catch (x) { /* closed */ } process.exit(1); });
