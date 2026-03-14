from __future__ import annotations

from pathlib import Path
import subprocess


def _run_git_status(project_root: str | Path) -> set[str]:
    root = Path(project_root).resolve()
    if not (root / ".git").exists():
        return set()
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path)
    return paths


def snapshot_changed_files(project_root: str | Path) -> set[str]:
    return _run_git_status(project_root)


def diff_changed_files(before: set[str], after: set[str]) -> list[str]:
    return sorted(after - before)

