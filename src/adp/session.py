"""ADPSession — dynamic LUT adattiva HPACK-style.

Mantiene una LUT dinamica condivisa tra agenti, sincronizzata via prefissi
in-band nei messaggi ADP, persistita localmente.

Vedi spec: docs/superpowers/specs/2026-05-24-dynamic-lut-design.md
"""
from __future__ import annotations

import atexit
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

import adp


class ADPLUTSyncError(Exception):
    """Sollevata quando un alias dynamic LUT non è risolvibile."""

    def __init__(self, alias: str, message: str | None = None):
        self.alias = alias
        super().__init__(message or f"Alias dynamic LUT non risolvibile: {alias!r}")


DEFAULT_PATH = "~/.adp/lut_state.json"
SCHEMA_VERSION = 1


class ADPSession:
    """Sessione ADP con dynamic LUT adattiva.

    Mantiene una LUT in-memory persistita su disco. Encoder analizza payload,
    aggiunge alias per chiavi/valori string ricorrenti, dichiara updates via
    prefisso `_lut_add={...}` o `_lut_reset=1` nel messaggio.
    """

    def __init__(
        self,
        path: str | Path | None = DEFAULT_PATH,
        max_entries: int = 256,
        static_lut: dict[str, str] | None = None,
        k_threshold: int = 2,
        auto_save: bool = True,
    ) -> None:
        # Path resolution
        if path is None:
            self._path: Path | None = None  # in-memory only
        elif isinstance(path, str):
            override = os.environ.get("ADP_LUT_PATH")
            chosen = override if override else path
            self._path = Path(chosen).expanduser()
        else:
            self._path = Path(path).expanduser()

        self._max_entries = max_entries
        self._static_lut = static_lut or {}
        self._k_threshold = k_threshold
        self._auto_save = auto_save

        # Mutable state
        self._entries: dict[str, str] = {}       # alias -> fullname
        self._inv: dict[str, str] = {}           # fullname -> alias (cached)
        self._lru_order: list[str] = []          # least-recent first
        self._next_alias_id: int = 0
        self._stats = {
            "hit_count": 0,
            "miss_count": 0,
            "evictions": 0,
        }

        if self._path is not None and self._path.exists():
            self._load()

        if auto_save and self._path is not None:
            atexit.register(self._atexit_save)

    def _load(self) -> None:
        assert self._path is not None
        with self._path.open("r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        version = data.get("version", 1)
        if version != SCHEMA_VERSION:
            # Backup vecchio e ripartiti vuoto
            backup = self._path.with_suffix(self._path.suffix + ".bak")
            self._path.rename(backup)
            return

        self._entries = dict(data.get("entries", {}))
        self._lru_order = list(data.get("lru_order", []))
        self._next_alias_id = int(data.get("next_alias_id", 0))
        self._stats.update(data.get("stats", {}))
        self._inv = {v: k for k, v in self._entries.items()}

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": SCHEMA_VERSION,
            "entries": dict(self._entries),
            "lru_order": list(self._lru_order),
            "next_alias_id": self._next_alias_id,
            "stats": dict(self._stats),
        }
        # Atomic write: temp + rename in stessa directory
        fd, tmp_path_str = tempfile.mkstemp(
            prefix=".lut_", suffix=".json.tmp", dir=str(self._path.parent)
        )
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(tmp_path, self._path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _atexit_save(self) -> None:
        try:
            self.save()
        except Exception:
            pass  # atexit: mai sollevare


__all__ = ["ADPSession", "ADPLUTSyncError", "DEFAULT_PATH", "SCHEMA_VERSION",
           "apply_lut_updates", "encode_with_dyn_lut"]
