#!/usr/bin/env python3
"""Start a blueprint folder from the starter kit. Standard library only.

    python3 init_blueprint.py <target-dir> --name "Project name" [--summary "One sentence"]

Copies blueprint.css, blueprint.js, blueprint.json and four small example pages (a screen, a screen
with two states, a message, a reference page). The example pages are marked as starter pages and the
check fails until each one is replaced or removed, so they cannot be left in by accident.
Requires a missing or empty target folder. Refuses linked destinations and never overwrites a file.
"""
import json
import sys
from pathlib import Path

STARTER = Path(__file__).resolve().parent.parent / 'assets' / 'starter'


def main(argv):
    if not argv or argv[0].startswith('--'):
        print(__doc__); return 2
    target = Path(argv[0]).absolute()
    name, summary = 'Project Starter', ''
    for i, a in enumerate(argv):
        if a == '--name' and i + 1 < len(argv):
            name = argv[i + 1]
        if a == '--summary' and i + 1 < len(argv):
            summary = argv[i + 1]
    for candidate in (target, *target.parents):
        try:
            attributes = candidate.lstat()
        except FileNotFoundError:
            continue
        if candidate.is_symlink() or getattr(attributes, 'st_file_attributes', 0) & 0x400:
            print('Linked destinations are not supported: %s. Nothing was changed.' % candidate)
            return 1
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        print('The target must be a missing or empty folder: %s. Continue an existing blueprint separately; nothing was changed.' % target)
        return 1
    outputs = []
    for src in sorted(STARTER.iterdir()):
        if not src.is_file():
            continue
        raw = src.read_bytes()
        if src.suffix == '.html':
            raw = raw.decode('utf-8').replace('Project Starter', name).encode('utf-8')
        elif src.name == 'blueprint.json':
            man = json.loads(raw)
            man['name'] = name
            if summary:
                man['summary'] = summary
            raw = (json.dumps(man, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        outputs.append((src.name, raw))
    target.mkdir(parents=True, exist_ok=True)
    try:
        for filename, raw in outputs:
            with (target / filename).open('xb') as destination:
                destination.write(raw)
    except FileExistsError:
        print('A destination file appeared during initialization. Existing bytes were preserved; reconcile the partial folder: %s.' % target)
        return 1
    print('Blueprint started in %s' % target)
    print('Next: write your groups and screens into blueprint.json, replace the four starter pages, then run check_blueprint.py.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
