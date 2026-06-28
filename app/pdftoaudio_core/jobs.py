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
    chunk_report: Path


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
        chunk_report=reports_dir / "chunk.json",
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
    ("reports/chunk.json", "chunk_report"),
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
        if paths.chunk_report.exists():
            return f"pdftoaudio synthesize {paths.book} --provider google"
        return f"pdftoaudio clean {paths.book} --mode codex"
    if not paths.chunk_report.exists():
        return f"pdftoaudio chunk {paths.book}"
    return f"pdftoaudio synthesize {paths.book} --provider google"


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
