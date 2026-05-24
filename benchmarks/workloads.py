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
