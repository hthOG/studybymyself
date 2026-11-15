#!/usr/bin/env python3
"""Flag likely internal notes/placeholders in final PDFs; never judge formulas.

Findings require reading the actual page. Empty extracted text is not a pass.
"""
import argparse
import json
from pathlib import Path
import re
import sys

PATTERNS = {
    "unapproved_correction": r"候選訂正|待主代理.{0,4}核定",
    "internal_handoff": r"不印正式|草稿子代理|figures\.json|verification-fragment",
    "placeholder": r"此處放原圖|此處放原書|此處(?:補寫|插入)|原書\s*p\.?\s*[?？]|TODO|PLACEHOLDER",
    "pending_review": r"待視覺|未逐項全驗|待(?:核驗|驗算|補圖)",
}


def inspect(pdf):
    import fitz

    findings = []
    with fitz.open(pdf) as document:
        if document.needs_pass:
            raise ValueError("PDF is encrypted")
        if not document.page_count:
            raise ValueError("PDF has no pages")
        for number, page in enumerate(document, 1):
            text = page.get_text()
            if not text.strip():
                findings.append({"page": number, "kind": "no_text",
                                 "match": "No extractable text; visual review required"})
                continue
            # PDF extraction can break a phrase between lines. Preserve displayed
            # page identity while joining whitespace for this heuristic search.
            joined = re.sub(r"\s+", "", text)
            for kind, pattern in PATTERNS.items():
                for match in re.finditer(pattern, joined, re.IGNORECASE):
                    findings.append({"page": number, "kind": kind, "match": match.group(0)})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args(argv)
    try:
        findings = inspect(args.pdf)
        print(json.dumps({"pdf": str(args.pdf), "findings": findings,
                          "scope": "text heuristic only; actual page review required"},
                         ensure_ascii=True, indent=2))
        return 1 if findings else 0
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
