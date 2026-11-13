"""Task reuse must fail closed when reviewed inputs/evidence change."""
from pathlib import Path
import sys
import unittest

import test_project as fixtures
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reuse


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.HandoffTests('test_extraction_is_not_reading')
        self.fixture.setUp()
        self.fixture.ready_source()
        self.root = self.fixture.root
        self.folder = self.root / 'tasks/read-01'
        self.folder.mkdir(parents=True)
        self.evidence = self.folder / 'evidence.md'
        self.evidence.write_text('Synthetic test evidence only', encoding='utf-8')
        source = self.fixture.read('source.json')
        fixtures.project.save(self.folder / 'handoff.json',
                              {'task_id':'read-01', 'status':'ready', 'issues':[], 'source_sha256':source['sha256'], 'unit_ids':['u0001']})
        self.draft = self.root / 'content/draft.tex'
        self.draft.write_text('Synthetic draft', encoding='utf-8')

    def tearDown(self):
        self.fixture.tearDown()

    def seal(self, kind='reading', inputs=None):
        return reuse.seal(self.root, 'read-01', kind, ['u0001'], inputs or [], ['tasks/read-01/evidence.md'])

    def test_unchanged_task_can_be_reused_without_updating_coverage(self):
        before = (self.root / 'coverage.json').read_bytes()
        self.seal()
        self.assertTrue(reuse.check(self.root, 'read-01')['reuse_candidate'])
        self.assertEqual(before, (self.root / 'coverage.json').read_bytes())

    def test_unrelated_unit_change_preserves_task_receipt(self):
        self.seal()
        (self.root / 'source/text/u0002.txt').write_text('Changed other unit', encoding='utf-8')
        self.assertTrue(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_changed_scoped_text_invalidates(self):
        self.seal()
        (self.root / 'source/text/u0001.txt').write_text('Changed unit', encoding='utf-8')
        self.assertFalse(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_changed_scoped_preview_invalidates(self):
        self.seal()
        (self.root / 'source/previews/u0001.png').write_bytes(b'changed')
        self.assertFalse(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_changed_evidence_invalidates(self):
        self.seal()
        self.evidence.write_text('Changed evidence', encoding='utf-8')
        self.assertFalse(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_verification_requires_draft_dependencies(self):
        with self.assertRaises(ValueError):
            self.seal('verification')

    def test_changed_verified_draft_invalidates(self):
        self.seal('verification', ['content/draft.tex'])
        self.draft.write_text('Different equation', encoding='utf-8')
        self.assertFalse(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_changed_original_invalidates(self):
        self.seal()
        self.fixture.pdf.write_bytes(b'changed source')
        self.assertFalse(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_missing_receipt_not_reusable(self):
        self.assertFalse(reuse.check(self.root, 'read-01')['reuse_candidate'])

    def test_incomplete_handoff_cannot_be_sealed(self):
        handoff = fixtures.project.load(self.folder / 'handoff.json')
        handoff['status'] = 'needs_followup'
        fixtures.project.save(self.folder / 'handoff.json', handoff)
        with self.assertRaises(ValueError): self.seal()

    def test_receipt_cannot_be_silently_overwritten(self):
        self.seal()
        with self.assertRaises(ValueError): self.seal()

    def test_outputs_cannot_escape_task_directory(self):
        with self.assertRaises(ValueError):
            reuse.seal(self.root, 'read-01', 'reading', ['u0001'], [], ['content/draft.tex'])
