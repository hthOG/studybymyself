"""Synthetic portability and failure-path tests; no real textbook is published."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

import handoff
from pypdf import PdfWriter


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.gettempdir()) / ("muse-handoff-" + uuid.uuid4().hex)
        self.base.mkdir()
        self.original = self.base / "original.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with self.original.open("wb") as f:
            writer.write(f)
        self.src = self.base / "muse-project"
        self.pkg = self.base / "private-package"
        handoff.ledger.init_project(argparse.Namespace(pdf=str(self.original), out=str(self.src), pages="1"))
        source = handoff.load(self.src / "source.json")
        source.update(scope="Synthetic whole book", scope_verified=True)
        source["units"][0]["scope_note"] = "Synthetic complete page"
        handoff.save(self.src / "source.json", source)
        text = self.src / "source/text/u0001.txt"
        text.write_text("Synthetic section source", encoding="utf-8")
        preview = self.src / "source/previews/u0001.png"
        preview.parent.mkdir(exist_ok=True)
        preview.write_bytes(b"synthetic preview fixture; not evidence of visual reading")
        handoff.save(self.src / "coverage.json", {"units": [{"id": "u0001", "text_review": "done",
                     "visual_review": "done", "evidence": "Synthetic fixture only", "issues": []}]})
        handoff.save(self.src / "inventory.json", {"complete": True, "items": [{"id": "S1",
                     "category": "section", "units": ["u0001"], "locator": "Synthetic section",
                     "locator_verified": True, "disposition": "pending"}]})
        ref = {"file": "source/text/u0001.txt", "anchor": "Synthetic section source"}
        handoff.save(self.src / "toc.json", {"schema_version": 1, "source_sha256": source["sha256"],
                     "status": "verified", "evidence": [ref], "chapters": [{"id": "T1",
                     "title": "Synthetic", "locator": "Synthetic section", "units": ["u0001"],
                     "evidence": [ref]}], "exclusions": []})
        handoff.save(self.src / "book.json", {"chapters_complete": True, "chapters": [{"id": "ch01", "toc_ids": ["T1"],
                     "units": ["u0001"]}]})
        (self.src / "handoff-notes.md").write_text("Synthetic handoff only", encoding="utf-8")
        rows = {k: {"status": "provided", "files": ["source/text/u0001.txt"]} for k in handoff.CATEGORIES}
        handoff.save(self.src / "handoff-materials.json", {"user_request": "Synthetic explicit role split",
                     "scope": "Synthetic whole book", "reading_summary": "Synthetic fixture, no real review",
                     "completed_batches": ["synthetic-1"], "pending_batches": [], "materials": rows})
        (self.src / "content-lock.json").write_text('{"synthetic":true}', encoding="utf-8")
        handoff.save(self.src / "math-audit.json", {"synthetic_old_review": True})
        qa = handoff.load(self.src / "qa.json")
        qa["requirements"]["concepts"]["status"] = "pass"
        qa["semantic_review"]["status"] = "pass"
        qa["pdf"]["status"] = "pass"
        handoff.save(self.src / "qa.json", qa)
        (self.src / "logs").mkdir()
        (self.src / "logs/important.log").write_text("Retain audit logs", encoding="utf-8")
        (self.src / "custom-data").mkdir()
        (self.src / "custom-data/table.csv").write_text("x,y\n1,2\n", encoding="utf-8")
        self.before = {p.relative_to(self.src).as_posix(): handoff.sha(p) for p in handoff.files(self.src)}

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_complete_pack_contains_original_all_data_and_leaves_source_unchanged(self):
        manifest = handoff.pack(self.src, self.pkg)
        self.assertEqual(manifest["status"], "source_records_complete")
        self.assertEqual(handoff.sha(self.original), handoff.sha(self.pkg / "original/book.pdf"))
        for name, digest in self.before.items():
            if name != "source.json":
                self.assertEqual(handoff.sha(self.pkg / "project" / name), digest)
            self.assertEqual(handoff.sha(self.src / name), digest)
        self.assertTrue((self.pkg / "workflow/skills/textbook-to-zh-tw-notes/SKILL.md").is_file())
        self.assertEqual(handoff.check(self.pkg)["quality_acceptance"], "pending_codex_review")

    def test_moved_package_runs_its_own_tool_without_muse_source(self):
        handoff.pack(self.src, self.pkg)
        moved = self.base / "moved-package"
        self.pkg.rename(moved)
        shutil.rmtree(self.src)
        self.original.unlink()
        tool = moved / "workflow/workflows/muse-codex/handoff.py"
        work = self.base / "codex-work"
        # -S proves check/prepare need only Python's standard library, not site packages.
        result = subprocess.run([sys.executable, "-S", str(tool), "prepare", str(moved), "--out", str(work)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        project_root = work / "project"
        self.assertEqual(Path(handoff.load(project_root / "source.json")["path"]), work / "original/book.pdf")
        self.assertFalse((project_root / "content-lock.json").exists())
        self.assertTrue((project_root / "handoff-history/content-lock.before-codex.json").is_file())
        self.assertTrue((project_root / "handoff-history/math-audit.before-codex.json").is_file())
        self.assertFalse((project_root / "math-audit.json").exists())
        qa = handoff.load(project_root / "qa.json")
        self.assertEqual(qa["requirements"]["concepts"]["status"], "pending")
        self.assertEqual(qa["semantic_review"]["status"], "pending")
        self.assertEqual(qa["pdf"]["status"], "pending")
        self.assertEqual(handoff.load(project_root / "codex-acceptance.json")["status"], "pending")
        self.assertTrue((work / "workflow/setup.ps1").is_file())
        self.assertEqual(handoff.sha(work / "original/book.pdf"), handoff.sha(moved / "original/book.pdf"))
        handoff.check(moved)  # Preparing a new worktree did not mutate the frozen package.

    def test_changed_deleted_and_unlisted_files_rejected(self):
        handoff.pack(self.src, self.pkg)
        p = self.pkg / "project/custom-data/table.csv"
        saved = p.read_bytes()
        p.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Changed package"):
            handoff.check(self.pkg)
        p.unlink()
        with self.assertRaisesRegex(ValueError, "Missing or unlisted"):
            handoff.check(self.pkg)
        p.write_bytes(saved)
        (self.pkg / "extra.txt").write_text("unlisted", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Missing or unlisted"):
            handoff.check(self.pkg)

    def test_wrong_original_rejected_but_relocated_matching_original_accepted(self):
        wrong = self.base / "wrong.pdf"
        wrong.write_bytes(b"wrong original")
        with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
            handoff.pack(self.src, self.pkg, wrong)
        self.assertFalse(self.pkg.exists())
        s = handoff.load(self.src / "source.json")
        s["path"] = "/old-machine/missing.pdf"
        handoff.save(self.src / "source.json", s)
        handoff.pack(self.src, self.pkg, self.original)

    def test_incomplete_reading_requires_explicit_checkpoint(self):
        c = handoff.load(self.src / "coverage.json")
        c["units"][0]["visual_review"] = "pending"
        handoff.save(self.src / "coverage.json", c)
        with self.assertRaisesRegex(ValueError, "Source handoff incomplete"):
            handoff.pack(self.src, self.pkg)
        self.assertFalse(self.pkg.exists())
        m = handoff.pack(self.src, self.pkg, checkpoint=True)
        self.assertEqual(m["status"], "checkpoint")
        self.assertTrue(m["source_gate_errors"])
        self.assertEqual(handoff.check(self.pkg)["status"], "checkpoint")

    def test_missing_material_and_escaping_reference_rejected(self):
        p = self.src / "handoff-materials.json"
        m = handoff.load(p)
        for name in ("absent.png", "../original.pdf", "C:/outside.txt"):
            m["materials"]["figures_tables"]["files"] = [name]
            handoff.save(p, m)
            with self.assertRaises(ValueError):
                handoff.pack(self.src, self.pkg)
            self.assertFalse(self.pkg.exists())

    def test_nested_existing_outputs_rejected(self):
        for out in (self.src / "nested-package", handoff.REPO / "private-package", self.src):
            with self.assertRaises(ValueError):
                handoff.pack(self.src, out)
        handoff.pack(self.src, self.pkg)
        with self.assertRaises(ValueError):
            handoff.prepare(self.pkg, self.pkg / "work")

    def test_missing_original_or_preview_blocks_ready_export(self):
        (self.src / "source/previews/u0001.png").unlink()
        with self.assertRaisesRegex(ValueError, "Source handoff incomplete"):
            handoff.pack(self.src, self.pkg)
        self.original.unlink()
        with self.assertRaisesRegex(ValueError, "original PDF"):
            handoff.pack(self.src, self.pkg, checkpoint=True)


if __name__ == "__main__":
    unittest.main()
