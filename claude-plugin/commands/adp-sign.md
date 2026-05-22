---
description: Append integrity trailer (CRC32 / SHA-256 / HMAC) to an ADP document
argument-hint: [--algo crc32|sha256|hmac] [--key STR | --key-file PATH] [file.adp]
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read
disable-model-invocation: false
---

Append a `;_chk=<algo>:<hex>` trailer to an ADP message so the
recipient can detect tampering or corruption.

```bash
# Default: SHA-256
adp sign < msg.adp

# Lightweight CRC32 (~12 token overhead, only catches casual corruption)
adp sign --algo crc32 < msg.adp

# HMAC with shared secret (also authenticates the sender)
adp sign --algo hmac --key-file ~/.adp-key < msg.adp
```

Use SHA-256 when the message passes through an LLM that may alter it,
HMAC when authenticity matters, CRC32 when the channel is already
trusted (TLS) and only fast corruption detection is needed.

To verify the trailer on the receiving side: `/adp-verify`.
