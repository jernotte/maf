from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shlex

import yaml


@dataclass
class AgentConfig:
    name: str
    command: list[str]
    timeout_s: int = 1800


@dataclass
class ResearchConfig:
    worker_focuses: list[str] = field(
        default_factory=lambda: [
            "architecture",
            "domain-model",
            "risks-and-edge-cases",
        ]
    )
    max_workers: int = 3


@dataclass
class ValidationProfile:
    name: str
    commands: list[str]


@dataclass
class AppConfig:
    maf_dir: str = ".maf"
    default_validation_profile: str | None = None
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    validation_profiles: dict[str, ValidationProfile] = field(default_factory=dict)

    def resolve_validation_commands(self, profile_name: str | None) -> list[str]:
        resolved = profile_name or self.default_validation_profile
        if not resolved:
            return []
        profile = self.validation_profiles.get(resolved)
        return profile.commands if profile else []


def _normalize_command(raw: str | list[str] | None, fallback_binary: str) -> list[str]:
    if raw is None:
        return [fallback_binary]
    if isinstance(raw, str):
        return shlex.split(raw)
    return [str(part) for part in raw]


_AGENT_DEFAULTS: dict[str, tuple[list[str], int]] = {
    "claude-build": (["claude", "-p", "--no-session-persistence"], 3600),
}


def _load_agent_configs(raw: dict | None) -> dict[str, AgentConfig]:
    agent_names = ("claude", "claude-build", "codex", "gemini")
    configs: dict[str, AgentConfig] = {}
    raw = raw or {}
    for name in agent_names:
        agent_data = raw.get(name, {})
        default_cmd, default_timeout = _AGENT_DEFAULTS.get(name, (None, 1800))
        if agent_data.get("command") is not None:
            command = _normalize_command(agent_data["command"], name)
        elif default_cmd is not None:
            command = list(default_cmd)
        else:
            command = _normalize_command(None, name)
        configs[name] = AgentConfig(
            name=name,
            command=command,
            timeout_s=int(agent_data.get("timeout_s", default_timeout)),
        )
    return configs


def _load_validation_profiles(raw: dict | None) -> dict[str, ValidationProfile]:
    profiles: dict[str, ValidationProfile] = {}
    raw = raw or {}
    for name, profile_data in raw.items():
        profiles[name] = ValidationProfile(
            name=name,
            commands=[str(command) for command in profile_data.get("commands", [])],
        )
    return profiles


def load_project_config(project_root: str | Path) -> AppConfig:
    root = Path(project_root).resolve()
    config_path = root / ".maf.yml"
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        data = {}

    research_data = data.get("research", {})
    research = ResearchConfig(
        worker_focuses=[
            str(item)
            for item in research_data.get(
                "worker_focuses",
                ["architecture", "domain-model", "risks-and-edge-cases"],
            )
        ],
        max_workers=int(research_data.get("max_workers", 3)),
    )

    return AppConfig(
        maf_dir=str(data.get("maf_dir", ".maf")),
        default_validation_profile=data.get("default_validation_profile"),
        agents=_load_agent_configs(data.get("agents")),
        research=research,
        validation_profiles=_load_validation_profiles(data.get("validation_profiles")),
    )

