# ADP — Adriano Dal Pastro format

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-blue)

**Formato testuale lossless e aggressivamente token-efficient per la comunicazione tra agenti AI.**

ADP (versione 0.2) è una libreria Python che definisce e implementa un
piccolo linguaggio di serializzazione progettato specificamente per lo
scambio di messaggi tra modelli linguistici. Non è pensato per essere
letto da un essere umano a prima vista: a quello pensano i convertitori
in Markdown leggibile e in JSON canonico.

L'obiettivo è ridurre il numero di token che gli agenti spendono per
parlarsi preservando tutta l'informazione strutturale di un payload JSON
tipico — mappe annidate, liste, tabelle con cells annidate, testi
multilinea, primitive tipizzate, **bytes** — senza mai introdurre perdita
di dati.

**Quanto risparmia (vs JSON-min, tokenizer cl100k_base):**

| Payload tipico | JSON-min (tok) | ADP (tok) | Δ |
|---|---:|---:|---:|
| Tabella omogenea (it) | 333 | 164 | **+50,8%** |
| Lista contatti con URL/email | 145 | 94 | **+35,2%** |
| Tabelle con cells annidate | 100 | 75 | **+25,0%** |
| Conversazione 20 msg agent-to-agent (full stack) | 2079 | **908** | **+56,3%** |

L'ultima riga è ottenuta con `ADPSession` (dynamic LUT HPACK-style + differential encoding inter-message + capability negotiation + TPD auto-promotion + tokenizer-aware cost). Sullo stesso payload, **TOON** richiede 2249 token: ADP è **2,5× più economico di TOON** in scenari multi-turn realistici. Vedi sezione [Dynamic LUT](#dynamic-lut-hpack-style--differential-encoding) per dettagli.

## Indice

1. [Perché ADP](#perché-adp)
2. [Installazione](#installazione)
3. [Quickstart](#quickstart)
4. [Sintassi in pillole](#sintassi-in-pillole)
5. [Convertitori](#convertitori)
6. [Integrazione con agenti AI](#integrazione-con-agenti-ai)
7. [Dynamic LUT (HPACK-style) + differential encoding](#dynamic-lut-hpack-style--differential-encoding)
8. [Riduzione token misurata](#riduzione-token-misurata)
9. [Esempi a confronto](#esempi-a-confronto)
10. [Immagini](#immagini)
11. [Usare ADP in Claude Code](#usare-adp-in-claude-code)
12. [Integrità — sign / verify](#integrità--sign--verify)
13. [Struttura del progetto](#struttura-del-progetto)
14. [Sviluppo e test](#sviluppo-e-test)
15. [Roadmap](#roadmap)
16. [Licenza](#licenza)

---

## Perché ADP

Quando due o più agenti AI si scambiano dati, la rappresentazione più
naturale è JSON. JSON funziona benissimo per le macchine, ma è verboso
per i tokenizer LLM: ogni virgoletta intorno a una chiave costa, ogni
`true` costa più di un singolo `1`, ogni tabella di righe omogenee paga
il prezzo di ripetere le chiavi a ogni riga, e i bytes binari non sono
nativamente rappresentabili.

ADP prende le decisioni di design che JSON non poteva permettersi:

- niente virgolette obbligatorie su chiavi o stringhe semplici;
- `1`/`0` al posto di `true`/`false`, `~` al posto di `null`;
- newline letterali dentro le stringhe (niente sequenze `\n`);
- una notazione tabella dedicata per le liste di dizionari omogenei,
  che ammette **cells annidate** (liste e mappe);
- bare strings ampliate per assorbire URL, email e percorsi senza
  virgolette;
- `bytes` nativi tramite prefisso `b!` + base64 standard;
- top-level senza wrappers (`name=value;name=value` invece di sintassi
  ridondante).

Il prezzo da pagare è la perdita di leggibilità diretta da parte di un
umano, ma il convertitore Markdown della libreria ricostruisce sempre
una versione leggibile, mentre il convertitore JSON ripristina una
struttura universalmente machine-readable.

## Installazione

```bash
uv sync --all-extras
```

Requisiti: Python 3.11 o superiore.

## Quickstart

```python
import adp

payload = {
    "user": {"id": 42, "name": "Adriano", "active": True, "email": "adp@example.com"},
    "users": [                                              # tabella inferita
        {"id": 1, "name": "alice", "roles": ["admin", "ops"]},
        {"id": 2, "name": "bob",   "roles": ["dev"]},
    ],
    "thumbnail": b"\x89PNG\r\n\x1a\n...",                   # bytes nativi
    "report": "Riga 1\nRiga 2 con \"virgolette\"",          # multilinea letterale
}

s = adp.encode(payload)
print(s)
# user={id=42;name=Adriano;active=1;email=adp@example.com};
# users=#id,name,roles|1i,alice,[admin,ops]|2,bob,[dev];
# thumbnail=b!iVBORw0KGgoaLi4u;
# report="Riga 1
# Riga 2 con \"virgolette\""

assert adp.decode(s) == payload   # round-trip lossless, bytes inclusi

print(adp.to_json(s))      # JSON canonico per macchine non-AI
print(adp.to_markdown(s))  # Markdown leggibile per umani
```

Da riga di comando:

```bash
echo '{"user":{"id":42,"name":"Adriano"}}' | uv run adp encode
# user={id=42;name=Adriano}

echo 'user={id=42;name=Adriano}' | uv run adp decode
# {"user": {"id": 42, "name": "Adriano"}}

uv run adp bench < payload.json    # confronto token ADP vs JSON
uv run adp prompt --few-shot       # stampa il prompt di sistema per LLM
```

## Sintassi in pillole

| Elemento | Sintassi | Esempio |
|---|---|---|
| Top-level | `name=value;name=value` | `id=42;ok=1` |
| Intero | nudo | `42`, `-7` |
| Intero 0 o 1 (disambiguazione) | suffisso `i` | `0i`, `1i` |
| Float | con punto decimale | `3.14`, `-0.5` |
| Booleano | `1` / `0` | `1` = true |
| Null | `~` | `~` |
| Bytes | `b!<base64>` | `b!aGVsbG8=` |
| Stringa "bare" | senza virgolette | `Adriano`, `ops@acme.example`, `https://x.y/api` |
| Stringa quotata | tra `"..."` | `"con spazio"` |
| Escape dentro stringa | solo `\"` e `\\` | `"dice \"ciao\""` |
| Lista | `[a,b,c]` | `[admin,root]` |
| Mappa | `{k=v;k=v}` | `{id=1;qty=2}` |
| Tabella | `#h1,h2\|r1c1,r1c2\|...` | `#id,unit\|1i,kg\|2,m` |
| Tabella con cells nested | `#h\|[a,b]\|{k=v}` | `#id,tags\|1i,[a,b]\|2,[c]` |

Una stringa va in virgolette solo se contiene spazi, ritorni a capo,
delimitatori sintattici (`,;=[]{}|"#&~`) o se sembra un numero. Tutto il
resto può essere "bare" — incluso email (`@`), URL (`:`, `/`), percorsi
(`/`, `.`), espressioni con parentesi (`(2+3)`).

Grammatica completa: vedi
[`docs/superpowers/specs/2026-05-22-adp-design.md`](docs/superpowers/specs/2026-05-22-adp-design.md).

## Convertitori

| Direzione | Funzione | Round-trip | Uso tipico |
|---|---|:---:|---|
| Python → ADP | `adp.encode(obj)` | ✓ | serializzazione |
| ADP → Python | `adp.decode(s)` | ✓ | deserializzazione |
| ADP → JSON | `adp.to_json(s)` | ✓ | macchine senza AI |
| JSON → ADP | `adp.from_json(s)` | ✓ | importazione da JSON |
| ADP → Markdown | `adp.to_markdown(s)` | ✗ (one-way) | lettura umana |
| ADP → HTML | `adp.to_html(s)` | ✗ (one-way) | dashboard, browser |

### HTML standalone con auto dark mode

```python
html_page = adp.to_html(adp_msg, title="Report Q1")
Path("report.html").write_text(html_page)
```

Produce un documento HTML5 completo con CSS embedded, tabelle bordate,
auto-switch light/dark via `prefers-color-scheme`, tooltip sui bytes,
code-block per testi multilinea. Da CLI: `adp to-html < msg.adp > out.html`.

### Pagina HTML dinamica (live viewer append-only)

Per scenari in cui un agente emette record ADP a flusso continuo (log,
monitoring, output multi-step), il sottocomando `adp serve` avvia un
piccolo server HTTP che apre una **pagina unica** auto-aggiornata via
Server-Sent Events: ogni nuovo record viene renderizzato e accodato in
fondo senza ricaricare la pagina.

```bash
my-agent-emitting-adp | uv run adp serve --port 8000
# Apri http://localhost:8000 nel browser; la pagina si aggiorna in tempo reale
```

![Live viewer SSE](docs/img/live-viewer.png)

Caratteristiche:

- zero dipendenze (usa solo stdlib `http.server`)
- pagina cronologica con timestamp per ogni record
- backfill automatico dei record già ricevuti se apri il browser dopo
- indicatore live/disconnected in basso a destra
- contatore record nell'header
- mantiene auto-scroll in fondo all'arrivo di nuovi dati

Casi d'uso tipici: monitoraggio agente long-running, debug di pipeline
multi-step, dashboard di sviluppo, demo a clienti.

Bytes nel passaggio JSON sono codificati come
`{"_adp_bytes": "<base64>"}` per preservarli.

## Integrazione con agenti AI

### 1. System prompt

```python
import adp
from anthropic import Anthropic

client = Anthropic()
resp = client.messages.create(
    model="claude-opus-4-7",
    system=adp.system_prompt(),
    messages=[{"role": "user", "content": "Restituisci un report con id 42 e due metriche."}],
    max_tokens=1024,
)
data = adp.decode(resp.content[0].text)
```

Il modulo `adp.prompt` espone `system_prompt()`, `few_shot_examples()`,
`few_shot_block()`.

### 2. Validator-with-retry

```python
def chat_in_adp(prompt: str, max_retries: int = 2) -> dict:
    history = [{"role": "user", "content": prompt}]
    for _ in range(max_retries + 1):
        out = llm_call(system=adp.system_prompt(), messages=history)
        try:
            return adp.decode(out)
        except adp.ADPParseError as e:
            history.append({"role": "assistant", "content": out})
            history.append({"role": "user", "content": f"Errore: {e}. Riemetti SOLO ADP valido."})
    raise RuntimeError("ADP non valido dopo retry")
```

### 3. Pipeline multi-agente

```python
def pipeline(input_data: dict) -> dict:
    msg = adp.encode(input_data)
    msg = agent_call("planner",  system=adp.system_prompt(), user=msg); adp.decode(msg)
    msg = agent_call("executor", system=adp.system_prompt(), user=msg); adp.decode(msg)
    msg = agent_call("reviewer", system=adp.system_prompt(), user=msg)
    return adp.decode(msg)
```

### 4. Persistenza session

```python
Path("session.adp").write_text(msg, encoding="utf-8")
restored = adp.decode(Path("session.adp").read_text(encoding="utf-8"))
```

## LUT — Look-Up Table condivisa (opzionale, ulteriore risparmio)

Se mittente e destinatario condividono una **LUT** (tabella di sigle) le
chiavi ricorrenti vengono compresse a 1-2 caratteri durante l'encoding e
ripristinate durante il decoding. Il messaggio finale non è più
testualmente leggibile ma resta lossless e attraversa lo stesso parser.

```python
import adp

LUT = {"user": "u", "id": "i", "name": "n", "email": "em"}
obj = {"user": {"id": 42, "name": "Adriano", "email": "a@b.c"}}

s = adp.encode(obj, key_lut=LUT)
# 'u={i=42;n=Adriano;em=a@b.c}'        (vs 'user={id=42;name=Adriano;email=a@b.c}')

assert adp.decode(s, key_lut=LUT) == obj
```

La libreria espone `adp.DEFAULT_AGENT_LUT`, una LUT pre-confezionata
per i nomi tipici dei messaggi inter-agente (`msg_id`, `from_agent`,
`intent`, `payload`, `id`, `name`, `status`, `value`, ...). Su un
messaggio di task tra agenti il risparmio passa da +5,7% (ADP solo) a
**+13,6%** (ADP+LUT) sui token cl100k_base.

Vincoli LUT: chiavi e sigle devono essere identificatori validi
`[A-Za-z_][A-Za-z0-9_-]*`; le sigle non possono coincidere con i
letterali riservati (`~`, `0`, `1`, `0i`, `1i`). `adp.validate_lut(lut)`
verifica entrambi i requisiti.

## Dynamic LUT (HPACK-style) + differential encoding

La LUT statica richiede che mittente e destinatario condividano in anticipo
lo stesso dizionario di sigle. Per scenari dove gli agenti non possono
coordinarsi a priori, oppure dove il vocabolario è specifico del dominio di
conversazione, ADP offre `ADPSession`: una **LUT dinamica adattiva
HPACK-style** (modellata sull'header compression di HTTP/2, RFC 7541) che
**cresce in modo sincronizzato durante la sessione** tramite update in-band,
e un **differential encoding inter-message** che invia solo il delta
rispetto al messaggio precedente quando conviene.

Le due tecniche sono ortogonali e combinabili: sullo stesso workload da 20
messaggi agent-to-agent, la combinazione `static LUT + dynamic LUT + diff
encoding` (full stack) riduce i token del **56,9% rispetto a JSON-min** e
del **60,1% rispetto a TOON** (best competitor).

### Uso base

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

Lo state cresce ad ogni messaggio scambiato. Persistenza locale automatica
in `~/.adp/lut_state.json` (override via parametro `path=` o env
`ADP_LUT_PATH`). LRU bounded a 256 entry di default. Tutto stdlib, zero
dipendenze nuove.

### Sintassi in-band

ADPSession emette tre prefissi top-level riservati all'inizio del messaggio:

| Prefisso | Significato |
|---|---|
| `_lut_add={alias=fullname;...}` | aggiunge nuove entry alla LUT dinamica |
| `_lut_reset=1` | pulisce completamente la LUT dinamica del receiver |
| `_base=ID;_diff={set=...;del=[...]}` | applica un diff al baseline ID |

Gli alias dinamici usano il namespace riservato `_N` (underscore + cifre),
disgiunto dalle short letters della LUT statica. Eviction LRU side-local
deterministica: sender e receiver evictono identicamente perché osservano
le stesse inserzioni e gli stessi USI.

### Differential encoding

Quando due messaggi consecutivi nella stessa direzione condividono la
maggior parte dei campi (pattern tipico: status report, incremental result,
state update), `ADPSession` calcola il diff e invia solo le modifiche:

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

L'encoder valuta automaticamente quando emettere diff: solo se il diff
codificato è inferiore al `diff_threshold * len(full_msg)` (default 0.7).
Per cambi massivi, fallback automatico a full encoding. Recovery dopo
desincronizzazione tramite `session.encode_full(obj)`.

### Sincronizzazione e recovery

Sender e receiver mantengono stati indipendenti che si allineano per
costruzione: ogni messaggio porta gli update LUT necessari per la sua
decodifica e (per il diff) un base_id che identifica univocamente il
payload precedente. Se il receiver non riconosce il base_id (perché ha
perso lo state, ha appena riavviato, o ha ricevuto messaggi fuori
ordine), solleva `ADPDiffSyncError`. L'app intercetta l'errore e chiede
al sender un full re-send via `encode_full()`.

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

### Confronto static vs dynamic vs full stack

Benchmark su 20 messaggi agent-to-agent (planner ↔ executor) con
tokenizer `cl100k_base`. Pattern realistico request/reply, payload
strutturato (annidamento dict + lista di eventi):

| Formato | Token totali | Δ vs JSON | Δ vs TOON |
|---|---:|---:|---:|
| JSON-min | 2079 | baseline | +7,6% |
| **TOON** | **2249** | **−8,2%** | baseline |
| ADP base (no LUT) | 1903 | +8,5% | +15,4% |
| ADP + static LUT (`DEFAULT_AGENT_LUT`) | 1833 | +11,8% | +18,5% |
| ADP + dynamic LUT (cold) | 2071 | +0,4% | +7,9% |
| ADP + dynamic + static LUT | 1890 | +9,1% | +16,0% |
| ADP + dynamic LUT + diff encoding | 977 | +53,0% | +56,6% |
| ADP + full stack (static + dynamic + diff) | 931 | +55,2% | +58,6% |
| **ADP full stack + tokenizer-aware cost** | **908** | **+56,3%** | **+59,6%** |

Con warm-start (pre-popolazione della LUT da log di sessione passata via
`session.warmup(messages_log)`), la seconda metà di una conversazione
risparmia ulteriormente ~6% rispetto al cold-start.

### Benchmark comprehensive: 7 workload × 4 lunghezze

Oltre al benchmark singolo qui sopra, una suite più ampia copre sette
workload diversi (status polling, tool use, narrative, ETL pipeline,
broadcast, DB query, mixed) a quattro lunghezze di conversazione
(10/50/100/500 messaggi), con stima costo $ per provider e latenza
encode/decode.

Sintesi @ 100 msg per workload — ADP full stack vs TOON (best competitor):

| Workload | Δ vs TOON | Risparmio $ per 1k msg (Sonnet 4.6) |
|---|---:|---:|
| status_polling | **+61.1%** | $0.156 |
| etl_pipeline | **+60.2%** | $2.61 |
| mixed | **+49.8%** | $0.418 |
| db_query_response | **+18.8%** | $0.114 |
| tool_use | **+15.3%** | $0.019 |
| multi_agent_broadcast | **+11.3%** | $0.015 |
| long_narrative | +1.3% | $0.003 |

Il guadagno è massimo sui workload con alta similarità inter-message
(status polling) o forte struttura tabulare (ETL pipeline). Sul testo
prosa libero (long_narrative) il margine è minimo perché diff/dyn LUT
hanno poco materiale ricorrente da catturare.

Report completo con tutte le lunghezze, latenza, pricing per provider:
[`benchmarks/comprehensive_report.md`](benchmarks/comprehensive_report.md).
Generabile con:

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

Il guadagno principale arriva dal diff encoding: su pattern request/reply
con payload simili tra messaggi successivi, il delta è una frazione minima
del payload completo. La dynamic LUT cold-start da sola non è
particolarmente competitiva perché la LUT statica copre già la maggior
parte dei pattern frequenti — il vero valore aggiunto è la combinazione
con il diff e la specializzazione dinamica sul vocabolario di sessione.

Per rigenerare il benchmark:

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
```

### Quando usare cosa

| Scenario | Configurazione consigliata |
|---|---|
| Singolo messaggio, agenti non coordinati | ADP base |
| Agenti che condividono codebase (pre-share LUT) | ADP + static LUT (`DEFAULT_AGENT_LUT`) |
| Sessione lunga, vocabolario dominio-specifico | ADP + dynamic LUT |
| Pattern request/reply, payload simili tra msg | ADP + diff encoding |
| **Workload misto, max risparmio** | **ADPSession full stack** |

### Parametri principali

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

# Pre-warm da corpus passato (accelera bootstrap)
session.warmup(past_messages_log)

# Recovery dopo sync error
try:
    obj = session.decode(received)
except (adp.ADPLUTSyncError, adp.ADPDiffSyncError):
    msg = session.encode_full(payload)  # forza re-send completo
```

API completa: `encode`, `encode_full`, `encode_reset`, `decode`, `reset`,
`reset_caps`, `save`, `stats`, `warmup`, `_run_tpd_promotion`,
property `peer_caps`. Helper stateless: `apply_lut_updates`,
`encode_with_dyn_lut`. Estimator standalone: `TokenizerCostEstimator`,
`estimate_cost`.

Vedi il modulo `src/adp/session.py` e la spec di design in
[`docs/superpowers/specs/2026-05-24-dynamic-lut-design.md`](docs/superpowers/specs/2026-05-24-dynamic-lut-design.md).

Optional extra per cost-benefit preciso:
```bash
pip install adp[tokenizer]   # aggiunge tiktoken
```

## Riduzione token misurata

Tokenizer `cl100k_base` (Claude 3.x / GPT-4), confronto vs JSON-min:

| Payload | JSON-min (tok) | ADP (tok) | Δ cl100k | Δ o200k |
|---|---:|---:|---:|---:|
| short_string_en | 15 | 13 | **+13,3%** | +13,3% |
| short_string_it | 18 | 16 | **+11,1%** | +11,8% |
| long_text_en | 115 | 109 | +5,2% | +5,3% |
| long_text_it | 176 | 170 | +3,4% | +3,7% |
| special_chars_en | 92 | 89 | +3,3% | +3,4% |
| special_chars_it | 134 | 131 | +2,2% | +2,4% |
| **tabular_en** | **241** | **145** | **+39,8%** | +40,1% |
| **tabular_it** | **333** | **164** | **+50,8%** | +46,4% |
| database_en | 150 | 134 | +10,7% | +10,5% |
| database_it | 180 | 157 | +12,8% | +12,8% |
| agent_task_en | 88 | 83 | +5,7% | +6,8% |
| agent_task_it | 118 | 113 | +4,2% | +5,0% |
| **contacts_en** (URL/email) | **145** | **94** | **+35,2%** | +34,9% |
| **nested_table_en** (cells annidate) | **100** | **75** | **+25,0%** | +30,3% |
| binary_en | (JSON N/A) | 279 | — | — |

Con `DEFAULT_AGENT_LUT` su `agent_task_en` il risparmio sale da +5,7% a **+13,6%**.

Lettura: ADP vince in modo significativo dove la struttura è tabella
omogenea o contiene molti URL/email (bare strings ampliate), e sui dati
binari dove JSON non funziona affatto. Sul testo libero il risparmio è
contenuto ma sempre positivo. Su nested-table-with-cells (caso tipico
dei messaggi multi-agente con sotto-strutture) il guadagno è del 25-30%.

Il file completo è in
[`benchmarks/results.md`](benchmarks/results.md). Per rigenerarlo:

```bash
uv run python -m benchmarks.compare_formats
```

### Bytes nativi: vantaggio strutturale

Sul payload `binary_en` (immagine 256 byte) i risultati sono:

| Formato | Bytes | Token cl100k | Lossless | Note |
|---|---:|---:|:---:|---|
| **ADP** | **412** | **279** | ✓ | bytes nativi via `b!base64` |
| JSON-min | — | — | — | TypeError: bytes non serializzabili |
| JSON-pretty | — | — | — | TypeError: bytes non serializzabili |
| TOML | — | — | — | TypeError: bytes non serializzabili |
| YAML | 460 | 299 | ✓ | richiede tag !!binary |
| MsgPack-b64 | 428 | 309 | ✓ | binario base64-encoded |
| XML | 908 | 469 | — | one-way, str(bytes) |

ADP è uno dei pochi formati testuali che gestisce bytes lossless senza
adattatori custom, ed è il più economico per token.

### Nota importante: si paga ciò che il modello EMETTE, non ciò che vede l'utente

I provider LLM (Anthropic, OpenAI, ...) addebitano gli **output token in
base a ciò che il modello emette**, non a ciò che la UI mostra. La
differenza non è banale:

| Cosa emesso dal modello | Pagato | Visto dall'utente |
|---|:---:|:---:|
| Testo finale della risposta | ✓ | ✓ |
| `thinking` / `reasoning` block (Claude 4, o1, o3) | **✓** | ✗ nascosto |
| Argomenti JSON dei tool call | **✓** | parziale |
| Caratteri Markdown raw (`**`, `##`, `|`) | ✓ | ✗ (renderizzati) |
| Token emessi prima di stop sequence | ✓ | ✗ |

Questa asimmetria è una **buona notizia per ADP**: chiedere al modello
di emettere ADP (denso, pochi token) e poi convertirlo lato client in
Markdown o JSON pretty produce la stessa esperienza utente a un costo
significativamente inferiore.

```
Modello emette ADP  ──── paghi pochi token  (output_tokens API)
        │
        └── client converte con adp.to_markdown()  ── zero costo
                                       │
                                       └── utente vede output ricco
```

Verifica nel response API:

```python
resp = client.messages.create(model="claude-opus-4-7", ...)
print("output_tokens:", resp.usage.output_tokens)
# include thinking + tool_use + text — non solo ciò che renderizzi
```

Su modelli con extended thinking, il reasoning interno può essere il
50-90% degli output token. Se il reasoning è verboso (es. JSON
intermedio) lo paghi tutto, anche se non viene mostrato.

## Esempi a confronto

Stesso payload nested-table (4 utenti con ruoli e permessi):

### ADP — 75 token, 159 byte

```
users=#id,name,roles,perms|1i,alice,[admin,ops],{read=1;write=1}|2,bob,[dev],{read=1;write=0}|3,carol,[dev,qa],{read=1;write=0}|4,dan,[viewer],{read=1;write=0}
```

### JSON-min — 100 token, 326 byte

```json
{"users":[{"id":1,"name":"alice","roles":["admin","ops"],"perms":{"read":true,"write":true}},{"id":2,"name":"bob","roles":["dev"],"perms":{"read":true,"write":false}},{"id":3,"name":"carol","roles":["dev","qa"],"perms":{"read":true,"write":false}},{"id":4,"name":"dan","roles":["viewer"],"perms":{"read":true,"write":false}}]}
```

### YAML — 135 token, 342 byte

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

### CSV — 88 token (vince marginalmente ma perde struttura)

```csv
id,name,roles,perms
1,alice,"['admin', 'ops']","{'read': True, 'write': True}"
...
```

CSV "vince" sui token solo perché annega le sub-strutture in stringhe
non parsabili: round-trip semantico fallito. ADP conserva la struttura
nativa.

## Immagini

Le immagini raster sono un caso speciale. Una volta convertite in
base64 per il canale testuale, il loro costo in token è dominato dal
base64 stesso, non dalla sintassi del wrapper. Misura su PNG
sintetico 128×128 RGBA:

| Formato | Token cl100k | Note |
|---|---:|---|
| JSON con `"data_b64":"..."` | 54.462 | base64 + sintassi JSON |
| ADP con `data=b!...` | 54.457 | base64 + sintassi ADP |
| RAW base64 puro | 54.425 | nessun wrapper, nessun metadato |

La differenza fra i tre è inferiore allo 0,1%. Sui binari inline il
wrapper non conta — è il base64 a dominare il costo.

ADP risolve il problema in due direzioni complementari: trattando le
immagini come **riferimenti** (ADP-DB) oppure comprimendole con
**strategie lossy** mirate al consumo LLM (modulo `adp.image`).

### Strategie lossy inline (modulo `adp.image`)

Misure su immagine sorgente PNG 256×256 RGB (gradiente + forme),
baseline 2.842 token cl100k per la versione lossless:

| Strategia | Token | Δ vs PNG | Lossless | Caso ideale |
|---|---:|---:|:---:|---|
| `passthrough` (PNG inline) | 2.842 | — | ✓ | qualità massima necessaria |
| `thumbnail_webp` q30 256×256 | 1.438 | **−49%** | ✗ | full-resolution lossy |
| `thumbnail_jpeg` size=128 q20 | 1.353 | **−52%** | ✗ | qualità decente |
| `thumbnail_jpeg` size=64 q50 | 934 | **−67%** | ✗ | analisi LLM generica |
| `thumbnail_jpeg` size=32 q30 | 524 | **−82%** | ✗ | essenza visiva |
| `hybrid` (thumb 24×24 + pHash + caption) | 550 | **−81%** | ✗ | best balance |
| `bitmap_8x8` (8×8 RGB raw) | 182 | **−94%** | ✗ | colori dominanti |
| `caption` (descrizione testuale) | 27 | **−99%** | ✗ | vision offline disponibile |
| `perceptual_hash` (64-bit) | 11 | **−99,6%** | ✗ | solo similarity check |
| ADP-DB ref `^id` (dopo bootstrap) | 5 | **−99,8%** | ✓ | asset ricorrente |

### API

```python
import adp
from adp.image import compress_for_llm, decompress, hamming_distance

# Strategia raccomandata generale: thumbnail 64×64 JPEG q50
payload = compress_for_llm(img_bytes, strategy="thumbnail_jpeg", size=64, quality=50)
msg = adp.encode({"task": "describe", "image": payload})
# ~930 token vs ~2840 PNG inline

# Hybrid: thumbnail visibile + hash + caption + metadati
payload = compress_for_llm(img_bytes, strategy="hybrid",
                            thumb_size=24, thumb_quality=30,
                            caption="red square on blue gradient")
# ~550 token, contiene tutto ciò che serve per analisi + similarity

# Perceptual hash: solo similarity check, nessuna decompressione
p1 = compress_for_llm(img_a, strategy="perceptual_hash")
p2 = compress_for_llm(img_b, strategy="perceptual_hash")
distance = hamming_distance(p1, p2)   # 0 = identici, basso = simili
```

Sette strategie disponibili: `passthrough`, `thumbnail_jpeg`,
`thumbnail_webp`, `perceptual_hash`, `bitmap_8x8`, `caption`,
`hybrid`. Tutte producono dict compatibili con `adp.encode()`.

### Strategia ADP-DB per asset ricorrenti

Quando gli stessi asset (avatar, icone, screenshot di riferimento)
viaggiano più volte tra gli stessi agenti, ADP-DB li promuove a
identificatori brevi nel database condiviso. Costo bootstrap una
sola volta, follow-up praticamente gratuiti.

```python
from adp import ADPStore

store = ADPStore(path="agents_shared.json")
with open("avatar_42.png", "rb") as f:
    img_id = store.put(f.read().decode("latin1"))
store.save()

# Messaggi successivi: ~5 token al posto di ~14.000
msg = adp.encode({"task": "lookup_user", "avatar_ref": img_id})
```

Su un workload di cento chiamate che riutilizzano tre immagini, il
risparmio totale misurato è di circa **16 milioni di token** rispetto
all'invio inline ripetuto.

### Decision tree rapido

| Necessità | Strategia consigliata |
|---|---|
| Identificare oggetti specifici in alta risoluzione | `passthrough` o `thumbnail_jpeg` size=256 |
| LLM deve descrivere o classificare l'immagine | `thumbnail_jpeg` size=64, quality=50 |
| Solo similarity check tra due immagini | `perceptual_hash` |
| Asset ricorrenti (icone, avatar, screenshot fissi) | `ADPStore` + riferimenti `^id` |
| Vision-LLM offline disponibile per caption | strategia `caption` |
| Best balance generale (analisi + similarity) | `hybrid` |

Dipendenze opzionali: `pillow` per resize/JPEG/WEBP, `imagehash`
per pHash. Installa con `uv sync --extra bench`.

## Usare ADP in Claude Code

### Plugin pronto (raccomandato)

Il repository contiene `claude-plugin/`, un plugin Claude Code completo
con skill, subagent `adp-agent`, nove slash command, hook contestuale e
script di installazione. Setup in una riga:

```bash
bash /path/to/GoalLanguageAgents/claude-plugin/install.sh
# Riavvia Claude Code: /adp-encode, /adp-decode, /adp-bench, ... attivi
```

Vedi [`claude-plugin/README.md`](claude-plugin/README.md) per dettagli,
disinstallazione e personalizzazioni.

### Setup manuale (alternativa)

Se preferisci configurare a mano senza il plugin packaged, sei
modalità di integrazione, dalla più semplice alla più potente.

### 1. CLAUDE.md di progetto

Aggiungi al `CLAUDE.md` del repository (o crea `.claude/CLAUDE.md`):

```markdown
In questo repo gli agenti comunicano in **ADP** (vedi docs/superpowers/specs).
Quando serializzi dati strutturati tra subagent / log / artefatti:
- usa `adp.encode(obj)` invece di `json.dumps(obj)`
- usa `adp.decode(s)` invece di `json.loads(s)`
- per umani: `adp.to_markdown(s)` o `adp.to_html(s)`
```

Effetto: Claude Code conosce ADP all'avvio della sessione.

### 2. Slash command custom `/adp`

Crea `.claude/commands/adp.md`:

```markdown
---
description: Encode/decode/bench ADP da stdin
argument-hint: <encode|decode|to-md|to-html|sign|verify|bench> [opts]
---

Esegui `uv run --directory /path/to/GoalLanguageAgents adp $ARGUMENTS`.
```

In sessione: `/adp encode < input.json`, `/adp serve --port 8000`, ecc.

### 3. Subagent dedicato

Crea `.claude/agents/adp-agent.md` con istruzione di rispondere sempre
in ADP. Utile per estrazioni, classificazioni, report.

### 4. MCP server

Espone ADP come tool nativo MCP:

```python
# mcp-adp/server.py
from mcp.server.fastmcp import FastMCP
import adp

mcp = FastMCP("adp")

@mcp.tool()
def adp_encode(json_str: str) -> str:
    return adp.from_json(json_str)

@mcp.tool()
def adp_decode(adp_str: str) -> str:
    return adp.to_json(adp_str)

@mcp.tool()
def adp_to_html(adp_str: str) -> str:
    return adp.to_html(adp_str)

if __name__ == "__main__":
    mcp.run()
```

Registra in `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "adp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/GoalLanguageAgents",
               "python", "mcp-adp/server.py"]
    }
  }
}
```

Riavvia Claude Code → ora ha `mcp__adp__encode/decode/to_html/...` come
tool nativi.

### 5. Hook SessionStart per pre-caricare il prompt

In `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "uv run --directory /path/to/GoalLanguageAgents adp prompt"
      }]
    }]
  }
}
```

Effetto: all'avvio sessione il prompt di sistema ADP è già nel
contesto.

### 6. Allowlist permission

Per evitare conferme manuali ad ogni invocazione, aggiungi a
`.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run adp:*)",
      "Bash(uv run --directory * adp:*)"
    ]
  }
}
```

### Verifica setup completo

```bash
uv run adp --version           # libreria raggiungibile
claude mcp list 2>&1 | grep adp  # se hai impostato MCP server
ls .claude/commands/adp.md     # slash command attivo
ls .claude/agents/adp-agent.md # subagent attivo
```

## Integrità — sign / verify

ADP di base non protegge un messaggio in transito: garantisce solo
round-trip semantico (`decode(encode(x)) == x`). Per detectare
corruzioni accidentali o modifiche intenzionali (incluse alterazioni
prodotte da un LLM intermediario), la libreria offre il modulo
opzionale `adp.integrity`, che appende un trailer della forma
`;_chk=<algo>:<hex>` al messaggio.

### Tre algoritmi disponibili

| Algoritmo | Hex | Overhead token | Forza | Caso ideale |
|---|---:|---:|---|---|
| `crc32` | 8 char | +~12 token | detection corruzione casuale | canale già autenticato (TLS), serve solo robustezza |
| `sha256` | 64 char | +~42 token | detection crittografica | LLM in mezzo (può alterare il testo) |
| `hmac` | 64 char | +~42 token | detection + autenticità mittente | flotte multi-agente con chiave condivisa |

L'overhead è **costante** (non scala con la lunghezza del payload),
quindi è proporzionalmente più caro sui messaggi piccoli e
trascurabile su quelli grandi.

### API Python

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

### Uso da CLI

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

Opzioni `adp sign`:
- `--algo crc32|sha256|hmac` (default `sha256`)
- `--key STRING` chiave HMAC inline (visibile nella shell history)
- `--key-file PATH` chiave HMAC da file (consigliato)

Opzioni `adp verify`:
- `--key` / `--key-file` per HMAC
- `--strict/--no-strict` se richiedere o no la presenza del trailer
- `--strip-only` rimuove il trailer senza verificarlo (sconsigliato)

### Caso d'uso più rilevante: detection alterazioni LLM

Quando un agente comunica attraverso un LLM intermediario, il modello
**può modificare silenziosamente** il messaggio: cambiare whitespace,
alterare un escape, aggiungere o togliere un carattere. Senza
checksum il destinatario non se ne accorge, e i dati corrotti
proseguono nella pipeline.

```
Agente A → encode → sign(sha256) → LLM B (forward) → verify → Agente C
                                       │
                                       └─ se modifica anche 1 byte
                                          → IntegrityError lato C
```

In ambienti dove l'LLM è solo un router/orchestrator del messaggio,
firmare con SHA-256 è il modo standard per garantire che il payload
arrivi intatto. Per autenticità del mittente (non solo integrità)
usare HMAC con chiave condivisa fuori-canale.

### Quando NON serve

| Canale | Integrità built-in? | Serve `adp.integrity`? |
|---|---|---|
| HTTPS / gRPC / TLS | sì (TLS) | no (ridondante) |
| File su disco condiviso | no | sì (CRC32 basta) |
| Coda di messaggi (Redis, RabbitMQ) | no | sì (CRC32 o SHA-256) |
| **LLM in mezzo** (agent → LLM → agent) | **NO** | **sì, SHA-256 o HMAC** |
| Storage long-term (audit log) | no | sì (SHA-256 per bit-rot) |

## Struttura del progetto

```
GoalLanguageAgents/
├── src/adp/
│   ├── __init__.py        API pubblica
│   ├── parser.py          ADP → Python (recursive-descent, zero deps)
│   ├── serializer.py      Python → ADP
│   ├── converters.py      JSON / Markdown (con _adp_bytes tag)
│   ├── prompt.py          system prompt + 8 few-shot pairs
│   ├── lut.py             LUT condivisa per chiavi (DEFAULT_AGENT_LUT)
│   ├── tpd.py             Token-aware Phrase Dictionary + learn_lut
│   ├── db.py              ADPStore: DB persistente di blob testuali
│   ├── image.py           7 strategie compressione immagini per LLM
│   ├── integrity.py       sign / verify (CRC32, SHA-256, HMAC)
│   ├── serve.py           live HTML viewer via SSE (append-only)
│   └── cli.py             CLI Click (encode/decode/sign/verify/serve/...)
├── tests/
│   ├── test_roundtrip.py        round-trip su 23 payload
│   ├── test_converters.py       JSON e Markdown
│   ├── test_v02_features.py     bytes, bare ampliate, nested tables
│   ├── test_lut.py              LUT key shortening
│   ├── test_tpd_db.py           TPD + ADPStore
│   ├── test_image.py            7 strategie immagine
│   └── test_integrity.py        sign / verify / tampering detection
├── benchmarks/
│   ├── payloads.py         18 payload (6 famiglie × IT/EN/ZH + binary)
│   ├── encoders.py         adattatori JSON/YAML/TOML/MsgPack/XML/CSV/RAW
│   ├── compare_formats.py  runner che genera results.md
│   └── results.md          report generato (~110 KB)
├── docs/
│   ├── superpowers/specs/2026-05-22-adp-design.md   design doc v0.2
│   └── ADP-relazione-completa.md                     relazione tecnica
├── examples/
│   ├── quickstart.py             demo base
│   └── two_agents_db.py          demo LUT/DB condivisa
├── pyproject.toml
└── README.md
```

## Sviluppo e test

```bash
uv sync --all-extras
uv run pytest                              # 80 test
uv run pytest --cov=adp                    # con coverage
uv run python -m benchmarks.compare_formats  # rigenera benchmark
uv run adp bench < tests/fixtures/example.json
```

La libreria core non ha dipendenze runtime oltre alla stdlib.

## Roadmap

- **v0.3.5 (corrente)** — **`ADPSession` completo**: dynamic LUT
  HPACK-style, differential encoding inter-message, capability negotiation
  con auto-degrade, tokenizer-aware cost estimation, pre-warm da corpus,
  TPD auto-promotion. Riduce i token del ~60% rispetto a TOON su workload
  multi-turn realistici. Vedi sezione [Dynamic LUT](#dynamic-lut-hpack-style--differential-encoding).
- **v0.4** — envelope opzionale (`from`, `to`, `id`, `intent`, `reply_to`)
  per protocolli inter-agente espliciti.
- **v0.5** — schema/contract opzionale, codegen Pydantic.
- **v0.6** — implementazione di riferimento in TypeScript.

## Licenza

MIT.
