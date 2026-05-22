# ADP — Adriano Dal Pastro format — Design Document

> Data: 2026-05-22 (v0.1: stessa data; v0.2: stessa data, aggressivo refresh)
> Stato: spec v0.2
> Autore: Adriano Dal Pastro + Claude

## 1. Obiettivo

Definire un formato testuale di scambio messaggi tra agenti AI che sia:

1. **Token-efficient aggressivo**: rispetto a JSON-min su `cl100k_base`,
   risparmio reale misurato (`benchmarks/results.md`):
   - **+40-50%** su dati tabulari omogenei,
   - **+25-35%** su tabelle con cells annidate e su payload URL/email/path-heavy,
   - **+10-13%** su strutture annidate generiche,
   - **+3-13%** su testi brevi, lunghi e caratteri speciali (mai negativo).
2. **Lossless**: round-trip perfetto `decode(encode(x)) == x` su primitivi,
   stringhe (anche con escape, Unicode, emoji, multilinea letterale),
   liste, mappe annidate, tabelle, **bytes**.
3. **Annidamento illimitato**: liste/mappe in qualunque combinazione, e
   tabelle con cells che possono contenere liste o mappe (no sub-table
   dentro cell per evitare ambiguità di parsing).
4. **Bytes nativi**: il formato accetta `bytes` direttamente, codificati
   come `b!<base64>` — gli altri formati testuali (JSON, YAML, TOML)
   richiedono codifiche custom o falliscono nettamente.
5. **Salvabile / ricaricabile**: testo UTF-8 puro, persistibile su file e
   ricaricabile senza stato esterno.
6. **Convertitori**: GLA ↔ **JSON canonico** (bidirezionale, lossless,
   bytes come `{"_adp_bytes": "<base64>"}`); ADP → **Markdown** (one-way
   per umani).
7. **Universale**: copre il superset dei dati che un agente AI scambia
   tipicamente.

Il formato **non è pensato per essere letto a colpo d'occhio da un umano**:
a quello pensano i convertitori. La leggibilità diretta è stata sacrificata
per massimizzare il risparmio token.

## 2. Cambiamenti rispetto a v0.1

v0.2 è un **breaking change** intenzionale:

| Aspetto | v0.1 | v0.2 |
|---|---|---|
| Top-level | `&name:value&&name:value&` | `name=value;name=value` |
| Bare string char set | `[A-Za-z_][A-Za-z0-9_.-]*` | `[A-Za-z_][A-Za-z0-9_.\-/@+*?<>%():$]*` |
| Bytes | non supportati | `b!<base64>` |
| Table cells | solo scalari | scalari + list + map + bytes |
| Nome formato | GLA | **ADP** |

## 3. Grammatica (EBNF)

```
document    := pair (';' pair)* ';'?
pair        := IDENT '=' value
value       := primitive | string | bytes | list | map | table
primitive   := integer | float | boolean | null
integer     := -? DIGIT+
float       := -? DIGIT+ '.' DIGIT+ (('e' | 'E') ('+' | '-')? DIGIT+)?
boolean     := '1' | '0'
null        := '~'
string      := bare_string | quoted_string
bare_string := [A-Za-z_] [A-Za-z0-9_.\-/@+*?<>%():$]*
quoted_string := '"' (ESC | NON_QUOTE)* '"'
ESC         := '\"' | '\\'
bytes       := 'b!' BASE64_CHAR*
list        := '[' (value (',' value)*)? ']'
map         := '{' (entry (';' entry)*)? '}'
entry       := IDENT '=' value
table       := '#' header ('|' row)+
header      := IDENT (',' IDENT)*
row         := value (',' value)*

IDENT       := [A-Za-z_][A-Za-z0-9_-]*
DIGIT       := [0-9]
BASE64_CHAR := [A-Za-z0-9+/=]
```

Note semantiche:

- **Boolean**: `1` = true, `0` = false. Per int 0/1 si usa `0i` / `1i`.
- **Null**: `~`.
- **Stringhe nude**: ampliate v0.2. Esempi nudi: `Adriano`, `kg`,
  `ops@acme.example`, `https://acme.example/api/v2`, `src/adp/parser.py`,
  `+39`, `(2+3)`.
- **Stringhe numeriche**: una stringa che matcha il pattern numerico
  (es. `"42"`) deve essere quoted per non collidere con il tipo.
- **Stringhe quoted**: ammettono newline letterali. Escape solo per `"` e
  `\`.
- **Bytes**: prefisso `b!` seguito da base64 standard (alfabeto
  `A-Za-z0-9+/=`). Lossless garantito.
- **Tabelle**: prima riga è header. Cells possono essere scalari,
  stringhe, liste, mappe, bytes. **NON** sub-table (per evitare ambiguità
  fra `|` di row separator e `|` interno).
- **Top-level**: equivalente semanticamente a una mappa senza graffe.

## 4. Esempi

### 4.1 Base

```
user={id=42;name=Adriano;active=1};tags=[admin,root,"user con spazio"]
```

### 4.2 Testo multilinea

```
report="Riga 1
Riga 2 con \"virgolette\" e \\backslash intatti
Riga 3"
```

### 4.3 Tabella semplice

```
metrics=#id,value,unit|1i,42.0,kg|2,3.14,m|3,7.5,kg
```

### 4.4 Tabella con cells annidate

```
users=#id,name,roles,perms|1i,alice,[admin,ops],{read=1;write=1}|2,bob,[dev],{read=1;write=0}
```

### 4.5 URL / email / path bare

```
contact={email=ops@acme.example;url=https://acme.example/api/v2;file=src/adp/parser.py}
```

### 4.6 Bytes

```
thumbnail={name=thumb.png;mime=image/png;data=b!iVBORw0KGgoAAAANSUhEUg==}
```

## 5. Convertitori

### 5.1 ADP ↔ JSON canonico

- Round-trip totale.
- `bytes` → `{"_adp_bytes": "<base64>"}` (tag riservato).
- `null` JSON ↔ `~` ADP.
- `true`/`false` JSON ↔ `1`/`0` ADP (con `0i`/`1i` quando origine è int).

### 5.2 ADP → Markdown

Output strutturato per umani, **one-way** (Markdown è meno strutturato).
Tabelle Markdown native; bytes mostrati come `\`<bytes N B: <base64>>\``.

## 6. Architettura libreria Python

```
src/adp/
├── __init__.py        API pubblica
├── parser.py          ADP → Python (recursive-descent, zero deps)
├── serializer.py      Python → ADP
├── converters.py      JSON / Markdown (con bytes tag)
├── prompt.py          system prompt + 8 few-shot pairs
└── cli.py             CLI Click: adp encode/decode/to-md/bench/prompt/validate
```

API pubblica:

```python
import adp

s = adp.encode(obj)              # Python obj -> ADP string
o = adp.decode(s)                # ADP string -> Python obj
adp.to_json(s)                   # ADP -> JSON canonico
adp.from_json(json_str)          # JSON -> ADP
adp.to_markdown(s)               # ADP -> Markdown (one-way)
adp.system_prompt()              # prompt LLM
adp.few_shot_examples()          # 8 esempi (obj, ADP) per few-shot
adp.few_shot_block()             # blocco testuale pronto per prompt
```

## 7. Garanzia lossless

Test obbligatori (`tests/test_roundtrip.py` + `tests/test_v02_features.py`):

```python
assert decode(encode(obj)) == obj
assert encode(decode(encode(obj))) == encode(obj)   # determinismo
assert from_json(to_json(s)) == s   # via JSON canonico
```

Coverage: 80 test passanti su primitivi, multilinea, escape, Unicode,
emoji, tabelle omogenee/eterogenee, **tabelle con cells nested**,
**bytes empty/bin/in-list/in-table**, **URL/email/path bare**, stringhe
numeriche, errori di parser, base64 invalido.

## 8. Stack tecnico

- Python 3.11+
- Parser scritto a mano (recursive-descent), zero dipendenze runtime per
  la core lib (oltre stdlib).
- `click` per CLI.
- `tiktoken`, `pyyaml`, `tomli-w`, `msgpack` (dev/bench only).
- `pytest` per test.
- `uv` per gestione dipendenze.

## 9. Risk register

| Rischio | Impatto | Mitigazione |
|---|---|---|
| LLM genera output non conforme | Alto | system prompt rigoroso + few-shot + validator + retry |
| Bool/int 0/1 confusione | Medio | suffisso `i` esplicito |
| Newline dentro stringhe rompono parser | Medio | test multilinea esplicito, parser permissivo |
| Bytes confusi con bare string `b...` | Basso | prefisso univoco `b!` (l'`!` non è valid in bare) |
| Cell di tabella con `,` o `|` non quotata | Medio | encoder forza quoting o usa wrapper `[]`/`{}` |
| Sub-table dentro cell | Medio | vietata da encoder, parser non la cerca dentro cell |

## 10. Roadmap

- v0.3: envelope opzionale (`from`, `to`, `id`, `intent`, `reply_to`).
- v0.4: schema/contract opzionale, codegen Pydantic.
- v0.5: impl TS di riferimento.
