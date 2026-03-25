"""§2.5.5 — persist `global.knowledge_base` across runs (best-effort JSON file)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KB_FILENAME = "knowledge_base.json"
KB_CAP = 500


def _key(item: Any) -> str:
    if isinstance(item, dict):
        return json.dumps(item, sort_keys=True, ensure_ascii=False)
    return str(item)


def load_kb_into_session(session: dict[str, Any], state_dir: Path) -> None:
    p = state_dir / KB_FILENAME
    if not p.is_file():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, list):
        return
    g = session.setdefault("global", {})
    kb = g.setdefault("knowledge_base", [])
    if not isinstance(kb, list):
        g["knowledge_base"] = list(data[-200:])
        return
    seen = {_key(x) for x in kb}
    for item in data[-200:]:
        k = _key(item)
        if k not in seen:
            kb.append(item)
            seen.add(k)


def persist_kb_from_session(session: dict[str, Any], state_dir: Path) -> None:
    g = session.get("global") or {}
    kb = g.get("knowledge_base")
    if not isinstance(kb, list) or not kb:
        return
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / KB_FILENAME
    existing: list[Any] = []
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = raw
        except (json.JSONDecodeError, OSError):
            pass
    seen = {_key(x) for x in existing}
    for item in kb:
        k = _key(item)
        if k not in seen:
            existing.append(item)
            seen.add(k)
    p.write_text(json.dumps(existing[-KB_CAP:], indent=2, ensure_ascii=False), encoding="utf-8")
