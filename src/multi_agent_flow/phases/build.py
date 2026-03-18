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
    text = raw_text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

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
# Validation baseline
# ---------------------------------------------------------------------------

def _extract_failed_tests(stdout: str) -> set[str]:
    """Extract FAILED test node IDs from pytest output."""
    failed: set[str] = set()
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            # "FAILED tests/unit/test_foo.py::test_bar - reason..."
            node = line[7:].split(" - ", 1)[0].strip()
            if node:
                failed.add(node)
    return failed


def _capture_baseline(project_root: str, commands: list[str], profile: str | None) -> dict[str, Any]:
    """Run validation before the build and record baseline failures."""
    log("build", "Capturing validation baseline...")
    result = run_validation(project_root, commands, profile)
    baseline_failures: set[str] = set()
    for cmd_result in result.commands:
        baseline_failures |= _extract_failed_tests(cmd_result.stdout)
    log("build", f"Baseline: {len(baseline_failures)} pre-existing test failures")
    return {
        "success": result.success,
        "failed_tests": sorted(baseline_failures),
        "result": result,
    }


def _compare_validation(
    final_result,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Compare final validation against baseline. Return regression info."""
    baseline_failures = set(baseline["failed_tests"])
    final_failures: set[str] = set()
    for cmd_result in final_result.commands:
        final_failures |= _extract_failed_tests(cmd_result.stdout)

    new_failures = sorted(final_failures - baseline_failures)
    fixed = sorted(baseline_failures - final_failures)

    return {
        "baseline_failure_count": len(baseline_failures),
        "final_failure_count": len(final_failures),
        "new_failures": new_failures,
        "fixed": fixed,
        "regressed": len(new_failures) > 0,
    }


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

    manifest = _build_manifest(phase, "completed", files_changed, clean_output)
    write_json(phase_dir / "manifest.json", manifest)
    return manifest, clean_output


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

    # Capture validation baseline before any changes
    baseline = _capture_baseline(project_root, validation_commands, task.validation_profile) if validation_commands else None
    if baseline:
        write_json(base_dir / "build" / "baseline-validation.json", {
            "success": baseline["success"],
            "failed_tests": baseline["failed_tests"],
        })

    # Stage 1: Decompose
    phases = _decompose_spec(
        adapter, config, task_id, project_root, base_dir,
        approved_spec, source_brief,
    )
    task.metadata["phases_total"] = len(phases)
    task.metadata["phases_completed"] = 0
    save_task(project_root, config, task)

    # Stage 2: Execute all phases sequentially (agents self-validate inline)
    before_all = snapshot_changed_files(project_root)
    manifests: list[dict[str, Any]] = []

    for i, phase in enumerate(phases):
        log("build", f"Phase {i + 1}/{len(phases)}: {phase['title']}")

        manifest, _ = _run_phase(
            adapter, project_root, base_dir, task.title,
            phase, i, len(phases), manifests, source_brief,
            validation_commands,
        )
        manifests.append(manifest)

        task.metadata["phases_completed"] = i + 1
        save_task(project_root, config, task)

    agent_done("build", "claude-build", 0, label="all-phases", last=True)

    # Stage 3: Assemble output
    log("build", "Assembling build output...")
    assembled_log = _assemble_output(base_dir, phases, manifests, task.title)
    write_text(base_dir / "build" / "implementation-log.md", assembled_log)

    after_all = snapshot_changed_files(project_root)
    all_changed = diff_changed_files(before_all, after_all)
    write_json(base_dir / "build" / "changed-files.json", {"changed_files": all_changed})

    # Final validation with baseline comparison
    log("build", "Running final validation...")
    final_validation = run_validation(project_root, validation_commands, task.validation_profile)
    write_json(base_dir / "build" / "validation.json", final_validation.to_dict())

    if baseline:
        comparison = _compare_validation(final_validation, baseline)
        write_json(base_dir / "build" / "validation-comparison.json", comparison)
        if comparison["regressed"]:
            log("build", f"REGRESSION: {len(comparison['new_failures'])} new test failures introduced")
            for t in comparison["new_failures"][:20]:
                log("build", f"  NEW FAIL: {t}")
            task.metadata["new_test_failures"] = comparison["new_failures"]
        else:
            log("build", f"No regressions ({comparison['final_failure_count']} failures, all pre-existing)")
        if comparison["fixed"]:
            log("build", f"Bonus: {len(comparison['fixed'])} previously failing tests now pass")
    else:
        log("build", f"Final validation {'passed' if final_validation.success else 'failed'}")

    task.status = "built"
    task.metadata["build_log_path"] = "build/implementation-log.md"
    task.metadata["changed_files_path"] = "build/changed-files.json"
    task.metadata["validation_path"] = "build/validation.json"
    save_task(project_root, config, task)
    log("build", f"Done → build/implementation-log.md ({len(phases)} phases, {len(all_changed)} files changed)")
    return base_dir / "build" / "implementation-log.md"
