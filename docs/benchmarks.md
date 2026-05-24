# ADP Benchmarks — Token Reduction & Comparisons

> Purpose: detailed token reduction measurements, side-by-side format comparisons, and comprehensive multi-workload benchmark results.
> Back to [main README](../README.md)

---

## Measured token reduction

`cl100k_base` tokenizer (Claude 3.x / GPT-4), comparison vs JSON-min:

| Payload | JSON-min (tok) | ADP (tok) | Δ cl100k | Δ o200k |
|---|---:|---:|---:|---:|
| short_string_en | 15 | 13 | **+13.3%** | +13.3% |
| short_string_it | 18 | 16 | **+11.1%** | +11.8% |
| long_text_en | 115 | 109 | +5.2% | +5.3% |
| long_text_it | 176 | 170 | +3.4% | +3.7% |
| special_chars_en | 92 | 89 | +3.3% | +3.4% |
| special_chars_it | 134 | 131 | +2.2% | +2.4% |
| **tabular_en** | **241** | **145** | **+39.8%** | +40.1% |
| **tabular_it** | **333** | **164** | **+50.8%** | +46.4% |
| database_en | 150 | 134 | +10.7% | +10.5% |
| database_it | 180 | 157 | +12.8% | +12.8% |
| agent_task_en | 88 | 83 | +5.7% | +6.8% |
| agent_task_it | 118 | 113 | +4.2% | +5.0% |
| **contacts_en** (URL/email) | **145** | **94** | **+35.2%** | +34.9% |
| **nested_table_en** (nested cells) | **100** | **75** | **+25.0%** | +30.3% |
| binary_en | (JSON N/A) | 279 | — | — |

With `DEFAULT_AGENT_LUT` on `agent_task_en`, savings rise from +5.7% to **+13.6%**.

Reading guide: ADP wins significantly where the structure is a homogeneous
table or contains many URLs/emails (extended bare strings), and on binary data
where JSON does not work at all. On free text the savings are modest but always
positive. On nested-table-with-cells (the typical case for multi-agent messages
with sub-structures), the gain is 25–30%.

The full file is at
[`benchmarks/results.md`](../benchmarks/results.md). To regenerate it:

```bash
uv run python -m benchmarks.compare_formats
```

### Native bytes: structural advantage

On the `binary_en` payload (256-byte image) the results are:

| Format | Bytes | Token cl100k | Lossless | Notes |
|---|---:|---:|:---:|---|
| **ADP** | **412** | **279** | ✓ | native bytes via `b!base64` |
| JSON-min | — | — | — | TypeError: bytes not serializable |
| JSON-pretty | — | — | — | TypeError: bytes not serializable |
| TOML | — | — | — | TypeError: bytes not serializable |
| YAML | 460 | 299 | ✓ | requires !!binary tag |
| MsgPack-b64 | 428 | 309 | ✓ | binary base64-encoded |
| XML | 908 | 469 | — | one-way, str(bytes) |

ADP is one of the few text formats that handles bytes losslessly without custom
adapters, and it is the cheapest in terms of tokens.

### Important note: you pay for what the model EMITS, not what the user sees

LLM providers (Anthropic, OpenAI, ...) charge **output tokens based on what the
model emits**, not on what the UI displays. The difference is non-trivial:

| What the model emits | Billed | Seen by user |
|---|:---:|:---:|
| Final response text | ✓ | ✓ |
| `thinking` / `reasoning` block (Claude 4, o1, o3) | **✓** | ✗ hidden |
| JSON arguments of tool calls | **✓** | partial |
| Raw Markdown characters (`**`, `##`, `|`) | ✓ | ✗ (rendered) |
| Tokens emitted before stop sequence | ✓ | ✗ |

This asymmetry is **good news for ADP**: asking the model to emit ADP (dense,
few tokens) and then converting it client-side to Markdown or pretty JSON
produces the same user experience at a significantly lower cost.

```
Model emits ADP  ──── you pay few tokens  (output_tokens API)
        │
        └── client converts with adp.to_markdown()  ── zero cost
                                       │
                                       └── user sees rich output
```

Verify in the API response:

```python
resp = client.messages.create(model="claude-opus-4-7", ...)
print("output_tokens:", resp.usage.output_tokens)
# include thinking + tool_use + text — non solo ciò che renderizzi
```

On models with extended thinking, the internal reasoning can account for 50–90%
of output tokens. If the reasoning is verbose (e.g., intermediate JSON), you
pay for all of it, even though it is not displayed.

---

## Side-by-side examples

Same nested-table payload (4 users with roles and permissions):

### ADP — 75 tokens, 159 bytes

```
users=#id,name,roles,perms|1i,alice,[admin,ops],{read=1;write=1}|2,bob,[dev],{read=1;write=0}|3,carol,[dev,qa],{read=1;write=0}|4,dan,[viewer],{read=1;write=0}
```

### JSON-min — 100 tokens, 326 bytes

```json
{"users":[{"id":1,"name":"alice","roles":["admin","ops"],"perms":{"read":true,"write":true}},{"id":2,"name":"bob","roles":["dev"],"perms":{"read":true,"write":false}},{"id":3,"name":"carol","roles":["dev","qa"],"perms":{"read":true,"write":false}},{"id":4,"name":"dan","roles":["viewer"],"perms":{"read":true,"write":false}}]}
```

### YAML — 135 tokens, 342 bytes

```yaml
users:
- id: 1
  name: alice
  roles:
  - admin
  - ops
  perms:
    read: true
    write: true
- id: 2
  name: bob
  ...
```

### CSV — 88 tokens (wins marginally but loses structure)

```csv
id,name,roles,perms
1,alice,"['admin', 'ops']","{'read': True, 'write': True}"
...
```

CSV "wins" on tokens only because it drowns sub-structures in non-parseable
strings: the semantic round-trip fails. ADP preserves the native structure.

---

## Comprehensive benchmark: 7 workloads × 4 lengths

Beyond the single benchmark above, a broader suite covers seven different
workloads (status polling, tool use, narrative, ETL pipeline, broadcast,
DB query, mixed) at four conversation lengths (10/50/100/500 messages), with
estimated cost in $ per provider and encode/decode latency.

Summary @ 100 messages per workload — ADP full stack vs TOON (best competitor):

| Workload | Δ vs TOON | Savings $ per 1k msg (Sonnet 4.6) |
|---|---:|---:|
| status_polling | **+61.1%** | $0.156 |
| etl_pipeline | **+60.2%** | $2.61 |
| mixed | **+49.8%** | $0.418 |
| db_query_response | **+18.8%** | $0.114 |
| tool_use | **+15.3%** | $0.019 |
| multi_agent_broadcast | **+11.3%** | $0.015 |
| long_narrative | +1.3% | $0.003 |

The gain is highest on workloads with high inter-message similarity (status
polling) or strong tabular structure (ETL pipeline). On free-prose text
(long_narrative) the margin is minimal because diff/dynamic LUT have little
recurring material to capture.

Full report with all lengths, latency, pricing per provider:
[`benchmarks/comprehensive_report.md`](../benchmarks/comprehensive_report.md).

To regenerate:

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

The main gain comes from diff encoding: on request/reply patterns with similar
payloads between consecutive messages, the delta is a tiny fraction of the full
payload. The dynamic LUT cold-start alone is not particularly competitive
because the static LUT already covers most frequent patterns — the real added
value is the combination with diff and dynamic specialization on the session
vocabulary.

To regenerate the dynamic LUT benchmark specifically:

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
```
