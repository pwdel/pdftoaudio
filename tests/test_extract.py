import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.pdftoaudio_core.extract import extract_pdf
from app.pdftoaudio_core.jobs import init_job, load_manifest, resolve_job


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    def __init__(self, _path):
        self.pages = [FakePage("Page one."), FakePage("Page two.")]


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        self.pdf = self.project_root / "book.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test fixture")
        init_job(self.project_root, "my-book", self.pdf)
        self.paths = resolve_job(self.project_root, "my-book")

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("app.pdftoaudio_core.extract.PdfReader", FakeReader)
    def test_extract_writes_raw_text_and_updates_manifest(self):
        report = extract_pdf(self.paths)

        self.assertEqual(self.paths.raw_text.read_text(encoding="utf-8"), "Page one.\n\nPage two.\n")
        self.assertEqual(report["pages"], 2)
        manifest = load_manifest(self.paths)
        self.assertEqual(manifest["steps"]["extract"]["status"], "ok")
        self.assertEqual(manifest["steps"]["extract"]["output"], "text/raw.txt")

    @patch("app.pdftoaudio_core.extract.PdfReader", FakeReader)
    def test_extract_refuses_existing_output_without_force(self):
        extract_pdf(self.paths)

        with self.assertRaises(FileExistsError):
            extract_pdf(self.paths)

    @patch("app.pdftoaudio_core.extract.PdfReader", FakeReader)
    def test_extract_force_replaces_existing_output(self):
        extract_pdf(self.paths)
        self.paths.raw_text.write_text("stale", encoding="utf-8")

        extract_pdf(self.paths, force=True)

        self.assertEqual(self.paths.raw_text.read_text(encoding="utf-8"), "Page one.\n\nPage two.\n")


if __name__ == "__main__":
    unittest.main()
