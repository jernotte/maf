from __future__ import annotations

from pathlib import Path

from ..agents import ClaudeAdapter
from ..config import AppConfig
from ..progress import agent_done, agent_start, log
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
from .common import persist_agent_result, require_file, sanitize_agent_output


def run_spec_direct(
    project_root: str,
    config: AppConfig,
    title: str,
    input_path: str,
) -> tuple[str, Path]:
    """Create a task from raw input and generate a spec directly — no normalization, no research."""
    from ..state import create_task

    input_file = Path(input_path).expanduser().resolve()
    if input_file.exists():
        raw_content = read_text(input_file)
        source_type = "direct-file"
    else:
        raw_content = input_path
        source_type = "direct-inline"

    task = create_task(
        project_root=project_root,
        config=config,
        title=title,
        input_value=input_path,
        source_type=source_type,
        validation_profile=None,
    )
    base_dir = task_dir(project_root, config, task.task_id)
    # Write the raw input as the brief — no normalization
    write_text(base_dir / "normalized-brief.md", raw_content)
    task.status = "researched"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    save_task(project_root, config, task)

    # Now run spec generation
    spec_path = run_spec(project_root, config, task.task_id)
    return task.task_id, spec_path


def run_spec(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task.task_id)
    normalized_brief = read_text(base_dir / "normalized-brief.md")
    research_summary_path = base_dir / "research" / "synthesis.md"
    research_summary = read_text(research_summary_path) if research_summary_path.exists() else ""

    log("spec", "Rendering prompt...")
    prompt = render_prompt(
        "spec.md",
        title=task.title,
        normalized_brief=normalized_brief,
        research_summary=research_summary,
    )
    adapter = ClaudeAdapter(config.agents["claude"])
    agent_start("spec", "claude")
    result = adapter.run(prompt, project_root, base_dir, "spec", "draft")
    agent_done("spec", "claude", result.duration_s, last=True)
    persist_agent_result(base_dir / "spec", "draft", result)
    clean_output = sanitize_agent_output(result.stdout)
    destination = draft_spec_path(project_root, config, task_id)
    write_text(destination, clean_output)

    task.status = "spec-drafted"
    task.metadata["spec_draft_path"] = "spec/spec-draft.md"
    save_task(project_root, config, task)
    log("spec", "Done → spec/spec-draft.md")
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

