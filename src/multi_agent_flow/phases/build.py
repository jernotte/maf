from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..agents import ClaudeAdapter
from ..config import AppConfig
from ..git import diff_changed_files, snapshot_changed_files
from ..progress import agent_done, agent_start, log
from ..prompts import render_prompt
from ..state import approved_spec_path, load_task, read_text, save_task, task_dir, write_json, write_text
from ..validation import run_validation
from .common import persist_agent_result, require_file, sanitize_agent_output


# ---------------------------------------------------------------------------
# Phase JSON parsing / validation
# ---------------------------------------------------------------------------

def _parse_phases_json(raw_text: str) -> list[dict[str, Any]]:
    """Extract a JSON array from agent output, handling code fences."""
    # Try raw parse first
    text = raw_text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Try finding the outermost array brackets
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse phases JSON from agent output. Raw output:\n{text[:500]}")


_REQUIRED_PHASE_KEYS = {"id", "title", "spec_slice", "files_expected", "depends_on"}


def _validate_phases(phases: list[dict[str, Any]]) -> None:
    """Check required keys, duplicate IDs, and forward-reference deps."""
    seen_ids: set[str] = set()
    for i, phase in enumerate(phases):
        missing = _REQUIRED_PHASE_KEYS - set(phase.keys())
        if missing:
            raise ValueError(f"Phase {i} missing keys: {missing}")
        pid = phase["id"]
        if pid in seen_ids:
            raise ValueError(f"Duplicate phase id: {pid}")
        seen_ids.add(pid)
        for dep in phase.get("depends_on", []):
            if dep not in seen_ids:
                raise ValueError(f"Phase {pid} has forward-reference dependency: {dep}")


# ---------------------------------------------------------------------------
# Decomposition
# ---------------------------------------------------------------------------

def _decompose_spec(
    adapter: ClaudeAdapter,
    config: AppConfig,
    task_id: str,
    project_root: str,
    base_dir: Path,
    approved_spec: str,
    source_brief: str,
) -> list[dict[str, Any]]:
    """Run the decomposition agent and return validated phases."""
    log("build", "Decomposing spec into phases...")
    prompt = render_prompt(
        "build-decompose.md",
        title=load_task(project_root, config, task_id).title,
        approved_spec=approved_spec,
        source_brief=source_brief,
    )

    agent_start("build", "claude-build", label="decompose")
    result = adapter.run(prompt, project_root, base_dir, "build", "decompose")
    agent_done("build", "claude-build", result.duration_s, label="decompose")
    persist_agent_result(base_dir / "build", "decompose", result)

    if result.exit_code != 0 and not result.stdout.strip():
        raise RuntimeError(
            f"Decomposition agent failed (exit {result.exit_code}): {result.stderr[:500]}"
        )

    phases = _parse_phases_json(result.stdout)
    _validate_phases(phases)
    write_json(base_dir / "build" / "phases.json", phases)
    log("build", f"Decomposed into {len(phases)} phases")
    return phases


# ---------------------------------------------------------------------------
# Phase manifest rendering
# ---------------------------------------------------------------------------

def _build_manifest(
    phase: dict[str, Any],
    status: str,
    files_changed: list[str],
    summary: str,
) -> dict[str, Any]:
    return {
        "id": phase["id"],
        "title": phase["title"],
        "status": status,
        "files_changed": files_changed,
        "summary": summary[:2000],
    }


def _render_manifests(manifests: list[dict[str, Any]]) -> str:
    if not manifests:
        return "No prior phases yet."
    lines: list[str] = []
    for m in manifests:
        lines.append(f"### {m['id']}: {m['title']} ({m['status']})")
        lines.append(f"Files changed: {', '.join(m['files_changed']) or 'none'}")
        lines.append(f"Summary: {m['summary']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-phase execution
# ---------------------------------------------------------------------------

def _run_phase(
    adapter: ClaudeAdapter,
    project_root: str,
    base_dir: Path,
    task_title: str,
    phase: dict[str, Any],
    phase_index: int,
    total_phases: int,
    prior_manifests: list[dict[str, Any]],
    source_brief: str,
    validation_commands: list[str],
) -> tuple[dict[str, Any], str]:
    """Run a single build phase. Returns (manifest, clean_log)."""
    pid = phase["id"]
    phase_dir = base_dir / "build" / pid

    val_text = (
        "\n".join(f"- {cmd}" for cmd in validation_commands)
        or "- No validation commands configured."
    )

    prompt = render_prompt(
        "build-phase.md",
        title=task_title,
        phase_id=pid,
        phase_title=phase["title"],
        phase_number=str(phase_index + 1),
        total_phases=str(total_phases),
        spec_slice=phase["spec_slice"],
        prior_manifests=_render_manifests(prior_manifests),
        source_brief=source_brief,
        validation_commands=val_text,
    )

    before = snapshot_changed_files(project_root)
    agent_start("build", "claude-build", label=pid)
    result = adapter.run(prompt, project_root, base_dir, "build", pid)
    agent_done("build", "claude-build", result.duration_s, label=pid)
    persist_agent_result(phase_dir, "implementation", result)
    after = snapshot_changed_files(project_root)
    files_changed = diff_changed_files(before, after)

    clean_output = sanitize_agent_output(result.stdout)
    write_text(phase_dir / "implementation-log.md", clean_output)

    # Validation gate
    if validation_commands:
        log("build", f"Validating {pid}...")
        validation = run_validation(project_root, validation_commands, None)
        write_json(phase_dir / "validation.json", validation.to_dict())

        if not validation.success:
            log("build", f"Validation failed for {pid}, retrying...")
            retry_result, retry_files = _retry_phase(
                adapter, project_root, base_dir, task_title, phase,
                phase_index, total_phases, prior_manifests, source_brief,
                validation_commands, validation, prompt,
            )
            if retry_result is not None:
                clean_output = sanitize_agent_output(retry_result.stdout)
                write_text(phase_dir / "implementation-log.md", clean_output)
                files_changed = sorted(set(files_changed) | set(retry_files))

                retry_validation = run_validation(project_root, validation_commands, None)
                write_json(phase_dir / "validation.json", retry_validation.to_dict())

                if not retry_validation.success:
                    manifest = _build_manifest(phase, "failed", files_changed, clean_output)
                    write_json(phase_dir / "manifest.json", manifest)
                    return manifest, clean_output
            else:
                manifest = _build_manifest(phase, "failed", files_changed, clean_output)
                write_json(phase_dir / "manifest.json", manifest)
                return manifest, clean_output

    manifest = _build_manifest(phase, "completed", files_changed, clean_output)
    write_json(phase_dir / "manifest.json", manifest)
    return manifest, clean_output


def _retry_phase(
    adapter: ClaudeAdapter,
    project_root: str,
    base_dir: Path,
    task_title: str,
    phase: dict[str, Any],
    phase_index: int,
    total_phases: int,
    prior_manifests: list[dict[str, Any]],
    source_brief: str,
    validation_commands: list[str],
    failed_validation,
    original_prompt: str,
) -> tuple[Any, list[str]]:
    """Retry a phase once with validation errors appended."""
    pid = phase["id"]
    phase_dir = base_dir / "build" / pid

    # Build error context from failed validation commands
    error_parts: list[str] = []
    for cmd_result in failed_validation.commands:
        if cmd_result.exit_code != 0:
            stdout_cap = cmd_result.stdout[:3000] if cmd_result.stdout else "(empty)"
            stderr_cap = cmd_result.stderr[:3000] if cmd_result.stderr else "(empty)"
            error_parts.append(
                f"Command: {cmd_result.command}\n"
                f"Exit code: {cmd_result.exit_code}\n"
                f"stdout:\n{stdout_cap}\n"
                f"stderr:\n{stderr_cap}"
            )

    retry_prompt = (
        original_prompt
        + "\n\n## RETRY CONTEXT\n\n"
        "The previous build attempt for this phase failed validation. "
        "Read the current file state on disk and fix the issues.\n\n"
        "Validation errors:\n\n"
        + "\n---\n".join(error_parts)
    )

    before = snapshot_changed_files(project_root)
    agent_start("build", "claude-build", label=f"{pid}-retry")
    result = adapter.run(retry_prompt, project_root, base_dir, "build", f"{pid}-retry")
    agent_done("build", "claude-build", result.duration_s, label=f"{pid}-retry")
    persist_agent_result(phase_dir, "retry", result)
    after = snapshot_changed_files(project_root)
    retry_files = diff_changed_files(before, after)

    if result.exit_code != 0 and not result.stdout.strip():
        log("build", f"Retry agent failed for {pid} (exit {result.exit_code})")
        return None, []

    return result, retry_files


# ---------------------------------------------------------------------------
# Output assembly
# ---------------------------------------------------------------------------

def _assemble_output(
    base_dir: Path,
    phases: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    task_title: str,
) -> str:
    """Merge all phase logs into a single implementation-log.md."""
    sections: list[str] = []
    sections.append(f"# Build: {task_title}\n")
    sections.append(f"Phases: {len(phases)}\n")

    for i, (phase, manifest) in enumerate(zip(phases, manifests)):
        pid = phase["id"]
        phase_dir = base_dir / "build" / pid
        log_path = phase_dir / "implementation-log.md"
        phase_log = log_path.read_text(encoding="utf-8") if log_path.exists() else "(no output)"

        sections.append(f"## Phase {i + 1}/{len(phases)}: {phase['title']} ({manifest['status']})")
        sections.append(f"ID: {pid}")
        if manifest["files_changed"]:
            sections.append(f"Files changed: {', '.join(manifest['files_changed'])}")
        sections.append("")
        sections.append(phase_log)
        sections.append("")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_build(project_root: str, config: AppConfig, task_id: str) -> Path:
    task = load_task(project_root, config, task_id)
    if not task.spec_approved:
        raise RuntimeError("Spec is not approved. Run `maf approve-spec --task <task-id>` first.")

    base_dir = task_dir(project_root, config, task_id)
    spec_path = approved_spec_path(project_root, config, task_id)
    require_file(spec_path, "Approved spec is missing.")
    approved_spec = read_text(spec_path)
    validation_commands = config.resolve_validation_commands(task.validation_profile)

    brief_path = base_dir / "normalized-brief.md"
    source_brief = read_text(brief_path) if brief_path.exists() else ""

    adapter = ClaudeAdapter(config.agents["claude-build"])

    # Stage 1: Decompose
    phases = _decompose_spec(
        adapter, config, task_id, project_root, base_dir,
        approved_spec, source_brief,
    )
    task.metadata["phases_total"] = len(phases)
    task.metadata["phases_completed"] = 0
    save_task(project_root, config, task)

    # Stage 2: Execute phases sequentially
    before_all = snapshot_changed_files(project_root)
    manifests: list[dict[str, Any]] = []
    failed_phase: str | None = None

    for i, phase in enumerate(phases):
        pid = phase["id"]
        log("build", f"Phase {i + 1}/{len(phases)}: {phase['title']}")

        is_last = i == len(phases) - 1
        manifest, _ = _run_phase(
            adapter, project_root, base_dir, task.title,
            phase, i, len(phases), manifests, source_brief,
            validation_commands,
        )
        manifests.append(manifest)

        if manifest["status"] == "failed":
            failed_phase = pid
            log("build", f"Phase {pid} failed — stopping build.")
            break

        task.metadata["phases_completed"] = i + 1
        save_task(project_root, config, task)
        if is_last:
            agent_done("build", "claude-build", 0, label="all-phases", last=True)

    # Stage 3: Assemble output
    log("build", "Assembling build output...")
    assembled_log = _assemble_output(base_dir, phases, manifests, task.title)
    write_text(base_dir / "build" / "implementation-log.md", assembled_log)

    after_all = snapshot_changed_files(project_root)
    all_changed = diff_changed_files(before_all, after_all)
    write_json(base_dir / "build" / "changed-files.json", {"changed_files": all_changed})

    log("build", "Running final validation...")
    final_validation = run_validation(project_root, validation_commands, task.validation_profile)
    write_json(base_dir / "build" / "validation.json", final_validation.to_dict())
    log("build", f"Final validation {'passed' if final_validation.success else 'failed'}")

    if failed_phase:
        task.status = "built"
        task.metadata["failed_phase"] = failed_phase
    else:
        task.status = "built"

    task.metadata["build_log_path"] = "build/implementation-log.md"
    task.metadata["changed_files_path"] = "build/changed-files.json"
    task.metadata["validation_path"] = "build/validation.json"
    save_task(project_root, config, task)
    log("build", f"Done → build/implementation-log.md ({len(phases)} phases, {len(all_changed)} files changed)")
    return base_dir / "build" / "implementation-log.md"
