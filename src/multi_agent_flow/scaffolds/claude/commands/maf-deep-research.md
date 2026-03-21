Run deep research with citation-enforced sourcing through the `maf` multi-agent flow.

Usage: /maf-deep-research <input-path-or-idea> --title "<task title>" [--iterations <N>] [--prefetch-site <URL>]

Parse the arguments from: $ARGUMENTS

This runs N iterations of parallel deep research where workers must find, fetch, and cite external sources. Every factual claim requires a citation. Sources are fetched via a tiered fallback chain (direct HTTP, wget, Jina Reader, Google Cache, Wayback Machine).

Steps:
1. Verify `maf` is installed and `.maf.yml` exists. If not, tell the user to run `/maf-init` first.
2. Determine the input: if the argument looks like a file path and exists, use it as `--input <path>`. Otherwise treat it as inline text.
3. Extract the title from `--title "..."`, iterations from `--iterations N` (default: from config, usually 3), and optionally `--prefetch-site <URL>`.
4. Run: `maf --project-root . deep-research --input <input> --title "<title>" --iterations <N> [--prefetch-site <URL>]`
5. This will take a while. Each iteration prints progress.
6. When complete, capture the task ID from stdout.
7. Read `.maf/tasks/<task-id>/task.json` to confirm state.
8. Read `.maf/tasks/<task-id>/research/synthesis.md` (the final evidence-backed research report) and present it.
9. Check if `.maf/tasks/<task-id>/research/source-gaps.md` exists. If so, present it — these are sources that need manual retrieval.
10. Tell the user they can re-run consolidation after adding missing sources: `maf deep-research --resume-task <task-id> --consolidate-only`
