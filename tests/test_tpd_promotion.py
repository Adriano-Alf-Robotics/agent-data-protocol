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
