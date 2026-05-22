# ADP — Adriano Dal Pastro format

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

## Indice

1. [Perché ADP](#perché-adp)
2. [Installazione](#installazione)
3. [Quickstart](#quickstart)
4. [Sintassi in pillole](#sintassi-in-pillole)
5. [Convertitori](#convertitori)
6. [Integrazione con agenti AI](#integrazione-con-agenti-ai)
7. [Riduzione token misurata](#riduzione-token-misurata)
8. [Esempi a confronto](#esempi-a-confronto)
9. [Struttura del progetto](#struttura-del-progetto)
10. [Sviluppo e test](#sviluppo-e-test)
11. [Roadmap](#roadmap)
12. [Licenza](#licenza)

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

## Struttura del progetto

```
GoalLanguageAgents/
├── src/adp/
│   ├── __init__.py        API pubblica
│   ├── parser.py          ADP → Python (recursive-descent, zero deps)
│   ├── serializer.py      Python → ADP
│   ├── converters.py      JSON / Markdown (con _adp_bytes tag)
│   ├── prompt.py          system prompt + 8 few-shot pairs
│   └── cli.py             CLI Click
├── tests/
│   ├── test_roundtrip.py       round-trip su 23 payload
│   ├── test_converters.py      JSON e Markdown
│   └── test_v02_features.py    bytes, bare ampliate, nested tables, error cases
├── benchmarks/
│   ├── payloads.py        15 payload (6 famiglie × IT/EN + 3 v0.2-specifici)
│   ├── encoders.py        adattatori JSON/YAML/TOML/MsgPack/XML/CSV
│   ├── compare_formats.py runner che genera results.md
│   └── results.md         report generato (~63 KB)
├── docs/superpowers/specs/
│   └── 2026-05-22-adp-design.md   design document v0.2
├── examples/quickstart.py
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

- **v0.3** — envelope opzionale (`from`, `to`, `id`, `intent`, `reply_to`)
  per protocolli inter-agente espliciti.
- **v0.4** — schema/contract opzionale, codegen Pydantic.
- **v0.5** — implementazione di riferimento in TypeScript.

## Licenza

MIT.
