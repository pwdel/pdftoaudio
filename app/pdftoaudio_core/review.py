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
                    line + "\n" + lines[index],
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
