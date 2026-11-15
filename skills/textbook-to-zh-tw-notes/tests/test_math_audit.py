"""Behavioral tests for evidence integrity, not mathematical correctness."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import math_audit


class MathAuditTests(unittest.TestCase):
    def setUp(self):
        # Explicit mkdir preserves inherited permissions under restricted Windows tokens.
        self.temp_root = Path(tempfile.gettempdir()).resolve()
        self.root = self.temp_root / ("study-math-audit-" + uuid.uuid4().hex)
        self.root.mkdir()
        (self.root / "content").mkdir()
        (self.root / "content/eq.tex").write_text("equation and assumptions", encoding="utf-8")
        (self.root / "verification.md").write_text("conventions\nsource review\nindependent derivation\n", encoding="utf-8")
        self.source = {"sha256": "a" * 64}
        self.inventory = {"items": [{"id": "E1", "category": "equation", "disposition": "covered",
                                      "output_refs": [{"file": "content/eq.tex", "anchor": "equation"}]}]}
        vhash = math_audit.digest(self.root / "verification.md")
        fhash = math_audit.digest(self.root / "content/eq.tex")
        self.ref = lambda anchor: {"file": "verification.md", "anchor": anchor}
        self.ledger = {"schema_version": 1, "source_sha256": self.source["sha256"],
                       "conventions_ref": self.ref("conventions"), "entries": [{
                           "item_id": "E1", "author": "author-session", "reviewer": "reviewer-session",
                           "status": "pass", "issues": [], "reviewed_files": {"content/eq.tex": fhash},
                           "evidence_files": {"verification.md": vhash}, "checks": {
                               "source_visual": {"status": "pass", "evidence": [self.ref("source review")]},
                               "recompute": {"status": "pass", "evidence": [self.ref("independent derivation")]},
                               "dimension": {"status": "pass", "evidence": [self.ref("independent derivation")]},
                               "limit": {"status": "not_applicable", "reason": "no relevant limit"},
                               "domain": {"status": "pass", "evidence": [self.ref("independent derivation")]},
                           }}]}
        self.save()

    def tearDown(self):
        if self.root.resolve().parent != self.temp_root or not self.root.name.startswith("study-math-audit-"):
            raise ValueError("invalid test cleanup target")
        shutil.rmtree(self.root)

    def save(self):
        (self.root / "math-audit.json").write_text(json.dumps(self.ledger), encoding="utf-8")

    def errors(self):
        return math_audit.validate(self.root, self.source, self.inventory)

    def test_valid_records_and_changed_content_or_evidence(self):
        self.assertEqual(self.errors(), [])
        (self.root / "content/eq.tex").write_text("changed equation", encoding="utf-8")
        self.assertTrue(any("changed since review" in error for error in self.errors()))
        (self.root / "content/eq.tex").write_text("equation and assumptions", encoding="utf-8")
        (self.root / "verification.md").write_text("rewritten evidence", encoding="utf-8")
        self.assertTrue(any("changed since review" in error for error in self.errors()))

    def test_source_change_missing_unknown_and_duplicate(self):
        self.source["sha256"] = "b" * 64
        self.assertTrue(any("source sha256" in e for e in self.errors()))
        self.source["sha256"] = "a" * 64
        self.ledger["entries"] = []
        self.save()
        self.assertTrue(any("selected item missing" in e for e in self.errors()))
        unknown = copy.deepcopy(self.ledger)
        self.ledger["entries"] = [{"item_id": "unknown"}]
        self.save()
        self.assertTrue(any("unknown" in e for e in self.errors()))
        self.ledger = unknown
        self.ledger["entries"] = [{"item_id": "E1"}, {"item_id": "E1"}]
        self.save()
        self.assertTrue(any("duplicate" in e for e in self.errors()))

    def test_identity_unresolved_and_missing_source_review(self):
        row = self.ledger["entries"][0]
        row["reviewer"] = row["author"].upper()
        row["issues"] = ["unresolved"]
        row["checks"]["source_visual"] = {"status": "not_applicable", "reason": "no"}
        self.save()
        result = "\n".join(self.errors())
        self.assertIn("independent reviewer", result)
        self.assertIn("unresolved issues", result)
        self.assertIn("source_visual", result)

    def test_recompute_na_requires_explanation_and_conceptual_review(self):
        self.inventory["items"][0]["category"] = "exercise"
        checks = self.ledger["entries"][0]["checks"]
        checks["recompute"] = {"status": "not_applicable"}
        self.save()
        self.assertTrue(any("needs a reason" in e for e in self.errors()))
        self.assertTrue(any("conceptual" in e for e in self.errors()))
        checks["recompute"]["reason"] = "conceptual question with no calculation"
        checks["conceptual"] = {"status": "pass", "evidence": [self.ref("independent derivation")]}
        self.save()
        self.assertEqual(self.errors(), [])

    def test_equation_cannot_skip_recomputation(self):
        checks = self.ledger["entries"][0]["checks"]
        checks["recompute"] = {"status": "not_applicable", "reason": "conceptual"}
        checks["conceptual"] = {"status": "pass", "evidence": [self.ref("independent derivation")]}
        self.save()
        self.assertTrue(any("require recomputation" in e for e in self.errors()))

    def test_escape_missing_output_and_missing_anchor_are_rejected(self):
        row = self.ledger["entries"][0]
        row["reviewed_files"] = {"../eq.tex": "c" * 64}
        row["checks"]["source_visual"]["evidence"][0]["anchor"] = "missing"
        self.save()
        result = "\n".join(self.errors())
        self.assertIn("noncanonical", result)
        self.assertIn("output file not present", result)
        self.assertIn("anchor not found", result)

    def test_init_is_pending_and_does_not_overwrite(self):
        (self.root / "math-audit.json").unlink()
        math_audit.init(self.root, self.source, self.inventory)
        entry = json.loads((self.root / "math-audit.json").read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["reviewed_files"], {})
        self.assertTrue(self.errors())
        with self.assertRaises(FileExistsError):
            math_audit.init(self.root, self.source, self.inventory)

    def test_no_selected_math_allows_absent_ledger(self):
        (self.root / "math-audit.json").unlink()
        self.inventory["items"][0]["disposition"] = "omitted"
        self.assertEqual(self.errors(), [])
        math_audit.init(self.root, self.source, self.inventory)
        self.assertEqual(self.errors(), [])

    def test_snapshot_changes_when_ledger_changes(self):
        old = math_audit.snapshot_files(self.root)
        self.ledger["entries"][0]["status"] = "pending"
        self.save()
        self.assertNotEqual(old, math_audit.snapshot_files(self.root))

    def test_snapshot_changes_when_a_declared_evidence_dependency_changes(self):
        old = math_audit.snapshot_files(self.root)
        (self.root / "verification.md").write_text("changed evidence", encoding="utf-8")
        self.assertNotEqual(old, math_audit.snapshot_files(self.root))

    def test_malformed_nested_data_returns_errors(self):
        samples = [None, [], {"schema_version": 1, "entries": [None, [], {}, {"item_id": []}]},
                   {**self.ledger, "entries": [{**self.ledger["entries"][0],
                     "reviewed_files": [], "evidence_files": None, "checks": []}]},
                   {**self.ledger, "entries": [{**self.ledger["entries"][0],
                     "checks": {"source_visual": {"status": "pass", "evidence": [None]}}}]}]
        for sample in samples:
            with self.subTest(sample=sample):
                self.ledger = sample
                self.save()
                self.assertTrue(self.errors())
                self.assertIsInstance(math_audit.snapshot_files(self.root), dict)


if __name__ == "__main__":
    unittest.main()
