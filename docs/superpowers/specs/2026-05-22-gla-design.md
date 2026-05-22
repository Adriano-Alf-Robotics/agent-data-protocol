# GLA — Goal Language Agents — Design Document

> Data: 2026-05-22
> Stato: spec v0.1 — implementazione iniziale
> Autore: Adriano + Claude

## 1. Obiettivo

Definire un formato testuale di scambio messaggi tra agenti AI che sia:

1. **Token-efficient**: economico rispetto a JSON sui tokenizer LLM moderni (cl100k_base, o200k_base). Risparmio reale misurato (vedi `benchmarks/results.md`): **~40-50% su dati tabulari omogenei**, ~10-15% su strutture annidate, 0-6% su testi liberi.
2. **Lossless**: round-trip perfetto `encode(decode(x)) == x` su tutti i payload supportati. Nessuna perdita di precisione, nessuna trasformazione semantica.
3. **Salvabile / ricaricabile**: il formato è puro testo UTF-8, persistibile su file e ricaricabile senza stato esterno.
4. **Convertibile**: due convertitori bidirezionali deterministici:
   - GLA ↔ **JSON canonico** (per macchine senza AI)
   - GLA → **Markdown leggibile** (per umani)
5. **Universale**: supporta primitivi, container annidati, testo libero multilinea, tabelle.

Il formato non deve essere leggibile a colpo d'occhio da un umano — è il convertitore che traduce.

## 2. Scope

In scope:
- Specifica del linguaggio (grammatica EBNF).
- Libreria Python `gla` con encoder, decoder, convertitori.
- CLI per uso da shell.
- Helper per integrazione in system prompt LLM (template, few-shot, validator).
- Benchmark token vs JSON.

Fuori scope (v0.1):
- Trasporto / runtime / orchestrazione multi-agente.
- Persistenza di stato conversazionale di lungo termine.
- Compressione lossy.
- Supporto a binari (immagini, file): solo via base64 in stringhe.

## 3. Grammatica (EBNF)

```
document    := record+
record      := "&" name ":" value "&"
name        := IDENT
value       := primitive | string | list | map | table
primitive   := integer | float | boolean | null
integer     := "-"? DIGIT+
float       := "-"? DIGIT+ "." DIGIT+ (("e"|"E") ("+"|"-")? DIGIT+)?
boolean     := "1" | "0"
null        := "~"
string      := bare_string | quoted_string
bare_string := [A-Za-z_][A-Za-z0-9_.\-]*
quoted_string := "\"" ( ESC | NORMAL_CHAR | NEWLINE )* "\""
ESC         := "\\\"" | "\\\\"
list        := "[" ( value ( "," value )* )? "]"
map         := "{" ( entry ( ";" entry )* )? "}"
entry       := name "=" value
table       := "#" header ( "|" row )+
header      := name ( "," name )*
row         := value ( "," value )*

IDENT       := [A-Za-z_][A-Za-z0-9_-]*
DIGIT       := [0-9]
```

Note semantiche:

- **Boolean**: `1` = true, `0` = false. Gli integer letterali `1` e `0` come valori scalari sono distinti dai boolean solo se chi codifica li tipa come int; in pratica il parser GLA ritorna sempre `True`/`False` quando incontra `1` o `0` come scalari standalone, mentre il caller può forzare interpretazione int via API (`encode(value, ints={'campo'})`).
  Per evitare ambiguità, **gli integer 0 e 1 sono codificati come `0` / `1`** ma marcati come `int` se chiamati via API tipizzata; il default parser→Python è: `1` → `True`, `0` → `False`, qualsiasi altro intero → `int`. Vedi sezione 4.4 per la disambiguazione.
- **Null**: rappresentato dal carattere `~`.
- **Stringhe nude**: solo caratteri sicuri (alfanumerici, `_`, `.`, `-`). Tutto il resto richiede quoting.
- **Stringhe quoted**: ammettono newline letterali, escape solo per `"` (→ `\"`) e `\` (→ `\\`).
- **Liste**: omogenee o eterogenee, ammesse vuote.
- **Mappe**: sequenza ordinata di `name=value` separate da `;`. La codifica preserva l'ordine.
- **Tabelle**: prima riga è header. Tutte le righe devono avere lo stesso numero di colonne dell'header. Equivalente lossless a una lista di mappe omogenee.
- **Record top-level**: ogni `&...&` è un record. Un documento è una sequenza di record. Più record sono equivalenti a un singolo record con valore mappa, ma più compatti se i nomi top-level sono identificatori brevi.

## 4. Esempi

### 4.1 Esempio base

```
&user:{id=42;name=Adriano;active=1}&
&tags:[admin,root,"user con spazio"]&
```

JSON equivalente:

```json
{
  "user": {"id": 42, "name": "Adriano", "active": true},
  "tags": ["admin", "root", "user con spazio"]
}
```

### 4.2 Testo multilinea

```
&report:"Riga 1
Riga 2 con \"virgolette\" e \\backslash intatti
Riga 3"&
```

Le newline sono letterali. Nessun escape `\n`. Lossless.

### 4.3 Tabella

```
&metrics:#id,value,unit|1,42.0,kg|2,3.14,m|3,7.5,kg&
```

Equivalente a:

```json
{"metrics": [
  {"id": 1, "value": 42.0, "unit": "kg"},
  {"id": 2, "value": 3.14, "unit": "m"},
  {"id": 3, "value": 7.5, "unit": "kg"}
]}
```

Risparmio token significativo: header citato una sola volta.

### 4.4 Disambiguazione boolean vs int

In API:

```python
import gla
gla.encode({"flag": True, "count": 1})
# &flag:1&&count:1&    <- ambiguità!
```

Soluzione: il decoder di default usa **type hint a runtime**:

- Scalari `1` / `0` decodificano a `bool` per default.
- Per forzare a `int`, l'encoder usa un suffisso typecode: `1i` per int, `1` per bool. (Lossless, +1 token per int 0/1).

```python
gla.encode({"flag": True, "count": 1})
# &flag:1&&count:1i&
gla.decode("&flag:1&&count:1i&")
# {"flag": True, "count": 1}
```

Altri integer (`2`, `42`, `-7`) non hanno bisogno di suffisso: già non collidono con bool.

## 5. Convertitori

### 5.1 GLA ↔ JSON canonico

- Round-trip totale per qualsiasi struttura JSON-compatibile.
- JSON output: ordinato per chiavi alfabeticamente? No — preserva l'ordine di inserimento (Python dict insertion-ordered).
- `null` JSON ↔ `~` GLA.
- `true`/`false` JSON ↔ `1`/`0` GLA (con `i`-suffix se l'origine era int).
- Float NaN/Infinity non supportati (come JSON standard).

### 5.2 GLA → Markdown

Output strutturato, leggibile a umani:

```markdown
## user

- **id**: 42
- **name**: Adriano
- **active**: true

## report

```
Riga 1
Riga 2 con "virgolette" e \backslash intatti
```

## metrics

| id | value | unit |
|----|-------|------|
| 1  | 42.0  | kg   |
| 2  | 3.14  | m    |
```

La conversione GLA → Markdown è **one-way** (Markdown è meno strutturato; non c'è un parser Markdown → GLA garantito).

## 6. Architettura libreria Python

```
src/gla/
├── __init__.py        # API pubblica: encode, decode, to_json, from_json, to_markdown
├── tokens.py          # Token types per il lexer
├── lexer.py           # Tokenizer minimale (no lark per ridurre dipendenze)
├── parser.py          # Parser ricorsivo-discendente
├── serializer.py      # Encode Python → GLA
├── converters.py      # JSON / Markdown
├── prompt.py          # System prompt template + few-shot per LLM
└── cli.py             # Click CLI: gla encode/decode/to-json/to-md
```

### API pubblica

```python
import gla

# Encode Python object → GLA string
s = gla.encode({"user": {"id": 42, "name": "Adriano"}})

# Decode GLA string → Python object
obj = gla.decode(s)

# JSON convertitori
gla.to_json(s)            # GLA → JSON string
gla.from_json(json_str)   # JSON → GLA string

# Markdown (one-way, human-readable)
gla.to_markdown(s)

# Prompt helpers
gla.system_prompt()       # Returns ready-to-paste system prompt for LLM
gla.few_shot_examples()   # Returns list of (input_obj, gla_output) tuples
```

### CLI

```bash
gla encode < input.json          # JSON stdin → GLA stdout
gla decode < input.gla           # GLA stdin → JSON stdout (alias di to-json)
gla to-md < input.gla            # GLA stdin → Markdown stdout
gla validate < input.gla         # Verifica grammatica, exit code 0/1
gla bench < input.json           # Mostra confronto token GLA vs JSON
```

## 7. Garanzia di lossless round-trip

Test obbligatori (test_roundtrip.py):

Per ogni `obj` nei fixture set:

```python
assert decode(encode(obj)) == obj
assert from_json(to_json(encode(obj))) == encode(obj)   # GLA→JSON→GLA
```

Fixture include: scalari di ogni tipo, mappe annidate, liste eterogenee, stringhe con caratteri Unicode/escape/newline/emoji, tabelle 0×0, 1×N, N×1, N×M, payload tipici di agenti (task assignment, report, query, response).

## 8. Stack tecnico

- Python 3.11+
- `lark` rimosso → parser scritto a mano (ricorsivo-discendente) → zero dipendenze runtime per la core lib.
- `click` per CLI.
- `tiktoken` (dev only) per benchmark.
- `pytest` per test.
- `uv` per gestione dipendenze.

## 9. Roadmap post-v0.1

- v0.2: envelope opzionale (`from`, `to`, `id`, `intent`).
- v0.3: schema/contract per validare struttura attesa.
- v0.4: convertitori per altri formati (YAML, TOML).
- v0.5: implementazione TypeScript della spec.

## 10. Risk register

| Rischio | Impatto | Mitigazione |
|---|---|---|
| LLM genera output non conforme | Alto | System prompt rigoroso + few-shot + validator + retry |
| Bool/int 0/1 confusione | Medio | Suffisso `i` esplicito |
| Newline dentro stringhe rompono parser | Medio | Test fixtures con newline, parser tolerante |
| Tabelle con `,` nei valori | Medio | Quote string nelle celle |
| Adozione bassa vs JSON | Basso | Spec aperta + convertitore JSON → drop-in |
