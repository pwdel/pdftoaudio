import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from app.pdftoaudio_core.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        self.pdf = self.project_root / "book.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test fixture")

    def tearDown(self):
        self.tmpdir.cleanup()

    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args, project_root=self.project_root)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_help_lists_commands(self):
        code, stdout, stderr = self.run_cli(["--help"])

        self.assertEqual(code, 0)
        self.assertIn("init", stdout)
        self.assertIn("status", stdout)
        self.assertIn("chunk", stdout)
        self.assertIn("help", stdout)
        self.assertEqual(stderr, "")

    def test_help_command_lists_commands(self):
        code, stdout, stderr = self.run_cli(["help"])

        self.assertEqual(code, 0)
        self.assertIn("init", stdout)
        self.assertIn("status", stdout)
        self.assertIn("chunk", stdout)
        self.assertIn("help", stdout)
        self.assertEqual(stderr, "")

    def test_help_command_prints_command_help(self):
        code, stdout, stderr = self.run_cli(["help", "chunk"])

        self.assertEqual(code, 0)
        self.assertIn("usage: pdftoaudio chunk", stdout)
        self.assertIn("--max-bytes", stdout)
        self.assertEqual(stderr, "")

    def test_help_command_rejects_unknown_topic(self):
        code, stdout, stderr = self.run_cli(["help", "missing"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Unknown help topic: missing", stderr)

    def test_init_creates_job(self):
        code, stdout, stderr = self.run_cli(["init", "my-book", str(self.pdf)])

        self.assertEqual(code, 0)
        self.assertIn("Initialized job: my-book", stdout)
        self.assertIn("next: pdftoaudio extract my-book", stdout)
        self.assertEqual(stderr, "")
        self.assertTrue((self.project_root / "jobs/my-book/source/original.pdf").exists())

    def test_status_prints_files_and_next_command(self):
        self.run_cli(["init", "my-book", str(self.pdf)])

        code, stdout, stderr = self.run_cli(["status", "my-book"])

        self.assertEqual(code, 0)
        self.assertIn("my-book", stdout)
        self.assertIn("source/original.pdf      ok", stdout)
        self.assertIn("text/raw.txt             missing", stdout)
        self.assertIn("next: pdftoaudio extract my-book", stdout)
        self.assertEqual(stderr, "")

    def test_status_for_missing_job_returns_error(self):
        code, stdout, stderr = self.run_cli(["status", "missing-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing job manifest", stderr)

    def test_extract_missing_source_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])
        source = self.project_root / "jobs/my-book/source/original.pdf"
        source.unlink()

        code, stdout, stderr = self.run_cli(["extract", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing source PDF", stderr)

    def test_sanitize_missing_raw_text_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])

        code, stdout, stderr = self.run_cli(["sanitize", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing raw text", stderr)

    def test_review_missing_sanitized_text_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])

        code, stdout, stderr = self.run_cli(["review", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing sanitized text", stderr)

    def test_chunk_missing_cleaned_text_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])

        code, stdout, stderr = self.run_cli(["chunk", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing cleaned text", stderr)


if __name__ == "__main__":
    unittest.main()
