#!/usr/bin/env python3
"""Synthetic tests for Ari's approval-gated dossier publication workflow."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "dossier_publication.py"
SPEC = importlib.util.spec_from_file_location("dossier_publication", MODULE_PATH)
assert SPEC and SPEC.loader
workflow = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = workflow
SPEC.loader.exec_module(workflow)


class DossierPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / "private"
        self.resumes = self.private / "Resumes"
        self.project = self.root / "career-dossier"
        (self.project / "content" / "claims").mkdir(parents=True)
        self.resumes.mkdir(parents=True)
        self.source = self.resumes / "example.docx"
        self.source.write_bytes(b"synthetic resume")
        self.bank = self.private / "Resume Bullet Bank.md"
        self.bank.write_text(
            "# Bank\n\n### RB-001 — Synthetic example\n\n"
            "- **Status:** verified\n"
            "- **Canonical evidence:** A private synthetic fact.\n"
            "- **Source:** `.private/Resumes/example.docx`\n\n"
            "### RB-002 — Retired example\n\n"
            "- **Status:** retired\n"
            "- **Source:** RB-001\n",
            encoding="utf-8",
        )
        source_hash = workflow.file_digest(self.source).removeprefix("sha256:")
        self.resume_manifest = self.private / "Resume Corpus Manifest.json"
        self.resume_manifest.write_text(json.dumps({
            "schemaVersion": 1,
            "artifacts": [{
                "id": "resume-synthetic",
                "docxPath": "example.docx",
                "pdfPath": "example.pdf",
                "docxSha256": source_hash,
                "pdfSha256": "1" * 64,
                "bulletIds": ["RB-001"],
            }],
        }), encoding="utf-8")
        self.provenance = self.private / "Career Claim Provenance.json"
        self.publications = self.private / "Dossier Publication Manifest.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def init_args(self) -> argparse.Namespace:
        return argparse.Namespace(
            bullet_bank=str(self.bank),
            resume_manifest=str(self.resume_manifest),
            provenance=str(self.provenance),
            publication_manifest=str(self.publications),
        )

    def public_claim(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "id": "RB-001",
            "type": "experience",
            "title": "Synthetic public title",
            "claim": "Synthetic public wording.",
            "status": "historical",
            "asOf": "2026-09-01",
            "skills": ["Testing"],
            "evidenceIds": [],
            "limitations": ["Synthetic only."],
            "evidenceLevel": "resume-sourced",
            "visibility": "public",
        }

    def test_init_maps_active_claims_only_and_uses_owner_permissions(self) -> None:
        workflow.initialize(self.init_args())
        provenance = workflow.validate_provenance(workflow.load_json(self.provenance))
        self.assertEqual(["RB-001"], [claim["claimId"] for claim in provenance["claims"]])
        self.assertEqual(0o600, self.provenance.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.publications.stat().st_mode & 0o777)

    def test_unsealed_proposal_cannot_publish(self) -> None:
        proposal = {
            "schemaVersion": 1,
            "batchId": "BATCH-001",
            "createdAt": "2026-09-01T00:00:00Z",
            "claims": [self.public_claim()],
        }
        with self.assertRaisesRegex(workflow.PublicationError, "not been sealed"):
            workflow.validate_proposal(proposal, require_seal=True)

    def test_exact_approval_code_changes_with_public_diff(self) -> None:
        claim = {**self.public_claim(), "approvedAt": "2026-09-01T00:00:00Z"}
        first_diff = workflow.claim_diff(self.project, [claim])
        first = workflow.digest_value({"batchId": "BATCH-001", "claims": [claim], "diff": first_diff})
        claim["claim"] = "Changed wording."
        second_diff = workflow.claim_diff(self.project, [claim])
        second = workflow.digest_value({"batchId": "BATCH-001", "claims": [claim], "diff": second_diff})
        self.assertNotEqual(first, second)

    def test_private_or_public_change_marks_publication_stale_without_touching_dist(self) -> None:
        workflow.initialize(self.init_args())
        provenance = workflow.load_json(self.provenance)
        resume_manifest = workflow.load_json(self.resume_manifest)
        entries = workflow.parse_bullet_bank(self.bank)
        claim = {**self.public_claim(), "approvedAt": "2026-09-01T00:00:00Z"}
        public_path = self.project / "content" / "claims" / "RB-001.json"
        workflow.atomic_write_json(public_path, claim, 0o644)
        dist = self.project / "dist"
        dist.mkdir()
        marker = dist / "marker.txt"
        marker.write_text("unchanged", encoding="utf-8")
        source_digest = workflow.current_source_digest(
            "RB-001", entries, provenance, resume_manifest, self.resumes
        )
        workflow.atomic_write_json(self.publications, {
            "schemaVersion": 1,
            "publications": [{
                "schemaVersion": 1,
                "claimId": "RB-001",
                "privateSourceDigest": source_digest,
                "publicContentDigest": workflow.digest_value(claim),
                "approvedAt": "2026-09-01T00:00:00Z",
                "exportedAt": "2026-09-01T00:00:00Z",
                "status": "published",
            }],
        })
        args = argparse.Namespace(
            publication_manifest=str(self.publications),
            provenance=str(self.provenance),
            resume_manifest=str(self.resume_manifest),
            bullet_bank=str(self.bank),
            project_dir=str(self.project),
            resumes_dir=str(self.resumes),
        )
        self.bank.write_text(self.bank.read_text(encoding="utf-8").replace("private synthetic", "changed synthetic"), encoding="utf-8")
        workflow.status(args)
        self.assertEqual("stale", workflow.load_json(self.publications)["publications"][0]["status"])
        self.assertEqual("unchanged", marker.read_text(encoding="utf-8"))

    def test_failed_validation_leaves_public_and_private_files_unchanged(self) -> None:
        workflow.initialize(self.init_args())
        before_publications = self.publications.read_bytes()
        proposal = {
            "schemaVersion": 1,
            "batchId": "BATCH-001",
            "createdAt": "2026-09-01T00:00:00Z",
            "claims": [{**self.public_claim(), "limitations": []}],
        }
        proposal_path = self.private / "proposal.json"
        workflow.atomic_write_json(proposal_path, proposal)
        with self.assertRaises(workflow.PublicationError):
            workflow.validate_proposal(workflow.load_json(proposal_path))
        self.assertFalse((self.project / "content" / "claims" / "RB-001.json").exists())
        self.assertEqual(before_publications, self.publications.read_bytes())


if __name__ == "__main__":
    unittest.main()
