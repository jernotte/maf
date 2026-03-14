# Multi-Agent Flow Commands

## Quick Start

Install the baseline in editable mode from the repo that owns it:

```bash
python -m pip install -e .
```

Initialize project config:

```bash
maf --project-root <project-root> init
```

Start from a design doc or idea:

```bash
maf --project-root <project-root> research --input <path-or-inline-text> --title "<task>"
```

Generate the spec:

```bash
maf --project-root <project-root> spec --task <task-id>
```

Pause for explicit human approval, then:

```bash
maf --project-root <project-root> approve-spec --task <task-id>
maf --project-root <project-root> build --task <task-id>
maf --project-root <project-root> review --task <task-id>
maf --project-root <project-root> finalize --task <task-id>
```

## Artifact Contract

Read these files first when continuing an existing task:

- `.maf/tasks/<task-id>/task.json`
- `.maf/tasks/<task-id>/normalized-brief.md`
- `.maf/tasks/<task-id>/research/synthesis.md`
- `.maf/tasks/<task-id>/spec/spec-approved.md`
- `.maf/tasks/<task-id>/build/implementation-log.md`
- `.maf/tasks/<task-id>/review/gemini-review.json`
- `.maf/tasks/<task-id>/review/codex-review.json`
- `.maf/tasks/<task-id>/finalize/final-summary.md`

## Configuration Contract

Use `.maf.yml` for:

- model CLI command wiring
- validation profiles
- research worker focuses

Patch `.maf.yml` when adapting the workflow to a particular project. Patch `src/multi_agent_flow/` only when changing the reusable engine itself.

## Claude Counterpart

The matching Claude scaffolds live here (bundled in the package and written by `maf init`):

- `src/multi_agent_flow/scaffolds/claude/CLAUDE.md`
- `src/multi_agent_flow/scaffolds/claude/commands/`

Run `maf --project-root <project-root> init` to write these into a project alongside the Codex skill.

