from __future__ import annotations

from pathlib import Path

from ..agents import ClaudeAdapter
from ..config import AppConfig
from ..prompts import render_prompt
from ..state import (
    approved_spec_path,
    copy_file,
    draft_spec_path,
    load_task,
    read_text,
    save_task,
    task_dir,
    write_text,
)
from .common import persist_agent_result, require_file


def run_spec(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task.task_id)
    normalized_brief = read_text(base_dir / "normalized-brief.md")
    research_summary_path = base_dir / "research" / "synthesis.md"
    research_summary = read_text(research_summary_path) if research_summary_path.exists() else ""

    prompt = render_prompt(
        "spec.md",
        title=task.title,
        normalized_brief=normalized_brief,
        research_summary=research_summary,
    )
    adapter = ClaudeAdapter(config.agents["claude"])
    result = adapter.run(prompt, project_root, base_dir, "spec", "draft")
    persist_agent_result(base_dir / "spec", "draft", result)
    destination = draft_spec_path(project_root, config, task_id)
    write_text(destination, result.stdout)

    task.status = "spec-drafted"
    task.metadata["spec_draft_path"] = "spec/spec-draft.md"
    save_task(project_root, config, task)
    return destination


def approve_spec(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    source = draft_spec_path(project_root, config, task_id)
    require_file(source, "Spec draft is missing. Run `maf spec --task <task-id>` first.")
    destination = approved_spec_path(project_root, config, task_id)
    copy_file(source, destination)
    task.spec_approved = True
    task.status = "spec-approved"
    task.metadata["approved_spec_path"] = "spec/spec-approved.md"
    save_task(project_root, config, task)
    return destination

