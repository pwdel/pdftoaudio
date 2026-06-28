import tempfile
import unittest
from pathlib import Path

from app.pdftoaudio_core.jobs import (
    init_job,
    inspect_status,
    load_manifest,
    resolve_job,
    update_step,
)


class JobWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        self.source_pdf = self.project_root / "book.pdf"
        self.source_pdf.write_bytes(b"%PDF-1.4 test fixture")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_resolve_job_rejects_path_separators(self):
        with self.assertRaises(ValueError):
            resolve_job(self.project_root, "../bad")

    def test_init_job_creates_workspace_and_manifest(self):
        manifest = init_job(self.project_root, "my-book", self.source_pdf)
        paths = resolve_job(self.project_root, "my-book")

        self.assertTrue(paths.source_pdf.exists())
        self.assertEqual(paths.source_pdf.read_bytes(), b"%PDF-1.4 test fixture")
        self.assertTrue(paths.text_dir.is_dir())
        self.assertTrue(paths.reports_dir.is_dir())
        self.assertTrue(paths.chunks_dir.is_dir())
        self.assertTrue(paths.audio_dir.is_dir())
        self.assertEqual(manifest["book"], "my-book")
        self.assertEqual(manifest["source_pdf"], "source/original.pdf")
        self.assertEqual(manifest["steps"]["init"]["status"], "ok")

    def test_init_job_refuses_existing_source_without_force(self):
        init_job(self.project_root, "my-book", self.source_pdf)
        with self.assertRaises(FileExistsError):
            init_job(self.project_root, "my-book", self.source_pdf)

    def test_init_job_force_replaces_existing_source(self):
        init_job(self.project_root, "my-book", self.source_pdf)
        replacement = self.project_root / "replacement.pdf"
        replacement.write_bytes(b"%PDF replacement")

        init_job(self.project_root, "my-book", replacement, force=True)
        paths = resolve_job(self.project_root, "my-book")

        self.assertEqual(paths.source_pdf.read_bytes(), b"%PDF replacement")

    def test_update_step_records_status_and_error(self):
        init_job(self.project_root, "my-book", self.source_pdf)
        paths = resolve_job(self.project_root, "my-book")

        update_step(paths, "extract", "error", error="missing source")
        manifest = load_manifest(paths)

        self.assertEqual(manifest["steps"]["extract"]["status"], "error")
        self.assertEqual(manifest["steps"]["extract"]["error"], "missing source")

    def test_inspect_status_reports_expected_files(self):
        init_job(self.project_root, "my-book", self.source_pdf)
        paths = resolve_job(self.project_root, "my-book")
        paths.raw_text.write_text("raw text", encoding="utf-8")

        status = inspect_status(paths)

        self.assertEqual(status["book"], "my-book")
        self.assertEqual(status["files"]["source/original.pdf"], "ok")
        self.assertEqual(status["files"]["text/raw.txt"], "ok")
        self.assertEqual(status["files"]["text/sanitized.txt"], "missing")
        self.assertEqual(status["next_command"], "pdftoaudio sanitize my-book")

    def test_inspect_status_suggests_chunk_after_cleaned_text(self):
        init_job(self.project_root, "my-book", self.source_pdf)
        paths = resolve_job(self.project_root, "my-book")
        paths.raw_text.write_text("raw text", encoding="utf-8")
        paths.sanitized_text.write_text("sanitized text", encoding="utf-8")
        paths.review_report.write_text("{}", encoding="utf-8")
        paths.cleaned_text.write_text("cleaned text", encoding="utf-8")

        status = inspect_status(paths)

        self.assertEqual(status["next_command"], "pdftoaudio chunk my-book")

    def test_inspect_status_suggests_synthesis_after_sanitized_chunks(self):
        init_job(self.project_root, "my-book", self.source_pdf)
        paths = resolve_job(self.project_root, "my-book")
        paths.raw_text.write_text("raw text", encoding="utf-8")
        paths.sanitized_text.write_text("sanitized text", encoding="utf-8")
        paths.review_report.write_text("{}", encoding="utf-8")
        paths.chunk_report.write_text("{}", encoding="utf-8")

        status = inspect_status(paths)

        self.assertEqual(
            status["next_command"], "pdftoaudio synthesize my-book --provider google"
        )


if __name__ == "__main__":
    unittest.main()
