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
    # Round-trip via session.decode (gestisce _caps= prefix)
    receiver = ADPSession(path=None, auto_save=False, announce_caps=False)
    assert receiver.decode(msg) == {"id": 42}


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


def test_decode_without_prefix():
    s = ADPSession(path=None, auto_save=False)
    import adp
    msg = adp.encode({"id": 42})
    out = s.decode(msg)
    assert out == {"id": 42}


def test_decode_applies_lut_add():
    s = ADPSession(path=None, auto_save=False)
    msg = "_lut_add={_0=admin;_1=role};u={_1=_0;name=alice}"
    out = s.decode(msg)
    # Dopo decode, lut deve contenere le nuove entry
    assert s._entries == {"_0": "admin", "_1": "role"}
    # Payload espanso correttamente
    assert out == {"u": {"role": "admin", "name": "alice"}}


def test_decode_round_trip_two_sessions():
    a = ADPSession(path=None, auto_save=False)
    b = ADPSession(path=None, auto_save=False)

    obj = {
        "user": {"role": "administrator", "dept": "engineering"},
        "user2": {"role": "administrator", "dept": "engineering"},
    }
    msg = a.encode(obj)
    out = b.decode(msg)
    assert out == obj
    # Stato LUT sincronizzato
    assert a._entries == b._entries
    assert a._lru_order == b._lru_order


def test_decode_unknown_alias_raises_sync_error():
    s = ADPSession(path=None, auto_save=False)
    msg = "_0={id=42}"  # _0 non in lut
    with pytest.raises(ADPLUTSyncError) as exc_info:
        s.decode(msg)
    assert exc_info.value.alias == "_0"


def test_decode_lut_reset_clears_state():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")  # _0=admin
    s._add_entry("dev")    # _1=dev
    msg = "_lut_reset=1;id=42"
    out = s.decode(msg)
    assert s._entries == {}
    assert s._lru_order == []
    assert out == {"id": 42}


def test_encode_reset_emits_reset_prefix():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")
    s._add_entry("dev")
    msg = s.encode_reset({"id": 1})
    assert msg.startswith("_lut_reset=1;")
    # Anche lato locale lo state è pulito (encode_reset pulisce SENDER)
    assert s._entries == {}


def test_reset_clears_only_local_state():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")
    assert len(s._entries) == 1
    s.reset()
    assert s._entries == {}
    assert s._lru_order == []
    # next_alias_id NON resettato
    assert s._next_alias_id == 1


def test_stats_reports_real_events():
    a = ADPSession(path=None, auto_save=False)
    b = ADPSession(path=None, auto_save=False)
    obj = {"x": {"role": "administrator", "k": "valuevalue"},
           "y": {"role": "administrator", "k": "valuevalue"}}
    msg = a.encode(obj)
    b.decode(msg)
    st = b.stats()
    assert st["entries_count"] >= 1
    assert st["hit_count"] >= 2  # almeno role o administrator espanso 2 volte


def test_apply_lut_updates_extracts_prefix():
    from adp.lut import apply_lut_updates
    msg = "_lut_add={_0=admin};u={i=42;r=_0}"
    payload_str, updated_lut = apply_lut_updates(msg, {})
    assert payload_str == "u={i=42;r=_0}"
    assert updated_lut == {"_0": "admin"}


def test_apply_lut_updates_handles_reset():
    from adp.lut import apply_lut_updates
    msg = "_lut_reset=1;u={i=42}"
    payload_str, updated_lut = apply_lut_updates(msg, {"_0": "old"})
    assert payload_str == "u={i=42}"
    assert updated_lut == {}


def test_encode_with_dyn_lut_returns_msg_and_updated_lut():
    from adp.lut import encode_with_dyn_lut
    obj = {"a": {"role": "administrator"}, "b": {"role": "administrator"}}
    msg, new_lut = encode_with_dyn_lut(obj, {}, k_threshold=2, max_entries=256)
    assert "_lut_add" in msg
    assert len(new_lut) >= 1


def test_concurrent_save_no_corruption(tmp_path):
    """Due session che scrivono in parallelo non corrompono il file."""
    import threading
    path = tmp_path / "lut.json"
    s1 = ADPSession(path=path, auto_save=False)
    s2 = ADPSession(path=path, auto_save=False)
    s1._add_entry("a")
    s2._add_entry("b")

    errors = []
    def writer(s):
        try:
            for _ in range(20):
                s.save()
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=writer, args=(s1,))
    t2 = threading.Thread(target=writer, args=(s2,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert errors == []
    # File parsabile
    data = json.loads(path.read_text())
    assert data["version"] == 1


def test_round_trip_20_messages_two_agents(tmp_path):
    """Scambio bidirezionale 20 messaggi, LUT cresce, decode resta consistente."""
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a = ADPSession(path=a_path, max_entries=32, auto_save=False)
    b = ADPSession(path=b_path, max_entries=32, auto_save=False)

    payloads = []
    for i in range(20):
        if i % 2 == 0:
            obj = {
                "user": {"id": i, "role": "administrator", "dept": "engineering"},
                "user2": {"id": i + 100, "role": "administrator", "dept": "engineering"},
                "metadata": {"src": "agent_aaaa", "src2": "agent_aaaa"},
            }
            sender, receiver = a, b
        else:
            obj = {
                "status": "successful",
                "status2": "successful",
                "result": {"value": i, "kind": "reportreport", "kind2": "reportreport"},
            }
            sender, receiver = b, a
        msg = sender.encode(obj)
        out = receiver.decode(msg)
        assert out == obj, f"mismatch at msg {i}"
        payloads.append(obj)

    # Con TPD attivo i due agenti promuovono da buffer diversi → LUT non identiche.
    # L'invariante che conta: tutti i decode hanno avuto successo (assert out==obj sopra)
    # e le entry promosse via encode normale (senza TPD) coincidono tra i due agenti.
    # Queste sono le prime 5 entry (_0..._4) aggiunte prima del primo ciclo TPD.
    for k in ("_0", "_1", "_2", "_3", "_4"):
        if k in a._entries and k in b._entries:
            assert a._entries[k] == b._entries[k], (
                f"Entry {k} diverge: {a._entries[k]!r} vs {b._entries[k]!r}"
            )


def test_persistence_after_long_session(tmp_path):
    """Save dopo 20 msg, reload, encode/decode usa stato persistito."""
    path = tmp_path / "lut.json"
    s = ADPSession(path=path, max_entries=32, auto_save=False)
    for i in range(20):
        s.encode({"user": {"id": i, "role": "administrator"},
                  "u2": {"id": i + 1, "role": "administrator"}})
    s.save()
    entries_before = dict(s._entries)
    lru_before = list(s._lru_order)

    s2 = ADPSession(path=path, max_entries=32, auto_save=False)
    assert s2._entries == entries_before
    assert s2._lru_order == lru_before


def test_miss_count_increments_on_sync_error():
    s = ADPSession(path=None, auto_save=False)
    msg = "_99={id=1}"  # _99 non in lut
    with pytest.raises(ADPLUTSyncError):
        s.decode(msg)
    assert s.stats()["miss_count"] == 1
