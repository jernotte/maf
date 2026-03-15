"""Lightweight progress feedback for maf phases.

Writes status lines to stderr so they don't interfere with stdout
(which carries structured output like task IDs and file paths).
"""
from __future__ import annotations

import sys


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def log(phase: str, msg: str) -> None:
    print(f"[{phase}] {msg}", file=sys.stderr, flush=True)


def agent_start(phase: str, name: str, label: str = "") -> None:
    tag = f"{name}[{label}]" if label else name
    log(phase, f"├ {tag:<35} running...")


def agent_done(
    phase: str,
    name: str,
    duration: float,
    label: str = "",
    last: bool = False,
) -> None:
    tag = f"{name}[{label}]" if label else name
    prefix = "└" if last else "├"
    log(phase, f"{prefix} {tag:<35} done ({_fmt_duration(duration)})")
