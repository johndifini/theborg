#!/usr/bin/env python3
"""Synthetic tests for the public resume-corpus workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "resume_corpus.py"
SPEC = importlib.util.spec_from_file_location("resume_corpus", MODULE_PATH)
assert SPEC and SPEC.loader
corpus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = corpus
SPEC.loader.exec_module(corpus)


NOW = dt.datetime(2026, 8, 29, 18, 0, tzinfo=dt.timezone.utc)


class ResumeCorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.resumes = self.root / "Resumes"
        self.resumes.mkdir()
        self.manifest_path = self.root / "manifest.json"
        self.write_manifest([])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_file(self, relative: str, content: bytes = b"synthetic", age_hours: float = 72) -> Path:
        path = self.resumes / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        timestamp = NOW.timestamp() - age_hours * 3600
        os.utime(path, (timestamp, timestamp))
        return path

    def artifact(self, docx: str, pdf: str, artifact_id: str = "resume-synthetic") -> dict[str, object]:
        return {
            "id": artifact_id,
            "docxPath": docx,
            "pdfPath": pdf,
            "docxSha256": corpus.stable_hash(self.resumes / docx),
            "pdfSha256": corpus.stable_hash(self.resumes / pdf),
            "finalizedAt": "2026-08-01T00:00:00Z",
            "harvestedAt": "2026-08-01T00:00:00Z",
            "status": "final",
            "bulletIds": ["RB-001"],
            "baselineId": None,
            "supersedesId": None,
        }

    def write_manifest(self, artifacts: list[dict[str, object]]) -> None:
        self.manifest_path.write_text(
            json.dumps({"schemaVersion": 1, "artifacts": artifacts}, indent=2) + "\n",
            encoding="utf-8",
        )

    def scan(self) -> list[object]:
        manifest = corpus.load_manifest(self.manifest_path)
        return corpus.scan_corpus(self.resumes, manifest, NOW, 48)

    def test_unchanged_finalized_artifact_is_quiet(self) -> None:
        self.write_file("target role.docx")
        self.write_file("target role.pdf")
        self.write_manifest([self.artifact("target role.docx", "target role.pdf")])
        self.assertEqual([], self.scan())

    def test_changed_docx_after_harvest_is_reported_when_stable(self) -> None:
        docx = self.write_file("target.docx")
        self.write_file("target.pdf")
        artifact = self.artifact("target.docx", "target.pdf")
        docx.write_bytes(b"changed")
        old = NOW.timestamp() - 72 * 3600
        os.utime(docx, (old, old))
        self.write_manifest([artifact])
        self.assertEqual(["changed-docx"], [finding.kind for finding in self.scan()])

    def test_changed_pdf_is_immediate_export_signal(self) -> None:
        self.write_file("target.docx", age_hours=1)
        pdf = self.write_file("target.pdf", age_hours=1)
        artifact = self.artifact("target.docx", "target.pdf")
        pdf.write_bytes(b"manual export")
        fresh = NOW.timestamp() - 60
        os.utime(pdf, (fresh, fresh))
        self.write_manifest([artifact])
        self.assertEqual(["changed-pdf"], [finding.kind for finding in self.scan()])

    def test_new_unmanifested_pair_is_reported_even_when_fresh(self) -> None:
        self.write_file("new role.docx", age_hours=1)
        self.write_file("new role.pdf", age_hours=1)
        self.assertEqual(["unmanifested-pair"], [finding.kind for finding in self.scan()])

    def test_stable_docx_without_pdf_is_reported(self) -> None:
        self.write_file("draft.docx")
        self.assertEqual(["docx-without-pdf"], [finding.kind for finding in self.scan()])

    def test_pdf_without_docx_is_reported(self) -> None:
        self.write_file("orphan.pdf", age_hours=1)
        self.assertEqual(["pdf-without-docx"], [finding.kind for finding in self.scan()])

    def test_actively_edited_docx_without_pdf_is_suppressed(self) -> None:
        self.write_file("active.docx", age_hours=1)
        self.assertEqual([], self.scan())

    def test_lock_backup_and_archive_files_are_ignored(self) -> None:
        self.write_file("~$locked.docx")
        self.write_file("backup.bak.pdf")
        self.write_file("Older Resumes/archived.docx")
        self.write_file(".DS_Store")
        self.assertEqual([], self.scan())

    def test_malformed_manifest_fails(self) -> None:
        self.manifest_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(corpus.CorpusError):
            corpus.load_manifest(self.manifest_path)

    def test_manifest_entry_with_missing_target_is_reported(self) -> None:
        self.write_file("target.docx")
        self.write_file("target.pdf")
        artifact = self.artifact("target.docx", "target.pdf")
        (self.resumes / "target.pdf").unlink()
        self.write_manifest([artifact])
        findings = self.scan()
        self.assertEqual("missing-recorded-file", findings[0].kind)
        self.assertEqual(("target.pdf",), findings[0].paths)

    def test_paths_with_spaces_record_atomically(self) -> None:
        self.write_file("folder with spaces/target role.docx")
        self.write_file("folder with spaces/target role.pdf")
        args = argparse.Namespace(
            manifest=str(self.manifest_path),
            resume_dir=str(self.resumes),
            artifact_id="resume-space-test",
            docx="folder with spaces/target role.docx",
            pdf="folder with spaces/target role.pdf",
            status="final",
            bullet_id=["RB-002", "RB-001", "RB-002"],
            baseline_id=None,
            supersedes_id=None,
            now="2026-08-29T18:00:00Z",
        )
        corpus.record_artifact(args)
        manifest = corpus.load_manifest(self.manifest_path)
        self.assertEqual(["RB-001", "RB-002"], manifest["artifacts"][0]["bulletIds"])
        self.assertEqual([], self.scan())

    def test_ambiguous_resume_name_fails(self) -> None:
        self.write_file("example-alpha.docx")
        self.write_file("example-beta.docx")
        with self.assertRaisesRegex(corpus.CorpusError, "ambiguous"):
            corpus.resolve_resume(self.resumes, "example")

    def test_resolution_rejects_archive_backup_and_non_docx(self) -> None:
        self.write_file("Older Resumes/example.docx")
        self.write_file("example.bak.docx")
        self.write_file("example.pdf")
        for query in ("Older Resumes/example.docx", "example.bak.docx", "example.pdf"):
            with self.subTest(query=query), self.assertRaises(corpus.CorpusError):
                corpus.resolve_resume(self.resumes, query)

    def test_command_contract_requires_manual_current_word_export(self) -> None:
        command = (MODULE_PATH.parents[1] / ".claude/commands/finalize-resume.md").read_text(encoding="utf-8")
        self.assertIn("final PDF must be exported by the candidate from", command)
        self.assertIn("Never create or replace the final PDF with LibreOffice", command)
        self.assertIn("Pause the workflow; do not harvest or update the manifest", command)
        self.assertIn("require the PDF to be new", command)
        self.assertIn("PDF metadata alone is not sufficient proof", command)
        self.assertIn("Extract text from both the DOCX", command)
        self.assertIn("require another manual Word export", command)
        self.assertLess(command.index("## Require a current Word PDF"), command.index("## Harvest"))
        self.assertLess(command.index("## Harvest"), command.index("## Record"))


if __name__ == "__main__":
    unittest.main()
