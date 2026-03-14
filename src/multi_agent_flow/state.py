from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from uuid import uuid4

from .config import AppConfig
from .models import TaskRecord


PHASE_DIRS = ("research", "spec", "build", "review", "finalize", "prompts")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def maf_root(project_root: str | Path, config: AppConfig) -> Path:
    return Path(project_root).resolve() / config.maf_dir


def tasks_root(project_root: str | Path, config: AppConfig) -> Path:
    return maf_root(project_root, config) / "tasks"


def task_dir(project_root: str | Path, config: AppConfig, task_id: str) -> Path:
    return tasks_root(project_root, config) / task_id


def ensure_task_layout(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    for name in PHASE_DIRS:
        (base_dir / name).mkdir(parents=True, exist_ok=True)


def create_task(
    project_root: str | Path,
    config: AppConfig,
    title: str,
    input_value: str,
    source_type: str,
    validation_profile: str | None,
) -> TaskRecord:
    task_id = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    now = utc_now()
    task = TaskRecord(
        task_id=task_id,
        title=title,
        project_root=str(Path(project_root).resolve()),
        input_value=input_value,
        source_type=source_type,
        validation_profile=validation_profile,
        status="created",
        spec_approved=False,
        created_at=now,
        updated_at=now,
    )
    base_dir = task_dir(project_root, config, task_id)
    ensure_task_layout(base_dir)
    save_task(project_root, config, task)
    return task


def task_file(project_root: str | Path, config: AppConfig, task_id: str) -> Path:
    return task_dir(project_root, config, task_id) / "task.json"


def save_task(project_root: str | Path, config: AppConfig, task: TaskRecord) -> None:
    base_dir = task_dir(project_root, config, task.task_id)
    ensure_task_layout(base_dir)
    task.updated_at = utc_now()
    task_file(project_root, config, task.task_id).write_text(
        json.dumps(task.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def load_task(project_root: str | Path, config: AppConfig, task_id: str) -> TaskRecord:
    path = task_file(project_root, config, task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task not found: {task_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return TaskRecord.from_dict(data)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict | list) -> None:
    write_text(path, json.dumps(payload, indent=2) + "\n")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def approved_spec_path(project_root: str | Path, config: AppConfig, task_id: str) -> Path:
    return task_dir(project_root, config, task_id) / "spec" / "spec-approved.md"


def draft_spec_path(project_root: str | Path, config: AppConfig, task_id: str) -> Path:
    return task_dir(project_root, config, task_id) / "spec" / "spec-draft.md"


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)

