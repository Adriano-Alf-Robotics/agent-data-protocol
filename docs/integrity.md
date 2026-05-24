# ADP Integrity — Sign / Verify

> Purpose: how to detect accidental corruption or intentional LLM-in-the-middle alterations using `adp.integrity` (CRC32 / SHA-256 / HMAC).
> Back to [main README](../README.md)

---

## Overview

ADP at its base does not protect a message in transit: it only guarantees
semantic round-trip (`decode(encode(x)) == x`). To detect accidental
corruption or intentional modifications (including alterations produced by an
intermediary LLM), the library provides the optional `adp.integrity` module,
which appends a trailer of the form `;_chk=<algo>:<hex>` to the message.

---

## Three available algorithms

| Algorithm | Hex | Token overhead | Strength | Ideal case |
|---|---:|---:|---|---|
| `crc32` | 8 chars | ~+12 tokens | casual corruption detection | already authenticated channel (TLS), robustness only |
| `sha256` | 64 chars | ~+42 tokens | cryptographic detection | LLM in the middle (may alter text) |
| `hmac` | 64 chars | ~+42 tokens | detection + sender authenticity | multi-agent fleets with shared key |

The overhead is **constant** (it does not scale with payload length), so it is
proportionally more expensive on small messages and negligible on large ones.

---

## Python API

```python
import adp

msg = adp.encode({"task": "transfer", "amount": 100.0, "to": "alice"})

# CRC32 — economico
signed = adp.integrity.sign(msg, algo="crc32")
# task=transfer;amount=100.0;to=alice;_chk=crc32:6b4d2817

# SHA-256 — robusto contro modifiche dell'LLM
signed = adp.integrity.sign(msg, algo="sha256")

# HMAC — anche autenticità
signed = adp.integrity.sign(msg, algo="hmac", key=b"shared-secret")

# Verifica: ritorna messaggio pulito, oppure solleva IntegrityError
clean = adp.integrity.verify(signed, key=b"shared-secret")
data = adp.decode(clean)
```

---

## CLI usage

```bash
# Firma da pipeline
echo '{"task":"transfer","amount":100.0,"to":"alice"}' \
  | uv run adp encode \
  | uv run adp sign --algo sha256
# task=transfer;amount=100.0;to=alice;_chk=sha256:8cb2afe81e13b004...

# Round-trip integro
echo '{"x":42}' | uv run adp encode | uv run adp sign | uv run adp verify
# x=42  (exit 0)

# Tampering rilevato (exit code 1)
echo '{"x":42}' | uv run adp encode | uv run adp sign \
  | sed 's/42/99/' | uv run adp verify
# INTEGRITY FAILURE: sha256 mismatch...   (exit 1)

# HMAC con chiave da file (preferito per i secrets)
echo 'shared-secret' > /tmp/k.key
echo '{"x":1}' | uv run adp encode | uv run adp sign --algo hmac --key-file /tmp/k.key
echo '<msg>' | uv run adp verify --key-file /tmp/k.key
```

`adp sign` options:
- `--algo crc32|sha256|hmac` (default `sha256`)
- `--key STRING` inline HMAC key (visible in shell history)
- `--key-file PATH` HMAC key from file (recommended)

`adp verify` options:
- `--key` / `--key-file` for HMAC
- `--strict/--no-strict` whether to require the presence of the trailer
- `--strip-only` removes the trailer without verifying it (not recommended)

---

## Most relevant use case: LLM alteration detection

When an agent communicates through an intermediary LLM, the model **can
silently modify** the message: change whitespace, alter an escape character,
add or remove a character. Without a checksum the receiver does not notice, and
the corrupted data continues through the pipeline.

```
Agent A → encode → sign(sha256) → LLM B (forward) → verify → Agent C
                                       │
                                       └─ se modifica anche 1 byte
                                          → IntegrityError lato C
```

In environments where the LLM is only a message router/orchestrator, signing
with SHA-256 is the standard way to ensure the payload arrives intact. For
sender authenticity (not just integrity), use HMAC with an out-of-band shared
key.

---

## When it is NOT needed

| Channel | Built-in integrity? | Need `adp.integrity`? |
|---|---|---|
| HTTPS / gRPC / TLS | yes (TLS) | no (redundant) |
| File on shared disk | no | yes (CRC32 is enough) |
| Message queue (Redis, RabbitMQ) | no | yes (CRC32 or SHA-256) |
| **LLM in the middle** (agent → LLM → agent) | **NO** | **yes, SHA-256 or HMAC** |
| Long-term storage (audit log) | no | yes (SHA-256 for bit-rot) |
