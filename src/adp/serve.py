"""Live HTML viewer per ADP — pagina dinamica append-only.

Server HTTP minimale (zero dipendenze) che:
1. Legge record ADP da stdin (uno per riga o separati da ';')
2. Espone una pagina HTML che si aggiorna automaticamente via SSE
3. Ogni nuovo record viene renderizzato e accodato in fondo alla pagina

Uso tipico:
    my-agent-emitting-adp | uv run adp serve --port 8000
    # apri http://localhost:8000

Il server non scrive nulla su disco: tutto in memoria. Quando si chiude,
la cronologia va persa.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from adp.converters import to_html, _HTML_CSS    # noqa: F401  (riuso CSS)
from adp.parser import decode, ADPParseError


# In-memory log of (timestamp, html_fragment) tuples
_HISTORY: list[tuple[float, str]] = []
_HISTORY_LOCK = threading.Lock()
_SUBSCRIBERS: list[queue.Queue] = []
_SUBSCRIBERS_LOCK = threading.Lock()


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__
.adp-log-entry {
  margin: 24px 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
}
.adp-log-entry .ts {
  font-size: 11px;
  color: var(--muted);
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
#adp-status {
  position: fixed;
  bottom: 12px;
  right: 12px;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 12px;
  background: var(--code-bg);
  color: var(--muted);
  border: 1px solid var(--border);
  z-index: 1000;
}
#adp-status.live { color: #16a34a; }
#adp-status.err { color: #dc2626; }
.adp-empty {
  text-align: center;
  padding: 80px 20px;
  color: var(--muted);
}
</style>
</head>
<body>
<main>
<header class="adp-header">
  <h1>__TITLE__</h1>
  <div class="meta">live stream &middot; <span id="adp-count">0</span> records</div>
</header>
<div id="adp-log">
  <div class="adp-empty">In attesa di record ADP&hellip;</div>
</div>
</main>
<div id="adp-status">connecting&hellip;</div>
<script>
(function() {
  var log = document.getElementById('adp-log');
  var count = document.getElementById('adp-count');
  var status = document.getElementById('adp-status');
  var n = 0;
  var empty = log.querySelector('.adp-empty');

  function setStatus(s, cls) {
    status.textContent = s;
    status.className = cls || '';
  }

  var es = new EventSource('/stream');

  es.onopen = function() { setStatus('live', 'live'); };
  es.onerror = function() { setStatus('disconnected', 'err'); };

  es.addEventListener('record', function(e) {
    if (empty && empty.parentNode) { empty.parentNode.removeChild(empty); empty = null; }
    try {
      var payload = JSON.parse(e.data);
      var div = document.createElement('div');
      div.className = 'adp-log-entry';
      div.innerHTML = '<div class="ts">' + payload.ts + '</div>' + payload.html;
      log.appendChild(div);
      n += 1;
      count.textContent = n;
      window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    } catch(err) {
      console.error('record parse error', err);
    }
  });

  // Initial backfill: server may have queued history
  fetch('/history').then(function(r) { return r.json(); }).then(function(items) {
    if (items.length === 0) return;
    if (empty && empty.parentNode) { empty.parentNode.removeChild(empty); empty = null; }
    items.forEach(function(payload) {
      var div = document.createElement('div');
      div.className = 'adp-log-entry';
      div.innerHTML = '<div class="ts">' + payload.ts + '</div>' + payload.html;
      log.appendChild(div);
      n += 1;
    });
    count.textContent = n;
    window.scrollTo(0, document.body.scrollHeight);
  });
})();
</script>
</body>
</html>
"""


def _ingest_records_from_stdin() -> None:
    """Background thread: reads stdin, parses ADP records, fans out via SSE.

    Accepts:
    - one ADP document per line (newline-delimited)
    - empty lines ignored
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            html_fragment = to_html(line, standalone=False)
        except ADPParseError as e:
            html_fragment = (
                f'<div style="color:#dc2626"><strong>Parse error:</strong> '
                f'{e}</div><pre style="font-size:12px">{line[:500]}</pre>'
            )
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        payload = {"ts": ts, "html": html_fragment}
        with _HISTORY_LOCK:
            _HISTORY.append((time.time(), payload))
        with _SUBSCRIBERS_LOCK:
            dead = []
            for q in _SUBSCRIBERS:
                try:
                    q.put_nowait(payload)
                except Exception:
                    dead.append(q)
            for q in dead:
                try:
                    _SUBSCRIBERS.remove(q)
                except ValueError:
                    pass


class _Handler(BaseHTTPRequestHandler):
    page_title: str = "ADP live"

    def log_message(self, fmt, *args):
        # Silenzio i log per non sporcare la stdout dell'agente
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            self._serve_page()
        elif self.path == "/history":
            self._serve_history()
        elif self.path == "/stream":
            self._serve_stream()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_page(self) -> None:
        body = (
            _PAGE_TEMPLATE
            .replace("__TITLE__", self.page_title)
            .replace("__CSS__", _HTML_CSS)
        )
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _serve_history(self) -> None:
        with _HISTORY_LOCK:
            items = [payload for (_, payload) in _HISTORY]
        body = json.dumps(items).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q: queue.Queue = queue.Queue(maxsize=1024)
        with _SUBSCRIBERS_LOCK:
            _SUBSCRIBERS.append(q)
        try:
            # Keep-alive pings every 15 s
            last_ping = time.time()
            while True:
                try:
                    payload = q.get(timeout=1.0)
                    data = json.dumps(payload)
                    self.wfile.write(f"event: record\ndata: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    pass
                if time.time() - last_ping > 15:
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    last_ping = time.time()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _SUBSCRIBERS_LOCK:
                try:
                    _SUBSCRIBERS.remove(q)
                except ValueError:
                    pass


def run_live_server(*, host: str = "127.0.0.1", port: int = 8765,
                    title: str = "ADP live stream") -> None:
    """Avvia il server live finché stdin non chiude o l'utente interrompe."""
    _Handler.page_title = title
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"ADP live viewer → http://{host}:{port}", file=sys.stderr)
    print("Invia record ADP su stdin, uno per riga (Ctrl-D per terminare).",
          file=sys.stderr)

    ingest_thread = threading.Thread(target=_ingest_records_from_stdin, daemon=True)
    ingest_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.", file=sys.stderr)
        server.shutdown()
