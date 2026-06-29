import tempfile
import unittest
from pathlib import Path

from app.pdftoaudio_core.workspace import inspect_workspace, workspace_ready


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_inspect_workspace_reports_missing_directories(self):
        entries = inspect_workspace(self.project_root)

        self.assertFalse(workspace_ready(entries))
        self.assertEqual(
            {entry["path"]: entry["status"] for entry in entries},
            {
                "books/": "missing",
                "jobs/": "missing",
                "secrets/": "missing",
            },
        )

    def test_inspect_workspace_fix_creates_directories(self):
        entries = inspect_workspace(self.project_root, fix=True)

        self.assertTrue(workspace_ready(entries))
        self.assertEqual(
            {entry["path"]: entry["status"] for entry in entries},
            {
                "books/": "created",
                "jobs/": "created",
                "secrets/": "created",
            },
        )
        self.assertTrue((self.project_root / "books").is_dir())
        self.assertTrue((self.project_root / "jobs").is_dir())
        self.assertTrue((self.project_root / "secrets").is_dir())

    def test_inspect_workspace_flags_file_instead_of_directory(self):
        (self.project_root / "books").write_text("not a directory", encoding="utf-8")

        entries = inspect_workspace(self.project_root, fix=True)

        self.assertFalse(workspace_ready(entries))
        self.assertEqual(entries[0]["path"], "books/")
        self.assertEqual(entries[0]["status"], "not_directory")


if __name__ == "__main__":
    unittest.main()
