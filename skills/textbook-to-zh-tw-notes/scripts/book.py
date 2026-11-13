#!/usr/bin/env python3
"""Whole-book planning, multi-volume compilation and mechanical release checks."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import project


def validate_plan(root: Path, book: dict) -> list[str]:
    errors = []
    source = project.load(root / 'source.json')
    known_units = {u['id'] for u in source['units']}
    chapters, volumes = book.get('chapters', []), book.get('volumes', [])
    if book.get('schema_version') != 1 or book.get('chapters_complete') is not True or not chapters:
        errors.append('Complete chapter inventory required before release')
    ids = [c['id'] for c in chapters]
    if len(ids) != len(set(ids)):
        errors.append('Duplicate chapter IDs')
    if not 2 <= len(volumes) <= 4:
        errors.append('Book must contain 2-4 volumes')
    assigned, outputs, layouts = [], [], []
    volume_ids = [v['id'] for v in volumes]
    if len(volume_ids) != len(set(volume_ids)):
        errors.append('Duplicate volume IDs')
    retained = set()
    for c in chapters:
        if not c.get('units') or not set(c['units']).issubset(known_units):
            errors.append(c['id'] + ': chapter needs registered source units')
        if not c.get('priority_reason', '').strip():
            errors.append(c['id'] + ': chapter importance rationale missing')
        if c.get('treatment') not in {'full', 'compressed', 'omitted'}:
            errors.append(c['id'] + ': unknown chapter treatment')
        if c.get('treatment') in {'compressed', 'omitted'} and not c.get('reason', '').strip():
            errors.append(c['id'] + ': compression/omission reason required')
        if c.get('treatment') != 'omitted':
            retained.add(c['id'])
            for key in ('output', 'answers'):
                p = project.local(root, c.get(key, ''))
                if not p.is_relative_to(root / 'content') or not project.nonempty(p):
                    errors.append(c['id'] + ': missing content/' + key)
    for v in volumes:
        if not re.fullmatch(r'vol-[0-9]{2}', v['id']):
            errors.append('Volume ID must be vol-NN: ' + v['id'])
        if not v.get('chapter_ids'):
            errors.append(v['id'] + ': empty volume')
        assigned.extend(v.get('chapter_ids', []))
        pages = v.get('planned_pages')
        if type(pages) is not int or not 1 <= pages <= 100:
            errors.append(v['id'] + ': estimated pages must be 1-100')
        layout = project.local(root, v.get('layout', ''))
        if not layout.is_relative_to(root / 'layout') or not project.nonempty(layout):
            errors.append(v['id'] + ': layout missing/outside layout/')
        layouts.append(str(layout))
        pdf = project.local(root, v.get('qa', {}).get('path', ''))
        outputs.append(str(pdf))
    if len(assigned) != len(set(assigned)) or set(assigned) != retained:
        errors.append('Every retained chapter must be assigned exactly once; omitted chapters must not be assigned')
    if len(layouts) != len(set(layouts)) or len(outputs) != len(set(outputs)):
        errors.append('Each volume needs a distinct layout and PDF path')
    return errors


def init_book(args):
    from pypdf import PdfReader
    original = Path(args.pdf).resolve()
    count = len(PdfReader(str(original)).pages)
    result = project.init_project(argparse.Namespace(pdf=str(original), pages=f'1-{count}', out=args.out))
    root = Path(args.out).resolve()
    volumes = []
    for n in range(1, args.volumes + 1):
        vid = f'vol-{n:02d}'
        volumes.append({'id': vid, 'chapter_ids': [], 'planned_pages': 85,
                        'layout': f'layout/{vid}.tex',
                        'qa': {'status': 'pending', 'path': f'build/{vid}.pdf',
                               'log': f'build/{vid}.log', 'build_record': f'build/{vid}.compile.txt',
                               'page_count': 0, 'reviewed_pages': [], 'issues': []}})
    project.save(root / 'book.json', {'schema_version': 1, 'title': '繁體中文自學講義',
                                    'chapters_complete': False, 'chapters': [], 'volumes': volumes})
    project.save(root / 'progress.json', {'stage': 'structure', 'next_section': '',
                 'open_issues': [], 'tasks': {}, 'recommended_effort': 'high', 'actual_effort': None})
    for folder in ('tasks', 'content/chapters', 'content/answers'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    result.update(next='Inspect TOC only in main-agent context, then dispatch bounded parallel reading tasks',
                  volumes=args.volumes)
    return result


def tex_escape(value):
    substitutions = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
                     '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(substitutions.get(c, c) for c in str(value))


def write_layouts(root, book):
    template = (Path(__file__).resolve().parents[1] / 'assets/main.tex').read_text(encoding='utf-8')
    preamble = template.split(r'\begin{document}', 1)[0]
    chapters = {c['id']: c for c in book['chapters']}
    for v in book['volumes']:
        lines = [preamble, r'\begin{document}',
                 r'\begin{center}{\LARGE\bfseries ' + tex_escape(book.get('title', '自學講義')) + r'}\par',
                 tex_escape(v['id']) + r'\end{center}', r'\tableofcontents', r'\clearpage']
        for cid in v['chapter_ids']:
            c = chapters[cid]
            for key in ('output', 'answers'):
                path = project.local(root, c[key])
                if not path.is_relative_to(root / 'content'):
                    raise ValueError('Chapter inputs must stay inside content/')
                rel = path.relative_to(root).as_posix()
                # Restrict input paths rather than allowing TeX macro injection from a JSON path.
                if not re.fullmatch(r'[A-Za-z0-9_./-]+\.tex', rel):
                    raise ValueError('Use ASCII letters/digits/underscores/hyphens for TeX file paths')
                if key == 'answers':
                    lines += [r'\clearpage', r'\subsection*{提示與參考解答}']
                lines.append(r'\input{' + rel + '}')
            lines.append(r'\clearpage')
        lines.append(r'\end{document}')
        project.local(root, v['layout']).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def find_xelatex():
    found = shutil.which('xelatex')
    if found:
        return found
    if os.name == 'nt':
        for variable, suffix in [('LOCALAPPDATA', 'Programs/MiKTeX/miktex/bin/x64/xelatex.exe'),
                                 ('APPDATA', 'MiKTeX/miktex/bin/x64/xelatex.exe'),
                                 ('ProgramFiles', 'MiKTeX/miktex/bin/x64/xelatex.exe')]:
            base = os.environ.get(variable)
            if base and (Path(base) / suffix).is_file():
                return str(Path(base) / suffix)
    return None


def compile_volumes(root, book):
    errors = project.run_checks(root, 'teaching') + validate_plan(root, book)
    if errors:
        raise ValueError('\n'.join(errors))
    if project.load(root / 'content-lock.json') != project.snapshot(root):
        raise ValueError('Content differs from reviewed lock')
    engine = find_xelatex()
    if not engine:
        raise ValueError('XeLaTeX unavailable; run setup.ps1 and inspect doctor output')
    (root / 'build').mkdir(exist_ok=True)
    for v in book['volumes']:
        vid = v['id']
        expected = {'path': f'build/{vid}.pdf', 'log': f'build/{vid}.log',
                    'build_record': f'build/{vid}.compile.txt'}
        if any(v['qa'].get(k) != val for k, val in expected.items()):
            raise ValueError('Compile expects standard build/vol-NN PDF/log/record paths')
        # Explicitly invalidate old QA before the first attempt, including failed rebuilds.
        v['qa'].update(status='pending', reviewed_pages=[], issues=['Recompiled; review required'])
        v['qa'].pop('review_fingerprint', None)
        project.save(root / 'book.json', book)
        cmd = [engine, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', '-output-directory=build', '-jobname=' + vid, v['layout']]
        record = {'time_utc': datetime.now(timezone.utc).isoformat(), 'command': cmd, 'passes': []}
        record_path = project.local(root, v['qa']['build_record'])
        for attempt in range(1, 5):
            result = subprocess.run(cmd, cwd=root, capture_output=True, timeout=300)
            record['passes'].append({'pass': attempt, 'returncode': result.returncode,
                                     'stdout': result.stdout.decode('utf-8', errors='replace')[-12000:]})
            project.save(record_path, record)
            if result.returncode:
                raise ValueError(vid + ': XeLaTeX failed; inspect build record and log')
            text = project.local(root, v['qa']['log']).read_text(encoding='utf-8', errors='replace')
            if attempt >= 2 and not re.search(r'Rerun to get|Label\(s\) may have changed', text):
                break
        if re.search(r'Rerun to get|Label\(s\) may have changed', text):
            raise ValueError(vid + ': cross-references did not stabilize after 4 passes')
        if re.search(r'(?m)^!|Undefined control sequence|Missing character:|(?:Reference|Citation) .* undefined|multiply[- ]defined', text):
            raise ValueError(vid + ': unresolved LaTeX diagnostics')
        from pypdf import PdfReader
        n = len(PdfReader(str(project.local(root, v['qa']['path']))).pages)
        if n > 100:
            raise ValueError(f'{vid}: {n} PDF pages exceeds 100; return to editorial planning')


def prepare_review(root, book):
    errors = project.run_checks(root, 'teaching') + validate_plan(root, book)
    if errors:
        raise ValueError('\n'.join(errors))
    if project.load(root / 'content-lock.json') != project.snapshot(root):
        raise ValueError('Content/evidence differs from lock')
    from pypdf import PdfReader
    for v in book['volumes']:
        pdf = v['qa']
        pdf.update(status='pending', reviewed_pages=[], issues=[],
                   page_count=len(PdfReader(str(project.local(root, pdf['path']))).pages),
                   review_fingerprint=project.pdf_fingerprint(root, pdf))
    project.save(root / 'book.json', book)


def check_book(root):
    errors = project.run_checks(root, 'teaching')
    try:
        book = project.load(root / 'book.json')
        errors.extend(validate_plan(root, book))
        if not project.nonempty(root / 'selection-log.md'):
            errors.append('Missing selection-log.md')
        for v in book['volumes']:
            audit = project.Audit(root)
            audit.release({'pdf': v['qa']})
            errors.extend(v['id'] + ': ' + e for e in audit.errors)
            from pypdf import PdfReader
            actual = len(PdfReader(str(project.local(root, v['qa']['path']))).pages)
            if not 1 <= actual <= 100:
                errors.append(v['id'] + ': actual PDF page count must be 1-100, including all front/end matter')
    except Exception as exc:
        errors.append(f'Invalid/incomplete book record: {type(exc).__name__}: {exc}')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--pdf', required=True)
    init.add_argument('--out', required=True)
    init.add_argument('--volumes', type=int, choices=(2, 3, 4), default=2)
    for command in ('write-layouts', 'compile', 'prepare-review', 'check'):
        p = sub.add_parser(command)
        p.add_argument('project')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = init_book(args)
        else:
            root = Path(args.project).resolve()
            book = project.load(root / 'book.json')
            if args.command == 'check':
                errors = check_book(root)
                result = {'status': 'fail' if errors else 'pass', 'errors': errors,
                          'scope': 'mechanical record/file/PDF checks; semantic review still required'}
                print(json.dumps(result, ensure_ascii=True, indent=2))
                return 1 if errors else 0
            if args.command == 'write-layouts':
                write_layouts(root, book)
            elif args.command == 'compile':
                compile_volumes(root, book)
            else:
                prepare_review(root, book)
            result = {'status': 'pass', 'action': args.command}
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=True))
        return 2


if __name__ == '__main__':
    sys.exit(main())
