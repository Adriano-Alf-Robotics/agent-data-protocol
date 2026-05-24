# Comprehensive Benchmark Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** estendere il benchmark esistente da un singolo workload (20-msg agent task) a una suite comprensiva con 6 workload distinti, sweep su lunghezze conversazione, payload misti, pricing $ per provider, e misure di performance (latenza encode/decode).

**Architecture:** nuovo modulo `benchmarks/workloads.py` con generatori per ogni scenario. Runner `benchmarks/bench_comprehensive.py` che esegue tutti i workload, raccoglie metriche (token + latency), produce report tabellare Markdown + JSON. Pricing tabella stati AI lookup per Anthropic/OpenAI.

**Tech Stack:** Python 3.11+, `tiktoken`, `toon-py`, stdlib (`time.perf_counter`, `statistics`, `json`, `random`).

---

## Scope

**Incluso:**
- `benchmarks/workloads.py`: 6 workload generators
  - `status_polling` — payload molto similari, perfetto per diff encoding
  - `tool_use` — schemi tool eterogenei + reply, mixed structure
  - `long_narrative` — testo prosa lungo (logs, conversation history)
  - `etl_pipeline` — large nested dicts (database row collections)
  - `multi_agent_broadcast` — 1 sender N receivers + N→1 reply (simula fan-out)
  - `db_query_response` — query in / tabular result out
- `benchmarks/pricing.py`: pricing $ per provider
- `benchmarks/bench_comprehensive.py`: runner unificato
  - Per ogni workload: 4 lunghezze (10/50/100/500 msg)
  - Mixed payload variant (random mix dei 6)
  - Per ogni run: token + latency mediana/p95
  - Output: Markdown table + JSON file `benchmarks/comprehensive_results.json`
- TOON head-to-head: per ogni workload, calcola Δ vs TOON
- Pricing: stima costo $ per 1M conversation su Anthropic Claude / OpenAI GPT

**Escluso:**
- Multi-tokenizer comparison (solo cl100k_base default)
- Plot grafici (CSV/Markdown only)
- Distributed benchmark (single-process)
- Memory profiling
- Confronto con altri formati (MessagePack, CBOR) — solo TOON + ADP variants

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `benchmarks/workloads.py` | crea | 6 generator + mixed |
| `benchmarks/pricing.py` | crea | tabella $ + helper `cost_estimate` |
| `benchmarks/bench_comprehensive.py` | crea | runner unificato + output report |
| `benchmarks/comprehensive_results.json` | output | risultati persistiti (committato per snapshot) |

Nota: `benchmarks/bench_dynamic_lut.py` resta intatto — è il bench veloce single-workload usato dalla README.

---

## Task 1 — Modulo `workloads.py` con 6 generator

**Files:**
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/workloads.py`

- [ ] **Step 1: Crea il modulo con tutti e 6 i generator**

```python
"""Workload generators per benchmark comprehensive.

Ogni funzione ritorna list[dict] di n messaggi simulando un pattern
realistico di comunicazione agent-to-agent.
"""
from __future__ import annotations

import random
from typing import Any, Callable


def status_polling(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Pattern: status report ricorrente. Solo counter/timestamp cambiano.
    PERFETTO per diff encoding (delta minimo per msg)."""
    rng = random.Random(seed)
    msgs = []
    for i in range(n):
        msgs.append({
            "service": "ingest_pipeline",
            "instance_id": "i-0a1b2c3d4e5f",
            "status": "healthy" if i % 5 != 0 else "degraded",
            "uptime_seconds": 3600 + i * 60,
            "metrics": {
                "requests_per_second": 1000 + rng.randint(-50, 50),
                "p50_latency_ms": 12,
                "p95_latency_ms": 45,
                "p99_latency_ms": 120,
                "error_rate": 0.001 if i % 5 != 0 else 0.05,
            },
            "alerts": [] if i % 5 != 0 else ["high_error_rate"],
        })
    return msgs


def tool_use(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Pattern: tool call alternati con reply. Schemi eterogenei.
    Testa la varianza inter-msg: diff dovrebbe FALLIRE spesso, dyn LUT vince."""
    rng = random.Random(seed)
    tools = ["read_file", "search_web", "execute_query", "send_email", "calculate"]
    msgs = []
    for i in range(n):
        if i % 2 == 0:
            tool = rng.choice(tools)
            msgs.append({
                "type": "tool_call",
                "id": f"call_{i:04d}",
                "name": tool,
                "arguments": _tool_args(tool, rng),
            })
        else:
            msgs.append({
                "type": "tool_result",
                "tool_call_id": f"call_{i-1:04d}",
                "status": "success" if rng.random() > 0.1 else "error",
                "content": _tool_result_content(rng),
                "duration_ms": rng.randint(50, 2000),
            })
    return msgs


def _tool_args(tool: str, rng: random.Random) -> dict:
    if tool == "read_file":
        return {"path": f"/var/log/app/{rng.randint(1,100)}.log", "encoding": "utf-8"}
    if tool == "search_web":
        return {"query": "machine learning benchmarks 2026", "max_results": 10}
    if tool == "execute_query":
        return {"sql": "SELECT * FROM users WHERE active = true LIMIT 100",
                "params": []}
    if tool == "send_email":
        return {"to": "user@example.com", "subject": "Report", "body_preview": "..."}
    if tool == "calculate":
        return {"expression": f"{rng.randint(1,1000)} * {rng.randint(1,100)}"}
    return {}


def _tool_result_content(rng: random.Random) -> Any:
    kind = rng.choice(["text", "list", "dict"])
    if kind == "text":
        return "Operation completed successfully. Result available in cache."
    if kind == "list":
        return [{"id": i, "value": f"item_{i}"} for i in range(5)]
    return {"key1": "value1", "key2": rng.randint(1, 100), "nested": {"a": 1}}


def long_narrative(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Pattern: testo prosa lungo (conversation history, log entries).
    Testa scenari dove il payload ha alta entropia textuale."""
    rng = random.Random(seed)
    topics = [
        "The quarterly revenue analysis indicates strong growth across all segments.",
        "Customer feedback surveys show a marked improvement in satisfaction scores.",
        "Engineering team completed the migration to the new infrastructure platform.",
        "Marketing campaign metrics exceeded targets by a substantial margin.",
        "Operations identified three optimization opportunities for next quarter.",
    ]
    msgs = []
    for i in range(n):
        # Componi narrativa concatenando 3-5 frasi
        sentences = [rng.choice(topics) for _ in range(rng.randint(3, 5))]
        msgs.append({
            "type": "log_entry",
            "level": rng.choice(["info", "warning", "error"]),
            "timestamp": f"2026-05-24T{i % 24:02d}:00:00Z",
            "source": "narrative_generator",
            "message": " ".join(sentences),
        })
    return msgs


def etl_pipeline(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Pattern: large nested objects (collection di row da DB).
    Testa scenari dove ogni msg porta molti dati strutturati."""
    rng = random.Random(seed)
    msgs = []
    for i in range(n):
        rows = []
        for j in range(20):  # 20 rows per msg
            rows.append({
                "id": i * 100 + j,
                "user_id": rng.randint(1000, 9999),
                "event_type": rng.choice(["page_view", "click", "purchase"]),
                "timestamp_ms": 1700000000000 + i * 1000 + j,
                "properties": {
                    "url": "https://example.com/products",
                    "referrer": "https://google.com",
                    "user_agent": "Mozilla/5.0 Chrome/127.0",
                },
            })
        msgs.append({
            "batch_id": f"batch_{i:04d}",
            "source": "ingestion_pipeline",
            "row_count": len(rows),
            "rows": rows,
        })
    return msgs


def multi_agent_broadcast(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Pattern: 1→N broadcast then N→1 replies. Alterna ampi msg di
    broadcast con risposte concise.

    Per semplificare il bench, modelliamo come sequenza alternata di
    msg broadcast (large) e msg reply (small)."""
    rng = random.Random(seed)
    msgs = []
    for i in range(n):
        if i % 5 == 0:
            # Broadcast: large msg con destinatari
            msgs.append({
                "type": "broadcast",
                "from": "coordinator",
                "to": [f"worker_{j}" for j in range(10)],
                "topic": "task_assignment",
                "payload": {
                    "task_id": f"t_{i:04d}",
                    "deadline": "2026-06-01T00:00:00Z",
                    "priority": "high",
                    "instructions": "Process batch and emit results in standard format",
                },
            })
        else:
            # Reply: small msg da uno dei worker
            worker = rng.randint(0, 9)
            msgs.append({
                "type": "reply",
                "from": f"worker_{worker}",
                "to": "coordinator",
                "task_id": f"t_{(i // 5) * 5:04d}",
                "status": "completed",
                "result_count": rng.randint(1, 50),
            })
    return msgs


def db_query_response(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Pattern: query parameters in / tabular result out.
    Alterna query e response strutturati."""
    rng = random.Random(seed)
    msgs = []
    for i in range(n):
        if i % 2 == 0:
            msgs.append({
                "type": "query",
                "query_id": f"q_{i:04d}",
                "sql": "SELECT id, name, email, role, dept FROM users WHERE active = ?",
                "params": [True],
                "limit": 100,
                "timeout_seconds": 30,
            })
        else:
            rows = [
                {"id": rng.randint(1, 10000),
                 "name": f"user_{rng.randint(1, 1000)}",
                 "email": f"user{rng.randint(1, 1000)}@example.com",
                 "role": rng.choice(["admin", "developer", "viewer"]),
                 "dept": rng.choice(["engineering", "sales", "marketing"])}
                for _ in range(20)
            ]
            msgs.append({
                "type": "query_result",
                "query_id": f"q_{i-1:04d}",
                "row_count": len(rows),
                "rows": rows,
                "execution_time_ms": rng.randint(10, 500),
            })
    return msgs


def mixed(n: int = 20, seed: int = 42) -> list[dict[str, Any]]:
    """Random mix di tutti i workload. Più realistico: stessa session
    può vedere diversi tipi di msg."""
    rng = random.Random(seed)
    workloads = [
        status_polling, tool_use, long_narrative,
        etl_pipeline, multi_agent_broadcast, db_query_response,
    ]
    msgs = []
    for i in range(n):
        w = rng.choice(workloads)
        # Prendi 1 msg da un mini-batch di 5
        batch = w(5, seed=seed + i)
        msgs.append(rng.choice(batch))
    return msgs


# Registry per il runner
WORKLOADS: dict[str, Callable[[int, int], list[dict[str, Any]]]] = {
    "status_polling": status_polling,
    "tool_use": tool_use,
    "long_narrative": long_narrative,
    "etl_pipeline": etl_pipeline,
    "multi_agent_broadcast": multi_agent_broadcast,
    "db_query_response": db_query_response,
    "mixed": mixed,
}
```

- [ ] **Step 2: Verifica syntax + generators producono dict validi**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run python -c "
from benchmarks.workloads import WORKLOADS
for name, fn in WORKLOADS.items():
    msgs = fn(5)
    assert isinstance(msgs, list)
    assert len(msgs) == 5
    for m in msgs:
        assert isinstance(m, dict)
    print(f'{name}: OK ({len(msgs)} msgs)')
"
```

Expected: 7 righe `OK`.

- [ ] **Step 3: Commit**

```bash
git add benchmarks/workloads.py
git commit -m "bench: aggiunto benchmarks/workloads.py con 6 generator + mixed"
```

---

## Task 2 — Modulo `pricing.py` con tabella provider

**Files:**
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/pricing.py`

- [ ] **Step 1: Crea il modulo**

```python
"""Pricing per provider LLM, in $ per milione di token (input).

Numeri aggiornati a maggio 2026. Usati per stimare il costo $ delle
conversazioni nei benchmark.
"""
from __future__ import annotations

# $ per 1M input tokens (i token che paghi quando emetti messaggi al modello)
PRICING_INPUT_PER_MTOK: dict[str, float] = {
    # Anthropic Claude 4.x family
    "claude-opus-4-7": 15.00,
    "claude-sonnet-4-6": 3.00,
    "claude-haiku-4-5": 0.80,
    # OpenAI
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
    "o1": 15.00,
    "o3-mini": 1.10,
}


def cost_estimate(tokens: int, model: str = "claude-sonnet-4-6") -> float:
    """Stima il costo $ per `tokens` input al modello indicato.

    Ritorna 0.0 se model non riconosciuto (con warning silenzioso).
    """
    rate = PRICING_INPUT_PER_MTOK.get(model, 0.0)
    return tokens * rate / 1_000_000


def format_cost(cost: float) -> str:
    """Formatta $ in modo leggibile (4 cifre dopo decimal se < 1$)."""
    if cost < 0.0001:
        return f"${cost*1000:.4f}m"  # millesimi
    if cost < 1.0:
        return f"${cost:.4f}"
    return f"${cost:.2f}"
```

- [ ] **Step 2: Verify**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run python -c "
from benchmarks.pricing import cost_estimate, format_cost
c = cost_estimate(1_000_000, 'claude-sonnet-4-6')
print(f'1M token su Sonnet 4.6: {format_cost(c)}')
c2 = cost_estimate(897, 'claude-opus-4-7')
print(f'897 token su Opus 4.7: {format_cost(c2)}')
"
```

Expected: 2 righe con costi calcolati.

- [ ] **Step 3: Commit**

```bash
git add benchmarks/pricing.py
git commit -m "bench: pricing per provider LLM ($/Mtok)"
```

---

## Task 3 — Runner core `bench_comprehensive.py` con loop principale

**Files:**
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/bench_comprehensive.py`

- [ ] **Step 1: Crea il modulo con core runner (solo workload + token, no latency/pricing ancora)**

```python
"""Comprehensive benchmark suite per ADP vs TOON.

Esegue 7 workload × 4 lunghezze × 5 encoders, raccoglie token + latency,
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

    # Stateless encoders
    results["json_min"] = _measure_stateless(
        msgs, lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)
    )
    results["adp_base"] = _measure_stateless(msgs, lambda o: adp.encode(o))
    results["adp_static"] = _measure_stateless(
        msgs, lambda o: adp.encode(o, key_lut=adp.DEFAULT_AGENT_LUT)
    )
    results["toon"] = _measure_stateless(msgs, lambda o: toon_py.encode(o))

    # Session-based encoders
    results["adp_dyn_cold"] = _measure_session_encode_decode(
        msgs,
        lambda: adp.ADPSession(path=None, auto_save=False,
                                announce_caps=False, enable_diff=False,
                                tpd_promote_every=0),
        lambda: adp.ADPSession(path=None, auto_save=False,
                                announce_caps=False, enable_diff=False,
                                tpd_promote_every=0),
    )
    results["adp_full_stack"] = _measure_session_encode_decode(
        msgs,
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
                all_results[name][str(length)] = run_workload(name, fn, length)
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
            print(f"{workload:<25} ERROR")
            continue
        print(f"{workload:<25}", end="")
        for e in encoders:
            tokens = run.get(e, {}).get("total_tokens", 0)
            print(f"{tokens:>16,}", end="")
        print()
    print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Esegui**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

REPORTA OUTPUT COMPLETO incluso eventuali errori. Workload più pesante (etl_pipeline @ 500 msg con 20 rows ognuno) potrebbe essere lento. Se timeout > 5 min: ridurre LENGTHS a [10, 50, 100] per ora.

Verifica `benchmarks/comprehensive_results.json` esiste e è valido JSON.

- [ ] **Step 3: Commit**

```bash
git add benchmarks/bench_comprehensive.py benchmarks/comprehensive_results.json
git commit -m "bench: comprehensive suite runner (workloads × lengths × encoders)"
```

---

## Task 4 — Estendi report: pricing $ + latency, Markdown output

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/bench_comprehensive.py`
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/comprehensive_report.md`

- [ ] **Step 1: Aggiungi report Markdown + pricing alle stampe**

In `bench_comprehensive.py`, sostituire `print_summary` con una versione che produce anche output Markdown:

```python
def print_summary(all_results: dict, length: str = "100") -> None:
    """Stampa summary su stdout E genera markdown report."""
    encoders = ["json_min", "toon", "adp_base", "adp_static",
                "adp_dyn_cold", "adp_full_stack"]
    print(f"\n{'='*100}")
    print(f"Summary @ {length} msg per workload (token totali)")
    print(f"{'='*100}\n")
    print(f"{'Workload':<25}", end="")
    for e in encoders:
        print(f"{e:>16}", end="")
    print()
    print("-" * (25 + 16 * len(encoders)))
    for workload, by_length in all_results.items():
        run = by_length.get(length, {})
        if "error" in run:
            print(f"{workload:<25} ERROR")
            continue
        print(f"{workload:<25}", end="")
        for e in encoders:
            tokens = run.get(e, {}).get("total_tokens", 0)
            print(f"{tokens:>16,}", end="")
        print()
    print()


def generate_markdown_report(all_results: dict, output_path: Path) -> None:
    """Genera report Markdown con tutte le viste."""
    lines = [
        "# Comprehensive Benchmark Report",
        "",
        "Auto-generato da `benchmarks/bench_comprehensive.py`. Tokenizer `cl100k_base`.",
        "",
    ]
    encoders = ["json_min", "toon", "adp_base", "adp_static",
                "adp_dyn_cold", "adp_full_stack"]

    # Sezione 1: token totali per (workload, length, encoder)
    lines.append("## Token totali")
    lines.append("")
    for length in LENGTHS:
        lines.append(f"### @ {length} msg")
        lines.append("")
        header = "| Workload | " + " | ".join(encoders) + " |"
        sep = "|---|" + "|".join(["---:"] * len(encoders)) + "|"
        lines.append(header)
        lines.append(sep)
        for workload, by_length in all_results.items():
            run = by_length.get(str(length), {})
            if "error" in run:
                lines.append(f"| {workload} | ERROR |" + " |" * (len(encoders) - 1))
                continue
            row = f"| {workload} |"
            for e in encoders:
                tokens = run.get(e, {}).get("total_tokens", 0)
                row += f" {tokens:,} |"
            lines.append(row)
        lines.append("")

    # Sezione 2: Δ% vs TOON e vs JSON-min per full stack @ 100
    lines.append("## ADP full_stack vs TOON e JSON @ 100 msg")
    lines.append("")
    lines.append("| Workload | JSON | TOON | ADP full | Δ vs JSON | Δ vs TOON |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for workload, by_length in all_results.items():
        run = by_length.get("100", {})
        if "error" in run:
            continue
        j = run.get("json_min", {}).get("total_tokens", 0)
        t = run.get("toon", {}).get("total_tokens", 0)
        a = run.get("adp_full_stack", {}).get("total_tokens", 0)
        d_json = (j - a) / j * 100 if j else 0
        d_toon = (t - a) / t * 100 if t else 0
        lines.append(f"| {workload} | {j:,} | {t:,} | {a:,} | "
                     f"{d_json:+.1f}% | {d_toon:+.1f}% |")
    lines.append("")

    # Sezione 3: Pricing $ stima per conversazione 1k msg @ Claude Sonnet 4.6
    lines.append("## Costo $ stima per 1 conversazione di 1000 msg")
    lines.append("")
    lines.append("Estrapolato linearmente dal run @ 100 msg, Claude Sonnet 4.6 ($3/Mtok).")
    lines.append("")
    lines.append("| Workload | JSON 1k | TOON 1k | ADP full 1k | Risparmio vs TOON |")
    lines.append("|---|---:|---:|---:|---:|")
    for workload, by_length in all_results.items():
        run = by_length.get("100", {})
        if "error" in run:
            continue
        j_1k = run.get("json_min", {}).get("total_tokens", 0) * 10
        t_1k = run.get("toon", {}).get("total_tokens", 0) * 10
        a_1k = run.get("adp_full_stack", {}).get("total_tokens", 0) * 10
        cost_j = cost_estimate(j_1k, "claude-sonnet-4-6")
        cost_t = cost_estimate(t_1k, "claude-sonnet-4-6")
        cost_a = cost_estimate(a_1k, "claude-sonnet-4-6")
        saving = cost_t - cost_a
        lines.append(f"| {workload} | {format_cost(cost_j)} | "
                     f"{format_cost(cost_t)} | {format_cost(cost_a)} | "
                     f"{format_cost(saving)} |")
    lines.append("")

    # Sezione 4: Latency
    lines.append("## Latency encode median @ 100 msg (ms)")
    lines.append("")
    lines.append("| Workload | json | toon | adp_full | "
                 "decode adp_full median |")
    lines.append("|---|---:|---:|---:|---:|")
    for workload, by_length in all_results.items():
        run = by_length.get("100", {})
        if "error" in run:
            continue
        j = run.get("json_min", {}).get("encode_median_ms", 0)
        t = run.get("toon", {}).get("encode_median_ms", 0)
        a_enc = run.get("adp_full_stack", {}).get("encode_median_ms", 0)
        a_dec = run.get("adp_full_stack", {}).get("decode_median_ms", 0)
        lines.append(f"| {workload} | {j:.3f} | {t:.3f} | "
                     f"{a_enc:.3f} | {a_dec:.3f} |")
    lines.append("")

    output_path.write_text("\n".join(lines))
    print(f"Markdown report salvato in {output_path}")
```

E nella `main()`, dopo il `out_path.write_text(...)`, aggiungere:

```python
    md_path = Path(__file__).parent / "comprehensive_report.md"
    generate_markdown_report(all_results, md_path)
```

- [ ] **Step 2: Esegui di nuovo per generare il report**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

Verifica che `benchmarks/comprehensive_report.md` esista.

```bash
head -50 benchmarks/comprehensive_report.md
```

- [ ] **Step 3: Commit (incluso report generato)**

```bash
git add benchmarks/bench_comprehensive.py benchmarks/comprehensive_report.md benchmarks/comprehensive_results.json
git commit -m "bench(comprehensive): aggiunto Markdown report con pricing \$ + latency"
```

---

## Task 5 — Update README: link al comprehensive report + 1 riga riassuntiva

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/README.md`

- [ ] **Step 1: Aggiungi link al comprehensive report**

Trova nella sezione "### Confronto static vs dynamic vs full stack" il paragrafo che termina con `uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut`. Aggiungi DOPO:

```markdown
Per un confronto più ampio su 7 workload diversi (status polling, tool use,
narrative, ETL, broadcast, DB query, mixed) × 4 lunghezze (10/50/100/500 msg)
con pricing $ e latency, vedi
[`benchmarks/comprehensive_report.md`](benchmarks/comprehensive_report.md).
Generabile con:

​```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
​```
```

(NOTA: i `​` sono zero-width characters per evitare nested code fence collision — sostituire con i veri backtick triple nello step.)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): link al comprehensive benchmark report"
```

---

## Self-review (post-stesura del plan)

**1. Spec coverage:**

| Spec requirement | Task |
|---|---|
| a) 6 workload type | Task 1 (5 spec + mixed) |
| b) Sweep lunghezze 10/50/100/500 | Task 3 (`LENGTHS`) |
| c) Mixed payload | Task 1 (`mixed` generator) |
| d) Pricing $ per provider | Task 2, 4 |
| e) Performance encode/decode | Task 3 (`_measure_*`), Task 4 (report) |
| f) TOON head-to-head | Task 3 (encoders list), Task 4 (Δ vs TOON table) |

Tutto coperto.

**2. Placeholder scan:** nessun TBD/TODO.

**3. Type consistency:**

- `WORKLOADS: dict[str, Callable]` consistente
- `_measure_*` funzioni ritornano dict con stesse chiavi
- `run_workload` ritorna `dict[encoder_name, metrics_dict]`
- `all_results: dict[workload, dict[length, dict[encoder, metrics]]]`
- Pricing functions consistenti

Nessuna divergenza.

## Note per future estensioni

- Plot grafici (matplotlib): out of scope, ma facile aggiungerli leggendo `comprehensive_results.json`
- Multi-tokenizer comparison (o200k_base, claude tokenizer reale): out of scope v1
- Memory profiling: out of scope, ma `tracemalloc` integrabile in `_measure_*`
- Distributed bench (workers paralleli per workload): nice-to-have ma non priorità
