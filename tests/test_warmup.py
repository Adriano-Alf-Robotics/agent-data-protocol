"""Test suite per ADPSession.warmup() (pre-warm da corpus)."""
from __future__ import annotations

from pathlib import Path

import pytest

from adp.session import ADPSession


def test_warmup_empty_returns_zero():
    s = ADPSession(path=None, auto_save=False)
    added = s.warmup([])
    assert added == 0
    assert s._entries == {}


def test_warmup_from_dict_list_populates_lut():
    """Lista di payload pre-decodificati: chiavi/valori ricorrenti
    (>= K=2 occorrenze cumulative) vanno in dynamic LUT."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    messages = [
        {"user": {"id": 1, "role": "administrator", "dept": "engineering"}},
        {"user": {"id": 2, "role": "administrator", "dept": "engineering"}},
        {"user": {"id": 3, "role": "developer", "dept": "engineering"}},
    ]
    added = s.warmup(messages)
    # Almeno una entry aggiunta (administrator, engineering compaiono >= 2 volte)
    assert added > 0
    # "administrator" appare 2 volte → candidato sopra soglia
    assert "administrator" in s._inv
    # "engineering" appare 3 volte → sicuramente in LUT
    assert "engineering" in s._inv
