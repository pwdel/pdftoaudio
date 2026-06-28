from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .jobs import JobPaths, atomic_write_json, atomic_write_text, update_step, utc_now


SENTENCE_BOUNDARY_RE = re.compile(r"""[.!?]["')\]]?(?=\s|$)""")
DEFAULT_MAX_BYTES = 4900


def byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def window_end_by_bytes(text: str, start: int, max_bytes: int) -> int:
    total = 0
    end = start

    while end < len(text):
        character_bytes = byte_len(text[end])
        if total + character_bytes > max_bytes:
            break
        total += character_bytes
        end += 1

    if end == start:
        raise ValueError("max_bytes is too small for the next character")

    return end


def last_regex_boundary(window: str, pattern: re.Pattern[str]) -> int | None:
    boundary = None
    for match in pattern.finditer(window):
        boundary = match.end()
    return boundary


def last_string_boundary(window: str, marker: str) -> int | None:
    index = window.rfind(marker)
    if index <= 0:
        return None
    return index + len(marker)


def last_whitespace_boundary(window: str) -> int | None:
    for index in range(len(window) - 1, 0, -1):
        if window[index].isspace():
            return index
    return None


def choose_split_end(text: str, start: int, hard_end: int) -> int:
    if hard_end >= len(text):
        return hard_end

    window = text[start:hard_end]
    for boundary in (
        last_regex_boundary(window, SENTENCE_BOUNDARY_RE),
        last_string_boundary(window, "\n\n"),
        last_string_boundary(window, "\n"),
        last_whitespace_boundary(window),
    ):
        if boundary:
            return start + boundary

    return hard_end


def split_text_for_tts(text: str, max_bytes: int = DEFAULT_MAX_BYTES) -> list[str]:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    chunks: list[str] = []
    start = 0

    while start < len(text):
        while start < len(text) and text[start].isspace():
            start += 1

        if start >= len(text):
            break

        hard_end = window_end_by_bytes(text, start, max_bytes)
        split_end = choose_split_end(text, start, hard_end)
        chunk = text[start:split_end].strip()

        if not chunk:
            start = hard_end
            continue

        chunks.append(chunk)
        start = split_end

    return chunks


def split_text_by_sentence(text: str, max_bytes: int = DEFAULT_MAX_BYTES) -> list[str]:
    """Compatibility wrapper for the legacy helper name."""
    return split_text_for_tts(text, max_bytes=max_bytes)


def split_text_by_size(text: str, max_bytes: int = DEFAULT_MAX_BYTES) -> list[str]:
    """Compatibility wrapper for callers that name chunks by their real purpose."""
    return split_text_for_tts(text, max_bytes=max_bytes)


def source_path(paths: JobPaths, source: str) -> tuple[Path, str]:
    if source == "cleaned":
        return paths.cleaned_text, "text/cleaned.txt"
    if source == "sanitized":
        return paths.sanitized_text, "text/sanitized.txt"
    raise ValueError("source must be 'cleaned' or 'sanitized'")


def existing_chunk_files(paths: JobPaths) -> list[Path]:
    if not paths.chunks_dir.exists():
        return []
    return sorted(paths.chunks_dir.glob("*.txt"))


def chunk_job(
    paths: JobPaths,
    source: str = "cleaned",
    max_bytes: int = DEFAULT_MAX_BYTES,
    force: bool = False,
) -> dict[str, Any]:
    input_path, input_name = source_path(paths, source)
    if not input_path.exists():
        message = f"Missing {source} text: {input_path}"
        update_step(paths, "chunk", "error", error=message)
        raise FileNotFoundError(message)

    existing = existing_chunk_files(paths)
    if (existing or paths.chunk_report.exists()) and not force:
        raise FileExistsError(f"Chunk output already exists: {paths.chunks_dir}")

    try:
        chunks = split_text_for_tts(
            input_path.read_text(encoding="utf-8"),
            max_bytes=max_bytes,
        )
    except ValueError as error:
        update_step(paths, "chunk", "error", error=str(error))
        raise

    paths.chunks_dir.mkdir(parents=True, exist_ok=True)
    if force:
        for chunk_file in existing:
            chunk_file.unlink()

    chunk_entries: list[dict[str, Any]] = []

    for index, chunk in enumerate(chunks, start=1):
        filename = f"{index:03}.txt"
        chunk_path = paths.chunks_dir / filename
        content = chunk.rstrip()
        atomic_write_text(chunk_path, content)
        chunk_entries.append(
            {
                "index": index,
                "path": f"chunks/{filename}",
                "characters": len(content),
                "bytes": byte_len(content),
            }
        )

    report = {
        "schema_version": 1,
        "book": paths.book,
        "generated_at": utc_now(),
        "input": input_name,
        "output": "chunks/",
        "max_bytes": max_bytes,
        "chunks": chunk_entries,
    }
    atomic_write_json(paths.chunk_report, report)
    update_step(paths, "chunk", "ok", output="chunks/")
    return report
