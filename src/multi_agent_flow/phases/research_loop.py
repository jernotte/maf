from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..agents import ClaudeAdapter, CodexAdapter, GeminiAdapter
from ..config import AppConfig
from ..inputs import normalize_input
from ..progress import agent_done, agent_start, log
from ..prompts import render_prompt
from ..state import create_task, load_task, read_text, save_task, task_dir, write_text
from .common import persist_agent_result, sanitize_agent_output


def _build_adapters(config: AppConfig) -> dict[str, object]:
    return {
        "claude": ClaudeAdapter(config.agents["claude"]),
        "codex": CodexAdapter(config.agents["codex"]),
        "gemini": GeminiAdapter(config.agents["gemini"]),
    }


def _run_iteration(
    iteration: int,
    total_iterations: int,
    title: str,
    normalized_brief: str,
    previous_synthesis: str,
    worker_focuses: list[str],
    concurrency: int,
    adapters: dict[str, object],
    project_root: str,
    base_dir: Path,
) -> str:
    """Run one research-critique iteration. Returns the synthesis text."""
    iter_dir = base_dir / "research" / f"iteration-{iteration:03d}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    if previous_synthesis:
        previous_context = (
            f"Previous iteration synthesis (iteration {iteration - 1}):\n\n"
            f"{previous_synthesis}"
        )
    else:
        previous_context = "This is the first iteration. There is no prior research to build on."

    jobs: list[tuple[str, str, object, str]] = []
    for index, focus in enumerate(worker_focuses, start=1):
        jobs.append((
            f"claude-worker-{index}",
            focus,
            adapters["claude"],
            render_prompt(
                "critique_worker.md",
                title=title,
                normalized_brief=normalized_brief,
                focus=focus,
                iteration=str(iteration),
                total_iterations=str(total_iterations),
                previous_context=previous_context,
            ),
        ))
    jobs.append((
        "gemini",
        "broad-critique",
        adapters["gemini"],
        render_prompt(
            "critique_worker.md",
            title=title,
            normalized_brief=normalized_brief,
            focus="broad-critique",
            iteration=str(iteration),
            total_iterations=str(total_iterations),
            previous_context=previous_context,
        ),
    ))
    jobs.append((
        "codex",
        "broad-critique",
        adapters["codex"],
        render_prompt(
            "critique_worker.md",
            title=title,
            normalized_brief=normalized_brief,
            focus="broad-critique",
            iteration=str(iteration),
            total_iterations=str(total_iterations),
            previous_context=previous_context,
        ),
    ))

    phase = f"research:{iteration}/{total_iterations}"
    for stem, focus, _adapter, _prompt in jobs:
        agent_start(phase, stem, label=focus)

    summaries: list[str] = []
    completed_count = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {
            executor.submit(
                adapter.run,
                prompt,
                project_root,
                base_dir,
                f"research-loop-{iteration:03d}",
                stem,
            ): (stem, focus)
            for stem, focus, adapter, prompt in jobs
        }
        for future in as_completed(future_map):
            stem, focus = future_map[future]
            result = future.result()
            completed_count += 1
            agent_done(phase, stem, result.duration_s, label=focus, last=completed_count == len(jobs))
            persist_agent_result(iter_dir, stem, result)
            clean_output = sanitize_agent_output(result.stdout)
            summaries.append(
                f"## {stem}\n"
                f"- focus: {focus}\n"
                f"- exit_code: {result.exit_code}\n"
                f"- timed_out: {result.timed_out}\n\n"
                f"{clean_output}\n"
            )

    if previous_synthesis:
        previous_synthesis_context = (
            f"Previous iteration synthesis (iteration {iteration - 1}):\n\n"
            f"{previous_synthesis}"
        )
    else:
        previous_synthesis_context = "This is the first iteration."

    synthesis_prompt = render_prompt(
        "critique_synthesis.md",
        title=title,
        normalized_brief=normalized_brief,
        research_outputs="\n\n".join(summaries),
        iteration=str(iteration),
        total_iterations=str(total_iterations),
        previous_synthesis_context=previous_synthesis_context,
    )
    agent_start(phase, "claude", label="synthesis")
    synthesis = adapters["claude"].run(
        synthesis_prompt,
        project_root,
        base_dir,
        f"research-loop-{iteration:03d}",
        "synthesis",
    )
    agent_done(phase, "claude", synthesis.duration_s, label="synthesis", last=True)
    persist_agent_result(iter_dir, "synthesis", synthesis)
    clean_synthesis = sanitize_agent_output(synthesis.stdout)
    write_text(iter_dir / "synthesis.md", clean_synthesis)
    return clean_synthesis


def _run_final_consolidation(
    title: str,
    normalized_brief: str,
    iteration_syntheses: list[str],
    total_iterations: int,
    adapters: dict[str, object],
    project_root: str,
    base_dir: Path,
) -> str:
    """Run a final pass that consolidates all iteration syntheses into one document."""
    all_syntheses_text = ""
    for i, synthesis in enumerate(iteration_syntheses, start=1):
        all_syntheses_text += f"---\n\n# Iteration {i} of {total_iterations}\n\n{synthesis}\n\n"

    prompt = render_prompt(
        "critique_final.md",
        title=title,
        normalized_brief=normalized_brief,
        all_syntheses=all_syntheses_text,
        total_iterations=str(total_iterations),
    )

    final_dir = base_dir / "research" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    result = adapters["claude"].run(
        prompt,
        project_root,
        base_dir,
        "research-loop-final",
        "consolidation",
    )
    persist_agent_result(final_dir, "consolidation", result)
    clean_output = sanitize_agent_output(result.stdout)
    write_text(final_dir / "consolidation.md", clean_output)
    return clean_output


def run_research_loop(
    project_root: str,
    config: AppConfig,
    title: str,
    input_value: str,
    validation_profile: str | None,
    max_research_workers: int | None,
    iterations: int,
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
    concurrency = max_research_workers or config.research.max_workers

    adapters = _build_adapters(config)

    previous_synthesis = ""
    all_syntheses: list[str] = []
    for iteration in range(1, iterations + 1):
        log("research-loop", f"Iteration {iteration}/{iterations}")
        previous_synthesis = _run_iteration(
            iteration=iteration,
            total_iterations=iterations,
            title=task.title,
            normalized_brief=normalized.normalized_brief,
            previous_synthesis=previous_synthesis,
            worker_focuses=worker_focuses,
            concurrency=concurrency,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
        )
        all_syntheses.append(previous_synthesis)

    # Final consolidation pass
    log("research-loop", "Final consolidation...")
    final_output = _run_final_consolidation(
        title=task.title,
        normalized_brief=normalized.normalized_brief,
        iteration_syntheses=all_syntheses,
        total_iterations=iterations,
        adapters=adapters,
        project_root=project_root,
        base_dir=base_dir,
    )

    # Write the final consolidated output to the top-level research dir
    research_dir = base_dir / "research"
    write_text(research_dir / "synthesis.md", final_output)

    task.status = "research-loop-complete"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    task.metadata["research_summary_path"] = "research/synthesis.md"
    task.metadata["iterations_completed"] = iterations
    save_task(project_root, config, task)
    return task.task_id


def resume_research_loop(
    project_root: str,
    config: AppConfig,
    task_id: str,
    start_iteration: int,
    iterations: int,
    max_research_workers: int | None,
) -> str:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task_id)
    normalized_brief = read_text(base_dir / "normalized-brief.md")

    worker_focuses = config.research.worker_focuses[:]
    concurrency = max_research_workers or config.research.max_workers

    adapters = _build_adapters(config)

    # Load syntheses from completed iterations
    all_syntheses: list[str] = []
    previous_synthesis = ""
    for i in range(1, start_iteration):
        synth_path = base_dir / "research" / f"iteration-{i:03d}" / "synthesis.md"
        if not synth_path.exists():
            raise FileNotFoundError(
                f"Cannot resume from iteration {start_iteration}: "
                f"iteration {i} synthesis not found at {synth_path}"
            )
        synthesis_text = read_text(synth_path)
        all_syntheses.append(synthesis_text)
        previous_synthesis = synthesis_text
        log("research-loop", f"Loaded iteration {i}/{iterations} from disk")

    # Run remaining iterations
    for iteration in range(start_iteration, iterations + 1):
        log("research-loop", f"Iteration {iteration}/{iterations}")
        previous_synthesis = _run_iteration(
            iteration=iteration,
            total_iterations=iterations,
            title=task.title,
            normalized_brief=normalized_brief,
            previous_synthesis=previous_synthesis,
            worker_focuses=worker_focuses,
            concurrency=concurrency,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
        )
        all_syntheses.append(previous_synthesis)

    # Final consolidation pass
    log("research-loop", "Final consolidation...")
    final_output = _run_final_consolidation(
        title=task.title,
        normalized_brief=normalized_brief,
        iteration_syntheses=all_syntheses,
        total_iterations=iterations,
        adapters=adapters,
        project_root=project_root,
        base_dir=base_dir,
    )

    research_dir = base_dir / "research"
    write_text(research_dir / "synthesis.md", final_output)

    task.status = "research-loop-complete"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    task.metadata["research_summary_path"] = "research/synthesis.md"
    task.metadata["iterations_completed"] = iterations
    save_task(project_root, config, task)
    return task.task_id
