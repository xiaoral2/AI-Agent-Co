# XR-AI-Co

[![CI](https://github.com/xiaoral2/AI-Agent-Co/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaoral2/AI-Agent-Co/actions)
[![GitHub stars](https://img.shields.io/github/stars/xiaoral2/AI-Agent-Co?style=social)](https://github.com/xiaoral2/AI-Agent-Co/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/xiaoral2/AI-Agent-Co?style=social)](https://github.com/xiaoral2/AI-Agent-Co/forks)
![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)

**A spec-driven “AI software company” harness for a single human CEO:** you give a mission, the system plans (DAG tasks), runs coder / tester / reviewer / architect tools, checkpoints state, and stops at human approval or escalation—not a chat loop, a **controlled org loop**.

Same *intent* as long-running agent stacks such as [TokenFly](https://tokenfly.ai/) and the open [Agentic_System](https://github.com/TokenFlyAI/Agentic_System) framework: **persistent goals, structured execution, and clear boundaries**. XR-AI-Co narrows that into a **Mode 1 MVP**: one workspace, JSON task graph, CEO gate, and explicit failure routing (see design spec §4.4, §7.2).

> **GitHub `owner/repo`:** These badges and `[project.urls]` in `pyproject.toml` use **`xiaoral2/AI-Agent-Co`**. After you create the remote (or if you fork), search-replace that string in **README.md** and **pyproject.toml** so CI / stars / forks / Issues links resolve. Until the repo exists on GitHub, the star/fork badges may show *invalid* or `0`.

---

## Why XR-AI-Co?

- **Mission-first** — Natural-language goal → validated task plan → execute until `done`, `blocked`, or `paused`.
- **Durable state** — Session checkpoints (`state/`) so you can **resume** after crashes or human decisions (§6.7).
- **Honest budgets** — Token, retry, optional USD ceiling, and wall-clock limits wired into scheduling and the loop (§17.2).
- **Three-layer context** — Global / parent / local blocks for every LLM role (§6.5), aligned with the spec.
- **Template or LLM** — Run end-to-end **without** an API key (stub planner + templates) or plug in **Anthropic** for real codegen.

---

## How this relates to [Agentic_System](https://github.com/TokenFlyAI/Agentic_System)

If you have the TokenFly repo checked out locally (e.g. `Agentic_System`), you can think of the split like this:

| | **Agentic_System** (TokenFly) | **XR-AI-Co** (this repo) |
|---|-------------------------------|---------------------------|
| **Center of gravity** | `Tool` + generator execution; agents-as-tools; YAML-configured DAG executor | Task JSON (`task.v1`) + reference **orchestrator loop** + CLI CEO flow |
| **Config surface** | Rich YAML (`!file`, skills, nested agents) | `xr_ai_co.yaml` + checkpoint JSON |
| **Context** | `ContextNode` tree (local / parent / global) | Same *idea*, implemented as prompt blocks + session `global` |
| **Best for** | Composable multi-agent products, TUI/service APIs | Single-repo “company harness”, spec-traceable Mode 1 slice |

XR-AI-Co does **not** replace Agentic_System; it is a **smaller, spec-anchored** slice you can run as a CLI over one workspace.

---

## Table of contents

- [Quick start](#quick-start)
- [Features](#features-at-a-glance)
- [Repository layout](#repository-layout)
- [Testing & development](#testing--development)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [CLI reference](#cli-reference)
- [Spec compliance & non-goals](#spec-compliance)
- [Contributing & security](#contributing--security)

---

## Quick start

```bash
git clone https://github.com/xiaoral2/AI-Agent-Co.git
cd AI-Agent-Co
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### Template mode (no API key)

```bash
python main.py "build a rate limiter"          # interactive CEO approve
xr-ai-co run -y "build a rate limiter"         # non-interactive
```

### LLM mode (Anthropic)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
xr-ai-co run -y --config xr_ai_co.yaml "build a rate limiter"
```

### Resume / pause / status (§6.7, §2.2)

```bash
xr-ai-co resume --session-id default
xr-ai-co resume --session-id default -y
xr-ai-co resume --session-id default --refresh-config
xr-ai-co pause --session-id default
xr-ai-co status --session-id default
xr-ai-co status --session-id default --json
```

Non-interactive runs that hit `blocked`: `xr-ai-co run -y --blocked-interactive ...` or `XR_AI_CO_BLOCKED_INTERACTIVE=1`.

Resume merges YAML policies into the checkpoint without a flag: `XR_AI_CO_RESUME_REFRESH_CONFIG=1`.

---

## Features at a glance

- DAG task scheduling with cycle detection (§6.4)
- Failure taxonomy + routing (`test_failure`, `syntax_error`, `requirement_mismatch`, `infra_error`) (§4.4)
- CEO choices on escalation: modify plan / continue / abort (§7.2)
- Optional workspace `git init` / snapshot / rollback (§9.2–§9.3)
- SLA-style deadline priority boosts in the scheduler (§2.5.3a)
- Cross-run `state/knowledge_base.json` merge (§2.5.5)
- `status` subcommand for a CEO-friendly snapshot (§2.2)

**Spec files:** the normative spec for this harness is maintained as Markdown under `design_notes/` (e.g. `ai-company-spec.md`). That directory is **gitignored** in this repo so local specs stay private; clone or author your own copies beside the code. For a related long-running agent framework, see [Agentic_System](https://github.com/TokenFlyAI/Agentic_System).

---

## Repository layout

```
AI-Agent-Co/
├── .github/workflows/ci.yml   # pytest on 3.11–3.13
├── orchestrator/              # state manager, scheduler, reference loop, types
├── tools/                     # filesystem, pytest, planner/coder/tester/reviewer/architect
├── xr_ai_co/                  # CLI, config, LLM, context, harness, session builder, workspace git
├── schemas/task.v1.json       # JSON Schema for tasks (§2.5.1a)
├── tests/                     # unit tests (coverage gate in pyproject.toml)
├── xr_ai_co.yaml              # example configuration
├── main.py                    # thin entrypoint → CLI
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── CITATION.cff
└── README.md
```

Runtime artifacts `workspace/` and `state/` are gitignored (generated code and checkpoints).

---

## Testing & development

```bash
pip install -e .
pytest
```

Default `pytest` options enforce **≥90% line coverage** on `orchestrator/`, `xr_ai_co/`, and `tools/`. `main.py` and `xr_ai_co/cli.py` are **omitted** from the gate (thin / interactive entrypoints).

Quick run without coverage:

```bash
pytest --no-cov
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for PR expectations.

---

## Configuration

Copy or edit `xr_ai_co.yaml`. Highlights:

| Key | Default | Spec |
|-----|---------|------|
| `llm.provider` | `anthropic` | §14 |
| `llm.model` | `claude-sonnet-4-20250514` | §14 |
| `llm.llm_call_timeout_sec` | `120` | §17.1 |
| `budget.max_tokens_per_task` / `max_tokens_per_session` | `200000` / `2000000` | §17.2 |
| `budget.max_retries_total` | `50` | §17.2 |
| `policies.retry_policy.max_retries_per_task` | `5` | §4.1 |
| `policies.parallelism_policy.max_concurrent_code_tasks` | `2` | §2.2 |
| `clamp_code_tasks_to_host` | `false` | §2.2 |
| `pm.clarification_before_plan` | `false` | §2.5.6 |
| `planner.include_design_task` | `false` | §5.5 |
| `decision_log_max_entries` | `500` | §2.5.9 |

Environment overrides: `ANTHROPIC_API_KEY`, `XR_AI_CO_MODEL`, `XR_AI_CO_PROVIDER`.

---

## Architecture

```
CLI (§11) → Planner (§4.3) → CEO gate → Orchestrator loop (§7.1.1)
                                              ↓
                                    scheduling_dispatch_tick (§6.4.1)
                                              ↓
                                    HarnessExecutor (§6.3)
                                    ├── Coder (§5.2) — LLM or template
                                    ├── Tester (§5.3) — LLM or pytest
                                    └── Reviewer (§5.4) — LLM or stub
```

### Context injection (§6.5.2 / §6.5.3)

System prompt → **A: Global** → **B: Parent** → **C: Local** (+ workspace tree for coder/architect) → **D: Untrusted** (CEO mission).

| Role | Blocks |
|------|--------|
| Planner | A + B |
| Coder | A + B + C (+ workspace tree) |
| Tester | A + B + C |
| Reviewer | A + B + C |

### Failure routing (§4.4)

| `failure_type` | Routing |
|----------------|---------|
| `test_failure` | Reviewer → re-queue upstream code → re-run test |
| `syntax_error` | Reviewer → Coder retry |
| `requirement_mismatch` | Escalate → replan / CEO `modify_plan` |
| `infra_error` | Transient retry or escalate |

Bounded by `max_retries_per_task` and `max_retries_total` (§17.2).

### CEO escalation (§7.2)

On `blocked`: **modify_plan**, **continue** (reset failed), or **abort**. Executive report JSON on stdout for scripting.

### Workspace git (§9.2 / §9.3)

Optional `git init`, snapshot after green tests, `commit_sha` on tasks; optional rollback via `git_policy.rollback_on_code_failure`.

### Budget (§17.2)

Pre-schedule checks (`violates_budget_next_step`), post-call usage on session counters, per-task cap in the loop, optional USD heuristic when `max_cost_per_project` is set.

### Artifact lineage (§2.5.8)

`ToolResult.payload` carries `task_id`, `plan_revision_id`, `retry_count` where applicable.

---

## CLI reference

```
xr-ai-co run [OPTIONS] [MISSION...]
  --text TEXT          Mission as one string
  --config PATH        Path to xr_ai_co.yaml
  --workspace DIR      Workspace root (default: workspace)
  --state-dir DIR      Checkpoint directory (default: state)
  --session-id ID      Session basename (default: default)
  --revision REV       plan_revision_id (default: rev-001)
  -y, --yes            Auto-approve plan
  --clarify            §2.5.6 PM Q&A (interactive; not with -y)
  --blocked-interactive
                       CEO menu on blocked even with -y (or XR_AI_CO_BLOCKED_INTERACTIVE=1)
  --plan-only          Print JSON tasks and exit
  --max-ticks N        Orchestrator iteration cap (default: 512)
  -v, --verbose        Debug logging

xr-ai-co resume [OPTIONS]   # same session/workspace flags; --refresh-config; -y
xr-ai-co pause [OPTIONS]
xr-ai-co status [OPTIONS]   # add --json for machine-readable output
```

---

## Spec compliance

### MVO serial mode (§7.1 / §7.3)

One mutating **code or design** task at a time (both count toward `max_concurrent_code_tasks`). File locks use `path_hints` or `"."` when hints are absent (§9.4).

### PM clarification (§2.5.6)

Enable in YAML or `--clarify` for interactive runs without `-y`. With an API key, PM can emit short questions; without LLM, a single free-text prompt.

### DAG cycles (§6.4)

Invalid cyclic `depends_on` graphs are rejected before execution.

### Recently added depth (Mode 1)

Success-path code review gate, optional cost cap + USD heuristic, session wall-clock and pytest timeouts, design / architect path, PM module, SLA deadline floors, `status`, lane pressure in parent context, cross-run KB file—see previous detailed notes in git history or inline docstrings for § references.

### Deferred (§13 — explicit non-goals here)

- Terminal-agent coder (e.g. Claude Code / PTY)
- Multi-project CEO portfolio
- Distributed workers, web UI, RAG store
- Full PM product beyond §2.5.6
- Reward / payout channels outside `ToolResult` + `DecisionLog`

---

## Contributing & security

- **[CONTRIBUTING.md](./CONTRIBUTING.md)** — tests, PRs, style, and [issue templates](.github/ISSUE_TEMPLATE/).
- **[SECURITY.md](./SECURITY.md)** — responsible disclosure.
- **[CHANGELOG.md](./CHANGELOG.md)** — release notes.
- **[CITATION.cff](./CITATION.cff)** — citation metadata for papers / reports (update `repository-code` if your fork URL differs).

## License

[Apache License 2.0](./LICENSE)

---

## Demo

```bash
python main.py -y "build a rate limiter"
# → workspace/ gets ratelimit.py + tests/test_ratelimit.py
# → pytest runs; on success → project status: done
```
