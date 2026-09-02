#!/usr/bin/env python3
"""Manage Ari's private career-dossier provenance and approval workflow.

The implementation is candidate-agnostic and safe to track. Candidate facts,
source paths, proposal wording, and publication digests remain in the private
files supplied at runtime.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable


SCHEMA_VERSION = 1
CLAIM_ID_RE = re.compile(r"^RB-[0-9]{3,}$")
HEADING_RE = re.compile(r"^### (RB-[0-9]{3,}) — (.+)$", re.MULTILINE)
FIELD_RE = re.compile(r"^- \*\*(.+?):\*\*\s*(.*)$", re.MULTILINE)
PRIVATE_PATH_RE = re.compile(r"`\.private/Resumes/([^`]+\.(?:docx|pdf))`")
DATE_RE = re.compile(r"\b(20[0-9]{2}-[0-9]{2}-[0-9]{2})\b")
DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


class PublicationError(Exception):
    """A user-actionable publication error."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def format_time(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise PublicationError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise PublicationError(f"{label} must include a timezone")
    return parsed


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def digest_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    except OSError as exc:
        raise PublicationError(f"cannot hash source artifact: {path.name}") from exc
    return "sha256:" + hasher.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"cannot read valid JSON: {path}") from exc


def atomic_write(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    atomic_write(path, stable_json(value), mode)


def parse_bullet_bank(path: Path) -> dict[str, dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PublicationError(f"cannot read evidence bank: {path}") from exc
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        raise PublicationError("evidence bank contains no RB claim headings")
    entries: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        claim_id, title = match.groups()
        if claim_id in entries:
            raise PublicationError(f"duplicate evidence-bank claim: {claim_id}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.end():end].strip()
        fields = {name: value.strip() for name, value in FIELD_RE.findall(section)}
        entries[claim_id] = {
            "id": claim_id,
            "title": title.strip(),
            "status": fields.get("Status", ""),
            "section": "\n".join(line.rstrip() for line in section.splitlines()).strip(),
            "sourcePaths": sorted(set(PRIVATE_PATH_RE.findall(section))),
            "confirmationDates": sorted(set(DATE_RE.findall(fields.get("Candidate confirmation", "")))),
        }
    return entries


def validate_resume_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != 1 or not isinstance(value.get("artifacts"), list):
        raise PublicationError("resume corpus manifest has an invalid root contract")
    ids: set[str] = set()
    for artifact in value["artifacts"]:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("id"), str):
            raise PublicationError("resume corpus manifest contains an invalid artifact")
        if artifact["id"] in ids:
            raise PublicationError(f"duplicate resume artifact ID: {artifact['id']}")
        ids.add(artifact["id"])
        if not isinstance(artifact.get("bulletIds"), list):
            raise PublicationError(f"resume artifact {artifact['id']} has invalid bulletIds")
    return value


def source_id(relative_path: str) -> str:
    token = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:20]
    return f"resume-source-{token}"


def build_provenance(entries: dict[str, dict[str, Any]], resume_manifest: dict[str, Any]) -> dict[str, Any]:
    path_artifacts: dict[str, list[str]] = {}
    artifact_by_id: dict[str, dict[str, Any]] = {}
    for artifact in resume_manifest["artifacts"]:
        artifact_by_id[artifact["id"]] = artifact
        for key in ("docxPath", "pdfPath"):
            if isinstance(artifact.get(key), str):
                path_artifacts.setdefault(artifact[key], []).append(artifact["id"])

    source_artifacts: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    retired_to_successor: dict[str, str] = {}
    for claim_id, entry in entries.items():
        if entry["status"] == "retired":
            successor = re.search(r"\b(RB-[0-9]{3,})\b", entry["section"])
            if successor:
                retired_to_successor[claim_id] = successor.group(1)

    for claim_id in sorted(entries):
        entry = entries[claim_id]
        if entry["status"] == "retired":
            continue
        artifact_ids: set[str] = set()
        for relative in entry["sourcePaths"]:
            normalized = PurePosixPath(relative).as_posix()
            matched = path_artifacts.get(normalized, [])
            if matched:
                for artifact_id in matched:
                    artifact_ids.add(artifact_id)
                    source_artifacts[artifact_id] = {
                        "id": artifact_id,
                        "kind": "resume-manifest",
                        "manifestArtifactId": artifact_id,
                    }
            else:
                artifact_id = source_id(normalized)
                artifact_ids.add(artifact_id)
                source_artifacts[artifact_id] = {
                    "id": artifact_id,
                    "kind": "resume-file",
                    "relativePath": normalized,
                }
        if not artifact_ids:
            artifact_id = f"candidate-confirmation-{claim_id.lower()}"
            artifact_ids.add(artifact_id)
            source_artifacts[artifact_id] = {
                "id": artifact_id,
                "kind": "candidate-confirmation",
                "claimId": claim_id,
            }
        dates = entry["confirmationDates"]
        confirmations = [
            {
                "confirmedAt": f"{date}T00:00:00Z",
                "note": "Candidate confirmation recorded in the private evidence bank.",
            }
            for date in dates
        ]
        claims.append({
            "schemaVersion": SCHEMA_VERSION,
            "claimId": claim_id,
            "sourceArtifactIds": sorted(artifact_ids),
            "confirmationHistory": confirmations,
            "supersedes": sorted(retired for retired, successor in retired_to_successor.items() if successor == claim_id),
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceArtifacts": [source_artifacts[key] for key in sorted(source_artifacts)],
        "claims": claims,
    }


def validate_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise PublicationError("provenance sidecar has an invalid root contract")
    sources = value.get("sourceArtifacts")
    claims = value.get("claims")
    if not isinstance(sources, list) or not isinstance(claims, list):
        raise PublicationError("provenance sidecar requires sourceArtifacts and claims arrays")
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise PublicationError("provenance contains an invalid source artifact")
        if source["id"] in source_ids:
            raise PublicationError(f"duplicate provenance source artifact: {source['id']}")
        source_ids.add(source["id"])
        if source.get("kind") not in {"resume-manifest", "resume-file", "candidate-confirmation"}:
            raise PublicationError(f"invalid provenance source kind: {source.get('kind')}")
    claim_ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict) or not CLAIM_ID_RE.fullmatch(str(claim.get("claimId", ""))):
            raise PublicationError("provenance contains an invalid claim mapping")
        claim_id = claim["claimId"]
        if claim_id in claim_ids:
            raise PublicationError(f"duplicate provenance claim: {claim_id}")
        claim_ids.add(claim_id)
        artifact_ids = claim.get("sourceArtifactIds")
        if not isinstance(artifact_ids, list) or not artifact_ids:
            raise PublicationError(f"provenance {claim_id} has no source artifacts")
        missing = sorted(set(artifact_ids) - source_ids)
        if missing:
            raise PublicationError(f"provenance {claim_id} has missing source artifacts: {', '.join(missing)}")
        if "claim" in claim or "title" in claim:
            raise PublicationError(f"provenance {claim_id} duplicates public claim prose")
    return value


def validate_publication_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise PublicationError("publication manifest has an invalid root contract")
    publications = value.get("publications")
    if not isinstance(publications, list):
        raise PublicationError("publication manifest requires a publications array")
    seen: set[str] = set()
    for entry in publications:
        if not isinstance(entry, dict) or not CLAIM_ID_RE.fullmatch(str(entry.get("claimId", ""))):
            raise PublicationError("publication manifest contains an invalid claim entry")
        claim_id = entry["claimId"]
        if claim_id in seen:
            raise PublicationError(f"duplicate publication entry: {claim_id}")
        seen.add(claim_id)
        for key in ("privateSourceDigest", "publicContentDigest"):
            if not DIGEST_RE.fullmatch(str(entry.get(key, ""))):
                raise PublicationError(f"publication {claim_id} has invalid {key}")
        parse_time(entry.get("approvedAt"), f"publication {claim_id}.approvedAt")
        parse_time(entry.get("exportedAt"), f"publication {claim_id}.exportedAt")
        if entry.get("status") not in {"published", "stale"}:
            raise PublicationError(f"publication {claim_id} has invalid status")
    return value


def provenance_maps(value: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    return (
        {source["id"]: source for source in value["sourceArtifacts"]},
        {claim["claimId"]: claim for claim in value["claims"]},
    )


def current_source_digest(
    claim_id: str,
    bullet_entries: dict[str, dict[str, Any]],
    provenance: dict[str, Any],
    resume_manifest: dict[str, Any],
    resumes_dir: Path,
) -> str:
    sources, claims = provenance_maps(provenance)
    claim = claims.get(claim_id)
    fact = bullet_entries.get(claim_id)
    if claim is None or fact is None:
        raise PublicationError(f"cannot resolve private source facts for {claim_id}")
    resume_by_id = {artifact["id"]: artifact for artifact in resume_manifest["artifacts"]}
    resolved: list[dict[str, Any]] = []
    for source_artifact_id in claim["sourceArtifactIds"]:
        source = sources[source_artifact_id]
        kind = source["kind"]
        if kind == "resume-manifest":
            artifact = resume_by_id.get(source.get("manifestArtifactId"))
            if artifact is None:
                raise PublicationError(f"missing resume manifest artifact for {claim_id}")
            if claim_id not in artifact["bulletIds"]:
                raise PublicationError(f"resume manifest artifact no longer selects {claim_id}")
            resolved.append({
                "id": source_artifact_id,
                "kind": kind,
                "docxSha256": artifact.get("docxSha256"),
                "pdfSha256": artifact.get("pdfSha256"),
            })
        elif kind == "resume-file":
            relative = PurePosixPath(source.get("relativePath", ""))
            if relative.is_absolute() or ".." in relative.parts:
                raise PublicationError(f"unsafe private resume path for {claim_id}")
            path = resumes_dir.joinpath(*relative.parts)
            if not path.is_file():
                raise PublicationError(f"private source artifact is missing for {claim_id}")
            resolved.append({"id": source_artifact_id, "kind": kind, "digest": file_digest(path)})
        else:
            resolved.append({"id": source_artifact_id, "kind": kind})
    normalized_fact = {
        "claimId": claim_id,
        "title": fact["title"],
        "status": fact["status"],
        "section": fact["section"],
        "provenance": claim,
        "sources": sorted(resolved, key=lambda item: item["id"]),
    }
    return digest_value(normalized_fact)


def validate_proposal(value: Any, require_seal: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise PublicationError("proposal has an invalid root contract")
    batch_id = value.get("batchId")
    if not isinstance(batch_id, str) or not re.fullmatch(r"BATCH-[0-9]{3,}", batch_id):
        raise PublicationError("proposal batchId must match BATCH-NNN")
    parse_time(value.get("createdAt"), "proposal.createdAt")
    claims = value.get("claims")
    if not isinstance(claims, list) or not claims:
        raise PublicationError("proposal requires at least one claim")
    ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict) or not CLAIM_ID_RE.fullmatch(str(claim.get("id", ""))):
            raise PublicationError("proposal contains an invalid claim")
        if claim["id"] in ids:
            raise PublicationError(f"proposal contains duplicate claim {claim['id']}")
        ids.add(claim["id"])
        if "approvedAt" in claim:
            raise PublicationError("unsealed proposal claims must not contain approvedAt")
        for required in (
            "schemaVersion", "type", "title", "claim", "status", "asOf", "skills",
            "evidenceIds", "limitations", "evidenceLevel", "visibility"
        ):
            if required not in claim:
                raise PublicationError(f"proposal {claim['id']} is missing {required}")
        if claim["visibility"] != "public" or not claim["limitations"]:
            raise PublicationError(f"proposal {claim['id']} must be public and include limitations")
    sealed = value.get("sealedApproval")
    if require_seal and not isinstance(sealed, dict):
        raise PublicationError("proposal has not been sealed for exact-diff approval")
    return value


def sealed_claims(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    sealed = proposal.get("sealedApproval")
    if not isinstance(sealed, dict):
        raise PublicationError("proposal is not sealed")
    approved_at = sealed.get("approvedAt")
    parse_time(approved_at, "sealedApproval.approvedAt")
    return [{**claim, "approvedAt": approved_at} for claim in proposal["claims"]]


def claim_diff(project_dir: Path, claims: Iterable[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for claim in sorted(claims, key=lambda item: item["id"]):
        relative = f"content/claims/{claim['id']}.json"
        path = project_dir / relative
        before = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
        after = stable_json(claim).splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(before, after, fromfile=f"a/{relative}", tofile=f"b/{relative}"))
    return "".join(chunks)


def preflight_project(project_dir: Path, claims: list[dict[str, Any]], runner: Callable[..., Any] = subprocess.run) -> None:
    with tempfile.TemporaryDirectory(prefix="dossier-publication-") as temporary:
        staged = Path(temporary) / "career-dossier"
        shutil.copytree(project_dir, staged, ignore=shutil.ignore_patterns("node_modules", "dist"))
        node_modules = project_dir / "node_modules"
        if not node_modules.is_dir():
            raise PublicationError("career-dossier/node_modules is missing; run npm ci before publication review")
        os.symlink(node_modules, staged / "node_modules", target_is_directory=True)
        for claim in claims:
            atomic_write_json(staged / "content" / "claims" / f"{claim['id']}.json", claim, 0o644)
        try:
            runner(["npm", "run", "verify"], cwd=staged, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PublicationError("candidate public records failed the full dossier verification suite") from exc


def initialize(args: argparse.Namespace) -> None:
    bullet_entries = parse_bullet_bank(Path(args.bullet_bank))
    manifest = validate_resume_manifest(load_json(Path(args.resume_manifest)))
    provenance = build_provenance(bullet_entries, manifest)
    validate_provenance(provenance)
    provenance_path = Path(args.provenance)
    publication_path = Path(args.publication_manifest)
    if provenance_path.exists() or publication_path.exists():
        raise PublicationError("private sidecars already exist; refusing to replace them")
    atomic_write_json(provenance_path, provenance)
    atomic_write_json(publication_path, {"schemaVersion": 1, "publications": []})
    print(f"Initialized provenance for {len(provenance['claims'])} active claims; no public files changed.")


def audit(args: argparse.Namespace) -> None:
    bullet_entries = parse_bullet_bank(Path(args.bullet_bank))
    resume_manifest = validate_resume_manifest(load_json(Path(args.resume_manifest)))
    provenance = validate_provenance(load_json(Path(args.provenance)))
    _, claims = provenance_maps(provenance)
    active_ids = sorted(claim_id for claim_id, entry in bullet_entries.items() if entry["status"] != "retired")
    if sorted(claims) != active_ids:
        missing = sorted(set(active_ids) - set(claims))
        unexpected = sorted(set(claims) - set(active_ids))
        raise PublicationError(
            f"provenance coverage mismatch; missing={missing or 'none'} unexpected={unexpected or 'none'}"
        )
    for claim_id in active_ids:
        current_source_digest(
            claim_id, bullet_entries, provenance, resume_manifest, Path(args.resumes_dir)
        )
    print(f"Resolved private provenance for all {len(active_ids)} active claims; no files changed.")


def review(args: argparse.Namespace) -> None:
    proposal_path = Path(args.proposal)
    proposal = validate_proposal(load_json(proposal_path))
    approved_at = args.approved_at or format_time(utc_now())
    parse_time(approved_at, "--approved-at")
    claims = [{**claim, "approvedAt": approved_at} for claim in proposal["claims"]]
    project_dir = Path(args.project_dir).resolve()
    preflight_project(project_dir, claims)
    diff = claim_diff(project_dir, claims)
    if not diff:
        raise PublicationError("proposal produces no tracked claim diff")
    code = digest_value({"batchId": proposal["batchId"], "claims": claims, "diff": diff})
    proposal["sealedApproval"] = {
        "approvedAt": approved_at,
        "approvalCode": code,
        "publicDiffDigest": digest_value(diff),
    }
    atomic_write_json(proposal_path, proposal)
    print(diff, end="" if diff.endswith("\n") else "\n")
    print(f"Approval code: {code}")
    print("No tracked or generated files were changed.")


def check_proposal(args: argparse.Namespace) -> None:
    proposal = validate_proposal(load_json(Path(args.proposal)))
    validation_time = format_time(utc_now())
    claims = [{**claim, "approvedAt": validation_time} for claim in proposal["claims"]]
    preflight_project(Path(args.project_dir).resolve(), claims)
    print(
        f"Validated {proposal['batchId']} with {len(claims)} candidate public claims "
        "against the full dossier suite; no files changed."
    )


def status(args: argparse.Namespace) -> None:
    publication_path = Path(args.publication_manifest)
    manifest = validate_publication_manifest(load_json(publication_path))
    provenance = validate_provenance(load_json(Path(args.provenance)))
    resume_manifest = validate_resume_manifest(load_json(Path(args.resume_manifest)))
    bullet_entries = parse_bullet_bank(Path(args.bullet_bank))
    project_dir = Path(args.project_dir)
    changed = False
    lines: list[str] = []
    for entry in manifest["publications"]:
        claim_id = entry["claimId"]
        public_path = project_dir / "content" / "claims" / f"{claim_id}.json"
        if not public_path.is_file():
            current = "stale"
        else:
            source_digest = current_source_digest(
                claim_id, bullet_entries, provenance, resume_manifest, Path(args.resumes_dir)
            )
            public_digest = digest_value(load_json(public_path))
            current = "published" if (
                source_digest == entry["privateSourceDigest"]
                and public_digest == entry["publicContentDigest"]
            ) else "stale"
        if entry["status"] != current:
            entry["status"] = current
            changed = True
        lines.append(f"{claim_id}: {current}")
    if changed:
        atomic_write_json(publication_path, manifest)
    print("\n".join(lines) if lines else "No published claims.")
    print("No tracked or generated files were changed.")


def snapshot_files(paths: Iterable[Path]) -> dict[Path, tuple[bool, bytes, int]]:
    result: dict[Path, tuple[bool, bytes, int]] = {}
    for path in paths:
        if path.exists():
            result[path] = (True, path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        else:
            result[path] = (False, b"", 0o644)
    return result


def restore_files(snapshot: dict[Path, tuple[bool, bytes, int]]) -> None:
    for path, (existed, content, mode) in snapshot.items():
        if existed:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.rollback")
            temporary.write_bytes(content)
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        elif path.exists():
            path.unlink()


def publish(args: argparse.Namespace) -> None:
    proposal = validate_proposal(load_json(Path(args.proposal)), require_seal=True)
    claims = sealed_claims(proposal)
    sealed = proposal["sealedApproval"]
    expected_code = digest_value({
        "batchId": proposal["batchId"],
        "claims": claims,
        "diff": claim_diff(Path(args.project_dir), claims),
    })
    if sealed.get("approvalCode") != expected_code or args.approval_code != expected_code:
        raise PublicationError("approval code does not match the current exact public diff")
    required_phrase = f"APPROVE {expected_code}"
    confirmation = args.confirm or input(f"Type {required_phrase} to publish: ")
    if confirmation != required_phrase:
        raise PublicationError("explicit approval phrase not received; nothing was published")

    project_dir = Path(args.project_dir).resolve()
    preflight_project(project_dir, claims)
    provenance = validate_provenance(load_json(Path(args.provenance)))
    resume_manifest = validate_resume_manifest(load_json(Path(args.resume_manifest)))
    bullet_entries = parse_bullet_bank(Path(args.bullet_bank))
    publication_path = Path(args.publication_manifest)
    publication = validate_publication_manifest(load_json(publication_path))
    by_id = {entry["claimId"]: entry for entry in publication["publications"]}
    exported_at = format_time(utc_now())
    for claim in claims:
        claim_id = claim["id"]
        by_id[claim_id] = {
            "schemaVersion": 1,
            "claimId": claim_id,
            "privateSourceDigest": current_source_digest(
                claim_id, bullet_entries, provenance, resume_manifest, Path(args.resumes_dir)
            ),
            "publicContentDigest": digest_value(claim),
            "approvedAt": claim["approvedAt"],
            "exportedAt": exported_at,
            "status": "published",
        }
    publication["publications"] = [by_id[key] for key in sorted(by_id)]
    validate_publication_manifest(publication)

    claim_paths = [project_dir / "content" / "claims" / f"{claim['id']}.json" for claim in claims]
    dist_paths = [path for path in (project_dir / "dist").glob("*") if path.is_file()]
    snapshot = snapshot_files([*claim_paths, publication_path, *dist_paths])
    try:
        for claim, path in zip(claims, claim_paths):
            atomic_write_json(path, claim, 0o644)
        atomic_write_json(publication_path, publication)
        subprocess.run(["npm", "run", "verify"], cwd=project_dir, check=True)
    except BaseException:
        restore_files(snapshot)
        raise
    print(f"Published {len(claims)} approved claims and updated the private manifest.")


def add_common(parser: argparse.ArgumentParser) -> None:
    ari_root = Path(__file__).resolve().parents[1]
    private = ari_root / ".private"
    parser.add_argument("--project-dir", default=str(ari_root / "career-dossier"))
    parser.add_argument("--bullet-bank", default=str(private / "Resume Bullet Bank.md"))
    parser.add_argument("--resume-manifest", default=str(private / "Resume Corpus Manifest.json"))
    parser.add_argument("--resumes-dir", default=str(private / "Resumes"))
    parser.add_argument("--provenance", default=str(private / "Career Claim Provenance.json"))
    parser.add_argument("--publication-manifest", default=str(private / "Dossier Publication Manifest.json"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create owner-only private sidecars")
    add_common(init_parser)
    init_parser.set_defaults(func=initialize)

    audit_parser = subparsers.add_parser("audit", help="resolve every active private provenance mapping")
    add_common(audit_parser)
    audit_parser.set_defaults(func=audit)

    review_parser = subparsers.add_parser("review", help="validate and seal an exact public diff")
    add_common(review_parser)
    review_parser.add_argument("--proposal", required=True)
    review_parser.add_argument("--approved-at")
    review_parser.set_defaults(func=review)

    check_parser = subparsers.add_parser("check", help="validate an unsealed proposal without writing files")
    add_common(check_parser)
    check_parser.add_argument("--proposal", required=True)
    check_parser.set_defaults(func=check_proposal)

    status_parser = subparsers.add_parser("status", help="mark and report stale publications")
    add_common(status_parser)
    status_parser.set_defaults(func=status)

    publish_parser = subparsers.add_parser("publish", help="write only an explicitly approved sealed diff")
    add_common(publish_parser)
    publish_parser.add_argument("--proposal", required=True)
    publish_parser.add_argument("--approval-code", required=True)
    publish_parser.add_argument("--confirm", help=argparse.SUPPRESS)
    publish_parser.set_defaults(func=publish)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except PublicationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
