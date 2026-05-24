# Spec — LUT dinamica adattiva (HPACK-style)

**Data:** 2026-05-24
**Stato:** in attesa di review utente
**Scope:** nuovo modulo `adp.session`, integrazione con encoder/decoder esistenti, persistenza locale

## Obiettivo

Ridurre ulteriormente il consumo di token nelle conversazioni inter-agente di lunga durata mantenendo una **LUT condivisa che evolve durante la sessione**. Modello architetturale: HPACK (RFC 7541, header compression per HTTP/2).

A differenza della LUT statica esistente (pre-condivisa in codice via `DEFAULT_AGENT_LUT`), la LUT dinamica:

- si costruisce a partire dai messaggi effettivamente scambiati (domain-specific);
- propaga aggiornamenti in-band, senza canale secondario;
- sopravvive a restart tramite persistenza locale;
- non richiede pre-share o coordinamento out-of-band tra gli agenti;
- funziona su qualsiasi canale di trasporto (HTTP, gRPC, file, queue) e con qualsiasi provider LLM black-box.

Sul piano competitivo, questa feature riempie un gap che né TOON, né JTON, né CompactPrompt, né alcuna pipeline LLM commerciale (LangGraph/AutoGen/CrewAI) offre nativamente. Vedi la ricerca del 2026-05-23: il territorio è vergine per il caso text-serialization + API-agnostic + stateful bidirezionale + in-band propagation.

## Architettura

```
   Agente A                                          Agente B
   ┌─────────────────┐                          ┌─────────────────┐
   │  ADPSession     │                          │  ADPSession     │
   │  ┌───────────┐  │                          │  ┌───────────┐  │
   │  │ dyn LUT   │  │  msg con _lut+={...}     │  │ dyn LUT   │  │
   │  │ LRU 256   │──┼─encode──────────────────▶│──┼ decode──▶ │  │
   │  │ counter   │  │                          │  │ apply upd │  │
   │  └───────────┘  │                          │  └───────────┘  │
   │       │         │                          │       │         │
   └───────┼─────────┘                          └───────┼─────────┘
           ▼                                            ▼
       lut_state.json                              lut_state.json
       (persistenza locale)                        (persistenza locale)
```

Principi:
- HPACK-style: entrambi gli agenti mantengono LUT identica via update in-band.
- Persistenza locale per agente in `~/.adp/lut_state.json` (path configurabile).
- Bounded LRU 256 entries di default.
- Eager learning: encoder identifica chiavi e valori string ripetuti K≥2 nel payload corrente, li aggiunge e li dichiara nel header del messaggio stesso.
- Eviction LRU side-local deterministica: nessuna propagazione necessaria, perché entrambi i lati osservano le stesse inserzioni e gli stessi USI (l'uso è visibile dal payload).

## Sintassi in-band

L'update sta in **prefisso** del messaggio (non trailer), perché le nuove sigle vengono usate immediatamente nel payload.

### Variante adottata: solo addizioni, riusa grammatica mappa ADP

```
_lut+={_0=admin;_1=dev};u={i=42;r=_0;dpt=_1}
```

- Chiave riservata: `_lut+`
- Valore: mappa ADP standard `{alias=fullname;alias=fullname}`
- Le sigle alias sono nel namespace `_N` (underscore + numero progressivo), che non collide mai con chiavi utente né con il namespace short-letter della LUT statica.

### Reset esplicito

```
_lut!={};payload...
```

- Chiave riservata: `_lut!`
- Valore: mappa vuota `{}`
- Receiver pulisce LUT, payload deve essere autosufficiente (no alias dinamici).

### Vincoli grammaticali

- `_lut+` e `_lut!` riconosciuti dal parser ADP come chiavi riservate top-level
- Devono apparire al massimo una volta ciascuna e prima di qualsiasi altra chiave del payload
- Decodifica fallisce con `ADPParseError` se `_lut+` appare in posizione interna (non top-level)

## Componenti

### `src/adp/session.py` — nuovo modulo

Responsabilità: classe `ADPSession`, ciclo di vita LUT, persistenza, applicazione update.

API pubblica:

```python
class ADPSession:
    def __init__(
        self,
        path: str | Path | None = None,         # default ~/.adp/lut_state.json
        max_entries: int = 256,
        static_lut: dict[str, str] | None = None,
        k_threshold: int = 2,
        auto_save: bool = True,                  # atexit hook
        # Estensione 1 — tokenizer-aware
        cost_estimator: "TokenizerCostEstimator | None" = None,
        # Estensione 2 — capability negotiation
        announce_caps: bool = True,
        caps_timeout_msgs: int = 3,
        # Estensione 3 — TPD auto-promotion
        tpd_promote_every: int = 10,
        tpd_promote_max_per_run: int = 10,
        # Estensione 5 — differential encoding
        enable_diff: bool = True,
        diff_threshold: float = 0.7,
    ) -> None: ...

    # --- Core ---
    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj. no_lut=True bypassa dynamic LUT (fallback dopo sync error)."""

    def decode(self, msg: str) -> Any:
        """Decode msg. Applica nell'ordine: _caps=, _lut!=, _lut+=, _base+_diff,
        infine payload."""

    def save(self) -> None: ...
    def reset(self) -> None:
        """Pulisce LUT + diff state locali. NON propaga (vedi encode_reset)."""
    def encode_reset(self, obj: Any) -> str:
        """Encode con prefix _lut!={} (e _diff_reset=1 se enable_diff) per forzare
        reset al receiver."""
    def stats(self) -> dict: ...

    # --- Estensione 2: capability ---
    @property
    def peer_caps(self) -> dict | None:
        """Capability della controparte, popolato dopo primo round-trip."""
    def reset_caps(self) -> None: ...

    # --- Estensione 3: TPD promotion ---
    def _run_tpd_promotion(self) -> list[str]:
        """Forza un giro di promozione, ritorna alias aggiunti. Pubblica per test."""

    # --- Estensione 4: pre-warm ---
    def warmup(self, messages: Iterable[str] | Path,
               max_entries: int | None = None) -> int:
        """Pre-popola dynamic LUT da log/corpus passato. Ritorna n_entry aggiunte."""

    # --- Estensione 5: differential encoding ---
    def encode_full(self, obj: Any) -> str:
        """Forza encoding completo, ignora baseline. Reset diff state."""
```

API di basso livello (per integrazioni custom, non per uso comune):

```python
def apply_lut_updates(msg: str, lut: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Estrae _lut+=/_lut!= da msg, restituisce (payload_pulito, lut_aggiornata)."""

def encode_with_dyn_lut(obj: Any, dyn_lut: dict[str, str], k_threshold: int = 2,
                       max_entries: int = 256) -> tuple[str, dict[str, str]]:
    """Encode + restituisce (msg_con_prefix, lut_aggiornata_post_encode)."""

def compute_diff(base: dict, current: dict) -> list[tuple[str, str, Any]]:
    """RFC-6902-like diff. Ritorna lista di (op, path, value).
    Op: 'set', 'del', 'append', 'replace_list'."""

def apply_diff(base: dict, diff_ops: list) -> dict:
    """Applica diff a base, ritorna nuovo dict."""

def negotiate_capabilities(local: dict, peer: dict | None) -> dict:
    """Calcola capability effettive (intersezione, min su numerici)."""
```

### Persistenza — `~/.adp/lut_state.json`

Schema:

```json
{
  "version": 2,
  "entries": {
    "_0": "admin",
    "_1": "dev",
    "_2": "alice"
  },
  "lru_order": ["_2", "_0", "_1"],
  "next_alias_id": 3,
  "peer_caps": {"dyn_lut": 1, "max_entries": 256, "tok_aware": 0},
  "diff_state": {
    "last_sent_base_id": "a3f24e87",
    "last_received_base_id": "b2e0119c"
  },
  "stats": {
    "hit_count": 142,
    "miss_count": 38,
    "evictions": 0,
    "diff_hits": 24,
    "tpd_promotions": 3,
    "saved_at": "2026-05-24T10:32:11Z"
  }
}
```

- `version`: format version, attualmente `2` (incrementata vs design base per accogliere `peer_caps` e `diff_state`).
- `entries`: alias → fullname
- `lru_order`: lista alias dal meno recente al più recente. L'eviction prende il primo elemento.
- `next_alias_id`: counter per nuovi alias. Mai resettato salvo `version` bump o reset esplicito.
- `peer_caps`: capability negoziate con controparte (Estensione 2). Null se mai negoziato.
- `diff_state`: ID dei baseline correnti (Estensione 5). I payload base full vengono cached in-memory, non persistiti (ricostruiti via prossimo full re-send se restart).
- `stats`: contatori opzionali per `session.stats()`.

Locking: `fcntl.flock(f, LOCK_EX)` su Linux durante write. Read accetta lock condiviso.

Path default: `~/.adp/lut_state.json`. Override:
- argomento `path=` al costruttore
- variabile ambiente `ADP_LUT_PATH`
- `None` → in-memory only (no persistenza)

### Eager learner

Algoritmo encoder per ogni `session.encode(obj)`:

1. Walking di `obj` (dict/list ricorsivi), conta occorrenze di:
   - chiavi dict (string)
   - valori string scalari
2. Per ogni candidato con `count >= k_threshold`:
   - Se già in static LUT: skip (static è già zero-overhead)
   - Se già in dynamic LUT: marca come "used" (bumpa LRU)
   - Altrimenti: candidato per nuovo alias
3. Per ogni nuovo candidato, valuta cost-benefit:
   - `saving = count × len_chars(fullname) - len_chars(alias) - header_overhead_chars(alias, fullname)`
   - Se `saving > 0` (in caratteri): aggiunge entry
4. Se aggiunge entry quando `len(entries) >= max_entries`: evict LRU front (entry meno recente)
5. Compila `_lut+={...}` header con le nuove entry aggiunte in questo messaggio
6. Encoda payload sostituendo fullname con alias

Nota: cost-benefit usa **caratteri** come proxy approssimativo per token. Stima accurata richiederebbe tiktoken (dipendenza opzionale, fuori scope v1).

### Decoder

1. Riceve messaggio raw (string ADP)
2. Parser ADP top-level: identifica chiavi riservate `_lut+`, `_lut!`
3. Se `_lut!` presente: `self.entries.clear(); self.lru_order.clear()`
4. Se `_lut+` presente: per ogni `alias=fullname`, aggiungi a entries (può triggerare eviction se max raggiunto, deterministica side-local)
5. Decodifica payload normalmente. Quando incontra una chiave/valore che è un alias `_N` nella LUT dinamica, espande a fullname.
6. Se incontra alias `_N` NON in LUT → solleva `ADPLUTSyncError(alias)`.

### Statistiche e diagnostica

`session.stats()` ritorna:

```python
{
    "entries_count": 87,
    "max_entries": 256,
    "hit_count": 142,        # quante volte un alias è stato risolto in decoded
    "miss_count": 38,        # quante chiavi/valori candidate sono state lasciate bare
    "evictions": 0,
    "estimated_chars_saved": 4321,
}
```

## Data flow tipico

Sequenza di 4 messaggi tra Agente A e Agente B, LUT vuota all'inizio.

**Msg 1 (A → B):**
```
_lut+={_0=user;_1=admin;_2=email};_0={id=42;role=_1;_2=adp@example.com}
```
A ha visto `user`, `admin`, `email` ripetuti K≥2 nel payload espanso. Li aggiunge, dichiara prefix, payload usa alias.
B: applica `_lut+=`, decodifica payload usando nuova LUT.

**Msg 2 (B → A):**
```
_0={id=43;role=dev;status=ok}
```
B usa `_0` (già in LUT), `role`/`status` non superano K=2 in questo messaggio (singola occorrenza). Nessun nuovo entry.
A: decodifica usando LUT esistente.

**Msg 3 (A → B):**
```
_lut+={_3=status};users=[{_0=alice;_1=admin;_3=active},{_0=bob;_1=dev;_3=active}]
```
A vede `status` ripetuto 2x. Lo aggiunge ora. Notare: `users`, `alice`, `bob`, `active` no — `users` 1x, `alice` 1x, `bob` 1x. `active` 2x ma string corta (6 char) vs alias `_4` (2 char) + header 13 char (`_4=active;`) = saving 12-13 = -1, non vale.

**Msg 4 (A → B), agente B riavviato perdendo state:**
```
_0={id=44;role=_1;_2=c@d.e}
```
A pensa B abbia LUT. B non ha `_0`. Decoder solleva `ADPLUTSyncError(alias="_0")`.
App: cattura errore, chiede ad A di reinviare con `session.encode(obj, no_lut=True)`. Successivi messaggi gradualmente ricostruiscono LUT.

## Edge case

### Receiver senza ADPSession (decodifica ad-hoc)

Un consumatore vuole leggere un messaggio singolo senza state. Soluzione: una funzione standalone `adp.decode_with_inline_lut(msg)` che:

1. Estrae `_lut+=` dal prefix
2. Decodifica il payload usando SOLO quegli alias dichiarati nel messaggio stesso
3. Funziona per messaggi self-contained (cioè quando A non riferisce alias di messaggi precedenti)
4. Solleva `ADPLUTSyncError` se trova alias non dichiarati nel messaggio corrente

### Conflitto alias static vs dynamic

Impossibile per costruzione: static LUT usa short letters (`u`, `i`, `n`, ...), dynamic usa `_N`. Namespace disgiunti.

### Race condition file `lut_state.json`

Multipli processi sullo stesso file: `fcntl.flock` exclusive sulle write. Lettura iniziale del costruttore usa shared lock. Save atomico tramite write su temp file + rename.

### Receiver perde alcuni messaggi (es. queue reordering)

In sync HPACK richiede ordine. Per agent comm tipico (request/reply), assumiamo ordine. Per scenari con MQ che riordina: documentare limitazione, suggerire wrapping in canale ordinato (TCP, sequence-numbered queue).

### Versionamento schema persistenza

Costruttore legge `version`. Se diverso da `1`: log warning, archivia file vecchio in `.adp/lut_state.bak`, inizia con LUT vuota.

## Estensione 1 — Tokenizer-aware cost estimation

Sostituisce la stima caratteri-based del cost-benefit con conteggio token reale.

**Nuovo modulo:** `src/adp/cost.py`

```python
def estimate_cost(text: str, tokenizer: str = "cl100k_base") -> int:
    """Conta token usando tiktoken. Fallback a len(text) // 4 se tiktoken assente."""

class TokenizerCostEstimator:
    def __init__(self, tokenizer: str = "cl100k_base"): ...
    def saving_for_entry(self, alias: str, fullname: str, count: int) -> int:
        """saving = count × tok(fullname) − count × tok(alias) − tok(header_entry)"""
```

**Integrazione:** `ADPSession(..., cost_estimator: TokenizerCostEstimator | None = None)`.
- Se `None` (default): char-count approssimazione (esistente)
- Se passato: tiktoken-aware decisioni più precise

**Dipendenza:** `tiktoken>=0.7` come optional extra (`pip install adp[tokenizer]`). Già presente in `[project.optional-dependencies].dev`. Aggiungere gruppo `tokenizer` separato.

**Effort stimato:** ~50 LOC + 3 test.

## Estensione 2 — Capability negotiation

Handshake iniziale per scoprire se la controparte supporta dynamic LUT, evita errori silenziosi quando un agente non-aware riceve `_lut+=`.

**Nuovo tipo messaggio (top-level):**

```
_caps={dyn_lut=1;max_entries=256;tok_aware=1};_lut+={...};payload...
```

**Protocollo:**

1. Primo messaggio di una sessione: encoder prepende `_caps=` con le proprie capability
2. Receiver risponde nel suo primo messaggio con il proprio `_caps=` (negoziazione bidirezionale)
3. Da quel momento, sender adatta:
   - Se receiver `dyn_lut=0`: `session.encode()` usa internamente `no_lut=True` automatic
   - Se `max_entries` controparte < proprio: sender rispetta il minimo
   - Se `tok_aware=0` ma sender ha tokenizer: sender usa comunque char-count per condividere stesso algoritmo

**API:**

```python
class ADPSession:
    def __init__(self, ..., announce_caps: bool = True): ...
    @property
    def peer_caps(self) -> dict | None: ...  # popolato dopo primo round-trip
    def reset_caps(self) -> None: ...  # forza re-negoziazione
```

**Edge case:** se sender non vede `_caps=` di ritorno dopo N messaggi (default N=3), assume controparte non supporta capability negotiation, mantiene comportamento conservativo (no dyn LUT). Configurabile via `caps_timeout_msgs`.

**Effort stimato:** ~30 LOC + 4 test.

## Estensione 3 — Auto-promozione TPD → dynamic LUT

Unifica i due sistemi: phrase ricorrenti scoperti dal TPD vengono automaticamente migrate nel dynamic LUT, eliminando la divisione artificiale.

**Algoritmo:**

1. Periodicamente (ogni N messaggi, default N=10): `session._run_tpd_promotion()`
2. Concatena ultimi N messaggi raw scambiati (mantenuti in ring buffer in-memory)
3. Esegue `tpd.learn_lut(concatenated, max_codes=10)` (riusa funzione esistente)
4. Per ogni phrase rilevata da TPD: se non in dynamic LUT, aggiungila come entry. Alias namespace condiviso (`_N`).
5. Propaga via `_lut+=` nel prossimo messaggio
6. Ring buffer size = max(N×avg_msg_size, 4KB), evicted via FIFO

**Differenza chiave vs TPD originale:** TPD esistente richiede LUT pre-condivisa. La promozione automatica rende l'apprendimento di phrase 100% dynamic e in-band, eliminando il vincolo di pre-sharing.

**API:**

```python
class ADPSession:
    def __init__(self, ..., tpd_promote_every: int = 10,
                 tpd_promote_max_per_run: int = 10): ...
    def _run_tpd_promotion(self) -> list[str]:
        """Forza un giro di promozione, ritorna alias aggiunti. Pubblica per test."""
```

**Default:** `tpd_promote_every=10`. Set a `0` per disabilitare.

**Effort stimato:** ~100 LOC + ring buffer + 5 test.

## Estensione 4 — Pre-warm da corpus

`session.warmup()` carica dynamic LUT da conversazioni passate (log file, corpus statico, output di sessione precedente), accelerando il bootstrap.

**API:**

```python
class ADPSession:
    def warmup(self, messages: Iterable[str] | Path,
               max_entries: int | None = None) -> int:
        """Analizza messaggi (lista di ADP raw OR path a file newline-delimited),
        applica algoritmo eager learner, popola dynamic LUT.

        Ritorna numero di entry aggiunte.
        """
```

**Algoritmo warmup:**

1. Itera messaggi
2. Per ogni msg: decoda usando state corrente (alias esistenti risolti, nuovi non aggiunti — solo lettura)
3. Conta occorrenze cumulative di chiavi/valori string non in static LUT
4. Quando un candidato supera K=2 cumulative: aggiunge a dynamic LUT (rispettando `max_entries` di sessione)
5. Salva state al termine

**Use case tipico:**

```python
# Bootstrap LUT da 1000 messaggi passati prima di iniziare nuova sessione
session = adp.ADPSession()
n_added = session.warmup(Path("logs/last_session.ndjson"))
print(f"Pre-warmed con {n_added} entry")
# Prima conversazione live parte con LUT già stabilizzata
```

**Differenza vs persistenza:** persistenza salva lo state di UNA sessione corrente. Warmup importa state da fonte esterna (può essere log di una sessione diversa, dump di un agente diverso, corpus dominio-specifico).

**Effort stimato:** ~80 LOC + 4 test.

## Estensione 5 — Differential encoding inter-message

Invece di inviare il payload completo a ogni messaggio, sender invia solo il **delta** rispetto all'ultimo messaggio scambiato in quella direzione. Combinato con dynamic LUT, raddoppia il risparmio su pattern request/reply tipici (status reports, polling, watch streams).

**Nuovo prefisso top-level:** `_base=ID;_diff={...}`

- `_base=ID`: identifica il "baseline" da cui calcolare il diff. ID è hash troncato (8 hex char) del payload base + counter
- `_diff={...}`: mappa di operazioni delta

**Operazioni delta:**

| Op | Sintassi | Semantica |
|---|---|---|
| Set/update | `path=value` | Imposta path al nuovo valore (overwrite) |
| Delete | `-path` | Rimuove path |
| List append | `+path=value` | Append a lista in path |
| List replace | `path=[...]` | Sostituisce intera lista |

Path notation ADP-native: `user.id`, `users.0.role`, `metrics.errors`.

**Sender state (per direzione):**

```python
self.last_sent_payload: dict | None  # ultimo payload completo inviato
self.last_sent_base_id: str | None
```

**Receiver state (per direzione):**

```python
self.last_received_payload: dict | None
self.last_received_base_id: str | None
```

**Algoritmo encoder:**

1. Se nessun baseline (primo msg o reset): invia payload completo + assegna `base_id` = hash(payload)[:8] + counter
2. Altrimenti: calcola diff = `compute_diff(last_sent, current)`. Se `len(diff_encoded) > 0.7 × len(full_encoded)`: invia full (poco guadagno dal diff). Altrimenti: invia `_base=ID;_diff={...}`
3. Memorizza `current` come nuovo last_sent

**Algoritmo decoder:**

1. Se `_base=ID` presente: carica payload base da `last_received_payload` con ID corrispondente. Se ID non match (out of sync): solleva `ADPDiffSyncError(expected=..., got=...)`
2. Se `_diff={...}` presente: applica operazioni al base, ottieni nuovo payload
3. Memorizza nuovo payload come last_received

**Reset esplicito:** `_diff_reset=1;payload...` → entrambi i lati scartano baseline, ripartono full.

**Combinazione con dynamic LUT:** ortogonali. Il prefix di un msg può contenere SIA `_lut+=` SIA `_base+_diff`:

```
_lut+={_5=status};_base=a3f2;_diff={u._5=active;m.errors=-5}
```

Espande a: "applica LUT update, poi diff su baseline a3f2".

**API:**

```python
class ADPSession:
    def __init__(self, ..., enable_diff: bool = True,
                 diff_threshold: float = 0.7): ...
    def encode_full(self, obj: Any) -> str:
        """Forza encoding completo, ignora baseline. Reset diff state."""
```

**Edge case principali:**

- **First msg:** sempre full (no baseline)
- **Sync error:** receiver solleva `ADPDiffSyncError`, app chiede full re-send via `session.encode_full(obj)`
- **Payload molto cambiato:** diff > 70% del full → encoder sceglie automaticamente full
- **Out-of-order messaging:** `base_id` mismatch → sync error → fallback

**Effort stimato:** ~180 LOC + diff algorithm (potenzialmente RFC 6902 JSON Patch adattato) + 8 test.

## Out of scope (v1)

- LUT sharing tra più di 2 agenti (broker centralizzato)
- Riconciliazione automatica post-loss oltre `ADPLUTSyncError`/`ADPDiffSyncError`
- Versioning del protocollo per backward-compat futura
- Compressione substring arbitraria (LZ77-style)
- Web UI per ispezionare LUT state
- Multi-baseline diff (più baseline candidati)

## Testing

Test suite nuova: `tests/test_session.py` (core) + file dedicati per estensioni.

### Core (test_session.py)

1. **Round-trip base**: encode + decode su singolo agente, vari payload
2. **Round-trip due agenti**: due `ADPSession`, scambio bidirezionale 10 msg, verifica sync persistente
3. **Soglia K=2**: chiave appare 1x → no entry; 2x → entry
4. **Static LUT precedenza**: chiavi in `DEFAULT_AGENT_LUT` non finiscono in dynamic
5. **LRU eviction**: max_entries=4 + 6 inserzioni, verificare entry corretta evicta
6. **Reset propagation**: `session.encode_reset(obj)` pulisce stato in receiver
7. **SyncError LUT**: messaggio con alias sconosciuto solleva `ADPLUTSyncError`
8. **Persistenza**: save + new session reload → stessa LUT
9. **Locking concorrente**: due processi che scrivono lo stesso file, no corruption
10. **Decodifica ad-hoc**: messaggio con `_lut+=` self-contained decodificabile senza session
11. **Stats**: `session.stats()` riflette eventi reali
12. **Cost-benefit char-based**: candidato corto ("ok" 3x) non aggiunto se overhead supera saving

### Estensione 1 — Tokenizer-aware (test_cost.py)

13. **Tiktoken fallback assente**: `estimate_cost()` ritorna `len(text)//4` se tiktoken not installed
14. **Tiktoken presente**: count corrisponde a `tiktoken.encoding_for_model(...)` reale
15. **Cost-benefit con estimator**: payload reale → decisione add coincide con saving token > 0

### Estensione 2 — Capability negotiation (test_caps.py)

16. **Handshake bidirezionale**: A invia `_caps=`, B risponde con suo `_caps=`, entrambi popolano `peer_caps`
17. **Receiver non-aware**: sender ricco invia `_lut+=` a receiver senza ADPSession → receiver bypassa, sender rileva dopo `caps_timeout_msgs=3` e disabilita auto
18. **Max_entries clamping**: A=256, B=64 → entrambi rispettano min(256,64)=64
19. **Reset caps**: `session.reset_caps()` riavvia negoziazione

### Estensione 3 — TPD auto-promotion (test_tpd_promotion.py)

20. **Promotion triggered ogni N=10 msg**: dopo 10 msg con phrase "in the EMEA region" ripetuta, alias dyn LUT aggiunto
21. **Ring buffer fifo**: superato buffer size, msg vecchio evicted
22. **Tpd_promote_every=0**: disabilita feature, nessuna promozione
23. **Promotion riconoscibile da entrambi**: alias `_N` propagato via `_lut+=`, receiver applica

### Estensione 4 — Pre-warm (test_warmup.py)

24. **Warmup da lista**: `session.warmup(["msg1","msg2",...])` popola LUT
25. **Warmup da file**: `session.warmup(Path("log.ndjson"))` legge linee, popola LUT
26. **Warmup rispetta max_entries**: cap globale, non override
27. **Warmup idempotente**: ri-eseguire stesso input non duplica entry

### Estensione 5 — Differential encoding (test_diff.py)

28. **First msg full**: nessun baseline → `encode()` produce payload completo, no `_diff`
29. **Second msg diff small change**: cambia 1 campo → output contiene `_base=ID;_diff={field=newval}`
30. **Diff threshold 70%**: cambio massivo → encoder sceglie full, no diff
31. **Diff sync error**: receiver con baseline diverso → `ADPDiffSyncError`, app chiama `encode_full()`
32. **Diff + dyn LUT combinati**: msg contiene SIA `_lut+=` SIA `_base+_diff`, decoder applica nell'ordine corretto
33. **`encode_full()` forza completo**: anche con baseline disponibile
34. **Diff_reset propagation**: `_diff_reset=1` pulisce baseline in receiver
35. **Operazioni delta**: set/del/append/replace_list tutti supportati e round-trip

## Benchmark target

Aggiungere a `benchmarks/`:

- `bench_dynamic_lut.py`: simula conversazione 20 msg tra 2 agenti su payload realistici (agent task, user lookup, status report). Misura token cl100k_base totali vs:
  - JSON-min
  - ADP base (no LUT)
  - ADP + static LUT
  - ADP + dynamic LUT (cold start)
  - ADP + dynamic LUT (warm start via `warmup()`)
  - ADP + dynamic LUT + differential encoding (Est. 5)
  - ADP + full stack (LUT + diff + TPD promotion + tokenizer-aware)
  - TOON (best competitor)

Target atteso (da validare empiricamente):
- Dynamic LUT core: +10-25% vs ADP + static LUT
- Warmup attivo: +5-10% extra primi 5 msg
- Differential encoding aggiunge: +20-40% su pattern request/reply con payload simili
- Full stack: target **+50-70% vs TOON** su sessione 20+ msg con pattern ricorrenti

## Integrazione con README

Sezione `## LUT — Look-Up Table` esistente: aggiungere sotto-sezione `### Dynamic LUT (HPACK-style)` con esempio API e tabella "static vs dynamic vs full-stack".

Nuova sezione `## Differential encoding` con esempio request/reply.

Aggiornare `## Roadmap`:
- v0.3 — envelope (esistente)
- v0.3.5 — dynamic LUT in-session (NUOVO, questa spec)
- v0.4 — schema/contract (spostato giù)
- v0.5 — TypeScript port (esistente)

## Struttura file finale

```
src/adp/
├── session.py          NUOVO — ADPSession class (core + Est. 2/3/4/5)
├── cost.py             NUOVO — TokenizerCostEstimator (Est. 1)
├── diff.py             NUOVO — compute_diff/apply_diff (Est. 5)
├── lut.py              esistente — static LUT (DEFAULT_AGENT_LUT)
├── tpd.py              MODIFICA leggera — esporta helper per promotion (Est. 3)
├── parser.py           MODIFICA — riconosce _lut+, _lut!, _caps, _base, _diff,
│                       _diff_reset come top-level riservate
├── serializer.py       MODIFICA — emette prefix riservati se richiesto
├── __init__.py         MODIFICA — esporta ADPSession, ADPLUTSyncError,
│                       ADPDiffSyncError, TokenizerCostEstimator
└── ...

tests/
├── test_session.py            NUOVO — core (12 test)
├── test_cost.py               NUOVO — Est. 1 (3 test)
├── test_caps.py               NUOVO — Est. 2 (4 test)
├── test_tpd_promotion.py      NUOVO — Est. 3 (4 test)
├── test_warmup.py             NUOVO — Est. 4 (4 test)
├── test_diff.py               NUOVO — Est. 5 (8 test)

benchmarks/
├── bench_dynamic_lut.py       NUOVO — simula sessione, confronta full stack vs TOON

pyproject.toml             MODIFICA — extra opzionale 'tokenizer' (tiktoken)
```

## Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Drift sync LUT tra agenti | media | alto (corruzione decode) | LRU deterministica + `ADPLUTSyncError` + fallback `no_lut=True` |
| Drift sync baseline diff | media | alto (corruzione decode) | base_id check + `ADPDiffSyncError` + `encode_full()` |
| Overhead header > savings | bassa | medio (peggior caso = +5% token) | Cost-benefit char-count (Est. 1: tokenizer-aware preciso) |
| Capability negotiation persa | bassa | medio (sender non sa che B non supporta) | `caps_timeout_msgs` fallback auto a no_lut |
| TPD promotion ridondante | bassa | basso (entry duplicate skippate) | check `alias not in entries` prima di add |
| Warmup conflict con state esistente | bassa | basso | warmup additivo, rispetta `max_entries` |
| File corruption locale | bassa | basso (recovery rebuild) | Atomic write + version field + backup .bak |
| Race condition multi-process | media | medio (perdita aggiornamenti) | flock + temp+rename |
| Tokenizer dep mancante | alta | basso (fallback char-count) | `tiktoken` come optional extra, runtime ImportError handle |
| Receiver senza supporto session | media | medio (errore decode) | Capability negotiation (Est. 2) + `decode_with_inline_lut` |
| Diff size > full size (corner) | media | basso (no saving) | `diff_threshold=0.7`, encoder sceglie full automatico |
| Out-of-order delivery (queue) | bassa | alto (sync error cascade) | Documentare requisito FIFO; suggerire sequence-numbered queue |
