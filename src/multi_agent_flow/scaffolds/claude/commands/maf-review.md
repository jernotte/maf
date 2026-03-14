Run independent Gemini and Codex reviews for an existing `maf` task.

Usage: /maf-review <task-id>

Steps:
1. Parse the task ID from: $ARGUMENTS
2. Read `.maf/tasks/<task-id>/task.json` to confirm the task has been built.
3. Run: `maf --project-root . review --task <task-id>`
4. Read `.maf/tasks/<task-id>/review/gemini-review.json` and summarize Gemini's findings.
5. Read `.maf/tasks/<task-id>/review/codex-review.json` and summarize Codex's findings.
6. Present a consolidated view of all findings grouped by severity (high, medium, low).
7. Remind the user: "These are independent review outputs. They should be treated as evidence, not automatic truth. Run `/maf-finalize <task-id>` to evaluate findings and complete the task."
