"""Comprehensive benchmark suite per ADP vs TOON.

Esegue 7 workload × 4 lunghezze × 6 encoders, raccoglie token + latency,
produce report Markdown + JSON.

Esecuzione:
    uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import tiktoken
import toon_py

import adp
from benchmarks.workloads import WORKLOADS
from benchmarks.pricing import cost_estimate, format_cost


ENCODER = tiktoken.get_encoding("cl100k_base")
LENGTHS = [10, 50, 100, 500]


def _tok(s: str) -> int:
    return len(ENCODER.encode(s))


def _measure_session_encode_decode(
    msgs: list[dict[str, Any]],
    sender_factory: Callable,
    receiver_factory: Callable,
) -> dict[str, Any]:
    """Esegue encode/decode su tutti msg, alternando direzione (A→B, B→A).
    Ritorna dict con: total_tokens, encode_times, decode_times."""
    a = sender_factory()
    b = receiver_factory()
    total_tokens = 0
    encode_times: list[float] = []
    decode_times: list[float] = []
    for i, m in enumerate(msgs):
        sender, receiver = (a, b) if i % 2 == 0 else (b, a)
        t0 = time.perf_counter()
        encoded = sender.encode(m)
        t1 = time.perf_counter()
        decoded = receiver.decode(encoded)
        t2 = time.perf_counter()
        assert decoded == m, f"round-trip rotto msg {i}"
        total_tokens += _tok(encoded)
        encode_times.append((t1 - t0) * 1000)  # ms
        decode_times.append((t2 - t1) * 1000)
    return {
        "total_tokens": total_tokens,
        "encode_median_ms": statistics.median(encode_times),
        "encode_p95_ms": _p95(encode_times),
        "decode_median_ms": statistics.median(decode_times),
        "decode_p95_ms": _p95(decode_times),
    }


def _p95(xs: list[float]) -> float:
    """Percentile 95 semplice (no numpy)."""
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = int(0.95 * (len(s) - 1))
    return s[idx]


def _measure_stateless(msgs: list[dict[str, Any]],
                        encoder: Callable[[dict], str]) -> dict[str, Any]:
    """Misura encoder stateless (JSON, ADP base, ADP+static, TOON):
    no session, no diff, ogni msg encodato indipendentemente."""
    total_tokens = 0
    encode_times: list[float] = []
    for m in msgs:
        t0 = time.perf_counter()
        s = encoder(m)
        t1 = time.perf_counter()
        total_tokens += _tok(s)
        encode_times.append((t1 - t0) * 1000)
    return {
        "total_tokens": total_tokens,
        "encode_median_ms": statistics.median(encode_times),
        "encode_p95_ms": _p95(encode_times),
        "decode_median_ms": 0.0,  # N/A per stateless misura
        "decode_p95_ms": 0.0,
    }


def run_workload(
    workload_name: str,
    workload_fn: Callable,
    length: int,
) -> dict[str, dict]:
    """Esegue un workload alla lunghezza data su tutti gli encoders.
    Ritorna dict {encoder_name: metrics_dict}."""
    msgs = workload_fn(length)

    results: dict[str, dict] = {}

    def _safe_stateless(name: str, encoder: Callable[[dict], str]) -> None:
        try:
            results[name] = _measure_stateless(msgs, encoder)
        except Exception as exc:
            results[name] = {"error": str(exc)}

    def _safe_session(name: str, sf: Callable, rf: Callable) -> None:
        try:
            results[name] = _measure_session_encode_decode(msgs, sf, rf)
        except Exception as exc:
            results[name] = {"error": str(exc)}

    # Stateless encoders
    _safe_stateless(
        "json_min",
        lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False),
    )
    _safe_stateless("adp_base", lambda o: adp.encode(o))
    _safe_stateless(
        "adp_static",
        lambda o: adp.encode(o, key_lut=adp.DEFAULT_AGENT_LUT),
    )
    _safe_stateless("toon", lambda o: toon_py.encode(o))

    # Session-based encoders
    _safe_session(
        "adp_dyn_cold",
        lambda: adp.ADPSession(path=None, auto_save=False,
                                announce_caps=False, enable_diff=False,
                                tpd_promote_every=0),
        lambda: adp.ADPSession(path=None, auto_save=False,
                                announce_caps=False, enable_diff=False,
                                tpd_promote_every=0),
    )
    _safe_session(
        "adp_full_stack",
        lambda: adp.ADPSession(path=None, auto_save=False,
                                static_lut=adp.DEFAULT_AGENT_LUT,
                                announce_caps=False, enable_diff=True,
                                tpd_promote_every=0,
                                cost_estimator=adp.TokenizerCostEstimator()),
        lambda: adp.ADPSession(path=None, auto_save=False,
                                static_lut=adp.DEFAULT_AGENT_LUT,
                                announce_caps=False, enable_diff=True,
                                tpd_promote_every=0,
                                cost_estimator=adp.TokenizerCostEstimator()),
    )
    return results


def main() -> None:
    all_results: dict[str, dict] = {}
    for name, fn in WORKLOADS.items():
        all_results[name] = {}
        for length in LENGTHS:
            print(f"Running {name} @ {length} msg...")
            try:
                enc_results = run_workload(name, fn, length)
                all_results[name][str(length)] = enc_results
                # Segnala eventuali encoder con errore (senza bloccare)
                for enc_name, enc_data in enc_results.items():
                    if "error" in enc_data:
                        print(f"  WARN {enc_name}: {enc_data['error']}")
            except Exception as e:
                print(f"  ERROR: {e}")
                all_results[name][str(length)] = {"error": str(e)}

    # Salva risultati
    out_path = Path(__file__).parent / "comprehensive_results.json"
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nRisultati salvati in {out_path}")

    # Print summary table (solo @ length 100 per brevità)
    print_summary(all_results, length="100")


def print_summary(all_results: dict, length: str = "100") -> None:
    print(f"\n{'='*100}")
    print(f"Summary @ {length} msg per workload (token totali)")
    print(f"{'='*100}\n")
    encoders = ["json_min", "toon", "adp_base", "adp_static",
                "adp_dyn_cold", "adp_full_stack"]
    print(f"{'Workload':<25}", end="")
    for e in encoders:
        print(f"{e:>16}", end="")
    print()
    print("-" * (25 + 16 * len(encoders)))
    for workload, by_length in all_results.items():
        run = by_length.get(length, {})
        if "error" in run:
            print(f"{workload:<25} FATAL ERROR: {run['error']}")
            continue
        print(f"{workload:<25}", end="")
        for e in encoders:
            enc_data = run.get(e, {})
            if "error" in enc_data:
                print(f"{'ERR':>16}", end="")
            else:
                tokens = enc_data.get("total_tokens", 0)
                print(f"{tokens:>16,}", end="")
        print()
    print()


if __name__ == "__main__":
    main()
