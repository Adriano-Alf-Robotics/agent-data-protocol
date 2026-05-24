# Dynamic LUT (HPACK-style) + Differential Encoding

> Purpose: complete reference for `ADPSession`, the adaptive compression layer that achieves 56–60% token reduction vs JSON on multi-turn agent workloads.
> Back to [main README](../README.md)

---

## LUT — Shared Look-Up Table (static, optional)

If sender and receiver share a **LUT** (abbreviation table), recurring keys
are compressed to 1–2 characters during encoding and restored during decoding.
The final message is no longer textually readable but remains lossless and
passes through the same parser.

```python
import adp

LUT = {"user": "u", "id": "i", "name": "n", "email": "em"}
obj = {"user": {"id": 42, "name": "Adriano", "email": "a@b.c"}}

s = adp.encode(obj, key_lut=LUT)
# 'u={i=42;n=Adriano;em=a@b.c}'        (vs 'user={id=42;name=Adriano;email=a@b.c}')

assert adp.decode(s, key_lut=LUT) == obj
```

The library exposes `adp.DEFAULT_AGENT_LUT`, a pre-packaged LUT for typical
inter-agent message field names (`msg_id`, `from_agent`, `intent`, `payload`,
`id`, `name`, `status`, `value`, ...). On an inter-agent task message, savings
grow from +5.7% (ADP alone) to **+13.6%** (ADP+LUT) on cl100k_base tokens.

LUT constraints: keys and abbreviations must be valid identifiers
`[A-Za-z_][A-Za-z0-9_-]*`; abbreviations cannot coincide with reserved literals
(`~`, `0`, `1`, `0i`, `1i`). `adp.validate_lut(lut)` checks both requirements.

---

## Dynamic LUT (HPACK-style) + Differential Encoding

The static LUT requires that sender and receiver share the same abbreviation
dictionary in advance. For scenarios where agents cannot coordinate beforehand,
or where the vocabulary is specific to the conversation domain, ADP provides
`ADPSession`: an **adaptive HPACK-style dynamic LUT** (modeled on HTTP/2 header
compression, RFC 7541) that **grows synchronously during the session** via
in-band updates, and a **differential inter-message encoding** that sends only
the delta relative to the previous message when it is advantageous to do so.

The two techniques are orthogonal and composable: on the same 20-message
agent-to-agent workload, the combination `static LUT + dynamic LUT + diff
encoding` (full stack) reduces tokens by **56.9% relative to JSON-min** and
**60.1% relative to TOON** (best competitor).

### Basic usage

```python
import adp

session = adp.ADPSession()   # carica/crea ~/.adp/lut_state.json

# Mittente A
msg = session.encode({
    "user": {"id": 42, "role": "administrator", "dept": "engineering"},
    "user2": {"id": 43, "role": "administrator", "dept": "engineering"},
})
# msg contiene un prefisso _lut_add={...} con le nuove sigle dinamiche,
# poi il payload sostituito con quelle sigle.

# Destinatario B (con la propria ADPSession)
obj = session.decode(msg)
# Lo stato LUT di entrambi è ora sincronizzato dopo la decodifica.
```

The state grows with every exchanged message. Automatic local persistence in
`~/.adp/lut_state.json` (override via the `path=` parameter or the
`ADP_LUT_PATH` env variable). LRU bounded to 256 entries by default. Pure
stdlib, zero new dependencies.

### In-band syntax

ADPSession emits three reserved top-level prefixes at the start of each message:

| Prefix | Meaning |
|---|---|
| `_lut_add={alias=fullname;...}` | adds new entries to the dynamic LUT |
| `_lut_reset=1` | completely clears the receiver's dynamic LUT |
| `_base=ID;_diff={set=...;del=[...]}` | applies a diff to the baseline ID |

Dynamic aliases use the reserved namespace `_N` (underscore + digits),
disjoint from the short letters of the static LUT. Deterministic side-local LRU
eviction: sender and receiver evict identically because they observe the same
insertions and the same accesses.

> **⚠️ Reserved namespace:** dynamic LUT aliases use the `_N` pattern (underscore + digits). User payloads with keys or values matching `_\d+` (e.g. `{"_0": "literal"}`) will raise `ADPLUTSyncError` on decode. Avoid this pattern in your payloads.

### Differential encoding

When two consecutive messages in the same direction share most of their fields
(a typical pattern: status reports, incremental results, state updates),
`ADPSession` computes the diff and sends only the changes:

```python
sender = adp.ADPSession()
receiver = adp.ADPSession()

msg1 = sender.encode({"task_id": "t1", "user": {"id": 42, "role": "administrator"}})
receiver.decode(msg1)

# Secondo messaggio: cambia solo task_id, user resta uguale
msg2 = sender.encode({"task_id": "t2", "user": {"id": 42, "role": "administrator"}})
# msg2 ≈ "_base=a3f2;_diff={set={task_id=t2}};"
# molto più corto del payload completo
receiver.decode(msg2)
```

The encoder automatically evaluates when to emit a diff: only if the encoded
diff is smaller than `diff_threshold * len(full_msg)` (default 0.7). For
massive changes, it automatically falls back to full encoding. Recovery after
desynchronization via `session.encode_full(obj)`.

### Synchronization and recovery

Sender and receiver maintain independent states that align by construction:
every message carries the LUT updates needed for its own decoding and (for
diffs) a base_id that uniquely identifies the previous payload. If the receiver
does not recognize the base_id (because it lost its state, just restarted, or
received messages out of order), it raises `ADPDiffSyncError`. The application
catches the error and requests a full re-send from the sender via `encode_full()`.

```python
try:
    obj = receiver.decode(msg)
except adp.ADPDiffSyncError:
    # Recovery: chiedi al mittente un full re-send
    request_full_resend()
except adp.ADPLUTSyncError:
    # Alias dinamico sconosciuto: stessa logica di recovery
    request_full_resend()
```

### Static vs dynamic vs full stack comparison

Benchmark on 20 agent-to-agent messages (planner ↔ executor) with the
`cl100k_base` tokenizer. Realistic request/reply pattern, structured payload
(nested dict + list of events):

| Format | Total tokens | Δ vs JSON | Δ vs TOON |
|---|---:|---:|---:|
| JSON-min | 2079 | baseline | +7.6% |
| **TOON** | **2249** | **−8.2%** | baseline |
| ADP base (no LUT) | 1903 | +8.5% | +15.4% |
| ADP + static LUT (`DEFAULT_AGENT_LUT`) | 1833 | +11.8% | +18.5% |
| ADP + dynamic LUT (cold) | 2071 | +0.4% | +7.9% |
| ADP + dynamic + static LUT | 1890 | +9.1% | +16.0% |
| ADP + dynamic LUT + diff encoding | 977 | +53.0% | +56.6% |
| ADP + full stack (static + dynamic + diff) | 931 | +55.2% | +58.6% |
| **ADP full stack + tokenizer-aware cost** | **908** | **+56.3%** | **+59.6%** |

With warm-start (pre-populating the LUT from a past session log via
`session.warmup(messages_log)`), the second half of a conversation saves an
additional ~6% compared to cold-start.

### Main parameters

```python
session = adp.ADPSession(
    # Core
    path="~/.adp/lut_state.json",  # None = in-memory; env ADP_LUT_PATH override
    max_entries=256,               # bound LRU
    static_lut=adp.DEFAULT_AGENT_LUT,
    k_threshold=2,                 # quante occorrenze in msg per aggiungere entry
    auto_save=True,                # persistenza atexit
    # Diff encoding
    enable_diff=True,              # disabilita per messaggi stateless
    diff_threshold=0.7,            # diff usato solo se len < 0.7 * full
    # Tokenizer-aware cost (opzionale, richiede tiktoken)
    cost_estimator=adp.TokenizerCostEstimator("cl100k_base"),
    # Capability negotiation
    announce_caps=True,            # annuncia _caps={...} al primo msg
    caps_timeout_msgs=3,           # auto-degrade dopo N send senza peer_caps
    # TPD auto-promotion (Phrase learning durante sessione)
    tpd_promote_every=10,          # 0 = disabilitato
    tpd_promote_max_per_run=10,    # cap entry promosse per giro
)

# ⚠️ TPD overhead on short sessions: default tpd_promote_every=10 assumes
# conversations of 50+ messages. On shorter workloads, header overhead from
# promoted entries may exceed savings. Set tpd_promote_every=0 to disable.

# Pre-warm da corpus passato (accelera bootstrap)
session.warmup(past_messages_log)

# Recovery dopo sync error
try:
    obj = session.decode(received)
except (adp.ADPLUTSyncError, adp.ADPDiffSyncError):
    msg = session.encode_full(payload)  # forza re-send completo
```

> **⚠️ TPD overhead on short sessions:** default `tpd_promote_every=10` assumes conversations of 50+ messages. On shorter workloads, header overhead from promoted entries may exceed savings. Set `tpd_promote_every=0` to disable for short sessions.

Full API: `encode`, `encode_full`, `encode_reset`, `decode`, `reset`,
`reset_caps`, `save`, `stats`, `warmup`, `_run_tpd_promotion`,
property `peer_caps`. Stateless helpers: `apply_lut_updates`,
`encode_with_dyn_lut`. Standalone estimator: `TokenizerCostEstimator`,
`estimate_cost`.

See the `src/adp/session.py` module and the design spec at
[`docs/superpowers/specs/2026-05-24-dynamic-lut-design.md`](superpowers/specs/2026-05-24-dynamic-lut-design.md).

Optional extra for precise cost-benefit analysis:
```bash
pip install adp[tokenizer]   # adds tiktoken
```
