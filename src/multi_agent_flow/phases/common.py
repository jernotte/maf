from __future__ import annotations

import json
from pathlib import Path
import re

from ..models import AgentExecutionResult
from ..state import write_json, write_text


def persist_worker_findings(
    iter_dir: Path,
    stem: str,
    focus: str,
    result: AgentExecutionResult,
) -> None:
    """Ensure a canonical findings file and metadata sidecar exist for a worker.

    Three cases:
    1. Agent wrote the file via write_findings tool → file already exists.
    2. Agent didn't write the file (Gemini/Codex, or Claude didn't use tool) → write sanitized stdout.
    3. Agent failed → write whatever stdout was captured.
    """
    findings_path = iter_dir / f"{stem}.findings.md"
    source: str

    if findings_path.exists():
        # Case 1: agent already wrote findings via the write_findings tool
        source = "agent_write"
    else:
        # Case 2/3: orchestrator writes sanitized stdout as fallback
        clean_output = sanitize_agent_output(result.stdout)
        write_text(findings_path, clean_output)
        source = "orchestrator_fallback"

    size_bytes = findings_path.stat().st_size

    meta = {
        "stem": stem,
        "focus": focus,
        "size_bytes": size_bytes,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "source": source,
    }
    write_json(iter_dir / f"{stem}.findings.meta.json", meta)


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes}B"


def build_worker_manifest(iter_dir: Path) -> str:
    """Build a markdown manifest table from worker metadata sidecar files."""
    rows: list[tuple[str, str, str, str]] = []
    for meta_path in sorted(iter_dir.glob("*.findings.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        findings_path = iter_dir / f"{meta['stem']}.findings.md"
        rows.append((
            meta["stem"],
            meta["focus"],
            _format_size(meta["size_bytes"]),
            str(findings_path),
        ))

    if not rows:
        return "No worker outputs available."

    lines = [
        "## Available Worker Outputs",
        "",
        "| Worker | Focus | Size | Path |",
        "|--------|-------|------|------|",
    ]
    for stem, focus, size, path in rows:
        lines.append(f"| {stem} | {focus} | {size} | {path} |")

    lines.append("")
    lines.append(
        "Read specific worker outputs using the Read tool. "
        "Search across all findings using Grep."
    )
    return "\n".join(lines)


def build_syntheses_manifest(research_dir: Path, total_iterations: int) -> str:
    """Build a markdown manifest of iteration synthesis files."""
    rows: list[tuple[int, str, str]] = []
    for i in range(1, total_iterations + 1):
        synth_path = research_dir / f"iteration-{i:03d}" / "synthesis.md"
        if synth_path.exists():
            size = _format_size(synth_path.stat().st_size)
            rows.append((i, size, str(synth_path)))

    if not rows:
        return "No iteration syntheses available."

    lines = [
        "## Iteration Syntheses",
        "",
        "| Iteration | Size | Path |",
        "|-----------|------|------|",
    ]
    for iteration, size, path in rows:
        lines.append(f"| {iteration} | {size} | {path} |")

    lines.append("")
    lines.append(
        "Read each synthesis using the Read tool, starting from iteration 1. "
        "Use Grep to search for specific themes across all syntheses."
    )
    return "\n".join(lines)


def _extract_from_write_calls(text: str) -> str | None:
    """Try to extract content from hallucinated Write tool calls.

    When an LLM hallucinates tool usage, it sometimes wraps the actual
    content inside a Write tool call's "content" parameter. This extracts
    the longest such block if present.
    """
    contents: list[str] = []
    for match in re.finditer(
        r'\{"name":\s*"Write",\s*"arguments":\s*(\{.*?\})\}',
        text,
        re.DOTALL,
    ):
        try:
            args = json.loads(match.group(1))
            if "content" in args and len(args["content"]) > 500:
                contents.append(args["content"])
        except json.JSONDecodeError:
            pass
    if contents:
        return max(contents, key=len)
    return None


def _strip_tool_blocks(text: str) -> str:
    """Strip tool call XML blocks and preamble lines, keep everything else."""
    lines = text.split("\n")
    output: list[str] = []
    in_block = False

    for line in lines:
        stripped = line.strip()

        if stripped in ("<tool_call>", "<tool_use>", "<tool_result>"):
            in_block = True
            continue
        if stripped in ("</tool_call>", "</tool_use>", "</tool_result>"):
            in_block = False
            continue
        if in_block:
            continue

        # Standalone JSON tool calls not wrapped in tags
        if re.match(r'^\{"(name|tool_name)":', stripped):
            continue

        # Preamble lines where agent announces tool usage
        if re.match(
            r"^(I'll |I will |Let me |I need to |Now let me )"
            r"(read|fetch|search|look up|check|load|open|access|produce|verify)",
            stripped,
            re.IGNORECASE,
        ):
            continue

        # Trailing unclosed tool tags
        if stripped.startswith("<tool_call>") or stripped.startswith("<tool_use>") or stripped.startswith("<tool_result>"):
            in_block = True
            continue

        output.append(line)

    result = "\n".join(output)
    # Remove any remaining unclosed tool artifacts at end of text
    result = re.sub(r"\n*<tool_(?:call|use|result)>.*$", "", result, flags=re.DOTALL)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def sanitize_agent_output(text: str) -> str:
    """Clean hallucinated tool call artifacts from agent output.

    Strategy:
    1. If the output contains a Write tool call with markdown content,
       extract that content (the LLM wrote the real output inside a
       hallucinated file write).
    2. Otherwise, strip tool call blocks and keep the remaining text.
    """
    # Strategy 1: extract from Write calls
    extracted = _extract_from_write_calls(text)
    if extracted and len(extracted) > len(text) * 0.3:
        # Clean any nested tool artifacts in the extracted content too
        return _strip_tool_blocks(extracted)

    # Strategy 2: strip tool blocks, keep the rest
    return _strip_tool_blocks(text)


def persist_agent_result(output_dir: Path, stem: str, result: AgentExecutionResult) -> None:
    write_text(output_dir / f"{stem}.{result.agent}.out.md", result.stdout)
    write_text(output_dir / f"{stem}.{result.agent}.err.txt", result.stderr)
    write_json(output_dir / f"{stem}.{result.agent}.meta.json", result.to_dict())


def coerce_json_output(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    # Try extracting JSON from markdown code fences
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {
        "parse_error": "Agent output was not valid JSON.",
        "raw_output": raw_text,
    }


def require_file(path: Path, message: str) -> None:
    if not path.exists():
        raise FileNotFoundError(message)
