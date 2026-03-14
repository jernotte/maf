from __future__ import annotations

from pathlib import Path
import subprocess
import time

from ..config import AgentConfig
from ..models import AgentExecutionResult


class ShellAgentAdapter:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name

    def run(
        self,
        instruction: str,
        cwd: str | Path,
        task_dir: str | Path,
        phase: str,
        stem: str,
    ) -> AgentExecutionResult:
        working_dir = Path(cwd).resolve()
        task_path = Path(task_dir).resolve()
        instruction_path = task_path / "prompts" / f"{phase}-{stem}-{self.name}.md"
        instruction_path.parent.mkdir(parents=True, exist_ok=True)
        instruction_path.write_text(instruction, encoding="utf-8")

        replacements = {
            "{instruction}": instruction,
            "{instruction_file}": str(instruction_path),
            "{project_root}": str(working_dir),
            "{task_dir}": str(task_path),
            "{phase}": phase,
            "{agent}": self.name,
        }
        command = []
        for part in self.config.command:
            resolved = part
            for placeholder, value in replacements.items():
                resolved = resolved.replace(placeholder, value)
            command.append(resolved)

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=working_dir,
                input=instruction,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_s,
                check=False,
            )
            duration = time.monotonic() - started
            return AgentExecutionResult(
                agent=self.name,
                command=command,
                cwd=str(working_dir),
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_s=duration,
                instruction_path=str(instruction_path),
                timed_out=False,
            )
        except FileNotFoundError as exc:
            duration = time.monotonic() - started
            return AgentExecutionResult(
                agent=self.name,
                command=command,
                cwd=str(working_dir),
                exit_code=127,
                stdout="",
                stderr=str(exc),
                duration_s=duration,
                instruction_path=str(instruction_path),
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            return AgentExecutionResult(
                agent=self.name,
                command=command,
                cwd=str(working_dir),
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_s=duration,
                instruction_path=str(instruction_path),
                timed_out=True,
            )
