"""Persistent runtime memory with safe JSON read/write."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_MEM_PATH = Path(__file__).resolve().parent / "runtime_memory.json"
_TMP_PATH = _MEM_PATH.with_suffix(".json.tmp")
_BAK_PATH = _MEM_PATH.with_suffix(".json.bak")
_SCHEMA_VERSION = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_memory() -> dict[str, Any]:
    return {
        "meta": {
            "version": _SCHEMA_VERSION,
            "updated_at": _now_iso(),
        },
        "intent_rules": [],
        "intent_candidates": [],
        "summary_patterns": {},
    }


def load_memory() -> dict[str, Any]:
    with _LOCK:
        if not _MEM_PATH.exists():
            return _default_memory()
        try:
            data = json.loads(_MEM_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return _default_memory()
            merged = _default_memory()
            merged.update(data)
            merged["meta"]["version"] = _SCHEMA_VERSION
            return merged
        except Exception:
            try:
                os.replace(_MEM_PATH, _BAK_PATH)
            except Exception:
                pass
            return _default_memory()


def save_memory(memory: dict[str, Any]) -> None:
    with _LOCK:
        memory.setdefault("meta", {})
        memory["meta"]["version"] = _SCHEMA_VERSION
        memory["meta"]["updated_at"] = _now_iso()
        payload = json.dumps(memory, ensure_ascii=True, indent=2)
        _TMP_PATH.write_text(payload, encoding="utf-8")
        os.replace(_TMP_PATH, _MEM_PATH)


def now_iso() -> str:
    return _now_iso()
