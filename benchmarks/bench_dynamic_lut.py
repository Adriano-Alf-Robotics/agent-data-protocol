"""Benchmark dynamic LUT (ADPSession) vs JSON, ADP base, ADP+static LUT, TOON.

Simula una conversazione multi-messaggio tra agenti per misurare il guadagno
cumulativo della dynamic LUT su pattern realistici. Single-message benchmark
(senza stato) sono già coperti in compare_formats.py.

Esecuzione:
    uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
"""
from __future__ import annotations

import json
from typing import Any

import tiktoken
import toon_py

import adp


ENCODER = tiktoken.get_encoding("cl100k_base")


def _tok(s: str) -> int:
    return len(ENCODER.encode(s))


# ---------------------------------------------------------------------------
# Simulazione conversazione 20 messaggi: agent task pipeline realistica
# ---------------------------------------------------------------------------

def _build_conversation(n: int = 20) -> list[dict[str, Any]]:
    """Genera n messaggi alternati tra Agente A (planner) e Agente B (executor).

    Riusa nomi-chiave e valori-string ricorrenti tipici di una pipeline
    multi-step: task_id, status, role, dept, agent, intent, result.
    """
    msgs: list[dict[str, Any]] = []
    for i in range(n):
        if i % 2 == 0:
            msgs.append({
                "task_id": f"task_{i:03d}",
                "from_agent": "planner_agent_alpha",
                "to_agent": "executor_agent_beta",
                "intent": "execute_step",
                "step": i // 2,
                "context": {
                    "user": {
                        "id": 1000 + i,
                        "role": "administrator",
                        "department": "engineering",
                        "status": "active",
                    },
                    "previous_user": {
                        "id": 999 + i,
                        "role": "administrator",
                        "department": "engineering",
                        "status": "active",
                    },
                },
                "payload": {
                    "action": "process_request",
                    "parameters": {
                        "timeout_seconds": 30,
                        "retries": 3,
                        "priority": "high",
                    },
                },
            })
        else:
            msgs.append({
                "task_id": f"task_{i-1:03d}",
                "from_agent": "executor_agent_beta",
                "to_agent": "planner_agent_alpha",
                "intent": "step_completed",
                "step": (i - 1) // 2,
                "status": "successful",
                "result": {
                    "outcome": "ok",
                    "duration_ms": 200 + i * 10,
                    "metrics": {
                        "tokens_processed": 1024 + i,
                        "cache_hits": 87,
                        "cache_misses": 13,
                        "status": "successful",
                    },
                    "events": [
                        {"step": 1, "name": "validate", "status": "successful"},
                        {"step": 2, "name": "transform", "status": "successful"},
                        {"step": 3, "name": "emit", "status": "successful"},
                    ],
                },
            })
    return msgs


# ---------------------------------------------------------------------------
# Encoders per ogni formato (per messaggio)
# ---------------------------------------------------------------------------

def encode_json_min(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def encode_adp_base(obj: dict) -> str:
    return adp.encode(obj)


def encode_adp_static(obj: dict) -> str:
    return adp.encode(obj, key_lut=adp.DEFAULT_AGENT_LUT)


def encode_toon(obj: dict) -> str:
    return toon_py.encode(obj)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run() -> None:
    msgs = _build_conversation(20)

    # Static-per-message: ogni encode è indipendente
    json_tokens = sum(_tok(encode_json_min(m)) for m in msgs)
    adp_base_tokens = sum(_tok(encode_adp_base(m)) for m in msgs)
    adp_static_tokens = sum(_tok(encode_adp_static(m)) for m in msgs)
    toon_tokens = sum(_tok(encode_toon(m)) for m in msgs)

    # Dynamic LUT (cold start: vuota all'inizio)
    # Pattern realistico: A invia X-type (i pari), B invia Y-type (i dispari).
    # Ogni session tiene baseline per la propria direzione di invio.
    a_cold = adp.ADPSession(path=None, auto_save=False, enable_diff=False)
    b_cold = adp.ADPSession(path=None, auto_save=False, enable_diff=False)
    dyn_cold_tokens = 0
    for i, m in enumerate(msgs):
        sender, receiver = (a_cold, b_cold) if i % 2 == 0 else (b_cold, a_cold)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (cold) msg {i}"
        dyn_cold_tokens += _tok(encoded)

    # Dynamic LUT + static LUT combinata
    a_combo = adp.ADPSession(path=None, auto_save=False,
                              static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=False)
    b_combo = adp.ADPSession(path=None, auto_save=False,
                              static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=False)
    dyn_combo_tokens = 0
    for i, m in enumerate(msgs):
        sender, receiver = (a_combo, b_combo) if i % 2 == 0 else (b_combo, a_combo)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (combo) msg {i}"
        dyn_combo_tokens += _tok(encoded)

    # Dynamic LUT + diff encoding (cold)
    a_diff = adp.ADPSession(path=None, auto_save=False, enable_diff=True)
    b_diff = adp.ADPSession(path=None, auto_save=False, enable_diff=True)
    dyn_diff_tokens = 0
    for i, m in enumerate(msgs):
        sender, receiver = (a_diff, b_diff) if i % 2 == 0 else (b_diff, a_diff)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (diff) msg {i}"
        dyn_diff_tokens += _tok(encoded)

    # Full stack: dyn LUT + static + diff
    a_full = adp.ADPSession(path=None, auto_save=False,
                             static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    b_full = adp.ADPSession(path=None, auto_save=False,
                             static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    full_stack_tokens = 0
    for i, m in enumerate(msgs):
        sender, receiver = (a_full, b_full) if i % 2 == 0 else (b_full, a_full)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (full stack) msg {i}"
        full_stack_tokens += _tok(encoded)

    # Full stack + tokenizer-aware cost estimator
    est = adp.TokenizerCostEstimator("cl100k_base")
    a_tok = adp.ADPSession(path=None, auto_save=False,
                            static_lut=adp.DEFAULT_AGENT_LUT,
                            enable_diff=True, cost_estimator=est)
    b_tok = adp.ADPSession(path=None, auto_save=False,
                            static_lut=adp.DEFAULT_AGENT_LUT,
                            enable_diff=True, cost_estimator=est)
    tokenizer_aware_tokens = 0
    for i, m in enumerate(msgs):
        sender, receiver = (a_tok, b_tok) if i % 2 == 0 else (b_tok, a_tok)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (tokenizer-aware) msg {i}"
        tokenizer_aware_tokens += _tok(encoded)

    # Warm start: pre-warm da prima metà della conversazione, misura solo seconda metà
    msgs_warmup = msgs[: len(msgs) // 2]
    msgs_measure = msgs[len(msgs) // 2 :]

    a_warm = adp.ADPSession(path=None, auto_save=False,
                             static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    b_warm = adp.ADPSession(path=None, auto_save=False,
                             static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    # Pre-warm: entrambe le sessions imparano dal corpus di prima metà
    a_warm.warmup(msgs_warmup)
    b_warm.warmup(msgs_warmup)
    warm_start_tokens = 0
    for i, m in enumerate(msgs_measure):
        sender, receiver = (a_warm, b_warm) if i % 2 == 0 else (b_warm, a_warm)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (warm start) msg {i}"
        warm_start_tokens += _tok(encoded)

    # Equivalente "cold" sulla seconda metà per confronto onesto
    a_cold_half = adp.ADPSession(path=None, auto_save=False,
                                   static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    b_cold_half = adp.ADPSession(path=None, auto_save=False,
                                   static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    cold_half_tokens = 0
    for i, m in enumerate(msgs_measure):
        sender, receiver = (a_cold_half, b_cold_half) if i % 2 == 0 else (b_cold_half, a_cold_half)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (cold half) msg {i}"
        cold_half_tokens += _tok(encoded)

    baseline = json_tokens
    print(f"\n{'='*70}")
    print(f"Benchmark: 20-message agent conversation")
    print(f"Tokenizer: cl100k_base")
    print(f"{'='*70}\n")
    print(f"{'Formato':<35} {'Token totali':>14} {'Δ vs JSON':>15}")
    print(f"{'-'*70}")
    fmt = lambda n, b: f"{n:>14,} {((b-n)/b*100):>14.1f}%"
    print(f"{'JSON-min':<35} {fmt(json_tokens, baseline)}")
    print(f"{'ADP base':<35} {fmt(adp_base_tokens, baseline)}")
    print(f"{'ADP + static LUT':<35} {fmt(adp_static_tokens, baseline)}")
    print(f"{'ADP + dynamic LUT (cold)':<35} {fmt(dyn_cold_tokens, baseline)}")
    print(f"{'ADP + dynamic + static LUT':<35} {fmt(dyn_combo_tokens, baseline)}")
    print(f"{'ADP + dyn LUT + diff':<35} {fmt(dyn_diff_tokens, baseline)}")
    print(f"{'ADP + full stack (lut+static+diff)':<35} {fmt(full_stack_tokens, baseline)}")
    print(f"{'ADP full stack + tokenizer-aware':<35} "
          f"{fmt(tokenizer_aware_tokens, baseline)}")
    print(f"{'TOON':<35} {fmt(toon_tokens, baseline)}")
    print(f"{'-'*70}")

    # Confronto diretto vs TOON (target)
    print(f"\nConfronto diretto vs TOON (best competitor):")
    print(f"{'Formato':<35} {'Δ vs TOON':>15}")
    print(f"{'-'*70}")
    delta_toon = lambda n: f"{((toon_tokens-n)/toon_tokens*100):>14.1f}%"
    print(f"{'ADP base':<35} {delta_toon(adp_base_tokens):>15}")
    print(f"{'ADP + static LUT':<35} {delta_toon(adp_static_tokens):>15}")
    print(f"{'ADP + dynamic LUT (cold)':<35} {delta_toon(dyn_cold_tokens):>15}")
    print(f"{'ADP + dynamic + static LUT':<35} {delta_toon(dyn_combo_tokens):>15}")
    print(f"{'ADP + dyn LUT + diff':<35} {delta_toon(dyn_diff_tokens):>15}")
    print(f"{'ADP + full stack':<35} {delta_toon(full_stack_tokens):>15}")
    print(f"{'ADP full stack + tokenizer-aware':<35} "
          f"{delta_toon(tokenizer_aware_tokens):>15}")
    print(f"{'-'*70}\n")

    print(f"{'-'*70}")
    print(f"\nSotto-benchmark seconda metà (10 msg) — warm vs cold:")
    print(f"{'-'*70}")
    half_baseline = sum(_tok(encode_json_min(m)) for m in msgs_measure)
    print(f"{'JSON-min (10 msg)':<35} {fmt(half_baseline, half_baseline)}")
    print(f"{'full stack cold (10 msg)':<35} {fmt(cold_half_tokens, half_baseline)}")
    print(f"{'full stack WARM (10 msg)':<35} {fmt(warm_start_tokens, half_baseline)}")
    print(f"{'-'*70}")
    print(f"Δ warm vs cold sulla seconda metà:")
    if cold_half_tokens > 0:
        cold_delta = (cold_half_tokens - warm_start_tokens) / cold_half_tokens * 100
        print(f"  warm risparmia {cold_delta:.1f}% dei token vs cold start")
    print()

    # Statistiche dyn LUT
    print(f"Statistiche dynamic LUT (cold start):")
    print(f"  entries finali (a+b): {a_cold.stats()['entries_count']} + "
          f"{b_cold.stats()['entries_count']}")
    print(f"  hit count (a+b): {a_cold.stats()['hit_count']} + "
          f"{b_cold.stats()['hit_count']}")
    print()
    print(f"Statistiche dynamic+static LUT:")
    print(f"  entries finali (a+b): {a_combo.stats()['entries_count']} + "
          f"{b_combo.stats()['entries_count']}")
    print(f"  hit count (a+b): {a_combo.stats()['hit_count']} + "
          f"{b_combo.stats()['hit_count']}")
    print()
    print(f"Statistiche dynamic LUT + diff:")
    print(f"  entries finali (a+b): {a_diff.stats()['entries_count']} + "
          f"{b_diff.stats()['entries_count']}")
    print(f"  hit count (a+b): {a_diff.stats()['hit_count']} + "
          f"{b_diff.stats()['hit_count']}")
    print()
    print(f"Statistiche full stack:")
    print(f"  entries finali (a+b): {a_full.stats()['entries_count']} + "
          f"{b_full.stats()['entries_count']}")
    print(f"  hit count (a+b): {a_full.stats()['hit_count']} + "
          f"{b_full.stats()['hit_count']}")
    print()
if __name__ == "__main__":
    run()
