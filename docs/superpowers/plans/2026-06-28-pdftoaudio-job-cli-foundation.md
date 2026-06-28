# pdftoaudio Job CLI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `$subagent-driven-development` (recommended, if installed) or `$executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first job-first `pdftoaudio` CLI slice with `init`, `status`, `extract`, `sanitize`, and `review`.

**Architecture:** Add a thin root-level `./pdftoaudio` executable that delegates to focused Python modules under `app/pdftoaudio_core/`. Each command reads and writes predictable files inside `jobs/<book>/`, updates `manifest.json`, and refuses destructive overwrites unless `--force` is passed. Deterministic cleanup runs before LLM cleanup: `sanitize` writes conservative text fixes plus reports, while `review` flags suspicious spans without changing text.

**Tech Stack:** Python 3, standard library `argparse`, `dataclasses`, `json`, `pathlib`, `unittest`, existing `pypdf` dependency.

## Global Constraints

- No web UI.
- No database.
- No daemon or background job runner.
- No A2A requirement in the first architecture.
- No full-book MLX cleanup until small text-slice benchmarks prove it is worth using.
- No live Google TTS calls in default tests.
- Filesystem as the job database.
- One CLI front door: `pdftoaudio <command> <book>`.
- Small commands read known inputs and write known outputs.
- Source PDF stays immutable after `init`.
- Deterministic cleanup runs before Codex or MLX.
- Reports point to text with line ranges and reasons.
- Existing outputs are reused unless `--force` is passed.
- Prefer plain Python modules and `argparse` over frameworks.
- `jobs/` is gitignored by default.
- Expose a root-level `./pdftoaudio` executable first.

---

## Scope Check

The approved architecture spec covers the full future system. This plan implements the first independently shippable slice:

- `pdftoaudio init`
- `pdftoaudio status`
- `pdftoaudio extract`
- `pdftoaudio sanitize`
- `pdftoaudio review`
- `jobs/` workspace layout
- `manifest.json`
- `sanitize.json`, `line-map.json`, and `review.json`
- local unit and CLI smoke tests

This plan does not implement:

- `clean --mode codex`
- `clean --mode mlx`
- `chunk`
- `synthesize`
- `stitch`
- TTS provider adapters
- A2A wrappers

Those belong in later plans after the job foundation lands.

## File Structure

- Create `pdftoaudio`: root executable CLI entry point. Adds `app/` to `sys.path`, calls `pdftoaudio_core.cli.main()`.
- Create `app/pdftoaudio_core/__init__.py`: package marker and version constant.
- Create `app/pdftoaudio_core/jobs.py`: job path resolution, manifest creation, status inspection, atomic writes.
- Create `app/pdftoaudio_core/cli.py`: `argparse` parser and command dispatch.
- Create `app/pdftoaudio_core/extract.py`: PDF extraction from `source/original.pdf` to `text/raw.txt`.
- Create `app/pdftoaudio_core/sanitize.py`: conservative deterministic text normalization and reports.
- Create `app/pdftoaudio_core/review.py`: non-mutating review detectors and `review.json`.
- Modify `.gitignore`: add `jobs/`.
- Modify `README.md`: add the first job CLI workflow.
- Create `tests/test_jobs.py`: manifest and path tests.
- Create `tests/test_cli.py`: CLI smoke tests for `init`, `status`, missing inputs, and help.
- Create `tests/test_extract.py`: PDF extraction behavior with a fake `PdfReader`.
- Create `tests/test_sanitize.py`: sanitizer output and reports.
- Create `tests/test_review.py`: review detector output.

## Task 1: Job Workspace And Manifest Core

**Files:**
- Create: `app/pdftoaudio_core/__init__.py`
- Create: `app/pdftoaudio_core/jobs.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Produces: `JobPaths` dataclass with `root`, `book`, `job_dir`, `source_dir`, `text_dir`, `reports_dir`, `chunks_dir`, `audio_dir`, `manifest_path`, `source_pdf`, `raw_text`, `sanitized_text`, `cleaned_text`, `sanitize_report`, `line_map_report`, `review_report`.
- Produces: `resolve_job(project_root: Path, book: str) -> JobPaths`.
- Produces: `init_job(project_root: Path, book: str, source_pdf: Path, force: bool = False) -> dict`.
- Produces: `load_manifest(paths: JobPaths) -> dict`.
- Produces: `save_manifest(paths: JobPaths, manifest: dict) -> None`.
- Produces: `update_step(paths: JobPaths, step: str, status: str, output: str | None = None, error: str | None = None) -> dict`.
- Produces: `inspect_status(paths: JobPaths) -> dict`.
- Consumes: Standard library only.

- [ ] **Step 1: Write the failing job tests**

Create `tests/test_jobs.py`:

```python
import json
import shutil
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_jobs -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.pdftoaudio_core'`.

- [ ] **Step 3: Create the package marker**

Create `app/pdftoaudio_core/__init__.py`:

```python
"""Core modules for the pdftoaudio job-first CLI."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Implement job workspace and manifest helpers**

Create `app/pdftoaudio_core/jobs.py`:

```python
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOOK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class JobPaths:
    root: Path
    book: str
    job_dir: Path
    source_dir: Path
    text_dir: Path
    reports_dir: Path
    chunks_dir: Path
    audio_dir: Path
    manifest_path: Path
    source_pdf: Path
    raw_text: Path
    sanitized_text: Path
    cleaned_text: Path
    sanitize_report: Path
    line_map_report: Path
    review_report: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_book_name(book: str) -> None:
    if not BOOK_RE.match(book):
        raise ValueError(
            "Book names may contain letters, numbers, dots, underscores, and hyphens."
        )


def resolve_job(project_root: Path, book: str) -> JobPaths:
    validate_book_name(book)
    root = project_root.resolve()
    job_dir = root / "jobs" / book
    source_dir = job_dir / "source"
    text_dir = job_dir / "text"
    reports_dir = job_dir / "reports"
    chunks_dir = job_dir / "chunks"
    audio_dir = job_dir / "audio"
    return JobPaths(
        root=root,
        book=book,
        job_dir=job_dir,
        source_dir=source_dir,
        text_dir=text_dir,
        reports_dir=reports_dir,
        chunks_dir=chunks_dir,
        audio_dir=audio_dir,
        manifest_path=job_dir / "manifest.json",
        source_pdf=source_dir / "original.pdf",
        raw_text=text_dir / "raw.txt",
        sanitized_text=text_dir / "sanitized.txt",
        cleaned_text=text_dir / "cleaned.txt",
        sanitize_report=reports_dir / "sanitize.json",
        line_map_report=reports_dir / "line-map.json",
        review_report=reports_dir / "review.json",
    )


def ensure_job_dirs(paths: JobPaths) -> None:
    for directory in (
        paths.source_dir,
        paths.text_dir,
        paths.reports_dir,
        paths.chunks_dir,
        paths.audio_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def manifest_template(book: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "book": book,
        "created_at": now,
        "updated_at": now,
        "source_pdf": "source/original.pdf",
        "settings": {
            "chunk_size": 4900,
            "cleanup_mode": None,
            "tts_provider": None,
            "voice": None,
        },
        "steps": {},
    }


def load_manifest(paths: JobPaths) -> dict[str, Any]:
    if not paths.manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {paths.manifest_path}")
    return json.loads(paths.manifest_path.read_text(encoding="utf-8"))


def save_manifest(paths: JobPaths, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now()
    atomic_write_json(paths.manifest_path, manifest)


def update_step(
    paths: JobPaths,
    step: str,
    status: str,
    output: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(paths)
    manifest.setdefault("steps", {})[step] = {
        "status": status,
        "output": output,
        "error": error,
        "updated_at": utc_now(),
    }
    save_manifest(paths, manifest)
    return manifest


def init_job(
    project_root: Path,
    book: str,
    source_pdf: Path,
    force: bool = False,
) -> dict[str, Any]:
    source_pdf = source_pdf.expanduser().resolve()
    if not source_pdf.exists():
        raise FileNotFoundError(f"Missing source PDF: {source_pdf}")

    paths = resolve_job(project_root, book)
    ensure_job_dirs(paths)

    if paths.source_pdf.exists() and not force:
        raise FileExistsError(f"Job already has source PDF: {paths.source_pdf}")

    shutil.copyfile(source_pdf, paths.source_pdf)
    manifest = manifest_template(book)
    atomic_write_json(paths.manifest_path, manifest)
    update_step(paths, "init", "ok", output="source/original.pdf")
    return load_manifest(paths)


STATUS_FILES = (
    ("source/original.pdf", "source_pdf"),
    ("text/raw.txt", "raw_text"),
    ("text/sanitized.txt", "sanitized_text"),
    ("reports/sanitize.json", "sanitize_report"),
    ("reports/line-map.json", "line_map_report"),
    ("reports/review.json", "review_report"),
    ("text/cleaned.txt", "cleaned_text"),
)


def next_command(paths: JobPaths) -> str | None:
    if not paths.source_pdf.exists():
        return f"pdftoaudio init {paths.book} <path-to-pdf>"
    if not paths.raw_text.exists():
        return f"pdftoaudio extract {paths.book}"
    if not paths.sanitized_text.exists():
        return f"pdftoaudio sanitize {paths.book}"
    if not paths.review_report.exists():
        return f"pdftoaudio review {paths.book}"
    if not paths.cleaned_text.exists():
        return f"pdftoaudio clean {paths.book} --mode codex"
    return None


def inspect_status(paths: JobPaths) -> dict[str, Any]:
    files: dict[str, str] = {}
    for display_path, attr_name in STATUS_FILES:
        files[display_path] = "ok" if getattr(paths, attr_name).exists() else "missing"

    manifest = None
    if paths.manifest_path.exists():
        manifest = load_manifest(paths)

    return {
        "book": paths.book,
        "job_dir": str(paths.job_dir),
        "manifest": manifest,
        "files": files,
        "next_command": next_command(paths),
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_jobs -v
```

Expected: PASS all six tests.

- [ ] **Step 6: Commit**

```bash
git add app/pdftoaudio_core/__init__.py app/pdftoaudio_core/jobs.py tests/test_jobs.py
git commit -m "Add job workspace manifest core"
```

## Task 2: Root CLI With `init` And `status`

**Files:**
- Create: `pdftoaudio`
- Create: `app/pdftoaudio_core/cli.py`
- Modify: `.gitignore`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `init_job`, `inspect_status`, and `resolve_job` from `app/pdftoaudio_core/jobs.py`.
- Produces: `main(argv: list[str] | None = None, project_root: Path | None = None) -> int`.
- Produces: root command `./pdftoaudio`.

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
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
        self.assertEqual(stderr, "")

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_cli -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.pdftoaudio_core.cli'`.

- [ ] **Step 3: Implement CLI dispatch**

Create `app/pdftoaudio_core/cli.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .jobs import init_job, inspect_status, resolve_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdftoaudio",
        description="Turn PDFs into audiobooks through inspectable local job files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a job from a source PDF")
    init_parser.add_argument("book")
    init_parser.add_argument("pdf")
    init_parser.add_argument("--force", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show job files and next step")
    status_parser.add_argument("book")

    extract_parser = subparsers.add_parser("extract", help="Extract PDF text")
    extract_parser.add_argument("book")
    extract_parser.add_argument("--force", action="store_true")

    sanitize_parser = subparsers.add_parser(
        "sanitize",
        help="Normalize safe text characters and write sanitize reports",
    )
    sanitize_parser.add_argument("book")
    sanitize_parser.add_argument("--force", action="store_true")
    sanitize_parser.add_argument("--report-only", action="store_true")

    review_parser = subparsers.add_parser(
        "review",
        help="Flag suspicious text spans without changing text",
    )
    review_parser.add_argument("book")
    review_parser.add_argument("--force", action="store_true")

    return parser


def print_status(project_root: Path, book: str) -> int:
    paths = resolve_job(project_root, book)
    if not paths.manifest_path.exists():
        print(f"Missing job manifest: {paths.manifest_path}", file=sys.stderr)
        return 1

    status = inspect_status(paths)
    print(book)
    for display_path, state in status["files"].items():
        print(f"  {display_path:<24} {state}")

    if status["next_command"]:
        print()
        print(f"next: {status['next_command']}")
    else:
        print()
        print("next: job foundation steps complete")
    return 0


def main(argv: list[str] | None = None, project_root: Path | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    root = project_root or Path.cwd()

    try:
        if args.command == "init":
            init_job(root, args.book, Path(args.pdf), force=args.force)
            print(f"Initialized job: {args.book}")
            print(f"next: pdftoaudio extract {args.book}")
            return 0

        if args.command == "status":
            return print_status(root, args.book)

        parser.error(f"Command not wired yet: {args.command}")
        return 2

    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create root executable**

Create `pdftoaudio`:

```python
#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app"))

from pdftoaudio_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
chmod +x pdftoaudio
```

Expected: no output.

- [ ] **Step 5: Gitignore job workspaces**

Modify `.gitignore` to include `jobs/`:

```gitignore
*.pdf
*.mp3
.DS_Store
books/*
secrets/*
text/*
jobs/
```

- [ ] **Step 6: Run CLI tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_cli -v
```

Expected: PASS all four tests.

- [ ] **Step 7: Smoke-test root executable help**

Run:

```bash
./pdftoaudio --help
```

Expected output includes:

```text
Turn PDFs into audiobooks through inspectable local job files.
```

- [ ] **Step 8: Commit**

```bash
git add .gitignore pdftoaudio app/pdftoaudio_core/cli.py tests/test_cli.py
git commit -m "Add pdftoaudio init and status CLI"
```

## Task 3: Extract Command

**Files:**
- Create: `app/pdftoaudio_core/extract.py`
- Modify: `app/pdftoaudio_core/cli.py`
- Test: `tests/test_extract.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `JobPaths`, `atomic_write_text`, and `update_step` from `jobs.py`.
- Produces: `extract_pdf(paths: JobPaths, force: bool = False) -> dict`.
- CLI wires `pdftoaudio extract <book> [--force]`.

- [ ] **Step 1: Write failing extract unit tests**

Create `tests/test_extract.py`:

```python
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
```

- [ ] **Step 2: Add CLI smoke coverage for `extract`**

Append this test method to `tests/test_cli.py` inside `CliTests`:

```python
    def test_extract_missing_source_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])
        source = self.project_root / "jobs/my-book/source/original.pdf"
        source.unlink()

        code, stdout, stderr = self.run_cli(["extract", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing source PDF", stderr)
```

- [ ] **Step 3: Run extract tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_extract tests.test_cli -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.pdftoaudio_core.extract'`.

- [ ] **Step 4: Implement PDF extraction**

Create `app/pdftoaudio_core/extract.py`:

```python
from __future__ import annotations

from typing import Any

from pypdf import PdfReader

from .jobs import JobPaths, atomic_write_text, update_step


def extract_pdf(paths: JobPaths, force: bool = False) -> dict[str, Any]:
    if not paths.source_pdf.exists():
        update_step(paths, "extract", "error", error=f"Missing source PDF: {paths.source_pdf}")
        raise FileNotFoundError(f"Missing source PDF: {paths.source_pdf}")

    if paths.raw_text.exists() and not force:
        raise FileExistsError(f"Raw text already exists: {paths.raw_text}")

    reader = PdfReader(str(paths.source_pdf))
    page_texts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        page_texts.append(text.strip())

    content = "\n\n".join(page_texts).rstrip() + "\n"
    atomic_write_text(paths.raw_text, content)
    update_step(paths, "extract", "ok", output="text/raw.txt")
    return {"pages": len(reader.pages), "output": "text/raw.txt"}
```

- [ ] **Step 5: Wire `extract` into the CLI**

Modify `app/pdftoaudio_core/cli.py` imports:

```python
from .extract import extract_pdf
from .jobs import init_job, inspect_status, resolve_job
```

Add this branch before `parser.error(...)` in `main()`:

```python
        if args.command == "extract":
            paths = resolve_job(root, args.book)
            extract_pdf(paths, force=args.force)
            print(f"Extracted raw text: jobs/{args.book}/text/raw.txt")
            print(f"next: pdftoaudio sanitize {args.book}")
            return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_extract tests.test_cli -v
```

Expected: PASS all tests.

- [ ] **Step 7: Commit**

```bash
git add app/pdftoaudio_core/extract.py app/pdftoaudio_core/cli.py tests/test_extract.py tests/test_cli.py
git commit -m "Add PDF extraction command"
```

## Task 4: Sanitizer Command And Reports

**Files:**
- Create: `app/pdftoaudio_core/sanitize.py`
- Modify: `app/pdftoaudio_core/cli.py`
- Test: `tests/test_sanitize.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `JobPaths`, `atomic_write_json`, `atomic_write_text`, and `update_step`.
- Produces: `sanitize_text(text: str) -> dict`.
- Produces: `sanitize_job(paths: JobPaths, force: bool = False, report_only: bool = False) -> dict`.
- CLI wires `pdftoaudio sanitize <book> [--force] [--report-only]`.

- [ ] **Step 1: Write failing sanitizer tests**

Create `tests/test_sanitize.py`:

```python
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
        self.assertEqual([change["code"] for change in result["changes"]], [
            "nbsp",
            "soft_hyphen",
            "control_character",
            "repeated_blank_lines",
            "control_character",
        ])

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
```

- [ ] **Step 2: Add CLI smoke coverage for `sanitize`**

Append this test method to `tests/test_cli.py` inside `CliTests`:

```python
    def test_sanitize_missing_raw_text_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])

        code, stdout, stderr = self.run_cli(["sanitize", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing raw text", stderr)
```

- [ ] **Step 3: Run sanitizer tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_sanitize tests.test_cli -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.pdftoaudio_core.sanitize'`.

- [ ] **Step 4: Implement deterministic sanitizer**

Create `app/pdftoaudio_core/sanitize.py`:

```python
from __future__ import annotations

from typing import Any

from .jobs import JobPaths, atomic_write_json, atomic_write_text, update_step, utc_now


def is_disallowed_control(character: str) -> bool:
    return ord(character) < 32 and character not in "\n\t"


def append_change(
    changes: list[dict[str, Any]],
    code: str,
    raw_line: int,
    column: int,
    before: str,
    after: str,
) -> None:
    changes.append(
        {
            "code": code,
            "raw_line": raw_line,
            "column": column,
            "before": before,
            "after": after,
        }
    )


def sanitize_text(text: str) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    output_lines: list[str] = []
    line_map: list[dict[str, int]] = []
    blank_run = 0

    raw_lines = text.split("\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]

    for raw_index, raw_line in enumerate(raw_lines, start=1):
        cleaned_chars: list[str] = []
        for column, character in enumerate(raw_line, start=1):
            if character == "\u00a0":
                append_change(changes, "nbsp", raw_index, column, character, " ")
                cleaned_chars.append(" ")
            elif character == "\u00ad":
                append_change(changes, "soft_hyphen", raw_index, column, character, "")
            elif is_disallowed_control(character):
                append_change(changes, "control_character", raw_index, column, character, " ")
                cleaned_chars.append(" ")
            else:
                cleaned_chars.append(character)

        cleaned_line = "".join(cleaned_chars).rstrip()
        if cleaned_line == "":
            blank_run += 1
            if blank_run > 1:
                append_change(changes, "repeated_blank_lines", raw_index, 1, "", "")
                continue
        else:
            blank_run = 0

        output_lines.append(cleaned_line)
        line_map.append({"raw_line": raw_index, "sanitized_line": len(output_lines)})

    sanitized = "\n".join(output_lines).rstrip() + "\n"
    return {"text": sanitized, "changes": changes, "line_map": line_map}


def sanitize_job(
    paths: JobPaths,
    force: bool = False,
    report_only: bool = False,
) -> dict[str, Any]:
    if not paths.raw_text.exists():
        update_step(paths, "sanitize", "error", error=f"Missing raw text: {paths.raw_text}")
        raise FileNotFoundError(f"Missing raw text: {paths.raw_text}")

    if paths.sanitized_text.exists() and not force and not report_only:
        raise FileExistsError(f"Sanitized text already exists: {paths.sanitized_text}")

    result = sanitize_text(paths.raw_text.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "book": paths.book,
        "generated_at": utc_now(),
        "input": "text/raw.txt",
        "output": None if report_only else "text/sanitized.txt",
        "changes": result["changes"],
    }
    line_map = {
        "schema_version": 1,
        "book": paths.book,
        "generated_at": utc_now(),
        "input": "text/raw.txt",
        "output": "text/sanitized.txt",
        "lines": result["line_map"],
    }

    atomic_write_json(paths.sanitize_report, report)
    atomic_write_json(paths.line_map_report, line_map)
    if not report_only:
        atomic_write_text(paths.sanitized_text, result["text"])

    update_step(
        paths,
        "sanitize",
        "ok",
        output="reports/sanitize.json" if report_only else "text/sanitized.txt",
    )
    return report
```

- [ ] **Step 5: Wire `sanitize` into the CLI**

Modify `app/pdftoaudio_core/cli.py` imports:

```python
from .extract import extract_pdf
from .jobs import init_job, inspect_status, resolve_job
from .sanitize import sanitize_job
```

Add this branch before `parser.error(...)` in `main()`:

```python
        if args.command == "sanitize":
            paths = resolve_job(root, args.book)
            sanitize_job(paths, force=args.force, report_only=args.report_only)
            print(f"Wrote sanitize report: jobs/{args.book}/reports/sanitize.json")
            if args.report_only:
                print(f"next: pdftoaudio sanitize {args.book}")
            else:
                print(f"next: pdftoaudio review {args.book}")
            return 0
```

- [ ] **Step 6: Run sanitizer tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_sanitize tests.test_cli -v
```

Expected: PASS all tests.

- [ ] **Step 7: Commit**

```bash
git add app/pdftoaudio_core/sanitize.py app/pdftoaudio_core/cli.py tests/test_sanitize.py tests/test_cli.py
git commit -m "Add deterministic sanitize command"
```

## Task 5: Review Command And Suspicion Report

**Files:**
- Create: `app/pdftoaudio_core/review.py`
- Modify: `app/pdftoaudio_core/cli.py`
- Test: `tests/test_review.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `JobPaths`, `atomic_write_json`, `update_step`, and `utc_now`.
- Produces: `review_text(text: str, book: str) -> dict`.
- Produces: `review_job(paths: JobPaths, force: bool = False) -> dict`.
- CLI wires `pdftoaudio review <book> [--force]`.

- [ ] **Step 1: Write failing review tests**

Create `tests/test_review.py`:

```python
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
        text = "\n".join([
            "1",
            "Chapter Title",
            "hyphen-",
            "ated word",
            "Name | Value | Notes",
            long_sentence,
            "Cafe \u2603",
        ])

        report = review_text(text, "my-book")
        codes = [issue["code"] for issue in report["issues"]]

        self.assertIn("likely_page_number", codes)
        self.assertIn("hyphenated_line_break", codes)
        self.assertIn("table_like_block", codes)
        self.assertIn("long_sentence", codes)
        self.assertIn("non_ascii_character", codes)

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
```

- [ ] **Step 2: Add CLI smoke coverage for `review`**

Append this test method to `tests/test_cli.py` inside `CliTests`:

```python
    def test_review_missing_sanitized_text_reports_error(self):
        self.run_cli(["init", "my-book", str(self.pdf)])

        code, stdout, stderr = self.run_cli(["review", "my-book"])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Missing sanitized text", stderr)
```

- [ ] **Step 3: Run review tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_review tests.test_cli -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.pdftoaudio_core.review'`.

- [ ] **Step 4: Implement review detectors**

Create `app/pdftoaudio_core/review.py`:

```python
from __future__ import annotations

import re
from typing import Any

from .jobs import JobPaths, atomic_write_json, update_step, utc_now


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def issue(
    code: str,
    line_start: int,
    line_end: int,
    severity: str,
    message: str,
    excerpt: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "line_start": line_start,
        "line_end": line_end,
        "severity": severity,
        "message": message,
        "excerpt": excerpt[:240],
    }


def find_long_sentences(text: str, start_line: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sentences = SENTENCE_SPLIT_RE.split(text)
    for sentence in sentences:
        compact = " ".join(sentence.split())
        if len(compact) >= 500:
            findings.append(
                issue(
                    "long_sentence",
                    start_line,
                    start_line,
                    "high",
                    "Sentence is at least 500 characters and may fail TTS.",
                    compact,
                )
            )
    return findings


def review_text(text: str, book: str) -> dict[str, Any]:
    lines = text.splitlines()
    issues: list[dict[str, Any]] = []

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.isdigit():
            issues.append(
                issue(
                    "likely_page_number",
                    index,
                    index,
                    "medium",
                    "Line contains only digits and may be page furniture.",
                    line,
                )
            )

        if line.rstrip().endswith("-") and index < len(lines):
            issues.append(
                issue(
                    "hyphenated_line_break",
                    index,
                    index + 1,
                    "medium",
                    "Line ends with a hyphen and may split a word across lines.",
                    line + "\\n" + lines[index],
                )
            )

        if line.count("|") >= 2 or line.count("\t") >= 2:
            issues.append(
                issue(
                    "table_like_block",
                    index,
                    index,
                    "medium",
                    "Line contains repeated column separators.",
                    line,
                )
            )

        non_ascii = [character for character in line if ord(character) > 127]
        if non_ascii:
            issues.append(
                issue(
                    "non_ascii_character",
                    index,
                    index,
                    "low",
                    "Line contains non-ASCII characters for review before SSML/TTS.",
                    line,
                )
            )

        issues.extend(find_long_sentences(line, index))

    return {
        "schema_version": 1,
        "book": book,
        "generated_at": utc_now(),
        "input": "text/sanitized.txt",
        "issues": issues,
    }


def review_job(paths: JobPaths, force: bool = False) -> dict[str, Any]:
    if not paths.sanitized_text.exists():
        update_step(paths, "review", "error", error=f"Missing sanitized text: {paths.sanitized_text}")
        raise FileNotFoundError(f"Missing sanitized text: {paths.sanitized_text}")

    if paths.review_report.exists() and not force:
        raise FileExistsError(f"Review report already exists: {paths.review_report}")

    report = review_text(paths.sanitized_text.read_text(encoding="utf-8"), paths.book)
    atomic_write_json(paths.review_report, report)
    update_step(paths, "review", "ok", output="reports/review.json")
    return report
```

- [ ] **Step 5: Wire `review` into the CLI**

Modify `app/pdftoaudio_core/cli.py` imports:

```python
from .extract import extract_pdf
from .jobs import init_job, inspect_status, resolve_job
from .review import review_job
from .sanitize import sanitize_job
```

Add this branch before `parser.error(...)` in `main()`:

```python
        if args.command == "review":
            paths = resolve_job(root, args.book)
            report = review_job(paths, force=args.force)
            print(f"Wrote review report: jobs/{args.book}/reports/review.json")
            print(f"issues: {len(report['issues'])}")
            print(f"next: pdftoaudio clean {args.book} --mode codex")
            return 0
```

- [ ] **Step 6: Run review tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_review tests.test_cli -v
```

Expected: PASS all tests.

- [ ] **Step 7: Commit**

```bash
git add app/pdftoaudio_core/review.py app/pdftoaudio_core/cli.py tests/test_review.py tests/test_cli.py
git commit -m "Add text review command"
```

## Task 6: README Workflow And Full Local Test Pass

**Files:**
- Modify: `README.md`
- Test: all `tests/*.py`

**Interfaces:**
- Consumes: root `./pdftoaudio` CLI.
- Produces: README section documenting the first job CLI workflow.

- [ ] **Step 1: Update README with the job CLI foundation workflow**

Replace the top of `README.md` with this content, keeping the existing Google TTS quota and SSML sections below it:

````markdown
## Job CLI Workflow

The new workflow uses one directory per book under `jobs/`.

```bash
./pdftoaudio init my-book ./books/my-book.pdf
./pdftoaudio extract my-book
./pdftoaudio sanitize my-book
./pdftoaudio review my-book
./pdftoaudio status my-book
```

Files are written under:

```text
jobs/my-book/
  source/original.pdf
  text/raw.txt
  text/sanitized.txt
  reports/sanitize.json
  reports/line-map.json
  reports/review.json
  manifest.json
```

`sanitize` applies conservative character and whitespace cleanup. `review` does not edit text; it flags suspicious line ranges for later Codex or MLX cleanup.

The older script workflow still exists while the CLI migration is in progress.

## Older Script Workflow
````

- [ ] **Step 2: Run all unit tests**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: PASS all tests in `test_jobs`, `test_cli`, `test_extract`, `test_sanitize`, and `test_review`.

- [ ] **Step 3: Run CLI help smoke test**

Run:

```bash
./pdftoaudio --help
```

Expected output includes:

```text
init
status
extract
sanitize
review
```

- [ ] **Step 4: Run an end-to-end text-only CLI smoke test**

Run:

```bash
tmpdir="$(mktemp -d)"
printf '%s\n' '%PDF-1.4 fake' > "$tmpdir/book.pdf"
./pdftoaudio init smoke "$tmpdir/book.pdf"
mkdir -p jobs/smoke/text
python3 - <<'PY'
from pathlib import Path

Path("jobs/smoke/text/raw.txt").write_text(
    "1\nA\u00a0B\u00adC\nhyphen-\nated\n",
    encoding="utf-8",
)
PY
./pdftoaudio sanitize smoke
./pdftoaudio review smoke
./pdftoaudio status smoke
rm -rf "$tmpdir"
```

Expected output from the final command includes:

```text
reports/review.json      ok
next: pdftoaudio clean smoke --mode codex
```

- [ ] **Step 5: Remove the smoke job**

Run:

```bash
rm -rf jobs/smoke
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "Document job CLI foundation workflow"
```

## Plan Self-Review Checklist

- Spec coverage: this plan covers the first implementation slice from the spec: job workspace, root CLI, `init`, `status`, `extract`, `sanitize`, `review`, conservative reports, `jobs/` gitignore, and local tests.
- Deferred spec areas: Codex cleanup, MLX cleanup, chunking, synthesis, stitching, and A2A are intentionally left for later plans because they are independent subsystems.
- Red-flag scan: no banned task text is present in this plan.
- Type consistency: `JobPaths`, `resolve_job`, `init_job`, `inspect_status`, `extract_pdf`, `sanitize_job`, `review_job`, and `main` are named consistently across tasks.
- Testability: every task has a local `python3 -m unittest` command and a commit point.
