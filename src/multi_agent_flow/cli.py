from __future__ import annotations

import argparse
from importlib.resources import files
from pathlib import Path
import sys
from typing import Iterator

from .config import load_project_config
from .phases import approve_spec, run_build, run_finalize, run_research, run_research_loop, run_review, run_spec
from .phases.research_loop import resume_research_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maf", description="Multi-agent delivery baseline.")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Target project root for config, artifacts, and command execution.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Write a sample .maf.yml and agent scaffolds into the target project.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    init_parser.add_argument(
        "--skip-scaffolds",
        action="store_true",
        help="Only write .maf.yml, skip .claude/ and .codex/ scaffolds.",
    )

    research = subparsers.add_parser("research", help="Create a task and run research.")
    research.add_argument("--input", required=True, help="Path to a design doc or inline idea text.")
    research.add_argument("--title", required=True, help="Short task title.")
    research.add_argument("--validation-profile", help="Optional validation profile override.")
    research.add_argument(
        "--max-research-workers",
        type=int,
        help="Override the configured number of Claude research workers.",
    )

    research_loop = subparsers.add_parser(
        "research-loop",
        help="Iterative research-critique loop. Runs parallel research + synthesis N times, each building on the last.",
    )
    research_loop.add_argument("--input", help="Path to a design doc or inline idea text (required for new tasks).")
    research_loop.add_argument("--title", help="Short task title (required for new tasks).")
    research_loop.add_argument("--iterations", type=int, default=5, help="Number of research-critique iterations (default: 5).")
    research_loop.add_argument("--validation-profile", help="Optional validation profile override.")
    research_loop.add_argument(
        "--max-research-workers",
        type=int,
        help="Override the configured number of Claude research workers.",
    )
    research_loop.add_argument(
        "--resume-task",
        help="Resume an existing task instead of creating a new one.",
    )
    research_loop.add_argument(
        "--start-iteration",
        type=int,
        help="Iteration to resume from (requires --resume-task). Prior iterations are loaded from disk.",
    )

    spec = subparsers.add_parser("spec", help="Generate a spec draft for an existing task.")
    spec.add_argument("--task", required=True, help="Task ID.")

    approve = subparsers.add_parser("approve-spec", help="Approve the current spec draft.")
    approve.add_argument("--task", required=True, help="Task ID.")

    build = subparsers.add_parser("build", help="Implement the approved spec.")
    build.add_argument("--task", required=True, help="Task ID.")

    review = subparsers.add_parser("review", help="Run Gemini and Codex review.")
    review.add_argument("--task", required=True, help="Task ID.")

    finalize = subparsers.add_parser("finalize", help="Fix findings and finalize the task.")
    finalize.add_argument("--task", required=True, help="Task ID.")
    return parser


def _walk_scaffold(scaffold_dir) -> Iterator[tuple[str, str]]:
    """Yield (relative_path, content) for every file in a scaffold directory."""
    for item in scaffold_dir.iterdir():
        if item.is_dir():
            for child_rel, child_content in _walk_scaffold(item):
                yield f"{item.name}/{child_rel}", child_content
        elif item.is_file():
            yield item.name, item.read_text(encoding="utf-8")


def _write_scaffold(project_root: Path, dot_dir: str, scaffold_name: str, force: bool) -> list[Path]:
    """Copy a scaffold directory into the project root. Returns list of written paths."""
    scaffold_dir = files("multi_agent_flow").joinpath("scaffolds").joinpath(scaffold_name)
    written: list[Path] = []
    for rel_path, content in _walk_scaffold(scaffold_dir):
        dest = project_root / dot_dir / rel_path
        if dest.exists() and not force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(dest)
    return written


def _init_config(project_root: Path, force: bool, skip_scaffolds: bool = False) -> list[Path]:
    written: list[Path] = []

    destination = project_root / ".maf.yml"
    if destination.exists() and not force:
        raise FileExistsError(f"{destination} already exists. Use --force to overwrite it.")
    sample = files("multi_agent_flow").joinpath("default_maf.yml").read_text(encoding="utf-8")
    destination.write_text(sample, encoding="utf-8")
    written.append(destination)

    if not skip_scaffolds:
        written.extend(_write_scaffold(project_root, ".claude", "claude", force))
        written.extend(_write_scaffold(project_root, ".codex/skills/multi-agent-flow", "codex/skills/multi-agent-flow", force))

    return written


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve()

    if args.command == "init":
        written = _init_config(project_root, args.force, args.skip_scaffolds)
        for path in written:
            print(path)
        return 0

    config = load_project_config(project_root)

    if args.command == "research":
        task_id = run_research(
            project_root=str(project_root),
            config=config,
            title=args.title,
            input_value=args.input,
            validation_profile=args.validation_profile,
            max_research_workers=args.max_research_workers,
        )
        print(task_id)
        return 0

    if args.command == "research-loop":
        if args.resume_task:
            task_id = resume_research_loop(
                project_root=str(project_root),
                config=config,
                task_id=args.resume_task,
                start_iteration=args.start_iteration or 1,
                iterations=args.iterations,
                max_research_workers=args.max_research_workers,
            )
        else:
            task_id = run_research_loop(
                project_root=str(project_root),
                config=config,
                title=args.title,
                input_value=args.input,
                validation_profile=args.validation_profile,
                max_research_workers=args.max_research_workers,
                iterations=args.iterations,
            )
        print(task_id)
        return 0

    if args.command == "spec":
        path = run_spec(str(project_root), config, args.task)
        print(path)
        return 0

    if args.command == "approve-spec":
        path = approve_spec(str(project_root), config, args.task)
        print(path)
        return 0

    if args.command == "build":
        path = run_build(str(project_root), config, args.task)
        print(path)
        return 0

    if args.command == "review":
        path = run_review(str(project_root), config, args.task)
        print(path)
        return 0

    if args.command == "finalize":
        path = run_finalize(str(project_root), config, args.task)
        print(path)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
