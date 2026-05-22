# ADP — Analisi Comparativa vs Formati Esistenti

Repeat per misura tempo: **200** esecuzioni (mediana).
Token count via `tiktoken`: `cl100k_base` (GPT-4 / Claude 3.x) e `o200k_base` (GPT-4o / Opus 4.x).
Tempi in µs (microsecondi) — encoding e decoding di un singolo payload Python in-memory.

## Indice
- [short_string_en](#short-string-en)
- [short_string_it](#short-string-it)
- [long_text_en](#long-text-en)
- [long_text_it](#long-text-it)
- [special_chars_en](#special-chars-en)
- [special_chars_it](#special-chars-it)
- [tabular_en](#tabular-en)
- [tabular_it](#tabular-it)
- [database_en](#database-en)
- [database_it](#database-it)
- [agent_task_en](#agent-task-en)
- [agent_task_it](#agent-task-it)
- [contacts_en](#contacts-en)
- [nested_table_en](#nested-table-en)
- [binary_en](#binary-en)

## Sintesi globale — risparmio token ADP vs JSON-min

| Payload | JSON-min tok | ADP tok | ADP+LUT tok | Δ ADP cl100k | Δ ADP+LUT cl100k |
|---------|-------------:|--------:|------------:|-------------:|-----------------:|
| short_string_en | 15 | 13 | 13 | +13.3% | +13.3% |
| short_string_it | 18 | 16 | 16 | +11.1% | +11.1% |
| long_text_en | 115 | 109 | 109 | +5.2% | +5.2% |
| long_text_it | 176 | 170 | 170 | +3.4% | +3.4% |
| special_chars_en | 92 | 89 | 89 | +3.3% | +3.3% |
| special_chars_it | 134 | 131 | 131 | +2.2% | +2.2% |
| tabular_en | 241 | 145 | 147 | +39.8% | +39.0% |
| tabular_it | 333 | 164 | 164 | +50.8% | +50.8% |
| database_en | 150 | 134 | 134 | +10.7% | +10.7% |
| database_it | 180 | 157 | 157 | +12.8% | +12.8% |
| agent_task_en | 88 | 83 | 76 | +5.7% | +13.6% |
| agent_task_it | 118 | 113 | 110 | +4.2% | +6.8% |
| contacts_en | 145 | 94 | 96 | +35.2% | +33.8% |
| nested_table_en | 100 | 75 | 76 | +25.0% | +24.0% |

## short_string_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 46 | 13 | 13 | +13.3% | 2.1µs | 4.8µs | ✓ |  |
| ADP+LUT | 42 | 13 | 13 | +13.3% | 19.0µs | 23.2µs | ✓ |  |
| JSON-min | 54 | 15 | 15 | +0.0% | 1.8µs | 956ns | ✓ |  |
| JSON-pretty | 63 | 21 | 21 | -40.0% | 3.0µs | 1.1µs | ✓ |  |
| YAML | 47 | 13 | 13 | +13.3% | 59.2µs | 96.3µs | ✓ |  |
| TOML | 53 | 15 | 15 | +0.0% | 4.1µs | 6.8µs | ✓ |  |
| MsgPack-b64 | 64 | 47 | 42 | -213.3% | 701ns | 650ns | ✓ |  |
| XML | 73 | 22 | 22 | -46.7% | 5.6µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
intent=ack;msg="Task received. Working on it."
```

#### ADP+LUT

```text
it=ack;msg="Task received. Working on it."
```

#### JSON-min

```json
{"intent":"ack","msg":"Task received. Working on it."}
```

#### JSON-pretty

```json
{
  "intent": "ack",
  "msg": "Task received. Working on it."
}
```

#### YAML

```yaml
intent: ack
msg: Task received. Working on it.
```

#### TOML

```toml
intent = "ack"
msg = "Task received. Working on it."
```

#### MsgPack-b64

```text
gqZpbnRlbnSjYWNro21zZ71UYXNrIHJlY2VpdmVkLiBXb3JraW5nIG9uIGl0Lg==
```

#### XML

```xml
<root><intent>ack</intent><msg>Task received. Working on it.</msg></root>
```

---

## short_string_it

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 49 | 16 | 15 | +11.1% | 1.9µs | 4.6µs | ✓ |  |
| ADP+LUT | 45 | 16 | 15 | +11.1% | 17.8µs | 24.6µs | ✓ |  |
| JSON-min | 57 | 18 | 17 | +0.0% | 2.0µs | 1.0µs | ✓ |  |
| JSON-pretty | 66 | 24 | 23 | -33.3% | 3.2µs | 1.1µs | ✓ |  |
| YAML | 50 | 16 | 15 | +11.1% | 67.3µs | 101.6µs | ✓ |  |
| TOML | 56 | 18 | 17 | +0.0% | 4.5µs | 7.2µs | ✓ |  |
| MsgPack-b64 | 68 | 50 | 47 | -177.8% | 765ns | 698ns | ✓ |  |
| XML | 76 | 25 | 24 | -38.9% | 6.0µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
intent=ack;msg="Compito ricevuto. Sto lavorando."
```

#### ADP+LUT

```text
it=ack;msg="Compito ricevuto. Sto lavorando."
```

#### JSON-min

```json
{"intent":"ack","msg":"Compito ricevuto. Sto lavorando."}
```

#### JSON-pretty

```json
{
  "intent": "ack",
  "msg": "Compito ricevuto. Sto lavorando."
}
```

#### YAML

```yaml
intent: ack
msg: Compito ricevuto. Sto lavorando.
```

#### TOML

```toml
intent = "ack"
msg = "Compito ricevuto. Sto lavorando."
```

#### MsgPack-b64

```text
gqZpbnRlbnSjYWNro21zZ9kgQ29tcGl0byByaWNldnV0by4gU3RvIGxhdm9yYW5kby4=
```

#### XML

```xml
<root><intent>ack</intent><msg>Compito ricevuto. Sto lavorando.</msg></root>
```

---

## long_text_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 457 | 109 | 107 | +5.2% | 2.4µs | 28.2µs | ✓ |  |
| ADP+LUT | 457 | 109 | 107 | +5.2% | 19.8µs | 49.5µs | ✓ |  |
| JSON-min | 467 | 115 | 113 | +0.0% | 2.8µs | 1.5µs | ✓ |  |
| JSON-pretty | 476 | 121 | 119 | -5.2% | 4.1µs | 1.4µs | ✓ |  |
| YAML | 470 | 115 | 113 | +0.0% | 227.4µs | 252.9µs | ✓ |  |
| TOML | 466 | 115 | 113 | +0.0% | 19.1µs | 26.8µs | ✓ |  |
| MsgPack-b64 | 612 | 423 | 399 | -267.8% | 1.2µs | 1.1µs | ✓ |  |
| XML | 482 | 118 | 116 | -2.6% | 5.6µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
title="Quarterly Summary";body="Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region. Operational expenses remained flat, expanding margins.

Customer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.

Outlook: cautious optimism. Macro headwinds persist but pipeline coverage for the next quarter stands at 3.4x, above the 3.0x threshold."
```

#### ADP+LUT

```text
title="Quarterly Summary";body="Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region. Operational expenses remained flat, expanding margins.

Customer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.

Outlook: cautious optimism. Macro headwinds persist but pipeline coverage for the next quarter stands at 3.4x, above the 3.0x threshold."
```

#### JSON-min

```json
{"title":"Quarterly Summary","body":"Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region. Operational expenses remained flat, expanding margins.\n\nCustomer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.\n\nOutlook: cautious optimism. Macro headwinds persist but pipeline coverage for the next quarter stands at 3.4x, above the 3.0x threshold."}
```

#### JSON-pretty

```json
{
  "title": "Quarterly Summary",
  "body": "Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region. Operational expenses remained flat, expanding margins.\n\nCustomer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.\n\nOutlook: cautious optimism. Macro headwinds persist but pipeline coverage for the next quarter stands at 3.4x, above the 3.0x threshold."
}
```

#### YAML

```yaml
title: Quarterly Summary
body: 'Revenue grew 12% year over year, driven primarily by enterprise sales in the
  EMEA region. Operational expenses remained flat, expanding margins.


  Customer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added:
  47. Top-three industries by ARR: SaaS, Fintech, Healthcare.


  Outlook: cautious optimism. Macro headwinds persist but pipeline coverage for the
  next quarter stands at 3.4x, above the 3.0x threshold.'
```

#### TOML

```toml
title = "Quarterly Summary"
body = "Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region. Operational expenses remained flat, expanding margins.\n\nCustomer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.\n\nOutlook: cautious optimism. Macro headwinds persist but pipeline coverage for the next quarter stands at 3.4x, above the 3.0x threshold."
```

#### MsgPack-b64

```text
gqV0aXRsZbFRdWFydGVybHkgU3VtbWFyeaRib2R52gGoUmV2ZW51ZSBncmV3IDEyJSB5ZWFyIG92ZXIgeWVhciwgZHJpdmVuIHByaW1hcmlseSBieSBlbnRlcnByaXNlIHNhbGVzIGluIHRoZSBFTUVBIHJlZ2lvbi4gT3BlcmF0aW9uYWwgZXhwZW5zZXMgcmVtYWluZWQgZmxhdCwgZXhwYW5kaW5nIG1hcmdpbnMuCgpDdXN0b21lciBjaHVybiBkcm9wcGVkIHRvIDIuMSUsIHRoZSBsb3dlc3QgaW4gc2l4IHF1YXJ0ZXJzLiBOZXQtbmV3IGxvZ29zIGFkZGVkOiA0Ny4gVG9wLXRocmVlIGluZHVzdHJpZXMgYnkgQVJSOiBTYWFTLCBGaW50ZWNoLCBIZWFsdGhjYXJlLgoKT3V0bG9vazogY2F1dGlvdXMgb3B0aW1pc20uIE1hY3JvIGhlYWR3aW5kcyBwZXJzaXN0IGJ1dCBwaXBlbGluZSBjb3ZlcmFnZSBmb3IgdGhlIG5leHQgcXVhcnRlciBzdGFuZHMgYXQgMy40eCwgYWJvdmUgdGhlIDMuMHggdGhyZXNob2xkLg==
```

#### XML

```xml
<root><title>Quarterly Summary</title><body>Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region. Operational expenses remained flat, expanding margins.

Customer churn dropped to 2.1%, the lowest in six quarters. Net-new logos added: 47. Top-three industries by ARR: SaaS, Fintech, Healthcare.

Outlook: cautious optimism. Macro headwinds persist but pipeline coverage for the next quarter stands at 3.4x, above the 3.0x threshold.</body></root>
```

---

## long_text_it

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 542 | 170 | 155 | +3.4% | 2.4µs | 34.7µs | ✓ |  |
| ADP+LUT | 542 | 170 | 155 | +3.4% | 21.7µs | 55.4µs | ✓ |  |
| JSON-min | 552 | 176 | 161 | +0.0% | 3.0µs | 1.6µs | ✓ |  |
| JSON-pretty | 561 | 182 | 167 | -3.4% | 4.2µs | 1.6µs | ✓ |  |
| YAML | 558 | 180 | 166 | -2.3% | 261.7µs | 283.3µs | ✓ |  |
| TOML | 551 | 176 | 161 | +0.0% | 23.2µs | 32.4µs | ✓ |  |
| MsgPack-b64 | 724 | 513 | 485 | -191.5% | 1.4µs | 1.3µs | ✓ |  |
| XML | 569 | 180 | 166 | -2.3% | 6.0µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
titolo="Sintesi Trimestrale";corpo="Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando i margini.

L'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.

Prospettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x."
```

#### ADP+LUT

```text
titolo="Sintesi Trimestrale";corpo="Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando i margini.

L'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.

Prospettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x."
```

#### JSON-min

```json
{"titolo":"Sintesi Trimestrale","corpo":"Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando i margini.\n\nL'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.\n\nProspettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x."}
```

#### JSON-pretty

```json
{
  "titolo": "Sintesi Trimestrale",
  "corpo": "Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando i margini.\n\nL'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.\n\nProspettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x."
}
```

#### YAML

```yaml
titolo: Sintesi Trimestrale
corpo: 'Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle
  vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando
  i margini.


  L''abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri.
  Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.


  Prospettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura
  di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x.'
```

#### TOML

```toml
titolo = "Sintesi Trimestrale"
corpo = "Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando i margini.\n\nL'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.\n\nProspettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x."
```

#### MsgPack-b64

```text
gqZ0aXRvbG+zU2ludGVzaSBUcmltZXN0cmFsZaVjb3Jwb9oB+UlsIGZhdHR1cmF0byDDqCBjcmVzY2l1dG8gZGVsIDEyJSBhbm5vIHN1IGFubm8sIHRyYWluYXRvIHByaW5jaXBhbG1lbnRlIGRhbGxlIHZlbmRpdGUgZW50ZXJwcmlzZSBpbiBhcmVhIEVNRUEuIEkgY29zdGkgb3BlcmF0aXZpIHNvbm8gcmltYXN0aSBzdGFiaWxpLCBhbXBsaWFuZG8gaSBtYXJnaW5pLgoKTCdhYmJhbmRvbm8gY2xpZW50aSDDqCBzY2VzbyBhbCAyLDElLCBpbCB2YWxvcmUgcGnDuSBiYXNzbyBkZWdsaSB1bHRpbWkgc2VpIHRyaW1lc3RyaS4gTnVvdmkgY2xpZW50aSBhY3F1aXNpdGk6IDQ3LiBUb3AgdHJlIHNldHRvcmkgcGVyIEFSUjogU2FhUywgRmludGVjaCwgU2FuaXTDoC4KClByb3NwZXR0aXZlOiBvdHRpbWlzbW8gY2F1dG8uIExlIGRpZmZpY29sdMOgIG1hY3JvZWNvbm9taWNoZSBwZXJzaXN0b25vIG1hIGxhIGNvcGVydHVyYSBkaSBwaXBlbGluZSBwZXIgaWwgcHJvc3NpbW8gdHJpbWVzdHJlIMOoIHBhcmkgYSAzLDR4LCBzb3ByYSBsYSBzb2dsaWEgZGkgMywweC4=
```

#### XML

```xml
<root><titolo>Sintesi Trimestrale</titolo><corpo>Il fatturato è cresciuto del 12% anno su anno, trainato principalmente dalle vendite enterprise in area EMEA. I costi operativi sono rimasti stabili, ampliando i margini.

L'abbandono clienti è sceso al 2,1%, il valore più basso degli ultimi sei trimestri. Nuovi clienti acquisiti: 47. Top tre settori per ARR: SaaS, Fintech, Sanità.

Prospettive: ottimismo cauto. Le difficoltà macroeconomiche persistono ma la copertura di pipeline per il prossimo trimestre è pari a 3,4x, sopra la soglia di 3,0x.</corpo></root>
```

---

## special_chars_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 235 | 89 | 86 | +3.3% | 5.6µs | 17.3µs | ✓ |  |
| ADP+LUT | 235 | 89 | 86 | +3.3% | 26.1µs | 40.0µs | ✓ |  |
| JSON-min | 249 | 92 | 89 | +0.0% | 2.9µs | 2.1µs | ✓ |  |
| JSON-pretty | 270 | 107 | 104 | -16.3% | 4.5µs | 2.1µs | ✓ |  |
| YAML | 230 | 90 | 88 | +2.2% | 170.6µs | 243.9µs | ✓ |  |
| TOML | 248 | 95 | 92 | -3.3% | 13.7µs | 23.1µs | ✓ |  |
| MsgPack-b64 | 296 | 212 | 198 | -130.4% | 1.1µs | 1.3µs | ✓ |  |
| XML | 292 | 103 | 101 | -12.0% | 9.4µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
code_snippet="function f(x) {
  return x[\"a\\b\\\"c\"] + 1;
}";emoji="Done ✅ 🎉 — 100% reliable 🚀";math="α + β = γ; ∑ᵢ xᵢ → ∞";quoted_quotes="She said \"hi\" and left.";backslash_path="C:\\Users\\admin\\file.txt"
```

#### ADP+LUT

```text
code_snippet="function f(x) {
  return x[\"a\\b\\\"c\"] + 1;
}";emoji="Done ✅ 🎉 — 100% reliable 🚀";math="α + β = γ; ∑ᵢ xᵢ → ∞";quoted_quotes="She said \"hi\" and left.";backslash_path="C:\\Users\\admin\\file.txt"
```

#### JSON-min

```json
{"code_snippet":"function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}","emoji":"Done ✅ 🎉 — 100% reliable 🚀","math":"α + β = γ; ∑ᵢ xᵢ → ∞","quoted_quotes":"She said \"hi\" and left.","backslash_path":"C:\\Users\\admin\\file.txt"}
```

#### JSON-pretty

```json
{
  "code_snippet": "function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}",
  "emoji": "Done ✅ 🎉 — 100% reliable 🚀",
  "math": "α + β = γ; ∑ᵢ xᵢ → ∞",
  "quoted_quotes": "She said \"hi\" and left.",
  "backslash_path": "C:\\Users\\admin\\file.txt"
}
```

#### YAML

```yaml
code_snippet: "function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}"
emoji: Done ✅ 🎉 — 100% reliable 🚀
math: α + β = γ; ∑ᵢ xᵢ → ∞
quoted_quotes: She said "hi" and left.
backslash_path: C:\Users\admin\file.txt
```

#### TOML

```toml
code_snippet = "function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}"
emoji = "Done ✅ 🎉 — 100% reliable 🚀"
math = "α + β = γ; ∑ᵢ xᵢ → ∞"
quoted_quotes = "She said \"hi\" and left."
backslash_path = "C:\\Users\\admin\\file.txt"
```

#### MsgPack-b64

```text
haxjb2RlX3NuaXBwZXTZK2Z1bmN0aW9uIGYoeCkgewogIHJldHVybiB4WyJhXGJcImMiXSArIDE7Cn2lZW1vamnZJERvbmUg4pyFIPCfjokg4oCUIDEwMCUgcmVsaWFibGUg8J+agKRtYXRo2SHOsSArIM6yID0gzrM7IOKIkeG1oiB44bWiIOKGkiDiiJ6tcXVvdGVkX3F1b3Rlc7dTaGUgc2FpZCAiaGkiIGFuZCBsZWZ0Lq5iYWNrc2xhc2hfcGF0aLdDOlxVc2Vyc1xhZG1pblxmaWxlLnR4dA==
```

#### XML

```xml
<root><code_snippet>function f(x) {
  return x["a\b\"c"] + 1;
}</code_snippet><emoji>Done ✅ 🎉 — 100% reliable 🚀</emoji><math>α + β = γ; ∑ᵢ xᵢ → ∞</math><quoted_quotes>She said "hi" and left.</quoted_quotes><backslash_path>C:\Users\admin\file.txt</backslash_path></root>
```

---

## special_chars_it

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 311 | 131 | 123 | +2.2% | 6.0µs | 22.1µs | ✓ |  |
| ADP+LUT | 311 | 131 | 123 | +2.2% | 24.9µs | 43.6µs | ✓ |  |
| JSON-min | 327 | 134 | 126 | +0.0% | 3.3µs | 2.3µs | ✓ |  |
| JSON-pretty | 352 | 152 | 144 | -13.4% | 4.7µs | 2.3µs | ✓ |  |
| YAML | 305 | 130 | 123 | +3.0% | 200.1µs | 309.8µs | ✓ |  |
| TOML | 326 | 138 | 130 | -3.0% | 16.8µs | 28.4µs | ✓ |  |
| MsgPack-b64 | 396 | 268 | 250 | -100.0% | 1.3µs | 1.6µs | ✓ |  |
| XML | 377 | 151 | 146 | -12.7% | 10.4µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
frammento_codice="function f(x) {
  return x[\"a\\b\\\"c\"] + 1;
}";emoji="Fatto ✅ 🎉 — affidabile al 100% 🚀";matematica="α + β = γ; ∑ᵢ xᵢ → ∞";virgolette="Ha detto \"ciao\" e se n'è andata.";percorso="C:\\Utenti\\admin\\file.txt";accenti="città, perché, già, può, è, à, ò, ù, ì"
```

#### ADP+LUT

```text
frammento_codice="function f(x) {
  return x[\"a\\b\\\"c\"] + 1;
}";emoji="Fatto ✅ 🎉 — affidabile al 100% 🚀";matematica="α + β = γ; ∑ᵢ xᵢ → ∞";virgolette="Ha detto \"ciao\" e se n'è andata.";percorso="C:\\Utenti\\admin\\file.txt";accenti="città, perché, già, può, è, à, ò, ù, ì"
```

#### JSON-min

```json
{"frammento_codice":"function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}","emoji":"Fatto ✅ 🎉 — affidabile al 100% 🚀","matematica":"α + β = γ; ∑ᵢ xᵢ → ∞","virgolette":"Ha detto \"ciao\" e se n'è andata.","percorso":"C:\\Utenti\\admin\\file.txt","accenti":"città, perché, già, può, è, à, ò, ù, ì"}
```

#### JSON-pretty

```json
{
  "frammento_codice": "function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}",
  "emoji": "Fatto ✅ 🎉 — affidabile al 100% 🚀",
  "matematica": "α + β = γ; ∑ᵢ xᵢ → ∞",
  "virgolette": "Ha detto \"ciao\" e se n'è andata.",
  "percorso": "C:\\Utenti\\admin\\file.txt",
  "accenti": "città, perché, già, può, è, à, ò, ù, ì"
}
```

#### YAML

```yaml
frammento_codice: "function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}"
emoji: Fatto ✅ 🎉 — affidabile al 100% 🚀
matematica: α + β = γ; ∑ᵢ xᵢ → ∞
virgolette: Ha detto "ciao" e se n'è andata.
percorso: C:\Utenti\admin\file.txt
accenti: città, perché, già, può, è, à, ò, ù, ì
```

#### TOML

```toml
frammento_codice = "function f(x) {\n  return x[\"a\\b\\\"c\"] + 1;\n}"
emoji = "Fatto ✅ 🎉 — affidabile al 100% 🚀"
matematica = "α + β = γ; ∑ᵢ xᵢ → ∞"
virgolette = "Ha detto \"ciao\" e se n'è andata."
percorso = "C:\\Utenti\\admin\\file.txt"
accenti = "città, perché, già, può, è, à, ò, ù, ì"
```

#### MsgPack-b64

```text
hrBmcmFtbWVudG9fY29kaWNl2StmdW5jdGlvbiBmKHgpIHsKICByZXR1cm4geFsiYVxiXCJjIl0gKyAxOwp9pWVtb2pp2SpGYXR0byDinIUg8J+OiSDigJQgYWZmaWRhYmlsZSBhbCAxMDAlIPCfmoCqbWF0ZW1hdGljYdkhzrEgKyDOsiA9IM6zOyDiiJHhtaIgeOG1oiDihpIg4oieqnZpcmdvbGV0dGXZIUhhIGRldHRvICJjaWFvIiBlIHNlIG4nw6ggYW5kYXRhLqhwZXJjb3Jzb7hDOlxVdGVudGlcYWRtaW5cZmlsZS50eHSnYWNjZW50adkvY2l0dMOgLCBwZXJjaMOpLCBnacOgLCBwdcOyLCDDqCwgw6AsIMOyLCDDuSwgw6w=
```

#### XML

```xml
<root><frammento_codice>function f(x) {
  return x["a\b\"c"] + 1;
}</frammento_codice><emoji>Fatto ✅ 🎉 — affidabile al 100% 🚀</emoji><matematica>α + β = γ; ∑ᵢ xᵢ → ∞</matematica><virgolette>Ha detto "ciao" e se n'è andata.</virgolette><percorso>C:\Utenti\admin\file.txt</percorso><accenti>città, perché, già, può, è, à, ò, ù, ì</accenti></root>
```

---

## tabular_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 315 | 145 | 145 | +39.8% | 23.1µs | 49.3µs | ✓ |  |
| ADP+LUT | 297 | 147 | 147 | +39.0% | 51.6µs | 78.7µs | ✓ |  |
| JSON-min | 808 | 241 | 242 | +0.0% | 9.7µs | 6.4µs | ✓ |  |
| JSON-pretty | 1316 | 426 | 426 | -76.8% | 32.7µs | 6.6µs | ✓ |  |
| YAML | 794 | 303 | 302 | -25.7% | 921.1µs | 1.77ms | ✓ |  |
| TOML | 919 | 301 | 301 | -24.9% | 49.0µs | 125.7µs | ✓ |  |
| MsgPack-b64 | 816 | 551 | 503 | -128.6% | 3.4µs | 5.1µs | ✓ |  |
| XML | 1229 | 383 | 384 | -58.9% | 64.0µs | — | — | no decoder (one-way) |
| CSV | 347 | 133 | 143 | +44.8% | 16.7µs | 11.3µs | ✗ |  |

### Esempi codificati

#### ADP

```text
employees=#id,name,department,salary,active|1i,Alice,Sales,52000.0,1|2,Bruno,Engineering,68000.0,1|3,Carla,Sales,55000.0,0|4,David,Engineering,72000.0,1|5,Elena,Marketing,49000.0,1|6,Fabio,Engineering,80000.0,1|7,Grace,Sales,53000.0,1|8,Hugo,Marketing,51000.0,0|9,Irene,Engineering,75000.0,1|10,Luca,Sales,56000.0,1
```

#### ADP+LUT

```text
employees=#i,nm,dp,sl,ac2|1i,Alice,Sales,52000.0,1|2,Bruno,Engineering,68000.0,1|3,Carla,Sales,55000.0,0|4,David,Engineering,72000.0,1|5,Elena,Marketing,49000.0,1|6,Fabio,Engineering,80000.0,1|7,Grace,Sales,53000.0,1|8,Hugo,Marketing,51000.0,0|9,Irene,Engineering,75000.0,1|10,Luca,Sales,56000.0,1
```

#### JSON-min

```json
{"employees":[{"id":1,"name":"Alice","department":"Sales","salary":52000.0,"active":true},{"id":2,"name":"Bruno","department":"Engineering","salary":68000.0,"active":true},{"id":3,"name":"Carla","department":"Sales","salary":55000.0,"active":false},{"id":4,"name":"David","department":"Engineering","salary":72000.0,"active":true},{"id":5,"name":"Elena","department":"Marketing","salary":49000.0,"active":true},{"id":6,"name":"Fabio","department":"Engineering","salary":80000.0,"active":true},{"id":7,"name":"Grace","department":"Sales","salary":53000.0,"active":true},{"id":8,"name":"Hugo","department":"Marketing","salary":51000.0,"active":false},{"id":9,"name":"Irene","department":"Engineering","salary":75000.0,"active":true},{"id":10,"name":"Luca","department":"Sales","salary":56000.0,"active":true}]}
```

#### JSON-pretty

```json
{
  "employees": [
    {
      "id": 1,
      "name": "Alice",
      "department": "Sales",
      "salary": 52000.0,
      "active": true
    },
    {
      "id": 2,
      "name": "Bruno",
      "department": "Engineering",
      "salary": 68000.0,
      "active": true
    },
    {
      "id": 3,
      "name": "Carla",
      "department": "Sales",
      "salary": 55000.0,
      "active": false
    },
    {
      "id": 4,
      "name": "David",
      "department": "Engineering",
      "salary": 72000.0,
      "active": true
    },
    {
      "id": 5,
      "name": "Elena",
      "department": "Marketing",
      "salary": 49000.0,
      "active": true
    },
    {
      "id": 6,
      "name": "Fabio",
      "department": "Engineering",
      "salary": 80000.0,
      "active": true
    },
    {
      "id": 7,
      "name": "Grace",
      "department": "Sales",
      "salary": 53000.0,
      "active": true
    },
    {
      "id": 8,
      "name": "Hugo",
      "department": "Marketing",
      "salary": 51000.0,
      "active": false
    },
    {
      "id": 9,
      "name": "Irene",
      "department": "Engineering",
      "salary": 75000.0,
      "active": true
    },
    {
      "i
... [troncato]
```

#### YAML

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
- id: 3
  name: Carla
  department: Sales
  salary: 55000.0
  active: false
- id: 4
  name: David
  department: Engineering
  salary: 72000.0
  active: true
- id: 5
  name: Elena
  department: Marketing
  salary: 49000.0
  active: true
- id: 6
  name: Fabio
  department: Engineering
  salary: 80000.0
  active: true
- id: 7
  name: Grace
  department: Sales
  salary: 53000.0
  active: true
- id: 8
  name: Hugo
  department: Marketing
  salary: 51000.0
  active: false
- id: 9
  name: Irene
  department: Engineering
  salary: 75000.0
  active: true
- id: 10
  name: Luca
  department: Sales
  salary: 56000.0
  active: true
```

#### TOML

```toml
employees = [
    { id = 1, name = "Alice", department = "Sales", salary = 52000.0, active = true },
    { id = 2, name = "Bruno", department = "Engineering", salary = 68000.0, active = true },
    { id = 3, name = "Carla", department = "Sales", salary = 55000.0, active = false },
    { id = 4, name = "David", department = "Engineering", salary = 72000.0, active = true },
    { id = 5, name = "Elena", department = "Marketing", salary = 49000.0, active = true },
    { id = 6, name = "Fabio", department = "Engineering", salary = 80000.0, active = true },
    { id = 7, name = "Grace", department = "Sales", salary = 53000.0, active = true },
    { id = 8, name = "Hugo", department = "Marketing", salary = 51000.0, active = false },
    { id = 9, name = "Irene", department = "Engineering", salary = 75000.0, active = true },
    { id = 10, name = "Luca", department = "Sales", salary = 56000.0, active = true },
]
```

#### MsgPack-b64

```text
gallbXBsb3llZXOahaJpZAGkbmFtZaVBbGljZapkZXBhcnRtZW50pVNhbGVzpnNhbGFyectA6WQAAAAAAKZhY3RpdmXDhaJpZAKkbmFtZaVCcnVub6pkZXBhcnRtZW50q0VuZ2luZWVyaW5npnNhbGFyectA8JoAAAAAAKZhY3RpdmXDhaJpZAOkbmFtZaVDYXJsYapkZXBhcnRtZW50pVNhbGVzpnNhbGFyectA6tsAAAAAAKZhY3RpdmXChaJpZASkbmFtZaVEYXZpZKpkZXBhcnRtZW50q0VuZ2luZWVyaW5npnNhbGFyectA8ZQAAAAAAKZhY3RpdmXDhaJpZAWkbmFtZaVFbGVuYapkZXBhcnRtZW50qU1hcmtldGluZ6ZzYWxhcnnLQOftAAAAAACmYWN0aXZlw4WiaWQGpG5hbWWlRmFiaW+qZGVwYXJ0bWVudKtFbmdpbmVlcmluZ6ZzYWxhcnnLQPOIAAAAAACmYWN0aXZlw4WiaWQHpG5hbWWlR3JhY2WqZGVwYXJ0bWVudKVTYWxlc6ZzYWxhcnnLQOnhAAAAAACmYWN0aXZlw4WiaWQIpG5hbWWkSHVnb6pkZXBhcnRtZW50qU1hcmtldGluZ6ZzYWxhcnnLQOjnAAAAAACmYWN0aXZlwoWiaWQJpG5hbWWlSXJlbmWqZGVwYXJ0bWVudKtFbmdpbmVlcmluZ6ZzYWxhcnnLQPJPgAAAAACmYWN0aXZlw4WiaWQKpG5hbWWkTHVjYapkZXBhcnRtZW50pVNhbGVzpnNhbGFyectA61gAAAAAAKZhY3RpdmXD
```

#### XML

```xml
<root><employees><item><id>1</id><name>Alice</name><department>Sales</department><salary>52000.0</salary><active>True</active></item><item><id>2</id><name>Bruno</name><department>Engineering</department><salary>68000.0</salary><active>True</active></item><item><id>3</id><name>Carla</name><department>Sales</department><salary>55000.0</salary><active>False</active></item><item><id>4</id><name>David</name><department>Engineering</department><salary>72000.0</salary><active>True</active></item><item><id>5</id><name>Elena</name><department>Marketing</department><salary>49000.0</salary><active>True</active></item><item><id>6</id><name>Fabio</name><department>Engineering</department><salary>80000.0</salary><active>True</active></item><item><id>7</id><name>Grace</name><department>Sales</department><salary>53000.0</salary><active>True</active></item><item><id>8</id><name>Hugo</name><department>Marketing</department><salary>51000.0</salary><active>False</active></item><item><id>9</id><name>Irene</name><department>Engineering</department><salary>75000.0</salary><active>True</active></item><item><id>10</id><name>Luca</name><department>Sales</department><salary>56000.0</salary><active>True</acti
... [troncato]
```

#### CSV

```text
id,name,department,salary,active
1,Alice,Sales,52000.0,True
2,Bruno,Engineering,68000.0,True
3,Carla,Sales,55000.0,False
4,David,Engineering,72000.0,True
5,Elena,Marketing,49000.0,True
6,Fabio,Engineering,80000.0,True
7,Grace,Sales,53000.0,True
8,Hugo,Marketing,51000.0,False
9,Irene,Engineering,75000.0,True
10,Luca,Sales,56000.0,True
```

---

## tabular_it

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 315 | 164 | 163 | +50.8% | 22.1µs | 48.5µs | ✓ |  |
| ADP+LUT | 314 | 164 | 163 | +50.8% | 51.9µs | 78.0µs | ✓ |  |
| JSON-min | 853 | 333 | 304 | +0.0% | 10.1µs | 6.4µs | ✓ |  |
| JSON-pretty | 1361 | 518 | 488 | -55.6% | 32.5µs | 6.6µs | ✓ |  |
| YAML | 839 | 366 | 354 | -9.9% | 936.4µs | 1.76ms | ✓ |  |
| TOML | 964 | 373 | 353 | -12.0% | 50.4µs | 126.3µs | ✓ |  |
| MsgPack-b64 | 876 | 585 | 555 | -75.7% | 3.5µs | 5.1µs | ✓ |  |
| XML | 1325 | 539 | 498 | -61.9% | 64.5µs | — | — | no decoder (one-way) |
| CSV | 346 | 149 | 159 | +55.3% | 16.9µs | 11.1µs | ✗ |  |

### Esempi codificati

#### ADP

```text
dipendenti=#id,nome,dipartimento,stipendio,attivo|1i,Alice,Vendite,52000.0,1|2,Bruno,Tecnico,68000.0,1|3,Carla,Vendite,55000.0,0|4,Davide,Tecnico,72000.0,1|5,Elena,Marketing,49000.0,1|6,Fabio,Tecnico,80000.0,1|7,Giulia,Vendite,53000.0,1|8,Hugo,Marketing,51000.0,0|9,Irene,Tecnico,75000.0,1|10,Luca,Vendite,56000.0,1
```

#### ADP+LUT

```text
dipendenti=#i,nome,dipartimento,stipendio,attivo|1i,Alice,Vendite,52000.0,1|2,Bruno,Tecnico,68000.0,1|3,Carla,Vendite,55000.0,0|4,Davide,Tecnico,72000.0,1|5,Elena,Marketing,49000.0,1|6,Fabio,Tecnico,80000.0,1|7,Giulia,Vendite,53000.0,1|8,Hugo,Marketing,51000.0,0|9,Irene,Tecnico,75000.0,1|10,Luca,Vendite,56000.0,1
```

#### JSON-min

```json
{"dipendenti":[{"id":1,"nome":"Alice","dipartimento":"Vendite","stipendio":52000.0,"attivo":true},{"id":2,"nome":"Bruno","dipartimento":"Tecnico","stipendio":68000.0,"attivo":true},{"id":3,"nome":"Carla","dipartimento":"Vendite","stipendio":55000.0,"attivo":false},{"id":4,"nome":"Davide","dipartimento":"Tecnico","stipendio":72000.0,"attivo":true},{"id":5,"nome":"Elena","dipartimento":"Marketing","stipendio":49000.0,"attivo":true},{"id":6,"nome":"Fabio","dipartimento":"Tecnico","stipendio":80000.0,"attivo":true},{"id":7,"nome":"Giulia","dipartimento":"Vendite","stipendio":53000.0,"attivo":true},{"id":8,"nome":"Hugo","dipartimento":"Marketing","stipendio":51000.0,"attivo":false},{"id":9,"nome":"Irene","dipartimento":"Tecnico","stipendio":75000.0,"attivo":true},{"id":10,"nome":"Luca","dipartimento":"Vendite","stipendio":56000.0,"attivo":true}]}
```

#### JSON-pretty

```json
{
  "dipendenti": [
    {
      "id": 1,
      "nome": "Alice",
      "dipartimento": "Vendite",
      "stipendio": 52000.0,
      "attivo": true
    },
    {
      "id": 2,
      "nome": "Bruno",
      "dipartimento": "Tecnico",
      "stipendio": 68000.0,
      "attivo": true
    },
    {
      "id": 3,
      "nome": "Carla",
      "dipartimento": "Vendite",
      "stipendio": 55000.0,
      "attivo": false
    },
    {
      "id": 4,
      "nome": "Davide",
      "dipartimento": "Tecnico",
      "stipendio": 72000.0,
      "attivo": true
    },
    {
      "id": 5,
      "nome": "Elena",
      "dipartimento": "Marketing",
      "stipendio": 49000.0,
      "attivo": true
    },
    {
      "id": 6,
      "nome": "Fabio",
      "dipartimento": "Tecnico",
      "stipendio": 80000.0,
      "attivo": true
    },
    {
      "id": 7,
      "nome": "Giulia",
      "dipartimento": "Vendite",
      "stipendio": 53000.0,
      "attivo": true
    },
    {
      "id": 8,
      "nome": "Hugo",
      "dipartimento": "Marketing",
      "stipendio": 51000.0,
      "attivo": false
    },
    {
      "id": 9,
      "nome": "Irene",
      "dipartimento": "Tecnico",
      "stipendio": 75000.0,
    
... [troncato]
```

#### YAML

```yaml
dipendenti:
- id: 1
  nome: Alice
  dipartimento: Vendite
  stipendio: 52000.0
  attivo: true
- id: 2
  nome: Bruno
  dipartimento: Tecnico
  stipendio: 68000.0
  attivo: true
- id: 3
  nome: Carla
  dipartimento: Vendite
  stipendio: 55000.0
  attivo: false
- id: 4
  nome: Davide
  dipartimento: Tecnico
  stipendio: 72000.0
  attivo: true
- id: 5
  nome: Elena
  dipartimento: Marketing
  stipendio: 49000.0
  attivo: true
- id: 6
  nome: Fabio
  dipartimento: Tecnico
  stipendio: 80000.0
  attivo: true
- id: 7
  nome: Giulia
  dipartimento: Vendite
  stipendio: 53000.0
  attivo: true
- id: 8
  nome: Hugo
  dipartimento: Marketing
  stipendio: 51000.0
  attivo: false
- id: 9
  nome: Irene
  dipartimento: Tecnico
  stipendio: 75000.0
  attivo: true
- id: 10
  nome: Luca
  dipartimento: Vendite
  stipendio: 56000.0
  attivo: true
```

#### TOML

```toml
dipendenti = [
    { id = 1, nome = "Alice", dipartimento = "Vendite", stipendio = 52000.0, attivo = true },
    { id = 2, nome = "Bruno", dipartimento = "Tecnico", stipendio = 68000.0, attivo = true },
    { id = 3, nome = "Carla", dipartimento = "Vendite", stipendio = 55000.0, attivo = false },
    { id = 4, nome = "Davide", dipartimento = "Tecnico", stipendio = 72000.0, attivo = true },
    { id = 5, nome = "Elena", dipartimento = "Marketing", stipendio = 49000.0, attivo = true },
    { id = 6, nome = "Fabio", dipartimento = "Tecnico", stipendio = 80000.0, attivo = true },
    { id = 7, nome = "Giulia", dipartimento = "Vendite", stipendio = 53000.0, attivo = true },
    { id = 8, nome = "Hugo", dipartimento = "Marketing", stipendio = 51000.0, attivo = false },
    { id = 9, nome = "Irene", dipartimento = "Tecnico", stipendio = 75000.0, attivo = true },
    { id = 10, nome = "Luca", dipartimento = "Vendite", stipendio = 56000.0, attivo = true },
]
```

#### MsgPack-b64

```text
gapkaXBlbmRlbnRpmoWiaWQBpG5vbWWlQWxpY2WsZGlwYXJ0aW1lbnRvp1ZlbmRpdGWpc3RpcGVuZGlvy0DpZAAAAAAApmF0dGl2b8OFomlkAqRub21lpUJydW5vrGRpcGFydGltZW50b6dUZWNuaWNvqXN0aXBlbmRpb8tA8JoAAAAAAKZhdHRpdm/DhaJpZAOkbm9tZaVDYXJsYaxkaXBhcnRpbWVudG+nVmVuZGl0ZalzdGlwZW5kaW/LQOrbAAAAAACmYXR0aXZvwoWiaWQEpG5vbWWmRGF2aWRlrGRpcGFydGltZW50b6dUZWNuaWNvqXN0aXBlbmRpb8tA8ZQAAAAAAKZhdHRpdm/DhaJpZAWkbm9tZaVFbGVuYaxkaXBhcnRpbWVudG+pTWFya2V0aW5nqXN0aXBlbmRpb8tA5+0AAAAAAKZhdHRpdm/DhaJpZAakbm9tZaVGYWJpb6xkaXBhcnRpbWVudG+nVGVjbmljb6lzdGlwZW5kaW/LQPOIAAAAAACmYXR0aXZvw4WiaWQHpG5vbWWmR2l1bGlhrGRpcGFydGltZW50b6dWZW5kaXRlqXN0aXBlbmRpb8tA6eEAAAAAAKZhdHRpdm/DhaJpZAikbm9tZaRIdWdvrGRpcGFydGltZW50b6lNYXJrZXRpbmepc3RpcGVuZGlvy0Do5wAAAAAApmF0dGl2b8KFomlkCaRub21lpUlyZW5lrGRpcGFydGltZW50b6dUZWNuaWNvqXN0aXBlbmRpb8tA8k+AAAAAAKZhdHRpdm/DhaJpZAqkbm9tZaRMdWNhrGRpcGFydGltZW50b6dWZW5kaXRlqXN0aXBlbmRpb8tA61gAAAAAAKZhdHRpdm/D
```

#### XML

```xml
<root><dipendenti><item><id>1</id><nome>Alice</nome><dipartimento>Vendite</dipartimento><stipendio>52000.0</stipendio><attivo>True</attivo></item><item><id>2</id><nome>Bruno</nome><dipartimento>Tecnico</dipartimento><stipendio>68000.0</stipendio><attivo>True</attivo></item><item><id>3</id><nome>Carla</nome><dipartimento>Vendite</dipartimento><stipendio>55000.0</stipendio><attivo>False</attivo></item><item><id>4</id><nome>Davide</nome><dipartimento>Tecnico</dipartimento><stipendio>72000.0</stipendio><attivo>True</attivo></item><item><id>5</id><nome>Elena</nome><dipartimento>Marketing</dipartimento><stipendio>49000.0</stipendio><attivo>True</attivo></item><item><id>6</id><nome>Fabio</nome><dipartimento>Tecnico</dipartimento><stipendio>80000.0</stipendio><attivo>True</attivo></item><item><id>7</id><nome>Giulia</nome><dipartimento>Vendite</dipartimento><stipendio>53000.0</stipendio><attivo>True</attivo></item><item><id>8</id><nome>Hugo</nome><dipartimento>Marketing</dipartimento><stipendio>51000.0</stipendio><attivo>False</attivo></item><item><id>9</id><nome>Irene</nome><dipartimento>Tecnico</dipartimento><stipendio>75000.0</stipendio><attivo>True</attivo></item><item><id>10</id><nome>
... [troncato]
```

#### CSV

```text
id,nome,dipartimento,stipendio,attivo
1,Alice,Vendite,52000.0,True
2,Bruno,Tecnico,68000.0,True
3,Carla,Vendite,55000.0,False
4,Davide,Tecnico,72000.0,True
5,Elena,Marketing,49000.0,True
6,Fabio,Tecnico,80000.0,True
7,Giulia,Vendite,53000.0,True
8,Hugo,Marketing,51000.0,False
9,Irene,Tecnico,75000.0,True
10,Luca,Vendite,56000.0,True
```

---

## database_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 337 | 134 | 136 | +10.7% | 18.9µs | 37.7µs | ✓ |  |
| ADP+LUT | 327 | 134 | 136 | +10.7% | 42.6µs | 66.5µs | ✓ |  |
| JSON-min | 458 | 150 | 152 | +0.0% | 7.2µs | 4.1µs | ✓ |  |
| JSON-pretty | 740 | 249 | 250 | -66.0% | 22.2µs | 4.3µs | ✓ |  |
| YAML | 486 | 187 | 187 | -24.7% | 523.8µs | 978.6µs | ✓ |  |
| TOML | — | — | — | — | — | — | — | N/A (TypeError) |
| MsgPack-b64 | 512 | 352 | 335 | -134.7% | 2.3µs | 3.0µs | ✓ |  |
| XML | 647 | 218 | 220 | -45.3% | 36.6µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
order={id=ORD-2026-04018;customer={id=7412;name="Acme Corp.";email=ops@acme.example;vip=1};items=#sku,qty,unit_price|A1,2,19.99|B7,1i,149.0|C3,5,4.5;shipping={address="12 Market St, Springfield, IL 62701, USA";method=standard;tracking=~};totals={subtotal=212.48;tax=17.0;total=229.48};paid=1;notes="Leave at the back door if no answer."}
```

#### ADP+LUT

```text
order={i=ORD-2026-04018;customer={i=7412;nm="Acme Corp.";em=ops@acme.example;vip=1};im=#sku,qty,unit_price|A1,2,19.99|B7,1i,149.0|C3,5,4.5;shipping={address="12 Market St, Springfield, IL 62701, USA";method=standard;tracking=~};totals={subtotal=212.48;tax=17.0;total=229.48};paid=1;notes="Leave at the back door if no answer."}
```

#### JSON-min

```json
{"order":{"id":"ORD-2026-04018","customer":{"id":7412,"name":"Acme Corp.","email":"ops@acme.example","vip":true},"items":[{"sku":"A1","qty":2,"unit_price":19.99},{"sku":"B7","qty":1,"unit_price":149.0},{"sku":"C3","qty":5,"unit_price":4.5}],"shipping":{"address":"12 Market St, Springfield, IL 62701, USA","method":"standard","tracking":null},"totals":{"subtotal":212.48,"tax":17.0,"total":229.48},"paid":true,"notes":"Leave at the back door if no answer."}}
```

#### JSON-pretty

```json
{
  "order": {
    "id": "ORD-2026-04018",
    "customer": {
      "id": 7412,
      "name": "Acme Corp.",
      "email": "ops@acme.example",
      "vip": true
    },
    "items": [
      {
        "sku": "A1",
        "qty": 2,
        "unit_price": 19.99
      },
      {
        "sku": "B7",
        "qty": 1,
        "unit_price": 149.0
      },
      {
        "sku": "C3",
        "qty": 5,
        "unit_price": 4.5
      }
    ],
    "shipping": {
      "address": "12 Market St, Springfield, IL 62701, USA",
      "method": "standard",
      "tracking": null
    },
    "totals": {
      "subtotal": 212.48,
      "tax": 17.0,
      "total": 229.48
    },
    "paid": true,
    "notes": "Leave at the back door if no answer."
  }
}
```

#### YAML

```yaml
order:
  id: ORD-2026-04018
  customer:
    id: 7412
    name: Acme Corp.
    email: ops@acme.example
    vip: true
  items:
  - sku: A1
    qty: 2
    unit_price: 19.99
  - sku: B7
    qty: 1
    unit_price: 149.0
  - sku: C3
    qty: 5
    unit_price: 4.5
  shipping:
    address: 12 Market St, Springfield, IL 62701, USA
    method: standard
    tracking: null
  totals:
    subtotal: 212.48
    tax: 17.0
    total: 229.48
  paid: true
  notes: Leave at the back door if no answer.
```

#### MsgPack-b64

```text
gaVvcmRlcoeiaWSuT1JELTIwMjYtMDQwMTioY3VzdG9tZXKEomlkzRz0pG5hbWWqQWNtZSBDb3JwLqVlbWFpbLBvcHNAYWNtZS5leGFtcGxlo3ZpcMOlaXRlbXOTg6Nza3WiQTGjcXR5Aqp1bml0X3ByaWNly0Az/XCj1wo9g6Nza3WiQjejcXR5Aap1bml0X3ByaWNly0BioAAAAAAAg6Nza3WiQzOjcXR5Bap1bml0X3ByaWNly0ASAAAAAAAAqHNoaXBwaW5ng6dhZGRyZXNz2SgxMiBNYXJrZXQgU3QsIFNwcmluZ2ZpZWxkLCBJTCA2MjcwMSwgVVNBpm1ldGhvZKhzdGFuZGFyZKh0cmFja2luZ8CmdG90YWxzg6hzdWJ0b3RhbMtAao9cKPXCj6N0YXjLQDEAAAAAAACldG90YWzLQGyvXCj1wo+kcGFpZMOlbm90ZXPZJExlYXZlIGF0IHRoZSBiYWNrIGRvb3IgaWYgbm8gYW5zd2VyLg==
```

#### XML

```xml
<root><order><id>ORD-2026-04018</id><customer><id>7412</id><name>Acme Corp.</name><email>ops@acme.example</email><vip>True</vip></customer><items><item><sku>A1</sku><qty>2</qty><unit_price>19.99</unit_price></item><item><sku>B7</sku><qty>1</qty><unit_price>149.0</unit_price></item><item><sku>C3</sku><qty>5</qty><unit_price>4.5</unit_price></item></items><shipping><address>12 Market St, Springfield, IL 62701, USA</address><method>standard</method><tracking nil="true" /></shipping><totals><subtotal>212.48</subtotal><tax>17.0</tax><total>229.48</total></totals><paid>True</paid><notes>Leave at the back door if no answer.</notes></order></root>
```

---

## database_it

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 373 | 157 | 156 | +12.8% | 17.9µs | 40.1µs | ✓ |  |
| ADP+LUT | 368 | 157 | 156 | +12.8% | 42.5µs | 65.8µs | ✓ |  |
| JSON-min | 504 | 180 | 179 | +0.0% | 7.0µs | 4.0µs | ✓ |  |
| JSON-pretty | 786 | 279 | 277 | -55.0% | 21.5µs | 4.2µs | ✓ |  |
| YAML | 532 | 215 | 207 | -19.4% | 519.4µs | 998.9µs | ✓ |  |
| TOML | — | — | — | — | — | — | — | N/A (TypeError) |
| MsgPack-b64 | 572 | 385 | 369 | -113.9% | 2.2µs | 3.1µs | ✓ |  |
| XML | 730 | 271 | 268 | -50.6% | 36.9µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
ordine={id=ORD-2026-04018;cliente={id=7412;ragione_sociale="Acme S.r.l.";email=ops@acme.example;vip=1};articoli=#sku,qta,prezzo_unitario|A1,2,19.99|B7,1i,149.0|C3,5,4.5;spedizione={indirizzo="Via Roma 12, 35100 Padova, Italia";metodo=standard;tracking=~};totali={imponibile=212.48;iva=46.74;totale=259.22};pagato=1;note="Lasciare sulla porta sul retro in caso di assenza."}
```

#### ADP+LUT

```text
ordine={i=ORD-2026-04018;cliente={i=7412;ragione_sociale="Acme S.r.l.";em=ops@acme.example;vip=1};articoli=#sku,qta,prezzo_unitario|A1,2,19.99|B7,1i,149.0|C3,5,4.5;spedizione={indirizzo="Via Roma 12, 35100 Padova, Italia";metodo=standard;tracking=~};totali={imponibile=212.48;iva=46.74;totale=259.22};pagato=1;note="Lasciare sulla porta sul retro in caso di assenza."}
```

#### JSON-min

```json
{"ordine":{"id":"ORD-2026-04018","cliente":{"id":7412,"ragione_sociale":"Acme S.r.l.","email":"ops@acme.example","vip":true},"articoli":[{"sku":"A1","qta":2,"prezzo_unitario":19.99},{"sku":"B7","qta":1,"prezzo_unitario":149.0},{"sku":"C3","qta":5,"prezzo_unitario":4.5}],"spedizione":{"indirizzo":"Via Roma 12, 35100 Padova, Italia","metodo":"standard","tracking":null},"totali":{"imponibile":212.48,"iva":46.74,"totale":259.22},"pagato":true,"note":"Lasciare sulla porta sul retro in caso di assenza."}}
```

#### JSON-pretty

```json
{
  "ordine": {
    "id": "ORD-2026-04018",
    "cliente": {
      "id": 7412,
      "ragione_sociale": "Acme S.r.l.",
      "email": "ops@acme.example",
      "vip": true
    },
    "articoli": [
      {
        "sku": "A1",
        "qta": 2,
        "prezzo_unitario": 19.99
      },
      {
        "sku": "B7",
        "qta": 1,
        "prezzo_unitario": 149.0
      },
      {
        "sku": "C3",
        "qta": 5,
        "prezzo_unitario": 4.5
      }
    ],
    "spedizione": {
      "indirizzo": "Via Roma 12, 35100 Padova, Italia",
      "metodo": "standard",
      "tracking": null
    },
    "totali": {
      "imponibile": 212.48,
      "iva": 46.74,
      "totale": 259.22
    },
    "pagato": true,
    "note": "Lasciare sulla porta sul retro in caso di assenza."
  }
}
```

#### YAML

```yaml
ordine:
  id: ORD-2026-04018
  cliente:
    id: 7412
    ragione_sociale: Acme S.r.l.
    email: ops@acme.example
    vip: true
  articoli:
  - sku: A1
    qta: 2
    prezzo_unitario: 19.99
  - sku: B7
    qta: 1
    prezzo_unitario: 149.0
  - sku: C3
    qta: 5
    prezzo_unitario: 4.5
  spedizione:
    indirizzo: Via Roma 12, 35100 Padova, Italia
    metodo: standard
    tracking: null
  totali:
    imponibile: 212.48
    iva: 46.74
    totale: 259.22
  pagato: true
  note: Lasciare sulla porta sul retro in caso di assenza.
```

#### MsgPack-b64

```text
gaZvcmRpbmWHomlkrk9SRC0yMDI2LTA0MDE4p2NsaWVudGWEomlkzRz0r3JhZ2lvbmVfc29jaWFsZatBY21lIFMuci5sLqVlbWFpbLBvcHNAYWNtZS5leGFtcGxlo3ZpcMOoYXJ0aWNvbGmTg6Nza3WiQTGjcXRhAq9wcmV6em9fdW5pdGFyaW/LQDP9cKPXCj2Do3NrdaJCN6NxdGEBr3ByZXp6b191bml0YXJpb8tAYqAAAAAAAIOjc2t1okMzo3F0YQWvcHJlenpvX3VuaXRhcmlvy0ASAAAAAAAAqnNwZWRpemlvbmWDqWluZGlyaXp6b9khVmlhIFJvbWEgMTIsIDM1MTAwIFBhZG92YSwgSXRhbGlhpm1ldG9kb6hzdGFuZGFyZKh0cmFja2luZ8CmdG90YWxpg6ppbXBvbmliaWxly0Bqj1wo9cKPo2l2YctAR164UeuFH6Z0b3RhbGXLQHAzhR64UeymcGFnYXRvw6Rub3Rl2TJMYXNjaWFyZSBzdWxsYSBwb3J0YSBzdWwgcmV0cm8gaW4gY2FzbyBkaSBhc3NlbnphLg==
```

#### XML

```xml
<root><ordine><id>ORD-2026-04018</id><cliente><id>7412</id><ragione_sociale>Acme S.r.l.</ragione_sociale><email>ops@acme.example</email><vip>True</vip></cliente><articoli><item><sku>A1</sku><qta>2</qta><prezzo_unitario>19.99</prezzo_unitario></item><item><sku>B7</sku><qta>1</qta><prezzo_unitario>149.0</prezzo_unitario></item><item><sku>C3</sku><qta>5</qta><prezzo_unitario>4.5</prezzo_unitario></item></articoli><spedizione><indirizzo>Via Roma 12, 35100 Padova, Italia</indirizzo><metodo>standard</metodo><tracking nil="true" /></spedizione><totali><imponibile>212.48</imponibile><iva>46.74</iva><totale>259.22</totale></totali><pagato>True</pagato><note>Lasciare sulla porta sul retro in caso di assenza.</note></ordine></root>
```

---

## agent_task_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 287 | 83 | 82 | +5.7% | 14.9µs | 29.8µs | ✓ |  |
| ADP+LUT | 204 | 76 | 75 | +13.6% | 39.6µs | 49.6µs | ✓ |  |
| JSON-min | 335 | 88 | 88 | +0.0% | 4.4µs | 2.8µs | ✓ |  |
| JSON-pretty | 450 | 145 | 144 | -64.8% | 10.7µs | 2.6µs | ✓ |  |
| YAML | 318 | 101 | 101 | -14.8% | 313.3µs | 550.8µs | ✓ |  |
| TOML | 356 | 109 | 108 | -23.9% | 24.5µs | 46.9µs | ✓ |  |
| MsgPack-b64 | 368 | 250 | 241 | -184.1% | 1.7µs | 2.0µs | ✓ |  |
| XML | 491 | 139 | 139 | -58.0% | 22.6µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
msg_id=m_8c14;from_agent=planner;to_agent=executor;intent=execute_step;step={n=3;tool=shell;command="uv run pytest -k 'roundtrip'";timeout_s=60};context={task_id=T-204;previous_outputs=["compile ok","lint ok"];constraints=[must_pass_tests,no_external_network]};expected_reply=step_result
```

#### ADP+LUT

```text
mi=m_8c14;fa=planner;ta=executor;it=execute_step;sp={n=3;tl=shell;cm="uv run pytest -k 'roundtrip'";to=60};cx={ti=T-204;po=["compile ok","lint ok"];cs=[must_pass_tests,no_external_network]};ex=step_result
```

#### JSON-min

```json
{"msg_id":"m_8c14","from_agent":"planner","to_agent":"executor","intent":"execute_step","step":{"n":3,"tool":"shell","command":"uv run pytest -k 'roundtrip'","timeout_s":60},"context":{"task_id":"T-204","previous_outputs":["compile ok","lint ok"],"constraints":["must_pass_tests","no_external_network"]},"expected_reply":"step_result"}
```

#### JSON-pretty

```json
{
  "msg_id": "m_8c14",
  "from_agent": "planner",
  "to_agent": "executor",
  "intent": "execute_step",
  "step": {
    "n": 3,
    "tool": "shell",
    "command": "uv run pytest -k 'roundtrip'",
    "timeout_s": 60
  },
  "context": {
    "task_id": "T-204",
    "previous_outputs": [
      "compile ok",
      "lint ok"
    ],
    "constraints": [
      "must_pass_tests",
      "no_external_network"
    ]
  },
  "expected_reply": "step_result"
}
```

#### YAML

```yaml
msg_id: m_8c14
from_agent: planner
to_agent: executor
intent: execute_step
step:
  n: 3
  tool: shell
  command: uv run pytest -k 'roundtrip'
  timeout_s: 60
context:
  task_id: T-204
  previous_outputs:
  - compile ok
  - lint ok
  constraints:
  - must_pass_tests
  - no_external_network
expected_reply: step_result
```

#### TOML

```toml
msg_id = "m_8c14"
from_agent = "planner"
to_agent = "executor"
intent = "execute_step"
expected_reply = "step_result"

[step]
n = 3
tool = "shell"
command = "uv run pytest -k 'roundtrip'"
timeout_s = 60

[context]
task_id = "T-204"
previous_outputs = [
    "compile ok",
    "lint ok",
]
constraints = [
    "must_pass_tests",
    "no_external_network",
]
```

#### MsgPack-b64

```text
h6Ztc2dfaWSmbV84YzE0qmZyb21fYWdlbnSncGxhbm5lcqh0b19hZ2VudKhleGVjdXRvcqZpbnRlbnSsZXhlY3V0ZV9zdGVwpHN0ZXCEoW4DpHRvb2ylc2hlbGynY29tbWFuZLx1diBydW4gcHl0ZXN0IC1rICdyb3VuZHRyaXAnqXRpbWVvdXRfczynY29udGV4dIOndGFza19pZKVULTIwNLBwcmV2aW91c19vdXRwdXRzkqpjb21waWxlIG9rp2xpbnQgb2urY29uc3RyYWludHOSr211c3RfcGFzc190ZXN0c7Nub19leHRlcm5hbF9uZXR3b3JrrmV4cGVjdGVkX3JlcGx5q3N0ZXBfcmVzdWx0
```

#### XML

```xml
<root><msg_id>m_8c14</msg_id><from_agent>planner</from_agent><to_agent>executor</to_agent><intent>execute_step</intent><step><n>3</n><tool>shell</tool><command>uv run pytest -k 'roundtrip'</command><timeout_s>60</timeout_s></step><context><task_id>T-204</task_id><previous_outputs><item>compile ok</item><item>lint ok</item></previous_outputs><constraints><item>must_pass_tests</item><item>no_external_network</item></constraints></context><expected_reply>step_result</expected_reply></root>
```

---

## agent_task_it

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 313 | 113 | 113 | +4.2% | 14.1µs | 28.4µs | ✓ |  |
| ADP+LUT | 297 | 110 | 110 | +6.8% | 35.5µs | 50.6µs | ✓ |  |
| JSON-min | 361 | 118 | 119 | +0.0% | 4.3µs | 2.6µs | ✓ |  |
| JSON-pretty | 476 | 175 | 175 | -48.3% | 10.1µs | 2.6µs | ✓ |  |
| YAML | 344 | 130 | 127 | -10.2% | 321.3µs | 559.2µs | ✓ |  |
| TOML | 382 | 139 | 139 | -17.8% | 26.3µs | 49.0µs | ✓ |  |
| MsgPack-b64 | 404 | 299 | 284 | -153.4% | 1.8µs | 2.0µs | ✓ |  |
| XML | 522 | 180 | 182 | -52.5% | 23.5µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
msg_id=m_8c14;agente_da=pianificatore;agente_a=esecutore;intento=esegui_passo;passo={n=3;strumento=shell;comando="uv run pytest -k 'roundtrip'";timeout_s=60};contesto={task_id=T-204;output_precedenti=["compilazione ok","lint ok"];vincoli=[test_devono_passare,rete_esterna_vietata]};risposta_attesa=risultato_passo
```

#### ADP+LUT

```text
mi=m_8c14;agente_da=pianificatore;agente_a=esecutore;intento=esegui_passo;passo={n=3;strumento=shell;comando="uv run pytest -k 'roundtrip'";to=60};contesto={ti=T-204;output_precedenti=["compilazione ok","lint ok"];vincoli=[test_devono_passare,rete_esterna_vietata]};risposta_attesa=risultato_passo
```

#### JSON-min

```json
{"msg_id":"m_8c14","agente_da":"pianificatore","agente_a":"esecutore","intento":"esegui_passo","passo":{"n":3,"strumento":"shell","comando":"uv run pytest -k 'roundtrip'","timeout_s":60},"contesto":{"task_id":"T-204","output_precedenti":["compilazione ok","lint ok"],"vincoli":["test_devono_passare","rete_esterna_vietata"]},"risposta_attesa":"risultato_passo"}
```

#### JSON-pretty

```json
{
  "msg_id": "m_8c14",
  "agente_da": "pianificatore",
  "agente_a": "esecutore",
  "intento": "esegui_passo",
  "passo": {
    "n": 3,
    "strumento": "shell",
    "comando": "uv run pytest -k 'roundtrip'",
    "timeout_s": 60
  },
  "contesto": {
    "task_id": "T-204",
    "output_precedenti": [
      "compilazione ok",
      "lint ok"
    ],
    "vincoli": [
      "test_devono_passare",
      "rete_esterna_vietata"
    ]
  },
  "risposta_attesa": "risultato_passo"
}
```

#### YAML

```yaml
msg_id: m_8c14
agente_da: pianificatore
agente_a: esecutore
intento: esegui_passo
passo:
  n: 3
  strumento: shell
  comando: uv run pytest -k 'roundtrip'
  timeout_s: 60
contesto:
  task_id: T-204
  output_precedenti:
  - compilazione ok
  - lint ok
  vincoli:
  - test_devono_passare
  - rete_esterna_vietata
risposta_attesa: risultato_passo
```

#### TOML

```toml
msg_id = "m_8c14"
agente_da = "pianificatore"
agente_a = "esecutore"
intento = "esegui_passo"
risposta_attesa = "risultato_passo"

[passo]
n = 3
strumento = "shell"
comando = "uv run pytest -k 'roundtrip'"
timeout_s = 60

[contesto]
task_id = "T-204"
output_precedenti = [
    "compilazione ok",
    "lint ok",
]
vincoli = [
    "test_devono_passare",
    "rete_esterna_vietata",
]
```

#### MsgPack-b64

```text
h6Ztc2dfaWSmbV84YzE0qWFnZW50ZV9kYa1waWFuaWZpY2F0b3JlqGFnZW50ZV9hqWVzZWN1dG9yZadpbnRlbnRvrGVzZWd1aV9wYXNzb6VwYXNzb4ShbgOpc3RydW1lbnRvpXNoZWxsp2NvbWFuZG+8dXYgcnVuIHB5dGVzdCAtayAncm91bmR0cmlwJ6l0aW1lb3V0X3M8qGNvbnRlc3Rvg6d0YXNrX2lkpVQtMjA0sW91dHB1dF9wcmVjZWRlbnRpkq9jb21waWxhemlvbmUgb2unbGludCBva6d2aW5jb2xpkrN0ZXN0X2Rldm9ub19wYXNzYXJltHJldGVfZXN0ZXJuYV92aWV0YXRhr3Jpc3Bvc3RhX2F0dGVzYa9yaXN1bHRhdG9fcGFzc28=
```

#### XML

```xml
<root><msg_id>m_8c14</msg_id><agente_da>pianificatore</agente_da><agente_a>esecutore</agente_a><intento>esegui_passo</intento><passo><n>3</n><strumento>shell</strumento><comando>uv run pytest -k 'roundtrip'</comando><timeout_s>60</timeout_s></passo><contesto><task_id>T-204</task_id><output_precedenti><item>compilazione ok</item><item>lint ok</item></output_precedenti><vincoli><item>test_devono_passare</item><item>rete_esterna_vietata</item></vincoli></contesto><risposta_attesa>risultato_passo</risposta_attesa></root>
```

---

## contacts_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 301 | 94 | 95 | +35.2% | 16.2µs | 29.8µs | ✓ |  |
| ADP+LUT | 284 | 96 | 97 | +33.8% | 39.1µs | 53.8µs | ✓ |  |
| JSON-min | 529 | 145 | 146 | +0.0% | 6.1µs | 3.6µs | ✓ |  |
| JSON-pretty | 787 | 240 | 240 | -65.5% | 17.3µs | 3.8µs | ✓ |  |
| YAML | 500 | 164 | 164 | -13.1% | 512.4µs | 921.7µs | ✓ |  |
| TOML | 574 | 176 | 176 | -21.4% | 45.7µs | 85.2µs | ✓ |  |
| MsgPack-b64 | 568 | 388 | 359 | -167.6% | 2.4µs | 3.3µs | ✓ |  |
| XML | 719 | 218 | 219 | -50.3% | 36.3µs | — | — | no decoder (one-way) |
| CSV | 297 | 92 | 93 | +36.6% | 10.5µs | 6.9µs | ✗ |  |

### Esempi codificati

#### ADP

```text
contacts=#id,name,email,homepage,country|1i,Alice,alice@example.com,https://alice.example/,US|2,Bruno,bruno@example.com,https://bruno.example/,IT|3,Carla,carla@example.com,https://carla.example/,FR|4,David,david@example.com,https://david.example/,DE|5,Elena,elena@example.com,https://elena.example/,ES
```

#### ADP+LUT

```text
contacts=#i,nm,em,hp,co|1i,Alice,alice@example.com,https://alice.example/,US|2,Bruno,bruno@example.com,https://bruno.example/,IT|3,Carla,carla@example.com,https://carla.example/,FR|4,David,david@example.com,https://david.example/,DE|5,Elena,elena@example.com,https://elena.example/,ES
```

#### JSON-min

```json
{"contacts":[{"id":1,"name":"Alice","email":"alice@example.com","homepage":"https://alice.example/","country":"US"},{"id":2,"name":"Bruno","email":"bruno@example.com","homepage":"https://bruno.example/","country":"IT"},{"id":3,"name":"Carla","email":"carla@example.com","homepage":"https://carla.example/","country":"FR"},{"id":4,"name":"David","email":"david@example.com","homepage":"https://david.example/","country":"DE"},{"id":5,"name":"Elena","email":"elena@example.com","homepage":"https://elena.example/","country":"ES"}]}
```

#### JSON-pretty

```json
{
  "contacts": [
    {
      "id": 1,
      "name": "Alice",
      "email": "alice@example.com",
      "homepage": "https://alice.example/",
      "country": "US"
    },
    {
      "id": 2,
      "name": "Bruno",
      "email": "bruno@example.com",
      "homepage": "https://bruno.example/",
      "country": "IT"
    },
    {
      "id": 3,
      "name": "Carla",
      "email": "carla@example.com",
      "homepage": "https://carla.example/",
      "country": "FR"
    },
    {
      "id": 4,
      "name": "David",
      "email": "david@example.com",
      "homepage": "https://david.example/",
      "country": "DE"
    },
    {
      "id": 5,
      "name": "Elena",
      "email": "elena@example.com",
      "homepage": "https://elena.example/",
      "country": "ES"
    }
  ]
}
```

#### YAML

```yaml
contacts:
- id: 1
  name: Alice
  email: alice@example.com
  homepage: https://alice.example/
  country: US
- id: 2
  name: Bruno
  email: bruno@example.com
  homepage: https://bruno.example/
  country: IT
- id: 3
  name: Carla
  email: carla@example.com
  homepage: https://carla.example/
  country: FR
- id: 4
  name: David
  email: david@example.com
  homepage: https://david.example/
  country: DE
- id: 5
  name: Elena
  email: elena@example.com
  homepage: https://elena.example/
  country: ES
```

#### TOML

```toml
[[contacts]]
id = 1
name = "Alice"
email = "alice@example.com"
homepage = "https://alice.example/"
country = "US"

[[contacts]]
id = 2
name = "Bruno"
email = "bruno@example.com"
homepage = "https://bruno.example/"
country = "IT"

[[contacts]]
id = 3
name = "Carla"
email = "carla@example.com"
homepage = "https://carla.example/"
country = "FR"

[[contacts]]
id = 4
name = "David"
email = "david@example.com"
homepage = "https://david.example/"
country = "DE"

[[contacts]]
id = 5
name = "Elena"
email = "elena@example.com"
homepage = "https://elena.example/"
country = "ES"
```

#### MsgPack-b64

```text
gahjb250YWN0c5WFomlkAaRuYW1lpUFsaWNlpWVtYWlssWFsaWNlQGV4YW1wbGUuY29tqGhvbWVwYWdltmh0dHBzOi8vYWxpY2UuZXhhbXBsZS+nY291bnRyeaJVU4WiaWQCpG5hbWWlQnJ1bm+lZW1haWyxYnJ1bm9AZXhhbXBsZS5jb22oaG9tZXBhZ2W2aHR0cHM6Ly9icnVuby5leGFtcGxlL6djb3VudHJ5oklUhaJpZAOkbmFtZaVDYXJsYaVlbWFpbLFjYXJsYUBleGFtcGxlLmNvbahob21lcGFnZbZodHRwczovL2NhcmxhLmV4YW1wbGUvp2NvdW50cnmiRlKFomlkBKRuYW1lpURhdmlkpWVtYWlssWRhdmlkQGV4YW1wbGUuY29tqGhvbWVwYWdltmh0dHBzOi8vZGF2aWQuZXhhbXBsZS+nY291bnRyeaJERYWiaWQFpG5hbWWlRWxlbmGlZW1haWyxZWxlbmFAZXhhbXBsZS5jb22oaG9tZXBhZ2W2aHR0cHM6Ly9lbGVuYS5leGFtcGxlL6djb3VudHJ5okVT
```

#### XML

```xml
<root><contacts><item><id>1</id><name>Alice</name><email>alice@example.com</email><homepage>https://alice.example/</homepage><country>US</country></item><item><id>2</id><name>Bruno</name><email>bruno@example.com</email><homepage>https://bruno.example/</homepage><country>IT</country></item><item><id>3</id><name>Carla</name><email>carla@example.com</email><homepage>https://carla.example/</homepage><country>FR</country></item><item><id>4</id><name>David</name><email>david@example.com</email><homepage>https://david.example/</homepage><country>DE</country></item><item><id>5</id><name>Elena</name><email>elena@example.com</email><homepage>https://elena.example/</homepage><country>ES</country></item></contacts></root>
```

#### CSV

```text
id,name,email,homepage,country
1,Alice,alice@example.com,https://alice.example/,US
2,Bruno,bruno@example.com,https://bruno.example/,IT
3,Carla,carla@example.com,https://carla.example/,FR
4,David,david@example.com,https://david.example/,DE
5,Elena,elena@example.com,https://elena.example/,ES
```

---

## nested_table_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 159 | 75 | 76 | +25.0% | 18.5µs | 27.5µs | ✓ |  |
| ADP+LUT | 150 | 76 | 77 | +24.0% | 45.9µs | 54.7µs | ✓ |  |
| JSON-min | 326 | 100 | 109 | +0.0% | 6.6µs | 3.8µs | ✓ |  |
| JSON-pretty | 692 | 210 | 214 | -110.0% | 24.7µs | 3.8µs | ✓ |  |
| YAML | 342 | 135 | 135 | -35.0% | 480.9µs | 950.5µs | ✓ |  |
| TOML | 408 | 145 | 145 | -45.0% | 39.7µs | 85.1µs | ✓ |  |
| MsgPack-b64 | 272 | 188 | 176 | -88.0% | 2.2µs | 2.8µs | ✓ |  |
| XML | 555 | 190 | 198 | -90.0% | 38.0µs | — | — | no decoder (one-way) |
| CSV | 238 | 88 | 89 | +12.0% | 10.7µs | 5.4µs | ✗ |  |

### Esempi codificati

#### ADP

```text
users=#id,name,roles,perms|1i,alice,[admin,ops],{read=1;write=1}|2,bob,[dev],{read=1;write=0}|3,carol,[dev,qa],{read=1;write=0}|4,dan,[viewer],{read=1;write=0}
```

#### ADP+LUT

```text
us=#i,nm,rs,perms|1i,alice,[admin,ops],{read=1;write=1}|2,bob,[dev],{read=1;write=0}|3,carol,[dev,qa],{read=1;write=0}|4,dan,[viewer],{read=1;write=0}
```

#### JSON-min

```json
{"users":[{"id":1,"name":"alice","roles":["admin","ops"],"perms":{"read":true,"write":true}},{"id":2,"name":"bob","roles":["dev"],"perms":{"read":true,"write":false}},{"id":3,"name":"carol","roles":["dev","qa"],"perms":{"read":true,"write":false}},{"id":4,"name":"dan","roles":["viewer"],"perms":{"read":true,"write":false}}]}
```

#### JSON-pretty

```json
{
  "users": [
    {
      "id": 1,
      "name": "alice",
      "roles": [
        "admin",
        "ops"
      ],
      "perms": {
        "read": true,
        "write": true
      }
    },
    {
      "id": 2,
      "name": "bob",
      "roles": [
        "dev"
      ],
      "perms": {
        "read": true,
        "write": false
      }
    },
    {
      "id": 3,
      "name": "carol",
      "roles": [
        "dev",
        "qa"
      ],
      "perms": {
        "read": true,
        "write": false
      }
    },
    {
      "id": 4,
      "name": "dan",
      "roles": [
        "viewer"
      ],
      "perms": {
        "read": true,
        "write": false
      }
    }
  ]
}
```

#### YAML

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
  roles:
  - dev
  perms:
    read: true
    write: false
- id: 3
  name: carol
  roles:
  - dev
  - qa
  perms:
    read: true
    write: false
- id: 4
  name: dan
  roles:
  - viewer
  perms:
    read: true
    write: false
```

#### TOML

```toml
[[users]]
id = 1
name = "alice"
roles = [
    "admin",
    "ops",
]

[users.perms]
read = true
write = true

[[users]]
id = 2
name = "bob"
roles = [
    "dev",
]

[users.perms]
read = true
write = false

[[users]]
id = 3
name = "carol"
roles = [
    "dev",
    "qa",
]

[users.perms]
read = true
write = false

[[users]]
id = 4
name = "dan"
roles = [
    "viewer",
]

[users.perms]
read = true
write = false
```

#### MsgPack-b64

```text
gaV1c2Vyc5SEomlkAaRuYW1lpWFsaWNlpXJvbGVzkqVhZG1pbqNvcHOlcGVybXOCpHJlYWTDpXdyaXRlw4SiaWQCpG5hbWWjYm9ipXJvbGVzkaNkZXalcGVybXOCpHJlYWTDpXdyaXRlwoSiaWQDpG5hbWWlY2Fyb2ylcm9sZXOSo2RldqJxYaVwZXJtc4KkcmVhZMOld3JpdGXChKJpZASkbmFtZaNkYW6lcm9sZXORpnZpZXdlcqVwZXJtc4KkcmVhZMOld3JpdGXC
```

#### XML

```xml
<root><users><item><id>1</id><name>alice</name><roles><item>admin</item><item>ops</item></roles><perms><read>True</read><write>True</write></perms></item><item><id>2</id><name>bob</name><roles><item>dev</item></roles><perms><read>True</read><write>False</write></perms></item><item><id>3</id><name>carol</name><roles><item>dev</item><item>qa</item></roles><perms><read>True</read><write>False</write></perms></item><item><id>4</id><name>dan</name><roles><item>viewer</item></roles><perms><read>True</read><write>False</write></perms></item></users></root>
```

#### CSV

```text
id,name,roles,perms
1,alice,"['admin', 'ops']","{'read': True, 'write': True}"
2,bob,['dev'],"{'read': True, 'write': False}"
3,carol,"['dev', 'qa']","{'read': True, 'write': False}"
4,dan,['viewer'],"{'read': True, 'write': False}"
```

---

## binary_en

| Formato | Bytes | Tok cl100k | Tok o200k | Δ vs JSON-min (cl100k) | Enc | Dec | Lossless | Note |
|---------|------:|-----------:|----------:|-----------------------:|----:|----:|:--------:|------|
| ADP | 412 | 267 | 260 | — | 4.6µs | 24.6µs | ✓ |  |
| ADP+LUT | 407 | 266 | 260 | — | 25.0µs | 46.7µs | ✓ |  |
| JSON-min | — | — | — | — | — | — | — | N/A (TypeError) |
| JSON-pretty | — | — | — | — | — | — | — | N/A (TypeError) |
| YAML | 460 | 290 | 283 | — | 242.7µs | 313.0µs | ✓ |  |
| TOML | — | — | — | — | — | — | — | N/A (TypeError) |
| MsgPack-b64 | 428 | 308 | 297 | — | 1.3µs | 1.2µs | ✓ |  |
| XML | 909 | 465 | 466 | — | 11.2µs | — | — | no decoder (one-way) |
| CSV | — | — | — | — | — | — | — | N/A (ValueError) |

### Esempi codificati

#### ADP

```text
thumbnail={name=thumb.png;mime=image/png;data=b!kgjPONoJQjqQpV7LfJRcxAsEq/7nbT5RsKVSGdy9Ot7a/QCpXceGM1I/o5AGhElB+G39LaX56A4PXabEkEOGcs9P8pErgMacid2AGfbd/tXnIslZ3HqI163x8rbrngY3MEjYma9cK5fV8HFAidL7y9hEqFgBlSe9ETY0HV7L1dcahHVyYaA8VUyf6sbzfNcBzaaiCO4SmOAkLTx7VWRhwi7aldYztNP/2VfUp3TEYiNp8zfSjGrlPZP1Uu6PiTy/9a/IMMG8jdf+roERf1Cuug+axC+mjJvaQ/1XwnjHUUK1dv1z/ipI8T1dp/Qvww2ldOHK7cG9eIuFKu1u5MM2ng==;width=64;height=64}
```

#### ADP+LUT

```text
thumbnail={nm=thumb.png;mime=image/png;d=b!kgjPONoJQjqQpV7LfJRcxAsEq/7nbT5RsKVSGdy9Ot7a/QCpXceGM1I/o5AGhElB+G39LaX56A4PXabEkEOGcs9P8pErgMacid2AGfbd/tXnIslZ3HqI163x8rbrngY3MEjYma9cK5fV8HFAidL7y9hEqFgBlSe9ETY0HV7L1dcahHVyYaA8VUyf6sbzfNcBzaaiCO4SmOAkLTx7VWRhwi7aldYztNP/2VfUp3TEYiNp8zfSjGrlPZP1Uu6PiTy/9a/IMMG8jdf+roERf1Cuug+axC+mjJvaQ/1XwnjHUUK1dv1z/ipI8T1dp/Qvww2ldOHK7cG9eIuFKu1u5MM2ng==;width=64;height=64}
```

#### YAML

```yaml
thumbnail:
  name: thumb.png
  mime: image/png
  data: !!binary |
    kgjPONoJQjqQpV7LfJRcxAsEq/7nbT5RsKVSGdy9Ot7a/QCpXceGM1I/o5AGhElB+G39LaX56A4P
    XabEkEOGcs9P8pErgMacid2AGfbd/tXnIslZ3HqI163x8rbrngY3MEjYma9cK5fV8HFAidL7y9hE
    qFgBlSe9ETY0HV7L1dcahHVyYaA8VUyf6sbzfNcBzaaiCO4SmOAkLTx7VWRhwi7aldYztNP/2VfU
    p3TEYiNp8zfSjGrlPZP1Uu6PiTy/9a/IMMG8jdf+roERf1Cuug+axC+mjJvaQ/1XwnjHUUK1dv1z
    /ipI8T1dp/Qvww2ldOHK7cG9eIuFKu1u5MM2ng==
  width: 64
  height: 64
```

#### MsgPack-b64

```text
gal0aHVtYm5haWyFpG5hbWWpdGh1bWIucG5npG1pbWWpaW1hZ2UvcG5npGRhdGHFAQCSCM842glCOpClXst8lFzECwSr/udtPlGwpVIZ3L063tr9AKldx4YzUj+jkAaESUH4bf0tpfnoDg9dpsSQQ4Zyz0/ykSuAxpyJ3YAZ9t3+1eciyVnceojXrfHytuueBjcwSNiZr1wrl9XwcUCJ0vvL2ESoWAGVJ70RNjQdXsvV1xqEdXJhoDxVTJ/qxvN81wHNpqII7hKY4CQtPHtVZGHCLtqV1jO00//ZV9SndMRiI2nzN9KMauU9k/VS7o+JPL/1r8gwwbyN1/6ugRF/UK66D5rEL6aMm9pD/VfCeMdRQrV2/XP+KkjxPV2n9C/DDaV04crtwb14i4Uq7W7kwzaepXdpZHRoQKZoZWlnaHRA
```

#### XML

```xml
<root><thumbnail><name>thumb.png</name><mime>image/png</mime><data>b'\x92\x08\xcf8\xda\tB:\x90\xa5^\xcb|\x94\\\xc4\x0b\x04\xab\xfe\xe7m&gt;Q\xb0\xa5R\x19\xdc\xbd:\xde\xda\xfd\x00\xa9]\xc7\x863R?\xa3\x90\x06\x84IA\xf8m\xfd-\xa5\xf9\xe8\x0e\x0f]\xa6\xc4\x90C\x86r\xcfO\xf2\x91+\x80\xc6\x9c\x89\xdd\x80\x19\xf6\xdd\xfe\xd5\xe7"\xc9Y\xdcz\x88\xd7\xad\xf1\xf2\xb6\xeb\x9e\x0670H\xd8\x99\xaf\\+\x97\xd5\xf0q@\x89\xd2\xfb\xcb\xd8D\xa8X\x01\x95\'\xbd\x1164\x1d^\xcb\xd5\xd7\x1a\x84ura\xa0&lt;UL\x9f\xea\xc6\xf3|\xd7\x01\xcd\xa6\xa2\x08\xee\x12\x98\xe0$-&lt;{Uda\xc2.\xda\x95\xd63\xb4\xd3\xff\xd9W\xd4\xa7t\xc4b#i\xf37\xd2\x8cj\xe5=\x93\xf5R\xee\x8f\x89&lt;\xbf\xf5\xaf\xc80\xc1\xbc\x8d\xd7\xfe\xae\x81\x11\x7fP\xae\xba\x0f\x9a\xc4/\xa6\x8c\x9b\xdaC\xfdW\xc2x\xc7QB\xb5v\xfds\xfe*H\xf1=]\xa7\xf4/\xc3\r\xa5t\xe1\xca\xed\xc1\xbdx\x8b\x85*\xedn\xe4\xc36\x9e'</data><width>64</width><height>64</height></thumbnail></root>
```

---

## Note metodologiche

- **Lossless** = `decode(encode(obj)) == obj` su tipi Python nativi. XML manca di decoder (encoder best-effort); CSV non rappresenta strutture annidate; MsgPack è binario, qui base64-encoded per il canale testuale tipico LLM.
- **Δ vs JSON-min** = riduzione percentuale token rispetto a JSON minified. Positivo = ADP risparmia token.
- **Tempi enc/dec**: misurati con `time.perf_counter_ns()`, ripetuti 200 volte, mediana. Riflettono CPU-only, in-memory: nessun I/O, nessuna rete. Significativi solo per confronti relativi sulla stessa macchina.
- **Tempi di trasferimento di rete**: proporzionali ai bytes. Esempio: su un canale a 1 Mbit/s reale, 1 KB ≈ 8 ms. La colonna `Bytes` è il proxy diretto del costo trasferimento.
- **IT vs EN**: i tokenizer LLM hanno vocabolari prevalentemente inglesi. Lo stesso contenuto in italiano genera tipicamente 15-40% token in più rispetto all'inglese. ADP mantiene il vantaggio strutturale (riduzione overhead di sintassi) indipendentemente dalla lingua.
