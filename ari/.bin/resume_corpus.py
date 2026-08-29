#!/usr/bin/env python3
"""Maintain and scan Ari's private resume-corpus manifest.

The implementation is intentionally candidate-agnostic so it can be tracked in
the public Borg repository. Candidate-specific paths and hashes live only in the
gitignored manifest supplied at runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
BULLET_ID_RE = re.compile(r"^RB-[0-9]+$")
IGNORED_DIRS = {"Older Resumes"}


class CorpusError(Exception):
    """A user-actionable corpus error."""


@dataclass(frozen=True)
class CandidateFile:
    path: Path
    relative: str
    suffix: str
    mtime: float


@dataclass(frozen=True)
class Finding:
    kind: str
    paths: tuple[str, ...]
    reason: str


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: str, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CorpusError(f"{label} must include a timezone")
    return parsed


def format_time(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def validate_relative_path(value: Any, suffix: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorpusError(f"{label} must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise CorpusError(f"{label} must be a normalized relative path")
    if any(part in IGNORED_DIRS for part in path.parts):
        raise CorpusError(f"{label} must identify an active resume, not an archive")
    if path.suffix.lower() != suffix:
        raise CorpusError(f"{label} must end in {suffix}")
    if ignored_name(path.name):
        raise CorpusError(f"{label} identifies a temporary or backup file")
    return path.as_posix()


def validate_manifest(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise CorpusError("manifest root must be an object")
    if data.get("schemaVersion") != SCHEMA_VERSION:
        raise CorpusError(f"schemaVersion must be {SCHEMA_VERSION}")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise CorpusError("artifacts must be an array")

    ids: set[str] = set()
    docx_paths: set[str] = set()
    pdf_paths: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            raise CorpusError(f"{prefix} must be an object")
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise CorpusError(f"{prefix}.id must be a non-empty string")
        if artifact_id in ids:
            raise CorpusError(f"duplicate artifact id: {artifact_id}")
        ids.add(artifact_id)

        docx_path = validate_relative_path(artifact.get("docxPath"), ".docx", f"{prefix}.docxPath")
        pdf_path = validate_relative_path(artifact.get("pdfPath"), ".pdf", f"{prefix}.pdfPath")
        if docx_path in docx_paths:
            raise CorpusError(f"duplicate DOCX path: {docx_path}")
        if pdf_path in pdf_paths:
            raise CorpusError(f"duplicate PDF path: {pdf_path}")
        docx_paths.add(docx_path)
        pdf_paths.add(pdf_path)

        for key in ("docxSha256", "pdfSha256"):
            value = artifact.get(key)
            if not isinstance(value, str) or not HASH_RE.fullmatch(value):
                raise CorpusError(f"{prefix}.{key} must be a lowercase SHA-256")
        for key in ("finalizedAt", "harvestedAt"):
            value = artifact.get(key)
            if not isinstance(value, str):
                raise CorpusError(f"{prefix}.{key} must be a timestamp string")
            parse_time(value, f"{prefix}.{key}")
        if artifact.get("status") not in {"final", "submitted"}:
            raise CorpusError(f"{prefix}.status must be final or submitted")
        bullet_ids = artifact.get("bulletIds")
        if not isinstance(bullet_ids, list) or any(
            not isinstance(item, str) or not BULLET_ID_RE.fullmatch(item) for item in bullet_ids
        ):
            raise CorpusError(f"{prefix}.bulletIds must be an array of RB-NNN identifiers")
        if len(set(bullet_ids)) != len(bullet_ids):
            raise CorpusError(f"{prefix}.bulletIds contains duplicates")
        for key in ("baselineId", "supersedesId"):
            value = artifact.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise CorpusError(f"{prefix}.{key} must be null or a non-empty string")
    return data


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CorpusError(f"manifest not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusError(f"cannot read valid JSON manifest {path}: {exc}") from exc
    return validate_manifest(data)


def write_manifest_atomic(path: Path, data: dict[str, Any]) -> None:
    validate_manifest(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temp_name = handle.name
            json.dump(data, handle, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    load_manifest(path)


def ignored_name(name: str) -> bool:
    lowered = name.lower()
    return (
        name.startswith("~$")
        or name == ".DS_Store"
        or lowered.endswith("~")
        or ".bak" in lowered
        or lowered.startswith(".tmp.")
        or ".tmp." in lowered
    )


def is_active_file(path: Path, resume_dir: Path) -> bool:
    try:
        relative = path.relative_to(resume_dir)
    except ValueError:
        return False
    return (
        path.is_file()
        and path.suffix.lower() in {".docx", ".pdf"}
        and not ignored_name(path.name)
        and not any(part in IGNORED_DIRS for part in relative.parts)
    )


def collect_files(resume_dir: Path) -> dict[str, CandidateFile]:
    if not resume_dir.is_dir():
        raise CorpusError(f"resume directory not found: {resume_dir}")
    result: dict[str, CandidateFile] = {}
    try:
        paths = resume_dir.rglob("*")
        for path in paths:
            if not is_active_file(path, resume_dir):
                continue
            stat = path.stat()
            relative = path.relative_to(resume_dir).as_posix()
            result[relative] = CandidateFile(path, relative, path.suffix.lower(), stat.st_mtime)
    except OSError as exc:
        raise CorpusError(f"cannot scan resume directory reliably: {exc}") from exc
    return result


def stable_hash(path: Path) -> str:
    try:
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
    except OSError as exc:
        raise CorpusError(f"cannot hash {path}: {exc}") from exc
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise CorpusError(f"file changed while being hashed: {path}")
    return digest.hexdigest()


def old_enough(file: CandidateFile, now: dt.datetime, minimum_age_hours: float) -> bool:
    return now.timestamp() - file.mtime >= minimum_age_hours * 3600


def scan_corpus(
    resume_dir: Path,
    manifest: dict[str, Any],
    now: dt.datetime,
    minimum_age_hours: float,
) -> list[Finding]:
    files = collect_files(resume_dir)
    findings: list[Finding] = []
    represented: set[str] = set()

    for artifact in manifest["artifacts"]:
        docx_rel = artifact["docxPath"]
        pdf_rel = artifact["pdfPath"]
        represented.update((docx_rel, pdf_rel))
        docx = files.get(docx_rel)
        pdf = files.get(pdf_rel)
        missing = tuple(path for path, item in ((docx_rel, docx), (pdf_rel, pdf)) if item is None)
        if missing:
            findings.append(Finding("missing-recorded-file", missing, "manifest entry points to a missing file"))
            continue

        assert docx is not None and pdf is not None
        docx_changed = stable_hash(docx.path) != artifact["docxSha256"]
        pdf_changed = stable_hash(pdf.path) != artifact["pdfSha256"]
        if pdf_changed:
            findings.append(
                Finding("changed-pdf", (docx_rel, pdf_rel), "PDF changed since harvest; export is a strong review signal")
            )
        elif docx_changed and old_enough(docx, now, minimum_age_hours):
            findings.append(
                Finding("changed-docx", (docx_rel,), f"DOCX changed since harvest and is stable for {minimum_age_hours:g}+ hours")
            )

    stems: dict[str, dict[str, CandidateFile]] = {}
    for relative, file in files.items():
        if relative in represented:
            continue
        key = str(PurePosixPath(relative).with_suffix(""))
        stems.setdefault(key, {})[file.suffix] = file

    for key in sorted(stems):
        pair = stems[key]
        docx = pair.get(".docx")
        pdf = pair.get(".pdf")
        if docx and pdf:
            findings.append(
                Finding("unmanifested-pair", (docx.relative, pdf.relative), "DOCX/PDF pair is not in the harvested manifest")
            )
        elif pdf:
            findings.append(Finding("pdf-without-docx", (pdf.relative,), "PDF has no matching editable DOCX"))
        elif docx and old_enough(docx, now, minimum_age_hours):
            findings.append(
                Finding("docx-without-pdf", (docx.relative,), f"DOCX has no PDF and is stable for {minimum_age_hours:g}+ hours")
            )

    findings.sort(key=lambda item: (item.kind, item.paths))
    return findings


def render_markdown(findings: list[Finding], now: dt.datetime) -> str:
    if not findings:
        return ""
    lines = [
        f"# Pending resume harvest — {now.astimezone().date().isoformat()}",
        "",
        f"{len(findings)} resume artifact issue(s) need review. No files or manifest records were changed.",
        "",
        "| Signal | Artifact(s) | Reason |",
        "|---|---|---|",
    ]
    for finding in findings:
        paths = "<br>".join(path.replace("|", "\\|") for path in finding.paths)
        reason = finding.reason.replace("|", "\\|")
        lines.append(f"| {finding.kind} | {paths} | {reason} |")
    lines.extend(("", "Run `/finalize-resume <DOCX path or name>` to verify and harvest an artifact."))
    return "\n".join(lines) + "\n"


def resolve_resume(resume_dir: Path, query: str) -> Path:
    files = collect_files(resume_dir)
    docx_files = [item for item in files.values() if item.suffix == ".docx"]
    if not query.strip():
        raise CorpusError("provide a DOCX path or resume name")

    raw = Path(query).expanduser()
    exact_candidates: list[Path] = []
    if raw.is_absolute():
        exact_candidates.append(raw)
    else:
        exact_candidates.append(resume_dir / raw)
    for candidate in exact_candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(resume_dir.resolve())
        except (FileNotFoundError, OSError, ValueError):
            continue
        if not is_active_file(resolved, resume_dir) or resolved.suffix.lower() != ".docx":
            raise CorpusError("resolved target is not an active DOCX resume")
        return resolved

    lowered = query.casefold()
    exact = [item.path for item in docx_files if item.path.name.casefold() == lowered or item.path.stem.casefold() == lowered]
    matches = exact or [
        item.path
        for item in docx_files
        if lowered in item.path.name.casefold() or lowered in item.relative.casefold()
    ]
    if not matches:
        raise CorpusError(f"no active DOCX resume matches: {query}")
    if len(matches) > 1:
        relative = sorted(path.relative_to(resume_dir).as_posix() for path in matches)
        raise CorpusError("ambiguous resume name; matches: " + ", ".join(relative))
    return matches[0].resolve()


def normalized_record_path(resume_dir: Path, raw: str, suffix: str) -> tuple[Path, str]:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = resume_dir / path
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(resume_dir.resolve()).as_posix()
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise CorpusError(f"record path is missing or outside the resume directory: {raw}") from exc
    validate_relative_path(relative, suffix, "record path")
    return resolved, relative


def record_artifact(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    resume_dir = Path(args.resume_dir)
    manifest = load_manifest(manifest_path)
    docx_path, docx_rel = normalized_record_path(resume_dir, args.docx, ".docx")
    pdf_path, pdf_rel = normalized_record_path(resume_dir, args.pdf, ".pdf")
    if PurePosixPath(docx_rel).with_suffix("") != PurePosixPath(pdf_rel).with_suffix(""):
        raise CorpusError("DOCX and PDF must have the same relative stem")

    timestamp = format_time(parse_time(args.now, "--now") if args.now else utc_now())
    artifact = {
        "id": args.artifact_id,
        "docxPath": docx_rel,
        "pdfPath": pdf_rel,
        "docxSha256": stable_hash(docx_path),
        "pdfSha256": stable_hash(pdf_path),
        "finalizedAt": timestamp,
        "harvestedAt": timestamp,
        "status": args.status,
        "bulletIds": sorted(set(args.bullet_id)),
        "baselineId": args.baseline_id,
        "supersedesId": args.supersedes_id,
    }

    replaced = False
    for index, existing in enumerate(manifest["artifacts"]):
        if existing["id"] == args.artifact_id:
            manifest["artifacts"][index] = artifact
            replaced = True
            break
    if not replaced:
        manifest["artifacts"].append(artifact)
    manifest["artifacts"].sort(key=lambda item: item["id"])
    write_manifest_atomic(manifest_path, manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate a manifest")
    validate_parser.add_argument("--manifest", required=True)

    scan_parser = subparsers.add_parser("scan", help="report unharvested or changed artifacts")
    scan_parser.add_argument("--resume-dir", required=True)
    scan_parser.add_argument("--manifest", required=True)
    scan_parser.add_argument("--minimum-age-hours", type=float, default=48.0)
    scan_parser.add_argument("--now", help="ISO-8601 time override for deterministic tests")

    resolve_parser = subparsers.add_parser("resolve", help="resolve an unambiguous active DOCX")
    resolve_parser.add_argument("--resume-dir", required=True)
    resolve_parser.add_argument("query")

    record_parser = subparsers.add_parser("record", help="atomically record a successful finalization and harvest")
    record_parser.add_argument("--resume-dir", required=True)
    record_parser.add_argument("--manifest", required=True)
    record_parser.add_argument("--artifact-id", required=True)
    record_parser.add_argument("--docx", required=True)
    record_parser.add_argument("--pdf", required=True)
    record_parser.add_argument("--status", choices=("final", "submitted"), default="final")
    record_parser.add_argument("--bullet-id", action="append", default=[])
    record_parser.add_argument("--baseline-id")
    record_parser.add_argument("--supersedes-id")
    record_parser.add_argument("--now", help="ISO-8601 time override for deterministic tests")

    subparsers.add_parser("new-id", help="generate a stable opaque artifact id")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            load_manifest(Path(args.manifest))
        elif args.command == "scan":
            now = parse_time(args.now, "--now") if args.now else utc_now()
            if args.minimum_age_hours < 0:
                raise CorpusError("--minimum-age-hours cannot be negative")
            manifest = load_manifest(Path(args.manifest))
            findings = scan_corpus(Path(args.resume_dir), manifest, now, args.minimum_age_hours)
            sys.stdout.write(render_markdown(findings, now))
        elif args.command == "resolve":
            print(resolve_resume(Path(args.resume_dir), args.query))
        elif args.command == "record":
            record_artifact(args)
        elif args.command == "new-id":
            print(f"resume-{uuid.uuid4()}")
        else:
            parser.error("unknown command")
    except CorpusError as exc:
        print(f"resume-corpus: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
