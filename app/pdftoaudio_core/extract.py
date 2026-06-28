from __future__ import annotations

from typing import Any

from .jobs import JobPaths, atomic_write_text, update_step

try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    PdfReader = None


def extract_pdf(paths: JobPaths, force: bool = False) -> dict[str, Any]:
    if not paths.source_pdf.exists():
        update_step(paths, "extract", "error", error=f"Missing source PDF: {paths.source_pdf}")
        raise FileNotFoundError(f"Missing source PDF: {paths.source_pdf}")

    if paths.raw_text.exists() and not force:
        raise FileExistsError(f"Raw text already exists: {paths.raw_text}")

    if PdfReader is None:
        message = "pypdf is required to extract PDF text"
        update_step(paths, "extract", "error", error=message)
        raise ModuleNotFoundError(message)

    reader = PdfReader(str(paths.source_pdf))
    page_texts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        page_texts.append(text.strip())

    content = "\n\n".join(page_texts).rstrip() + "\n"
    atomic_write_text(paths.raw_text, content)
    update_step(paths, "extract", "ok", output="text/raw.txt")
    return {"pages": len(reader.pages), "output": "text/raw.txt"}
