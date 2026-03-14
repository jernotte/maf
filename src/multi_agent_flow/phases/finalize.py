from __future__ import annotations

from pathlib import Path

from ..agents import ClaudeAdapter
from ..config import AppConfig
from ..prompts import render_prompt
from ..state import approved_spec_path, load_task, read_text, save_task, task_dir, write_json, write_text
from ..validation import run_validation
from .common import coerce_json_output, persist_agent_result, require_file


def run_finalize(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task_id)

    spec_path = approved_spec_path(project_root, config, task_id)
    gemini_review = base_dir / "review" / "gemini-review.json"
    codex_review = base_dir / "review" / "codex-review.json"
    require_file(spec_path, "Approved spec is missing.")
    require_file(gemini_review, "Gemini review is missing. Run `maf review --task <task-id>` first.")
    require_file(codex_review, "Codex review is missing. Run `maf review --task <task-id>` first.")

    approved_spec = read_text(spec_path)
    gemini_payload = read_text(gemini_review)
    codex_payload = read_text(codex_review)
    validation_commands = config.resolve_validation_commands(task.validation_profile)

    prompt = render_prompt(
        "finalize.md",
        title=task.title,
        approved_spec=approved_spec,
        gemini_review=gemini_payload,
        codex_review=codex_payload,
        validation_commands="\n".join(f"- {command}" for command in validation_commands)
        or "- No validation commands configured.",
    )

    adapter = ClaudeAdapter(config.agents["claude"])
    result = adapter.run(prompt, project_root, base_dir, "finalize", "summary")
    finalize_dir = base_dir / "finalize"
    persist_agent_result(finalize_dir, "summary", result)
    write_text(finalize_dir / "final-summary.md", result.stdout)
    write_json(finalize_dir / "disposition.json", coerce_json_output(result.stdout))

    validation = run_validation(project_root, validation_commands, task.validation_profile)
    write_json(finalize_dir / "validation.json", validation.to_dict())

    task.status = "finalized"
    task.metadata["final_summary_path"] = "finalize/final-summary.md"
    task.metadata["final_validation_path"] = "finalize/validation.json"
    save_task(project_root, config, task)
    return finalize_dir / "final-summary.md"

