"""Tests for LUT (Look-Up Table) support."""

from __future__ import annotations

import pytest

from adp import encode, decode, DEFAULT_AGENT_LUT, validate_lut


def test_simple_lut_roundtrip() -> None:
    lut = {"user": "u", "id": "i", "name": "n"}
    obj = {"user": {"id": 42, "name": "Adriano"}}
    s = encode(obj, key_lut=lut)
    assert s == "u={i=42;n=Adriano}"
    back = decode(s, key_lut=lut)
    assert back == obj


def test_lut_in_nested_table() -> None:
    lut = {"id": "i", "name": "n", "active": "a"}
    obj = {"users": [
        {"id": 1, "name": "alice", "active": True},
        {"id": 2, "name": "bob",   "active": False},
    ]}
    s = encode(obj, key_lut=lut)
    assert "#i,n,a|" in s
    assert decode(s, key_lut=lut) == obj


def test_lut_partial_mapping() -> None:
    """Keys not in LUT pass through unchanged."""
    lut = {"id": "i"}
    obj = {"item": {"id": 1, "weight": 2.5}}
    s = encode(obj, key_lut=lut)
    assert "i=1" in s
    assert "weight=2.5" in s
    assert decode(s, key_lut=lut) == obj


def test_default_agent_lut() -> None:
    """The packaged DEFAULT_AGENT_LUT must round-trip and shorten common fields."""
    validate_lut(DEFAULT_AGENT_LUT)
    obj = {
        "msg_id": "m_1",
        "from_agent": "planner",
        "to_agent": "executor",
        "intent": "execute_step",
        "payload": {"id": 1, "value": 42, "active": True},
    }
    s_no_lut = encode(obj)
    s_with_lut = encode(obj, key_lut=DEFAULT_AGENT_LUT)
    assert len(s_with_lut) < len(s_no_lut), (
        f"LUT should shorten: {len(s_no_lut)} -> {len(s_with_lut)}\n"
        f"no_lut={s_no_lut}\nwith_lut={s_with_lut}"
    )
    assert decode(s_with_lut, key_lut=DEFAULT_AGENT_LUT) == obj


def test_lut_invalid_alias_collides_with_reserved() -> None:
    with pytest.raises(ValueError):
        validate_lut({"some_field": "0i"})


def test_lut_invalid_alias_not_identifier() -> None:
    with pytest.raises(ValueError):
        validate_lut({"x": "has space"})


def test_lut_duplicate_alias() -> None:
    with pytest.raises(ValueError):
        validate_lut({"a": "x", "b": "x"})


def test_default_agent_lut_no_common_word_aliases():
    """Guard: nessun alias in DEFAULT_AGENT_LUT può essere una parola inglese
    standalone comune di 1-3 lettere (evita collision silenziosa con chiavi utente)."""
    from adp.lut import DEFAULT_AGENT_LUT
    forbidden = {"to", "in", "of", "at", "on", "by", "is", "as", "an",
                 "the", "and", "or", "for", "key", "id", "if", "no", "ok",
                 "be", "we", "us", "do", "go", "it", "me", "my"}
    for fullname, alias in DEFAULT_AGENT_LUT.items():
        assert alias not in forbidden, (
            f"Alias {alias!r} (for {fullname!r}) è una parola inglese "
            f"comune: rischio collision silenziosa con chiavi utente"
        )


def test_lut_savings_on_realistic_payload() -> None:
    """Encode a realistic agent payload with and without LUT, compare lengths."""
    obj = {
        "msg_id": "m_42",
        "from_agent": "router",
        "to_agent": "worker",
        "intent": "process",
        "payload": {
            "items": [
                {"id": 1, "name": "x", "value": 10, "status": "ok"},
                {"id": 2, "name": "y", "value": 20, "status": "ok"},
                {"id": 3, "name": "z", "value": 30, "status": "warn"},
            ]
        },
    }
    a = encode(obj)
    b = encode(obj, key_lut=DEFAULT_AGENT_LUT)
    saving = (len(a) - len(b)) / len(a) * 100
    assert saving > 15, f"expected >15% byte saving with LUT, got {saving:.1f}%"
