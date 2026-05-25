# ADP — Agent Data Protocol
## Relazione tecnica completa

> Documento consolidato della sessione di analisi e sviluppo del 22-05-2026.
> Versione del formato: **v0.2**.
> Autore: Adriano Dal Pastro, con assistenza Claude Opus 4.7.

---

## Indice

1. [Sommario esecutivo](#1-sommario-esecutivo)
2. [Cos'è ADP](#2-cosè-adp)
3. [Sintassi in pillole](#3-sintassi-in-pillole)
4. [Estensioni opzionali: LUT, TPD, DB](#4-estensioni-opzionali-lut-tpd-db)
5. [Confronto con altri formati](#5-confronto-con-altri-formati)
6. [Tabella riassuntiva token EN/IT/ZH](#6-tabella-riassuntiva-token-enitzh)
7. [Esempio realistico: report aziendale](#7-esempio-realistico-report-aziendale)
8. [Vantaggi reali con LLM](#8-vantaggi-reali-con-llm)
9. [Perché i token si riducono se gli LLM emettono testo](#9-perché-i-token-si-riducono-se-gli-llm-emettono-testo)
10. [Integrazione con LLM (Anthropic / OpenAI / altri)](#10-integrazione-con-llm)
11. [Integrazione con Claude Code](#11-integrazione-con-claude-code)
12. [Dove vive la LUT](#12-dove-vive-la-lut)
13. [Immagini: tre strategie a confronto](#13-immagini-tre-strategie-a-confronto)
14. [Relazione finale dei risultati](#14-relazione-finale-dei-risultati)

---

## 1. Sommario esecutivo

ADP è un formato testuale di scambio messaggi tra agenti AI con quattro
caratteristiche distintive: lossless, token-efficient, supporto nativo
ai dati binari, e capacità di battere il flat text (testo libero) tra
il 55% e l'80% nei token quando coadiuvato dal modulo TPD.

Risultati misurati con tokenizer `cl100k_base` (Claude 3.x / GPT-4) e
`o200k_base` (GPT-4o / Opus 4.x) su quindici payload di test in
inglese, italiano e cinese:

- dati tabulari omogenei: ADP risparmia il 40-50% di token rispetto a
  JSON minified;
- strutture annidate generiche: ADP risparmia il 10-15%;
- prosa libera mono-stringa: ADP+TPD batte il flat text del 55-80%;
- payload binari: ADP gestisce nativamente i bytes lossless, mentre
  JSON e TOML falliscono;
- round-trip lossless: 100 test verdi sull'intera libreria.

L'effetto economico atteso, su un caso d'uso di centomila chiamate al
mese a un report mensile di circa 2440 token JSON, è di circa
ottomila dollari risparmiati al mese sul piano Claude Opus 4.7. Lo
stesso budget di contesto da duecentomila token consente di leggere
ottantuno report in JSON minified contro centotrentadue report in
ADP+TPD, un guadagno netto del sessantatré percento in capacità
storica accessibile.

---

## 2. Cos'è ADP

ADP è un linguaggio di serializzazione testuale custom, ASCII/UTF-8,
progettato esplicitamente per la comunicazione fra agenti basati su
modelli linguistici di grandi dimensioni. Non è pensato per essere
letto comodamente da un essere umano a colpo d'occhio: il
convertitore Markdown ricostruisce sempre una versione leggibile,
mentre il convertitore JSON canonico restituisce una struttura
universalmente machine-readable.

L'obiettivo è ridurre il numero di token che gli agenti spendono per
parlarsi preservando tutta l'informazione strutturale di un payload
JSON tipico — mappe annidate, liste, tabelle con cells annidate,
testi multilinea, primitive tipizzate, bytes — senza mai introdurre
perdita di dati.

ADP prende le decisioni di design che JSON non poteva permettersi:

- niente virgolette obbligatorie su chiavi o stringhe semplici;
- `1` e `0` al posto di `true` e `false`;
- `~` al posto di `null`;
- newline letterali dentro le stringhe (niente sequenze `\n`);
- una notazione tabella dedicata per le liste di dizionari omogenei,
  che ammette cells annidate (liste, mappe);
- bare strings ampliate per assorbire URL, email e percorsi senza
  virgolette;
- bytes nativi tramite prefisso `b!` + base64 standard;
- top-level senza wrappers (`name=value;name=value`).

---

## 3. Sintassi in pillole

| Elemento | Sintassi | Esempio |
|---|---|---|
| Top-level | `name=value;name=value` | `id=42;ok=1` |
| Intero | nudo | `42`, `-7` |
| Intero 0 o 1 (disambiguazione) | suffisso `i` | `0i`, `1i` |
| Float | con punto decimale | `3.14`, `-0.5` |
| Booleano | `1` / `0` | `1` = true |
| Null | `~` | `~` |
| Bytes | `b!<base64>` | `b!aGVsbG8=` |
| Stringa bare | senza virgolette | `Adriano`, `ops@acme.example`, `https://x.y/api` |
| Stringa quotata | tra `"..."` | `"con spazio"` |
| Escape dentro stringa | solo `\"` e `\\` | `"dice \"ciao\""` |
| Lista | `[a,b,c]` | `[admin,root]` |
| Mappa | `{k=v;k=v}` | `{id=1;qty=2}` |
| Tabella | `#h1,h2\|r1c1,r1c2\|...` | `#id,unit\|1i,kg\|2,m` |
| Tabella nested | cells contengono list/map | `#id,tags\|1i,[a,b]\|2,[c]` |

Una stringa va in virgolette solo se contiene spazi, ritorni a capo,
delimitatori sintattici (`,;=[]{}|"#&~`) o se sembra un numero. Tutto
il resto può essere "bare", inclusi email (`@`), URL (`:`, `/`),
percorsi (`/`, `.`), espressioni con parentesi.

---

## 4. Estensioni opzionali: LUT, TPD, DB

ADP nasce essenziale, ma sono disponibili tre estensioni opzionali
per spingere oltre la compressione.

### 4.1 LUT — sigle per chiavi ricorrenti

Mittente e destinatario condividono una tabella di sigle che mappa
nomi-campo lunghi a identificatori brevi. Le chiavi non presenti nella
LUT restano invariate. La libreria fornisce `DEFAULT_AGENT_LUT`, una
LUT pre-confezionata per i campi tipici dei messaggi inter-agente
(`msg_id`, `from_agent`, `intent`, `payload`, eccetera).

```python
import adp
lut = {"user": "u", "id": "i", "name": "n"}
adp.encode({"user": {"id": 42, "name": "Adriano"}}, key_lut=lut)
# 'u={i=42;n=Adriano}'
```

Tipico guadagno aggiuntivo: dal 7% al 14% di token in più rispetto a
ADP base, quando le chiavi sono nel dizionario.

### 4.2 TPD — Token-aware Phrase Dictionary

Dizionario di frasi pre-condiviso. Si applica al contenuto testuale
delle stringhe (non solo alle chiavi). Un algoritmo greedy impara
ad-hoc, sul testo da scambiare, quali sequenze sostituire con codici
ASCII a 1 token (testati col tokenizer di riferimento). I codici
scelti sono garantiti non presenti nel testo originale, quindi non
servono escape.

```python
from adp.tpd import learn_lut, encode_text, decode_text
text = "Revenue grew 12% year over year, driven primarily by enterprise sales..."
lut = learn_lut(text, max_codes=40)
compressed = encode_text(text, lut)        # 33 token invece di 101
assert decode_text(compressed, lut) == text
```

Tipico guadagno sui mono-stringa: dal 55% all'80% di token in meno
rispetto al testo flat.

### 4.3 ADP-DB — database persistente di frammenti

Generalizzazione del TPD a uno store crescente nel tempo. Due agenti
condividono un file JSON (o un database remoto) di blob testuali
identificati da ID brevi. Quando un agente vuole inviare un blob già
nel DB, manda solo `^<id>`. Quando vuole introdurre un blob nuovo,
manda inline `^+<id>|contenuto|^`, e il destinatario lo registra
automaticamente.

```python
from adp import ADPStore
store = ADPStore(path="shared.adp.json")
store.seed({"Revenue grew 12% year over year": "a"})
compressed = store.encode("Q1: Revenue grew 12% year over year. Q2: Revenue grew 12% year over year.")
# 'Q1: ^a. Q2: ^a.'
```

---

## 5. Confronto con altri formati

| Formato | Lossless | Bytes nativi | Annidamento | Token-efficient | Dipendenze |
|---|:---:|:---:|:---:|:---:|---|
| RAW flat text | ✗ | ✗ | ✗ | base | nessuna |
| JSON | ✓ | ✗ | ✓ | base | stdlib |
| YAML | ✓ | parziale | ✓ | media | PyYAML |
| TOML | ✓ | ✗ | ✓ | media | stdlib |
| XML | parziale | ✗ | ✓ | bassa | stdlib |
| MessagePack | ✓ | ✓ | ✓ | bassa (su canale testo) | msgpack |
| **ADP** | ✓ | ✓ | ✓ | alta | nessuna |
| **ADP + LUT** | ✓ | ✓ | ✓ | alta+ | nessuna |
| **ADP + TPD** | ✓ | ✓ | ✓ | massima | nessuna (runtime) |

---

## 6. Tabella riassuntiva token EN/IT/ZH

Numeri misurati con `cl100k_base`. Best per riga in grassetto.

### 6.1 Testi lunghi

| Formato | EN | IT | ZH | Note |
|---|---:|---:|---:|---|
| **ADP** | **109** | **170** | **206** | |
| ADP+LUT | 109 | 170 | 206 | |
| JSON-min | 115 | 176 | 211 | |
| JSON-pretty | 121 | 182 | 218 | |
| YAML | 115 | 180 | 213 | |
| TOML | 115 | 176 | 212 | |
| MsgPack-b64 | 423 | 513 | 416 | base64 inflate |
| XML | 118 | 180 | 214 | |

### 6.2 Stesso payload mono-stringa con TPD

| Lingua | RAW flat | ADP solo | **ADP+TPD** | Risparmio TPD vs RAW |
|---|---:|---:|---:|---:|
| Inglese | 101 | 103 | **34** | **−66%** |
| Italiano | 157 | 160 | **31** | **−80%** |
| Cinese | 194 | 197 | **82** | **−58%** |

Tutti dentro o sopra il target del 30-60%.

### 6.3 Dati strutturati

| Payload | RAW flat | JSON-min | ADP | ADP+LUT | ADP+TPD |
|---|---:|---:|---:|---:|---:|
| Tabella 10 record | 331 | 241 | **145** | 147 | 145 |
| Tabella nested (cells annidate) | 135 | 100 | **75** | 76 | 75 |
| Contatti URL/email | 190 | 145 | **94** | 96 | 109 |
| Task agente multi-step EN | 114 | 88 | 83 | **76** | 83 |
| Task agente multi-step ZH | 138 | 110 | 107 | **102** | 107 |
| Payload binario 256 byte | 447 | non gestito | **263** | 262 | 263 |

### 6.4 Risparmio % vs RAW flat (obiettivo principale)

| Payload | ADP solo | ADP+TPD |
|---|---:|---:|
| pure_text_en | +2% | **+66%** |
| pure_text_it | +2% | **+80%** |
| pure_text_zh | +2% | **+58%** |
| long_text_en | +8% | **+55%** |
| long_text_it | +5% | **+68%** |
| long_text_zh | +4% | **+57%** |
| tabular_en | +56% | +56% |
| nested_table_en | +44% | +44% |
| contacts_en | +51% | +43% |

Tutti i payload raggiungono o superano il 30-60% di risparmio sul
flat text, in molti casi schiaccientemente.

---

## 7. Esempio realistico: report aziendale

Payload corposo: un report mensile aziendale composto da metadati,
indicatori chiave (KPI), cinquanta righe di vendita (tabella), cinque
top customer, quattro eventi loggati, tre regioni, una sintesi
testuale, tre contatti. Misure reali da Python.

### 7.1 Dimensioni e token

| Formato | Byte | Token cl100k | Token o200k | Δ vs JSON-min |
|---|---:|---:|---:|---:|
| JSON minified | 7.904 | 2.443 | 2.441 | baseline |
| JSON pretty | 11.955 | 3.956 | 3.949 | −62% (peggio) |
| **ADP** | **3.475** | **1.564** | 1.559 | **+36%** |
| **ADP + TPD** | **3.275** | **1.515** | 1.511 | **+38%** |

### 7.2 Impatto economico

Prezzi Claude Opus 4.7: 15 USD per milione di token in input, 75 USD
per milione in output. Scenario: centomila chiamate al mese.

| Formato | Token totali | Input USD | Output USD | Totale USD/mese |
|---|---:|---:|---:|---:|
| JSON minified | 244.300.000 | 3.664 | 18.322 | **21.987** |
| JSON pretty | 395.600.000 | 5.934 | 29.670 | **35.604** |
| ADP | 156.400.000 | 2.346 | 11.730 | **14.076** |
| ADP + TPD | 151.500.000 | 2.272 | 11.362 | **13.635** |

Risparmio annuo ADP vs JSON-min su questo workload: circa
novantaquattromila novecento dollari.

### 7.3 Impatto sul context window

A parità di duecentomila token disponibili, quanti report ci stanno?

| Formato | Report in 200k token |
|---|---:|
| JSON pretty | 50 |
| JSON minified | 81 |
| ADP | **127** |
| ADP + TPD | **132** |

Un agente conversa con cronologia molto più ricca a parità di vincolo
tecnico.

### 7.4 Anteprima ADP del payload

```
report_id=RPT-2026-04;company="Acme Corporation Ltd.";period={year=2026;
month=4;from="2026-04-01";to="2026-04-30";currency=EUR};kpis={revenue=
1287430.5;cost=894120.75;margin=393309.75;margin_pct=30.55;new_customers=142;
churned_customers=18;active_subscriptions=8417};sales=#order_id,customer_id,
amount,items,channel,country,paid|ORD-1000,100,150.0,1i,web,IT,0|
ORD-1001,107,173.7,2,mobile,DE,1|...
```

Le cinquanta righe di vendita stanno tutte in una sola tabella inline
che ripete l'header una volta sola. Lo stesso JSON ripete
`"order_id":..., "customer_id":..., "amount":..., "items":...,` per
cinquanta volte.

---

## 8. Vantaggi reali con LLM

1. **Soldi**: il risparmio diretto in token, su volume costante,
   diventa risparmio dollaro proporzionale. Su un volume realistico
   di centomila chiamate al mese il risparmio annuo si misura in
   decine di migliaia di dollari.
2. **Spazio**: a parità di context window, ADP fa entrare il 30-60%
   in più di dati utili. Una conversazione storica di cinquanta
   messaggi che pesa cinquemila token in JSON ne pesa circa tremila
   cinquecento in ADP, liberando millecinquecento token per nuova
   storia.
3. **Latenza**: l'LLM emette meno token in output, quindi risponde
   più velocemente. Su un payload tabulare grande la differenza è
   di circa il 30-40% di secondi di generazione.
4. **Meno allucinazioni sintattiche**: la sintassi piatta di ADP, con
   separatori non ambigui e niente virgolette obbligatorie, riduce i
   casi in cui un modello sbaglia la chiusura di parentesi, l'escape
   delle virgolette o la collocazione delle virgole.
5. **Tool calling più economico**: gli argomenti dei tool e le
   risposte vengono tokenizzati come testo normale. Sostituire il
   payload JSON con ADP nei tool call moltiplica il risparmio per il
   numero di chiamate.
6. **Annidamento e bytes nello stesso canale**: JSON non supporta
   `bytes` nativamente. ADP sì, con `b!base64`. Si trasferiscono
   thumbnail, embedding compressi, hash binari senza un protocollo
   custom.
7. **Persistenza conversazione zero-config**: salvare un payload ADP
   è scrivere una stringa UTF-8 su file. Ricaricarlo è leggerla e
   chiamare `adp.decode()`. Nessun runtime, nessuna libreria di
   stato, nessuno schema esterno.
8. **Multi-agent omogeneo**: tutti gli agenti parlano la stessa
   lingua. Convertitori a JSON o Markdown ne fanno la traduzione per
   sistemi esterni che non parlano ADP.
9. **Storage log compatto**: il log delle conversazioni LLM, spesso
   gigabyte di JSON, si comprime del 40-60% in ADP+TPD a parità di
   informazione, accelerando grep e backup.

---

## 9. Perché i token si riducono se gli LLM emettono testo

Domanda apparentemente paradossale: se l'LLM produce testo, ovvero
caratteri, come può un formato testuale risparmiare token rispetto a
un altro formato testuale?

La risposta sta nella differenza tra caratteri e token. L'LLM non
lavora a caratteri ma a unità lessicali del vocabolario del
tokenizer (BPE). Il vocabolario di `cl100k_base` ha circa
centomila voci, ciascuna delle quali rappresenta una sequenza di byte
che il tokenizer riconosce come unità singola.

Esempi misurati: la stringa `true` di quattro caratteri è un solo
token. La cifra `1` di un carattere è anch'essa un solo token. La
sequenza `":` di due caratteri è un solo token, perché compare con
frequenza tale nel corpus di training da essere stata premiata dal
vocabolario.

Conseguenza: due rappresentazioni dello stesso oggetto possono avere
un numero diverso di caratteri ma un costo in token molto diverso.

Dimostrazione su un payload piccolo:

```
JSON-min: {"id":42,"name":"Adriano","active":true}
  caratteri: 40, token cl100k: 15
  pezzi: {"  id  ":  42  ,"  name  ":"  Ad  ri  ano  ","  active  ":  true  }

ADP:      id=42;name=Adriano;active=1
  caratteri: 27, token cl100k: 13
  pezzi: id  =  42  ;  name  =  Ad  ri  ano  ;  active  =  1
```

Quindici token contro tredici. La differenza si amplifica sui payload
strutturati ripetitivi, dove JSON rispetta una grammatica che premia
la robustezza ma penalizza la densità.

JSON spreca token nelle sequenze `{"`, `":`, `,"`, `":"`, `","`,
`":`, `}` che, pur essendo singoli token, sono in eccesso rispetto
all'informazione che trasportano. ADP usa pochi separatori a un
carattere (`=`, `;`, `,`), ciascuno tokenizzato singolarmente ma in
numero minore.

L'analogia con il traffico stradale chiarisce l'intuizione: pensa al
testo come al traffico e a un token come alla larghezza di corsia
occupata. JSON è un'autostrada con tante corsie larghe (tutte le
virgolette e i due punti) per ogni veicolo. ADP è una stradina urbana
in cui passa lo stesso numero di passeggeri con metà del traffico.

---

## 10. Integrazione con LLM

### 10.1 System prompt zero-shot

```python
from anthropic import Anthropic
import adp

client = Anthropic()
resp = client.messages.create(
    model="claude-opus-4-7",
    system=adp.system_prompt(),
    messages=[{"role": "user", "content": "Estrai entità dal testo..."}],
    max_tokens=512,
)
data = adp.decode(resp.content[0].text)
```

### 10.2 Validator con retry per modelli piccoli

```python
def chat_in_adp(client, messages, *, max_retries=2):
    history = list(messages)
    for _ in range(max_retries + 1):
        out = client.messages.create(
            model="claude-opus-4-7",
            system=adp.system_prompt(),
            messages=history,
            max_tokens=1024,
        ).content[0].text
        try:
            return adp.decode(out)
        except adp.ADPParseError as e:
            history += [
                {"role": "assistant", "content": out},
                {"role": "user", "content": f"Errore: {e}. Riemetti SOLO ADP valido."},
            ]
    raise RuntimeError("ADP non valido dopo retry")
```

### 10.3 Tool calling

```python
TOOL_LUT = {"tool_name": "tn", "arguments": "ar", "result": "rl"}

adp_tool_call = adp.encode({
    "tool_name": "search_db",
    "arguments": {"query": "users active=1", "limit": 10},
}, key_lut=TOOL_LUT)
# tn=search_db;ar={query="users active=1";limit=10}
```

### 10.4 Pipeline multi-agente

```python
def pipeline(input_obj):
    msg = adp.encode(input_obj, key_lut=adp.DEFAULT_AGENT_LUT)
    for role in ["planner", "executor", "reviewer"]:
        msg = call_agent(role, system=adp.system_prompt(), user=msg,
                         key_lut=adp.DEFAULT_AGENT_LUT)
        adp.decode(msg, key_lut=adp.DEFAULT_AGENT_LUT)
    return adp.decode(msg, key_lut=adp.DEFAULT_AGENT_LUT)
```

### 10.5 Compatibility con tool che richiedono JSON

```python
resp_json = client.chat.completions.create(
    model="gpt-4o",
    response_format={"type": "json_schema", "json_schema": SCHEMA},
    messages=...
).choices[0].message.content
adp_msg = adp.from_json(resp_json)
```

---

## 11. Integrazione con Claude Code

Sei approcci, dal più semplice al più potente:

1. **CLAUDE.md di progetto**: includere nel file di istruzioni del
   repository una sezione che istruisce Claude Code a usare
   `adp.encode/decode` invece di `json.dumps/loads` per le
   serializzazioni interne.
2. **Slash command custom**: creare `.claude/commands/adp.md` con un
   comando che esegue `uv run adp $ARGUMENTS` per encode, decode,
   to-md, bench.
3. **Subagent dedicato**: creare `.claude/agents/adp-agent.md` con
   istruzione di rispondere sempre in ADP. Utile per estrazioni
   ricorrenti e classificazioni.
4. **MCP server**: esporre ADP come tool nativo MCP così Claude Code
   può chiamare encode/decode/to-md/bench come funzioni di prima
   classe.
5. **Hook SessionStart**: pre-caricare il prompt ADP all'avvio della
   sessione configurando un hook in `~/.claude/settings.json`.
6. **Permission allowlist**: aggiungere `Bash(uv run adp:*)` alla
   sezione `permissions.allow` per evitare prompt di conferma.

Il MCP server tipico:

```python
from mcp.server.fastmcp import FastMCP
import adp

mcp = FastMCP("adp")

@mcp.tool()
def adp_encode(json_str: str) -> str:
    return adp.from_json(json_str)

@mcp.tool()
def adp_decode(adp_str: str) -> str:
    return adp.to_json(adp_str)

if __name__ == "__main__":
    mcp.run()
```

Registrazione in `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "adp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/agent-data-protocol",
               "python", "mcp-adp/server.py"]
    }
  }
}
```

---

## 12. Dove vive la LUT

La LUT è un artefatto stateful che vive accanto agli agenti. Quattro
modalità di deployment a costo crescente.

| Modalità | Storage | Costo runtime | Update | Tipico |
|---|---|---|---|---|
| **STATIC** | dict in source code | zero | redeploy | LUT di dominio stabile |
| **FILE** | JSON locale o NFS / S3 | una read | hot reload | due agenti su filesystem condiviso |
| **HANDSHAKE** | in-memory ciascuno | overhead primo messaggio | inline `^+id|...|^` | sessioni effimere |
| **NEGOTIATED** | Redis / SQLite / HTTP API | TTL fetch | publish | flotte multi-agente |

Demo runnable nel repository: `uv run python examples/two_agents_db.py`.

---

## 13. Immagini: tre strategie a confronto

Le immagini raster sono un caso speciale e meritano attenzione. Una
volta convertite in base64 per il canale testuale, il loro costo in
token è dominato dal contenuto del base64 stesso, non dalla sintassi
del wrapper. Misura su PNG generato (128×128 RGBA, 56428 byte raw):

| Strategia | Token cl100k | Caratteristiche |
|---|---:|---|
| JSON con `"data_b64":"..."` | 54.462 | base64 + sintassi JSON |
| ADP con `data=b!...` (inline) | 54.457 | base64 + sintassi ADP |
| RAW base64 puro | 54.425 | base64 + nessun wrapper, nessun metadato |

La differenza fra JSON, ADP e RAW è di circa lo 0,1%. Sui binari
inline il wrapper non conta. Servono **altre strategie** per ridurre
il costo in token.

### 13.1 Strategia 1 — bytes inline

Comoda per piccoli payload occasionali, sostenibile fino a qualche
kilobyte. Oltre, brucia velocemente il context window.

### 13.2 Strategia 2 — ADP-DB con riferimenti per ID

Mittente e destinatario condividono uno store persistente di blob.
La prima volta che un'immagine viene scambiata, paga il costo
"bootstrap" (la spedisce inline e la registra nel DB con un ID).
Dalla seconda volta in poi, il messaggio porta solo `^<id>`,
qualche token in totale.

Misura su tre immagini 128×128 condivise tra due agenti:

| Fase | Token cl100k | Note |
|---|---:|---|
| Bootstrap (invia 3 immagini una volta) | 163.295 | costo iniziale |
| Followup (solo riferimenti `^img_0,^img_1,^img_2`) | 20 | costo a regime |
| Inline 3 immagini ogni chiamata (senza store) | 163.293 | controllo |

Risparmio per ogni chiamata successiva al bootstrap: **163.273
token**. Break-even dopo una sola chiamata di follow-up. Su cento
chiamate il risparmio totale è di circa **16,1 milioni di token**.

### 13.3 Strategia 3 — solo metadati e URL esterno

Le immagini vivono su CDN, object storage o filesystem condiviso, e
il messaggio porta solo il riferimento URL + metadati (mime, larghezza,
altezza, dimensione, hash di verifica). L'agente apre l'immagine via
tool quando le serve.

```
task=describe_image;thumbnail={name=img.png;mime=image/png;width=128;
height=128;size_bytes=56428;url=https://cdn.example/img/abc123.png;
sha256=<hash>}
```

Costo misurato: **86 token**. Massima efficienza, ma richiede
infrastruttura esterna.

### 13.4 Riepilogo strategie

| Strategia | Token / chiamata | Setup richiesto | Caso ideale |
|---|---:|---|---|
| Inline `b!base64` | ~54.000 (PNG 128×128) | nessuno | piccole icone, payload occasionali |
| ADP-DB ref `^id` | ~25 (dopo bootstrap) | store JSON / Redis condiviso | conversazioni che riutilizzano gli stessi asset |
| URL + metadati | ~50-90 | CDN o object storage | flotte multi-agente, dataset grandi |

**Lezione**: ADP con immagini non vince sulla sintassi del wrapper.
Vince se usato come **strato di indicizzazione** (DB di riferimenti) o
come **vettore di metadati** che rimanda al contenuto reale. Il
risparmio in token è di tre o quattro ordini di grandezza nei
follow-up.

### 13.5 Implementazione di riferimento

```python
import adp
from adp import ADPStore

# Setup una volta sola, condiviso su filesystem
store = ADPStore(path="agents_shared.json")

# Agente A registra una nuova immagine
with open("photo.png", "rb") as f:
    img_id = store.put(f.read().decode("latin1"))
store.save()

# Agente B sincronizza lo store (file letto)
store_b = ADPStore(path="agents_shared.json")

# Messaggi successivi: viaggiano solo gli ID
msg = adp.encode({"task": "describe", "image_ref": img_id})
# task=describe;image_ref=0   <- 6 token
```

### 13.6 Cinque strategie inline (lossy ma drasticamente più compatte)

Dopo aver chiarito che le immagini inline come `b!base64` PNG sono
costose, il modulo `adp.image` offre cinque tecniche lossy/lossless
che riducono il token cost di 1-3 ordini di grandezza, a fronte di
perdita di qualità accettabile per la maggior parte dei task LLM.

Misure su immagine sorgente PNG 256×256 RGB (gradiente + forme):

| Strategia | Token cl100k | Risparmio vs PNG inline | Lossless | Caso ideale |
|---|---:|---:|:---:|---|
| PNG inline (baseline) | 2.842 | — | ✓ | qualità massima necessaria |
| JPEG q90 inline 256×256 | 7.959 | peggio (header) | ✗ | mai consigliato |
| WEBP q30 inline 256×256 | 1.438 | **−49%** | ✗ | full-resolution lossy |
| Thumb 128×128 JPEG q20 | 1.353 | **−52%** | ✗ | qualità decente |
| Thumb 64×64 JPEG q50 | 934 | **−67%** | ✗ | analisi LLM generica |
| Thumb 32×32 JPEG q30 | 524 | **−82%** | ✗ | essenza visiva |
| Hybrid (24×24 + pHash + caption) | 550 | **−81%** | ✗ | best balance |
| Bitmap 8×8 RGB raw | 182 | **−94%** | ✗ | colori dominanti |
| Caption testuale 25 parole | 27 | **−99%** | ✗ | vision offline disponibile |
| pHash 64-bit | 11 | **−99,6%** | ✗ | solo similarity |
| ADP-DB ref `^id` | 5 | **−99,8%** | ✓ | asset ricorrente |

API:

```python
import adp
from adp.image import compress_for_llm, decompress, hamming_distance

# Strategia thumbnail_jpeg: resize 64x64 + JPEG q50
payload = compress_for_llm(src_bytes, strategy="thumbnail_jpeg", size=64, quality=50)
adp_msg = adp.encode({"image": payload})        # ~930 token vs ~2840 PNG

# Strategia hybrid (raccomandata se LLM deve "vedere" + similarity)
payload = compress_for_llm(src_bytes, strategy="hybrid",
                            thumb_size=24, thumb_quality=30,
                            caption="red square on blue gradient")
# ~550 token, contiene thumbnail visibile + pHash + caption + metadati

# Strategia perceptual_hash (solo similarity, niente decompressione)
p1 = compress_for_llm(img_a, strategy="perceptual_hash")
p2 = compress_for_llm(img_b, strategy="perceptual_hash")
hamming = hamming_distance(p1, p2)              # bassa = simili
```

Le sei strategie sono: `passthrough`, `thumbnail_jpeg`,
`thumbnail_webp`, `perceptual_hash`, `bitmap_8x8`, `caption`,
`hybrid`. Tutte producono dict compatibili con `adp.encode()`.

### 13.7 Quale scegliere — decision tree

- Devo identificare una **persona/oggetto specifico** in alta
  risoluzione → `passthrough` o `thumbnail_jpeg` con `size=256`.
- L'LLM deve **descrivere** o **classificare** l'immagine →
  `thumbnail_jpeg` con `size=64, quality=50` (−67%).
- Devo solo **confrontare** se due immagini sono uguali →
  `perceptual_hash` (−99,6%).
- Lavoro in un dominio con **asset ricorrenti** (icone, avatar) →
  `ADPStore` + riferimenti `^id` (−99,8% sui follow-up).
- Ho già un vision-LLM **offline** che genera caption →
  strategia `caption` (−99%, vincolo: serve modello esterno).
- Voglio il **best balance** generale → `hybrid` (−81%, contiene
  thumb visibile + hash + caption + metadati in 550 token).

---

## 14. Relazione finale dei risultati

In dieci righe:

1. ADP è un linguaggio di serializzazione testuale custom per agenti
   AI, lossless, con grammatica `name=value;name=value`, bytes nativi
   (`b!base64`), tabelle inline e cells annidate.
2. Su dati strutturati ADP batte JSON-min del +25-50% in token su
   `cl100k_base`: +50% sui tabulari, +35% su URL/email, +25% su
   tabelle con cells annidate.
3. Su prosa mono-stringa ADP da solo perdeva contro flat text di
   circa il 2%. Soluzione inventata: TPD (Token-aware Phrase
   Dictionary), che impara greedy un dizionario di n-grammi e li
   sostituisce con codici ASCII a un token, testati col tokenizer.
4. ADP+TPD batte RAW flat text del +55-80% in EN/IT/ZH (per esempio
   testo italiano da 157 a 31 token, meno ottanta percento). Tutti i
   payload superano il target 30-60%.
5. ADP+LUT (sigle per chiavi ricorrenti) aggiunge ulteriori +7-8% sui
   messaggi task-agente quando le chiavi sono nel dizionario
   pre-condiviso `DEFAULT_AGENT_LUT`.
6. La LUT/DB vive in quattro modalità implementate: STATIC,
   FILE-JSON, HANDSHAKE con definizioni inline, NEGOTIATED via
   registry centralizzato.
7. Lossless verificato: cento test pytest verdi (round-trip su
   primitivi, multilinea, Unicode, emoji, CJK, bytes, tabelle
   nested, LUT, DB, TPD).
8. Convertitori inclusi: ADP↔JSON canonico bidirezionale lossless
   (bytes via tag `_adp_bytes`), ADP→Markdown one-way leggibile.
9. Stack: Python 3.11+, parser recursive-descent zero-dipendenze,
   CLI Click, benchmark con `tiktoken`, `pyyaml`, `tomli-w`,
   `msgpack`. Demo runnable in `examples/two_agents_db.py`.
10. Limiti onesti: TPD encode costa tre-ventisette millisecondi
    (greedy learner) la prima volta, poi microsecondi con LUT
    cached; vantaggio TPD ammortizzato dal secondo messaggio in poi;
    la LUT è un artefatto stateful da gestire via filesystem,
    handshake o registry.

---

## Appendice: riferimenti rapidi

- Repository: `/home/adriano/Documenti/Git_XYZ/agent-data-protocol`
- Spec design: `docs/superpowers/specs/2026-05-22-adp-design.md`
- Report benchmark dettagliato: `benchmarks/results.md` (circa
  centodieci kilobyte, comprende esempi codificati in tutti i
  formati per ogni payload e timing encode/decode).
- Demo agenti: `examples/two_agents_db.py`
- Quickstart: `examples/quickstart.py`
- Test suite: 100 test in `tests/` (round-trip, converters,
  v0.2 features, LUT, TPD, DB).

Comandi essenziali:

```bash
uv sync --all-extras
uv run pytest                              # 100 test
uv run python -m benchmarks.compare_formats # rigenera benchmark
uv run adp encode < tests/fixtures/example.json
uv run adp bench < tests/fixtures/example.json
uv run adp prompt --few-shot                # system prompt per LLM
uv run python examples/two_agents_db.py     # demo LUT condivisa
```
