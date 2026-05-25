---
description: Verify integrity trailer of an ADP document (exit 1 if tampered)
argument-hint: "[--key STR | --key-file PATH] [file.adp]"
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read
disable-model-invocation: false
---

Validate the integrity trailer of a signed ADP document. If the
checksum matches, the original clean ADP is emitted on stdout. If the
message was modified in transit, the command exits with code 1 and
prints `INTEGRITY FAILURE: ...` to stderr.

```bash
adp verify < signed.adp

# For HMAC-signed messages:
adp verify --key-file ~/.adp-key < signed.adp

# To strip the trailer WITHOUT verifying (NOT recommended):
adp verify --strip-only < signed.adp
```

If the message has no trailer, the command fails by default. Use
`--no-strict` to accept unsigned messages silently.

After verification, you can pipe directly to `/adp-decode` or
`/adp-to-md` to inspect the content.
