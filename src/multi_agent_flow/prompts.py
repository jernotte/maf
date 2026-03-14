from __future__ import annotations

from importlib.resources import files


def render_prompt(template_name: str, **values: str) -> str:
    template = (
        files("multi_agent_flow")
        .joinpath("prompts")
        .joinpath(template_name)
        .read_text(encoding="utf-8")
    )
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered
