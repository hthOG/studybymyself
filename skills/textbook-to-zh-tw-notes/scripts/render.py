#!/usr/bin/env python3
"""Render bounded source units or draft PDF previews; output paths, never book text.

The ``pdf`` command is a draft-only convenience. Formal PDF QA previews and their
manifest are generated from the current successful receipt by prepare-review.
"""
import argparse
import json
from pathlib import Path
import re
import sys

import project


def select_units(value):
    selected = set()
    for token in value.split(','):
        match = re.fullmatch(r'(u\d{4,})(?:-(u\d{4,}))?', token.strip())
        if not match:
            raise ValueError('Use u0001-u0005 or u0001,u0003')
        a, b = int(match[1][1:]), int((match[2] or match[1])[1:])
        if a < 1 or b < a or b - a > 100:
            raise ValueError('Render batches must contain at most 101 units')
        selected.update(f'u{n:04d}' for n in range(a, b + 1))
    if len(selected) > 101:
        raise ValueError('Render a bounded batch, not the entire book at once')
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    source = sub.add_parser('source')
    source.add_argument('project')
    source.add_argument('--units', required=True)
    pdf = sub.add_parser('pdf')
    pdf.add_argument('path')
    pdf.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        import pymupdf as fitz
        images = []
        if args.command == 'source':
            root = Path(args.project).resolve()
            record = project.load(root / 'source.json')
            if project.digest(Path(record['path'])) != record['sha256']:
                raise ValueError('Original source hash changed')
            selected = select_units(args.units)
            units = {u['id']: u for u in record['units']}
            if not selected.issubset(units):
                raise ValueError('Unknown source units')
            with fitz.open(record['path']) as doc:
                for uid in sorted(selected):
                    unit = units[uid]
                    out = project.local(root, unit['preview_path'])
                    out.parent.mkdir(parents=True, exist_ok=True)
                    doc[unit['pdf_page'] - 1].get_pixmap(dpi=160).save(out)
                    images.append(str(out))
        else:
            root = Path(args.out).resolve()
            root.mkdir(parents=True, exist_ok=True)
            with fitz.open(args.path) as doc:
                for n, page in enumerate(doc, 1):
                    out = root / f'page-{n:03d}.png'
                    if out.is_symlink():
                        raise ValueError('refusing to replace a symlinked draft preview: ' + str(out))
                    page.get_pixmap(dpi=160).save(out)
                    images.append(str(out))
        result = {'rendered': len(images), 'paths': images, 'review_status': 'not_reviewed'}
        if args.command == 'pdf':
            result.update(artifact_kind='draft_previews', formal_manifest=None,
                          note='Use the supported prepare-review command for receipt-bound PDF QA previews')
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    sys.exit(main())
