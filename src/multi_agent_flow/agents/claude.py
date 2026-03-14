from __future__ import annotations

from ..config import AgentConfig
from .base import ShellAgentAdapter


class ClaudeAdapter(ShellAgentAdapter):
    def __init__(self, config: AgentConfig):
        super().__init__(config)

