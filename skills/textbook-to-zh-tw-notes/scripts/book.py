#!/usr/bin/env python3
"""Whole-book planning, multi-volume compilation and mechanical release checks."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

import project
import latex_build


def volume_count_errors(count: int, request=None) -> list[str]:
    """Apply the default range or an explicitly recorded user-requested count."""
    if type(count) is not int or count < 1:
        return ['Volume count must be a positive integer']
    if request is None:
        return [] if 2 <= count <= 4 else ['Default volume count must be 2-4; record the user request for another count']
    if (not isinstance(request, dict) or type(request.get('count')) is not int
            or request['count'] < 1 or not isinstance(request.get('evidence'), str)
            or not request['evidence'].strip()):
        return ['volume_count_request needs a positive integer count and the actual user request as evidence']
    return [] if count == request['count'] else ['Volume count must match the recorded user request']


def positive_volume_count(value):
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError('volume count must be a positive integer')
    return count


def validate_plan(root: Path, book: dict) -> list[str]:
    errors = project.validate_toc_plan(root, book)
    source = project.load(root / 'source.json')
    known_units = {u['id'] for u in source['units']}
    chapters, volumes = book.get('chapters', []), book.get('volumes', [])
    if book.get('schema_version') != 1 or book.get('chapters_complete') is not True or not chapters:
        errors.append('Complete chapter inventory required before release')
    ids = [c['id'] for c in chapters]
    if len(ids) != len(set(ids)):
        errors.append('Duplicate chapter IDs')
    errors.extend(volume_count_errors(len(volumes), book.get('volume_count_request')))
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
        if not re.fullmatch(r'vol-[0-9]{2,}', v['id']):
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
    evidence = getattr(args, 'volume_count_request', None)
    request = {'count': args.volumes, 'evidence': evidence} if evidence is not None else None
    errors = volume_count_errors(args.volumes, request)
    if errors:
        raise ValueError('; '.join(errors))
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
    plan = {'schema_version': 1, 'title': '繁體中文自學講義',
            'chapters_complete': False, 'chapters': [], 'volumes': volumes}
    if request is not None:
        plan['volume_count_request'] = request
    project.save(root / 'book.json', plan)
    source = project.load(root / 'source.json')
    project.save(root / 'toc.json', {'schema_version': 1, 'source_sha256': source['sha256'],
                                    'status': 'pending', 'evidence': [], 'chapters': [], 'exclusions': []})
    project.save(root / 'progress.json', {'stage': 'structure', 'next_section': '',
                 'open_issues': [], 'tasks': {}, 'recommended_effort': 'high', 'actual_effort': None})
    for folder in ('tasks', 'content/chapters', 'content/answers'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    result.update(next='Verify the original TOC in toc.json, reconcile every source unit, then dispatch bounded reading tasks',
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
    (root / 'build').mkdir(parents=True, exist_ok=True)
    # Invalidate every previous success before preflight or the first compiler attempt.
    for v in book['volumes']:
        latex_build.validate_destinations(root, v['id'], v['qa'])
    for v in book['volumes']:
        v['qa'].update(status='pending', page_count=0, reviewed_pages=[],
                       issues=['New compile attempt; PDF review required'])
        v['qa'].pop('review_fingerprint', None)
        v['qa'].pop('preview_manifest', None)
        latex_build.invalidate_build_record(root, v['id'], v['qa'], 'new compile attempt requested')
    project.save(root / 'book.json', book)

    errors = project.run_checks(root, 'teaching') + validate_plan(root, book)
    if errors:
        raise ValueError('\n'.join(errors))
    if project.load(root / 'content-lock.json') != project.snapshot(root):
        raise ValueError('Content differs from reviewed lock')
    engine = find_xelatex()
    if not engine:
        raise ValueError('XeLaTeX unavailable; run setup.ps1 and inspect doctor output')
    inventory = project.load(root / 'inventory.json')
    for v in book['volumes']:
        vid = v['id']
        required, errors = expected_inputs_for_volume(root, book, v, inventory)
        if errors:
            raise ValueError('\n'.join(errors))
        record = latex_build.compile_target(root, vid, v['qa'], v['layout'], engine, 100, required)
        v['qa'].update(status='pending', page_count=record['page_count'], reviewed_pages=[],
                       issues=['New successful compile; PDF review required'], recorder=record['recorder'])
        project.save(root / 'book.json', book)
    errors = validate_book_output_inputs(root, book, inventory)
    if errors:
        raise ValueError('\n'.join(errors))


def expected_inputs_for_volume(root, book, volume, inventory):
    chapters = {c['id']: c for c in book.get('chapters', [])}
    assigned = set(volume.get('chapter_ids', []))
    expected = {volume.get('layout', '')}
    errors = []
    for chapter_id in assigned:
        chapter = chapters.get(chapter_id)
        if not chapter:
            continue
        expected.update((chapter.get('output', ''), chapter.get('answers', '')))
    try:
        # Validate all input paths before a compiler can read from outside the project.
        for path in expected:
            if not path:
                raise ValueError('empty expected input path')
            project.local(root, path)
    except ValueError as exc:
        errors.append('invalid compile input path: ' + str(exc))
    return sorted(p for p in expected if p), errors


def validate_book_output_inputs(root, book, inventory):
    """Prove every inventory output ref was read by an appropriate compiled volume."""
    errors = []
    chapters = {c['id']: c for c in book.get('chapters', [])}
    volumes = {v['id']: v for v in book.get('volumes', [])}
    manifests = {}
    for volume_id, volume in volumes.items():
        try:
            receipt = project.load(project.local(root, volume['qa']['build_record']))
            if receipt.get('status') == 'success':
                manifests[volume_id] = receipt.get('final_inputs', {}).get('project_inputs', {})
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    for item in inventory.get('items', []):
        if item.get('disposition') not in {'covered', 'compressed'}:
            continue
        related_chapters = {c['id'] for c in chapters.values()
                            if c.get('treatment') != 'omitted'
                            and set(c.get('units', [])) & set(item.get('units', []))}
        related_volumes = {v['id'] for v in volumes.values()
                           if set(v.get('chapter_ids', [])) & related_chapters}
        if not related_chapters or not related_volumes:
            errors.append(item.get('id', '<item>') + ': covered output has no retained chapter/volume with matching source units')
            continue
        refs = item.get('output_refs', [])
        if not refs:
            errors.append(item.get('id', '<item>') + ': covered output has no file reference')
            continue
        for ref in refs:
            try:
                ref_path = project.local(root, ref['file'])
                if not ref_path.is_file():
                    raise ValueError('output reference is missing')
                matched = False
                for volume_id in related_volumes:
                    for relative in manifests.get(volume_id, {}):
                        compiled_path = project.local(root, relative)
                        if compiled_path == ref_path:
                            matched = True
                            break
                    if matched:
                        break
                if not matched:
                    errors.append(item.get('id', '<item>') + ': output ref was not read by a compiled volume for its source units: ' + ref['file'])
            except (TypeError, KeyError, ValueError) as exc:
                errors.append(item.get('id', '<item>') + ': invalid output ref: ' + str(exc))
    return errors


def prepare_review(root, book):
    errors = project.run_checks(root, 'teaching') + validate_plan(root, book)
    if errors:
        raise ValueError('\n'.join(errors))
    if project.load(root / 'content-lock.json') != project.snapshot(root):
        raise ValueError('Content/evidence differs from lock')
    inventory = project.load(root / 'inventory.json')
    # Invalidate all old visual QA before rendering any volume; a partial failure cannot retain old reviews.
    for v in book['volumes']:
        qa = v['qa']
        qa.update(status='pending', reviewed_pages=[], issues=['Preparing fresh PDF page previews'])
        qa.pop('review_fingerprint', None)
        qa.pop('preview_manifest', None)
    project.save(root / 'book.json', book)
    for v in book['volumes']:
        pdf = v['qa']
        expected, input_errors = expected_inputs_for_volume(root, book, v, inventory)
        receipt_errors = latex_build.validate_receipt(root, pdf, expected)
        if input_errors or receipt_errors:
            raise ValueError('\n'.join(input_errors + [v['id'] + ': ' + e for e in receipt_errors]))
        receipt = project.load(project.local(root, pdf['build_record']))
        pdf['recorder'] = receipt['recorder']
        import pdf_review
        manifest_path, manifest = pdf_review.create_manifest(root, pdf, v['id'])
        pdf.update(status='pending', reviewed_pages=[], issues=[], page_count=manifest['page_count'],
                   preview_manifest=manifest_path)
        pdf['review_fingerprint'] = project.pdf_fingerprint(root, pdf)
    output_errors = validate_book_output_inputs(root, book, inventory)
    if output_errors:
        raise ValueError('\n'.join(output_errors))
    project.save(root / 'book.json', book)


def check_book(root):
    errors = project.run_checks(root, 'teaching')
    try:
        book = project.load(root / 'book.json')
        errors.extend(validate_plan(root, book))
        inventory = project.load(root / 'inventory.json')
        if not project.nonempty(root / 'selection-log.md'):
            errors.append('Missing selection-log.md')
        for v in book['volumes']:
            audit = project.Audit(root)
            expected, input_errors = expected_inputs_for_volume(root, book, v, inventory)
            audit.release({'pdf': v['qa']}, expected)
            audit.errors.extend(input_errors)
            errors.extend(v['id'] + ': ' + e for e in audit.errors)
            from pypdf import PdfReader
            actual = len(PdfReader(str(project.local(root, v['qa']['path']))).pages)
            if not 1 <= actual <= 100:
                errors.append(v['id'] + ': actual PDF page count must be 1-100, including all front/end matter')
        errors.extend(validate_book_output_inputs(root, book, inventory))
    except Exception as exc:
        errors.append(f'Invalid/incomplete book record: {type(exc).__name__}: {exc}')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--pdf', required=True)
    init.add_argument('--out', required=True)
    init.add_argument('--volumes', type=positive_volume_count, default=2,
                      help='Planned count, default 2; normally 2-4 unless the user specifies a count')
    init.add_argument('--volume-count-request',
                      help='Actual user instruction for this count; records the exception in book.json')
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
