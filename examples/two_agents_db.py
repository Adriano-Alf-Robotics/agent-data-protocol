"""Dimostrazione: dove vive la LUT/DB e come due agenti la condividono.

Quattro modalità di deployment, ordinate dalla più semplice alla più
sofisticata:

  1. STATIC      LUT hard-coded nel codice di entrambi gli agenti (zero
                 overhead runtime, ma cambiamenti richiedono redeploy).

  2. FILE        LUT salvata in un file JSON sul filesystem (locale o
                 condiviso via NFS/S3). Persistente, semplice, default.

  3. HANDSHAKE   LUT scambiata nel PRIMO messaggio della sessione tramite
                 definizioni inline `^+id|content|^`. Il destinatario la
                 registra automaticamente nel suo store locale.

  4. NEGOTIATED  Un servizio centrale (registry/Redis/DB) ospita la LUT
                 master. Gli agenti la sincronizzano all'avvio.

Esempio: due agenti A e B che si scambiano report trimestrali.
"""

from __future__ import annotations

import tempfile
import tiktoken
from pathlib import Path

from adp import ADPStore
from adp.tpd import BUSINESS_LUT_EN, learn_lut, encode_text, decode_text


TEXT = (
    "Revenue grew 12% year over year, driven primarily by enterprise sales in "
    "the EMEA region. Operational expenses remained flat, expanding margins.\n"
    "Customer churn dropped to 2.1%, the lowest in six quarters. Net-new logos "
    "added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.\n"
    "Outlook: cautious optimism. Macro headwinds persist but pipeline coverage "
    "for the next quarter stands at 3.4x, above the 3.0x threshold."
)


enc = tiktoken.get_encoding("cl100k_base")


def tok(s: str) -> int:
    return len(enc.encode(s))


print("=" * 60)
print("Original text:", tok(TEXT), "token,", len(TEXT), "byte")
print("=" * 60)

# ---------------------------------------------------------------
# 1. STATIC LUT — hard-coded in the agent codebase
# ---------------------------------------------------------------
print("\n--- 1. STATIC LUT (BUSINESS_LUT_EN, ship-time constant) ---")
# Note: BUSINESS_LUT_EN uses '§' markers which cost ~2 tokens each.
# In practice, prefer learn_lut() output (cheap ASCII codes) and freeze it
# at build time.
compressed = encode_text(TEXT, BUSINESS_LUT_EN)
assert decode_text(compressed, BUSINESS_LUT_EN) == TEXT
print(f"  compressed: {tok(compressed)} token  ({len(BUSINESS_LUT_EN)} entries pre-shared)")
print(f"  -> LUT lives:  in source code of both agents")
print(f"  -> Update cost: redeploy both agents")

# ---------------------------------------------------------------
# 2. FILE-BACKED ADPStore — persistent JSON on disk
# ---------------------------------------------------------------
print("\n--- 2. FILE-backed ADPStore (JSON on disk) ---")
with tempfile.TemporaryDirectory() as tmp:
    store_path = Path(tmp) / "shared_lut.json"

    # Agent A creates and populates the store
    agent_a = ADPStore(path=store_path)
    learned = learn_lut(TEXT, max_codes=40, min_phrase_words=2,
                        min_occurrences=1, min_token_savings=1)
    agent_a.seed(learned)
    agent_a.save()
    print(f"  Agent A saved {len(agent_a)} entries -> {store_path}")
    print(f"  File size: {store_path.stat().st_size} byte")

    # Agent A sends a compressed message
    msg_a = agent_a.encode(TEXT)
    print(f"  Message tokens: {tok(msg_a)} (vs {tok(TEXT)} raw)")

    # Agent B starts fresh, loads the same file (or NFS-syncs it)
    agent_b = ADPStore(path=store_path)
    print(f"  Agent B loaded {len(agent_b)} entries -> ready to decode")

    # Agent B decodes
    recovered = agent_b.decode(msg_a)
    assert recovered == TEXT
    print(f"  Lossless round-trip: OK")
    print(f"  -> LUT lives:  JSON file at {store_path.name}")
    print(f"  -> Update:     write file, partners pick it up on next read")

# ---------------------------------------------------------------
# 3. HANDSHAKE — inline definitions in the first message
# ---------------------------------------------------------------
print("\n--- 3. HANDSHAKE (inline definitions in first message) ---")
agent_a = ADPStore()
agent_b = ADPStore()

# First message uses learn_lut + emits definitions inline
# Format: ^+id|content|^   (decoder registers id->content while reading)
learned = learn_lut(TEXT, max_codes=40, min_phrase_words=2,
                    min_occurrences=1, min_token_savings=1)
agent_a.seed(learned)
# Build a first-message with definitions
def_block_parts = []
for content, ident in learned.items():
    def_block_parts.append(f"^+{ident}|{content}|^")
def_block = "".join(def_block_parts)
first_msg = def_block + agent_a.encode(TEXT)
print(f"  First message tokens: {tok(first_msg)} (carries the LUT)")

# Agent B decodes the first message: registers all definitions on the fly
recovered = agent_b.decode(first_msg)
print(f"  After decode, agent B has {len(agent_b)} entries in its store")

# Subsequent messages are tiny
second_msg = agent_a.encode(TEXT)   # same text, dictionary already known
print(f"  Second message tokens: {tok(second_msg)} (LUT already shared)")

assert agent_b.decode(second_msg) == TEXT
print(f"  -> LUT lives:  in-memory in each agent, bootstrapped via inline defs")
print(f"  -> Update:     send new definitions inline whenever needed")

# ---------------------------------------------------------------
# 4. NEGOTIATED — central registry (sketched, not implemented here)
# ---------------------------------------------------------------
print("\n--- 4. NEGOTIATED (central registry, e.g. Redis/SQLite) ---")
print("  Sketch: agents query a shared service for the current LUT, signed")
print("  with a version hash. New entries are submitted via PR-like flow.")
print("  -> LUT lives:  central service (Redis/SQLite/HTTP API)")
print("  -> Update:     publish to registry, agents revalidate on TTL")


print("\n" + "=" * 60)
print("Riepilogo: la LUT è un artefatto stateful condiviso. Esistono 4")
print("modalità di deployment a costo crescente, scelta dipende dal contesto.")
print("=" * 60)
