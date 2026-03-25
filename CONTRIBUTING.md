# Contributing to XR-AI-Co

Thanks for helping improve this project.

## Before you start

- Put the canonical product spec under `design_notes/` locally (that directory is gitignored). The README describes behavior that tracks `ai-company-spec.md` **Mode 1** when present.
- Run the test suite before opening a PR:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -e .
  pytest
  ```

  `pytest` is configured with a **≥90% line coverage** gate on `orchestrator/`, `xr_ai_co/`, and `tools/` (see `pyproject.toml`). Use `pytest --no-cov` only for quick local iteration.

## Issues

Use the [**Bug report** or **Feature request** templates](.github/ISSUE_TEMPLATE/) when you open an issue on GitHub (structured forms with required fields). **Security vulnerabilities** must not be filed as public issues — see [SECURITY.md](./SECURITY.md).

## Pull requests

1. **One topic per PR** — easier to review and bisect.
2. **Describe the change** — what problem it solves and any spec section (§…) it aligns with.
3. **Keep diffs focused** — avoid drive-by formatting or unrelated refactors.
4. **Add or update tests** when you change behavior that is unit-testable.

## Code style

- Match surrounding modules (imports, typing, logging).
- Prefer small, readable functions over clever one-liners.
- Do not commit secrets (API keys, `.env`); use environment variables or local config only.

## CI

GitHub Actions runs `pytest` on Python 3.11–3.13 for pushes and PRs to `main` / `master` (see `.github/workflows/ci.yml`). If the workflow badge in the README shows “no workflow”, update the badge URL to your `owner/repository` path.
