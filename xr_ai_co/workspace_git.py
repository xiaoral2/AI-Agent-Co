"""§9.2 Workspace git — init / snapshot / rollback for workspace safety.

§9.3: commit only after green pytest when using git.
Provides lightweight revisioning under workspace/ without a remote.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _run_git(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


def git_init(workspace: Path) -> bool:
    """Initialize a git repo under workspace if not present. Returns True if init ran."""
    git_dir = workspace / ".git"
    if git_dir.is_dir():
        return False
    workspace.mkdir(parents=True, exist_ok=True)
    _run_git(workspace, "init")
    _run_git(workspace, "config", "user.email", "xr-ai-co@local")
    _run_git(workspace, "config", "user.name", "XR-AI-Co")
    _run_git(workspace, "add", ".")
    _run_git(workspace, "commit", "--allow-empty", "-m", "init: workspace created")
    log.info("git init completed in %s", workspace)
    return True


def snapshot(workspace: Path, message: str, task_id: str | None = None) -> str | None:
    """Stage all and commit; returns commit SHA or None if nothing to commit.

    §9.3: caller should only call this after green pytest.
    """
    _run_git(workspace, "add", "-A")
    status = _run_git(workspace, "status", "--porcelain")
    if not status.stdout.strip():
        return None

    tag = f"[task:{task_id}] " if task_id else ""
    _run_git(workspace, "commit", "-m", f"{tag}{message}")
    rev = _run_git(workspace, "rev-parse", "HEAD")
    sha = rev.stdout.strip()
    log.info("snapshot %s: %s%s", sha[:8], tag, message)
    return sha


def rollback(workspace: Path, sha: str) -> None:
    """Hard reset workspace to a prior commit (destructive)."""
    _run_git(workspace, "reset", "--hard", sha)
    log.info("rolled back workspace to %s", sha[:8])


def current_sha(workspace: Path) -> str | None:
    """Return HEAD SHA or None if not a git repo."""
    try:
        r = _run_git(workspace, "rev-parse", "HEAD", check=False)
        if r.returncode == 0:
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def log_short(workspace: Path, n: int = 10) -> list[str]:
    """Return last n one-line log entries."""
    try:
        r = _run_git(workspace, "log", f"--oneline", f"-{n}", check=False)
        if r.returncode == 0:
            return [line for line in r.stdout.strip().splitlines() if line]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []
