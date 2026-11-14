"""Synthetic fixtures validate record integrity, never physics or visual quality."""
import argparse
import base64
import contextlib
import hashlib
import json
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import uuid
import unittest
from unittest.mock import patch
import subprocess

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/project.py"
sys.path.insert(0, str(SCRIPT.parent))
import project
import latex_build
import pdf_review
import render
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


def install_synthetic_receipt(root, target_id, qa, layout_name, expected_inputs, pages=2, trace_inputs=None):
    """Create explicitly synthetic artifacts in the same receipt/FLS shape as compile_target."""
    root = root.resolve()
    latex_build.validate_destinations(root, target_id, qa)
    stage = root / "build" / (".synthetic-" + target_id)
    stage.mkdir(parents=True, exist_ok=True)
    pdf_path = project.local(root, qa["path"])
    log_path = project.local(root, qa["log"])
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    synthetic_pdf(pdf_path, pages=pages)
    log_content = "Synthetic fixture log; no real TeX compilation\nOutput written on " + target_id + ".pdf\n"
    log_path.write_text(log_content, encoding="utf-8")
    recorder_name = latex_build.recorder_name(qa)
    recorder_path = project.local(root, recorder_name)
    input_names = sorted(set(trace_inputs if trace_inputs is not None else expected_inputs))
    output_names = [str((stage / (target_id + suffix)).resolve()) for suffix in (".pdf", ".log")]
    shutil.copyfile(pdf_path, stage / (target_id + ".pdf"))
    shutil.copyfile(log_path, stage / (target_id + ".log"))
    fls_lines = ["PWD " + str(root)]
    fls_lines.extend("INPUT " + name for name in input_names)
    fls_lines.extend("OUTPUT " + name for name in output_names)
    recorder_path.write_text("\n".join(fls_lines) + "\n", encoding="utf-8")
    trace = latex_build.parse_fls(recorder_path)
    # This fixture intentionally records relative project INPUT paths and absolute staging OUTPUT paths.
    actual_inputs = {}
    for raw in trace["inputs"]:
        path = Path(raw).resolve()
        if path.is_relative_to(root):
            actual_inputs[path.relative_to(root).as_posix()] = project.digest(path)
        else:
            raise ValueError("synthetic receipts only use project-local authored inputs")
    actual_pages = len(__import__("pypdf").PdfReader(str(pdf_path)).pages)
    lock_path = root / "content-lock.json"
    snapshot = project.snapshot(root)
    snapshot_hash = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode("utf-8")).hexdigest()
    record = {
        "schema": latex_build.SCHEMA, "status": "success", "target_id": target_id,
        "started_at_utc": "2026-01-01T00:00:00+00:00", "completed_at_utc": "2026-01-01T00:00:02+00:00",
        "command_engine": "xelatex", "layout": layout_name,
        "layout_sha256": project.digest(project.local(root, layout_name)),
        "content_lock_sha256": project.digest(lock_path), "snapshot_sha256": snapshot_hash,
        "expected_inputs": sorted(set(expected_inputs)), "max_pages": 100,
        "staging_dir": stage.relative_to(root).as_posix(), "system_roots": [],
        "passes": [{"pass": n, "status": "finished", "returncode": 0,
                    "stdout": "Synthetic fixture only", "stderr": ""} for n in (1, 2)],
        "stable_passes": 2, "page_count": actual_pages, "recorder": recorder_name,
        "command": ["xelatex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
                    "-file-line-error", "-recorder", "-output-directory=" + str(stage),
                    "-jobname=" + target_id, Path(layout_name).as_posix()],
        "final_inputs": {"project_inputs": dict(sorted(actual_inputs.items())), "system_inputs": {}},
        "final_trace": {"pwd": trace["pwd"], "inputs": trace["inputs"], "outputs": trace["outputs"],
                        "relative_inputs": trace["relative_inputs"]},
        "generated_outputs": trace["outputs"], "final_trace_sha256": project.digest(recorder_path),
        "published_artifacts": {qa["path"]: project.digest(pdf_path), qa["log"]: project.digest(log_path),
                                recorder_name: project.digest(recorder_path)},
        "pdf_sha256": project.digest(pdf_path), "log_sha256": project.digest(log_path),
    }
    project.save(project.local(root, qa["build_record"]), record)
    qa["recorder"] = recorder_name
    return record


def fake_xelatex(root, input_names, no_output_after_first=False):
    calls = []

    def run(command, cwd, capture_output, timeout):
        calls.append(command)
        attempt = len(calls)
        stage = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("-output-directory=")))
        jobname = next(arg.split("=", 1)[1] for arg in command if arg.startswith("-jobname="))
        if no_output_after_first and attempt > 1:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        stage.mkdir(parents=True, exist_ok=True)
        synthetic_pdf(stage / (jobname + ".pdf"), pages=2)
        log = ("LaTeX Warning: Reference `future' undefined. Rerun to get cross-references right.\n"
               if attempt == 1 else "Synthetic clean final log\n")
        log += "Output written on " + jobname + ".pdf\n"
        (stage / (jobname + ".log")).write_text(log, encoding="utf-8")
        (stage / (jobname + ".aux")).write_text("Synthetic stable auxiliary\n", encoding="utf-8")
        outputs = [str((stage / (jobname + suffix)).resolve()) for suffix in (".pdf", ".log", ".aux")]
        lines = ["PWD " + str(Path(cwd).resolve())]
        lines.extend("INPUT " + name for name in sorted(set(input_names)))
        lines.extend("OUTPUT " + name for name in outputs)
        (stage / (jobname + ".fls")).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    return run, calls


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.test_root = (Path(tempfile.gettempdir()) / ("studybymyself-skill-tests-" + uuid.uuid4().hex)).resolve()
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
        temp_root = Path(tempfile.gettempdir()).resolve()
        if (self.test_root.parent == temp_root
                and self.test_root.name.startswith("studybymyself-skill-tests-")):
            self.test_root.rmdir()

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
        qa = self.read("qa.json")
        pdf = qa["pdf"]
        inventory = self.read("inventory.json")
        install_synthetic_receipt(self.root, "main", pdf, "layout/main.tex",
                                  project.standalone_expected_inputs(inventory))
        manifest_path, manifest = pdf_review.create_manifest(self.root, pdf, "main")
        pdf.update(status="pass", page_count=manifest["page_count"], preview_manifest=manifest_path,
                   reviewed_pages=[])
        for item in manifest["pages"]:
            pdf["reviewed_pages"].append({"page": item["page"], "preview": item["path"],
                                          "notes": "Synthetic fixture observation for release-path testing"})
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

    def test_compile_writes_receipt_and_accepts_first_pass_reference_warning(self):
        self.ready_teaching()
        self.write("content-lock.json", project.snapshot(self.root))
        inputs = project.standalone_expected_inputs(self.read("inventory.json"))
        fake, calls = fake_xelatex(self.root, inputs)
        with patch.object(project, "find_xelatex", return_value="fake-xelatex"), \
                patch.object(latex_build, "_system_roots", return_value=[]), \
                patch.object(latex_build.subprocess, "run", side_effect=fake):
            self.assertEqual(project.main(["compile", str(self.root)]), 0)
        self.assertEqual(len(calls), 2)
        receipt_before = (self.root / "build/compile.txt").read_bytes()
        record = project.load(self.root / "build/compile.txt")
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["stable_passes"], 2)
        self.assertEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)
        self.assertEqual((self.root / "build/compile.txt").read_bytes(), receipt_before)

    def test_later_zero_exit_without_fresh_outputs_fails_closed(self):
        self.ready_teaching()
        self.write("content-lock.json", project.snapshot(self.root))
        inputs = project.standalone_expected_inputs(self.read("inventory.json"))
        fake, calls = fake_xelatex(self.root, inputs, no_output_after_first=True)
        with patch.object(project, "find_xelatex", return_value="fake-xelatex"), \
                patch.object(latex_build, "_system_roots", return_value=[]), \
                patch.object(latex_build.subprocess, "run", side_effect=fake):
            self.assertEqual(project.main(["compile", str(self.root)]), 2)
        self.assertEqual(len(calls), 2)
        record = project.load(self.root / "build/compile.txt")
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["passes"][-1]["returncode"], 0)
        self.assertTrue(project.main(["prepare-pdf-review", str(self.root)]) != 0)

    def test_timeout_replaces_old_success_and_cannot_be_reblessed(self):
        self.ready_release()
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("fake-xelatex", 300, output=b"timed out")
        with patch.object(project, "find_xelatex", return_value="fake-xelatex"), \
                patch.object(latex_build, "_system_roots", return_value=[]), \
                patch.object(latex_build.subprocess, "run", side_effect=timeout):
            self.assertEqual(project.main(["compile", str(self.root)]), 2)
        record = project.load(self.root / "build/compile.txt")
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["passes"][0]["status"], "timeout")
        self.assertNotEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)

    def test_prepare_cannot_rebless_changed_layout_or_dependent_math(self):
        for index, changed in enumerate(("layout/main.tex", "content/math/E1.tex")):
            with self.subTest(changed=changed):
                self.ready_release()
                path = self.root / changed
                path.write_text(path.read_text(encoding="utf-8") + "\n% changed after compile\n", encoding="utf-8")
                self.assertNotEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)
                self.assertTrue(self.errors("release"))
                if index == 0:
                    self.tearDown()
                    self.setUp()

    def test_missing_or_legacy_receipt_is_not_auto_upgraded(self):
        self.ready_release()
        qa = self.read("qa.json")
        fls = self.root / qa["pdf"]["recorder"]
        fls.write_text(fls.read_text(encoding="utf-8") + "UNKNOWN stale record\n", encoding="utf-8")
        self.assertNotEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)
        inventory = self.read("inventory.json")
        install_synthetic_receipt(self.root, "main", qa["pdf"], "layout/main.tex",
                                  project.standalone_expected_inputs(inventory))
        self.write("qa.json", qa)
        (self.root / "build/compile.txt").write_text("Synthetic old plain-text record", encoding="utf-8")
        self.assertNotEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)
        self.assertTrue(self.errors("release"))

    def test_missing_receipt_is_not_auto_upgraded(self):
        self.ready_release()
        (self.root / "build/compile.txt").unlink()
        self.assertNotEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)

    def test_nested_and_build_directory_inputs_are_recorded_and_revalidated(self):
        self.ready_teaching()
        nested = self.root / "content/sections/nested.tex"
        nested.parent.mkdir(parents=True)
        nested.write_text("\\input{build/author-supplement.tex}\n", encoding="utf-8")
        author = self.root / "build/author-supplement.tex"
        author.write_text("\\input{content/math/E1.tex}\n", encoding="utf-8")
        (self.root / "content/chapter.tex").write_text(
            "\\section{Synthetic}\\label{S1}\n\\input{content/sections/nested.tex}\n", encoding="utf-8")
        self.write("content-lock.json", project.snapshot(self.root))
        inputs = project.standalone_expected_inputs(self.read("inventory.json"))
        inputs.extend(["content/sections/nested.tex", "build/author-supplement.tex"])
        fake, _ = fake_xelatex(self.root, inputs)
        with patch.object(project, "find_xelatex", return_value="fake-xelatex"), \
                patch.object(latex_build, "_system_roots", return_value=[]), \
                patch.object(latex_build.subprocess, "run", side_effect=fake):
            self.assertEqual(project.main(["compile", str(self.root)]), 0)
        record = self.read("build/compile.txt")
        self.assertIn("content/sections/nested.tex", record["final_inputs"]["project_inputs"])
        self.assertIn("build/author-supplement.tex", record["final_inputs"]["project_inputs"])
        author.write_text("Changed after compile", encoding="utf-8")
        errors = latex_build.validate_receipt(self.root, self.read("qa.json")["pdf"], inputs)
        self.assertTrue(any("input manifest changed" in error for error in errors))

    def test_output_ref_not_in_actual_recorder_inputs_fails_prepare(self):
        self.ready_release()
        qa = self.read("qa.json")
        inventory = self.read("inventory.json")
        expected = project.standalone_expected_inputs(inventory)
        trace_inputs = [name for name in expected if name != "content/math/E1.tex"]
        install_synthetic_receipt(self.root, "main", qa["pdf"], "layout/main.tex", expected,
                                  trace_inputs=trace_inputs)
        self.write("qa.json", qa)
        self.assertNotEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)

    def test_fls_parser_preserves_spaces_and_rejects_escape_or_malformed_trace(self):
        spaced = self.root / "content/with spaces.tex"
        spaced.write_text("Synthetic TeX input", encoding="utf-8")
        trace_path = self.root / "build/spaces.fls"
        trace_path.write_text("PWD " + str(self.root) + "\nINPUT content/with spaces.tex\nOUTPUT build/output.pdf\n",
                              encoding="utf-8")
        parsed = latex_build.parse_fls(trace_path)
        self.assertIn(str(spaced.resolve()), parsed["inputs"])
        trace_path.write_text("PWD " + str(self.root) + "\nINPUT ../outside.tex\nOUTPUT build/output.pdf\n",
                              encoding="utf-8")
        parsed = latex_build.parse_fls(trace_path)
        with self.assertRaisesRegex(ValueError, "escapes"):
            latex_build._manifest(self.root, parsed, self.root / "build/staging", set(parsed["outputs"]), [])
        trace_path.write_text("BROKEN record\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unknown recorder"):
            latex_build.parse_fls(trace_path)

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
        self.assertTrue((self.root / pdf["preview_manifest"]).is_file())
        self.assertEqual(pdf_review.validate_manifest(self.root, pdf), [])
        self.assertTrue(self.errors("release"))

    def test_legacy_standalone_snapshot_without_toc_evidence_can_prepare(self):
        self.ready_release()
        lock = self.read("content-lock.json")
        self.assertNotIn("toc_evidence", lock)
        self.assertEqual(lock, project.snapshot(self.root))
        pdf = self.read("qa.json")["pdf"]
        receipt_before = project.digest(self.root / pdf["build_record"])
        self.assertEqual(latex_build.validate_receipt(
            self.root, pdf, project.standalone_expected_inputs(self.read("inventory.json"))), [])

        self.assertEqual(project.main(["prepare-pdf-review", str(self.root)]), 0)
        prepared = self.read("qa.json")["pdf"]
        self.assertTrue((self.root / prepared["preview_manifest"]).is_file())
        self.assertEqual(pdf_review.validate_manifest(self.root, prepared), [])
        self.assertEqual(project.digest(self.root / prepared["build_record"]), receipt_before)

    def test_ordinary_pdf_render_is_draft_and_does_not_create_qa_manifest(self):
        draft_pdf = self.base / "draft.pdf"
        output = self.base / "draft-previews"
        synthetic_pdf(draft_pdf, pages=2)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = render.main(["pdf", str(draft_pdf), "--out", str(output)])
        self.assertEqual(status, 0)
        record = json.loads(stream.getvalue())
        self.assertEqual(record["review_status"], "not_reviewed")
        self.assertEqual(record["formal_manifest"], None)
        self.assertTrue(all((output / f"page-{n:03d}.png").is_file() for n in (1, 2)))
        self.assertFalse(list(output.rglob("manifest.json")))

    def test_draft_pdf_render_refuses_symlinked_page_output(self):
        draft_pdf = self.base / "draft-symlink.pdf"
        output = self.base / "draft-symlink-previews"
        output.mkdir()
        synthetic_pdf(draft_pdf, pages=1)
        sentinel = self.base / "must-remain.txt"
        sentinel.write_text("unchanged", encoding="utf-8")
        page_path = output / "page-001.png"
        try:
            os.symlink(str(sentinel), str(page_path))
            mock_used = False
        except (OSError, NotImplementedError):
            # Exercise the exact guard on hosts where Windows symlink privilege is unavailable.
            path_type = type(page_path)
            original = path_type.is_symlink

            def report_target_as_symlink(path):
                return path == page_path or original(path)

            with patch.object(path_type, "is_symlink", report_target_as_symlink):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    status = render.main(["pdf", str(draft_pdf), "--out", str(output)])
            mock_used = True
        else:
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = render.main(["pdf", str(draft_pdf), "--out", str(output)])
        self.assertEqual(status, 2, "mock fallback used: " + str(mock_used))
        self.assertIn("symlinked draft preview", json.loads(stream.getvalue())["error"])
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main(verbosity=2)
