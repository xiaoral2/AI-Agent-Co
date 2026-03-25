"""Execution Tool — pytest via subprocess, cwd = workspace (§6.2.1)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_pytest(
    workspace: Path,
    paths: list[str],
    extra_args: list[str] | None = None,
    timeout_sec: float | None = 120.0,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr).

    Workspace runs often live under a harness repo checkout; pytest walks upward
    and would otherwise inherit the parent's ``pyproject.toml`` ``addopts`` (e.g.
    ``--cov=orchestrator``), yielding 0%% coverage and spurious failures. We
    strip inherited ``addopts`` and disable coverage for subprocess runs.
    """
    extra_args = extra_args or []
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--override-ini",
        "addopts=",
        "--no-cov",
        *paths,
        *extra_args,
    ]
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    proc = subprocess.run(
        cmd,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        env=env,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""
