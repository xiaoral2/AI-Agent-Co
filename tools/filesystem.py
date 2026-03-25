"""read_file / write_file — paths confined under workspace root (§9)."""

from __future__ import annotations

from pathlib import Path


class PathEscapeError(ValueError):
    pass


def _resolve_under_workspace(workspace: Path, rel: str) -> Path:
    root = workspace.resolve()
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        raise PathEscapeError(f"path escapes workspace: {rel!r}")
    return target


def read_file(workspace: Path, rel_path: str, encoding: str = "utf-8") -> str:
    p = _resolve_under_workspace(workspace, rel_path)
    if not p.is_file():
        raise FileNotFoundError(rel_path)
    return p.read_text(encoding=encoding)


def write_file(workspace: Path, rel_path: str, content: str, encoding: str = "utf-8") -> None:
    p = _resolve_under_workspace(workspace, rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)
