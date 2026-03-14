---
name: multi-agent-flow
description: Operate repositories that use the shared `maf` multi-agent delivery baseline. Use when the repo contains `maf`, `.maf.yml`, or `.maf/tasks/`, or when the user wants a design document or idea driven through the reusable research, spec, approve-spec, build, review, and finalize flow with Claude leading and Codex/Gemini acting as parallel reviewers.
---

# Multi Agent Flow

Use the repository's `maf` CLI as the source of orchestration truth. Do not re-create the workflow ad hoc in prompts when the baseline already exists in code.

## Drive The Flow

1. Verify the repo has `maf` installed and a `.maf.yml` file.
2. If `.maf.yml` is missing, run `maf --project-root <root> init` and then update the generated config with the real Claude/Codex/Gemini CLI commands.
3. Start new work with `maf research --project-root <root> --input <design-or-idea> --title "<task>"`.
4. Continue with `maf spec --project-root <root> --task <task-id>`.
5. Stop for explicit user approval before running `maf approve-spec`.
6. Only after approval, run `maf build`, `maf review`, and `maf finalize`.

Do not skip the approval gate. Do not implement directly from the original design doc if the repo expects the `maf` artifacts to be the working baseline.

## Use The Right Layer

- Patch `.maf.yml` when the workflow logic is correct but the project's command wiring is wrong.
- Patch `src/multi_agent_flow/` when the baseline engine behavior is wrong for all projects.
- Patch the prompt templates when the phase instructions need to change across projects.
- Keep project-specific app logic in the target repo, not in this skill.

## Respect The Artifacts

- Read `.maf/tasks/<task-id>/task.json` for task status and metadata.
- Read `.maf/tasks/<task-id>/normalized-brief.md` as the normalized source baseline.
- Read `.maf/tasks/<task-id>/spec/spec-approved.md` as the implementation contract.
- Read `.maf/tasks/<task-id>/review/*.json` as the structured review outputs.
- Prefer using the existing artifact files over paraphrasing earlier chat messages.

## Handle Known Edges

- If the input is a PDF and extracted text is weak, prefer a Markdown or text version before running the flow at scale.
- If real model CLIs are not configured yet, update `.maf.yml` first instead of trying to compensate with prompt hacks.
- If the user asks for direct coding without the full flow, use normal repo work instead of forcing `maf`.
- If the user asks to change the workflow itself, patch the baseline package and keep the skill thin.

## Reference Files

- Read [references/commands.md](references/commands.md) for exact command patterns, expected artifacts, and the matching Claude wrapper template paths.
