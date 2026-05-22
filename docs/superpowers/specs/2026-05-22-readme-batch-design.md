# Spec — Batch di update al README

**Data:** 2026-05-22
**Stato:** approvato (in attesa di plan)
**Scope:** modifica a `README.md` + asset visuale + script di generazione

## Obiettivo

Migliorare la qualità di onboarding del README, in particolare:

- segnalare immediatamente versione, licenza e compatibilità Python tramite
  badge;
- offrire al lettore una sintesi quantitativa del risparmio di token già
  nelle prime righe, prima dell'indice;
- aggiungere uno screenshot del live viewer SSE, oggi descritto solo a
  parole;
- correggere eventuali ancore TOC rotte dovute a caratteri accentati
  italiani.

Tutto il lavoro è confinato al README e a un piccolo asset/script. Nessuna
modifica al codice della libreria.

## Sub-task

Quattro modifiche indipendenti raggruppate in un unico batch perché
piccole e tutte localizzate sullo stesso file (`README.md`).

### A — Badge in testa

Subito sotto il titolo `# ADP — Adriano Dal Pastro format`, prima del
paragrafo introduttivo, aggiungere una riga con due badge shields.io
**statici** (non collegati a CI/PyPI che oggi non esistono):

```markdown
![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
```

Vincoli:

- usare URL `img.shields.io` con sintassi `/badge/`, niente endpoint
  dinamici (`pypi`, `github/workflow`) finché l'infra non esiste;
- niente badge "tests passing" o "version on PyPI" — verranno aggiunti
  quando i task I (CI) e l'eventuale pubblicazione PyPI saranno completi.

### B — Screenshot del live viewer SSE

Nella sezione esistente `### Pagina HTML dinamica (live viewer
append-only)`, sotto il primo paragrafo descrittivo, inserire una
immagine:

```markdown
![Live viewer SSE](docs/img/live-viewer.png)
```

Asset:

- file: `docs/img/live-viewer.png`
- contenuto: schermata del browser su `http://localhost:8000` con 3-4
  record ADP demo già accodati, indicatore "live" visibile, contatore
  record nell'header.

Generazione **riproducibile** tramite uno script committato:

- percorso: `scripts/screenshot_live_viewer.py`
- comportamento: avvia `uv run adp serve --port 8765` in background,
  emette 3-4 record ADP di esempio sullo stdin del processo, attende il
  rendering, cattura uno screenshot con Chromium headless, salva su
  `docs/img/live-viewer.png`, termina il server.
- dipendenze ammesse: stdlib + `subprocess` + binario `chromium` o
  `chromium-browser` già presente sul sistema. Niente nuove dipendenze
  Python permanenti — lo script è uno strumento di sviluppo.
- lo script deve essere idempotente (rieseguibile genera lo stesso PNG
  modulo timestamp).

Se Chromium headless non è disponibile sulla macchina di chi esegue lo
script, lo script stampa un messaggio chiaro e termina con exit code !=0
invece di tentare fallback fragili.

### C — Verifica ancore TOC

L'indice corrente contiene voci con caratteri accentati:

- `Perché ADP` → ancora attesa `#perché-adp`
- `Integrità — sign / verify` → ancora attesa `#integrità--sign--verify`

GitHub mantiene gli accenti negli anchor, ma converte spazi multipli in
trattini multipli e rimuove caratteri non alfanumerici (eccetto `-` e
`_`).

Lavoro:

- scorrere ogni voce del TOC corrente (15 voci);
- per ognuna, verificare che cliccando dal TOC si arrivi alla sezione
  corretta. La verifica si fa renderizzando il README su GitHub oppure
  con un renderer markdown locale che simula la stessa logica di
  `slugify` di GitHub (eccezione: trattini `—` e `/` vengono normalizzati
  in modo specifico);
- correggere SOLO le voci rotte, lasciando intatte quelle che
  funzionano. Niente refactoring dell'intero indice.

Risultato atteso: ogni link del TOC porta esattamente alla sezione
corrispondente.

### D — Tabella TL;DR di confronto rapido

Inserire una tabella compatta tra il paragrafo introduttivo (che termina
con "...senza mai introdurre perdita di dati.") e la riga `## Indice`.

Layout:

```markdown
**Quanto risparmia:**

| Payload tipico | JSON-min (tok) | ADP (tok) | Δ |
|---|---:|---:|---:|
| Tabella omogenea (it) | 333 | 164 | **+50,8%** |
| Lista contatti con URL/email | 145 | 94 | **+35,2%** |
| Tabelle con cells annidate | 100 | 75 | **+25,0%** |
```

Vincoli:

- usare numeri **già presenti** nella tabella benchmark più sotto
  (sezione `## Riduzione token misurata`); nessun nuovo dato;
- tre righe esatte, top-3 risparmio per chiarezza;
- nessuna duplicazione testuale lunga: la tabella completa resta dov'è.

## Layout finale (sommario top→bottom)

```
# ADP — Adriano Dal Pastro format
[badge MIT] [badge Python ≥3.11]      ← A

**Formato testuale lossless...**       (paragrafo intro esistente)

ADP (versione 0.2)...                  (paragrafo esistente)

L'obiettivo è ridurre...               (paragrafo esistente)

**Quanto risparmia:**                  ← D
| Payload | JSON | ADP | Δ |
...

## Indice                              (TOC con anchor verificati ← C)
...
## Pagina HTML dinamica
![Live viewer SSE](docs/img/live-viewer.png)  ← B
...
```

## Test plan

1. Render del README su GitHub (oppure preview locale): i due badge
   sono visibili e leggibili.
2. Click su ogni voce del TOC: ognuna porta alla sezione corretta.
3. Lo screenshot `docs/img/live-viewer.png` viene visualizzato all'interno
   della sezione "Pagina HTML dinamica" e mostra effettivamente il viewer
   con record demo.
4. Esecuzione di `python scripts/screenshot_live_viewer.py` su una
   macchina con Chromium installato rigenera il PNG senza errori.
5. La tabella TL;DR contiene esattamente i numeri della tabella
   completa più sotto (no divergenze).

## Out of scope

- Pubblicazione PyPI.
- Setup CI GitHub Actions (item I del backlog, spec separata).
- Badge dinamici (versione, build status, coverage) — rinviati a quando
  l'infra esiste.
- GIF animata del live viewer (decisa contro nella fase brainstorming).
- Riscrittura del TOC o riorganizzazione delle sezioni.
- Traduzione del README in altre lingue.

## Dipendenze e rischi

- Chromium headless richiesto solo per chi rigenera lo screenshot;
  utenti finali e CI non sono impattati.
- I badge shields.io sono asset esterni: se shields.io è offline al
  momento del rendering, l'utente vede il testo alt. Accettabile.
- Le ancore TOC dipendono dall'algoritmo di slugify di GitHub. Test
  manuale obbligatorio: nessuna verifica automatica.
