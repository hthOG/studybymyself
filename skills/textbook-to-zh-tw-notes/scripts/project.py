#!/usr/bin/env python3
"""Create a source ledger and check handoff records; not a semantic validator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

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
        return qa

    def review_record(self, value, context):
        if value.get("status") != "pass" or not value.get("evidence"):
            self.error(context + ": not passed with evidence")
        for ref in value.get("evidence", []):
            self.ref(ref, context)

    def release(self, qa):
        locked = self.read("content-lock.json")
        if locked != snapshot(self.root):
            self.error("locked content or source evidence changed; return to content verification")
        self.file("quality-report.md")
        pdf = qa.get("pdf", {})
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


def snapshot(root: Path):
    files = sorted(p for p in (root / "content").rglob("*") if p.is_file())
    # Local input files are locked as well; symlink escapes are rejected.
    result = {"schema_version": 1,
            "content": {p.relative_to(root).as_posix(): digest(local(root, p.relative_to(root).as_posix()))
                        for p in files},
            "evidence": {name: digest(local(root, name)) for name in EVIDENCE_FILES},
            "source_assets": {p.relative_to(root).as_posix(): digest(local(root, p.relative_to(root).as_posix()))
                              for p in sorted((root / "source").rglob("*")) if p.is_file()},
            "teaching_review": {key: load(root / "qa.json")[key]
                                for key in ("requirements", "semantic_review")}}
    if (root / 'book.json').exists():
        book = load(root / 'book.json')
        result['book_plan'] = {'chapters_complete': book.get('chapters_complete'),
                               'chapters': book.get('chapters'), 'title': book.get('title'),
                               'volumes': [{k: v[k] for k in ('id', 'chapter_ids', 'planned_pages', 'layout')}
                                           for v in book.get('volumes', [])]}
        result['evidence']['selection-log.md'] = digest(root / 'selection-log.md')
    return result


def pdf_fingerprint(root: Path, pdf):
    return {"lock": digest(root / "content-lock.json"),
            "layout": {p.relative_to(root).as_posix(): digest(local(root, p.relative_to(root).as_posix()))
                       for p in sorted((root / "layout").rglob("*")) if p.is_file()},
            "artifacts": {key: digest(local(root, pdf[key])) for key in ("path", "log", "build_record")}}


def run_checks(root: Path, stage: str):
    audit = Audit(root)
    try:
        inventory = audit.source()
        if stage in {"teaching", "release"}:
            qa = audit.teaching(inventory)
        if stage == "release":
            audit.release(qa)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        audit.error(f"invalid/incomplete project record: {type(exc).__name__}: {exc}")
    return audit.errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="PDF extraction and pending ledgers; not OCR or a reading pass")
    init.add_argument("--pdf", required=True)
    init.add_argument("--pages", required=True, help="1-based physical PDF pages")
    init.add_argument("--out", required=True, help="fresh project directory")
    for command in ("check", "lock", "prepare-pdf-review"):
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
                from pypdf import PdfReader
                qa = load(root / "qa.json")
                pdf = qa["pdf"]
                pdf["page_count"] = len(PdfReader(str(local(root, pdf["path"]))).pages)
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
