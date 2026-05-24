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
    ) -> None: ...

    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj to ADP. Se no_lut=True bypassa la dynamic LUT (fallback)."""

    def decode(self, msg: str) -> Any:
        """Decode msg. Applica _lut+=/_lut!= se presenti, poi decodifica payload."""

    def save(self) -> None:
        """Persistenza esplicita su disco."""

    def reset(self) -> None:
        """Pulisce LUT locale. NON propaga: per propagare chiamare next encode con
        flag o usare encode_reset()."""

    def encode_reset(self, obj: Any) -> str:
        """Encode con prefix _lut!={} per forzare reset al receiver."""

    def stats(self) -> dict:
        """Dict diagnostico: entries_count, hit_count, miss_count, evictions,
        bytes_saved_estimate."""
```

API di basso livello (per integrazioni custom, non per uso comune):

```python
def apply_lut_updates(msg: str, lut: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Estrae _lut+=/_lut!= da msg, restituisce (payload_pulito, lut_aggiornata)."""

def encode_with_dyn_lut(obj: Any, dyn_lut: dict[str, str], k_threshold: int = 2,
                       max_entries: int = 256) -> tuple[str, dict[str, str]]:
    """Encode + restituisce (msg_con_prefix, lut_aggiornata_post_encode)."""
```

### Persistenza — `~/.adp/lut_state.json`

Schema:

```json
{
  "version": 1,
  "entries": {
    "_0": "admin",
    "_1": "dev",
    "_2": "alice"
  },
  "lru_order": ["_2", "_0", "_1"],
  "next_alias_id": 3,
  "stats": {
    "hit_count": 142,
    "miss_count": 38,
    "evictions": 0,
    "saved_at": "2026-05-24T10:32:11Z"
  }
}
```

- `version`: format version, attualmente `1`. Schema bumps in futuro forzano reset locale e ri-bootstrap della LUT.
- `entries`: alias → fullname
- `lru_order`: lista alias dal meno recente al più recente. L'eviction prende il primo elemento.
- `next_alias_id`: counter per nuovi alias. Mai resettato salvo `version` bump o reset esplicito.
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

## Out of scope (v1)

- Tokenizer-aware cost estimation (sostituito da char-count approssimazione)
- Auto-promozione di phrase TPD a dynamic LUT
- LUT sharing tra più di 2 agenti (broker centralizzato)
- Capability negotiation (handshake per scoprire se controparte supporta dynamic LUT)
- Riconciliazione automatica post-loss oltre `ADPLUTSyncError`
- Versioning del protocollo per backward-compat futura
- Compressione substring arbitraria (LZ77-style)
- Web UI per ispezionare LUT state

## Testing

Test suite nuova: `tests/test_session.py`. Copre:

1. **Round-trip base**: encode + decode su singolo agente, vari payload (chiavi ripetute, valori ripetuti, struttura annidata, tabelle)
2. **Round-trip due agenti**: due `ADPSession` istanze, scambio bidirezionale 10 messaggi, verifica sync persistente
3. **Soglia K=2**: chiave appare 1x → no entry; 2x → entry
4. **Static LUT precedenza**: chiavi in `DEFAULT_AGENT_LUT` non finiscono in dynamic
5. **LRU eviction**: superare max_entries=4 con N inserzioni, verificare entry corretta evicta
6. **Reset propagation**: `session.encode_reset(obj)` pulisce stato in receiver
7. **SyncError**: messaggio con alias sconosciuto solleva `ADPLUTSyncError`
8. **Persistenza**: save + new session reload → stessa LUT
9. **Locking concorrente**: due processi che scrivono lo stesso file, no corruption
10. **Decodifica ad-hoc**: messaggio con `_lut+=` self-contained decodificabile senza session
11. **Stats**: `session.stats()` riflette eventi reali
12. **Cost-benefit**: candidato corto (es. "ok" 3x) non aggiunto se overhead supera saving

## Benchmark target

Aggiungere a `benchmarks/`:

- `bench_dynamic_lut.py`: simula conversazione 20 msg tra 2 agenti su payload realistici (agent task, user lookup, status report). Misura token cl100k_base totali vs:
  - JSON-min
  - ADP base (no LUT)
  - ADP + static LUT
  - ADP + dynamic LUT (warm start = già stabilizzata)
  - TOON (best competitor)

Target atteso (da validare): dynamic LUT riduce di +10-25% in più rispetto a ADP + static LUT, e batte TOON di +15-30% su sessione lunga.

## Integrazione con README

Sezione `## LUT — Look-Up Table` esistente: aggiungere sotto-sezione `### Dynamic LUT (HPACK-style)` con esempio API e tabella "static vs dynamic". Aggiornare `## Roadmap`: spostare "v0.4 — schema/contract" giù di uno, inserire "v0.3.5 — dynamic LUT in-session".

## Struttura file finale

```
src/adp/
├── session.py          NUOVO — ADPSession class
├── lut.py              esistente — static LUT (DEFAULT_AGENT_LUT)
├── tpd.py              esistente — phrase dict
├── parser.py           MODIFICA — riconosce _lut+/_lut! come top-level riservate
├── serializer.py       MODIFICA — emette _lut+=/_lut!= se richiesto
├── __init__.py         MODIFICA — esporta ADPSession, ADPLUTSyncError
└── ...

tests/
├── test_session.py     NUOVO — 12 test categorie

benchmarks/
├── bench_dynamic_lut.py NUOVO — simula sessione, confronta vs TOON
```

## Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Drift sync tra agenti | media | alto (corruzione decode) | LRU deterministica + SyncError esplicito + fallback no_lut |
| Overhead header > savings | bassa | medio (peggior caso = +5% token) | Cost-benefit check pre-add con char-count |
| File corruption locale | bassa | basso (recovery rebuild) | Atomic write + version field + backup .bak |
| Race condition multi-process | media | medio (perdita aggiornamenti) | flock + temp+rename |
| Tokenizer mismatch (char≠token) | alta | basso (sub-ottimale ma corretto) | char-count come proxy v1, tiktoken-aware v2 |
| Receiver senza supporto | media | medio (errore decode) | Funzione `decode_with_inline_lut` per messaggi self-contained |
