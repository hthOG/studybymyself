"""Synthetic book fixtures exercise page budgets and multi-volume record integrity."""
import argparse
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import book
import test_project as fixture_module
import pdf_review

PNG = fixture_module.PNG
project = fixture_module.project
install_synthetic_receipt = fixture_module.install_synthetic_receipt
latex_build = fixture_module.latex_build


class BookTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.HandoffTests('test_extraction_is_not_reading')
        self.fixture.setUp()
        self.root = self.fixture.root
        self.fixture.ready_teaching()
        for n in (1, 2):
            for folder in ('chapters', 'answers'):
                p = self.root / 'content' / folder
                p.mkdir(exist_ok=True)
                body = (r'\section{Synthetic}\label{S1}' + '\n' + r'\input{content/math/E1.tex}') if (n, folder) == (1, 'chapters') else f'Synthetic {folder} {n}'
                (p / f'ch{n:02d}.tex').write_text(body + '\n', encoding='utf-8')
        chapters = [{'id': f'ch{n:02d}', 'title': f'Synthetic chapter {n}', 'toc_ids': [f'toc-{n:03d}'],
                     'units': [f'u{n:04d}'],
                     'treatment': 'full', 'priority_reason': 'Synthetic core dependency',
                     'output': f'content/chapters/ch{n:02d}.tex', 'answers': f'content/answers/ch{n:02d}.tex'}
                    for n in (1, 2)]
        volumes = [{'id': f'vol-{n:02d}', 'chapter_ids': [f'ch{n:02d}'], 'planned_pages': 85,
                    'layout': f'layout/vol-{n:02d}.tex',
                    'qa': {'status': 'pending', 'path': f'build/vol-{n:02d}.pdf', 'log': f'build/vol-{n:02d}.log',
                           'build_record': f'build/vol-{n:02d}.compile.txt', 'page_count': 0,
                           'reviewed_pages': [], 'issues': []}} for n in (1, 2)]
        self.data = {'schema_version': 1, 'chapters_complete': True, 'title': 'Synthetic book',
                     'chapters': chapters, 'volumes': volumes}
        source = self.fixture.read('source.json')
        toc_chapters = []
        for n in (1, 2):
            unit = f'u{n:04d}'
            anchor = f'Synthetic source page {n}'
            toc_chapters.append({'id': f'toc-{n:03d}', 'title': f'Synthetic chapter {n}',
                                 'locator': f'chapter {n}', 'units': [unit],
                                 'evidence': [{'file': f'source/text/{unit}.txt', 'anchor': anchor}]})
        project.save(self.root / 'toc.json', {'schema_version': 1, 'source_sha256': source['sha256'],
                                               'status': 'verified',
                                               'evidence': [{'file': 'source/text/u0001.txt',
                                                             'anchor': 'Synthetic source page 1'}],
                                               'chapters': toc_chapters, 'exclusions': []})
        project.save(self.root / 'book.json', self.data)
        book.write_layouts(self.root, self.data)
        inventory = self.fixture.read('inventory.json')
        for item in inventory['items']:
            item.update(priority='A', priority_reason='Synthetic core content')
            item['units'] = ['u0001']
            item['output_refs'] = [{'file': 'content/chapters/ch01.tex' if item['id'] == 'S1' else 'content/math/E1.tex',
                                    'anchor': '\\label{' + item['id'] + '}'}]
        self.fixture.write('inventory.json', inventory)
        (self.root / 'selection-log.md').write_text('Synthetic selection record only', encoding='utf-8')
        (self.root / 'quality-report.md').write_text('Synthetic quality record only', encoding='utf-8')
        project.save(self.root / 'content-lock.json', project.snapshot(self.root))
        for v in self.data['volumes']:
            self.pdf_record(v, 2)
        project.save(self.root / 'book.json', self.data)

    def tearDown(self):
        self.fixture.tearDown()

    def pdf_record(self, volume, count):
        qa = volume['qa']
        inventory = self.fixture.read('inventory.json')
        expected, errors = book.expected_inputs_for_volume(self.root, self.data, volume, inventory)
        self.assertEqual(errors, [])
        # Synthetic FLS input graph mirrors the chapter files included by this volume.
        trace_inputs = set(expected)
        for item in inventory['items']:
            if item['disposition'] not in {'covered', 'compressed'}:
                continue
            item_chapters = {chapter['id'] for chapter in self.data['chapters']
                             if set(chapter['units']) & set(item['units'])}
            if item_chapters & set(volume['chapter_ids']):
                trace_inputs.update(ref['file'] for ref in item.get('output_refs', []))
        install_synthetic_receipt(self.root, volume['id'], qa, volume['layout'], expected,
                                  pages=count, trace_inputs=sorted(trace_inputs))
        manifest_path, manifest = pdf_review.create_manifest(self.root, qa, volume['id'])
        qa.update(status='pass', page_count=manifest['page_count'], preview_manifest=manifest_path,
                  reviewed_pages=[])
        for page in manifest['pages']:
            qa['reviewed_pages'].append({'page': page['page'], 'preview': page['path'],
                                         'notes': 'Synthetic fixture observation for release-path testing'})
        qa['review_fingerprint'] = project.pdf_fingerprint(self.root, qa)

    def save(self):
        project.save(self.root / 'book.json', self.data)

    def test_two_complete_volumes_pass(self):
        self.assertEqual(book.check_book(self.root), [])
        self.assertEqual(project.main(['prepare-pdf-review', str(self.root)]), 2)
        self.assertEqual(project.main(['compile', str(self.root)]), 2)
        self.assertEqual(project.main(['check', str(self.root), '--stage', 'release']), 1)

    def test_chapter_and_answer_must_appear_in_its_volume_recorder(self):
        volume = self.data['volumes'][0]
        inventory = self.fixture.read('inventory.json')
        expected, errors = book.expected_inputs_for_volume(self.root, self.data, volume, inventory)
        self.assertEqual(errors, [])
        missing_chapter = [name for name in expected if name != 'content/chapters/ch01.tex']
        install_synthetic_receipt(self.root, volume['id'], volume['qa'], volume['layout'], expected,
                                  trace_inputs=missing_chapter)
        self.save()
        with self.assertRaisesRegex(ValueError, 'required authored input'):
            book.prepare_review(self.root, self.data)

    def test_inventory_output_ref_must_be_in_appropriate_volume_fls(self):
        volume = self.data['volumes'][0]
        inventory = self.fixture.read('inventory.json')
        expected, errors = book.expected_inputs_for_volume(self.root, self.data, volume, inventory)
        self.assertEqual(errors, [])
        install_synthetic_receipt(self.root, volume['id'], volume['qa'], volume['layout'], expected,
                                  trace_inputs=expected)
        self.save()
        with self.assertRaisesRegex(ValueError, 'output ref was not read'):
            book.prepare_review(self.root, self.data)

    def test_extra_volumes_without_user_request_rejected(self):
        self.data['volumes'] *= 3
        self.save()
        self.assertTrue(book.check_book(self.root))

    def test_single_volume_without_user_request_rejected(self):
        self.data['volumes'].pop()
        self.save()
        self.assertTrue(book.check_book(self.root))

    def test_requested_single_volume_passes_release_and_keeps_page_limit(self):
        self.data['volumes'] = self.data['volumes'][:1]
        volume = self.data['volumes'][0]
        volume['chapter_ids'] = ['ch01', 'ch02']
        self.data['volume_count_request'] = {'count': 1, 'evidence': 'Synthetic user request: one volume'}
        book.write_layouts(self.root, self.data)
        self.save()
        project.save(self.root / 'content-lock.json', project.snapshot(self.root))
        self.pdf_record(volume, 2)
        self.save()
        self.assertEqual(book.check_book(self.root), [])
        self.pdf_record(volume, 101)
        self.save()
        self.assertTrue(any('actual PDF page count' in e for e in book.check_book(self.root)))

    def test_requested_five_volumes_pass_plan_and_release(self):
        toc = project.load(self.root / 'toc.json')
        for n in range(3, 6):
            chapter = copy.deepcopy(self.data['chapters'][1])
            chapter.update(id=f'ch{n:02d}', title=f'Synthetic chapter {n}', toc_ids=[f'toc-{n:03d}'],
                           output=f'content/chapters/ch{n:02d}.tex', answers=f'content/answers/ch{n:02d}.tex')
            for key in ('output', 'answers'):
                (self.root / chapter[key]).write_text(f'Synthetic content {n}\n', encoding='utf-8')
            self.data['chapters'].append(chapter)
            toc_chapter = copy.deepcopy(toc['chapters'][1])
            toc_chapter.update(id=f'toc-{n:03d}', title=chapter['title'])
            toc['chapters'].append(toc_chapter)
            volume = copy.deepcopy(self.data['volumes'][1])
            volume.update(id=f'vol-{n:02d}', chapter_ids=[chapter['id']], layout=f'layout/vol-{n:02d}.tex')
            volume['qa'].update(path=f'build/vol-{n:02d}.pdf', log=f'build/vol-{n:02d}.log',
                                build_record=f'build/vol-{n:02d}.compile.txt',
                                recorder=f'build/vol-{n:02d}.compile.fls')
            self.data['volumes'].append(volume)
        project.save(self.root / 'toc.json', toc)
        self.assertTrue(any('Default volume count' in e for e in book.validate_plan(self.root, self.data)))
        self.data['volume_count_request'] = {'count': 5, 'evidence': 'Synthetic user request: five volumes'}
        book.write_layouts(self.root, self.data)
        self.save()
        self.assertEqual(book.validate_plan(self.root, self.data), [])
        project.save(self.root / 'content-lock.json', project.snapshot(self.root))
        for volume in self.data['volumes']:
            self.pdf_record(volume, 2)
        self.save()
        self.assertEqual(book.check_book(self.root), [])

    def test_requested_count_change_invalidates_lock(self):
        before = project.snapshot(self.root)
        self.data['volume_count_request'] = {'count': 2, 'evidence': 'Synthetic user request: exactly two volumes'}
        self.save()
        self.assertNotEqual(before, project.snapshot(self.root))
        self.assertTrue(book.check_book(self.root))

    def test_three_digit_volume_id_has_no_extra_preview_limit(self):
        volume = self.data['volumes'][1]
        volume.update(id='vol-100', layout='layout/vol-100.tex')
        volume['qa'].update(path='build/vol-100.pdf', log='build/vol-100.log',
                            build_record='build/vol-100.compile.txt', recorder='build/vol-100.compile.fls')
        book.write_layouts(self.root, self.data)
        self.save()
        self.assertEqual(book.validate_plan(self.root, self.data), [])
        project.save(self.root / 'content-lock.json', project.snapshot(self.root))
        for entry in self.data['volumes']:
            self.pdf_record(entry, 2)
        self.save()
        self.assertEqual(book.check_book(self.root), [])

    def test_init_requested_count_and_reject_invalid_before_creating_project(self):
        for count in (1, 5):
            fresh = self.fixture.base / f'requested-{count}'
            result = book.main(['init', '--pdf', str(self.fixture.pdf), '--out', str(fresh),
                                '--volumes', str(count), '--volume-count-request', f'Synthetic user: {count} volumes'])
            self.assertEqual(result, 0)
            plan = project.load(fresh / 'book.json')
            self.assertEqual(len(plan['volumes']), count)
            self.assertEqual(plan['volume_count_request']['count'], count)
        for count, evidence in ((5, None), (0, 'Synthetic invalid request'), (1, ' ')):
            fresh = self.fixture.base / f'invalid-{count}'
            with self.assertRaises(ValueError):
                book.init_book(argparse.Namespace(pdf=str(self.fixture.pdf), out=str(fresh),
                                                 volumes=count, volume_count_request=evidence))
            self.assertFalse(fresh.exists())

    def test_one_volume_over_100_even_when_total_under_400_fails(self):
        self.pdf_record(self.data['volumes'][0], 101)
        self.save()
        self.assertTrue(any('actual PDF page count' in e for e in book.check_book(self.root)))

    def test_100_actual_pages_accepted(self):
        self.pdf_record(self.data['volumes'][0], 100)
        self.save()
        self.assertEqual(book.check_book(self.root), [])

    def test_chapter_assignment_missing_fails(self):
        self.data['volumes'][1]['chapter_ids'] = []
        self.save()
        self.assertTrue(book.check_book(self.root))

    def test_chapter_assignment_duplicate_fails(self):
        self.data['volumes'][1]['chapter_ids'] = ['ch01', 'ch02']
        self.save()
        self.assertTrue(book.check_book(self.root))

    def test_book_plan_change_invalidates_lock(self):
        self.data['chapters'][0]['title'] = 'Changed chapter title'
        self.save()
        self.assertTrue(book.check_book(self.root))

    def test_book_plan_rejects_missing_toc_and_unmapped_chapter(self):
        toc_path = self.root / 'toc.json'
        original = toc_path.read_bytes()
        toc_path.unlink()
        self.assertTrue(any('TOC ledger' in error for error in book.validate_plan(self.root, self.data)))
        toc_path.write_bytes(original)
        self.data['chapters'][0]['toc_ids'] = []
        self.assertTrue(any('toc_ids' in error for error in book.validate_plan(self.root, self.data)))

    def test_book_chapter_units_must_equal_mapped_toc_units(self):
        self.data['chapters'][0]['units'] = ['u0001', 'u0002']
        errors = book.validate_plan(self.root, self.data)
        self.assertTrue(any('units must equal the union' in error for error in errors))

    def test_whole_book_source_units_cover_every_original_pdf_page(self):
        source = project.load(self.root / 'source.json')
        source['units'].pop()
        project.save(self.root / 'source.json', source)
        errors = project.validate_toc_plan(self.root, self.data)
        self.assertTrue(any('cover each physical PDF page' in error for error in errors))

    def test_source_units_need_chapter_coverage_or_evidenced_exclusion(self):
        toc = project.load(self.root / 'toc.json')
        toc['chapters'][1]['units'] = []
        project.save(self.root / 'toc.json', toc)
        self.data['chapters'][1]['units'] = []
        errors = project.validate_toc_plan(self.root, self.data)
        self.assertTrue(any('nonchapter exclusions' in error or 'source unit list' in error for error in errors))

        toc['chapters'] = toc['chapters'][:1]
        toc['exclusions'] = [{'units': ['u0002'], 'reason': 'Front matter outside chapter scope',
                              'evidence': [{'file': 'source/text/u0002.txt',
                                            'anchor': 'Synthetic source page 2'}]}]
        project.save(self.root / 'toc.json', toc)
        self.data['chapters'] = self.data['chapters'][:1]
        self.assertEqual(project.validate_toc_plan(self.root, self.data), [])

    def test_shared_chapter_boundary_unit_is_allowed(self):
        toc = project.load(self.root / 'toc.json')
        toc['chapters'][0]['units'].append('u0002')
        project.save(self.root / 'toc.json', toc)
        self.data['chapters'][0]['units'].append('u0002')
        self.assertEqual(project.validate_toc_plan(self.root, self.data), [])

    def test_toc_reference_files_are_part_of_the_content_lock_snapshot(self):
        toc = project.load(self.root / 'toc.json')
        toc['evidence'] = [{'file': 'source/text/u0001.txt', 'anchor': 'Synthetic source page 1'}]
        project.save(self.root / 'toc.json', toc)
        before = project.snapshot(self.root)
        evidence_path = self.root / 'source/text/u0001.txt'
        evidence_path.write_text(evidence_path.read_text(encoding='utf-8') + ' modified', encoding='utf-8')
        after = project.snapshot(self.root)
        self.assertNotEqual(before['toc_evidence'], after['toc_evidence'])

    def test_core_content_cannot_be_budget_omitted(self):
        inv = self.fixture.read('inventory.json')
        inv['items'][1].update(disposition='omitted', omission_basis='editorial_budget', reason='page limit')
        self.fixture.write('inventory.json', inv)
        self.assertTrue(project.run_checks(self.root, 'teaching'))

    def test_secondary_content_budget_omission_is_recordable(self):
        inv = self.fixture.read('inventory.json')
        inv['items'][1].update(priority='C', priority_reason='Duplicate demonstration',
                               disposition='omitted', omission_basis='editorial_budget', reason='Duplicate; page budget')
        self.fixture.write('inventory.json', inv)
        ledger = self.fixture.read('math-audit.json')
        ledger['entries'] = []
        self.fixture.write('math-audit.json', ledger)
        self.assertEqual(project.run_checks(self.root, 'teaching'), [])

    def test_compression_requires_reason_and_output(self):
        inv = self.fixture.read('inventory.json')
        inv['items'][0].update(disposition='compressed', reason='')
        self.fixture.write('inventory.json', inv)
        self.assertTrue(project.run_checks(self.root, 'teaching'))
        inv['items'][0]['reason'] = 'Merged repeated discussion'
        self.fixture.write('inventory.json', inv)
        self.assertEqual(project.run_checks(self.root, 'teaching'), [])

    def test_chapter_answers_follow_their_chapter_in_layout(self):
        text = (self.root / 'layout/vol-01.tex').read_text(encoding='utf-8')
        self.assertLess(text.index('content/chapters/ch01.tex'), text.index('content/answers/ch01.tex'))
        self.assertNotIn('content/answers/ch02.tex', text)

    def test_failed_rebuild_invalidates_old_pdf_review(self):
        fake = type('Result', (), {'returncode': 1, 'stdout': b'compile failed', 'stderr': b''})()
        with patch.object(book, 'find_xelatex', return_value='fake-xelatex'), patch.object(latex_build.subprocess, 'run', return_value=fake):
            with self.assertRaises(ValueError):
                book.compile_volumes(self.root, self.data)
        saved = project.load(self.root / 'book.json')['volumes'][0]['qa']
        self.assertEqual(saved['status'], 'pending')
        self.assertNotIn('review_fingerprint', saved)
        self.assertTrue(book.check_book(self.root))

    def test_new_review_invalidates_all_old_visual_claims(self):
        book.prepare_review(self.root, self.data)
        saved = project.load(self.root / 'book.json')
        for v in saved['volumes']:
            self.assertEqual(v['qa']['status'], 'pending')
            self.assertEqual(v['qa']['reviewed_pages'], [])
            self.assertTrue((self.root / v['qa']['preview_manifest']).is_file())
        self.assertTrue(book.check_book(self.root))

    def test_prepare_review_generates_receipt_bound_real_png_manifest(self):
        book.prepare_review(self.root, self.data)
        saved = project.load(self.root / 'book.json')
        for volume in saved['volumes']:
            qa = volume['qa']
            manifest = project.load(self.root / qa['preview_manifest'])
            self.assertEqual(manifest['pdf_sha256'], project.digest(self.root / qa['path']))
            self.assertEqual(manifest['build_record_sha256'], project.digest(self.root / qa['build_record']))
            self.assertEqual(manifest['page_count'], qa['page_count'])
            for page in manifest['pages']:
                png = self.root / page['path']
                self.assertEqual(png.read_bytes()[:8], pdf_review.PNG_SIGNATURE)
                self.assertEqual(project.digest(png), page['sha256'])
            self.assertEqual(qa['reviewed_pages'], [])

    def test_release_rejects_swapped_preview_page_mapping(self):
        qa = self.data['volumes'][0]['qa']
        first = qa['reviewed_pages'][0]['preview']
        second = qa['reviewed_pages'][1]['preview']
        qa['reviewed_pages'][0]['preview'] = second
        self.save()
        errors = book.check_book(self.root)
        self.assertTrue(any('different preview than its manifest' in error for error in errors))
        qa['reviewed_pages'][0]['preview'] = first

    def test_release_rejects_replaced_preview_png(self):
        qa = self.data['volumes'][0]['qa']
        first = self.root / qa['reviewed_pages'][0]['preview']
        second = self.root / qa['reviewed_pages'][1]['preview']
        first.write_bytes(second.read_bytes())
        errors = book.check_book(self.root)
        self.assertTrue(any('PNG SHA-256 changed' in error for error in errors))

    def test_full_book_intake_only_returns_statistics(self):
        fresh = self.fixture.base / 'new-book'
        result = book.init_book(argparse.Namespace(pdf=str(self.fixture.pdf), out=str(fresh), volumes=2))
        self.assertEqual(result['source_units'], 2)
        toc = project.load(fresh / 'toc.json')
        self.assertEqual(toc['status'], 'pending')
        self.assertEqual(toc['source_sha256'], project.load(fresh / 'source.json')['sha256'])
        self.assertNotIn('Synthetic source page', str(result))
        self.assertTrue(all(u['text_review'] == 'pending' for u in project.load(fresh / 'coverage.json')['units']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
