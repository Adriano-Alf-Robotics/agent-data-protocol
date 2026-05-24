"""Test suite per ADPSession (dynamic LUT core)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from adp.session import ADPSession, ADPLUTSyncError


def test_import_smoke():
    """Import OK, classi disponibili."""
    assert ADPSession is not None
    assert ADPLUTSyncError is not None


def test_lut_sync_error_carries_alias():
    err = ADPLUTSyncError("_42")
    assert err.alias == "_42"
    assert "_42" in str(err)


def test_persistence_save_creates_file(tmp_path: Path):
    session_path = tmp_path / "lut.json"
    session = ADPSession(path=session_path, auto_save=False)
    session.save()
    assert session_path.exists()
    data = json.loads(session_path.read_text())
    assert data["version"] == 1
    assert data["entries"] == {}
    assert data["lru_order"] == []
    assert data["next_alias_id"] == 0


def test_persistence_roundtrip(tmp_path: Path):
    session_path = tmp_path / "lut.json"
    s1 = ADPSession(path=session_path, auto_save=False)
    s1._entries = {"_0": "admin", "_1": "dev"}
    s1._lru_order = ["_0", "_1"]
    s1._next_alias_id = 2
    s1.save()

    s2 = ADPSession(path=session_path, auto_save=False)
    assert s2._entries == {"_0": "admin", "_1": "dev"}
    assert s2._lru_order == ["_0", "_1"]
    assert s2._next_alias_id == 2


def test_persistence_missing_file_starts_empty(tmp_path: Path):
    session_path = tmp_path / "doesnotexist.json"
    s = ADPSession(path=session_path, auto_save=False)
    assert s._entries == {}
    assert s._lru_order == []
    assert s._next_alias_id == 0


def test_persistence_atomic_write_uses_temp_file(tmp_path: Path):
    """Verifica che save() usi temp file + rename."""
    session_path = tmp_path / "lut.json"
    s = ADPSession(path=session_path, auto_save=False)
    s._entries = {"_0": "x"}
    s.save()
    # Nessun file temp residuo
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_lru_add_entry_increments_alias_id():
    s = ADPSession(path=None, auto_save=False)
    alias = s._add_entry("admin")
    assert alias == "_0"
    assert s._entries == {"_0": "admin"}
    assert s._lru_order == ["_0"]
    assert s._next_alias_id == 1


def test_lru_add_existing_returns_same_alias_and_bumps():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")
    s._add_entry("dev")
    # Re-using "admin" deve restituire stesso alias e bumpare in LRU
    alias = s._mark_used("_0")
    assert alias == "_0"
    assert s._lru_order == ["_1", "_0"]


def test_lru_eviction_when_full(tmp_path):
    s = ADPSession(path=None, max_entries=3, auto_save=False)
    s._add_entry("a")
    s._add_entry("b")
    s._add_entry("c")
    assert len(s._entries) == 3
    s._add_entry("d")
    # "a" era il meno recente, dovrebbe essere evicted
    assert "_0" not in s._entries  # _0 era "a"
    assert s._entries == {"_1": "b", "_2": "c", "_3": "d"}
    assert s._lru_order == ["_1", "_2", "_3"]
    assert s._stats["evictions"] == 1


def test_lru_use_existing_then_eviction_keeps_used():
    s = ADPSession(path=None, max_entries=3, auto_save=False)
    s._add_entry("a")  # _0
    s._add_entry("b")  # _1
    s._add_entry("c")  # _2
    s._mark_used("_0")  # promote _0 a most-recent
    s._add_entry("d")   # _3, evict _1 (meno recente)
    assert "_1" not in s._entries
    assert s._entries == {"_0": "a", "_2": "c", "_3": "d"}
