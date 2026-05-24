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


def test_decode_extracts_caps_and_populates_peer_caps():
    """Receiver decode msg con _caps=, popola peer_caps."""
    sender = ADPSession(path=None, auto_save=False, announce_caps=True)
    receiver = ADPSession(path=None, auto_save=False, announce_caps=False)
    msg = sender.encode({"a": 1})
    out = receiver.decode(msg)
    assert out == {"a": 1}  # payload decodificato correttamente
    assert receiver.peer_caps is not None
    assert receiver.peer_caps.get("dyn_lut") == 1
    assert receiver.peer_caps.get("max_entries") == 256


def test_decode_caps_idempotent_subsequent_msgs():
    """Decoded msg senza _caps non altera peer_caps esistente."""
    sender = ADPSession(path=None, auto_save=False, announce_caps=True)
    receiver = ADPSession(path=None, auto_save=False, announce_caps=False)
    receiver.decode(sender.encode({"a": 1}))
    caps_before = dict(receiver.peer_caps)
    receiver.decode(sender.encode({"b": 2}))
    assert receiver.peer_caps == caps_before


def test_encode_auto_degrade_after_timeout():
    """Dopo `caps_timeout_msgs` send senza vedere peer_caps, sender
    automaticamente disabilita dyn LUT (passa a no_lut)."""
    s = ADPSession(path=None, auto_save=False,
                   announce_caps=True, caps_timeout_msgs=3)
    # Send 4 msg senza mai ricevere caps di ritorno
    s.encode({"role": "administrator", "role2": "administrator"})  # send #1
    s.encode({"role": "administrator", "role2": "administrator"})  # send #2
    s.encode({"role": "administrator", "role2": "administrator"})  # send #3
    msg4 = s.encode({"role": "administrator", "role2": "administrator"})
    # Al 4° messaggio (counter > timeout), encoder dovrebbe aver
    # automaticamente disabilitato dyn LUT
    # Indicatore: nessun _lut_add nel msg4
    assert "_lut_add" not in msg4


def test_encode_no_degrade_if_peer_caps_received():
    """Se peer_caps è popolato, no auto-degrade."""
    s = ADPSession(path=None, auto_save=False,
                   announce_caps=True, caps_timeout_msgs=2)
    # Simula peer caps ricevuto
    s._peer_caps = {"dyn_lut": 1, "max_entries": 256, "diff": 1}
    # Send 5 msg
    for _ in range(5):
        s.encode({"role": "administrator", "role2": "administrator"})
    # Dopo timeout, ma peer_caps presente → continua a usare dyn LUT
    msg = s.encode({"role2": "administrator", "role3": "administrator"})
    # Verifica indiretta: "administrator" è sostituito da alias _N
    assert "administrator" not in msg


def test_caps_round_trip_two_aware_sessions():
    """Due ADPSession aware: handshake bidirezionale popola entrambi peer_caps."""
    a = ADPSession(path=None, auto_save=False, announce_caps=True)
    b = ADPSession(path=None, auto_save=False, announce_caps=True)

    # A invia primo msg con _caps=
    msg_a_to_b = a.encode({"task": "ping"})
    assert "_caps=" in msg_a_to_b
    b.decode(msg_a_to_b)
    # B ora conosce A
    assert b.peer_caps is not None

    # B risponde con il suo _caps=
    msg_b_to_a = b.encode({"task": "pong"})
    assert "_caps=" in msg_b_to_a
    a.decode(msg_b_to_a)
    # A ora conosce B
    assert a.peer_caps is not None

    # Da qui in poi, nessuno annuncia più caps
    msg_a_2 = a.encode({"task": "data"})
    assert "_caps=" not in msg_a_2


def test_reset_caps_forces_reannounce():
    """Dopo reset_caps, encode emette di nuovo _caps= al prossimo msg."""
    s = ADPSession(path=None, auto_save=False, announce_caps=True)
    s.encode({"a": 1})  # primo annuncio
    assert s._caps_announced is True
    msg2 = s.encode({"b": 2})
    assert "_caps=" not in msg2

    s.reset_caps()
    msg3 = s.encode({"c": 3})
    # Dopo reset, ri-annuncia caps
    assert "_caps=" in msg3
