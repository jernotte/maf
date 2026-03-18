from __future__ import annotations

from pathlib import Path

from ..config import AgentConfig
from ..models import AgentExecutionResult
from .base import ShellAgentAdapter


class CodexAdapter(ShellAgentAdapter):
    def __init__(self, config: AgentConfig):
        super().__init__(config)

    def run(
        self,
        instruction: str,
        cwd: str | Path,
        task_dir: str | Path,
        phase: str,
        stem: str,
    ) -> AgentExecutionResult:
        result = super().run(instruction, cwd, task_dir, phase, stem)
        # Codex writes its readable output to stderr and compact JSON to
        # stdout.  Swap so that downstream consumers (persist_agent_result,
        # coerce_json_output) see the rich content on stdout.
        if result.stderr and len(result.stderr) > len(result.stdout):
            return AgentExecutionResult(
                agent=result.agent,
                command=result.command,
                cwd=result.cwd,
                exit_code=result.exit_code,
                stdout=result.stderr,
                stderr=result.stdout,
                duration_s=result.duration_s,
                instruction_path=result.instruction_path,
                timed_out=result.timed_out,
            )
        return result
