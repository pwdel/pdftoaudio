import json
import tempfile
import unittest
from pathlib import Path

from app.pdftoaudio_core.jobs import init_job, load_manifest, resolve_job
from app.pdftoaudio_core.sanitize import sanitize_job, sanitize_text


class SanitizeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        self.pdf = self.project_root / "book.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test fixture")
        init_job(self.project_root, "my-book", self.pdf)
        self.paths = resolve_job(self.project_root, "my-book")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_sanitize_text_normalizes_safe_characters(self):
        result = sanitize_text("A\u00a0B\u00adC\x0c\n\n\nD\x00E")

        self.assertEqual(result["text"], "A BC\n\nD E\n")
        self.assertEqual(
            [change["code"] for change in result["changes"]],
            [
                "nbsp",
                "soft_hyphen",
                "control_character",
                "repeated_blank_lines",
                "control_character",
            ],
        )

    def test_sanitize_job_writes_text_and_reports(self):
        self.paths.raw_text.write_text("A\u00a0B\u00adC\x0c\n", encoding="utf-8")

        report = sanitize_job(self.paths)

        self.assertEqual(self.paths.sanitized_text.read_text(encoding="utf-8"), "A BC\n")
        self.assertTrue(self.paths.sanitize_report.exists())
        self.assertTrue(self.paths.line_map_report.exists())
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["book"], "my-book")

        saved = json.loads(self.paths.sanitize_report.read_text(encoding="utf-8"))
        self.assertEqual(saved["changes"][0]["code"], "nbsp")

        line_map = json.loads(self.paths.line_map_report.read_text(encoding="utf-8"))
        self.assertEqual(line_map["lines"][0]["raw_line"], 1)
        self.assertEqual(line_map["lines"][0]["sanitized_line"], 1)

        manifest = load_manifest(self.paths)
        self.assertEqual(manifest["steps"]["sanitize"]["status"], "ok")

    def test_report_only_does_not_write_sanitized_text(self):
        self.paths.raw_text.write_text("A\u00a0B\n", encoding="utf-8")

        sanitize_job(self.paths, report_only=True)

        self.assertFalse(self.paths.sanitized_text.exists())
        self.assertTrue(self.paths.sanitize_report.exists())

    def test_sanitize_refuses_existing_output_without_force(self):
        self.paths.raw_text.write_text("A B\n", encoding="utf-8")
        sanitize_job(self.paths)

        with self.assertRaises(FileExistsError):
            sanitize_job(self.paths)


if __name__ == "__main__":
    unittest.main()
