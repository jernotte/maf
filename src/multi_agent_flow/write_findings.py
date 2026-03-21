"""CLI tool for agents to write research findings to a deterministic path.

Usage:
    python -m multi_agent_flow.write_findings /path/to/output.md << 'FINDINGS'
    content here
    FINDINGS

    python -m multi_agent_flow.write_findings /path/to/output.md --append << 'FINDINGS'
    more content
    FINDINGS
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write research findings to a file.",
    )
    parser.add_argument("path", help="Destination file path")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the file instead of overwriting",
    )
    args = parser.parse_args()

    dest = Path(args.path).resolve()

    # Validate path is within a .maf/tasks directory
    parts = dest.parts
    if ".maf" not in parts or "tasks" not in parts:
        print(
            f"Error: path must be within a .maf/tasks directory: {dest}",
            file=sys.stderr,
        )
        return 1

    # Prevent path traversal via ..
    if ".." in parts:
        print("Error: path must not contain '..'", file=sys.stderr)
        return 1

    content = sys.stdin.read()
    if not content:
        print("Error: no content received on stdin", file=sys.stderr)
        return 1

    dest.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if args.append else "w"
    with open(dest, mode, encoding="utf-8") as f:
        f.write(content)

    action = "Appended to" if args.append else "Wrote"
    print(f"{action} {dest} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
