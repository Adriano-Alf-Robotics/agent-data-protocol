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


from adp.session import ADPSession


def test_session_accepts_cost_estimator_param():
    est = TokenizerCostEstimator()
    s = ADPSession(path=None, auto_save=False, cost_estimator=est)
    assert s._cost_estimator is est


def test_session_default_cost_estimator_is_none():
    s = ADPSession(path=None, auto_save=False)
    assert s._cost_estimator is None


def test_session_with_estimator_uses_tokenizer_for_selection():
    """Quando cost_estimator passato, _select_candidates lo usa per saving."""
    est = TokenizerCostEstimator()
    s = ADPSession(path=None, auto_save=False, k_threshold=2, cost_estimator=est)
    # "user_authentication_token" è 3 token; alias "_0" è 2 token; count=10 → saving positivo
    counts = {"user_authentication_token": 10}
    selected = s._select_candidates(counts)
    assert "user_authentication_token" in selected


def test_tokenizer_cost_estimator_exported_from_adp():
    """Importabile direttamente da `adp`."""
    import adp
    assert hasattr(adp, "TokenizerCostEstimator")
    assert hasattr(adp, "estimate_cost")


def test_warmup_uses_cost_estimator_when_present():
    """warmup() usa cost_estimator se ADPSession lo ha, per cost-benefit.
    Verifica che saving_for_entry sia chiamato (non il char-count fallback).
    """
    from unittest.mock import patch

    est = TokenizerCostEstimator()
    s = ADPSession(path=None, auto_save=False, k_threshold=2, cost_estimator=est)
    # 8 messaggi: count=8 → saving_for_entry("_0", "user_authentication_token", 8) = +2 > 0
    messages = [
        {"role": "user_authentication_token", "dept": "engineering_operations"},
    ] * 8
    with patch.object(est, "saving_for_entry", wraps=est.saving_for_entry) as mock_saving:
        s.warmup(messages)
        # saving_for_entry deve essere chiamato almeno una volta
        assert mock_saving.call_count > 0
    # Almeno una entry aggiunta
    assert len(s._entries) > 0


def test_warmup_without_estimator_falls_back_to_charcount():
    """warmup() senza cost_estimator usa char-count (default backward-compat)."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2, cost_estimator=None)
    messages = [
        {"role": "administrator", "dept": "engineering"},
        {"role": "administrator", "dept": "engineering"},
    ]
    s.warmup(messages)
    # Char-count è più "permissivo": "administrator" (13 char × 2 = 26)
    # − (2 char × 2 = 4) − header (~17) = 5 > 0 → entry aggiunta
    assert "administrator" in s._inv
