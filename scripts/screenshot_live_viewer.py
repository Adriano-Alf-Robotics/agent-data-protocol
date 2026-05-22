#!/usr/bin/env python3
"""Genera lo screenshot del live viewer ADP per il README.

Avvia `adp serve` in background, emette quattro record ADP demo via stdin,
attende il rendering e cattura uno screenshot via Chromium headless gestito
da Playwright (isolato in cache utente, niente install di sistema).

Esecuzione:
    uv run --with playwright python scripts/screenshot_live_viewer.py

Pre-requisito una tantum (scarica il binario Chromium ~150 MB in
~/.cache/ms-playwright/):
    uv run --with playwright python -m playwright install chromium

Output: docs/img/live-viewer.png
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "ERRORE: playwright non disponibile. Esegui con:\n"
        "  uv run --with playwright python scripts/screenshot_live_viewer.py",
        file=sys.stderr,
    )
    sys.exit(1)

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img" / "live-viewer.png"

DEMO_RECORDS = [
    "task=encode;status=ok;input_size=1024;output_size=387;ratio=0.378",
    "agent=planner;step=1;intent=decompose;subtasks=[parse,validate,emit]",
    "users=#id,name,role|1i,alice,admin|2,bob,dev|3,carol,qa",
    "result=success;duration_ms=234;tokens={in=512;out=87}",
]


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    server = subprocess.Popen(
        ["uv", "run", "adp", "serve", "--port", str(PORT)],
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=str(ROOT),
    )
    try:
        time.sleep(1.2)  # tempo per binding del socket
        assert server.stdin is not None
        for rec in DEMO_RECORDS:
            server.stdin.write(rec + "\n")
            server.stdin.flush()
            time.sleep(0.2)
        time.sleep(0.6)  # buffer per SSE + render

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 900})
                page.goto(URL, wait_until="networkidle", timeout=10_000)
                page.wait_for_selector(".adp-log-entry", timeout=5_000)
                page.wait_for_timeout(800)  # smooth-scroll completion
                page.screenshot(path=str(OUT), full_page=False)
            finally:
                browser.close()
    finally:
        if server.stdin is not None:
            try:
                server.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()

    if not OUT.exists() or OUT.stat().st_size < 1000:
        print(f"ERRORE: screenshot non generato o troppo piccolo ({OUT})",
              file=sys.stderr)
        return 1

    print(f"Screenshot salvato: {OUT} ({OUT.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
