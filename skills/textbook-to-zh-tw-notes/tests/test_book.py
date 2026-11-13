"""Synthetic book fixtures exercise page budgets and multi-volume record integrity."""
import argparse
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import book
import test_project as fixture_module

PNG = fixture_module.PNG
project = fixture_module.project
synthetic_pdf = fixture_module.synthetic_pdf


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
                (p / f'ch{n:02d}.tex').write_text(f'Synthetic {folder} {n}', encoding='utf-8')
        chapters = [{'id': f'ch{n:02d}', 'title': f'Synthetic chapter {n}', 'units': [f'u{n:04d}'],
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
        project.save(self.root / 'book.json', self.data)
        book.write_layouts(self.root, self.data)
        inventory = self.fixture.read('inventory.json')
        for item in inventory['items']:
            item.update(priority='A', priority_reason='Synthetic core content')
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
        synthetic_pdf(self.root / qa['path'], pages=count)
        (self.root / qa['log']).write_text('Synthetic clean log, no real TeX compilation', encoding='utf-8')
        (self.root / qa['build_record']).write_text('Synthetic command record', encoding='utf-8')
        qa.update(status='pass', page_count=count, reviewed_pages=[])
        for n in range(1, count + 1):
            name = f'build/{volume["id"]}-page-{n:03d}.png'
            (self.root / name).write_bytes(PNG)
            qa['reviewed_pages'].append({'page': n, 'preview': name, 'notes': 'Synthetic observation only'})
        qa['review_fingerprint'] = project.pdf_fingerprint(self.root, qa)

    def save(self):
        project.save(self.root / 'book.json', self.data)

    def test_two_complete_volumes_pass(self):
        self.assertEqual(book.check_book(self.root), [])

    def test_fifth_volume_rejected(self):
        self.data['volumes'] *= 3
        self.save()
        self.assertTrue(book.check_book(self.root))

    def test_single_volume_rejected(self):
        self.data['volumes'].pop()
        self.save()
        self.assertTrue(book.check_book(self.root))

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
        fake = type('Result', (), {'returncode': 1, 'stdout': b'compile failed'})()
        with patch.object(book, 'find_xelatex', return_value='fake-xelatex'), patch.object(book.subprocess, 'run', return_value=fake):
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
        self.assertTrue(book.check_book(self.root))

    def test_full_book_intake_only_returns_statistics(self):
        fresh = self.fixture.base / 'new-book'
        result = book.init_book(argparse.Namespace(pdf=str(self.fixture.pdf), out=str(fresh), volumes=2))
        self.assertEqual(result['source_units'], 2)
        self.assertNotIn('Synthetic source page', str(result))
        self.assertTrue(all(u['text_review'] == 'pending' for u in project.load(fresh / 'coverage.json')['units']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
