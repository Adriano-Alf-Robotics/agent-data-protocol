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
    sender_cold = adp.ADPSession(path=None, auto_save=False)
    receiver_cold = adp.ADPSession(path=None, auto_save=False)
    dyn_cold_tokens = 0
    for m in msgs:
        encoded = sender_cold.encode(m)
        decoded = receiver_cold.decode(encoded)
        assert decoded == m, "round-trip rotto"
        dyn_cold_tokens += _tok(encoded)

    # Dynamic LUT + static LUT combinata
    sender_combo = adp.ADPSession(
        path=None, auto_save=False, static_lut=adp.DEFAULT_AGENT_LUT
    )
    receiver_combo = adp.ADPSession(
        path=None, auto_save=False, static_lut=adp.DEFAULT_AGENT_LUT
    )
    dyn_combo_tokens = 0
    for m in msgs:
        encoded = sender_combo.encode(m)
        decoded = receiver_combo.decode(encoded)
        assert decoded == m, "round-trip rotto (combo)"
        dyn_combo_tokens += _tok(encoded)

    # Dynamic LUT + diff encoding (cold)
    sender_diff = adp.ADPSession(path=None, auto_save=False, enable_diff=True)
    receiver_diff = adp.ADPSession(path=None, auto_save=False, enable_diff=True)
    dyn_diff_tokens = 0
    for m in msgs:
        encoded = sender_diff.encode(m)
        decoded = receiver_diff.decode(encoded)
        assert decoded == m, "round-trip rotto (diff)"
        dyn_diff_tokens += _tok(encoded)

    # Full stack: dyn LUT + static + diff
    sender_full = adp.ADPSession(
        path=None, auto_save=False, static_lut=adp.DEFAULT_AGENT_LUT,
        enable_diff=True,
    )
    receiver_full = adp.ADPSession(
        path=None, auto_save=False, static_lut=adp.DEFAULT_AGENT_LUT,
        enable_diff=True,
    )
    full_stack_tokens = 0
    for m in msgs:
        encoded = sender_full.encode(m)
        decoded = receiver_full.decode(encoded)
        assert decoded == m, "round-trip rotto (full stack)"
        full_stack_tokens += _tok(encoded)

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
    print(f"{'-'*70}\n")

    # Statistiche dyn LUT
    print(f"Statistiche dynamic LUT (cold start):")
    print(f"  entries finali: {sender_cold.stats()['entries_count']}")
    print(f"  hit count (decoder): {receiver_cold.stats()['hit_count']}")
    print()
    print(f"Statistiche dynamic+static LUT:")
    print(f"  entries finali: {sender_combo.stats()['entries_count']}")
    print(f"  hit count (decoder): {receiver_combo.stats()['hit_count']}")
    print()
    print(f"Statistiche dynamic LUT + diff:")
    print(f"  entries finali: {sender_diff.stats()['entries_count']}")
    print(f"  hit count (decoder): {receiver_diff.stats()['hit_count']}")
    print()
    print(f"Statistiche full stack (dyn+static+diff):")
    print(f"  entries finali: {sender_full.stats()['entries_count']}")
    print(f"  hit count (decoder): {receiver_full.stats()['hit_count']}")
    print()


if __name__ == "__main__":
    run()
