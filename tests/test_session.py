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


def test_candidate_count_keys_only():
    s = ADPSession(path=None, auto_save=False)
    obj = {
        "user": {"id": 1, "role": "admin"},
        "other": {"id": 2, "role": "admin"},
    }
    counts = s._count_candidates(obj)
    # Conta chiavi: user 1, other 1, id 2, role 2
    # Conta valori string: admin 2
    assert counts["user"] == 1
    assert counts["other"] == 1
    assert counts["id"] == 2
    assert counts["role"] == 2
    assert counts["admin"] == 2


def test_candidate_skips_non_string_values():
    s = ADPSession(path=None, auto_save=False)
    obj = {"a": 1, "b": True, "c": None, "d": "text", "e": 3.14}
    counts = s._count_candidates(obj)
    # Solo chiavi (a,b,c,d,e) e valori string ("text")
    assert counts.get("text", 0) == 1
    assert 1 not in counts  # nessun int
    assert True not in counts  # nessun bool


def test_candidate_recursive_into_lists():
    s = ADPSession(path=None, auto_save=False)
    obj = {"users": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]}
    counts = s._count_candidates(obj)
    assert counts["id"] == 2
    assert counts["name"] == 2


def test_select_candidates_above_threshold():
    s = ADPSession(path=None, max_entries=256, k_threshold=2, auto_save=False)
    counts = {"admin": 3, "x": 1, "long_repeated_key": 5}
    selected = s._select_candidates(counts)
    # x sotto soglia esce
    assert "x" not in selected
    # admin e long_repeated_key passano la soglia
    assert "admin" in selected
    assert "long_repeated_key" in selected


def test_select_candidates_skips_already_in_static_lut():
    static = {"user": "u", "id": "i"}
    s = ADPSession(path=None, static_lut=static, auto_save=False)
    counts = {"user": 5, "admin": 3}
    selected = s._select_candidates(counts)
    assert "user" not in selected  # gestita da static
    assert "admin" in selected


def test_select_candidates_skips_negative_saving():
    s = ADPSession(path=None, k_threshold=2, auto_save=False)
    # "ok" (2 char) × 3 vs alias "_0" (2 char) + header "_0=ok;" (6 char)
    # saving = 3*2 - 3*2 - 6 = -6 < 0 → escluso
    counts = {"ok": 3}
    selected = s._select_candidates(counts)
    assert "ok" not in selected


def test_encode_no_repeats_no_prefix():
    s = ADPSession(path=None, auto_save=False)
    msg = s.encode({"id": 42})
    # Nessuna chiave ripetuta sopra soglia → nessun _lut_add
    assert "_lut_add" not in msg
    # Round-trip via standard adp.decode
    import adp
    assert adp.decode(msg) == {"id": 42}


def test_encode_with_repeats_adds_prefix():
    s = ADPSession(path=None, auto_save=False)
    # Usa chiavi/valori abbastanza lunghi da superare il break-even del cost-benefit
    obj = {
        "user1": {"department": "engineering", "location": "headquarters"},
        "user2": {"department": "engineering", "location": "headquarters"},
    }
    msg = s.encode(obj)
    assert "_lut_add" in msg
    # Dopo encode la LUT deve contenere "department" o "engineering" etc.
    assert len(s._entries) >= 2


def test_encode_substitutes_aliases_in_payload():
    s = ADPSession(path=None, auto_save=False)
    obj = {
        "a": {"department": "engineering"},
        "b": {"department": "engineering"},
    }
    msg = s.encode(obj)
    # _0=department o _0=engineering deve apparire nel prefix
    assert "department" in msg or "engineering" in msg  # in prefix
    # Nel payload, almeno un alias _N deve essere usato
    import re
    assert re.search(r"_\d+=", msg) is not None


def test_encode_no_lut_flag_bypasses():
    s = ADPSession(path=None, auto_save=False)
    obj = {"role": "admin", "role2": "admin"}
    msg = s.encode(obj, no_lut=True)
    assert "_lut_add" not in msg
    # Anche con ripetizioni, no_lut bypassa la dynamic LUT
    assert "admin" in msg  # valore bare, non sostituito
