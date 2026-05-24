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

    def _add_entry(self, fullname: str) -> str:
        """Aggiungi nuovo entry alla LUT dinamica. Ritorna alias assegnato.

        Se LUT piena: evict LRU front prima.
        Se fullname già presente: ritorna alias esistente e lo bumpa.
        """
        if fullname in self._inv:
            existing = self._inv[fullname]
            self._mark_used(existing)
            return existing

        if len(self._entries) >= self._max_entries:
            self._evict_lru()

        alias = f"_{self._next_alias_id}"
        self._next_alias_id += 1
        self._entries[alias] = fullname
        self._inv[fullname] = alias
        self._lru_order.append(alias)
        return alias

    def _mark_used(self, alias: str) -> str:
        """Bumpa alias a most-recently-used. Ritorna alias (per chaining)."""
        if alias in self._lru_order:
            self._lru_order.remove(alias)
            self._lru_order.append(alias)
        return alias

    def _evict_lru(self) -> str | None:
        """Rimuovi l'entry meno recente. Ritorna alias rimosso o None se LUT vuota."""
        if not self._lru_order:
            return None
        alias = self._lru_order.pop(0)
        fullname = self._entries.pop(alias, None)
        if fullname is not None:
            self._inv.pop(fullname, None)
        self._stats["evictions"] += 1
        return alias

    def _count_candidates(self, obj: Any, counts: dict[str, int] | None = None) -> dict[str, int]:
        """Conta occorrenze di chiavi dict e valori string scalari, ricorsivamente."""
        if counts is None:
            counts = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str):
                    counts[k] = counts.get(k, 0) + 1
                self._count_candidates(v, counts)
        elif isinstance(obj, list):
            for v in obj:
                self._count_candidates(v, counts)
        elif isinstance(obj, str):
            counts[obj] = counts.get(obj, 0) + 1
        # bool/int/float/None/bytes: ignorati
        return counts

    def _select_candidates(self, counts: dict[str, int]) -> dict[str, int]:
        """Filtra candidati: soglia K, non in static LUT, saving char non-negativo (break-even incluso)."""
        selected: dict[str, int] = {}
        next_id = self._next_alias_id
        for fullname, count in counts.items():
            if count < self._k_threshold:
                continue
            if fullname in self._static_lut:
                continue
            if fullname in self._inv:
                # Già in dynamic LUT: non re-aggiungere, ma il caller può bumpare LRU
                continue
            # Cost-benefit char-based
            alias_len = len(f"_{next_id}")
            header_entry_len = alias_len + 1 + len(fullname) + 1  # "_N=fullname;"
            saving = count * len(fullname) - count * alias_len - header_entry_len
            if saving >= 0:
                selected[fullname] = count
                next_id += 1  # simula incremento per stima alias futuri (approx)
        return selected

    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj a stringa ADP. Se no_lut=True bypassa dynamic LUT."""
        if no_lut:
            if self._static_lut:
                return adp.encode(obj, key_lut=self._static_lut)
            return adp.encode(obj)

        # 1. Conta candidati
        counts = self._count_candidates(obj)

        # 2. Bumpa LRU per quelli già in dynamic LUT
        for fullname in counts:
            if fullname in self._inv:
                self._mark_used(self._inv[fullname])

        # 3. Seleziona nuovi candidati
        new_candidates = self._select_candidates(counts)

        # 4. Aggiungi entry per ognuno
        new_aliases: dict[str, str] = {}  # alias -> fullname (per il prefix)
        for fullname in new_candidates:
            alias = self._add_entry(fullname)
            new_aliases[alias] = fullname

        # 5. Sostituisci nel payload (chiavi+valori string ricorrenti) usando
        #    static LUT + dynamic LUT
        substituted = self._substitute(obj)

        # 6. Compone messaggio finale
        payload_adp = adp.encode(substituted, key_lut=self._static_lut or None)
        if not new_aliases:
            return payload_adp

        # Prefix: _lut_add={alias=fullname;...};payload
        prefix_pairs = ";".join(f"{a}={self._quote_if_needed(f)}"
                                for a, f in new_aliases.items())
        prefix = f"_lut_add={{{prefix_pairs}}};"
        return prefix + payload_adp

    def _substitute(self, obj: Any) -> Any:
        """Ricorsivamente sostituisci chiavi e valori string usando dynamic LUT."""
        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                new_k = self._inv.get(k, k) if isinstance(k, str) else k
                out[new_k] = self._substitute(v)
            return out
        if isinstance(obj, list):
            return [self._substitute(v) for v in obj]
        if isinstance(obj, str):
            return self._inv.get(obj, obj)
        return obj

    @staticmethod
    def _quote_if_needed(s: str) -> str:
        """Quote un valore se contiene caratteri ADP-speciali."""
        if not s:
            return '""'
        if re.search(r"[\s,;=\[\]\{\}|\"#&~]", s):
            escaped = s.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return s


__all__ = ["ADPSession", "ADPLUTSyncError", "DEFAULT_PATH", "SCHEMA_VERSION",
           "apply_lut_updates", "encode_with_dyn_lut"]
