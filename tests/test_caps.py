"""Test suite per capability negotiation (Est. 2)."""
from __future__ import annotations

import pytest

from adp.session import ADPSession


def test_session_default_caps_params():
    s = ADPSession(path=None, auto_save=False)
    assert s._announce_caps is True
    assert s._caps_timeout_msgs == 3


def test_session_caps_params_configurable():
    s = ADPSession(path=None, auto_save=False,
                   announce_caps=False, caps_timeout_msgs=5)
    assert s._announce_caps is False
    assert s._caps_timeout_msgs == 5


def test_session_peer_caps_initially_none():
    s = ADPSession(path=None, auto_save=False)
    assert s.peer_caps is None


def test_session_reset_caps_clears_state():
    s = ADPSession(path=None, auto_save=False)
    s._peer_caps = {"dyn_lut": 1, "max_entries": 256}
    s._caps_announced = True
    s._caps_outbound_count = 5
    s.reset_caps()
    assert s.peer_caps is None
    assert s._caps_announced is False
    assert s._caps_outbound_count == 0


def test_encode_first_message_includes_caps_prefix():
    """Primo encode include _caps={dyn_lut=1;max_entries=256;diff=1} prefix."""
    s = ADPSession(path=None, auto_save=False, announce_caps=True)
    msg = s.encode({"a": 1})
    assert "_caps={" in msg
    assert "dyn_lut=1" in msg
    assert "max_entries=256" in msg
    assert "diff=1" in msg
    # Stato aggiornato
    assert s._caps_announced is True


def test_encode_subsequent_messages_no_caps_prefix():
    """Solo il primo msg include _caps. Successivi no."""
    s = ADPSession(path=None, auto_save=False, announce_caps=True)
    s.encode({"a": 1})  # primo: include caps
    msg2 = s.encode({"b": 2})
    assert "_caps=" not in msg2


def test_encode_announce_caps_false_skips_prefix():
    """announce_caps=False non emette mai caps."""
    s = ADPSession(path=None, auto_save=False, announce_caps=False)
    msg = s.encode({"a": 1})
    assert "_caps=" not in msg
    assert s._caps_announced is False
