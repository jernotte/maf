Run the full `maf` multi-agent flow end-to-end for a new task.

Usage: /maf-flow <input-path-or-idea> --title "<task title>"

Parse the arguments from: $ARGUMENTS

This command orchestrates the entire flow with an approval pause between spec and build.

Steps:
1. Verify `maf` is installed and `.maf.yml` exists. If not, run `/maf-init` first.
2. Determine the input and title from the arguments.
3. Run the research phase: `maf --project-root . research --input <input> --title "<title>"`
4. Capture the task ID from stdout.
5. Read and summarize `.maf/tasks/<task-id>/research/synthesis.md`.
6. Run the spec phase: `maf --project-root . spec --task <task-id>`
7. Read and present `.maf/tasks/<task-id>/spec/spec-draft.md` to the user.
8. STOP HERE and ask the user to review the spec. Tell them: "Please review the spec above. Reply 'approve' to proceed or provide feedback for revisions."
9. Wait for explicit user approval. Do NOT proceed without it.
10. Once approved, run: `maf --project-root . approve-spec --task <task-id>`
11. Run the build phase: `maf --project-root . build --task <task-id>`
12. Read and summarize the build output and validation results.
13. Run the review phase: `maf --project-root . review --task <task-id>`
14. Read and summarize both review outputs.
15. Run the finalize phase: `maf --project-root . finalize --task <task-id>`
16. Read and present the final summary and disposition.
17. Report task complete with the task ID.
