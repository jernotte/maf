Create a new task and run the research phase through the `maf` multi-agent flow.

Usage: /maf-research <input-path-or-idea> --title "<task title>"

Parse the arguments from: $ARGUMENTS

Steps:
1. Verify `maf` is installed and `.maf.yml` exists in the project root. If not, tell the user to run `/maf-init` first.
2. Determine the input: if the argument looks like a file path and exists, use it as `--input <path>`. Otherwise treat it as inline text.
3. Extract the title from `--title "..."` in the arguments. If no title is provided, ask the user for one.
4. Run: `maf --project-root . research --input <input> --title "<title>"`
5. Capture the task ID from stdout.
6. Read `.maf/tasks/<task-id>/task.json` to confirm state.
7. Read `.maf/tasks/<task-id>/research/synthesis.md` and present a summary to the user.
8. Tell the user the task ID and suggest running `/maf-spec <task-id>` next.
