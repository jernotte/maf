from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..agents import ClaudeAdapter, CodexAdapter, GeminiAdapter
from ..config import AppConfig
from ..inputs import normalize_input
from ..progress import agent_done, agent_start, log
from ..prompts import render_prompt
from ..state import create_task, load_task, read_text, save_task, task_dir, write_text
from .common import (
    build_syntheses_manifest,
    build_worker_manifest,
    persist_agent_result,
    persist_worker_findings,
    sanitize_agent_output,
)

# ── Prompt set registry ──────────────────────────────────────────────

PROMPT_SETS: dict[str, tuple[str, str, str]] = {
    "critique": ("critique_worker.md", "critique_synthesis.md", "critique_final.md"),
    "deep-research": ("deep_research_worker.md", "deep_research_synthesis.md", "deep_research_final.md"),
}


# ── Adapter builders ─────────────────────────────────────────────────

def _build_adapters(config: AppConfig) -> dict[str, object]:
    return {
        "claude": ClaudeAdapter(config.agents["claude"]),
        "claude-research": ClaudeAdapter(config.agents["claude-research"]),
        "codex": CodexAdapter(config.agents["codex"]),
        "gemini": GeminiAdapter(config.agents["gemini"]),
    }


def _build_deep_research_adapters(config: AppConfig) -> dict[str, object]:
    return {
        "claude": ClaudeAdapter(config.agents["claude"]),
        "claude-research": ClaudeAdapter(config.agents["claude-research"]),
        "codex": CodexAdapter(config.agents["codex-research"]),
        "gemini": GeminiAdapter(config.agents["gemini-research"]),
    }


# ── Core iteration + consolidation ───────────────────────────────────

def _run_iteration(
    iteration: int,
    total_iterations: int,
    title: str,
    normalized_brief: str,
    previous_synthesis_path: Path | None,
    worker_focuses: list[str],
    concurrency: int,
    adapters: dict[str, object],
    project_root: str,
    base_dir: Path,
    prompt_set: str = "critique",
    prefetch_context: str = "",
) -> Path:
    """Run one research-critique iteration. Returns the path to synthesis.md."""
    worker_tpl, synthesis_tpl, _final_tpl = PROMPT_SETS[prompt_set]

    iter_dir = base_dir / "research" / f"iteration-{iteration:03d}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    sources_dir = str(iter_dir / "sources")
    Path(sources_dir).mkdir(parents=True, exist_ok=True)

    if previous_synthesis_path:
        previous_context = (
            f"Previous iteration synthesis is at: {previous_synthesis_path}\n"
            f"Read it with the Read tool to see what prior iterations found."
        )
    else:
        previous_context = "This is the first iteration. There is no prior research to build on."

    jobs: list[tuple[str, str, object, str]] = []
    for index, focus in enumerate(worker_focuses, start=1):
        output_path = str(iter_dir / f"claude-worker-{index}.findings.md")
        jobs.append((
            f"claude-worker-{index}",
            focus,
            adapters["claude-research"],
            render_prompt(
                worker_tpl,
                title=title,
                normalized_brief=normalized_brief,
                focus=focus,
                iteration=str(iteration),
                total_iterations=str(total_iterations),
                previous_context=previous_context,
                output_path=output_path,
                sources_dir=sources_dir,
                prefetch_context=prefetch_context,
            ),
        ))
    jobs.append((
        "gemini",
        "broad-critique",
        adapters["gemini"],
        render_prompt(
            worker_tpl,
            title=title,
            normalized_brief=normalized_brief,
            focus="broad-critique",
            iteration=str(iteration),
            total_iterations=str(total_iterations),
            previous_context=previous_context,
            output_path=str(iter_dir / "gemini.findings.md"),
            sources_dir=sources_dir,
            prefetch_context=prefetch_context,
        ),
    ))
    jobs.append((
        "codex",
        "broad-critique",
        adapters["codex"],
        render_prompt(
            worker_tpl,
            title=title,
            normalized_brief=normalized_brief,
            focus="broad-critique",
            iteration=str(iteration),
            total_iterations=str(total_iterations),
            previous_context=previous_context,
            output_path=str(iter_dir / "codex.findings.md"),
            sources_dir=sources_dir,
            prefetch_context=prefetch_context,
        ),
    ))

    phase = f"research:{iteration}/{total_iterations}"
    for stem, focus, _adapter, _prompt in jobs:
        agent_start(phase, stem, label=focus)

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
            persist_agent_result(iter_dir, stem, result)  # raw audit trail
            persist_worker_findings(iter_dir, stem, focus, result)  # canonical findings + meta

    if previous_synthesis_path:
        previous_synthesis_context = (
            f"Previous iteration synthesis is at: {previous_synthesis_path}\n"
            f"Read it with the Read tool to understand what prior iterations found."
        )
    else:
        previous_synthesis_context = "This is the first iteration."

    synthesis_prompt = render_prompt(
        synthesis_tpl,
        title=title,
        normalized_brief=normalized_brief,
        worker_manifest=build_worker_manifest(iter_dir),
        iteration=str(iteration),
        total_iterations=str(total_iterations),
        previous_synthesis_context=previous_synthesis_context,
        sources_dir=sources_dir,
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
    synthesis_path = iter_dir / "synthesis.md"
    write_text(synthesis_path, clean_synthesis)
    return synthesis_path


def _run_final_consolidation(
    title: str,
    normalized_brief: str,
    total_iterations: int,
    adapters: dict[str, object],
    project_root: str,
    base_dir: Path,
    prompt_set: str = "critique",
) -> str:
    """Run a final pass that consolidates all iteration syntheses into one document."""
    _worker_tpl, _synthesis_tpl, final_tpl = PROMPT_SETS[prompt_set]

    prompt = render_prompt(
        final_tpl,
        title=title,
        normalized_brief=normalized_brief,
        syntheses_manifest=build_syntheses_manifest(
            base_dir / "research", total_iterations
        ),
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


# ── Source gap report (deep research) ────────────────────────────────

def _generate_source_gap_report(base_dir: Path, task_id: str) -> str | None:
    """Scan source meta files for failed/snippet fetches and write a gap report."""
    research_dir = base_dir / "research"
    gaps: list[dict[str, str]] = []

    for meta_path in sorted(research_dir.rglob("sources/*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("fetch_tier") in ("failed", "snippet"):
            # Determine iteration from path
            iteration = "unknown"
            for part in meta_path.parts:
                if part.startswith("iteration-"):
                    iteration = part
                    break

            # Find which workers cited this URL by scanning findings files
            url = meta.get("url", "unknown")
            cited_by: list[str] = []
            iter_dir = meta_path.parent.parent  # sources/ -> iteration-NNN/
            for findings_file in iter_dir.glob("*.findings.md"):
                try:
                    content = findings_file.read_text(encoding="utf-8")
                    if url in content:
                        cited_by.append(findings_file.stem.replace(".findings", ""))
                except OSError:
                    continue

            save_path = str(meta_path).replace(".meta.json", ".md")
            gaps.append({
                "url": url,
                "cited_by": ", ".join(cited_by) if cited_by else "unknown",
                "iteration": iteration,
                "tier": meta.get("fetch_tier", "unknown"),
                "save_to": save_path,
            })

    if not gaps:
        return None

    lines = [
        "# Source Gaps — Manual Retrieval Needed",
        "",
        "These sources were cited in research but could not be fully fetched.",
        "Download them manually and save to the listed paths, then re-run final consolidation.",
        "",
        "| URL | Cited By | Iteration | Current Tier | Save To |",
        "|-----|----------|-----------|--------------|---------|",
    ]
    for gap in gaps:
        lines.append(f"| {gap['url']} | {gap['cited_by']} | {gap['iteration']} | {gap['tier']} | {gap['save_to']} |")

    lines.extend([
        "",
        "To re-run consolidation with new sources:",
        f"  maf deep-research --resume-task {task_id} --consolidate-only",
    ])

    report = "\n".join(lines)
    report_path = research_dir / "source-gaps.md"
    write_text(report_path, report)
    return report


# ── Site pre-fetch helper ────────────────────────────────────────────

def _prefetch_site(url: str, base_dir: Path) -> str:
    """Download an entire site for local access. Returns context string for prompts."""
    from ..fetch_source import prefetch_site

    dest_dir = str(base_dir / "research" / "prefetched-sites")
    site_path = prefetch_site(url, dest_dir)
    return (
        f"A local mirror of {url} has been downloaded to: {site_path}\n"
        f"You can Read and Grep files in this directory instead of fetching individual pages."
    )


# ── Critique mode (existing) ────────────────────────────────────────

def run_research_loop(
    project_root: str,
    config: AppConfig,
    title: str,
    input_value: str,
    validation_profile: str | None,
    max_research_workers: int | None,
    iterations: int,
    prompt_set: str = "critique",
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

    previous_synthesis_path: Path | None = None
    for iteration in range(1, iterations + 1):
        log("research-loop", f"Iteration {iteration}/{iterations}")
        previous_synthesis_path = _run_iteration(
            iteration=iteration,
            total_iterations=iterations,
            title=task.title,
            normalized_brief=normalized.normalized_brief,
            previous_synthesis_path=previous_synthesis_path,
            worker_focuses=worker_focuses,
            concurrency=concurrency,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
            prompt_set=prompt_set,
        )

    # Final consolidation pass
    log("research-loop", "Final consolidation...")
    final_output = _run_final_consolidation(
        title=task.title,
        normalized_brief=normalized.normalized_brief,
        total_iterations=iterations,
        adapters=adapters,
        project_root=project_root,
        base_dir=base_dir,
        prompt_set=prompt_set,
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
    prompt_set: str = "critique",
) -> str:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task_id)
    normalized_brief = read_text(base_dir / "normalized-brief.md")

    worker_focuses = config.research.worker_focuses[:]
    concurrency = max_research_workers or config.research.max_workers

    adapters = _build_adapters(config)

    # Load synthesis path from the last completed iteration
    previous_synthesis_path: Path | None = None
    for i in range(1, start_iteration):
        synth_path = base_dir / "research" / f"iteration-{i:03d}" / "synthesis.md"
        if not synth_path.exists():
            raise FileNotFoundError(
                f"Cannot resume from iteration {start_iteration}: "
                f"iteration {i} synthesis not found at {synth_path}"
            )
        previous_synthesis_path = synth_path
        log("research-loop", f"Loaded iteration {i}/{iterations} from disk")

    # Run remaining iterations
    for iteration in range(start_iteration, iterations + 1):
        log("research-loop", f"Iteration {iteration}/{iterations}")
        previous_synthesis_path = _run_iteration(
            iteration=iteration,
            total_iterations=iterations,
            title=task.title,
            normalized_brief=normalized_brief,
            previous_synthesis_path=previous_synthesis_path,
            worker_focuses=worker_focuses,
            concurrency=concurrency,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
            prompt_set=prompt_set,
        )

    # Final consolidation pass
    log("research-loop", "Final consolidation...")
    final_output = _run_final_consolidation(
        title=task.title,
        normalized_brief=normalized_brief,
        total_iterations=iterations,
        adapters=adapters,
        project_root=project_root,
        base_dir=base_dir,
        prompt_set=prompt_set,
    )

    research_dir = base_dir / "research"
    write_text(research_dir / "synthesis.md", final_output)

    task.status = "research-loop-complete"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    task.metadata["research_summary_path"] = "research/synthesis.md"
    task.metadata["iterations_completed"] = iterations
    save_task(project_root, config, task)
    return task.task_id


# ── Deep research mode ───────────────────────────────────────────────

def run_deep_research(
    project_root: str,
    config: AppConfig,
    title: str,
    input_value: str,
    iterations: int | None,
    max_research_workers: int | None,
    prefetch_site_url: str | None,
) -> str:
    normalized = normalize_input(title=title, input_value=input_value)
    task = create_task(
        project_root=project_root,
        config=config,
        title=title,
        input_value=input_value,
        source_type=normalized.source_type,
        validation_profile=None,
    )
    base_dir = task_dir(project_root, config, task.task_id)
    write_text(base_dir / "normalized-brief.md", normalized.normalized_brief)

    dr = config.deep_research
    worker_focuses = dr.worker_focuses[:]
    concurrency = max_research_workers or dr.max_workers
    total_iterations = iterations or dr.iterations

    adapters = _build_deep_research_adapters(config)

    # Optional site pre-fetch
    prefetch_context = ""
    if prefetch_site_url:
        log("deep-research", f"Pre-fetching site: {prefetch_site_url}")
        prefetch_context = _prefetch_site(prefetch_site_url, base_dir)

    previous_synthesis_path: Path | None = None
    for iteration in range(1, total_iterations + 1):
        log("deep-research", f"Iteration {iteration}/{total_iterations}")
        previous_synthesis_path = _run_iteration(
            iteration=iteration,
            total_iterations=total_iterations,
            title=task.title,
            normalized_brief=normalized.normalized_brief,
            previous_synthesis_path=previous_synthesis_path,
            worker_focuses=worker_focuses,
            concurrency=concurrency,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
            prompt_set="deep-research",
            prefetch_context=prefetch_context,
        )

    # Final consolidation pass
    log("deep-research", "Final consolidation...")
    final_output = _run_final_consolidation(
        title=task.title,
        normalized_brief=normalized.normalized_brief,
        total_iterations=total_iterations,
        adapters=adapters,
        project_root=project_root,
        base_dir=base_dir,
        prompt_set="deep-research",
    )

    research_dir = base_dir / "research"
    write_text(research_dir / "synthesis.md", final_output)

    # Generate source gap report
    gap_report = _generate_source_gap_report(base_dir, task.task_id)
    if gap_report:
        log("deep-research", "Source gaps found — see research/source-gaps.md")
        print(gap_report)

    task.status = "deep-research-complete"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    task.metadata["research_summary_path"] = "research/synthesis.md"
    task.metadata["iterations_completed"] = total_iterations
    task.metadata["mode"] = "deep-research"
    save_task(project_root, config, task)
    return task.task_id


def resume_deep_research(
    project_root: str,
    config: AppConfig,
    task_id: str,
    start_iteration: int | None,
    iterations: int | None,
    max_research_workers: int | None,
    consolidate_only: bool = False,
) -> str:
    task = load_task(project_root, config, task_id)
    base_dir = task_dir(project_root, config, task_id)
    normalized_brief = read_text(base_dir / "normalized-brief.md")

    dr = config.deep_research
    total_iterations = iterations or task.metadata.get("iterations_completed", dr.iterations)

    adapters = _build_deep_research_adapters(config)

    if consolidate_only:
        log("deep-research", "Re-running final consolidation only...")
        final_output = _run_final_consolidation(
            title=task.title,
            normalized_brief=normalized_brief,
            total_iterations=total_iterations,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
            prompt_set="deep-research",
        )

        research_dir = base_dir / "research"
        write_text(research_dir / "synthesis.md", final_output)

        gap_report = _generate_source_gap_report(base_dir, task.task_id)
        if gap_report:
            log("deep-research", "Source gaps remain — see research/source-gaps.md")
            print(gap_report)

        task.status = "deep-research-complete"
        task.metadata["research_summary_path"] = "research/synthesis.md"
        save_task(project_root, config, task)
        return task.task_id

    # Resume iterations
    worker_focuses = dr.worker_focuses[:]
    concurrency = max_research_workers or dr.max_workers
    start = start_iteration or 1

    # Load synthesis path from the last completed iteration
    previous_synthesis_path: Path | None = None
    for i in range(1, start):
        synth_path = base_dir / "research" / f"iteration-{i:03d}" / "synthesis.md"
        if not synth_path.exists():
            raise FileNotFoundError(
                f"Cannot resume from iteration {start}: "
                f"iteration {i} synthesis not found at {synth_path}"
            )
        previous_synthesis_path = synth_path
        log("deep-research", f"Loaded iteration {i}/{total_iterations} from disk")

    for iteration in range(start, total_iterations + 1):
        log("deep-research", f"Iteration {iteration}/{total_iterations}")
        previous_synthesis_path = _run_iteration(
            iteration=iteration,
            total_iterations=total_iterations,
            title=task.title,
            normalized_brief=normalized_brief,
            previous_synthesis_path=previous_synthesis_path,
            worker_focuses=worker_focuses,
            concurrency=concurrency,
            adapters=adapters,
            project_root=project_root,
            base_dir=base_dir,
            prompt_set="deep-research",
        )

    log("deep-research", "Final consolidation...")
    final_output = _run_final_consolidation(
        title=task.title,
        normalized_brief=normalized_brief,
        total_iterations=total_iterations,
        adapters=adapters,
        project_root=project_root,
        base_dir=base_dir,
        prompt_set="deep-research",
    )

    research_dir = base_dir / "research"
    write_text(research_dir / "synthesis.md", final_output)

    gap_report = _generate_source_gap_report(base_dir, task.task_id)
    if gap_report:
        log("deep-research", "Source gaps found — see research/source-gaps.md")
        print(gap_report)

    task.status = "deep-research-complete"
    task.metadata["normalized_brief_path"] = "normalized-brief.md"
    task.metadata["research_summary_path"] = "research/synthesis.md"
    task.metadata["iterations_completed"] = total_iterations
    task.metadata["mode"] = "deep-research"
    save_task(project_root, config, task)
    return task.task_id
