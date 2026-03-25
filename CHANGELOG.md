# Changelog

All notable changes to this project are documented here. The format is loosely inspired by [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- GitHub Issue forms: bug report and feature request (`.github/ISSUE_TEMPLATE/`).

## [0.1.0] — 2026-03-24

### Added

- Spec-driven **Mode 1** harness: DAG tasks, checkpoints, CEO gate, planner / coder / tester / reviewer / architect tools.
- CLI: `run`, `resume`, `pause`, `status` (`xr-ai-co` and `python main.py` entrypoints).
- Orchestrator loop with failure taxonomy, optional workspace git snapshot / rollback, budget and SLA-aware scheduling.
- JSON Schema for tasks (`schemas/task.v1.json`) and pytest suite with ≥90% line coverage on core packages (see `pyproject.toml`).
- GitHub Actions CI for Python 3.11–3.13.
