Generate a spec draft for an existing `maf` task.

Usage: /maf-spec <task-id>

Steps:
1. Parse the task ID from: $ARGUMENTS
2. Verify the task exists by reading `.maf/tasks/<task-id>/task.json`.
3. Run: `maf --project-root . spec --task <task-id>`
4. Read the generated spec draft at `.maf/tasks/<task-id>/spec/spec-draft.md`.
5. Present the spec draft to the user for review.
6. Tell the user: "Review the spec above. When you're satisfied, run `/maf-approve-spec <task-id>` to approve it and proceed to the build phase. Do not skip this approval step."
