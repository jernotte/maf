from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .markdown import read_markdown_input
from .pdf import read_pdf_input
from .text import read_text_input


@dataclass
class NormalizedInput:
    source_type: str
    source_reference: str
    normalized_brief: str


def _render_brief(title: str, source_type: str, source_reference: str, raw_text: str) -> str:
    return f"""# Normalized Brief

## Title
{title}

## Source Type
{source_type}

## Source Reference
{source_reference}

## Objective
Develop the project work described below using the multi-agent delivery flow.

## Source Material
{raw_text.strip()}

## Initial Constraints
- Preserve alignment with the source material.
- Raise missing requirements as open questions instead of inventing them.
- Produce durable artifacts so later phases can reference the same baseline.
"""


def normalize_input(title: str, input_value: str) -> NormalizedInput:
    candidate = Path(input_value).expanduser()
    if candidate.exists():
        path = candidate.resolve()
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            raw_text = read_pdf_input(path)
            source_type = "pdf"
        elif suffix in {".md", ".markdown"}:
            raw_text = read_markdown_input(path)
            source_type = "markdown"
        else:
            raw_text = read_text_input(path)
            source_type = "text-file"
        return NormalizedInput(
            source_type=source_type,
            source_reference=str(path),
            normalized_brief=_render_brief(title, source_type, str(path), raw_text),
        )

    return NormalizedInput(
        source_type="inline-text",
        source_reference="inline",
        normalized_brief=_render_brief(title, "inline-text", "inline", input_value),
    )

