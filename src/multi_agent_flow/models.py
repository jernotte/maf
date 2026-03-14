from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TaskRecord:
    task_id: str
    title: str
    project_root: str
    input_value: str
    source_type: str
    validation_profile: str | None
    status: str
    spec_approved: bool
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        return cls(**data)


@dataclass
class AgentExecutionResult:
    agent: str
    command: list[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    instruction_path: str
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationCommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationRunResult:
    profile: str | None
    success: bool
    commands: list[ValidationCommandResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "success": self.success,
            "commands": [item.to_dict() for item in self.commands],
        }

