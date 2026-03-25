"""Execution Tool — pytest via subprocess, cwd = workspace (§6.2.1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_pytest(
    workspace: Path,
    paths: list[str],
    extra_args: list[str] | None = None,
    timeout_sec: float | None = 120.0,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr)."""
    extra_args = extra_args or []
    cmd = [sys.executable, "-m", "pytest", *paths, *extra_args]
    proc = subprocess.run(
        cmd,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""
