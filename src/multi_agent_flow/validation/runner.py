from __future__ import annotations

from pathlib import Path
import subprocess
import time

from ..models import ValidationCommandResult, ValidationRunResult


def run_validation(
    project_root: str | Path,
    commands: list[str],
    profile_name: str | None,
) -> ValidationRunResult:
    results: list[ValidationCommandResult] = []
    success = True
    root = Path(project_root).resolve()

    for command in commands:
        started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            shell=True,
            check=False,
        )
        duration = time.monotonic() - started
        item = ValidationCommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_s=duration,
        )
        results.append(item)
        success = success and completed.returncode == 0

    return ValidationRunResult(profile=profile_name, success=success, commands=results)

