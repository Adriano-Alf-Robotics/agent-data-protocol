"""Test suite per adp.cost (tokenizer-aware cost estimation)."""
from __future__ import annotations

import pytest

from adp.cost import estimate_cost, TokenizerCostEstimator


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


def test_estimator_init_default_tokenizer():
    """TokenizerCostEstimator default tokenizer è cl100k_base."""
    est = TokenizerCostEstimator()
    assert est.tokenizer == "cl100k_base"


def test_estimator_estimate_matches_estimate_cost():
    """TokenizerCostEstimator.estimate() usa estimate_cost() internamente."""
    est = TokenizerCostEstimator("cl100k_base")
    assert est.estimate("administrator") == estimate_cost("administrator", "cl100k_base")


def test_estimator_saving_positive_for_frequent_long_string():
    """administrator_interface (21 char) × 15 occorrenze vs alias x → saving positivo."""
    est = TokenizerCostEstimator()
    saving = est.saving_for_entry(alias="x", fullname="administrator_interface", count=15)
    assert saving > 0


def test_estimator_saving_negative_for_rare_short_string():
    """'ok' × 2 occorrenze: alias x + header overhead → saving negativo."""
    est = TokenizerCostEstimator()
    saving = est.saving_for_entry(alias="x", fullname="ok", count=2)
    assert saving < 0


def test_estimator_tiktoken_availability_flag():
    """is_tiktoken_available riflette se tiktoken è importato."""
    est = TokenizerCostEstimator()
    assert isinstance(est.is_tiktoken_available, bool)
