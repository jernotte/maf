from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..agents import CodexAdapter, GeminiAdapter
from ..config import AppConfig
from ..prompts import render_prompt
from ..state import approved_spec_path, load_task, read_text, save_task, task_dir, write_json
from .common import coerce_json_output, persist_agent_result, require_file


def run_review(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task_id)

    spec_path = approved_spec_path(project_root, config, task_id)
    build_log_path = base_dir / "build" / "implementation-log.md"
    changed_files_path = base_dir / "build" / "changed-files.json"
    require_file(spec_path, "Approved spec is missing.")
    require_file(build_log_path, "Build output is missing. Run `maf build --task <task-id>` first.")

    approved_spec = read_text(spec_path)
    implementation_log = read_text(build_log_path)
    changed_files = read_text(changed_files_path) if changed_files_path.exists() else '{"changed_files": []}'

    prompt = render_prompt(
        "review.md",
        title=task.title,
        approved_spec=approved_spec,
        implementation_log=implementation_log,
        changed_files=changed_files,
    )

    review_dir = base_dir / "review"
    jobs = [
        ("gemini", GeminiAdapter(config.agents["gemini"])),
        ("codex", CodexAdapter(config.agents["codex"])),
    ]

    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        future_map = {
            executor.submit(adapter.run, prompt, project_root, base_dir, "review", name): name
            for name, adapter in jobs
        }
        for future in as_completed(future_map):
            name = future_map[future]
            result = future.result()
            persist_agent_result(review_dir, name, result)
            write_json(review_dir / f"{name}-review.json", coerce_json_output(result.stdout))

    task.status = "reviewed"
    task.metadata["gemini_review_path"] = "review/gemini-review.json"
    task.metadata["codex_review_path"] = "review/codex-review.json"
    save_task(project_root, config, task)
    return review_dir

