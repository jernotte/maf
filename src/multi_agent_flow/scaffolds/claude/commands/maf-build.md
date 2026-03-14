Implement the approved spec for an existing `maf` task.

Usage: /maf-build <task-id>

Steps:
1. Parse the task ID from: $ARGUMENTS
2. Read `.maf/tasks/<task-id>/task.json` to confirm the spec is approved. If not, tell the user to run `/maf-approve-spec <task-id>` first.
3. Run: `maf --project-root . build --task <task-id>`
4. Read `.maf/tasks/<task-id>/build/implementation-log.md` and present a summary.
5. Read `.maf/tasks/<task-id>/build/changed-files.json` and list the files that were changed.
6. Read `.maf/tasks/<task-id>/build/validation.json` and report validation results.
7. Tell the user the build is complete and suggest running `/maf-review <task-id>` next.
