Fix validated findings and finalize an existing `maf` task.

Usage: /maf-finalize <task-id>

Steps:
1. Parse the task ID from: $ARGUMENTS
2. Read `.maf/tasks/<task-id>/task.json` to confirm the task has been reviewed.
3. Run: `maf --project-root . finalize --task <task-id>`
4. Read `.maf/tasks/<task-id>/finalize/final-summary.md` and present the final summary.
5. Read `.maf/tasks/<task-id>/finalize/disposition.json` and report which findings were accepted vs rejected with rationale.
6. Read `.maf/tasks/<task-id>/finalize/validation.json` and report final validation results.
7. Confirm the task is complete.
