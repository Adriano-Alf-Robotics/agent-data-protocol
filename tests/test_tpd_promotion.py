"""Test suite per TPD auto-promotion (Est. 3)."""
from __future__ import annotations

import pytest

from adp.session import ADPSession


def test_session_default_tpd_promote_params():
    s = ADPSession(path=None, auto_save=False)
    assert s._tpd_promote_every == 10
    assert s._tpd_promote_max_per_run == 10


def test_session_tpd_promote_zero_disables():
    s = ADPSession(path=None, auto_save=False, tpd_promote_every=0)
    assert s._tpd_promote_every == 0


def test_session_tpd_buffer_initialized_empty():
    s = ADPSession(path=None, auto_save=False)
    assert len(s._tpd_buffer) == 0


def test_run_tpd_promotion_empty_buffer_returns_empty():
    s = ADPSession(path=None, auto_save=False)
    added = s._run_tpd_promotion()
    assert added == []


def test_tpd_buffer_populates_on_encode():
    """encode() aggiunge il msg raw inviato al ring buffer."""
    s = ADPSession(path=None, auto_save=False, tpd_promote_every=10)
    s.encode({"a": 1})
    assert len(s._tpd_buffer) == 1
    s.encode({"b": 2})
    assert len(s._tpd_buffer) == 2


def test_tpd_buffer_fifo_evicts_oldest():
    """Ring buffer FIFO: superato maxlen, msg vecchi vengono evicted."""
    s = ADPSession(path=None, auto_save=False, tpd_promote_every=3)
    # buffer maxlen = 6 (2 × 3)
    for i in range(10):
        s.encode({"key": f"value_{i}"})
    # Buffer dovrebbe avere al massimo 6 elementi
    assert len(s._tpd_buffer) == 6


def test_tpd_promote_zero_skips_buffer_population():
    """tpd_promote_every=0: ring buffer mai popolato (feature disabilitata)."""
    s = ADPSession(path=None, auto_save=False, tpd_promote_every=0)
    s.encode({"a": 1})
    s.encode({"b": 2})
    assert len(s._tpd_buffer) == 0
