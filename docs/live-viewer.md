# ADP Live Viewer — Dynamic HTML via SSE

> Purpose: how to use `adp serve` to stream ADP records to a browser in real time using Server-Sent Events, with zero dependencies.
> Back to [main README](../README.md)

---

## Overview

For scenarios where an agent emits ADP records as a continuous stream (logs,
monitoring, multi-step output), the `adp serve` subcommand starts a small HTTP
server that opens a **single page** auto-updated via Server-Sent Events: each
new record is rendered and appended at the bottom without reloading the page.

```bash
my-agent-emitting-adp | uv run adp serve --port 8000
# Apri http://localhost:8000 nel browser; la pagina si aggiorna in tempo reale
```

![Live viewer SSE](img/live-viewer.png)

---

## Features

- zero dependencies (uses only stdlib `http.server`)
- chronological page with a timestamp for each record
- automatic backfill of records already received if the browser is opened late
- live/disconnected indicator in the bottom right corner
- record counter in the header
- maintains auto-scroll to the bottom as new data arrives

---

## Typical use cases

- long-running agent monitoring
- multi-step pipeline debugging
- development dashboards
- client demos

---

## Notes

Bytes in the JSON pass-through are encoded as
`{"_adp_bytes": "<base64>"}` to preserve them.

The HTML output uses `adp.to_html()` for each record, which produces
a complete styled fragment with embedded CSS, bordered tables, automatic
light/dark switching via `prefers-color-scheme`, tooltips on bytes,
and code blocks for multiline text.
