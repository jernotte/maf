from __future__ import annotations

import json
from pathlib import Path

from ..models import AgentExecutionResult
from ..state import write_json, write_text


def persist_agent_result(output_dir: Path, stem: str, result: AgentExecutionResult) -> None:
    write_text(output_dir / f"{stem}.{result.agent}.out.md", result.stdout)
    write_text(output_dir / f"{stem}.{result.agent}.err.txt", result.stderr)
    write_json(output_dir / f"{stem}.{result.agent}.meta.json", result.to_dict())


def coerce_json_output(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "parse_error": "Agent output was not valid JSON.",
            "raw_output": raw_text,
        }


def require_file(path: Path, message: str) -> None:
    if not path.exists():
        raise FileNotFoundError(message)

