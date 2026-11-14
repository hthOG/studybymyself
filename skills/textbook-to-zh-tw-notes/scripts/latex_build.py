#!/usr/bin/env python3
"""Fail-closed XeLaTeX build receipts and recorder-manifest validation."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from typing import Iterable

import project

SCHEMA = "studybymyself-xelatex-build-v1"
MAX_PASSES = 4
TIMEOUT_SECONDS = 300
RERUN = re.compile(r"Rerun to get|Label\(s\) may have changed|There were undefined references")
UNRESOLVED_REFS = re.compile(r"(?:Reference|Citation) .* undefined")
HARD_FATAL = re.compile(r"(?m)^!|Undefined control sequence|Missing character:|multiply[- ]defined|Emergency stop|Fatal error")
AUXILIARY_SUFFIXES = (
    ".aux", ".toc", ".out", ".lof", ".lot", ".nav", ".snm", ".vrb", ".bcf",
    ".run.xml", ".bbl", ".blg", ".idx", ".ind", ".ilg", ".glo", ".gls", ".glg",
    ".acn", ".acr", ".alg", ".ist", ".xdv", ".log", ".pdf", ".synctex.gz", ".fls",
)
FONT_SUFFIXES = {".otf", ".ttf", ".ttc", ".pfb", ".pfa", ".tfm", ".vf", ".enc", ".map"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json_digest(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _under(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _system_roots(engine: str | Path) -> list[str]:
    """Return concrete TeX-distribution and OS-font roots for external inputs."""
    roots: set[Path] = set()
    try:
        executable = Path(engine).resolve()
    except OSError:
        executable = Path(engine).absolute()
    parents = list(executable.parents)
    for index, parent in enumerate(parents):
        name = parent.name.casefold()
        if name in {"miktex", "texlive"}:
            roots.add(parent.resolve())
        elif parent.parent.name.casefold() == "texlive":
            roots.add(parent.parent.resolve())

    for variable in ("MIKTEX_ROOT", "TEXMFROOT", "TEXMFDIST", "TEXLIVE_ROOT"):
        value = os.environ.get(variable)
        if value:
            candidate = Path(value).resolve()
            if candidate.is_dir():
                roots.add(candidate)

    kpsewhich = shutil.which("kpsewhich")
    if not kpsewhich:
        engine_path = Path(engine)
        for name in ("kpsewhich.exe", "miktex-kpsewhich.exe", "kpsewhich"):
            candidate = engine_path.with_name(name)
            if candidate.is_file():
                kpsewhich = str(candidate)
                break
    if kpsewhich:
        for variable in ("TEXMFROOT", "TEXMFDIST", "TEXMFVAR", "TEXMFSYSVAR",
                         "TEXMFCONFIG", "TEXMFSYSCONFIG", "TEXMFHOME"):
            try:
                result = subprocess.run([kpsewhich, "--var-value=" + variable], capture_output=True,
                                        timeout=5, check=False)
                value = result.stdout.decode("utf-8", errors="replace").strip()
                candidate = Path(value).resolve() if value else None
                if result.returncode == 0 and candidate and candidate.is_dir():
                    roots.add(candidate)
            except (OSError, subprocess.TimeoutExpired):
                pass

    windows = os.environ.get("WINDIR")
    local_app = os.environ.get("LOCALAPPDATA")
    roaming_app = os.environ.get("APPDATA")
    program_data = os.environ.get("PROGRAMDATA")
    if windows:
        candidate = Path(windows) / "Fonts"
        if candidate.is_dir():
            roots.add(candidate.resolve())
    if local_app:
        candidate = Path(local_app) / "Microsoft" / "Windows" / "Fonts"
        if candidate.is_dir():
            roots.add(candidate.resolve())
        for base in (Path(local_app) / "MiKTeX", Path(local_app) / "Programs" / "MiKTeX"):
            if base.is_dir():
                roots.add(base.resolve())
    if roaming_app:
        candidate = Path(roaming_app) / "MiKTeX"
        if candidate.is_dir():
            roots.add(candidate.resolve())
    if program_data:
        candidate = Path(program_data) / "MiKTeX"
        if candidate.is_dir():
            roots.add(candidate.resolve())
    for raw in ("/usr/share/fonts", "/usr/local/share/fonts", "/System/Library/Fonts", "/Library/Fonts"):
        candidate = Path(raw)
        if candidate.is_dir():
            roots.add(candidate.resolve())
    for raw in ("/var/lib/texmf", "/var/cache/texmf", "/var/lib/miktex", "/var/cache/miktex"):
        candidate = Path(raw)
        if candidate.is_dir():
            roots.add(candidate.resolve())
    try:
        home_fonts = Path.home() / ".local" / "share" / "fonts"
        if home_fonts.is_dir():
            roots.add(home_fonts.resolve())
    except OSError:
        pass
    return sorted(str(path) for path in roots)


def _resolve_fls_path(raw: str, pwd: Path) -> Path:
    value = raw.strip()
    if not value:
        raise ValueError("empty recorder path")
    path = Path(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", value):
        return path.resolve()
    return (pwd / path).resolve()


def parse_fls(path: Path) -> dict:
    """Parse XeLaTeX's PWD/INPUT/OUTPUT trace without splitting paths on spaces."""
    if not project.nonempty(path):
        raise ValueError("missing or empty XeLaTeX recorder (.fls)")
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    pwd_raw = None
    records: list[tuple[str, str]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line:
            continue
        kind, sep, value = line.partition(" ")
        if not sep or not value:
            raise ValueError(f"malformed recorder line {line_number}")
        if kind == "PWD":
            pwd_raw = value
        elif kind in {"INPUT", "OUTPUT"}:
            records.append((kind, value))
        else:
            raise ValueError(f"unknown recorder record at line {line_number}: {kind}")
    if not pwd_raw:
        raise ValueError("recorder is missing PWD; cannot resolve relative INPUT paths")
    pwd = Path(pwd_raw).resolve()
    inputs, outputs, relative_inputs = [], [], []
    for kind, raw in records:
        resolved = _resolve_fls_path(raw, pwd)
        (inputs if kind == "INPUT" else outputs).append(str(resolved))
        if kind == "INPUT" and not Path(raw).is_absolute() and not re.match(r"^[A-Za-z]:[\\/]", raw):
            relative_inputs.append(str(resolved))
    if not inputs:
        raise ValueError("recorder contains no INPUT entries")
    if not outputs:
        raise ValueError("recorder contains no OUTPUT entries")
    return {"pwd": str(pwd), "inputs": sorted(set(inputs)), "outputs": sorted(set(outputs)),
            "relative_inputs": sorted(set(relative_inputs))}


def _is_auxiliary(path: Path) -> bool:
    name = path.name.casefold()
    return any(name.endswith(suffix) for suffix in AUXILIARY_SUFFIXES)


def _validate_trace_scope(root: Path, staging: Path, trace: dict) -> None:
    if Path(trace["pwd"]).resolve() != root.resolve():
        raise ValueError("recorder PWD does not match the project root")
    stage = staging.resolve()
    for raw in trace["outputs"]:
        if not _under(Path(raw).resolve(), stage):
            raise ValueError("XeLaTeX recorder lists an output outside its fresh staging directory: " + raw)


def _manifest(root: Path, trace: dict, staging: Path, all_outputs: set[str], system_roots: list[str]) -> dict:
    local_inputs: dict[str, str] = {}
    system_inputs: dict[str, str] = {}
    stage = staging.resolve()
    root = root.resolve()
    allowed_roots = [Path(raw).resolve() for raw in system_roots]
    relative_inputs = set(trace.get("relative_inputs", []))
    for raw in trace["inputs"]:
        path = Path(raw).resolve()
        if _under(path, root):
            if _under(path, stage):
                if raw not in all_outputs or not _is_auxiliary(path):
                    raise ValueError("recorder input inside fresh build staging is not a known compiler auxiliary: " + raw)
                continue
            if not path.is_file():
                raise ValueError("recorder input is missing: " + raw)
            rel = path.relative_to(root).as_posix()
            local_inputs[rel] = sha256(path)
            continue
        if raw in relative_inputs:
            raise ValueError("relative recorder INPUT escapes the project root: " + raw)
        if not path.is_file():
            raise ValueError("external recorder input is missing: " + raw)
        is_font = path.suffix.casefold() in FONT_SUFFIXES
        permitted = any(_under(path, base) for base in allowed_roots)
        if not permitted:
            if path.suffix.casefold() == ".tex":
                raise ValueError("external .tex input is not a configured TeX system resource; copy it into the project: " + raw)
            raise ValueError("external recorder input is outside configured TeX/font roots: " + raw)
        if not is_font and not any(_under(path, base) for base in allowed_roots):
            raise ValueError("external input is not an approved system resource: " + raw)
        system_inputs[str(path)] = sha256(path)
    return {"project_inputs": dict(sorted(local_inputs.items())),
            "system_inputs": dict(sorted(system_inputs.items()))}


def _require_expected(manifest: dict, expected: Iterable[str]) -> None:
    present = set(manifest["project_inputs"])
    missing = sorted(set(expected) - present)
    if missing:
        raise ValueError("compiled recorder does not contain required authored input(s): " + ", ".join(missing))


def _read_log(path: Path) -> str:
    if not project.nonempty(path):
        raise ValueError("missing or empty XeLaTeX log")
    return path.read_text(encoding="utf-8", errors="replace")


def _record_path(root: Path, qa: dict) -> Path:
    return project.local(root, qa["build_record"])


def recorder_name(qa: dict) -> str:
    return qa.get("recorder") or Path(qa["build_record"]).with_suffix(".fls").as_posix()


def validate_destinations(root: Path, target_id: str, qa: dict) -> None:
    """Keep compiler outputs on fixed build paths; QA metadata cannot redirect writes."""
    expected = {
        "path": f"build/{target_id}.pdf",
        "log": f"build/{target_id}.log",
        "build_record": "build/compile.txt" if target_id == "main" else f"build/{target_id}.compile.txt",
        "recorder": "build/compile.fls" if target_id == "main" else f"build/{target_id}.compile.fls",
    }
    if any(qa.get(key) != value for key, value in expected.items() if key != "recorder"):
        raise ValueError("compile QA destinations must use the standard build PDF/log/record paths")
    if recorder_name(qa) != expected["recorder"]:
        raise ValueError("compile recorder destination must use the standard build path")
    destinations = [project.local(root, qa[key]) for key in ("path", "log", "build_record")]
    destinations.append(project.local(root, expected["recorder"]))
    build_root = project.local(root, "build").resolve()
    normalized = [path.resolve() for path in destinations]
    if any(not _under(path, build_root) for path in normalized):
        raise ValueError("compiler outputs must stay inside build/")
    if len(set(normalized)) != len(normalized):
        raise ValueError("PDF, log, recorder, and build receipt destinations must be distinct")


def invalidate_build_record(root: Path, target_id: str, qa: dict, reason: str) -> None:
    """Invalidate an old successful receipt before preflight or compilation starts."""
    validate_destinations(root, target_id, qa)
    path = _record_path(root, qa)
    project.save(path, {"schema": SCHEMA, "status": "failed", "target_id": target_id,
                        "started_at_utc": now(), "completed_at_utc": now(),
                        "failure": reason, "passes": []})


def _set_failure(record: dict, record_path: Path, message: str) -> None:
    record.update(status="failed", completed_at_utc=now(), failure=message)
    project.save(record_path, record)


def begin_receipt(root: Path, target_id: str, qa: dict, layout_name: str, engine: str,
                  max_pages: int, expected_inputs: Iterable[str]) -> tuple[dict, Path]:
    record_path = _record_path(root, qa)
    layout = project.local(root, layout_name)
    stage = project.local(root, "build/" + ".latex-" + re.sub(r"[^A-Za-z0-9_-]", "_", target_id)
                          + "-" + uuid.uuid4().hex)
    stage.mkdir()
    lock_path = root / "content-lock.json"
    if not lock_path.is_file() or project.load(lock_path) != project.snapshot(root):
        raise ValueError("Content differs from reviewed lock before compile")
    expected = sorted(set(expected_inputs))
    record = {
        "schema": SCHEMA, "status": "started", "target_id": target_id,
        "started_at_utc": now(), "completed_at_utc": None,
        "command_engine": str(Path(engine).resolve()), "layout": layout_name,
        "layout_sha256": sha256(layout), "content_lock_sha256": sha256(lock_path),
        "snapshot_sha256": _json_digest(project.snapshot(root)),
        "expected_inputs": expected, "max_pages": max_pages,
        "staging_dir": stage.relative_to(root).as_posix(), "passes": [],
        "system_roots": _system_roots(engine),
    }
    project.save(record_path, record)
    return record, stage


def compile_target(root: Path, target_id: str, qa: dict, layout_name: str, engine: str,
                   max_pages: int, expected_inputs: Iterable[str]) -> dict:
    """Compile to a fresh staging directory and persist a successful receipt only after validation."""
    root = root.resolve()
    (root / "build").mkdir(parents=True, exist_ok=True)
    record_path = _record_path(root, qa)
    record = None
    stage = None
    try:
        validate_destinations(root, target_id, qa)
        record, stage = begin_receipt(root, target_id, qa, layout_name, engine, max_pages, expected_inputs)
        jobname = re.sub(r"[^A-Za-z0-9_-]", "_", target_id)
        layout = project.local(root, layout_name)
        expected_pdf = stage / (jobname + ".pdf")
        expected_log = stage / (jobname + ".log")
        expected_fls = stage / (jobname + ".fls")
        cmd = [str(engine), "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
               "-file-line-error", "-recorder", "-output-directory=" + str(stage.resolve()),
               "-jobname=" + jobname, layout.relative_to(root).as_posix()]
        if os.name == "nt" and any(part.casefold() == "miktex" for part in Path(engine).parts):
            cmd.insert(1, "-disable-installer")
        previous_aux: dict[str, str] | None = None
        previous_manifest: dict | None = None
        final_trace = None
        final_log = ""
        final_manifest = None
        all_outputs: set[str] = set()
        stable = False
        for attempt in range(1, MAX_PASSES + 1):
            # A zero exit without writing current-pass artifacts must not reuse the previous pass.
            for artifact in (expected_pdf, expected_log, expected_fls):
                if artifact.exists():
                    if not artifact.is_file():
                        raise ValueError("expected compiler artifact path is not a file: " + str(artifact))
                    artifact.unlink()
            try:
                result = subprocess.run(cmd, cwd=root, capture_output=True, timeout=TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                pass_record = {"pass": attempt, "status": "timeout", "returncode": None,
                               "stdout": _decode(getattr(exc, "stdout", b""))[-12000:],
                               "stderr": _decode(getattr(exc, "stderr", b""))[-12000:]}
                record["passes"].append(pass_record)
                project.save(record_path, record)
                raise ValueError(f"{target_id}: XeLaTeX timed out after {TIMEOUT_SECONDS}s") from exc
            pass_record = {"pass": attempt, "status": "finished", "returncode": result.returncode,
                           "stdout": _decode(result.stdout)[-12000:], "stderr": _decode(result.stderr)[-12000:]}
            record["passes"].append(pass_record)
            project.save(record_path, record)
            if result.returncode != 0:
                raise ValueError(f"{target_id}: XeLaTeX failed with exit code {result.returncode}; inspect build record")
            for artifact, description in ((expected_pdf, "PDF"), (expected_log, "log"), (expected_fls, "recorder")):
                if not project.nonempty(artifact):
                    raise ValueError(f"{target_id}: successful XeLaTeX pass did not create a fresh {description}")
            trace = parse_fls(expected_fls)
            _validate_trace_scope(root, stage, trace)
            all_outputs.update(trace["outputs"])
            manifest = _manifest(root, trace, stage, all_outputs, record["system_roots"])
            _require_expected(manifest, record["expected_inputs"])
            log_text = _read_log(expected_log)
            if HARD_FATAL.search(log_text):
                raise ValueError(f"{target_id}: unresolved LaTeX diagnostics")
            if jobname + ".pdf" not in re.sub(r"\s+", "", log_text):
                raise ValueError(f"{target_id}: fresh log does not report writing the expected PDF")
            aux_outputs = {}
            for raw in trace["outputs"]:
                output = Path(raw)
                if _under(output.resolve(), stage.resolve()) and _is_auxiliary(output):
                    if not output.is_file():
                        raise ValueError("recorder-listed compiler output is missing: " + raw)
                    if output.suffix.casefold() not in {".pdf", ".log", ".fls", ".synctex"}:
                        aux_outputs[raw] = sha256(output)
            manifest_is_stable = previous_manifest == manifest
            aux_is_stable = previous_aux == aux_outputs
            if (attempt >= 2 and manifest_is_stable and aux_is_stable
                    and not RERUN.search(log_text) and not UNRESOLVED_REFS.search(log_text)):
                stable = True
                final_trace, final_log, final_manifest = trace, log_text, manifest
                break
            previous_manifest, previous_aux = manifest, aux_outputs
            final_trace, final_log, final_manifest = trace, log_text, manifest
        if not stable:
            raise ValueError(f"{target_id}: XeLaTeX outputs/references did not stabilize within {MAX_PASSES} passes")

        from pypdf import PdfReader
        page_count = len(PdfReader(str(expected_pdf)).pages)
        if not 1 <= page_count <= max_pages:
            raise ValueError(f"{target_id}: actual PDF page count {page_count} is outside 1-{max_pages}")
        if not any(Path(raw).resolve() == expected_log.resolve() for raw in final_trace["outputs"]):
            raise ValueError(f"{target_id}: final recorder does not list the expected log as OUTPUT")

        # Recheck after the last XeLaTeX pass. The lock and authored dependencies must still match.
        lock_path = root / "content-lock.json"
        if project.load(lock_path) != project.snapshot(root):
            raise ValueError("Content/evidence changed during compile; discard the build and re-lock after review")
        if sha256(lock_path) != record["content_lock_sha256"]:
            raise ValueError("Content lock changed during compile")
        if sha256(project.local(root, layout_name)) != record["layout_sha256"]:
            raise ValueError("Layout changed during compile")
        current_manifest = _manifest(root, final_trace, stage, all_outputs, record["system_roots"])
        if current_manifest != final_manifest:
            raise ValueError("Authored TeX inputs changed during compile; rebuild after stabilizing files")
        _require_expected(current_manifest, record["expected_inputs"])

        # Publish stable artifacts at the QA paths; the unique staging directory remains isolated.
        published = {}
        for key, staged in (("path", expected_pdf), ("log", expected_log)):
            destination = project.local(root, qa[key])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staged, destination)
            published[qa[key]] = sha256(destination)
        published_recorder_name = recorder_name(qa)
        recorder_destination = project.local(root, published_recorder_name)
        shutil.copyfile(expected_fls, recorder_destination)
        published[published_recorder_name] = sha256(recorder_destination)

        record.update(status="success", completed_at_utc=now(), stable_passes=len(record["passes"]),
                      page_count=page_count, recorder=published_recorder_name,
                      command=cmd,
                      final_inputs=current_manifest,
                      final_trace={"pwd": final_trace["pwd"], "inputs": final_trace["inputs"],
                                   "outputs": final_trace["outputs"],
                                   "relative_inputs": final_trace.get("relative_inputs", [])},
                      generated_outputs=sorted(all_outputs),
                      final_trace_sha256=sha256(expected_fls),
                      published_artifacts=published,
                      log_sha256=sha256(project.local(root, qa["log"])),
                      pdf_sha256=sha256(project.local(root, qa["path"])))
        project.save(record_path, record)
        return record
    except Exception as exc:
        if record is None:
            # Even preflight failures must replace an older success receipt.
            record = {"schema": SCHEMA, "status": "failed", "target_id": target_id,
                      "started_at_utc": now(), "completed_at_utc": now(), "failure": str(exc), "passes": []}
            try:
                validate_destinations(root, target_id, qa)
                project.save(record_path, record)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        elif record.get("status") != "failed":
            _set_failure(record, record_path, str(exc))
        raise


def _decode(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def validate_receipt(root: Path, qa: dict, expected_inputs: Iterable[str] | None = None) -> list[str]:
    """Check that the current lock, inputs, recorder, and published artifacts match a real success receipt."""
    root = root.resolve()
    errors = []
    try:
        record_path = _record_path(root, qa)
        try:
            record = project.load(record_path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return ["missing/invalid successful XeLaTeX receipt; rerun the supported compile command, then redo PDF QA"]
        if not isinstance(record, dict) or record.get("schema") != SCHEMA:
            return ["legacy or unsupported build record; recompile with book.py compile or project.py compile, then redo PDF QA"]
        validate_destinations(root, record.get("target_id", ""), qa)
        if record.get("status") != "success":
            return ["latest XeLaTeX attempt is not successful; recompile before PDF review/release"]
        passes = record.get("passes")
        stable_passes = record.get("stable_passes")
        if (not isinstance(passes, list) or not isinstance(stable_passes, int)
                or stable_passes < 2 or len(passes) != stable_passes
                or any(not isinstance(p, dict) or p.get("status") != "finished"
                       or p.get("returncode") != 0 or p.get("pass") != n
                       for n, p in enumerate(passes, start=1))):
            errors.append("successful receipt has malformed or unsuccessful pass history")
        command = record.get("command")
        if not isinstance(command, list) or not all(flag in command for flag in
                ("-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-recorder")):
            errors.append("successful receipt does not prove the required safe recorder command")
        elif len(command) < 8:
            errors.append("successful receipt has an incomplete XeLaTeX command")
        else:
            command_engine = str(record.get("command_engine", ""))
            if Path(str(command[0])).resolve() != Path(command_engine).resolve():
                errors.append("successful receipt command engine differs from the recorded engine")
            if os.name == "nt" and any(part.casefold() == "miktex" for part in Path(command_engine).parts) \
                    and "-disable-installer" not in command:
                errors.append("MiKTeX build receipt must disable package installation")
            expected_stage = project.local(root, record.get("staging_dir", ""))
            if "-output-directory=" + str(expected_stage.resolve()) not in command:
                errors.append("successful receipt command did not use its fresh staging directory")
            if ("-jobname=" + str(record.get("target_id")) not in command
                    or command[-1] != Path(str(record.get("layout", ""))).as_posix()):
                errors.append("successful receipt command does not match its target/layout")
        if record.get("completed_at_utc") is None or record.get("started_at_utc") is None:
            errors.append("successful receipt is missing build timestamps")
        if type(record.get("page_count")) is not int or not 1 <= record.get("page_count", 0) <= record.get("max_pages", 0):
            errors.append("successful receipt has an invalid actual page count")
        if record.get("recorder") != recorder_name(qa):
            errors.append("QA recorder path differs from successful build receipt")
        if not isinstance(record.get("stable_passes"), int) or record["stable_passes"] < 2:
            errors.append("successful build receipt must prove at least two stable XeLaTeX passes")
        lock_path = root / "content-lock.json"
        if not lock_path.is_file() or project.load(lock_path) != project.snapshot(root):
            errors.append("content/evidence differs from the reviewed lock")
        elif sha256(lock_path) != record.get("content_lock_sha256"):
            errors.append("receipt is tied to a different content lock; recompile and redo PDF QA")
        if _json_digest(project.snapshot(root)) != record.get("snapshot_sha256"):
            errors.append("receipt is tied to a different reviewed content snapshot")
        layout_name = record.get("layout")
        if not isinstance(layout_name, str):
            errors.append("receipt is missing its layout path")
        else:
            layout = project.local(root, layout_name)
            if not layout.is_file() or sha256(layout) != record.get("layout_sha256"):
                errors.append("layout changed since successful compilation; recompile and redo PDF QA")
        artifact_names = [qa.get("path"), qa.get("log"), qa.get("build_record"), record.get("recorder")]
        for name in artifact_names:
            if not isinstance(name, str):
                errors.append("receipt is missing a required build artifact path")
                continue
            path = project.local(root, name)
            if not project.nonempty(path):
                errors.append("missing/empty build artifact: " + name)
        if errors:
            return errors
        published = record.get("published_artifacts", {})
        for name in (qa["path"], qa["log"], record["recorder"]):
            path = project.local(root, name)
            if published.get(name) != sha256(path):
                errors.append("build artifact changed since successful compilation: " + name)
        if record.get("pdf_sha256") != sha256(project.local(root, qa["path"])):
            errors.append("PDF bytes do not match successful build receipt")
        if record.get("log_sha256") != sha256(project.local(root, qa["log"])):
            errors.append("log bytes do not match successful build receipt")
        if errors:
            return errors
        if record.get("final_trace_sha256") != sha256(project.local(root, record["recorder"])):
            errors.append("recorder hash differs from successful build receipt")
        log_text = _read_log(project.local(root, qa["log"]))
        if HARD_FATAL.search(log_text) or RERUN.search(log_text) or UNRESOLVED_REFS.search(log_text):
            errors.append("successful build log now contains LaTeX errors or unresolved cross-reference warnings")
        elif re.sub(r"\s+", "", record["target_id"] + ".pdf") not in re.sub(r"\s+", "", log_text):
            errors.append("successful build log does not report writing the expected PDF")
        try:
            from pypdf import PdfReader
            actual_pages = len(PdfReader(str(project.local(root, qa["path"]))).pages)
            if actual_pages != record.get("page_count"):
                errors.append("PDF page count differs from successful compile receipt")
        except Exception as exc:
            errors.append(f"cannot confirm PDF page count from successful receipt: {type(exc).__name__}: {exc}")
        if errors:
            return errors
        fls_path = project.local(root, record["recorder"])
        if record.get("published_artifacts", {}).get(record["recorder"]) != sha256(fls_path):
            errors.append("recorder changed since successful compilation")
            return errors
        parsed = parse_fls(fls_path)
        _validate_trace_scope(root, project.local(root, record.get("staging_dir", "")), parsed)
        if (sorted(parsed["inputs"]) != sorted(record.get("final_trace", {}).get("inputs", []))
                or sorted(parsed.get("relative_inputs", [])) != sorted(record.get("final_trace", {}).get("relative_inputs", []))):
            errors.append("recorder INPUT set differs from successful compile receipt")
        if sorted(parsed["outputs"]) != sorted(record.get("final_trace", {}).get("outputs", [])):
            errors.append("recorder OUTPUT set differs from successful compile receipt")
        staging = project.local(root, record.get("staging_dir", ""))
        jobname = re.sub(r"[^A-Za-z0-9_-]", "_", record["target_id"])
        staged_pdf, staged_log = staging / (jobname + ".pdf"), staging / (jobname + ".log")
        if not project.nonempty(staged_pdf) or not project.nonempty(staged_log):
            errors.append("fresh staged PDF/log are missing; recompile before PDF review/release")
        else:
            if sha256(staged_pdf) != sha256(project.local(root, qa["path"])):
                errors.append("published PDF differs from the fresh staged XeLaTeX output")
            if sha256(staged_log) != sha256(project.local(root, qa["log"])):
                errors.append("published log differs from the fresh staged XeLaTeX output")
        manifest = _manifest(root, parsed, staging, set(record.get("generated_outputs", [])),
                             record.get("system_roots", []))
        if manifest != record.get("final_inputs"):
            errors.append("compiled input manifest changed; recompile and redo PDF QA")
        required = expected_inputs if expected_inputs is not None else record.get("expected_inputs", [])
        try:
            _require_expected(manifest, required)
        except ValueError as exc:
            errors.append(str(exc))
        if record.get("expected_inputs") != sorted(set(required)):
            errors.append("receipt does not cover the current required authored inputs")
        return errors
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f"invalid XeLaTeX receipt/recorder: {type(exc).__name__}: {exc}"]

