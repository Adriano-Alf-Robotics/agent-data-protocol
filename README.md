# GLA — Goal Language Agents

**Formato testuale lossless e token-efficient per la comunicazione tra agenti AI.**

GLA è una libreria Python che definisce e implementa un piccolo linguaggio di
serializzazione progettato specificamente per lo scambio di messaggi tra
modelli linguistici. Non è pensato per essere letto da un essere umano a
prima vista: a quello pensa il convertitore che traduce in Markdown leggibile
o in JSON canonico per le macchine che non parlano AI.

L'obiettivo è ridurre il numero di token che gli agenti spendono per parlarsi
preservando tutta l'informazione strutturale di un payload JSON tipico —
mappe annidate, liste, tabelle, testi multilinea, primitive tipizzate — senza
mai introdurre perdita di dati.

## Indice

1. [Perché GLA](#perché-gla)
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

## Perché GLA

Quando due o più agenti AI si scambiano dati, la rappresentazione più
naturale è JSON. JSON funziona benissimo per le macchine, ma è verboso per
i tokenizer LLM: ogni virgoletta intorno a una chiave costa, ogni `true`
costa più di un singolo `1`, ogni tabella di righe omogenee paga il prezzo
di ripetere le chiavi a ogni riga.

GLA prende le decisioni di design che JSON non poteva permettersi:

- niente virgolette obbligatorie sui nomi né sulle stringhe semplici;
- `1` e `0` al posto di `true` e `false`;
- `~` al posto di `null`;
- newline letterali dentro le stringhe (niente sequenze `\n`);
- una notazione tabella dedicata per le liste di dizionari omogenei,
  che vince in modo netto sul prezzo per riga.

Il prezzo da pagare è la perdita di leggibilità diretta da parte di un
umano, ma il convertitore Markdown della libreria ricostruisce sempre una
versione leggibile, mentre il convertitore JSON ripristina una struttura
universalmente machine-readable.

## Installazione

GLA usa `uv` come gestore di dipendenze:

```bash
uv sync --all-extras
```

Per usare la libreria senza clonare il repository (una volta pubblicata):

```bash
uv add gla
```

Requisiti: Python 3.11 o superiore.

## Quickstart

```python
import gla

payload = {
    "user": {"id": 42, "name": "Adriano", "active": True},
    "metrics": [
        {"id": 1, "value": 42.0, "unit": "kg"},
        {"id": 2, "value": 3.14, "unit": "m"},
    ],
    "report": "Riga 1\nRiga 2 con \"virgolette\"",
}

s = gla.encode(payload)
print(s)
# &user:{id=42;name=Adriano;active=1}&&metrics:#id,value,unit|1i,42.0,kg|2,3.14,m&&report:"Riga 1
# Riga 2 con \"virgolette\""&

back = gla.decode(s)
assert back == payload  # round-trip lossless

print(gla.to_json(s))      # JSON canonico per macchine non-AI
print(gla.to_markdown(s))  # Markdown leggibile per umani
```

Da riga di comando:

```bash
echo '{"user":{"id":42,"name":"Adriano"}}' | uv run gla encode
# &user:{id=42;name=Adriano}&

echo '&user:{id=42;name=Adriano}&' | uv run gla decode
# {
#   "user": {"id": 42, "name": "Adriano"}
# }

uv run gla bench < payload.json    # confronto token GLA vs JSON
uv run gla prompt --few-shot       # stampa il prompt di sistema per LLM
```

## Sintassi in pillole

| Elemento | Sintassi | Esempio |
|---|---|---|
| Record top-level | `&nome:valore&` | `&user:42&` |
| Intero | nudo | `42`, `-7` |
| Intero 0 o 1 (disambiguazione) | suffisso `i` | `0i`, `1i` |
| Float | con punto decimale | `3.14`, `-0.5` |
| Booleano | `1` / `0` | `1` = true, `0` = false |
| Null | `~` | `~` |
| Stringa "bare" | senza virgolette | `Adriano`, `kg` |
| Stringa quotata | tra `"..."` | `"con spazio"` |
| Escape dentro stringa | solo `\"` e `\\` | `"dice \"ciao\""` |
| Lista | `[a,b,c]` | `[admin,root]` |
| Mappa | `{k=v;k=v}` | `{id=1;qty=2}` |
| Tabella | `#h1,h2|r1c1,r1c2|...` | `#id,unit|1i,kg|2,m` |

Una stringa è candidata a essere bare se contiene solo caratteri
`[A-Za-z_][A-Za-z0-9_.-]*` e non collide con i letterali riservati (`~`,
`0`, `1`, `0i`, `1i`). Tutto il resto va in virgolette doppie. Dentro le
virgolette i ritorni a capo sono letterali, senza bisogno di escape.

La grammatica formale completa è in
[`docs/superpowers/specs/2026-05-22-gla-design.md`](docs/superpowers/specs/2026-05-22-gla-design.md).

## Convertitori

GLA viene fornito con due convertitori bidirezionali e uno mono-direzionale:

| Direzione | Funzione | Round-trip | Uso tipico |
|---|---|:---:|---|
| Python → GLA | `gla.encode(obj)` | ✓ | serializzazione |
| GLA → Python | `gla.decode(s)` | ✓ | deserializzazione |
| GLA → JSON | `gla.to_json(s)` | ✓ | macchine senza AI |
| JSON → GLA | `gla.from_json(s)` | ✓ | importazione da JSON |
| GLA → Markdown | `gla.to_markdown(s)` | ✗ (one-way) | lettura umana |

I convertitori sono deterministici: `encode(decode(encode(x)))` produce
sempre la stessa stringa. La copertura di test garantisce
`decode(encode(obj)) == obj` su tutti i tipi supportati, compresi caratteri
Unicode, emoji, sequenze di escape, testo multilinea, tabelle eterogenee,
strutture profondamente annidate.

## Integrazione con agenti AI

Ci sono tre modi non esclusivi per far parlare un LLM in GLA:

### 1. System prompt (zero codice nel modello)

```python
import gla
from anthropic import Anthropic

client = Anthropic()
resp = client.messages.create(
    model="claude-opus-4-7",
    system=gla.system_prompt(),
    messages=[{"role": "user", "content": "Restituisci un report con id 42 e due metriche."}],
    max_tokens=1024,
)
gla_text = resp.content[0].text
data = gla.decode(gla_text)
```

Il modulo `gla.prompt` espone:

- `gla.system_prompt()` — istruzioni complete sul formato, pronte da incollare
  nel campo system del modello;
- `gla.few_shot_examples()` — lista di coppie `(dict Python, stringa GLA)`
  da inserire come few-shot per agganciare lo stile;
- `gla.few_shot_block()` — versione testuale pronta per il prompt.

### 2. Validator-with-retry (production-grade)

```python
import gla

def chat_in_gla(prompt: str, max_retries: int = 2) -> dict:
    """Chiede una risposta in GLA, valida, riprova in caso di errore."""
    last_err = None
    history = [{"role": "user", "content": prompt}]
    for _ in range(max_retries + 1):
        out = llm_call(system=gla.system_prompt(), messages=history)
        try:
            return gla.decode(out)
        except gla.GLAParseError as e:
            last_err = str(e)
            history.append({"role": "assistant", "content": out})
            history.append({
                "role": "user",
                "content": f"Errore di parsing GLA: {e}. Riemetti SOLO GLA valido, niente prosa.",
            })
    raise RuntimeError(f"Impossibile ottenere GLA valido: {last_err}")
```

Questo pattern è particolarmente utile con modelli più piccoli, che
talvolta inseriscono prosa indesiderata o sbagliano un escape: il validator
intercetta l'errore e il modello correggere nel turno successivo.

### 3. Pipeline multi-agente

Quando una serie di agenti si passa output strutturato in sequenza, GLA
diventa il "linguaggio interno" della pipeline:

```python
def pipeline(input_data: dict) -> dict:
    msg = gla.encode(input_data)

    msg = agent_call("planner",  system=gla.system_prompt(), user=msg)
    gla.decode(msg)  # valida prima di passare oltre

    msg = agent_call("executor", system=gla.system_prompt(), user=msg)
    gla.decode(msg)

    msg = agent_call("reviewer", system=gla.system_prompt(), user=msg)
    return gla.decode(msg)
```

Vantaggi rispetto al passaggio in JSON nudo:

- ogni step paga meno token su input e output;
- i log della pipeline diventano la traccia letterale del messaggio
  scambiato, salvabile su disco con un semplice `open(...).write(msg)`;
- la conversione in JSON per una eventuale UI non-AI è un singolo
  `gla.to_json(msg)`.

### 4. Salvataggio e ricaricamento del contesto

Una conversazione GLA è un puro flusso di testo UTF-8. Per persisterla:

```python
Path("session.gla").write_text(msg, encoding="utf-8")
# più tardi, anche in un'altra macchina o un altro processo
restored = gla.decode(Path("session.gla").read_text(encoding="utf-8"))
```

Nessuna libreria di stato, nessun runtime: il messaggio basta a sé stesso.

## Riduzione token misurata

Lo script `benchmarks/compare_formats.py` confronta GLA con JSON minified,
JSON pretty, YAML, TOML, MessagePack (base64) e XML su sei famiglie di
payload, in versione inglese e italiana. La sintesi (tokenizer
`cl100k_base`, riferimento Claude 3.x / GPT-4):

| Payload | JSON-min (token) | GLA (token) | Riduzione GLA |
|---|---:|---:|---:|
| short_string_en | 15 | 14 | +6,7% |
| short_string_it | 18 | 17 | +5,6% |
| long_text_en | 115 | 111 | +3,5% |
| long_text_it | 176 | 172 | +2,3% |
| special_chars_en | 92 | 93 | −1,1% |
| special_chars_it | 134 | 136 | −1,5% |
| **tabular_en** | **241** | **147** | **+39,0%** |
| **tabular_it** | **333** | **166** | **+50,2%** |
| database_en | 150 | 135 | +10,0% |
| database_it | 180 | 158 | +12,2% |
| agent_task_en | 88 | 86 | +2,3% |
| agent_task_it | 118 | 116 | +1,7% |

Lettura: GLA vince in modo significativo dove la struttura ha forma di
tabella omogenea (caso comune nei dataset scambiati tra agenti). Sul testo
libero il risparmio è marginale, perché in quel regime è il contenuto a
dominare la spesa, non la sintassi. In due payload con tanti caratteri
speciali GLA paga un piccolo prezzo: l'escape di backslash e virgolette
costa quanto in JSON.

Il vantaggio è leggermente più contenuto con il tokenizer `o200k_base`
(GPT-4o, Opus 4.x), che è già più aggressivo sui formati esistenti, ma la
direzione resta la stessa.

Il file completo, comprensivo di tempi di encoding/decoding e di esempi
codificati in tutti i formati per ogni payload, è generato in
[`benchmarks/results.md`](benchmarks/results.md). Per rigenerarlo:

```bash
uv run python -m benchmarks.compare_formats
```

### Tempi e trasferimento

I tempi di encoding e decoding per un singolo payload tipico (database
nested, ~150 token) si misurano in microsecondi:

| Operazione | Tempo mediano |
|---|---:|
| `gla.encode(obj)` | ~10–25 µs |
| `gla.decode(s)` | ~30–80 µs |
| `json.dumps(obj)` | ~5–10 µs |
| `json.loads(s)` | ~5–10 µs |

GLA è scritto in Python puro senza dipendenze, quindi il decoder è 5–10×
più lento di `json.loads`. Su payload tipici da agenti AI (centinaia di
byte) si tratta sempre di tempi sotto i 100 microsecondi: trascurabili
rispetto al tempo di inferenza del modello, che si misura in secondi.

Il tempo di trasferimento sulla rete è proporzionale ai byte, quindi al
risparmio strutturale. Su un payload tabulare da 800 byte JSON che diventa
317 byte GLA, su un canale a 1 Mbit/s reale si guadagnano circa 4 ms;
trascurabile in latenza ma significativo nei contesti con migliaia di
messaggi al minuto.

## Esempi a confronto

Stesso payload tabolare (10 dipendenti) in quattro formati:

### GLA — 147 token, 317 byte

```
&employees:#id,name,department,salary,active|1i,Alice,Sales,52000.0,1|2,Bruno,Engineering,68000.0,1|3,Carla,Sales,55000.0,0|4,David,Engineering,72000.0,1|5,Elena,Marketing,49000.0,1|6,Fabio,Engineering,80000.0,1|7,Grace,Sales,53000.0,1|8,Hugo,Marketing,51000.0,0|9,Irene,Engineering,75000.0,1|10,Luca,Sales,56000.0,1&
```

### JSON minified — 241 token, 808 byte

```json
{"employees":[{"id":1,"name":"Alice","department":"Sales","salary":52000.0,"active":true},{"id":2,"name":"Bruno","department":"Engineering","salary":68000.0,"active":true},{"id":3,"name":"Carla","department":"Sales","salary":55000.0,"active":false}, ...]}
```

### YAML — 303 token, 794 byte

```yaml
employees:
- id: 1
  name: Alice
  department: Sales
  salary: 52000.0
  active: true
- id: 2
  name: Bruno
  department: Engineering
  salary: 68000.0
  active: true
...
```

### CSV — 133 token (vince ma non rappresenta strutture annidate)

```csv
id,name,department,salary,active
1,Alice,Sales,52000.0,True
2,Bruno,Engineering,68000.0,True
...
```

CSV batte GLA sui token per payload puramente tabulari, ma non gestisce
annidamenti né tipi: per uno scambio agente↔agente non è praticabile come
formato unico. GLA mantiene il vantaggio tabella **senza rinunciare** alla
generalità.

## Struttura del progetto

```
GoalLanguageAgents/
├── src/gla/
│   ├── __init__.py        API pubblica
│   ├── parser.py          GLA → Python (recursive-descent, zero deps)
│   ├── serializer.py      Python → GLA
│   ├── converters.py      JSON / Markdown
│   ├── prompt.py          system prompt + few-shot
│   └── cli.py             CLI Click (encode/decode/to-md/bench/...)
├── tests/
│   ├── test_roundtrip.py  54 test su tutti i tipi
│   └── test_converters.py JSON e Markdown converter
├── benchmarks/
│   ├── payloads.py        12 payload (6 famiglie × IT/EN)
│   ├── encoders.py        adattatori JSON/YAML/TOML/MsgPack/XML/CSV
│   ├── compare_formats.py runner che genera results.md
│   └── results.md         report generato (~51 KB)
├── docs/superpowers/specs/
│   └── 2026-05-22-gla-design.md   design document e grammatica
├── pyproject.toml
└── README.md              (questo file)
```

## Sviluppo e test

```bash
uv sync --all-extras                       # installa deps + dev + bench
uv run pytest                              # 54 test, ~0,05 s
uv run pytest --cov=gla                    # con coverage
uv run python -m benchmarks.compare_formats  # rigenera benchmark
uv run gla bench < tests/fixtures/example.json   # confronto token al volo
```

La libreria core (`gla/parser.py`, `gla/serializer.py`,
`gla/converters.py`) non ha dipendenze runtime oltre alla standard library:
la CLI dipende da `click`, i benchmark da `tiktoken`, `pyyaml`, `tomli-w`,
`msgpack`.

## Roadmap

- **v0.2** — envelope opzionale (`from`, `to`, `id`, `intent`, `reply_to`)
  come strato aggiuntivo per protocolli inter-agente più espliciti.
- **v0.3** — schema/contract opzionale per dichiarare la forma attesa di un
  messaggio e validarla in ricezione.
- **v0.4** — convertitori aggiuntivi (TOML, YAML) bidirezionali.
- **v0.5** — implementazione di riferimento in TypeScript per integrazione
  con backend Node/Deno e con MCP server.

## Licenza

MIT. Vedi `pyproject.toml`.
