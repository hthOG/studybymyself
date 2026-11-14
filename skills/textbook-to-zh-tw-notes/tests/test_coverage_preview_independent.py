"""Independent integration coverage for whole-book reconciliation and PDF QA binding.

All book content, source pages, page notes, and compile receipts here are synthetic.
The tests verify mechanical integrity; they do not claim semantic or visual review.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

import pymupdf as fitz

REPO = Path(__file__).resolve().parents[3]
SKILL = REPO / "skills" / "textbook-to-zh-tw-notes"
SCRIPTS = SKILL / "scripts"
TESTS = SKILL / "tests"
for path in (str(SCRIPTS), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import book
import latex_build
import pdf_review
import project
import render
import test_project as fixtures

ARTIFACTS = REPO / "work" / "coverage-preview-independent"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class CoveragePreviewIndependent(unittest.TestCase):
    def _new_root(self, kind: str) -> Path:
        suffix = uuid.uuid4().hex[:8]
        # Keep paths short for Windows while retaining one path-with-spaces fixture.
        name = f"{kind}-{suffix}" if kind == "s" else f"{kind}-{suffix} with space"
        root = ARTIFACTS / name
        if root.exists():
            raise AssertionError(f"unexpected artifact path collision: {root}")
        return root

    def _new_project(self, kind: str, pages: int):
        fixture = fixtures.HandoffTests("test_extraction_is_not_reading")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)

        root = self._new_root(kind)
        source = root.parent / (root.name + " source.pdf")
        fixtures.synthetic_pdf(source, pages=pages)
        project.init_project(argparse.Namespace(pdf=str(source), pages=f"1-{pages}", out=str(root)))
        fixture.root, fixture.pdf = root, source
        fixture.ready_teaching()
        return fixture

    def _make_single(self):
        fixture = self._new_project("s", 2)
        root = fixture.root
        (root / "quality-report.md").write_text(
            "Synthetic test fixture only; semantic and visual acceptance remain unreviewed.\n",
            encoding="utf-8")
        # This is also the compatibility shape of a valid pre-TOC standalone lock.
        snapshot = project.snapshot(root)
        self.assertNotIn("toc_evidence", snapshot)
        project.save(root / "content-lock.json", snapshot)
        qa = fixture.read("qa.json")
        pdf = qa["pdf"]
        expected = project.standalone_expected_inputs(fixture.read("inventory.json"))
        fixtures.install_synthetic_receipt(root, "main", pdf, "layout/main.tex", expected, pages=2)
        return fixture

    def _prepare_single(self, fixture):
        root = fixture.root
        with contextlib.redirect_stdout(io.StringIO()):
            status = project.main(["prepare-pdf-review", str(root)])
        self.assertEqual(status, 0)
        qa = fixture.read("qa.json")
        pdf = qa["pdf"]
        self.assertEqual(pdf["status"], "pending")
        self.assertEqual(pdf["reviewed_pages"], [])
        self.assertEqual(pdf_review.validate_manifest(root, pdf), [])
        manifest = project.load(root / pdf["preview_manifest"])
        for page in manifest["pages"]:
            pdf["reviewed_pages"].append({
                "page": page["page"],
                "preview": page["path"],
                "notes": f"Synthetic fixture observation for page {page['page']}; no content QA claim.",
            })
        pdf["status"] = "pass"
        pdf["review_fingerprint"] = project.pdf_fingerprint(root, pdf)
        fixture.write("qa.json", qa)
        return manifest

    def _make_book(self):
        fixture = self._new_project("b", 4)
        root = fixture.root
        chapters = [
            {"id": "ch01", "title": "Synthetic chapter one", "toc_ids": ["toc-001"],
             "units": ["u0001", "u0002"], "treatment": "full",
             "priority_reason": "Synthetic integration fixture",
             "output": "content/chapters/ch01.tex", "answers": "content/answers/ch01.tex"},
            {"id": "ch02", "title": "Synthetic chapter two", "toc_ids": ["toc-002"],
             "units": ["u0002", "u0003"], "treatment": "full",
             "priority_reason": "Synthetic integration fixture",
             "output": "content/chapters/ch02.tex", "answers": "content/answers/ch02.tex"},
        ]
        volumes = [
            {"id": f"vol-{n:02d}", "chapter_ids": [f"ch{n:02d}"], "planned_pages": 85,
             "layout": f"layout/vol-{n:02d}.tex",
             "qa": {"status": "pending", "path": f"build/vol-{n:02d}.pdf",
                    "log": f"build/vol-{n:02d}.log", "build_record": f"build/vol-{n:02d}.compile.txt",
                    "page_count": 0, "reviewed_pages": [], "issues": []}}
            for n in (1, 2)
        ]
        data = {"schema_version": 1, "chapters_complete": True, "title": "Synthetic acceptance book",
                "chapters": chapters, "volumes": volumes}
        source = fixture.read("source.json")
        toc = {
            "schema_version": 1,
            "source_sha256": source["sha256"],
            "status": "verified",
            "evidence": [{"file": "source/text/u0001.txt", "anchor": "Synthetic source page 1"}],
            "chapters": [
                {"id": "toc-001", "title": "Source chapter one", "locator": "Chapter 1",
                 "units": ["u0001", "u0002"],
                 "evidence": [{"file": "source/text/u0001.txt", "anchor": "Synthetic source page 1"}]},
                {"id": "toc-002", "title": "Source chapter two", "locator": "Chapter 2",
                 "units": ["u0002", "u0003"],
                 "evidence": [{"file": "source/text/u0003.txt", "anchor": "Synthetic source page 3"}]},
            ],
            "exclusions": [{"units": ["u0004"], "reason": "Synthetic front matter outside chapter scope",
                            "evidence": [{"file": "source/text/u0004.txt",
                                          "anchor": "Synthetic source page 4"}]}],
        }
        project.save(root / "toc.json", toc)

        chapters_dir = root / "content" / "chapters"
        answers_dir = root / "content" / "answers"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        answers_dir.mkdir(parents=True, exist_ok=True)
        (chapters_dir / "ch01.tex").write_text(
            r"\section{Synthetic chapter one}\label{S1}" + "\n" + r"\input{content/math/E1.tex}" + "\n",
            encoding="utf-8")
        (chapters_dir / "ch02.tex").write_text(
            r"\section{Synthetic chapter two}\label{S2}" + "\n", encoding="utf-8")
        for n in (1, 2):
            (answers_dir / f"ch{n:02d}.tex").write_text(
                f"\\section*{{Synthetic answer {n}}}\nSynthetic answer {n}.\n", encoding="utf-8")

        inventory = fixture.read("inventory.json")
        for item in inventory["items"]:
            item.update(priority="A", priority_reason="Synthetic integration fixture")
        inventory["items"][0].update(
            units=["u0001", "u0002"],
            output_refs=[{"file": "content/chapters/ch01.tex", "anchor": r"\label{S1}"}],
        )
        inventory["items"][1].update(
            units=["u0001"],
            output_refs=[{"file": "content/math/E1.tex", "anchor": r"\label{E1}"}],
        )
        fixture.write("inventory.json", inventory)

        project.save(root / "book.json", data)
        book.write_layouts(root, data)
        (root / "selection-log.md").write_text(
            "Synthetic selection record; this fixture does not claim source reading.\n", encoding="utf-8")
        (root / "quality-report.md").write_text(
            "Synthetic integration fixture only; semantic and visual QA are not claimed.\n", encoding="utf-8")
        project.save(root / "content-lock.json", project.snapshot(root))

        for volume in data["volumes"]:
            expected, errors = book.expected_inputs_for_volume(root, data, volume, inventory)
            self.assertEqual(errors, [])
            trace_inputs = set(expected)
            assigned = set(volume["chapter_ids"])
            for item in inventory["items"]:
                if item["disposition"] not in {"covered", "compressed"}:
                    continue
                item_chapters = {chapter["id"] for chapter in chapters
                                 if set(chapter["units"]) & set(item["units"])}
                if item_chapters & assigned:
                    trace_inputs.update(ref["file"] for ref in item.get("output_refs", []))
            fixtures.install_synthetic_receipt(
                root, volume["id"], volume["qa"], volume["layout"], expected,
                pages=2, trace_inputs=sorted(trace_inputs))
        return fixture, data

    def _prepare_book(self, fixture, data):
        root = fixture.root
        book.prepare_review(root, data)
        saved = project.load(root / "book.json")
        for volume in saved["volumes"]:
            qa = volume["qa"]
            manifest = project.load(root / qa["preview_manifest"])
            qa["status"] = "pass"
            qa["reviewed_pages"] = [
                {"page": page["page"], "preview": page["path"],
                 "notes": f"Synthetic fixture observation for {volume['id']} page {page['page']}; no content QA claim."}
                for page in manifest["pages"]
            ]
            qa["review_fingerprint"] = project.pdf_fingerprint(root, qa)
        project.save(root / "book.json", saved)
        return saved

    def test_toc_physical_page_coverage_allows_shared_boundary_and_evidenced_exclusion(self):
        fixture, data = self._make_book()
        root = fixture.root
        self.assertEqual(project.validate_toc_plan(root, data), [])
        self.assertEqual(book.validate_plan(root, data), [])
        source = fixture.read("source.json")
        self.assertEqual([unit["pdf_page"] for unit in source["units"]], [1, 2, 3, 4])
        toc = project.load(root / "toc.json")
        self.assertEqual(toc["source_sha256"], source["sha256"])
        self.assertIn("u0002", toc["chapters"][0]["units"])
        self.assertIn("u0002", toc["chapters"][1]["units"])
        self.assertEqual(toc["exclusions"][0]["units"], ["u0004"])
        locked = project.load(root / "content-lock.json")
        self.assertEqual(locked["evidence"]["toc.json"], project.digest(root / "toc.json"))
        self.assertTrue(locked["toc_evidence"])

    def test_toc_gate_rejects_missing_duplicate_unknown_and_unaccounted_units(self):
        fixture, data = self._make_book()
        root = fixture.root

        missing = copy.deepcopy(data)
        missing["chapters"] = missing["chapters"][:1]
        errors = project.validate_toc_plan(root, missing)
        self.assertTrue(any("toc-002: expected exactly one" in error for error in errors), errors)

        unknown_mapping = copy.deepcopy(data)
        unknown_mapping["chapters"][1]["toc_ids"] = ["unknown-toc"]
        errors = project.validate_toc_plan(root, unknown_mapping)
        self.assertTrue(any("unknown TOC chapter mapping" in error for error in errors), errors)

        duplicate_mapping = copy.deepcopy(data)
        duplicate_mapping["chapters"][1]["toc_ids"] = ["toc-001"]
        errors = project.validate_toc_plan(root, duplicate_mapping)
        self.assertTrue(any("toc-001: expected exactly one book.chapters mapping, found 2" in error
                            for error in errors), errors)

        wrong_units = copy.deepcopy(data)
        wrong_units["chapters"][1]["units"] = ["u0002"]
        errors = project.validate_toc_plan(root, wrong_units)
        self.assertTrue(any("units must equal the union" in error for error in errors), errors)

        toc_path = root / "toc.json"
        original_toc = project.load(toc_path)
        incomplete_toc = copy.deepcopy(original_toc)
        incomplete_toc["chapters"][1]["units"] = ["u0002"]
        project.save(toc_path, incomplete_toc)
        errors = project.validate_toc_plan(root, data)
        self.assertTrue(any("absent from TOC chapter coverage" in error for error in errors), errors)
        project.save(toc_path, original_toc)

        unknown_toc = copy.deepcopy(original_toc)
        unknown_toc["chapters"][0]["units"].append("u9999")
        project.save(toc_path, unknown_toc)
        errors = project.validate_toc_plan(root, data)
        self.assertTrue(any("unknown source units" in error for error in errors), errors)
        project.save(toc_path, original_toc)

        incomplete_book = copy.deepcopy(data)
        incomplete_book["chapters_complete"] = False
        errors = project.validate_toc_plan(root, incomplete_book)
        self.assertTrue(any("chapters_complete must be true" in error for error in errors), errors)

    def test_toc_and_cited_evidence_changes_invalidate_lock_and_receipt(self):
        fixture, data = self._make_book()
        root = fixture.root
        self.assertEqual(project.validate_toc_plan(root, data), [])
        volume = data["volumes"][0]
        expected, errors = book.expected_inputs_for_volume(root, data, volume, fixture.read("inventory.json"))
        self.assertEqual(errors, [])

        original = project.load(root / "toc.json")
        changed_toc = copy.deepcopy(original)
        changed_toc["chapters"][0]["title"] = "Corrected synthetic source title"
        project.save(root / "toc.json", changed_toc)
        self.assertNotEqual(project.snapshot(root), project.load(root / "content-lock.json"))
        receipt_errors = latex_build.validate_receipt(root, volume["qa"], expected)
        self.assertTrue(any("content/evidence differs" in error or "different reviewed content snapshot" in error
                            for error in receipt_errors), receipt_errors)

        project.save(root / "toc.json", original)
        evidence_path = root / "source/text/u0001.txt"
        evidence_path.write_text(evidence_path.read_text(encoding="utf-8") + " Supporting fixture evidence.\n",
                                 encoding="utf-8")
        changed_snapshot = project.snapshot(root)
        self.assertNotEqual(changed_snapshot["toc_evidence"], project.load(root / "content-lock.json")["toc_evidence"])
        receipt_errors = latex_build.validate_receipt(root, volume["qa"], expected)
        self.assertTrue(any("content/evidence differs" in error or "different reviewed content snapshot" in error
                            for error in receipt_errors), receipt_errors)
        with self.assertRaisesRegex(ValueError, "Content/evidence differs from lock"):
            book.prepare_review(root, data)

    def test_legacy_standalone_receipt_prepares_real_distinct_page_previews_and_releases(self):
        fixture = self._make_single()
        root = fixture.root
        manifest = self._prepare_single(fixture)
        qa = fixture.read("qa.json")["pdf"]

        self.assertEqual(manifest["pdf_sha256"], project.digest(root / qa["path"]))
        self.assertEqual(manifest["page_count"], 2)
        self.assertEqual(manifest["renderer"], "PyMuPDF")
        self.assertEqual(manifest["render_params"]["dpi"], pdf_review.DPI)
        self.assertEqual([page["page"] for page in manifest["pages"]], [1, 2])
        self.assertNotEqual(manifest["pages"][0]["sha256"], manifest["pages"][1]["sha256"])
        with fitz.open(str(root / qa["path"])) as document:
            self.assertIn("Synthetic source page 1", document[0].get_text())
            self.assertIn("Synthetic source page 2", document[1].get_text())
        preview_samples = [fitz.Pixmap(str(root / page["path"])).samples
                           for page in manifest["pages"]]
        self.assertNotEqual(preview_samples[0], preview_samples[1], "different PDF pages must render differently")
        self.assertEqual(pdf_review.validate_manifest(root, qa), [])
        self.assertEqual(project.run_checks(root, "release"), [])

    def test_two_volume_receipt_prepare_notes_manifest_and_release_flow(self):
        fixture, data = self._make_book()
        root = fixture.root
        self.assertEqual(project.validate_toc_plan(root, data), [])
        prepared = self._prepare_book(fixture, data)

        self.assertEqual(len(prepared["volumes"]), 2)
        for volume in prepared["volumes"]:
            qa = volume["qa"]
            self.assertEqual(qa["status"], "pass")
            self.assertEqual(qa["page_count"], 2)
            self.assertEqual(len(qa["reviewed_pages"]), 2)
            self.assertTrue(all("Synthetic fixture observation" in page["notes"]
                                for page in qa["reviewed_pages"]))
            self.assertEqual(pdf_review.validate_manifest(root, qa), [])
        self.assertEqual(book.check_book(root), [])

    def test_swapped_previews_page_mapping_and_manifest_drift_fail_release(self):
        fixture = self._make_single()
        root = fixture.root
        manifest = self._prepare_single(fixture)
        qa_record = fixture.read("qa.json")
        pdf = qa_record["pdf"]
        png_paths = [root / page["path"] for page in manifest["pages"]]
        original_bytes = [path.read_bytes() for path in png_paths]

        png_paths[0].write_bytes(original_bytes[1])
        png_paths[1].write_bytes(original_bytes[0])
        errors = pdf_review.validate_manifest(root, pdf)
        self.assertTrue(any("SHA-256 changed" in error for error in errors), errors)
        self.assertTrue(project.run_checks(root, "release"))
        for path, data in zip(png_paths, original_bytes):
            path.write_bytes(data)

        pdf["reviewed_pages"][0]["preview"], pdf["reviewed_pages"][1]["preview"] = (
            pdf["reviewed_pages"][1]["preview"], pdf["reviewed_pages"][0]["preview"])
        fixture.write("qa.json", qa_record)
        errors = pdf_review.validate_manifest(root, pdf)
        self.assertTrue(any("review points at a different preview" in error for error in errors), errors)
        self.assertTrue(project.run_checks(root, "release"))

        pdf["reviewed_pages"][0]["preview"], pdf["reviewed_pages"][1]["preview"] = (
            pdf["reviewed_pages"][1]["preview"], pdf["reviewed_pages"][0]["preview"])
        fixture.write("qa.json", qa_record)
        manifest_path = root / pdf["preview_manifest"]
        original_manifest = manifest_path.read_bytes()
        changed_manifest = project.load(manifest_path)
        changed_manifest["render_params"]["dpi"] += 1
        project.save(manifest_path, changed_manifest)
        errors = pdf_review.validate_manifest(root, pdf)
        self.assertTrue(any("render parameters are unsupported" in error for error in errors), errors)
        self.assertTrue(project.run_checks(root, "release"))
        manifest_path.write_bytes(original_manifest)
        self.assertEqual(project.run_checks(root, "release"), [])

    def test_pdf_replacement_and_failed_compile_attempt_invalidate_visual_qa(self):
        fixture = self._make_single()
        root = fixture.root
        self._prepare_single(fixture)
        pdf = fixture.read("qa.json")["pdf"]
        replacement = root.parent / (root.name + " replacement.pdf")
        fixtures.synthetic_pdf(replacement, pages=3)
        (root / pdf["path"]).write_bytes(replacement.read_bytes())
        errors = pdf_review.validate_manifest(root, pdf)
        self.assertTrue(any("do not match" in error for error in errors), errors)
        self.assertTrue(project.run_checks(root, "release"))

        # A separate valid run proves a new compile attempt clears existing review claims,
        # even when the attempted engine fails before publishing a replacement PDF.
        fixture = self._make_single()
        root = fixture.root
        self._prepare_single(fixture)
        with patch.object(project, "find_xelatex", return_value="synthetic-xelatex"), \
                patch.object(latex_build.subprocess, "run",
                             return_value=type("Failure", (), {"returncode": 1,
                                                               "stdout": b"synthetic failure",
                                                               "stderr": b""})()), \
                contextlib.redirect_stdout(io.StringIO()):
            status = project.main(["compile", str(root)])
        self.assertEqual(status, 2)
        qa = fixture.read("qa.json")["pdf"]
        self.assertEqual(qa["status"], "pending")
        self.assertNotIn("review_fingerprint", qa)
        self.assertTrue(project.run_checks(root, "release"))

    def test_ordinary_render_stays_draft_without_formal_qa_manifest(self):
        fixture = self._make_single()
        root = fixture.root
        draft = root / "build" / "draft-pages"
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = render.main(["pdf", str(fixture.pdf), "--out", str(draft)])
        self.assertEqual(status, 0)
        record = json.loads(output.getvalue())
        self.assertEqual(record["artifact_kind"], "draft_previews")
        self.assertEqual(record["formal_manifest"], None)
        self.assertEqual(record["review_status"], "not_reviewed")
        self.assertTrue((draft / "page-001.png").is_file())
        self.assertFalse(list(draft.rglob("manifest.json")))
        self.assertEqual(fixture.read("qa.json")["pdf"]["status"], "pending")


if __name__ == "__main__":
    unittest.main(verbosity=2)
