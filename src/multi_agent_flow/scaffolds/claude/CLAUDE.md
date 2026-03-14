# Claude Project Instructions

Use the shared `maf` workflow as the default delivery engine for design-to-code tasks.

## Default Behavior

- Treat `maf` as the orchestration source of truth.
- Do not bypass the spec approval gate.
- Do not implement directly from a raw design doc when the task should be tracked in `.maf/tasks/`.
- Prefer changing `.maf.yml` or the shared prompt templates over embedding one-off workflow rules into ad hoc prompts.
- When a repo contains `.maf.yml` or `.maf/tasks/`, assume the multi-agent flow is active.

## Execution Flow

1. Ensure `maf` is installed (`python -m pip install -e .` from this repo) and `.maf.yml` exists in the target project.
2. Run `maf --project-root <root> research --input <design-or-idea> --title "<task>"`.
3. Run `maf --project-root <root> spec --task <task-id>`.
4. Wait for explicit user approval before `maf approve-spec --task <task-id>`.
5. Run `maf --project-root <root> build --task <task-id>`.
6. Run `maf --project-root <root> review --task <task-id>`.
7. Run `maf --project-root <root> finalize --task <task-id>`.

## Artifacts

- Read `.maf/tasks/<task-id>/task.json` for state.
- Read `.maf/tasks/<task-id>/normalized-brief.md` for normalized source material.
- Read `.maf/tasks/<task-id>/research/synthesis.md` for research synthesis.
- Read `.maf/tasks/<task-id>/spec/spec-approved.md` as the implementation contract.
- Read `.maf/tasks/<task-id>/build/implementation-log.md` for build output.
- Read `.maf/tasks/<task-id>/build/changed-files.json` for files touched during build.
- Read `.maf/tasks/<task-id>/review/*.json` for independent review output.
- Read `.maf/tasks/<task-id>/finalize/final-summary.md` for the final disposition.

## Operating Rules

- Use `maf` for orchestration and task persistence.
- Use the approved spec as the build contract.
- Treat Gemini and Codex review outputs as independent evidence, not as automatic truth.
- Fix only validated findings during finalize.
- Keep repo-specific command wiring in `.maf.yml`.

## Right Layer For Changes

- Patch `.maf.yml` when the workflow logic is correct but the project's command wiring is wrong.
- Patch `src/multi_agent_flow/` when the baseline engine behavior is wrong for all projects.
- Patch the prompt templates in `src/multi_agent_flow/prompts/` when the phase instructions need to change across projects.
- Keep project-specific app logic in the target repo, not in this baseline.

## Slash Commands

- `/maf-init` - Initialize `.maf.yml` in a target project.
- `/maf-research` - Create a new task and run the research phase.
- `/maf-spec` - Generate a spec draft for an existing task.
- `/maf-approve-spec` - Approve the current spec draft.
- `/maf-build` - Implement the approved spec.
- `/maf-review` - Run independent Gemini and Codex reviews.
- `/maf-finalize` - Fix findings and finalize the task.
- `/maf-flow` - Run the full flow end-to-end with an approval pause.
- `/maf-status` - Show the current status of a task.
