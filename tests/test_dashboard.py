"""Tests for ADPSession per-message metrics (dashboard feature)."""
import json
import time
from pathlib import Path

import adp
from adp.session import ADPSession
from adp.cost import estimate_cost


def test_encode_records_history_entry():
    """After encode(), session.history has one entry with expected fields."""
    s = ADPSession(path=None, announce_caps=False)
    s.encode({"task": "hello", "value": 42})
    assert len(s.history) == 1
    entry = s.history[0]
    assert entry["direction"] == "encode"
    assert entry["tokens_adp"] > 0
    assert entry["tokens_json"] > 0
    assert entry["tokens_adp"] <= entry["tokens_json"]
    assert entry["bytes_adp"] > 0
    assert entry["bytes_json"] > 0
    assert entry["elapsed_ms"] >= 0
    assert "lut_entries" in entry
    assert "lut_hits" in entry
    assert "lut_misses" in entry
    assert isinstance(entry["used_diff"], bool)
    assert isinstance(entry["ts"], float)


def test_decode_records_history_entry():
    """After decode(), session.history has one entry for the decode."""
    s = ADPSession(path=None, announce_caps=False)
    msg = s.encode({"x": 1})
    s2 = ADPSession(path=None, announce_caps=False)
    s2.decode(msg)
    assert len(s2.history) == 1
    entry = s2.history[0]
    assert entry["direction"] == "decode"
    assert entry["tokens_adp"] > 0
    assert entry["elapsed_ms"] >= 0


def test_history_grows_with_messages():
    """Multiple encode/decode calls accumulate history entries."""
    s = ADPSession(path=None, announce_caps=False)
    for i in range(5):
        s.encode({"i": i})
    assert len(s.history) == 5


def test_diff_flag_in_history():
    """When diff encoding kicks in, used_diff is True."""
    s = ADPSession(path=None, announce_caps=False, enable_diff=True)
    s.encode({"task": "t1", "user": {"id": 42, "role": "administrator"}})
    s.encode({"task": "t2", "user": {"id": 42, "role": "administrator"}})
    assert s.history[0]["used_diff"] is False
    assert isinstance(s.history[1]["used_diff"], bool)


def test_history_persisted_and_loaded(tmp_path):
    """History survives save/load cycle."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.encode({"a": 1})
    s.encode({"b": 2})
    s.save()

    s2 = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    assert len(s2.history) == 2
    assert s2.history[0]["direction"] == "encode"


def test_history_in_stats():
    """stats() includes message_count."""
    s = ADPSession(path=None, announce_caps=False)
    s.encode({"x": 1})
    st = s.stats()
    assert st["message_count"] == 1
