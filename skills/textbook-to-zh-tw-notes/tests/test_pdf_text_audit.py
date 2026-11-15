"""Observable PDF text findings; these are not formula or visual tests."""
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
import shutil

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pdf_text_audit


class PDFTextAuditTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.gettempdir()) / ("pdf-text-audit-" + uuid.uuid4().hex)
        self.root.mkdir()

    def tearDown(self):
        if self.root.parent == Path(tempfile.gettempdir()) and self.root.name.startswith("pdf-text-audit-"):
            shutil.rmtree(self.root)

    def make_pdf(self, text):
        target = self.root / "fixture.pdf"
        with fitz.open() as document:
            page = document.new_page()
            if text:
                page.insert_text((40, 50), text, fontname="china-t")
            document.save(target)
        return target

    def test_internal_note_detected_on_actual_pdf(self):
        found = pdf_text_audit.inspect(self.make_pdf("候選訂正 待主代理核定 此處放原圖"))
        self.assertTrue(any(f["kind"] == "unapproved_correction" and f["page"] == 1 for f in found))
        self.assertTrue(any(f["kind"] == "placeholder" for f in found))

    def test_blank_pdf_is_not_clean_text_evidence(self):
        self.assertEqual(pdf_text_audit.inspect(self.make_pdf(""))[0]["kind"], "no_text")

    def test_normal_content_has_no_internal_markers(self):
        self.assertEqual(pdf_text_audit.inspect(self.make_pdf("座標時間與固有時的關係")), [])


if __name__ == "__main__":
    unittest.main()
