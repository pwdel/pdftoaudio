import json
import tempfile
import unittest
from pathlib import Path

from app.pdftoaudio_core.jobs import init_job, load_manifest, resolve_job
from app.pdftoaudio_core.review import review_job, review_text


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        self.pdf = self.project_root / "book.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test fixture")
        init_job(self.project_root, "my-book", self.pdf)
        self.paths = resolve_job(self.project_root, "my-book")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_review_text_flags_known_suspicious_lines(self):
        long_sentence = "This sentence " + ("keeps going " * 60) + "."
        text = "\n".join(
            [
                "1",
                "Chapter Title",
                "hyphen-",
                "ated word",
                "Name | Value | Notes",
                long_sentence,
                "Cafe \u2603",
            ]
        )

        report = review_text(text, "my-book")
        codes = [issue["code"] for issue in report["issues"]]

        self.assertIn("likely_page_number", codes)
        self.assertIn("hyphenated_line_break", codes)
        self.assertIn("table_like_block", codes)
        self.assertIn("long_sentence", codes)
        self.assertIn("non_ascii_character", codes)

    def test_review_text_flags_multiline_long_sentence_with_line_range(self):
        text = ("first line " * 28).strip() + "\n" + ("second line " * 28).strip() + "."

        report = review_text(text, "my-book")
        long_sentence = next(issue for issue in report["issues"] if issue["code"] == "long_sentence")

        self.assertEqual(long_sentence["line_start"], 1)
        self.assertEqual(long_sentence["line_end"], 2)

    def test_review_job_writes_report_and_updates_manifest(self):
        self.paths.sanitized_text.write_text("1\nContent\n", encoding="utf-8")

        report = review_job(self.paths)

        self.assertTrue(self.paths.review_report.exists())
        self.assertEqual(report["schema_version"], 1)
        saved = json.loads(self.paths.review_report.read_text(encoding="utf-8"))
        self.assertEqual(saved["issues"][0]["code"], "likely_page_number")
        manifest = load_manifest(self.paths)
        self.assertEqual(manifest["steps"]["review"]["status"], "ok")

    def test_review_refuses_existing_report_without_force(self):
        self.paths.sanitized_text.write_text("Content\n", encoding="utf-8")
        review_job(self.paths)

        with self.assertRaises(FileExistsError):
            review_job(self.paths)


if __name__ == "__main__":
    unittest.main()
