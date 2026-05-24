"""Test suite per adp.cost (tokenizer-aware cost estimation)."""
from __future__ import annotations

import pytest

from adp.cost import estimate_cost


def test_estimate_cost_returns_int():
    """estimate_cost ritorna sempre un int positivo per stringa non vuota."""
    n = estimate_cost("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_estimate_cost_empty_string_is_zero():
    assert estimate_cost("") == 0


def test_estimate_cost_consistent_for_same_input():
    """Stesso input → stesso conteggio (deterministico)."""
    s = "administrator engineering operations"
    assert estimate_cost(s) == estimate_cost(s)


def test_estimate_cost_longer_text_costs_more():
    """Testo più lungo → più token (in pratica monotono)."""
    short = estimate_cost("a")
    long = estimate_cost("administrator engineering operations marketing")
    assert long > short
