from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def read_pdf_input(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())
    joined = "\n\n".join(page for page in pages if page)
    if joined.strip():
        return joined
    return (
        "PDF text extraction returned no text. The file is likely image-based.\n"
        "Use OCR or supply a Markdown/text version for stronger downstream results."
    )

