#!/usr/bin/env python3
"""Bind PDF page previews to a supported local render of a compiled artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


SCHEMA_VERSION = 1
DPI = 160
RENDER_PARAMS = {"dpi": DPI, "colorspace": "RGB", "alpha": False}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _project_api():
    import project
    return project


def _safe_preview_destination(root: Path, relative: str, output_dir: Path) -> Path:
    """Reject existing links or non-files before writing generated preview artifacts."""
    project = _project_api()
    lexical_root = root.resolve()
    expected_base = lexical_root / "build" / "previews"
    expected_dir = Path(output_dir)
    lexical_path = lexical_root.joinpath(*relative.split("/"))
    if (expected_base.resolve() != expected_base or expected_dir.resolve() != expected_dir
            or not expected_dir.is_relative_to(expected_base)
            or lexical_path.parent.resolve() != expected_dir):
        raise ValueError("preview paths must resolve within the fixed build/previews output tree")
    project.local(lexical_root, relative)
    if lexical_path.exists() or lexical_path.is_symlink():
        if lexical_path.is_symlink() or not lexical_path.is_file():
            raise ValueError("refusing to replace a linked or non-regular preview output: " + relative)
    return lexical_path


def _safe_preview_directory(root: Path, relative: str) -> Path:
    lexical_root = root.resolve()
    base = lexical_root / "build" / "previews"
    path = lexical_root.joinpath(*relative.split("/"))
    if base.resolve() != base or path.parent.resolve() != base or path.resolve() != path:
        raise ValueError("preview output directories must resolve within the fixed build/previews tree")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            raise ValueError("refusing to write previews into a linked or non-directory path")
    else:
        path.mkdir()
    return path


def create_manifest(root: Path, qa: dict, target_id: str) -> tuple[str, dict]:
    """Render the current receipt-bound PDF and save a page/hash manifest under build/."""
    project = _project_api()
    root = root.resolve()
    if not re.fullmatch(r"(?:main|vol-[0-9]{2})", target_id):
        raise ValueError("unsupported PDF review target ID")
    pdf_path = project.local(root, qa["path"])
    receipt_path = project.local(root, qa["build_record"])
    if not project.nonempty(pdf_path) or not project.nonempty(receipt_path):
        raise ValueError("PDF and successful compile receipt are required before rendering review previews")

    pdf_sha_before = sha256(pdf_path)
    receipt_sha_before = sha256(receipt_path)
    receipt = project.load(receipt_path)
    if receipt.get("status") != "success" or receipt.get("pdf_sha256") != pdf_sha_before:
        raise ValueError("PDF no longer matches the successful compile receipt; compile again")
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise ValueError("PDF review rendering requires PyMuPDF (fitz)") from exc

    renderer_version = str(getattr(fitz, "VersionBind", "unknown"))
    signature = json.dumps({"pdf": pdf_sha_before, "receipt": receipt_sha_before,
                            "renderer": renderer_version, "params": RENDER_PARAMS},
                           sort_keys=True, separators=(",", ":")).encode("utf-8")
    run_id = hashlib.sha256(signature).hexdigest()[:20]
    relative_dir = f"build/previews/{target_id}-{run_id}"
    build_dir = root / "build"
    previews_root = build_dir / "previews"
    for directory in (build_dir, previews_root):
        if directory.exists() or directory.is_symlink():
            if directory.is_symlink() or not directory.is_dir() or directory.resolve() != directory:
                raise ValueError("preview output directories must be ordinary directories under build/")
    build_dir.mkdir(exist_ok=True)
    previews_root.mkdir(exist_ok=True)
    output_dir = _safe_preview_directory(root, relative_dir)

    pages = []
    with fitz.open(str(pdf_path)) as document:
        page_count = len(document)
        if page_count < 1:
            raise ValueError("cannot prepare visual review for a zero-page PDF")
        for page_number, page in enumerate(document, start=1):
            relative_png = f"{relative_dir}/page-{page_number:03d}.png"
            png_path = _safe_preview_destination(root, relative_png, output_dir)
            pixmap = page.get_pixmap(dpi=DPI, colorspace=fitz.csRGB, alpha=False)
            pixmap.save(str(png_path))
            pages.append({"page": page_number, "path": relative_png,
                          "sha256": sha256(png_path)})

    # Detect replacement/recompilation while rendering; never publish a manifest for mixed inputs.
    if sha256(pdf_path) != pdf_sha_before or sha256(receipt_path) != receipt_sha_before:
        raise ValueError("PDF or compile receipt changed while rendering previews; retry prepare-review")
    if receipt.get("page_count") != page_count:
        raise ValueError("rendered PDF page count differs from the successful compile receipt")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pdf_sha256": pdf_sha_before,
        "build_record": qa["build_record"],
        "build_record_sha256": receipt_sha_before,
        "page_count": page_count,
        "renderer": "PyMuPDF",
        "renderer_version": renderer_version,
        "render_params": RENDER_PARAMS,
        "pages": pages,
    }
    manifest_relative = f"{relative_dir}/manifest.json"
    manifest_path = _safe_preview_destination(root, manifest_relative, output_dir)
    project.save(manifest_path, manifest)
    return manifest_relative, manifest


def validate_manifest(root: Path, qa: dict) -> list[str]:
    """Check manifest, PDF, receipt, page mapping, and rendered PNG bytes without rerendering."""
    project = _project_api()
    errors = []
    manifest_relative = qa.get("preview_manifest")
    if not isinstance(manifest_relative, str) or not manifest_relative:
        return ["missing generated PDF preview manifest; rerun the supported prepare-review command"]
    try:
        manifest_path = project.local(root, manifest_relative)
        preview_root = project.local(root, "build/previews")
        if not manifest_path.is_relative_to(preview_root):
            raise ValueError("manifest must be stored under build/previews/")
        if not project.nonempty(manifest_path):
            raise ValueError("manifest is missing or empty")
        manifest = project.load(manifest_path)
        pdf_path = project.local(root, qa["path"])
        receipt_path = project.local(root, qa["build_record"])
        receipt = project.load(receipt_path)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return ["invalid PDF preview manifest or referenced artifact: " + str(exc)]

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported PDF preview manifest; rerun prepare-review")
    if manifest.get("renderer") != "PyMuPDF" or not isinstance(manifest.get("renderer_version"), str):
        errors.append("PDF preview manifest was not produced by the supported PyMuPDF renderer")
    if manifest.get("render_params") != RENDER_PARAMS:
        errors.append("PDF preview render parameters are unsupported")
    if manifest.get("build_record") != qa.get("build_record"):
        errors.append("PDF preview manifest references a different compile receipt")
    if not project.nonempty(pdf_path) or not project.nonempty(receipt_path):
        errors.append("PDF or compile receipt is missing after PDF review preparation")
        return errors

    current_pdf_sha = sha256(pdf_path)
    current_receipt_sha = sha256(receipt_path)
    if manifest.get("pdf_sha256") != current_pdf_sha or receipt.get("pdf_sha256") != current_pdf_sha:
        errors.append("PDF preview manifest, current PDF, and successful receipt do not match")
    if manifest.get("build_record_sha256") != current_receipt_sha:
        errors.append("PDF preview manifest no longer matches the compile receipt")
    if receipt.get("status") != "success":
        errors.append("PDF preview manifest does not reference a successful compile receipt")

    try:
        from pypdf import PdfReader
        actual_count = len(PdfReader(str(pdf_path)).pages)
    except Exception as exc:
        return errors + [f"cannot confirm PDF page count for preview manifest: {type(exc).__name__}: {exc}"]
    count = manifest.get("page_count")
    if type(count) is not int or count != actual_count or count != receipt.get("page_count") or count != qa.get("page_count"):
        errors.append("PDF preview page count differs from the current PDF, receipt, or QA record")

    pages = manifest.get("pages")
    if not isinstance(pages, list) or len(pages) != actual_count:
        errors.append("PDF preview manifest must contain one rendered image per actual page")
        return errors
    by_number = {}
    paths = set()
    for item in pages:
        if not isinstance(item, dict) or type(item.get("page")) is not int:
            errors.append("PDF preview manifest has an invalid page record")
            continue
        number = item["page"]
        if number in by_number:
            errors.append("PDF preview manifest has a duplicate page number")
            continue
        by_number[number] = item
        relative = item.get("path")
        expected_prefix = str(Path(manifest_relative).parent).replace("\\", "/") + "/"
        try:
            if not isinstance(relative, str) or not relative.startswith(expected_prefix):
                raise ValueError("page image must stay beside its generated manifest")
            image_path = project.local(root, relative)
            if not image_path.is_relative_to(preview_root) or image_path.suffix.casefold() != ".png":
                raise ValueError("page image must be a PNG under build/previews/")
            if relative in paths:
                raise ValueError("multiple PDF pages map to the same PNG")
            paths.add(relative)
            if not project.nonempty(image_path):
                raise ValueError("rendered page PNG is missing or empty")
            with image_path.open("rb") as stream:
                if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                    raise ValueError("rendered page is not a valid PNG file")
            if item.get("sha256") != sha256(image_path):
                raise ValueError("rendered page PNG SHA-256 changed")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"page {number} preview invalid: {exc}")
    if set(by_number) != set(range(1, actual_count + 1)):
        errors.append("PDF preview manifest page numbers must map exactly to 1..page_count")

    reviews = qa.get("reviewed_pages", [])
    for review in reviews:
        if not isinstance(review, dict) or type(review.get("page")) is not int:
            errors.append("PDF visual review contains an invalid page mapping")
            continue
        item = by_number.get(review["page"])
        if item and review.get("preview") != item.get("path"):
            errors.append(f"page {review['page']} review points at a different preview than its manifest")
    return errors
