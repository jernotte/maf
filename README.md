# maf — Multi-Agent Flow

A CLI orchestrator that drives design-to-code tasks through a fixed multi-agent pipeline using Claude, Codex, and Gemini.

Give it a design doc or plain-language idea, point it at any project, and `maf` runs the full lifecycle:

```
Research → Spec → Approve → Build → Review → Finalize
```

Each phase is executed by real AI agent CLIs (Claude, Codex, Gemini) running in parallel where possible, with structured artifacts persisted at every step.

## Install

```bash
pip install -e .
```

Requires Python 3.11+. You also need the CLI tools you plan to use installed and authenticated:

- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code)
- [Codex CLI](https://github.com/openai/codex)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)

## Quick start

### 1. Initialize a project

```bash
maf --project-root /path/to/your/project init
```

This writes a `.maf.yml` config and scaffolds `.claude/` and `.codex/` directories with agent instructions and slash commands.

### 2. Run research

```bash
maf --project-root . research --input docs/design.pdf --title "Add user auth"
```

Launches parallel research workers across all three agents, then synthesizes findings with Claude. Accepts Markdown, PDF, or plain text as input.

### 3. Generate a spec

```bash
maf --project-root . spec --task <task-id>
```

### 4. Approve the spec

Review the draft at `.maf/tasks/<task-id>/spec/spec-draft.md`, then:

```bash
maf --project-root . approve-spec --task <task-id>
```

No build can start without explicit approval.

### 5. Build

```bash
maf --project-root . build --task <task-id>
```

Claude implements against the approved spec with pre-approved tool access. Changed files are tracked and validation commands from `.maf.yml` run automatically.

### 6. Review

```bash
maf --project-root . review --task <task-id>
```

Gemini and Codex independently review the implementation against the spec. Findings are categorized by type and severity.

### 7. Finalize

```bash
maf --project-root . finalize --task <task-id>
```

Claude evaluates review findings, fixes valid issues, rejects unsupported ones with rationale, and produces a final summary.

## Research loop

For deeper analysis, use the iterative research-critique loop:

```bash
maf --project-root . research-loop --input idea.md --title "Redesign API" --iterations 5
```

Each iteration builds on the previous synthesis. A final consolidation pass produces the output. Supports `--resume-task` and `--start-iteration` for resuming interrupted runs.

## Configuration

`maf init` writes a `.maf.yml` in your project root. Key sections:

```yaml
agents:
  claude:
    command: [claude, -p, --tools, "", --no-session-persistence]
    timeout_s: 1800
  claude-build:
    command: [claude, -p, --allowedTools, "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch", --no-session-persistence]
    timeout_s: 3600
  codex:
    command: [codex, exec, --skip-git-repo-check, "-"]
    timeout_s: 1800
  gemini:
    command: [gemini, -p, ""]
    timeout_s: 1800

research:
  worker_focuses:
    - architecture
    - domain-model
    - risks-and-edge-cases
  max_workers: 3

validation_profiles:
  default:
    commands: []  # auto-detected by maf init (pytest, npm test, etc.)
```

`maf init` auto-detects your project language and sets validation commands accordingly (`pyproject.toml` → `pytest`, `package.json` → `npm test`).

## Artifacts

All state lives under `.maf/tasks/<task-id>/`:

```
task.json                    # task metadata and status
normalized-brief.md          # canonical input document
research/
  claude-worker-*.md         # per-agent research outputs
  synthesis.md               # consolidated research
spec/
  spec-draft.md              # generated spec
  spec-approved.md           # approved snapshot
build/
  implementation-log.md      # what changed and why
  changed-files.json         # files touched
review/
  gemini-review.json         # independent review
  codex-review.json          # independent review
finalize/
  final-summary.md           # disposition and summary
```

## Claude Code integration

`maf init` scaffolds Claude Code slash commands into your project. Available commands:

- `/maf-research` — create a task and run research
- `/maf-spec` — generate a spec draft
- `/maf-approve-spec` — approve the spec
- `/maf-build` — implement the approved spec
- `/maf-review` — run independent reviews
- `/maf-finalize` — fix findings and finalize
- `/maf-flow` — run the full flow end-to-end
- `/maf-research-loop` — iterative research-critique loop
- `/maf-status` — show task status

## Progress feedback

All phases emit progress to stderr so you can see what's happening during long runs:

```
[build] Rendering prompt...
[build] ├ claude-build                        running...
[build] └ claude-build                        done (12m 33s)
[build] Running validation...
[build] Validation passed
[build] Done → build/implementation-log.md

[review] Starting independent reviews...
[review] ├ gemini                              running...
[review] ├ codex                               running...
[review] ├ gemini                              done (3m 12s)
[review] └ codex                               done (4m 45s)
[review] Done → review/
```

## Design principles

- **Agent-agnostic**: thin adapters wrap each CLI. Phase logic lives in phase modules, not agent code.
- **Spec-gated**: no implementation without explicit approval.
- **Independent review**: Gemini and Codex review separately. Their outputs are evidence, not automatic truth.
- **Project-agnostic**: no framework assumptions. Validation commands come from config.
- **Auditable**: every prompt sent and every output received is persisted to disk.

## License

MIT
