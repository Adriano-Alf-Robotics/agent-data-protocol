"""Benchmark comparativo ADP vs JSON/YAML/TOML/MsgPack/XML/CSV.

Produce un report Markdown con:
- tabella metriche per ogni payload (bytes, token cl100k/o200k, tempo enc/dec, lossless)
- esempi concreti del payload codificato in ogni formato
- delta % rispetto a JSON-min e JSON-pretty

Esegui:
    uv run python -m benchmarks.compare_formats
    uv run python -m benchmarks.compare_formats --out benchmarks/results.md
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import tiktoken

from benchmarks.payloads import PAYLOADS
from benchmarks.encoders import all_formats


REPEAT = 200  # iterations for timing


@dataclass
class Result:
    payload: str
    fmt: str
    bytes_: int
    tokens_cl100k: int
    tokens_o200k: int
    enc_us: float        # microseconds, median
    dec_us: float | None
    lossless: bool
    note: str = ""
    sample: str = ""


def _time_us(fn: Callable[[], Any], repeat: int = REPEAT) -> float:
    """Median execution time in microseconds across `repeat` runs."""
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        times.append((t1 - t0) / 1000.0)  # ns -> us
    return statistics.median(times)


def _bench_one(
    name: str,
    fmt_name: str,
    encoder: Callable[[dict[str, Any]], str],
    decoder: Callable[[str], dict[str, Any]] | None,
    lossless_marked: bool,
    payload: dict[str, Any],
    enc_cl100k: tiktoken.Encoding,
    enc_o200k: tiktoken.Encoding,
) -> Result:
    try:
        encoded = encoder(payload)
    except Exception as e:
        return Result(name, fmt_name, 0, 0, 0, 0.0, None, False, f"N/A ({type(e).__name__})", "")

    bytes_ = len(encoded.encode("utf-8"))
    tok_cl = len(enc_cl100k.encode(encoded))
    tok_o = len(enc_o200k.encode(encoded))

    enc_us = _time_us(lambda: encoder(payload))

    dec_us: float | None = None
    lossless = False
    note = ""
    if decoder is not None:
        try:
            back = decoder(encoded)
            lossless = (back == payload) and lossless_marked
            dec_us = _time_us(lambda: decoder(encoded))
            if not lossless and lossless_marked:
                note = "decoded != original"
        except Exception as e:
            note = f"decode failed: {type(e).__name__}"
    else:
        note = "no decoder (one-way)"

    return Result(
        payload=name,
        fmt=fmt_name,
        bytes_=bytes_,
        tokens_cl100k=tok_cl,
        tokens_o200k=tok_o,
        enc_us=enc_us,
        dec_us=dec_us,
        lossless=lossless,
        note=note,
        sample=encoded,
    )


def run_all() -> list[Result]:
    enc_cl100k = tiktoken.get_encoding("cl100k_base")
    enc_o200k = tiktoken.get_encoding("o200k_base")
    fmts = all_formats()
    results: list[Result] = []
    for pname, payload in PAYLOADS.items():
        for fmt_name, enc, dec, lossless_marked in fmts:
            r = _bench_one(pname, fmt_name, enc, dec, lossless_marked, payload, enc_cl100k, enc_o200k)
            results.append(r)
    return results


def _safe_pct(numerator: float, baseline: float) -> str:
    if baseline <= 0:
        return "—"
    pct = (baseline - numerator) / baseline * 100.0
    return f"{pct:+.1f}%"


def _fmt_us(v: float | None) -> str:
    if v is None:
        return "—"
    if v < 1:
        return f"{v*1000:.0f}ns"
    if v < 1000:
        return f"{v:.1f}µs"
    return f"{v/1000:.2f}ms"


def render_markdown(results: list[Result]) -> str:
    by_payload: dict[str, list[Result]] = {}
    for r in results:
        by_payload.setdefault(r.payload, []).append(r)

    parts: list[str] = []
    parts.append("# ADP — Analisi Comparativa vs Formati Esistenti")
    parts.append("")
    parts.append(f"Repeat per misura tempo: **{REPEAT}** esecuzioni (mediana).")
    parts.append("Token count via `tiktoken`: `cl100k_base` (GPT-4 / Claude 3.x) e `o200k_base` (GPT-4o / Opus 4.x).")
    parts.append("Tempi in µs (microsecondi) — encoding e decoding di un singolo payload Python in-memory.")
    parts.append("")
    parts.append("## Indice")
    for pname in by_payload:
        parts.append(f"- [{pname}](#{pname.replace('_', '-')})")
    parts.append("")
    parts.append("## Sintesi globale — risparmio token ADP vs JSON-min")
    parts.append("")
    parts.append("| Payload | JSON-min tok | ADP tok | ADP+LUT tok | Δ ADP cl100k | Δ ADP+LUT cl100k |")
    parts.append("|---------|-------------:|--------:|------------:|-------------:|-----------------:|")
    for pname, rows in by_payload.items():
        adp = next((r for r in rows if r.fmt == "ADP"), None)
        adp_lut = next((r for r in rows if r.fmt == "ADP+LUT"), None)
        jsm = next((r for r in rows if r.fmt == "JSON-min"), None)
        if adp and jsm and jsm.tokens_cl100k > 0:
            d_cl = _safe_pct(adp.tokens_cl100k, jsm.tokens_cl100k)
            d_lut = _safe_pct(adp_lut.tokens_cl100k, jsm.tokens_cl100k) if adp_lut and adp_lut.tokens_cl100k else "—"
            lut_tok = adp_lut.tokens_cl100k if adp_lut and adp_lut.tokens_cl100k else "—"
            parts.append(f"| {pname} | {jsm.tokens_cl100k} | {adp.tokens_cl100k} | {lut_tok} | {d_cl} | {d_lut} |")
    parts.append("")

    for pname, rows in by_payload.items():
        parts.append(f"## {pname}")
        parts.append("")
        baseline = next((r for r in rows if r.fmt == "JSON-min"), None)
        bl_tok = baseline.tokens_cl100k if baseline else 0

        parts.append("| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |")
        parts.append("|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|")
        for r in rows:
            if r.bytes_ == 0:
                parts.append(f"| {r.fmt} | — | — | — | — | — | — | — | {r.note} |")
                continue
            delta = _safe_pct(r.tokens_cl100k, bl_tok) if bl_tok else "—"
            ll = "✓" if r.lossless else ("—" if "no decoder" in r.note else "✗")
            parts.append(
                f"| {r.fmt} | {r.bytes_} | {r.tokens_cl100k} | {r.tokens_o200k} | {delta} | "
                f"{_fmt_us(r.enc_us)} | {_fmt_us(r.dec_us)} | {ll} | {r.note or ''} |"
            )
        parts.append("")

        parts.append("### Esempi codificati")
        parts.append("")
        for r in rows:
            if not r.sample:
                continue
            sample = r.sample
            # Avoid runaway examples; cap length but show start
            if len(sample) > 1200:
                sample = sample[:1200] + "\n... [troncato]"
            lang = "json" if r.fmt.startswith("JSON") else (
                "yaml" if r.fmt == "YAML" else (
                    "toml" if r.fmt == "TOML" else (
                        "xml" if r.fmt == "XML" else "text"
                    )
                )
            )
            parts.append(f"#### {r.fmt}")
            parts.append("")
            parts.append(f"```{lang}")
            parts.append(sample.rstrip("\n"))
            parts.append("```")
            parts.append("")
        parts.append("---")
        parts.append("")

    parts.append("## Note metodologiche")
    parts.append("")
    parts.append("- **Lossless** = `decode(encode(obj)) == obj` su tipi Python nativi. XML manca di decoder (encoder best-effort); CSV non rappresenta strutture annidate; MsgPack è binario, qui base64-encoded per il canale testuale tipico LLM.")
    parts.append("- **Δ vs JSON-min** = riduzione percentuale token rispetto a JSON minified. Positivo = ADP risparmia token.")
    parts.append("- **Tempi enc/dec**: misurati con `time.perf_counter_ns()`, ripetuti 200 volte, mediana. Riflettono CPU-only, in-memory: nessun I/O, nessuna rete. Significativi solo per confronti relativi sulla stessa macchina.")
    parts.append("- **Tempi di trasferimento di rete**: proporzionali ai bytes. Esempio: su un canale a 1 Mbit/s reale, 1 KB ≈ 8 ms. La colonna `Bytes` è il proxy diretto del costo trasferimento.")
    parts.append("- **IT vs EN**: i tokenizer LLM hanno vocabolari prevalentemente inglesi. Lo stesso contenuto in italiano genera tipicamente 15-40% token in più rispetto all'inglese. ADP mantiene il vantaggio strutturale (riduzione overhead di sintassi) indipendentemente dalla lingua.")
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="benchmarks/results.md", help="Output markdown file")
    args = ap.parse_args()
    print("Running benchmarks...", file=sys.stderr)
    results = run_all()
    md = render_markdown(results)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote {out_path} ({len(md)} chars)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
