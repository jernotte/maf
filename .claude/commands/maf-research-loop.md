Run an iterative research-critique loop through the `maf` multi-agent flow.

Usage: /maf-research-loop <input-path-or-idea> --title "<task title>" --iterations <N>

Parse the arguments from: $ARGUMENTS

This runs N iterations of parallel research + synthesis, where each iteration builds on the previous one's findings. Workers critique the design, challenge assumptions, find gaps, and go deeper each round.

Steps:
1. Verify `maf` is installed and `.maf.yml` exists. If not, tell the user to run `/maf-init` first.
2. Determine the input: if the argument looks like a file path and exists, use it as `--input <path>`. Otherwise treat it as inline text.
3. Extract the title from `--title "..."` and iterations from `--iterations N` (default: 5).
4. Run: `maf --project-root . research-loop --input <input> --title "<title>" --iterations <N>`
5. This will take a while. Each iteration prints progress.
6. When complete, capture the task ID from stdout.
7. Read `.maf/tasks/<task-id>/task.json` to confirm state.
8. Read `.maf/tasks/<task-id>/research/synthesis.md` (the final cumulative synthesis) and present it.
9. Optionally, the user can read individual iteration outputs at `.maf/tasks/<task-id>/research/iteration-NNN/synthesis.md`.
