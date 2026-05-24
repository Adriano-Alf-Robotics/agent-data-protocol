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
