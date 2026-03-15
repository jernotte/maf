from __future__ import annotations

from pathlib import Path

from ..agents import ClaudeAdapter
from ..config import AppConfig
from ..git import diff_changed_files, snapshot_changed_files
from ..prompts import render_prompt
from ..state import approved_spec_path, load_task, read_text, save_task, task_dir, write_json, write_text
from ..validation import run_validation
from .common import persist_agent_result, require_file, sanitize_agent_output


def run_build(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    if not task.spec_approved:
        raise RuntimeError("Spec is not approved. Run `maf approve-spec --task <task-id>` first.")

    base_dir = task_dir(project_root, config, task_id)
    spec_path = approved_spec_path(project_root, config, task_id)
    require_file(spec_path, "Approved spec is missing.")
    approved_spec = read_text(spec_path)
    validation_commands = config.resolve_validation_commands(task.validation_profile)

    # Load the original source brief for reference content
    brief_path = base_dir / "normalized-brief.md"
    source_brief = read_text(brief_path) if brief_path.exists() else ""

    prompt = render_prompt(
        "build.md",
        title=task.title,
        approved_spec=approved_spec,
        source_brief=source_brief,
        validation_commands="\n".join(f"- {command}" for command in validation_commands)
        or "- No validation commands configured.",
    )

    before = snapshot_changed_files(project_root)
    adapter = ClaudeAdapter(config.agents["claude-build"])
    result = adapter.run(prompt, project_root, base_dir, "build", "implementation")
    persist_agent_result(base_dir / "build", "implementation", result)
    clean_output = sanitize_agent_output(result.stdout)
    write_text(base_dir / "build" / "implementation-log.md", clean_output)

    after = snapshot_changed_files(project_root)
    changed_files = diff_changed_files(before, after)
    write_json(base_dir / "build" / "changed-files.json", {"changed_files": changed_files})

    validation = run_validation(project_root, validation_commands, task.validation_profile)
    write_json(base_dir / "build" / "validation.json", validation.to_dict())

    task.status = "built"
    task.metadata["build_log_path"] = "build/implementation-log.md"
    task.metadata["changed_files_path"] = "build/changed-files.json"
    task.metadata["validation_path"] = "build/validation.json"
    save_task(project_root, config, task)
    return base_dir / "build" / "implementation-log.md"

