import json
import tempfile
import unittest
from pathlib import Path

from app.pdftoaudio_core.chunk import byte_len, chunk_job, split_text_for_tts
from app.pdftoaudio_core.jobs import init_job, load_manifest, resolve_job


class ChunkTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        self.pdf = self.project_root / "book.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test fixture")
        init_job(self.project_root, "my-book", self.pdf)
        self.paths = resolve_job(self.project_root, "my-book")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_split_text_for_tts_prefers_sentence_boundaries(self):
        chunks = split_text_for_tts("One. Two. Three.", max_bytes=12)

        self.assertEqual(chunks, ["One. Two.", "Three."])

    def test_split_text_for_tts_uses_whitespace_when_sentence_keeps_running(self):
        chunks = split_text_for_tts("word " * 12, max_bytes=20)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(byte_len(chunk) <= 20 for chunk in chunks))
        self.assertEqual(chunks[0], "word word word word")

    def test_split_text_for_tts_hard_splits_long_token(self):
        chunks = split_text_for_tts("abcdefghij", max_bytes=4)

        self.assertEqual(chunks, ["abcd", "efgh", "ij"])

    def test_split_text_for_tts_rejects_invalid_limit(self):
        with self.assertRaises(ValueError) as context:
            split_text_for_tts("Text.", max_bytes=0)

        self.assertIn("max_bytes must be greater than zero", str(context.exception))

    def test_chunk_job_records_invalid_limit_error(self):
        self.paths.cleaned_text.write_text("Text.", encoding="utf-8")

        with self.assertRaises(ValueError):
            chunk_job(self.paths, max_bytes=0)

        manifest = load_manifest(self.paths)
        self.assertEqual(manifest["steps"]["chunk"]["status"], "error")
        self.assertIn(
            "max_bytes must be greater than zero",
            manifest["steps"]["chunk"]["error"],
        )

    def test_chunk_job_writes_numbered_files_and_report(self):
        self.paths.cleaned_text.write_text("One. Two. Three.", encoding="utf-8")

        report = chunk_job(self.paths, max_bytes=12)

        self.assertEqual([entry["path"] for entry in report["chunks"]], ["chunks/001.txt", "chunks/002.txt"])
        self.assertEqual((self.paths.chunks_dir / "001.txt").read_text(encoding="utf-8"), "One. Two.")
        self.assertEqual((self.paths.chunks_dir / "002.txt").read_text(encoding="utf-8"), "Three.")
        saved = json.loads(self.paths.chunk_report.read_text(encoding="utf-8"))
        self.assertEqual(saved["max_bytes"], 12)
        manifest = load_manifest(self.paths)
        self.assertEqual(manifest["steps"]["chunk"]["status"], "ok")

    def test_chunk_job_can_use_sanitized_source(self):
        self.paths.sanitized_text.write_text("One. Two.", encoding="utf-8")

        report = chunk_job(self.paths, source="sanitized", max_bytes=100)

        self.assertEqual(report["input"], "text/sanitized.txt")
        self.assertEqual((self.paths.chunks_dir / "001.txt").read_text(encoding="utf-8"), "One. Two.")

    def test_chunk_job_refuses_existing_output_without_force(self):
        self.paths.cleaned_text.write_text("One. Two.", encoding="utf-8")
        chunk_job(self.paths)

        with self.assertRaises(FileExistsError):
            chunk_job(self.paths)

    def test_chunk_job_validates_forced_rechunk_before_deleting_old_chunks(self):
        self.paths.cleaned_text.write_text("One. Two.", encoding="utf-8")
        chunk_job(self.paths)
        first_chunk = self.paths.chunks_dir / "001.txt"

        with self.assertRaises(ValueError):
            chunk_job(self.paths, max_bytes=0, force=True)

        self.assertEqual(first_chunk.read_text(encoding="utf-8"), "One. Two.")


if __name__ == "__main__":
    unittest.main()
