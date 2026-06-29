import unittest
from pathlib import Path


class GitignoreTests(unittest.TestCase):
    def test_local_documents_jobs_and_secrets_remain_ignored(self):
        project_root = Path(__file__).resolve().parents[1]
        gitignore = (project_root / ".gitignore").read_text(encoding="utf-8")

        for pattern in ("*.pdf", "books/*", "jobs/", "secrets/*"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, gitignore)


if __name__ == "__main__":
    unittest.main()
