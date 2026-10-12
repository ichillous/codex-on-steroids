'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const EXCLUDED = new Set(['_check', 'map.html', '.git', 'node_modules', '__pycache__']);

function blueprintRoot(root) {
  root = path.resolve(root);
  for (let candidate = root; ; candidate = path.dirname(candidate)) {
    if (fs.lstatSync(candidate).isSymbolicLink()) throw new Error('Linked blueprint root is not supported: ' + candidate);
    if (path.dirname(candidate) === candidate) break;
  }
  return fs.realpathSync(root);
}
function canonicalRelative(relative) {
  const raw = String(relative).replace(/\\/g, '/');
  const parts = raw.split('/');
  if (!raw || raw.includes('\0') || path.win32.isAbsolute(raw) ||
      parts.some((p) => !p || p === '..' || p.includes(':'))) {
    throw new Error('Unsafe blueprint path: ' + relative);
  }
  const canonical = parts.filter((p) => p !== '.').join('/');
  if (!canonical) throw new Error('Unsafe blueprint path: ' + relative);
  return canonical;
}
function contained(root, relative) {
  root = blueprintRoot(root);
  const parts = canonicalRelative(relative).split('/');
  let candidate = root;
  for (const part of parts) {
    candidate = path.join(candidate, part);
    let info;
    try { info = fs.lstatSync(candidate); } catch (e) { if (e.code === 'ENOENT') continue; throw e; }
    // Node exposes Windows junctions as symbolic links; realpath also catches
    // other redirected components and avoids lexical sibling-prefix checks.
    const real = fs.realpathSync(candidate);
    const rel = path.relative(root, real);
    if (info.isSymbolicLink() || (info.isFile() && info.nlink > 1) || rel === '..' || rel.startsWith('..' + path.sep) || path.isAbsolute(rel) ||
        real.toLowerCase() !== path.resolve(candidate).toLowerCase()) {
      throw new Error('Linked or escaping blueprint path is not supported: ' + relative);
    }
  }
  return candidate;
}
const digest = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function sourceFiles(root) {
  const result = {};
  function visit(relative) {
    const directory = relative ? contained(root, relative) : root;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const rel = relative ? relative + '/' + entry.name : entry.name;
      const file = contained(root, rel);
      if ((entry.isDirectory() && EXCLUDED.has(entry.name)) || rel === 'map.html') continue;
      if (entry.isDirectory()) visit(rel);
      else if (entry.isFile()) result[rel] = digest(file);
      else throw new Error('Unsupported blueprint input: ' + rel);
    }
  }
  visit('');
  return result;
}
function equal(a, b) {
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return a === b;
  const ak = Object.keys(a).sort(), bk = Object.keys(b).sort();
  return ak.length === bk.length && ak.every((k, i) => k === bk[i] && equal(a[k], b[k]));
}
module.exports = { blueprintRoot, canonicalRelative, contained, digest, sourceFiles, equal };
