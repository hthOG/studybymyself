"""Independent P1 regressions for real compile receipts and input tracking.

Every fixture is synthetic. The installed XeLaTeX checks verify tool behavior,
not a genuine book's content or visual quality.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
SKILL = REPO / "skills" / "textbook-to-zh-tw-notes"
SCRIPTS = SKILL / "scripts"
TESTS = SKILL / "tests"
for path in (str(SCRIPTS), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import book
import latex_build
import project
import test_project as fixtures

ARTIFACTS = REPO / "work" / "p1-independent"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
_configured_engine = os.environ.get("STUDYBYMYSELF_TEST_XELATEX")
_discovered_engine = _configured_engine or book.find_xelatex()
XELATEX = Path(_discovered_engine).resolve() if _discovered_engine else None


@contextlib.contextmanager
def quiet_stdout():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


class IndependentP1Acceptance(unittest.TestCase):
    def fixture(self):
        value = fixtures.HandoffTests("test_extraction_is_not_reading")
        value.setUp()
        self.addCleanup(value.tearDown)
        return value

    def assert_path_under_artifacts(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(ARTIFACTS.resolve()):
            raise AssertionError(f"test artifact escaped work/p1-independent: {resolved}")
        return resolved

    def create_real_single_project(self, root: Path):
        root = self.assert_path_under_artifacts(root)
        source = self.assert_path_under_artifacts(root.parent / (root.name + " source.pdf"))
        fixtures.synthetic_pdf(source, pages=2)
        project.init_project(argparse.Namespace(pdf=str(source), pages="1-2", out=str(root)))
        value = fixtures.HandoffTests("test_extraction_is_not_reading")
        value.root, value.pdf = root, source
        value.ready_teaching()
        return value

    def add_real_single_inputs(self, fixture):
        root = fixture.root
        (root / "content" / "nested").mkdir(parents=True, exist_ok=True)
        (root / "build" / "shared macros.tex").write_text(
            r"\newcommand{\BuildOnlyMarker}{\textbf{Authored build input}}" + "\n", encoding="utf-8")
        (root / "content" / "hidden-conditional.tex").write_text(
            r"\section{Skipped conditional output}\label{hidden-conditional}" + "\n", encoding="utf-8")
        (root / "content" / "hidden-commented.tex").write_text(
            r"\section{Skipped commented output}\label{hidden-commented}" + "\n", encoding="utf-8")
        (root / "content" / "nested" / "fragment.tex").write_text(
            r"\input{content/math/E1.tex}" + "\n"
            + r"\input{build/shared macros.tex}" + "\n"
            + r"\BuildOnlyMarker" + "\n", encoding="utf-8")
        (root / "content" / "chapter.tex").write_text(
            r"\section{Synthetic single chapter}\label{S1}" + "\n"
            + r"See the answer on page~\pageref{answer-one}." + "\n"
            + r"\input{content/nested/fragment.tex}" + "\n"
            + "% \\input{content/hidden-commented.tex}\n"
            + r"\iffalse" + "\n"
            + r"\input{content/hidden-conditional.tex}" + "\n"
            + r"\fi" + "\n", encoding="utf-8")
        (root / "content" / "answers.tex").write_text(
            r"\section*{Synthetic answer}\label{answer-one}" + "\nSynthetic answer." + "\n",
            encoding="utf-8")
        return {
            "nested": "content/nested/fragment.tex",
            "build": "build/shared macros.tex",
            "skipped": ("content/hidden-conditional.tex", "content/hidden-commented.tex"),
        }

    def test_legacy_pdf_and_plain_text_record_cannot_be_reblessed(self):
        fixture = self.fixture()
        fixture.ready_release()
        qa = fixture.read("qa.json")
        pdf_bytes = (fixture.root / qa["pdf"]["path"]).read_bytes()
        (fixture.root / qa["pdf"]["build_record"]).write_text(
            "Old successful compile record; no receipt", encoding="utf-8")

        with quiet_stdout():
            prepare_status = project.main(["prepare-pdf-review", str(fixture.root)])
        errors = project.run_checks(fixture.root, "release")

        self.assertNotEqual(prepare_status, 0)
        self.assertTrue(any("receipt" in error.lower() or "legacy" in error.lower() for error in errors), errors)
        self.assertEqual((fixture.root / qa["pdf"]["path"]).read_bytes(), pdf_bytes)

    def test_timeout_replaces_success_receipt_and_old_pdf_stays_unreleasable(self):
        fixture = self.fixture()
        fixture.ready_release()
        qa = fixture.read("qa.json")["pdf"]
        old_pdf = (fixture.root / qa["path"]).read_bytes()

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("xelatex", 300, output=b"timed out")

        with patch.object(project, "find_xelatex", return_value="fake-xelatex"), \
                patch.object(latex_build, "_system_roots", return_value=[]), \
                patch.object(latex_build.subprocess, "run", side_effect=timeout), quiet_stdout():
            status = project.main(["compile", str(fixture.root)])

        receipt = project.load(fixture.root / qa["build_record"])
        self.assertEqual(status, 2)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["passes"][0]["status"], "timeout")
        self.assertEqual((fixture.root / qa["path"]).read_bytes(), old_pdf)
        self.assertTrue(project.run_checks(fixture.root, "release"))

    def test_skipped_tex_cannot_satisfy_an_inventory_output_ref(self):
        fixture = self.fixture()
        fixture.ready_teaching()
        (fixture.root / "content" / "hidden.tex").write_text(
            r"\section{Hidden output}\label{E1}" + "\n", encoding="utf-8")
        chapter = fixture.root / "content" / "chapter.tex"
        chapter.write_text(chapter.read_text(encoding="utf-8") +
                           "% \\input{content/hidden.tex}\n"
                           + r"\iffalse" + "\n" + r"\input{content/hidden.tex}" + "\n" + r"\fi" + "\n",
                           encoding="utf-8")
        inventory = fixture.read("inventory.json")
        inventory["items"][1]["output_refs"] = [{"file": "content/hidden.tex", "anchor": r"\label{E1}"}]
        fixture.write("inventory.json", inventory)
        fixture.write("content-lock.json", project.snapshot(fixture.root))
        expected = project.standalone_expected_inputs(inventory)
        observed = sorted(name for name in expected if name != "content/hidden.tex")
        observed.append("content/math/E1.tex")
        fake, calls = fixtures.fake_xelatex(fixture.root, observed)

        with patch.object(project, "find_xelatex", return_value="fake-xelatex"), \
                patch.object(latex_build, "_system_roots", return_value=[]), \
                patch.object(latex_build.subprocess, "run", side_effect=fake), quiet_stdout():
            status = project.main(["compile", str(fixture.root)])

        receipt = project.load(fixture.root / "build" / "compile.txt")
        self.assertEqual(status, 2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("required authored input", receipt["failure"])
        self.assertTrue(project.run_checks(fixture.root, "release"))

    def test_fls_keeps_space_paths_and_normalizes_windows_separator_forms(self):
        root = self.assert_path_under_artifacts(ARTIFACTS / ("FLS path spaces " + uuid.uuid4().hex))
        first = root / "authored folder" / "chapter one.tex"
        second = root / "authored folder" / "nested" / "math.tex"
        staged_log = root / "build stage" / "main output.log"
        for path in (first, second, staged_log):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic path fixture", encoding="utf-8")
        first_windows = str(first.resolve()).replace("/", "\\")
        second_posix = str(second.resolve()).replace("\\", "/")
        output_windows = str(staged_log.resolve()).replace("/", "\\")
        fls = root / "recorder with spaces.fls"
        fls.write_text("\n".join(("PWD " + str(root.resolve()), "INPUT " + first_windows,
                                   "INPUT " + second_posix, "OUTPUT " + output_windows)) + "\n",
                       encoding="utf-8")

        parsed = latex_build.parse_fls(fls)

        self.assertEqual(set(parsed["inputs"]), {str(first.resolve()), str(second.resolve())})
        self.assertEqual(parsed["outputs"], [str(staged_log.resolve())])

    def test_whole_book_rejects_single_pdf_routes_and_redirected_build_outputs(self):
        fixture = self.fixture()
        fixture.ready_release()
        project.save(fixture.root / "book.json", {"schema_version": 1})
        with quiet_stdout():
            compile_status = project.main(["compile", str(fixture.root)])
            prepare_status = project.main(["prepare-pdf-review", str(fixture.root)])
            release_status = project.main(["check", str(fixture.root), "--stage", "release"])
        self.assertEqual(compile_status, 2)
        self.assertEqual(prepare_status, 2)
        self.assertEqual(release_status, 1)

        qa = fixture.read("qa.json")["pdf"]
        qa["path"] = "build/../../outside.pdf"
        with self.assertRaises(ValueError):
            latex_build.validate_destinations(fixture.root, "main", qa)
        self.assertFalse((fixture.root.parent / "outside.pdf").exists())

    def test_real_miktex_single_build_tracks_nested_and_build_authored_inputs(self):
        if XELATEX is None or not XELATEX.is_file():
            self.skipTest("installed MiKTeX XeLaTeX path is unavailable")
        root = ARTIFACTS / ("single XeLaTeX project with spaces " + uuid.uuid4().hex)
        fixture = self.create_real_single_project(root)
        names = self.add_real_single_inputs(fixture)
        fixture.write("content-lock.json", project.snapshot(root))

        with patch.object(project, "find_xelatex", return_value=str(XELATEX)), quiet_stdout():
            compile_status = project.main(["compile", str(root)])

        self.assertEqual(compile_status, 0)
        receipt_path = root / "build" / "compile.txt"
        receipt = project.load(receipt_path)
        inputs = receipt["final_inputs"]["project_inputs"]
        self.assertEqual(receipt["status"], "success")
        self.assertGreaterEqual(receipt["stable_passes"], 2)
        self.assertTrue(all(p["returncode"] == 0 for p in receipt["passes"]))
        self.assertIn(names["nested"], inputs)
        self.assertIn(names["build"], inputs)
        self.assertTrue(all(name not in inputs for name in names["skipped"]))
        self.assertIn(root / "build" / "main.pdf", [root / name for name in receipt["published_artifacts"]])
        self.assertIn(root / "build" / "main.log", [root / name for name in receipt["published_artifacts"]])
        self.assertIn(root / receipt["recorder"], [root / name for name in receipt["published_artifacts"]])
        self.assertEqual(latex_build.validate_receipt(
            root, project.load(root / "qa.json")["pdf"], project.standalone_expected_inputs(project.load(root / "inventory.json"))), [])

        authored = root / names["build"]
        original = authored.read_bytes()
        authored.write_bytes(original + b"% authored dependency changed\n")
        self.assertTrue(latex_build.validate_receipt(
            root, project.load(root / "qa.json")["pdf"], project.standalone_expected_inputs(project.load(root / "inventory.json"))))
        authored.write_bytes(original)
        self.assertEqual(latex_build.validate_receipt(
            root, project.load(root / "qa.json")["pdf"], project.standalone_expected_inputs(project.load(root / "inventory.json"))), [])
        (ARTIFACTS / "real-single-project.json").write_text(
            json.dumps({"root": str(root), "engine": str(XELATEX), "synthetic_fixture": True}, indent=2) + "\n",
            encoding="utf-8")

    def create_real_book(self, root: Path):
        root = self.assert_path_under_artifacts(root)
        source = self.assert_path_under_artifacts(root.parent / (root.name + " source.pdf"))
        fixtures.synthetic_pdf(source, pages=2)
        project.init_project(argparse.Namespace(pdf=str(source), pages="1-2", out=str(root)))
        fixture = fixtures.HandoffTests("test_extraction_is_not_reading")
        fixture.root, fixture.pdf = root, source
        fixture.ready_teaching()

        chapters = [
            {"id": "ch01", "title": "Synthetic volume one", "toc_ids": ["toc-001"], "units": ["u0001"],
             "treatment": "full", "priority_reason": "Synthetic smoke fixture",
             "output": "content/chapters/ch01.tex", "answers": "content/answers/ch01.tex"},
            {"id": "ch02", "title": "Synthetic volume two", "toc_ids": ["toc-002"], "units": ["u0002"],
             "treatment": "full", "priority_reason": "Synthetic smoke fixture",
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
        source_record = project.load(root / "source.json")
        toc_entries = []
        for n in (1, 2):
            unit = f"u{n:04d}"
            anchor = f"Synthetic source page {n}"
            toc_entries.append({"id": f"toc-{n:03d}", "title": f"Synthetic volume {n}",
                                "locator": f"chapter {n}", "units": [unit],
                                "evidence": [{"file": f"source/text/{unit}.txt", "anchor": anchor}]})
        project.save(root / "toc.json", {"schema_version": 1, "source_sha256": source_record["sha256"],
                                          "status": "verified",
                                          "evidence": [{"file": "source/text/u0001.txt",
                                                        "anchor": "Synthetic source page 1"}],
                                          "chapters": toc_entries, "exclusions": []})
        for n in (1, 2):
            chapter = root / f"content/chapters/ch{n:02d}.tex"
            answers = root / f"content/answers/ch{n:02d}.tex"
            chapter.parent.mkdir(parents=True, exist_ok=True)
            answers.parent.mkdir(parents=True, exist_ok=True)
            if n == 1:
                chapter.write_text(
                    r"\section{Volume one}\label{S1}" + "\n"
                    + r"The answer is on page~\pageref{answer-one}." + "\n"
                    + r"\input{content/math/E1.tex}" + "\n"
                    + r"\input{content/nested/volume-one-fragment.tex}" + "\n", encoding="utf-8")
            else:
                chapter.write_text(
                    r"\section{Volume two}\label{S2}" + "\n"
                    + r"The answer is on page~\pageref{answer-two}." + "\n", encoding="utf-8")
            answers.write_text(
                rf"\section*{{Synthetic answer {n}}}\label{{answer-{('one' if n == 1 else 'two')}}}" + "\n"
                + f"Synthetic answer {n}.\n", encoding="utf-8")
        (root / "content" / "nested").mkdir(parents=True, exist_ok=True)
        (root / "content" / "nested" / "volume-one-fragment.tex").write_text(
            r"\input{build/book-shared.tex}" + "\n" + r"\BookSharedMarker" + "\n", encoding="utf-8")
        (root / "build" / "book-shared.tex").write_text(
            r"\newcommand{\BookSharedMarker}{\textbf{Merged inventory output owner: volume one}}" + "\n",
            encoding="utf-8")
        book.write_layouts(root, data)

        inventory = fixture.read("inventory.json")
        for item in inventory["items"]:
            item.update(priority="A", priority_reason="Synthetic smoke fixture")
        inventory["items"][0].update(units=["u0001"], output_refs=[{"file": "content/chapters/ch01.tex", "anchor": r"\label{S1}"}])
        inventory["items"][1].update(units=["u0001", "u0002"], output_refs=[{"file": "content/math/E1.tex", "anchor": r"\label{E1}"}])
        fixture.write("inventory.json", inventory)
        (root / "selection-log.md").write_text("Synthetic selection record; not real book content.\n", encoding="utf-8")
        (root / "quality-report.md").write_text("Synthetic smoke only; no semantic or visual acceptance.\n", encoding="utf-8")
        project.save(root / "book.json", data)
        project.save(root / "content-lock.json", project.snapshot(root))
        return fixture, data, inventory

    def test_real_miktex_two_volume_book_converges_and_tracks_assigned_files(self):
        if XELATEX is None or not XELATEX.is_file():
            self.skipTest("installed MiKTeX XeLaTeX path is unavailable")
        root = ARTIFACTS / ("two volume XeLaTeX book with spaces " + uuid.uuid4().hex)
        fixture, data, inventory = self.create_real_book(root)

        # A clean, independent first pass must see the forward reference unresolved.
        stage = root / "build" / "manual-first-pass"
        stage.mkdir(parents=True, exist_ok=True)
        manual_command = [str(XELATEX)]
        if any(part.casefold() == "miktex" for part in XELATEX.parts):
            manual_command.append("-disable-installer")
        manual_command += ["-no-shell-escape", "-interaction=nonstopmode",
                          "-halt-on-error", "-file-line-error", "-recorder", "-output-directory=" + str(stage),
                          "-jobname=firstpass", "layout/vol-01.tex"]
        manual = subprocess.run(manual_command, cwd=root, capture_output=True, timeout=300, check=False)
        self.assertEqual(manual.returncode, 0, manual.stderr.decode("utf-8", errors="replace")[-4000:])
        first_log = (stage / "firstpass.log").read_text(encoding="utf-8", errors="replace")
        self.assertRegex(first_log, r"Reference [`']answer-one['`] .* undefined")

        with patch.object(book, "find_xelatex", return_value=str(XELATEX)), quiet_stdout():
            compile_status = book.main(["compile", str(root)])
        self.assertEqual(compile_status, 0)

        records = [project.load(root / volume["qa"]["build_record"]) for volume in data["volumes"]]
        for record in records:
            self.assertEqual(record["status"], "success")
            self.assertGreaterEqual(record["stable_passes"], 2)
            self.assertTrue(all(p["status"] == "finished" and p["returncode"] == 0 for p in record["passes"]))
            self.assertNotRegex((root / record["layout"]).read_text(encoding="utf-8"), r"\\iffalse")
        first_log_final = (root / data["volumes"][0]["qa"]["log"]).read_text(encoding="utf-8", errors="replace")
        self.assertNotRegex(first_log_final, r"Reference [`']answer-one['`] .* undefined|There were undefined references")

        vol_one_inputs = records[0]["final_inputs"]["project_inputs"]
        vol_two_inputs = records[1]["final_inputs"]["project_inputs"]
        self.assertTrue({"layout/vol-01.tex", "content/chapters/ch01.tex", "content/answers/ch01.tex",
                         "content/math/E1.tex", "content/nested/volume-one-fragment.tex",
                         "build/book-shared.tex"}.issubset(vol_one_inputs))
        self.assertTrue({"layout/vol-02.tex", "content/chapters/ch02.tex", "content/answers/ch02.tex"}.issubset(vol_two_inputs))
        self.assertNotIn("content/chapters/ch01.tex", vol_two_inputs)
        self.assertNotIn("content/answers/ch01.tex", vol_two_inputs)
        # The E1 inventory item spans both chapters but one intersecting volume owns its actual output.
        self.assertIn("content/math/E1.tex", vol_one_inputs)
        self.assertNotIn("content/math/E1.tex", vol_two_inputs)
        self.assertEqual(book.validate_book_output_inputs(root, data, inventory), [])

        with patch.object(book, "find_xelatex", return_value=str(XELATEX)), quiet_stdout():
            prepare_status = book.main(["prepare-review", str(root)])
        self.assertEqual(prepare_status, 0)
        for volume in data["volumes"]:
            qa = project.load(root / "book.json")["volumes"]
            current = next(v["qa"] for v in qa if v["id"] == volume["id"])
            expected, errors = book.expected_inputs_for_volume(root, data, volume, inventory)
            self.assertEqual(errors, [])
            self.assertEqual(latex_build.validate_receipt(root, current, expected), [])

        authored = root / "build" / "book-shared.tex"
        original = authored.read_bytes()
        authored.write_bytes(original + b"% changed after real compile\n")
        volume_qa = project.load(root / "book.json")["volumes"][0]["qa"]
        expected, _ = book.expected_inputs_for_volume(root, data, data["volumes"][0], inventory)
        self.assertTrue(latex_build.validate_receipt(root, volume_qa, expected))
        authored.write_bytes(original)
        self.assertEqual(latex_build.validate_receipt(root, volume_qa, expected), [])
        (ARTIFACTS / "real-book-project.json").write_text(
            json.dumps({"root": str(root), "engine": str(XELATEX), "synthetic_fixture": True}, indent=2) + "\n",
            encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
