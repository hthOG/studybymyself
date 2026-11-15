#!/usr/bin/env python3
"""Check the integrity of recorded math reviews; never judge mathematical truth.

The ledger is data: its contents are never executed. A passing result verifies
only traceability, freshness and completeness of the recorded review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


MATH_CATEGORIES = {"equation", "derivation", "example", "exercise"}
CHECKS = ("source_visual", "recompute", "dimension", "limit", "domain")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local(root, name):
    """Return a project-local file path, rejecting traversal and symlinks outside."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("missing relative path")
    # Treat backslashes consistently on every host and reject Windows drive paths.
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError("absolute path")
    parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("noncanonical relative path")
    root = Path(root).resolve()
    path = (root / normalized).resolve()
    if not path.is_relative_to(root):
        raise ValueError("path escapes project")
    return path


def _nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _entries_required(inventory):
    if not isinstance(inventory, dict) or not isinstance(inventory.get("items"), list):
        raise ValueError("inventory.items must be a list")
    selected = {}
    for item in inventory["items"]:
        if not isinstance(item, dict):
            raise ValueError("inventory item must be an object")
        category, disposition = item.get("category"), item.get("disposition")
        if (isinstance(category, str) and category in MATH_CATEGORIES
                and isinstance(disposition, str) and disposition in {"covered", "compressed"}):
            item_id = item.get("id")
            if not _nonblank(item_id) or item_id in selected:
                raise ValueError("missing or duplicate selected inventory id")
            selected[item_id] = item
    return selected


def _references(value, context, errors):
    if not isinstance(value, list) or not value:
        errors.append(context + ": evidence must be a nonempty list")
        return []
    valid = []
    for ref in value:
        if not isinstance(ref, dict) or not _nonblank(ref.get("file")) or not _nonblank(ref.get("anchor")):
            errors.append(context + ": invalid evidence reference")
        else:
            valid.append(ref)
    return valid


def _check_file_hashes(root, mapping, context, errors):
    if not isinstance(mapping, dict) or not mapping:
        errors.append(context + ": file hashes must be a nonempty object")
        return set()
    valid = set()
    for name, expected in mapping.items():
        try:
            path = local(root, name)
            if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                raise ValueError("invalid sha256")
            if not path.is_file():
                raise ValueError("file missing")
            if digest(path) != expected:
                raise ValueError("file changed since review")
            valid.add(name)
        except (OSError, ValueError) as exc:
            errors.append(f"{context}: {name!r}: {exc}")
    return valid


def _check_ref(root, ref, hashed, context, errors):
    name, anchor = ref["file"], ref["anchor"]
    if name not in hashed:
        errors.append(context + ": evidence file missing or stale in evidence_files: " + name)
        return
    try:
        path = local(root, name)
        if anchor not in path.read_text(encoding="utf-8"):
            errors.append(context + ": anchor not found in " + name)
    except (OSError, ValueError, UnicodeError) as exc:
        errors.append(f"{context}: cannot read evidence {name!r}: {exc}")


def validate(root, source, inventory):
    """Return structural errors for math-audit.json; never mutate the project."""
    root = Path(root).resolve()
    errors = []
    try:
        selected = _entries_required(inventory)
    except ValueError as exc:
        return ["math audit: " + str(exc)]
    try:
        ledger_path = local(root, "math-audit.json")
    except ValueError as exc:
        return ["math audit: invalid ledger path: " + str(exc)]
    if not ledger_path.is_file():
        # A project without any selected mathematical objects has nothing to audit.
        return ["math audit: missing math-audit.json"] if selected else []
    try:
        ledger = _read_json(ledger_path)
    except (OSError, ValueError, UnicodeError) as exc:
        return ["math audit: invalid ledger: " + str(exc)]
    if not isinstance(ledger, dict):
        return ["math audit: ledger must be an object"]
    if type(ledger.get("schema_version")) is not int or ledger.get("schema_version") != 1:
        errors.append("math audit: unsupported schema_version")
    source_hash = source.get("sha256") if isinstance(source, dict) else None
    if not isinstance(source_hash, str) or not SHA256.fullmatch(source_hash) or ledger.get("source_sha256") != source_hash:
        errors.append("math audit: source sha256 missing or mismatched")
    convention = (_references([ledger.get("conventions_ref")], "math audit conventions", errors)
                  if selected else [])
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        return errors + ["math audit: entries must be a list"]
    seen = set()
    for row in entries:
        if not isinstance(row, dict):
            errors.append("math audit: entry must be an object")
            continue
        item_id = row.get("item_id")
        if not _nonblank(item_id):
            errors.append("math audit: missing item_id")
            continue
        context = "math audit " + item_id
        if item_id in seen:
            errors.append(context + ": duplicate entry")
            continue
        seen.add(item_id)
        if item_id not in selected:
            errors.append(context + ": unknown or unselected inventory item")
            continue
        author, reviewer = row.get("author"), row.get("reviewer")
        if not _nonblank(author) or not _nonblank(reviewer) or author.strip().casefold() == reviewer.strip().casefold():
            errors.append(context + ": author and independent reviewer must be distinct")
        if row.get("status") != "pass" or row.get("issues") != []:
            errors.append(context + ": review not passed or unresolved issues")
        reviewed = _check_file_hashes(root, row.get("reviewed_files"), context + " reviewed", errors)
        output_refs = selected[item_id].get("output_refs")
        if not isinstance(output_refs, list) or not output_refs:
            errors.append(context + ": selected item has no output_refs")
            output_refs = []
        for ref in output_refs:
            name = ref.get("file") if isinstance(ref, dict) else None
            if not _nonblank(name) or name not in reviewed:
                errors.append(context + ": output file not present or stale in reviewed_files: " + str(name))
        hashed = _check_file_hashes(root, row.get("evidence_files"), context + " evidence", errors)
        for ref in convention:
            _check_ref(root, ref, hashed, context + " conventions", errors)
        checks = row.get("checks")
        if not isinstance(checks, dict):
            errors.append(context + ": checks must be an object")
            continue
        for check_name in CHECKS:
            check = checks.get(check_name)
            label = context + " " + check_name
            if not isinstance(check, dict):
                errors.append(label + ": missing check")
                continue
            status = check.get("status")
            if status == "pass":
                for ref in _references(check.get("evidence"), label, errors):
                    _check_ref(root, ref, hashed, label, errors)
            elif status == "not_applicable" and check_name != "source_visual":
                if not _nonblank(check.get("reason")):
                    errors.append(label + ": not_applicable needs a reason")
            else:
                errors.append(label + ": must pass or be justified not_applicable")
        recompute = checks.get("recompute")
        if isinstance(recompute, dict) and recompute.get("status") == "not_applicable":
            if selected[item_id].get("category") not in {"example", "exercise"}:
                errors.append(context + ": equations and derivations require recomputation")
            conceptual = checks.get("conceptual")
            label = context + " conceptual"
            if not isinstance(conceptual, dict) or conceptual.get("status") != "pass":
                errors.append(label + ": required when recomputation is not applicable")
            else:
                for ref in _references(conceptual.get("evidence"), label, errors):
                    _check_ref(root, ref, hashed, label, errors)
    for item_id in sorted(set(selected) - seen):
        errors.append("math audit " + item_id + ": selected item missing from ledger")
    return errors


def snapshot_files(root):
    """Fingerprint the ledger and its declared review dependencies.

    Validation still checks their meaning and recorded hashes independently.
    Malformed data is not interpreted as review evidence and fails validation.
    """
    path = local(root, "math-audit.json")
    snapshot = {"math-audit.json": digest(path) if path.is_file() else None}
    if not path.is_file():
        return snapshot
    try:
        ledger = _read_json(path)
        rows = ledger.get("entries", []) if isinstance(ledger, dict) else []
        if not isinstance(rows, list):
            return snapshot
        names = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("reviewed_files", "evidence_files"):
                files = row.get(key)
                if isinstance(files, dict):
                    names.update(name for name in files if isinstance(name, str))
        for name in sorted(names):
            try:
                dependency = local(root, name)
                snapshot[name] = digest(dependency) if dependency.is_file() else None
            except (OSError, ValueError):
                snapshot[name] = None
    except (OSError, ValueError, UnicodeError):
        pass
    return snapshot


def init(root, source, inventory):
    """Create an explicitly pending ledger without claiming any review occurred."""
    root = Path(root).resolve()
    path = local(root, "math-audit.json")
    selected = _entries_required(inventory)
    entries = []
    for item_id in sorted(selected):
        entries.append({"item_id": item_id, "author": "", "reviewer": "", "status": "pending",
                        "issues": ["review not performed"], "reviewed_files": {}, "evidence_files": {},
                        "checks": {name: {"status": "pending", "evidence": []} for name in CHECKS}})
    ledger = {"schema_version": 1, "source_sha256": source.get("sha256"),
              "conventions_ref": {"file": "", "anchor": ""}, "entries": entries}
    # Exclusive creation prevents accidentally destroying existing review records.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(ledger, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "check"))
    parser.add_argument("project", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.project.resolve()
        source = _read_json(root / "source.json")
        inventory = _read_json(root / "inventory.json")
        if args.command == "init":
            print("Created pending ledger:", init(root, source, inventory))
            return 0
        errors = validate(root, source, inventory)
        if errors:
            for error in errors:
                print("FAIL:", error, file=sys.stderr)
            return 1
        print("Math audit records are structurally consistent; correctness is not proven.")
        return 0
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
