#!/usr/bin/env python3
"""Create a source ledger and check handoff records; not a semantic validator."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

import math_audit

REQUIREMENTS = (
    "concepts", "derivations", "deep_analysis", "examples", "figures_tables",
    "bilingual_terms", "review_exercises_answers",
)
CATEGORIES = {"section", "concept", "equation", "derivation", "example", "figure", "table", "exercise"}
VERIFIED_CATEGORIES = {"equation", "derivation", "example", "figure", "table", "exercise"}
EVIDENCE_FILES = ("source.json", "coverage.json", "inventory.json", "verification.md")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def local(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("empty project-relative path")
    if Path(relative).is_absolute() or re.match(r"^[A-Za-z]:", relative):
        raise ValueError("absolute project path: " + relative)
    p = (root / relative).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError("path escapes project: " + relative)
    return p


def nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def parse_pages(value: str, total: int) -> list[int]:
    pages = []
    for token in value.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:-(\d+))?\s*", token)
        if not match:
            raise ValueError("pages must be 1-based, e.g. 101-126 or 1,3-5")
        a, b = int(match[1]), int(match[2] or match[1])
        if a < 1 or b < a or b > total:
            raise ValueError(f"invalid range {a}-{b}; PDF has {total} pages")
        pages.extend(range(a, b + 1))
    if len(set(pages)) != len(pages):
        raise ValueError("duplicate page selection")
    return sorted(pages)


def init_project(args) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("init requires pypdf; use an available PDF reader or prepare ledgers manually") from exc
    original = Path(args.pdf).resolve()
    root = Path(args.out).resolve()
    if not original.is_file():
        raise ValueError("source PDF does not exist")
    if root.exists():
        raise ValueError("output already exists; choose a fresh chapter project directory")
    reader = PdfReader(str(original))
    if reader.is_encrypted:
        raise ValueError("encrypted PDF: provide a readable authorized copy")
    pages = parse_pages(args.pages, len(reader.pages))
    # Extract before creating files, so an extraction failure does not create a false ledger.
    texts = [reader.pages[n - 1].extract_text() or "" for n in pages]
    units, coverage = [], []
    for index, (page, text) in enumerate(zip(pages, texts), start=1):
        uid = f"u{index:04d}"
        path = f"source/text/{uid}.txt"
        local(root, path).parent.mkdir(parents=True, exist_ok=True)
        local(root, path).write_text(text, encoding="utf-8")
        units.append({"id": uid, "pdf_page": page, "printed_page": None, "anchor": None,
                      "section": "", "scope_note": "", "text_path": path,
                      "preview_path": f"source/previews/{uid}.png"})
        coverage.append({"id": uid, "text_review": "pending", "visual_review": "pending",
                         "evidence": "", "issues": []})
    metadata = reader.metadata
    save(root / "source.json", {"schema_version": 1, "source_id": "B1", "path": str(original),
         "sha256": digest(original), "kind": "pdf", "pdf_total_pages": len(reader.pages),
         "bibliography": {"title": str(metadata.title) if metadata and metadata.title else None,
                          "authors": None, "edition": None, "year": None},
         "scope": "", "scope_verified": False, "units": units})
    save(root / "coverage.json", {"units": coverage})
    save(root / "inventory.json", {"complete": False, "items": []})
    save(root / "progress.json", {"stage": "source", "next_section": "", "open_issues": []})
    save(root / "qa.json", {
        "requirements": {key: {"status": "pending", "evidence": []} for key in REQUIREMENTS},
        "semantic_review": {"status": "pending", "evidence": []},
        "pdf": {"status": "pending", "path": "build/main.pdf", "log": "build/main.log",
                "build_record": "build/compile.txt", "page_count": 0, "reviewed_pages": [], "issues": []},
        "unresolved": [],
    })
    for directory in ("content/math", "content/figures", "layout", "build", "source/previews"):
        local(root, directory).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "assets/main.tex", root / "layout/main.tex")
    return {"project": str(root), "source_units": len(units), "status": "extracted_only_not_read",
            "next": "render source pages; verify scope and page map; read all units; build inventory"}


class Audit:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def read(self, name: str):
        return load(local(self.root, name))

    def file(self, name: str) -> bool:
        p = local(self.root, name)
        if not nonempty(p):
            self.error("missing/empty file: " + name)
            return False
        return True

    def ref(self, ref, context: str, content_only=False) -> None:
        if not isinstance(ref, dict) or not ref.get("file") or not ref.get("anchor"):
            self.error(context + ": missing evidence file/anchor")
            return
        p = local(self.root, ref["file"])
        if content_only and not p.is_relative_to(self.root / "content"):
            self.error(context + ": output must point into content/")
        if self.file(ref["file"]):
            if not isinstance(ref["anchor"], str) or ref["anchor"] not in p.read_text(encoding="utf-8-sig"):
                self.error(context + ": anchor not found in " + ref["file"])

    def source(self):
        source, coverage, inventory = [self.read(n) for n in ("source.json", "coverage.json", "inventory.json")]
        if source.get("schema_version") != 1:
            self.error("unsupported source schema_version")
        p = Path(source.get("path", ""))
        if not p.is_file() or digest(p) != source.get("sha256"):
            self.error("source missing or SHA-256 changed; invalidate dependent reviews")
        if source.get("scope_verified") is not True or not source.get("scope", "").strip():
            self.error("chapter scope not verified")
        units = source.get("units", [])
        ids = [u["id"] for u in units]
        if not ids or len(ids) != len(set(ids)):
            self.error("source unit IDs empty or duplicated")
        kind = source.get("kind")
        if kind not in {"pdf", "epub"}:
            self.error("source kind must be pdf or epub")
        locators = []
        for u in units:
            if kind == "pdf":
                n = u.get("pdf_page")
                if type(n) is not int or n < 1 or n > source.get("pdf_total_pages", 10**9):
                    self.error(u["id"] + ": invalid 1-based PDF page")
                locators.append(n)
            else:
                if u.get("pdf_page") is not None or not u.get("anchor"):
                    self.error(u["id"] + ": EPUB needs anchor and no fabricated PDF page")
                locators.append(u.get("anchor"))
            if u.get("printed_page") is not None and not isinstance(u["printed_page"], str):
                self.error(u["id"] + ": printed_page must be a string or null")
            if not u.get("scope_note", "").strip():
                self.error(u["id"] + ": missing scope_note")
        if len(set(locators)) != len(locators):
            self.error("duplicate source unit locators")
        reviews = coverage.get("units", [])
        cids = [r["id"] for r in reviews]
        if len(cids) != len(set(cids)) or set(cids) != set(ids):
            self.error("coverage must match every source unit exactly once")
        by_id = {r["id"]: r for r in reviews}
        for u in units:
            r = by_id.get(u["id"], {})
            if r.get("text_review") not in {"done", "not_applicable"}:
                self.error(u["id"] + ": text/OCR not reviewed")
            if r.get("visual_review") != "done":
                self.error(u["id"] + ": source visual review incomplete")
            if not r.get("evidence", "").strip() or r.get("issues", []):
                self.error(u["id"] + ": evidence missing or source issues unresolved")
            if r.get("text_review") == "not_applicable":
                if not local(self.root, u["text_path"]).is_file():
                    self.error(u["id"] + ": missing text record for no-text page")
            else:
                self.file(u["text_path"])
            self.file(u["preview_path"])
        items = inventory.get("items", [])
        item_ids = [i["id"] for i in items]
        if inventory.get("complete") is not True or not items:
            self.error("source inventory not reviewed as complete")
        if len(item_ids) != len(set(item_ids)):
            self.error("duplicate inventory IDs")
        if not any(i.get("category") == "section" for i in items):
            self.error("inventory requires source section entries")
        for item in items:
            name = item["id"]
            if item.get("category") not in CATEGORIES:
                self.error(name + ": unknown category")
            if not item.get("units") or not set(item["units"]).issubset(ids):
                self.error(name + ": unregistered source units")
            if not item.get("locator", "").strip() or item.get("locator_verified") is not True:
                self.error(name + ": source locator not verified")
            if item.get("disposition") not in {"pending", "covered", "compressed", "omitted"}:
                self.error(name + ": unknown disposition")
        return inventory

    def teaching(self, inventory):
        for name in ("content/outline.md", "content/chapter.tex", "content/answers.tex", "verification.md"):
            self.file(name)
        for item in inventory.get("items", []):
            name, disposition = item["id"], item.get("disposition")
            if (self.root / 'book.json').exists():
                if item.get('priority') not in {'A', 'B', 'C'} or not item.get('priority_reason', '').strip():
                    self.error(name + ': whole-book items need priority A/B/C and rationale')
                if item.get('priority') == 'A' and disposition == 'omitted':
                    self.error(name + ': core content cannot be omitted')
            if disposition in {"covered", "compressed"}:
                if disposition == 'compressed' and not item.get('reason', '').strip():
                    self.error(name + ': compression reason missing')
                refs = item.get("output_refs", [])
                if not refs:
                    self.error(name + ": no teaching output location")
                for ref in refs:
                    self.ref(ref, name, content_only=True)
                if item.get("category") in VERIFIED_CATEGORIES:
                    self.ref(item.get("verification_ref"), name + " verification")
            elif disposition == "omitted":
                basis = item.get("omission_basis")
                if not item.get("reason", "").strip():
                    self.error(name + ": omission reason missing")
                valid = (
                    (basis == "decorative" and item.get("category") == "figure")
                    or (basis == "exercise_selection" and item.get("category") == "exercise")
                    or (basis == "user_scope" and bool(item.get("user_scope_evidence", "").strip()))
                    or (basis == 'editorial_budget' and (self.root / 'book.json').exists()
                        and item.get('priority') in {'B', 'C'})
                )
                if not valid:
                    self.error(name + ": required content omitted without scope authorization")
            else:
                self.error(name + ": teaching disposition pending")
        qa = self.read("qa.json")
        for key in REQUIREMENTS:
            self.review_record(qa.get("requirements", {}).get(key, {}), "requirement " + key)
        self.review_record(qa.get("semantic_review", {}), "semantic review")
        if qa.get("unresolved", []):
            self.error("unresolved content/semantic issues")
        self.errors.extend(math_audit.validate(self.root, self.read("source.json"), inventory))
        if (self.root / "book.json").exists():
            self.errors.extend(validate_toc_plan(self.root, load(self.root / "book.json")))
        return qa

    def review_record(self, value, context):
        if value.get("status") != "pass" or not value.get("evidence"):
            self.error(context + ": not passed with evidence")
        for ref in value.get("evidence", []):
            self.ref(ref, context)

    def release(self, qa, expected_inputs=None):
        locked = self.read("content-lock.json")
        if locked != snapshot(self.root):
            self.error("locked content or source evidence changed; return to content verification")
        self.file("quality-report.md")
        pdf = qa.get("pdf", {})
        from latex_build import validate_receipt
        self.errors.extend(validate_receipt(self.root, pdf, expected_inputs))
        import pdf_review
        self.errors.extend(pdf_review.validate_manifest(self.root, pdf))
        if pdf.get("review_fingerprint") != pdf_fingerprint(self.root, pdf):
            self.error("PDF, log, layout or lock changed since prepare-pdf-review; recompile/review")
        for key in ("path", "log", "build_record"):
            self.file(pdf.get(key, ""))
        n = pdf.get("page_count", 0)
        if type(n) is not int or n < 1:
            self.error("PDF page_count must be positive")
        else:
            try:
                from pypdf import PdfReader
            except ImportError:
                self.error("release requires pypdf to confirm actual PDF page count")
            else:
                actual = len(PdfReader(str(local(self.root, pdf["path"]))).pages)
                if actual != n:
                    self.error("PDF page_count differs from actual PDF")
        records = pdf.get("reviewed_pages", [])
        nums = [r["page"] for r in records]
        if len(nums) != len(set(nums)) or set(nums) != set(range(1, n + 1)):
            self.error("PDF visual review must cover every actual page exactly once")
        for r in records:
            self.file(r.get("preview", ""))
            if not r.get("notes", "").strip():
                self.error("PDF page review needs actual observations")
        if pdf.get("status") != "pass" or pdf.get("issues", []):
            self.error("PDF QA not passed or has unresolved issues")
        log = local(self.root, pdf.get("log", ""))
        if nonempty(log):
            text = log.read_text(encoding="utf-8", errors="replace")
            patterns = (r"(?m)^!", r"Undefined control sequence", r"Missing character:",
                        r"There were undefined references", r"multiply[- ]defined",
                        r"(?:Reference|Citation) .* undefined")
            if any(re.search(pattern, text) for pattern in patterns):
                self.error("unresolved LaTeX error, missing glyph or broken reference in log")


def validate_toc_plan(root: Path, book: dict) -> list[str]:
    """Check the human-verified whole-book TOC ledger and exact source-unit accounting."""
    root = root.resolve()
    errors = []
    try:
        source = load(root / "source.json")
        toc = load(root / "toc.json")
    except (OSError, ValueError, TypeError) as exc:
        return [f"whole-book TOC ledger missing/invalid; migrate by recording and verifying the source TOC: {exc}"]

    source_sha = source.get("sha256")
    if toc.get("schema_version") != 1:
        errors.append("unsupported toc.json schema_version")
    if toc.get("status") != "verified":
        errors.append("source TOC must be human checked and marked status=verified")
    if not source_sha or toc.get("source_sha256") != source_sha:
        errors.append("toc.json source_sha256 must match the original PDF SHA-256 in source.json")
    if book.get("chapters_complete") is not True:
        errors.append("chapters_complete must be true after the verified TOC is reconciled")

    units = source.get("units", [])
    source_ids = [u.get("id") for u in units if isinstance(u, dict)]
    if not source_ids or len(source_ids) != len(set(source_ids)):
        errors.append("whole-book source unit IDs must be nonempty and unique")
    known_units = set(source_ids)

    # A whole-book source ledger must represent every physical page of the original PDF.
    if source.get("kind") != "pdf":
        errors.append("whole-book TOC reconciliation requires the original PDF source")
    else:
        try:
            from pypdf import PdfReader
            original = Path(source.get("path", ""))
            if not original.is_file():
                raise ValueError("original PDF is missing")
            if digest(original) != source_sha:
                raise ValueError("original PDF SHA-256 changed")
            actual_page_count = len(PdfReader(str(original)).pages)
            page_numbers = [u.get("pdf_page") for u in units if isinstance(u, dict)]
            if source.get("pdf_total_pages") != actual_page_count:
                errors.append("source.json pdf_total_pages differs from the original PDF")
            if (any(type(n) is not int for n in page_numbers)
                    or len(page_numbers) != actual_page_count
                    or set(page_numbers) != set(range(1, actual_page_count + 1))):
                errors.append("whole-book source.units must cover each physical PDF page 1..N exactly once")
        except Exception as exc:
            errors.append(f"cannot verify complete source PDF page coverage: {type(exc).__name__}: {exc}")

    source_evidence_files = {}
    for unit in units:
        if not isinstance(unit, dict):
            continue
        for key, kind in (("text_path", "text"), ("preview_path", "preview")):
            relative = unit.get(key)
            if isinstance(relative, str):
                source_evidence_files[relative] = kind

    def evidence_rows(rows, context):
        if not isinstance(rows, list) or not rows:
            errors.append(context + ": traceability evidence is required")
            return
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("file"), str)
                    or not isinstance(row.get("anchor"), str) or not row["anchor"].strip()):
                errors.append(context + ": evidence must contain file and anchor")
                continue
            kind = source_evidence_files.get(row["file"])
            if kind is None:
                errors.append(context + ": evidence must cite an original source unit text or page preview")
                continue
            try:
                path = local(root, row["file"])
                if not nonempty(path):
                    errors.append(context + ": evidence file missing/empty: " + row["file"])
                elif kind == "text" and row["anchor"] not in path.read_text(encoding="utf-8-sig"):
                    errors.append(context + ": evidence anchor not found in " + row["file"])
            except (OSError, ValueError, UnicodeError) as exc:
                errors.append(context + ": invalid evidence reference: " + str(exc))

    evidence_rows(toc.get("evidence"), "TOC root")
    toc_chapters = toc.get("chapters", [])
    toc_ids = [c.get("id") for c in toc_chapters if isinstance(c, dict)]
    if not toc_ids or len(toc_ids) != len(set(toc_ids)):
        errors.append("verified TOC chapter IDs must be nonempty and unique")
    toc_by_id = {}
    chapter_units = set()
    for chapter in toc_chapters:
        if not isinstance(chapter, dict):
            errors.append("TOC chapter entries must be objects")
            continue
        cid = chapter.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append("TOC chapter entry needs a stable id")
            continue
        toc_by_id[cid] = chapter
        if not isinstance(chapter.get("title"), str) or not chapter["title"].strip():
            errors.append(cid + ": TOC title required")
        if not isinstance(chapter.get("locator"), str) or not chapter["locator"].strip():
            errors.append(cid + ": source TOC locator required")
        evidence_rows(chapter.get("evidence"), cid + " TOC chapter")
        values = chapter.get("units", [])
        if (not isinstance(values, list) or not values
                or any(not isinstance(u, str) for u in values)
                or len(values) != len(set(values))):
            errors.append(cid + ": TOC chapter needs a nonempty unique source unit list")
            values = []
        unknown = set(values) - known_units
        if unknown:
            errors.append(cid + ": TOC chapter contains unknown source units: " + ", ".join(sorted(unknown)))
        chapter_units.update(set(values) & known_units)

    exclusions = toc.get("exclusions", [])
    excluded_units = set()
    for index, exclusion in enumerate(exclusions):
        context = f"TOC exclusion {index + 1}"
        if not isinstance(exclusion, dict):
            errors.append(context + ": entry must be an object")
            continue
        if not isinstance(exclusion.get("reason"), str) or not exclusion["reason"].strip():
            errors.append(context + ": explicit nonchapter exclusion reason required")
        evidence_rows(exclusion.get("evidence"), context)
        values = exclusion.get("units", [])
        if (not isinstance(values, list) or not values
                or any(not isinstance(u, str) for u in values)
                or len(values) != len(set(values))):
            errors.append(context + ": exclusion needs a nonempty unique source unit list")
            values = []
        current = set(values)
        if current & chapter_units:
            errors.append(context + ": exclusions cannot overlap TOC chapter units")
        if current & excluded_units:
            errors.append(context + ": source units cannot be excluded more than once")
        unknown = current - known_units
        if unknown:
            errors.append(context + ": exclusion contains unknown source units: " + ", ".join(sorted(unknown)))
        excluded_units.update(current & known_units)
    unaccounted = known_units - chapter_units - excluded_units
    if unaccounted:
        errors.append("source units absent from TOC chapter coverage need evidenced nonchapter exclusions: "
                      + ", ".join(sorted(unaccounted)))

    book_chapters = book.get("chapters", [])
    mapped_counts = {cid: 0 for cid in toc_by_id}
    seen_chapter_ids = set()
    for chapter in book_chapters:
        if not isinstance(chapter, dict):
            errors.append("book.chapters entries must be objects")
            continue
        chapter_id = chapter.get("id", "<chapter>")
        if chapter_id in seen_chapter_ids:
            errors.append("duplicate book chapter IDs")
        seen_chapter_ids.add(chapter_id)
        toc_refs = chapter.get("toc_ids", [])
        if (not isinstance(toc_refs, list) or not toc_refs
                or any(not isinstance(cid, str) for cid in toc_refs)
                or len(toc_refs) != len(set(toc_refs))):
            errors.append(str(chapter_id) + ": book chapter must map one or more unique toc_ids")
            toc_refs = []
        expected_units = set()
        for toc_id in toc_refs:
            if toc_id not in toc_by_id:
                errors.append(str(chapter_id) + ": unknown TOC chapter mapping " + str(toc_id))
                continue
            mapped_counts[toc_id] += 1
            expected_units.update(toc_by_id[toc_id].get("units", []))
        values = chapter.get("units", [])
        if (not isinstance(values, list) or any(not isinstance(u, str) for u in values)
                or len(values) != len(set(values))):
            errors.append(str(chapter_id) + ": book chapter units must be a unique source unit list")
            values = []
        actual_units = set(values)
        unknown = actual_units - known_units
        if unknown:
            errors.append(str(chapter_id) + ": chapter contains unknown source units: " + ", ".join(sorted(unknown)))
        if actual_units != expected_units:
            errors.append(str(chapter_id) + ": units must equal the union of its mapped TOC chapters")
    for toc_id, count in mapped_counts.items():
        if count != 1:
            errors.append(toc_id + f": expected exactly one book.chapters mapping, found {count}")
    return errors


def snapshot(root: Path):
    files = sorted(p for p in (root / "content").rglob("*") if p.is_file())
    # Local input files are locked as well; symlink escapes are rejected.
    evidence_names = list(EVIDENCE_FILES)
    if (root / "book.json").exists():
        evidence_names.append("toc.json")
    evidence = {}
    for name in evidence_names:
        path = local(root, name)
        evidence[name] = digest(path) if path.is_file() else None
    toc_evidence = {}
    toc_path = root / "toc.json"
    if (root / "book.json").exists() and toc_path.is_file():
        try:
            toc = load(toc_path)
            cited = set()
            evidence_groups = ([toc.get("evidence", [])]
                               + [entry.get("evidence", []) for entry in toc.get("chapters", [])]
                               + [entry.get("evidence", []) for entry in toc.get("exclusions", [])])
            for rows in evidence_groups:
                if isinstance(rows, list):
                    cited.update(row.get("file") for row in rows
                                 if isinstance(row, dict) and isinstance(row.get("file"), str))
            for name in sorted(cited):
                try:
                    path = local(root, name)
                    toc_evidence[name] = digest(path) if path.is_file() else None
                except ValueError:
                    toc_evidence[name] = None
        except (OSError, ValueError, TypeError, AttributeError):
            toc_evidence = {"<invalid-toc-record>": None}
    result = {"schema_version": 1,
            "content": {p.relative_to(root).as_posix(): digest(local(root, p.relative_to(root).as_posix()))
                        for p in files},
            "evidence": evidence,
            "source_assets": {p.relative_to(root).as_posix(): digest(local(root, p.relative_to(root).as_posix()))
                              for p in sorted((root / "source").rglob("*")) if p.is_file()},
            "teaching_review": {key: load(root / "qa.json")[key]
                                for key in ("requirements", "semantic_review")}}
    result["math_audit"] = math_audit.snapshot_files(root)
    if (root / 'book.json').exists():
        book = load(root / 'book.json')
        result['book_plan'] = {'chapters_complete': book.get('chapters_complete'),
                               'chapters': book.get('chapters'), 'title': book.get('title'),
                               'volumes': [{k: v[k] for k in ('id', 'chapter_ids', 'planned_pages', 'layout')}
                                           for v in book.get('volumes', [])]}
        if 'volume_count_request' in book:
            result['book_plan']['volume_count_request'] = book['volume_count_request']
        result['evidence']['selection-log.md'] = digest(root / 'selection-log.md')
        result['toc_evidence'] = toc_evidence
    return result


def pdf_fingerprint(root: Path, pdf):
    manifest = pdf.get("preview_manifest")
    manifest_hash = None
    if isinstance(manifest, str) and manifest:
        path = local(root, manifest)
        if path.is_file():
            manifest_hash = digest(path)
    return {"lock": digest(root / "content-lock.json"),
            "layout": {p.relative_to(root).as_posix(): digest(local(root, p.relative_to(root).as_posix()))
                       for p in sorted((root / "layout").rglob("*")) if p.is_file()},
            "artifacts": {key: digest(local(root, pdf[key])) for key in ("path", "log", "build_record")},
            "preview_manifest": {"path": manifest, "sha256": manifest_hash}}


def run_checks(root: Path, stage: str):
    audit = Audit(root)
    try:
        inventory = audit.source()
        if stage in {"teaching", "release"}:
            qa = audit.teaching(inventory)
        if stage == "release":
            if (root / "book.json").exists():
                audit.error("Whole-book release must use book.py check; single-PDF release is disabled")
            else:
                audit.release(qa, standalone_expected_inputs(inventory))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        audit.error(f"invalid/incomplete project record: {type(exc).__name__}: {exc}")
    return audit.errors


def standalone_expected_inputs(inventory):
    expected = {"layout/main.tex", "content/chapter.tex", "content/answers.tex"}
    for item in inventory.get("items", []):
        if item.get("disposition") in {"covered", "compressed"}:
            for ref in item.get("output_refs", []):
                if isinstance(ref, dict) and isinstance(ref.get("file"), str):
                    expected.add(ref["file"])
    return sorted(expected)


def find_xelatex():
    found = shutil.which("xelatex")
    if found:
        return found
    if os.name == "nt":
        for variable, suffix in (("LOCALAPPDATA", "Programs/MiKTeX/miktex/bin/x64/xelatex.exe"),
                                 ("APPDATA", "MiKTeX/miktex/bin/x64/xelatex.exe"),
                                 ("ProgramFiles", "MiKTeX/miktex/bin/x64/xelatex.exe")):
            base = os.environ.get(variable)
            if base and (Path(base) / suffix).is_file():
                return str(Path(base) / suffix)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="PDF extraction and pending ledgers; not OCR or a reading pass")
    init.add_argument("--pdf", required=True)
    init.add_argument("--pages", required=True, help="1-based physical PDF pages")
    init.add_argument("--out", required=True, help="fresh project directory")
    for command in ("check", "lock", "prepare-pdf-review", "compile"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("project")
        if command == "check":
            command_parser.add_argument("--stage", choices=("source", "teaching", "release"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_project(args)
        else:
            root = Path(args.project).resolve()
            stage = args.stage if args.command == "check" else "teaching"
            if args.command in {"prepare-pdf-review", "compile"} and (root / "book.json").exists():
                raise ValueError("Whole-book projects must use book.py compile/prepare-review/check; single-PDF entrypoint is disabled")
            if args.command == "compile":
                from latex_build import compile_target, invalidate_build_record, validate_destinations
                qa = load(root / "qa.json")
                pdf = qa["pdf"]
                validate_destinations(root, "main", pdf)
                invalidate_build_record(root, "main", pdf, "new compile attempt requested")
                pdf.update(status="pending", page_count=0, reviewed_pages=[], issues=["New compile attempt; PDF review required"])
                pdf.pop("review_fingerprint", None)
                pdf.pop("preview_manifest", None)
                save(root / "qa.json", qa)
                errors = run_checks(root, "teaching")
                if errors:
                    raise ValueError("\n".join(errors))
                if load(root / "content-lock.json") != snapshot(root):
                    raise ValueError("Content/evidence differs from reviewed lock; verify and lock before compiling")
                engine = find_xelatex()
                if not engine:
                    raise ValueError("XeLaTeX unavailable; run setup.ps1 and inspect doctor output")
                inventory = load(root / "inventory.json")
                record = compile_target(root, "main", pdf, "layout/main.tex", engine, 100,
                                        standalone_expected_inputs(inventory))
                pdf.update(status="pending", page_count=record["page_count"], reviewed_pages=[],
                           issues=["New successful compile; PDF review required"], recorder=record["recorder"])
                save(root / "qa.json", qa)
                result = {"status": "pass", "action": "compile", "page_count": record["page_count"],
                          "scope": "successful XeLaTeX build receipt recorded; semantic and visual reviews remain required"}
                print(json.dumps(result, ensure_ascii=True, indent=2))
                return 0
            errors = run_checks(root, stage)
            if errors:
                print(json.dumps({"status": "fail", "stage": stage, "errors": errors}, ensure_ascii=True, indent=2))
                return 1
            if args.command == "lock":
                path = root / "content-lock.json"
                if path.exists():
                    raise ValueError("lock exists; archive it and document reviewed changes before re-locking")
                save(path, snapshot(root))
            elif args.command == "prepare-pdf-review":
                if load(root / "content-lock.json") != snapshot(root):
                    raise ValueError("content/evidence differs from lock; verify before compiling")
                from latex_build import validate_receipt
                qa = load(root / "qa.json")
                pdf = qa["pdf"]
                pdf.update(status="pending", reviewed_pages=[], issues=["Preparing fresh PDF page previews"])
                pdf.pop("review_fingerprint", None)
                pdf.pop("preview_manifest", None)
                save(root / "qa.json", qa)
                receipt_errors = validate_receipt(root, pdf, standalone_expected_inputs(load(root / "inventory.json")))
                if receipt_errors:
                    raise ValueError("\n".join(receipt_errors))
                receipt = load(local(root, pdf["build_record"]))
                pdf["recorder"] = receipt["recorder"]
                import pdf_review
                manifest_path, manifest = pdf_review.create_manifest(root, pdf, "main")
                pdf["page_count"] = manifest["page_count"]
                pdf["preview_manifest"] = manifest_path
                pdf["review_fingerprint"] = pdf_fingerprint(root, pdf)
                pdf["status"] = "pending"
                pdf["reviewed_pages"] = []
                pdf["issues"] = []
                save(root / "qa.json", qa)
            result = {"status": "pass", "stage": stage,
                      "scope": "record/file integrity only; semantic and visual reviews remain human/model responsibilities"}
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
