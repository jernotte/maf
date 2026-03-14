Approve the current spec draft for an existing `maf` task.

Usage: /maf-approve-spec <task-id>

Steps:
1. Parse the task ID from: $ARGUMENTS
2. Read `.maf/tasks/<task-id>/task.json` to confirm the task is in `spec-drafted` status.
3. Read `.maf/tasks/<task-id>/spec/spec-draft.md` and show a brief summary to confirm what is being approved.
4. Run: `maf --project-root . approve-spec --task <task-id>`
5. Confirm approval by reading `.maf/tasks/<task-id>/task.json` again and verifying `spec_approved` is true.
6. Tell the user the spec is approved and suggest running `/maf-build <task-id>` next.
