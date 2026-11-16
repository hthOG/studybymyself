#!/usr/bin/env python3
"""Freeze a private, portable Muse-to-Codex package; never publish book data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills/textbook-to-zh-tw-notes/scripts"
# A copied tool must not create unlisted __pycache__ files inside the frozen package.
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
import project as ledger

CATEGORIES = ("concepts", "formulas_derivations", "figures_tables", "exercises",
              "terms_symbols", "issues_corrections")
SKIP = {".git", ".venv", "__pycache__"}
WORKFLOW = ("AGENTS.md", "agent.md", "README.md", "requirements.txt", "setup.ps1",
            "setup.sh", "opencode.json", ".opencode", ".codex", ".gitignore", ".gitattributes",
            "scripts", "skills", "prompts", "docs", "examples", "tests", "workflows")


def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local(root, name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("Use a package-relative POSIX path: " + str(name))
    parts = PurePosixPath(name)
    if parts.is_absolute() or ".." in parts.parts or parts.as_posix() != name:
        raise ValueError("Unsafe relative path: " + name)
    p = root / name
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes package: " + name)
    return p


def regular(p):
    # Reject links/junctions, including directory links, rather than silently omit data.
    if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
        raise ValueError("Copy real files, not links/junctions: " + str(p))
    if getattr(p.stat(), "st_file_attributes", 0) & 0x400:
        raise ValueError("Reparse point is not portable: " + str(p))


def files(root, skip=False):
    regular(root)
    result = []
    for p in sorted(root.iterdir()):
        if skip and (p.name in SKIP or p.name.endswith(".pyc")):
            continue
        regular(p)
        if p.is_dir():
            result.extend(files(p, skip))
        elif p.is_file():
            result.append(p)
        else:
            raise ValueError("Unsupported file: " + str(p))
    return result


def copy_tree(src, dst):
    dst.mkdir(parents=True, exist_ok=False)
    for p in files(src, skip=True):
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


def outside(out, roots):
    if out.exists():
        raise ValueError("Choose a fresh output directory: " + str(out))
    for root in roots:
        if out.is_relative_to(root) or root.is_relative_to(out):
            raise ValueError("Output must be separate from repo/project/package: " + str(out))


def materials(root):
    for name in ("source.json", "coverage.json", "inventory.json", "toc.json", "book.json",
                 "progress.json", "handoff-notes.md", "handoff-materials.json"):
        if not (root / name).is_file() or not (root / name).stat().st_size:
            raise ValueError("Required handoff file missing/empty: " + name)
    data = load(root / "handoff-materials.json")
    for key in ("user_request", "scope", "reading_summary"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError("handoff-materials.json needs " + key)
    for key in ("completed_batches", "pending_batches"):
        if not isinstance(data.get(key), list):
            raise ValueError("handoff-materials.json needs a " + key + " list")
    for key in CATEGORIES:
        row = data.get("materials", {}).get(key, {})
        if row.get("status") == "not_present":
            if not row.get("reason", "").strip():
                raise ValueError(key + ": explain absence based on the source")
        elif row.get("status") == "provided" and row.get("files"):
            for name in row["files"]:
                p = local(root, name)
                if not p.is_file() or not p.stat().st_size:
                    raise ValueError(key + ": missing/empty material: " + name)
        else:
            raise ValueError(key + ": provide files or a reason for not_present")
    return data


def source_errors(root, original):
    source = load(root / "source.json")
    saved = (root / "source.json").read_bytes()
    try:
        source["path"] = str(original)
        save(root / "source.json", source)
        errors = ledger.run_checks(root, "source")
        from pypdf import PdfReader
        total = len(PdfReader(str(original)).pages)
        pages = [u.get("pdf_page") for u in source.get("units", [])]
        if source.get("pdf_total_pages") != total or set(pages) != set(range(1, total + 1)):
            errors.append("Whole-book source units must cover every actual PDF page")
        errors.extend(ledger.validate_toc_plan(root, load(root / "book.json")))
        return errors
    finally:
        (root / "source.json").write_bytes(saved)


def pack(src, out, original=None, checkpoint=False):
    src, out = Path(src).resolve(), Path(out).resolve()
    outside(out, (src, REPO))
    info = materials(src)
    source = load(src / "source.json")
    original = Path(original or source["path"]).resolve()
    if source.get("kind") != "pdf" or not original.is_file():
        raise ValueError("Provide the original PDF with --pdf (old paths may be stale)")
    regular(original)
    if sha(original) != source.get("sha256"):
        raise ValueError("Original PDF SHA-256 differs from source.json")
    # Preflight the entire source before creating output. Never edit the Muse project.
    files(src, skip=True)
    out.mkdir(parents=True)
    try:
        (out / "original").mkdir()
        shutil.copy2(original, out / "original/book.pdf")
        copy_tree(src, out / "project")
        portable = load(out / "project/source.json")
        portable["path"] = "../original/book.pdf"
        save(out / "project/source.json", portable)
        errors = source_errors(out / "project", out / "original/book.pdf")
        if info["pending_batches"]:
            errors.append("Muse records pending batches; Codex must complete/accept them")
        if errors and not checkpoint:
            raise ValueError("Source handoff incomplete; fix it or explicitly use --checkpoint:\n"
                             + "\n".join(errors))
        (out / "workflow").mkdir()
        for name in WORKFLOW:
            p, dest = REPO / name, out / "workflow" / name
            if p.is_dir():
                copy_tree(p, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
        (out / "START-HERE.md").write_text(
            "# Muse → Codex 私人交接包\n\n"
            "先讀 project/handoff-notes.md、handoff.json 和 workflow/workflows/muse-codex/README.md。\n"
            "本包含原文書實體副本 original/book.pdf；整包保留，不上傳公開 GitHub。\n"
            "project/ 是凍結快照，不能直接編寫或沿用舊 lock/pass。\n"
            "由 workflow/workflows/muse-codex/handoff.py check 核對後，\n"
            "執行 prepare --out <新的工作目錄>，再使用 codex-write.md。\n"
            "檢查通過只表示包內檔案一致，來源與數學仍需 Codex 接受及獨立核算。\n",
            encoding="utf-8")
        manifest = {"schema_version": 1, "workflow": "muse-read-codex-write",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "checkpoint" if checkpoint else "source_records_complete",
                    "user_request": info["user_request"], "scope": info["scope"],
                    "source_pdf": "original/book.pdf", "source_sha256": sha(out / "original/book.pdf"),
                    "source_gate_errors": errors, "quality_acceptance": "pending_codex_review",
                    "excluded": sorted(SKIP) + ["*.pyc"],
                    "files": {p.relative_to(out).as_posix(): sha(p) for p in files(out)}}
        save(out / "handoff.json", manifest)
        check(out)
        return manifest
    except Exception:
        # Only the freshly created, checked output is removed; original data is untouched.
        shutil.rmtree(out)
        raise


def check(root):
    root = Path(root).resolve()
    manifest = load(root / "handoff.json")
    if (manifest.get("schema_version") != 1 or manifest.get("workflow") != "muse-read-codex-write"
            or manifest.get("source_pdf") != "original/book.pdf"
            or manifest.get("quality_acceptance") != "pending_codex_review"):
        raise ValueError("Unsupported handoff manifest")
    if manifest.get("status") not in {"checkpoint", "source_records_complete"}:
        raise ValueError("Invalid handoff status")
    if manifest["status"] == "source_records_complete" and manifest.get("source_gate_errors"):
        raise ValueError("Complete handoff cannot contain source errors")
    actual = {p.relative_to(root).as_posix() for p in files(root)} - {"handoff.json"}
    entries = manifest.get("files", {})
    if set(entries) != actual:
        raise ValueError("Missing or unlisted package files")
    for name, expected in entries.items():
        if sha(local(root, name)) != expected:
            raise ValueError("Changed package file: " + name)
    for name in ("original/book.pdf", "project/source.json", "workflow/AGENTS.md",
                 "workflow/workflows/muse-codex/codex-write.md", "START-HERE.md"):
        if name not in entries:
            raise ValueError("Missing required package payload: " + name)
    source = load(root / "project/source.json")
    if source.get("path") != "../original/book.pdf":
        raise ValueError("Snapshot must use the bundled original pointer")
    if not source.get("sha256") == manifest.get("source_sha256") == sha(root / "original/book.pdf"):
        raise ValueError("Bundled original identity mismatch")
    info = materials(root / "project")
    if manifest["user_request"] != info["user_request"] or manifest["scope"] != info["scope"]:
        raise ValueError("Handoff request/scope mismatch")
    if manifest["status"] == "source_records_complete" and info["pending_batches"]:
        raise ValueError("Complete package still lists pending batches")
    return manifest


def prepare(root, out):
    root, out = Path(root).resolve(), Path(out).resolve()
    manifest = check(root)
    outside(out, (root, REPO))
    out.mkdir(parents=True)
    # Writable workflow copy keeps setup caches/venv out of the frozen package.
    for name in ("project", "workflow", "original"):
        copy_tree(root / name, out / name)
    project_root = out / "project"
    source = load(project_root / "source.json")
    source["path"] = str(out / "original/book.pdf")
    save(project_root / "source.json", source)
    # Preserve old records before removing active locks/reviews. Source reading stays intact.
    history = project_root / "handoff-history"
    history.mkdir(exist_ok=True)
    for name in ("content-lock.json", "math-audit.json", "qa.json", "book.json"):
        old = project_root / name
        if not old.is_file():
            continue
        target = history / (old.stem + ".before-codex.json")
        n = 1
        while target.exists():
            target = history / (old.stem + f".before-codex-{n}.json")
            n += 1
        shutil.copy2(old, target)
        if name in {"content-lock.json", "math-audit.json"}:
            old.unlink()

    def pending_pdf(row):
        row.update(status="pending", page_count=0, reviewed_pages=[], preview_manifest=None,
                   issues=["Codex handoff: recompile and perform full PDF review"])
        row.pop("review_fingerprint", None)

    if (project_root / "qa.json").is_file():
        qa = load(project_root / "qa.json")
        for row in qa.get("requirements", {}).values():
            row.update(status="pending", evidence=[])
        qa["semantic_review"] = {"status": "pending", "evidence": []}
        if isinstance(qa.get("pdf"), dict):
            pending_pdf(qa["pdf"])
        save(project_root / "qa.json", qa)
    book = load(project_root / "book.json")
    for volume in book.get("volumes", []):
        if isinstance(volume.get("qa"), dict):
            pending_pdf(volume["qa"])
    save(project_root / "book.json", book)
    save(project_root / "codex-acceptance.json", {"status": "pending", "package": str(root),
         "manifest_sha256": sha(root / "handoff.json"), "source_status": manifest["status"],
         "note": "Old QA, math-audit and receipts are history; accept evidence and revalidate changed content."})
    return {"workspace": str(out), "project": str(project_root), "workflow": str(out / "workflow"),
            "source_pdf": source["path"], "acceptance": "pending"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack")
    p.add_argument("project")
    p.add_argument("--out", required=True)
    p.add_argument("--pdf", help="Current original path; SHA must match source.json")
    p.add_argument("--checkpoint", action="store_true", help="Explicitly incomplete source snapshot")
    p = sub.add_parser("check")
    p.add_argument("package")
    p = sub.add_parser("prepare")
    p.add_argument("package")
    p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            result = pack(args.project, args.out, args.pdf, args.checkpoint)
            result = {k: result[k] for k in ("status", "source_gate_errors", "quality_acceptance")}
        elif args.command == "check":
            m = check(args.package)
            result = {"integrity": "ok", "status": m["status"], "quality_acceptance": m["quality_acceptance"]}
        else:
            result = prepare(args.package, args.out)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
