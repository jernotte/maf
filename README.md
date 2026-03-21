# maf — Multi-Agent Flow

A CLI orchestrator that drives design-to-code tasks through a fixed multi-agent pipeline using Claude, Codex, and Gemini.

Give it a design doc or plain-language idea, point it at any project, and `maf` runs the full lifecycle:

```
Research → Spec → Approve → Build → Review → Finalize
```

Each phase is executed by real AI agent CLIs (Claude, Codex, Gemini) running in parallel where possible, with structured artifacts persisted at every step.

## Install

```bash
git clone https://github.com/jernotte/maf.git
cd maf
pip install -e .
```

Requires Python 3.11+. You also need the agent CLIs installed and authenticated:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — used for research, spec, build, and finalize
- [Codex CLI](https://github.com/openai/codex) — used for research and review
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) — used for research and review

Verify the install:

```bash
maf --help
```

## Quick start

### 1. Initialize a project

```bash
maf --project-root /path/to/your/project init
```

This writes:
- `.maf.yml` — project config (agent commands, research focuses, validation)
- `.claude/` — Claude Code slash commands and project instructions
- `.codex/` — Codex skill files and `config.toml` (sandbox, approval, web search settings)
- `.gemini/` — Gemini `settings.json` (shell, search, file access tool permissions)

Run all subsequent commands from your project directory.

### 2. Run research

```bash
maf research --input docs/design.md --title "Add user auth"
```

Launches parallel research workers across all three agents, then synthesizes findings with Claude. Accepts Markdown, PDF, or plain text as input.

### 3. Generate a spec

```bash
maf spec --task <task-id>
```

### 4. Approve the spec

Review the draft at `.maf/tasks/<task-id>/spec/spec-draft.md`, then:

```bash
maf approve-spec --task <task-id>
```

No build can start without explicit approval.

### 5. Build

```bash
maf build --task <task-id>
```

Claude implements against the approved spec with pre-approved tool access. Changed files are tracked and validation commands from `.maf.yml` run automatically.

### 6. Review

```bash
maf review --task <task-id>
```

Gemini and Codex independently review the implementation against the spec. Findings are categorized by type and severity.

### 7. Finalize

```bash
maf finalize --task <task-id>
```

Claude evaluates review findings, fixes valid issues, rejects unsupported ones with rationale, and produces a final summary.

## Research loop

For deeper analysis, use the iterative research-critique loop:

```bash
maf research-loop --input idea.md --title "Redesign API" --iterations 5
```

Each iteration builds on the previous synthesis. A final consolidation pass produces the output. Supports `--resume-task` and `--start-iteration` for resuming interrupted runs.

## Deep research

For evidence-backed research with structured citations and source fetching:

```bash
maf deep-research --input "What are the tradeoffs of CRDT vs OT for collaborative editing?" --title "CRDT vs OT" --iterations 3
```

Deep research differs from the research loop:

- **Citation-enforced**: every factual claim must cite a source. Uncited claims are marked `[UNVERIFIED]`.
- **Source fetching**: workers use `fetch_source` to retrieve full page content from URLs found via web search, with a 6-tier fallback chain (direct HTTP, wget, Jina Reader, Google Cache, Wayback Machine, snippet).
- **Evidence assessment**: findings are rated by evidence strength (strong/moderate/weak/conflicting).
- **Source gap report**: after completion, any sources that couldn't be fetched are listed in `research/source-gaps.md` for manual retrieval.

### Pre-fetching a site

If your research centers on a specific site's documentation:

```bash
maf deep-research --input "How does X work?" --title "X deep dive" --prefetch-site https://docs.example.com
```

This downloads the site recursively before workers start. Workers can then read the local copy instead of fetching individual pages.

### Resuming and re-consolidation

```bash
# Resume from a specific iteration
maf deep-research --resume-task <task-id> --start-iteration 3 --iterations 5

# Re-run only final consolidation (e.g. after manually adding missing sources)
maf deep-research --resume-task <task-id> --consolidate-only
```

### Fetch source tool

`fetch_source` is a standalone CLI tool that agents call to retrieve URL content:

```bash
python -m multi_agent_flow.fetch_source "https://example.com/article" /path/to/sources/source-001.md --snippet "fallback text"
```

Tiered fallback chain (first success wins):

| Tier | Method | Timeout |
|------|--------|---------|
| 1 | Direct HTTP (urllib) | 15s |
| 2 | wget | 20s |
| 3 | Jina Reader (r.jina.ai) | 30s |
| 4 | Google Cache | 15s |
| 5 | Wayback Machine | 15s |
| 6 | Snippet fallback (--snippet) | N/A |

Each fetched source gets a `.meta.json` sidecar with the URL, fetch tier, size, and timestamp. The tool is also available in the regular research loop as an optional enhancement.

## Configuration

`maf init` writes a `.maf.yml` in your project root. It auto-detects your project language and sets validation commands accordingly (`pyproject.toml` → `pytest`, `package.json` → `npm test`).

```yaml
agents:
  claude:
    command: [claude, -p, --allowedTools, "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch", --no-session-persistence]
    timeout_s: 1800
  claude-research:
    command: [claude, -p, --allowedTools, "Bash,Read,Glob,Grep,WebFetch,WebSearch", --no-session-persistence]
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
  gemini-research:
    command: [gemini, -p, ""]
    timeout_s: 1800
  codex-research:
    command: [codex, exec, --skip-git-repo-check, -a, never, -s, workspace-write, --search, -c, "sandbox_workspace_write.network_access=true", "-"]
    timeout_s: 1800

research:
  worker_focuses:
    - architecture
    - domain-model
    - risks-and-edge-cases
  max_workers: 3

deep_research:
  worker_focuses:
    - foundational-sources
    - supporting-evidence
    - counterarguments
    - implementation-precedent
  max_workers: 4
  iterations: 3

validation_profiles:
  default:
    commands: []  # set by maf init based on detected language
```

### agents

Each agent entry defines how maf invokes an external AI CLI. The `command` list is the exact argv passed to `subprocess.run` — the phase prompt is piped to stdin. `timeout_s` is the maximum wall-clock time before the agent is killed.

- **claude** — used for synthesis and spec generation. `--allowedTools` pre-approves file and web tools.
- **claude-research** — used for research workers. Read-only tool access (no Edit/Write).
- **claude-build** — used for build and finalize. Full tool access including Edit/Write.
- **codex** — used for research and review. Runs in exec mode with stdin prompt.
- **gemini** — used for research and review. Runs in prompt mode.
- **gemini-research** — used for deep research workers. Tool permissions come from `.gemini/settings.json`.
- **codex-research** — used for deep research workers. Runs with auto-approval, workspace write, live web search, and network access enabled.

To swap an agent's model, change the command. To disable an agent entirely, remove it from the config (phases that need it will fail with a clear error).

### research

Controls the parallel research and research-loop phases.

- **worker_focuses** — each entry spawns a separate Claude research worker with that focus area as its lens. Add more focuses for broader coverage, remove for faster/cheaper runs. Examples: `architecture`, `domain-model`, `risks-and-edge-cases`, `feasibility`, `gaps-and-missing-requirements`, `security`.
- **max_workers** — limits how many Claude research workers run in parallel. All focuses run, but only N at a time. Gemini and Codex always run one broad-research worker each on top of this.

### deep_research

Controls the deep research phase.

- **worker_focuses** — each entry spawns a Claude worker with that research angle. Default focuses are designed for evidence gathering: `foundational-sources` (canonical references), `supporting-evidence` (corroboration), `counterarguments` (opposing views), `implementation-precedent` (real-world examples).
- **max_workers** — parallel worker limit (default: 4).
- **iterations** — number of research-critique iterations (default: 3). Each iteration builds on the previous synthesis.

### validation_profiles

Commands that run after build and finalize to verify the implementation. `maf init` auto-detects these, but you can customize:

```yaml
validation_profiles:
  default:
    commands:
      - pytest
      - npm test
      - mypy --strict src/
  strict:
    commands:
      - pytest --tb=short
      - ruff check .
```

Use `--validation-profile strict` on research to override the default for a task.

## Agent scaffolds

`maf init` writes agent-specific config files into your project:

### `.gemini/settings.json`

Enables tools that Gemini workers need:

```json
{
  "tools": {
    "google_search": true,
    "run_shell_command": true,
    "read_file": true,
    "list_directory": true
  }
}
```

### `.codex/config.toml`

Project-level Codex config for non-interactive execution:

```toml
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "live"

[sandbox_workspace_write]
network_access = true
```

### Updating scaffolds

If you initialized a project with an older version of maf, you can update just the scaffolds without touching `.maf.yml`:

```bash
# Add only new files (won't overwrite existing)
maf init --scaffolds-only

# Force-update all scaffolds to latest versions
maf init --update-scaffolds
```

## Artifacts

All state lives under `.maf/tasks/<task-id>/`:

```
task.json                    # task metadata and status
normalized-brief.md          # canonical input document
research/
  iteration-001/             # per-iteration (research-loop and deep-research)
    sources/                 # fetched source content (deep-research)
      source-001.md
      source-001.meta.json
    claude-worker-*.findings.md
    gemini.findings.md
    codex.findings.md
    synthesis.md
  iteration-002/
  ...
  final/
    consolidation.md
  prefetched-sites/          # optional site mirror (deep-research --prefetch-site)
  source-gaps.md             # unfetched sources for manual retrieval
  synthesis.md               # final consolidated output
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
- `/maf-research-loop` — iterative research-critique loop
- `/maf-deep-research` — deep research with citation-enforced sourcing
- `/maf-spec` — generate a spec draft
- `/maf-approve-spec` — approve the spec
- `/maf-build` — implement the approved spec
- `/maf-review` — run independent reviews
- `/maf-finalize` — fix findings and finalize
- `/maf-flow` — run the full flow end-to-end
- `/maf-status` — show task status

## Progress feedback

All phases emit progress to stderr so you can see what's happening during long runs:

```
[deep-research] Pre-fetching site: https://docs.example.com
[deep-research] Pre-fetched 47 files from docs.example.com
[deep-research] Iteration 1/3
[research:1/3] ├ claude-worker-1 [foundational-sources]     running...
[research:1/3] ├ claude-worker-2 [supporting-evidence]      running...
[research:1/3] ├ claude-worker-3 [counterarguments]         running...
[research:1/3] ├ claude-worker-4 [implementation-precedent] running...
[research:1/3] ├ gemini [broad-critique]                    running...
[research:1/3] ├ codex [broad-critique]                     running...
[research:1/3] ├ claude-worker-1 [foundational-sources]     done (8m 12s)
[research:1/3] └ codex [broad-critique]                     done (9m 45s)
[research:1/3] ├ claude [synthesis]                         running...
[research:1/3] └ claude [synthesis]                         done (4m 33s)
[deep-research] Iteration 2/3
...
[deep-research] Final consolidation...
[deep-research] Source gaps found — see research/source-gaps.md
```

## Design principles

- **Spec-gated**: no implementation without explicit approval.
- **Independent review**: Gemini and Codex review separately. Their outputs are evidence, not automatic truth.
- **Agent-agnostic**: thin adapters wrap each CLI. Phase logic lives in phase modules, not agent code.
- **Project-agnostic**: no framework assumptions. Validation commands come from config.
- **Auditable**: every prompt sent and every output received is persisted to disk.
- **Citation-enforced** (deep research): every claim must cite a source. Evidence strength is tracked across iterations.

## License

MIT
