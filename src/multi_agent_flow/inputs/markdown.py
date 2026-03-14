from __future__ import annotations

from pathlib import Path


def read_markdown_input(path: Path) -> str:
    return path.read_text(encoding="utf-8")

