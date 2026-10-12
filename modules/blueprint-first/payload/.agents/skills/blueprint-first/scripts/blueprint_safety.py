"""Local path containment and conservative source provenance for blueprint tools."""
import hashlib
import os
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlsplit

EXCLUDED = {'_check', 'map.html', '.git', 'node_modules', '__pycache__'}


def blueprint_root(root):
    root = Path(root).absolute()
    for candidate in (root, *root.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if candidate.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked blueprint root is not supported: %s' % candidate)
    return root.resolve()


def contained(root, relative):
    """Reject absolute/traversing paths and every existing linked descendant."""
    root = blueprint_root(root)
    raw = str(relative).replace('\\', '/')
    if not raw or '\x00' in raw or PureWindowsPath(raw).drive or raw.startswith('/'):
        raise ValueError('Unsafe blueprint path: %s' % relative)
    parts = raw.split('/')
    if any(p in ('', '.', '..') or ':' in p for p in parts):
        raise ValueError('Unsafe blueprint path: %s' % relative)
    candidate = root
    for part in parts:
        candidate /= part
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if (candidate.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400
                or (candidate.is_file() and info.st_nlink > 1)):
            raise ValueError('Linked blueprint path is not supported: %s' % relative)
    if not candidate.resolve().is_relative_to(root):
        raise ValueError('Blueprint path escapes its folder: %s' % relative)
    return candidate


def local_reference(root, reference):
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    local = unquote(parsed.path)
    if any(part in EXCLUDED for part in local.replace('\\', '/').split('/')[:-1]):
        raise ValueError('Local asset uses an excluded/generated directory: %s' % reference)
    return contained(root, local)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_files(root):
    """Hash all local source/assets, excluding only generated/tool directories.

    Whole-folder invalidation is deliberately conservative: shared scripts can
    dynamically load assets, so inferred per-page dependency lists are unsafe.
    """
    root = blueprint_root(root)
    result = {}
    for base, directories, files in os.walk(root, followlinks=False):
        for name in list(directories):
            rel = (Path(base) / name).relative_to(root).as_posix()
            contained(root, rel)  # reject linked directories even when excluded
            if name in EXCLUDED:
                directories.remove(name)
        for name in files:
            rel = (Path(base) / name).relative_to(root).as_posix()
            file = contained(root, rel)
            if not file.is_file():
                raise ValueError('Unsupported blueprint input: %s' % rel)
            if rel != 'map.html':
                result[rel] = digest(file)
    return result


def current_browser(root, record):
    """Only source-bound observations from this auditor version can be reused."""
    evidence = record.get('evidence') or {}
    scripts = Path(__file__).resolve().parent
    return (evidence.get('version') == 1
            and evidence.get('files') == source_files(root)
            and evidence.get('auditor') == digest(scripts / 'browser_audit.cjs')
            and evidence.get('helper') == digest(scripts / 'blueprint_safety.cjs')
            and isinstance(evidence.get('options'), dict))
