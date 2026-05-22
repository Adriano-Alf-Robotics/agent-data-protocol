---
description: Start a live HTML viewer (append-only, SSE) for streaming ADP records
argument-hint: [--port 8000] [--host 127.0.0.1] [--title "..."]
allowed-tools: Bash(adp:*), Bash(uv run adp:*)
disable-model-invocation: false
---

Start a tiny HTTP server that opens a single HTML page in the browser
auto-updating via Server-Sent Events. Each ADP record arriving on stdin
is rendered as an HTML fragment and appended to the bottom of the page.

```bash
my-agent-emitting-adp | adp serve --port 8000
# Open http://localhost:8000 in your browser
```

Use cases:
- live monitoring of a long-running agent
- debugging a multi-step pipeline
- quick dashboard during development
- demo to a non-technical stakeholder

The page shows: header with record count, timestamped log entries,
a live/disconnected indicator at the bottom right, automatic scroll to
new content.

Server is single-process, zero-deps, in-memory only (history is lost
when the server stops). Bind to `--host 0.0.0.0` to make it
network-accessible (be mindful of security on shared networks).
