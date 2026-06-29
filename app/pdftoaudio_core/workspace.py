from __future__ import annotations

from pathlib import Path
from typing import Any


WORKSPACE_DIRECTORIES = (
    ("books", "source PDFs before init, for example books/my-book.pdf"),
    ("jobs", "generated per-book job files; do not commit"),
    ("secrets", "local credentials and provider config; do not commit"),
)


def inspect_workspace(project_root: Path, fix: bool = False) -> list[dict[str, Any]]:
    root = project_root.resolve()
    entries: list[dict[str, Any]] = []

    for directory, purpose in WORKSPACE_DIRECTORIES:
        path = root / directory
        created = False

        if path.is_dir():
            status = "ok"
        elif path.exists():
            status = "not_directory"
        elif fix:
            path.mkdir(parents=True, exist_ok=True)
            status = "created"
            created = True
        else:
            status = "missing"

        entries.append(
            {
                "path": f"{directory}/",
                "status": status,
                "purpose": purpose,
                "created": created,
            }
        )

    return entries


def workspace_ready(entries: list[dict[str, Any]]) -> bool:
    return all(entry["status"] in {"ok", "created"} for entry in entries)
