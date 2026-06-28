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
