from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..agents import ClaudeAdapter, CodexAdapter, GeminiAdapter
from ..config import AppConfig
from ..inputs import normalize_input
from ..progress import agent_done, agent_start, log
from ..prompts import render_prompt
from ..state import create_task, save_task, task_dir, write_text
from .common import persist_agent_result


def _build_adapters(config: AppConfig) -> dict[str, object]:
    return {
        "claude": ClaudeAdapter(config.agents["claude"]),
        "codex": CodexAdapter(config.agents["codex"]),
        "gemini": GeminiAdapter(config.agents["gemini"]),
    }


def run_research(
    project_root: str,
    config: AppConfig,
    title: str,
    input_value: str,
    validation_profile: str | None,
    max_research_workers: int | None,
) -> str:
    normalized = normalize_input(title=title, input_value=input_value)
    task = create_task(
        project_root=project_root,
        config=config,
        title=title,
        input_value=input_value,
        source_type=normalized.source_type,
        validation_profile=validation_profile,
    )
    base_dir = task_dir(project_root, config, task.task_id)
    write_text(base_dir / "normalized-brief.md", normalized.normalized_brief)

    worker_focuses = config.research.worker_focuses[:]
    if max_research_workers is not None:
        worker_focuses = worker_focuses[:max_research_workers]
    else:
        worker_focuses = worker_focuses[: config.research.max_workers]

    adapters = _build_adapters(config)
    jobs: list[tuple[str, str, object, str]] = []
    for index, focus in enumerate(worker_focuses, start=1):
        jobs.append(
            (
                f"claude-worker-{index}",
                focus,
                adapters["claude"],
                render_prompt(
                    "research_worker.md",
                    title=task.title,
                    normalized_brief=normalized.normalized_brief,
                    focus=focus,
                ),
            )
        )
    jobs.append(
        (
            "gemini",
            "broad-research",
            adapters["gemini"],
            render_prompt(
                "research_worker.md",
                title=task.title,
                normalized_brief=normalized.normalized_brief,
                focus="broad-research",
            ),
        )
    )
    jobs.append(
        (
            "codex",
            "broad-research",
            adapters["codex"],
            render_prompt(
                "research_worker.md",
                title=task.title,
                normalized_brief=normalized.normalized_brief,
                focus="broad-research",
            ),
        )
    )

    research_dir = base_dir / "research"
    summaries: list[str] = []

    log("research", f"Starting {len(jobs)} research workers...")
    for stem, focus, _adapter, _prompt in jobs:
        agent_start("research", stem, label=focus)

    completed_count = 0
    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        future_map = {
            executor.submit(
                adapter.run,
                prompt,
                project_root,
                base_dir,
                "research",
                stem,
            ): (stem, focus)
            for stem, focus, adapter, prompt in jobs
        }
        for future in as_completed(future_map):
            stem, focus = future_map[future]
            result = future.result()
            completed_count += 1
            agent_done("research", stem, result.duration_s, label=focus, last=completed_count == len(jobs))
            persist_agent_result(research_dir, stem, result)
            summaries.append(
                f"## {stem}\n"
                f"- focus: {focus}\n"
                f"- exit_code: {result.exit_code}\n"
                f"- timed_out: {result.timed_out}\n\n"
                f"{result.stdout.strip()}\n"
            )

    log("research", "Running synthesis...")
    agent_start("research", "claude", label="synthesis")
    synthesis = adapters["claude"].run(
        render_prompt(
            "research_synthesis.md",
            title=task.title,
            normalized_brief=normalized.normalized_brief,
            research_outputs="\n\n".join(summaries),
        ),
        project_root,
        base_dir,
        "research",
        "synthesis",
    )
    agent_done("research", "claude", synthesis.duration_s, label="synthesis", last=True)
    persist_agent_result(research_dir, "synthesis", synthesis)
    write_text(research_dir / "synthesis.md", synthesis.stdout)

    task.status = "researched"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    task.metadata["research_summary_path"] = "research/synthesis.md"
    save_task(project_root, config, task)
    log("research", "Done → research/synthesis.md")
    return task.task_id

