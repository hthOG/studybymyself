"""Synthetic fixtures validate record integrity, never physics or visual quality."""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import shutil
import uuid
import unittest

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/project.py"
spec = importlib.util.spec_from_file_location("project", SCRIPT)
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=")


def synthetic_pdf(path, pages=2):
    writer = PdfWriter()
    for n in range(pages):
        page = writer.add_blank_page(width=300, height=400)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 300 Td (Synthetic source page {n+1}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as f:
        writer.write(f)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.test_root = (Path.cwd() / "work/skill-tests").resolve()
        self.test_root.mkdir(parents=True, exist_ok=True)
        # Default mkdir permissions also work with restricted Windows tokens.
        self.base = self.test_root / ("fixture-" + uuid.uuid4().hex)
        self.base.mkdir()
        self.pdf = self.base / "source.pdf"
        synthetic_pdf(self.pdf)
        self.root = self.base / "chapter"
        project.init_project(argparse.Namespace(pdf=str(self.pdf), pages="1-2", out=str(self.root)))

    def tearDown(self):
        if not self.base.resolve().is_relative_to(self.test_root):
            raise ValueError("test cleanup escaped intended workspace")
        shutil.rmtree(self.base)

    def read(self, name):
        return project.load(self.root / name)

    def write(self, name, value):
        project.save(self.root / name, value)

    def ready_source(self):
        source = self.read("source.json")
        source.update(scope="Synthetic chapter", scope_verified=True)
        for unit in source["units"]:
            unit.update(scope_note="whole page", section="1.1")
            (self.root / unit["preview_path"]).write_bytes(PNG)
        self.write("source.json", source)
        coverage = self.read("coverage.json")
        for record in coverage["units"]:
            record.update(text_review="done", visual_review="done",
                          evidence="Synthetic ledger fixture, not an actual reading claim")
        self.write("coverage.json", coverage)
        self.write("inventory.json", {"complete": True, "items": [
            {"id": "S1", "category": "section", "title": "synthetic section", "units": ["u0001", "u0002"],
             "locator": "section 1.1", "locator_verified": True, "disposition": "pending"},
            {"id": "E1", "category": "equation", "title": "synthetic formula", "units": ["u0001"],
             "locator": "equation 1", "locator_verified": True, "disposition": "pending"}]})

    def ready_teaching(self):
        self.ready_source()
        (self.root / "content/outline.md").write_text("Synthetic objective and exercise map", encoding="utf-8")
        (self.root / "content/chapter.tex").write_text(
            "\\section{Synthetic}\\label{S1}\n\\input{content/math/E1.tex}\n", encoding="utf-8")
        (self.root / "content/math/E1.tex").write_text(
            "\\begin{equation}F=ma\\label{E1}\\end{equation}\n", encoding="utf-8")
        (self.root / "content/answers.tex").write_text("Synthetic reference answer", encoding="utf-8")
        (self.root / "verification.md").write_text(
            "Synthetic integrity fixture only. E1 verified-reference anchor. semantic-review anchor.", encoding="utf-8")
        inventory = self.read("inventory.json")
        for item in inventory["items"]:
            item["disposition"] = "covered"
            item["output_refs"] = [{"file": "content/chapter.tex" if item["id"] == "S1" else "content/math/E1.tex",
                                    "anchor": "\\label{" + item["id"] + "}"}]
            item["verification_ref"] = {"file": "verification.md", "anchor": item["id"]}
        self.write("inventory.json", inventory)
        qa = self.read("qa.json")
        for record in list(qa["requirements"].values()) + [qa["semantic_review"]]:
            record.update(status="pass", evidence=[{"file": "verification.md", "anchor": "semantic-review"}])
        self.write("qa.json", qa)

    def ready_release(self):
        self.ready_teaching()
        self.write("content-lock.json", project.snapshot(self.root))
        synthetic_pdf(self.root / "build/main.pdf")
        (self.root / "build/main.log").write_text("Synthetic clean log; NOT an actual LaTeX compilation", encoding="utf-8")
        (self.root / "build/compile.txt").write_text("Synthetic build record for gate testing only", encoding="utf-8")
        qa = self.read("qa.json")
        pdf = qa["pdf"]
        pdf.update(status="pass", page_count=2, reviewed_pages=[])
        for page in (1, 2):
            name = f"build/page-{page}.png"
            (self.root / name).write_bytes(PNG)
            pdf["reviewed_pages"].append({"page": page, "preview": name, "notes": "Synthetic review fixture only"})
        pdf["review_fingerprint"] = project.pdf_fingerprint(self.root, pdf)
        self.write("qa.json", qa)
        (self.root / "quality-report.md").write_text("Synthetic test report only", encoding="utf-8")

    def errors(self, stage="source"):
        return project.run_checks(self.root, stage)

    def test_extraction_is_not_reading(self):
        self.assertEqual(self.read("coverage.json")["units"][0]["text_review"], "pending")
        self.assertIn("Synthetic source page 1", (self.root / "source/text/u0001.txt").read_text())
        self.assertEqual(project.digest(self.pdf), self.read("source.json")["sha256"])
        self.assertTrue(self.errors())

    def test_page_range_is_one_based(self):
        for value in ("0-1", "2-3", "2-1", "1,1", "1-2,2", "x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                project.parse_pages(value, 2)

    def test_init_does_not_overwrite(self):
        with self.assertRaises(ValueError):
            project.init_project(argparse.Namespace(pdf=str(self.pdf), pages="1", out=str(self.root)))

    def test_complete_source_records_pass(self):
        self.ready_source()
        self.assertEqual(self.errors(), [])

    def test_missing_page_record_fails(self):
        self.ready_source()
        coverage = self.read("coverage.json")
        coverage["units"].pop()
        self.write("coverage.json", coverage)
        self.assertTrue(self.errors())

    def test_unread_source_visual_fails(self):
        self.ready_source()
        coverage = self.read("coverage.json")
        coverage["units"][1]["visual_review"] = "pending"
        self.write("coverage.json", coverage)
        self.assertTrue(self.errors())

    def test_missing_source_preview_fails(self):
        self.ready_source()
        (self.root / "source/previews/u0002.png").unlink()
        self.assertTrue(self.errors())

    def test_changed_original_fails(self):
        self.ready_source()
        with self.pdf.open("ab") as f:
            f.write(b"\n% source changed\n")
        self.assertTrue(self.errors())

    def test_unverified_locator_fails(self):
        self.ready_source()
        inventory = self.read("inventory.json")
        inventory["items"][1]["locator_verified"] = False
        self.write("inventory.json", inventory)
        self.assertTrue(self.errors())

    def test_source_gate_does_not_imply_teaching(self):
        self.ready_source()
        self.assertEqual(self.errors(), [])
        self.assertTrue(self.errors("teaching"))

    def test_complete_teaching_records_pass(self):
        self.ready_teaching()
        self.assertEqual(self.errors("teaching"), [])

    def test_lock_command_refuses_to_overwrite_reviewed_baseline(self):
        self.ready_teaching()
        self.assertEqual(project.main(["lock", str(self.root)]), 0)
        baseline = (self.root / "content-lock.json").read_bytes()
        self.assertEqual(project.main(["lock", str(self.root)]), 2)
        self.assertEqual((self.root / "content-lock.json").read_bytes(), baseline)

    def test_formula_cannot_be_omitted_for_brevity(self):
        self.ready_teaching()
        inventory = self.read("inventory.json")
        inventory["items"][1].update(disposition="omitted", reason="shorter", omission_basis="decorative")
        self.write("inventory.json", inventory)
        self.assertTrue(self.errors("teaching"))

    def test_broken_output_anchor_fails(self):
        self.ready_teaching()
        inventory = self.read("inventory.json")
        inventory["items"][1]["output_refs"][0]["anchor"] = "nonexistent label"
        self.write("inventory.json", inventory)
        self.assertTrue(self.errors("teaching"))

    def test_missing_verification_fails(self):
        self.ready_teaching()
        inventory = self.read("inventory.json")
        del inventory["items"][1]["verification_ref"]
        self.write("inventory.json", inventory)
        self.assertTrue(self.errors("teaching"))

    def test_escaping_path_rejected(self):
        for name in ("../outside.txt", str(self.pdf), "C:/outside.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                project.local(self.root, name)

    def test_complete_release_records_pass(self):
        self.ready_release()
        self.assertEqual(self.errors("release"), [])

    def test_formula_change_after_lock_fails(self):
        self.ready_release()
        (self.root / "content/math/E1.tex").write_text("F=-ma", encoding="utf-8")
        self.assertTrue(self.errors("release"))

    def test_added_formula_after_lock_fails(self):
        self.ready_release()
        (self.root / "content/math/new.tex").write_text("x=1", encoding="utf-8")
        self.assertTrue(self.errors("release"))

    def test_source_asset_change_after_lock_fails(self):
        self.ready_release()
        (self.root / "source/text/u0001.txt").write_text("altered OCR", encoding="utf-8")
        self.assertTrue(self.errors("release"))

    def test_changed_teaching_review_invalidates_lock(self):
        self.ready_release()
        qa = self.read("qa.json")
        qa["semantic_review"]["evidence"][0]["anchor"] = "E1"
        self.write("qa.json", qa)
        self.assertTrue(self.errors("release"))

    def test_pdf_visual_review_must_cover_all_pages(self):
        self.ready_release()
        qa = self.read("qa.json")
        qa["pdf"]["reviewed_pages"].pop()
        self.write("qa.json", qa)
        self.assertTrue(self.errors("release"))

    def test_actual_pdf_page_count_is_checked(self):
        self.ready_release()
        qa = self.read("qa.json")
        qa["pdf"]["page_count"] = 1
        self.write("qa.json", qa)
        self.assertTrue(self.errors("release"))

    def test_pdf_replaced_after_review_fails(self):
        self.ready_release()
        synthetic_pdf(self.root / "build/main.pdf", pages=1)
        self.assertTrue(self.errors("release"))

    def test_layout_change_invalidates_pdf_review(self):
        self.ready_release()
        with (self.root / "layout/main.tex").open("a", encoding="utf-8") as f:
            f.write("\n% font changed\n")
        self.assertTrue(self.errors("release"))

    def test_latex_missing_glyph_is_a_release_error(self):
        self.ready_release()
        (self.root / "build/main.log").write_text("Missing character: glyph absent", encoding="utf-8")
        qa = self.read("qa.json")
        qa["pdf"]["review_fingerprint"] = project.pdf_fingerprint(self.root, qa["pdf"])
        self.write("qa.json", qa)
        self.assertTrue(self.errors("release"))

    def test_prepare_pdf_review_resets_old_visual_claims(self):
        self.ready_release()
        self.assertEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)
        pdf = self.read("qa.json")["pdf"]
        self.assertEqual(pdf["status"], "pending")
        self.assertEqual(pdf["reviewed_pages"], [])
        self.assertTrue(self.errors("release"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
