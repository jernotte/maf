Show the current status of a `maf` task.

Usage: /maf-status <task-id>

If no task ID is provided, list all tasks.

Steps:
1. Parse the task ID from: $ARGUMENTS
2. If a task ID is provided:
   - Read `.maf/tasks/<task-id>/task.json` and display the task status, title, creation time, and current phase.
   - Check which phase artifacts exist and report completion status for each phase:
     - Research: check for `research/synthesis.md`
     - Spec: check for `spec/spec-draft.md` and `spec/spec-approved.md`
     - Build: check for `build/implementation-log.md`
     - Review: check for `review/gemini-review.json` and `review/codex-review.json`
     - Finalize: check for `finalize/final-summary.md`
   - Suggest the next command to run based on the current status.
3. If no task ID is provided:
   - List all directories under `.maf/tasks/`.
   - For each task, read `task.json` and show the task ID, title, and status.
