# Plan — Batch update README

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** applicare le quattro migliorie al README descritte nella spec `docs/superpowers/specs/2026-05-22-readme-batch-design.md` (badge, TL;DR, screenshot, fix anchor TOC).

**Architecture:** modifica al solo `README.md` per A/C/D; nuovo script `scripts/screenshot_live_viewer.py` + asset `docs/img/live-viewer.png` per B. Lo script usa `playwright` isolato via `uv run --with playwright` per evitare dipendenze permanenti del progetto e installazioni di sistema.

**Tech Stack:** Markdown + shields.io badge statici; Python 3.11+, `playwright` (chromium headless isolato), `subprocess`.

---

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `README.md` | modifica | aggiunta badge, tabella TL;DR, embed screenshot, fix anchor TOC |
| `docs/img/live-viewer.png` | crea | screenshot del live viewer SSE con record demo |
| `scripts/screenshot_live_viewer.py` | crea | script riproducibile che lancia `adp serve`, emette record demo, cattura PNG |
| `.gitignore` | nessuna modifica | il PNG è committato di proposito |

---

## Task 1 — Verifica e fix delle ancore TOC (C)

**Files:**
- Modify: `README.md:17-33` (TOC) e gli header delle sezioni corrispondenti se necessario.

- [ ] **Step 1: Enumerare le voci TOC e i loro target**

Apri `README.md` e fai una mapping tabella di tutte le voci dell'indice (righe 19-33), per ognuna il link atteso e il testo dell'header puntato:

```
1. Perché ADP                          → #perché-adp                          → ## Perché ADP
2. Installazione                       → #installazione                       → ## Installazione
3. Quickstart                          → #quickstart                          → ## Quickstart
4. Sintassi in pillole                 → #sintassi-in-pillole                 → ## Sintassi in pillole
5. Convertitori                        → #convertitori                        → ## Convertitori
6. Integrazione con agenti AI          → #integrazione-con-agenti-ai          → ## Integrazione con agenti AI
7. Riduzione token misurata            → #riduzione-token-misurata            → ## Riduzione token misurata
8. Esempi a confronto                  → #esempi-a-confronto                  → ## Esempi a confronto
9. Immagini                            → #immagini                            → ## Immagini
10. Usare ADP in Claude Code            → #usare-adp-in-claude-code            → ## Usare ADP in Claude Code
11. Integrità — sign / verify           → #integrità--sign--verify             → ## Integrità — sign / verify
12. Struttura del progetto              → #struttura-del-progetto              → ## Struttura del progetto
13. Sviluppo e test                     → #sviluppo-e-test                     → ## Sviluppo e test
14. Roadmap                             → #roadmap                             → ## Roadmap
15. Licenza                             → #licenza                             → ## Licenza
```

- [ ] **Step 2: Capire la regola slugify di GitHub**

GitHub trasforma gli header così:
- minuscolizzazione (`Perché ADP` → `perché adp`)
- spazi sostituiti da `-` (`perché adp` → `perché-adp`)
- caratteri non alfanumerici (eccetto `-`, `_`, e i caratteri accentati Unicode latini) **rimossi**
- accenti **conservati** (non sono ASCII-fold)
- punteggiatura tipo `—`, `/`, `,`, `.` rimossa; più spazi/punteggiature consecutive producono trattini multipli

Esempio critico: `## Integrità — sign / verify`
- minuscolo: `integrità — sign / verify`
- rimossa `—` e `/`: `integrità  sign  verify` (doppi spazi)
- spazi → trattini: `integrità--sign--verify`

- [ ] **Step 3: Verifica manuale ogni anchor**

Apri il README su GitHub (push temporaneo a un branch oppure usa preview locale `grip` se installato) e clicca ogni voce TOC. Annota le voci che NON portano alla sezione attesa.

Comando di preview locale, se disponibile:
```bash
uvx grip README.md --quiet &
# apri http://localhost:6419
```

Se nessun preview disponibile, eseguire fix proattivamente: il caso più a rischio è la voce #11 (`Integrità — sign / verify`). Confronta con il link `[Integrità — sign / verify](#integrità--sign--verify)` nel TOC — i due trattini doppi devono essere presenti.

- [ ] **Step 4: Fix solo le voci rotte**

Per ogni voce rotta, correggi il link nell'indice (NON cambiare l'header della sezione). Esempio se trovi che `#integrità--sign--verify` non funziona ma `#integrita-sign-verify` sì (improbabile, ma ipotetico):

Edit di `README.md`:
```markdown
- da: [Integrità — sign / verify](#integrità--sign--verify)
- a:  [Integrità — sign / verify](#integrita-sign-verify)
```

Se invece tutto funziona, lascia il file invariato e procedi.

- [ ] **Step 5: Commit (solo se modifiche)**

```bash
git status
# se README.md modificato:
git add README.md
git commit -m "docs(readme): fix ancore TOC rotte"
# altrimenti salta il commit
```

---

## Task 2 — Badge in testa al README (A)

**Files:**
- Modify: `README.md:1-3` (subito dopo `# ADP — Adriano Dal Pastro format`)

- [ ] **Step 1: Verificare URL badge in browser**

Apri questi due URL in un browser e conferma che mostrano badge SVG corretti:

- `https://img.shields.io/badge/license-MIT-blue`
- `https://img.shields.io/badge/python-%E2%89%A53.11-blue`

(`%E2%89%A5` è la URL-encoded del simbolo `≥`.)

- [ ] **Step 2: Edit README.md**

Cerca la riga 1 `# ADP — Adriano Dal Pastro format` e la riga vuota immediatamente sotto. Inserisci una riga di badge tra il titolo e il paragrafo introduttivo:

Old (righe 1-3):
```markdown
# ADP — Adriano Dal Pastro format

**Formato testuale lossless e aggressivamente token-efficient per la comunicazione tra agenti AI.**
```

New:
```markdown
# ADP — Adriano Dal Pastro format

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-blue)

**Formato testuale lossless e aggressivamente token-efficient per la comunicazione tra agenti AI.**
```

- [ ] **Step 3: Verifica rendering**

Stessa preview locale del Task 1 step 3 (`grip` se disponibile). I due badge devono essere visibili come immagini affiancate sotto il titolo.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): aggiunta badge MIT e Python >=3.11"
```

---

## Task 3 — Tabella TL;DR di confronto rapido (D)

**Files:**
- Modify: `README.md` — inserire dopo il paragrafo intro e prima della riga `## Indice` (attualmente riga 17).

- [ ] **Step 1: Verificare i numeri sorgente**

Apri `README.md` alla sezione `## Riduzione token misurata` (righe 277-298). Conferma che le righe seguenti esistono con questi valori esatti:

- `| tabular_it | 333 | 164 | +50,8% |` (riga 288)
- `| contacts_en (URL/email) | 145 | 94 | +35,2% |` (riga 293)
- `| nested_table_en (cells annidate) | 100 | 75 | +25,0% |` (riga 294)

Se uno dei valori è diverso, **usa il valore corrente del file** anziché quello indicato qui (single source of truth: la tabella benchmark esistente).

- [ ] **Step 2: Edit README.md per inserire la tabella TL;DR**

Trova nel file la riga `## Indice` (attorno alla 17, possibilmente spostata di poche righe dopo Task 2). Subito **prima** di quella riga, dopo la riga vuota che segue l'ultimo paragrafo intro (`...senza mai introdurre perdita di dati.`), inserisci:

```markdown
**Quanto risparmia (vs JSON-min, tokenizer cl100k_base):**

| Payload tipico | JSON-min (tok) | ADP (tok) | Δ |
|---|---:|---:|---:|
| Tabella omogenea (it) | 333 | 164 | **+50,8%** |
| Lista contatti con URL/email | 145 | 94 | **+35,2%** |
| Tabelle con cells annidate | 100 | 75 | **+25,0%** |

```

Lascia una riga vuota prima e dopo il blocco.

- [ ] **Step 3: Verifica rendering e coerenza numerica**

```bash
# Conferma che i tre numeri siano identici alla tabella sotto:
grep -E '\| (tabular_it|contacts_en|nested_table_en)' README.md
```

I valori `333|164|+50,8%`, `145|94|+35,2%`, `100|75|+25,0%` devono comparire **sia** nella tabella TL;DR **sia** nella tabella benchmark completa.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): aggiunta tabella TL;DR sopra l'indice"
```

---

## Task 4 — Script screenshot live viewer (B, parte 1: script)

**Files:**
- Create: `scripts/screenshot_live_viewer.py`

- [ ] **Step 1: Creare la directory scripts/ se assente**

```bash
mkdir -p scripts
ls scripts/
```

- [ ] **Step 2: Scrivere lo script**

Scrivi il file `scripts/screenshot_live_viewer.py` con questo contenuto esatto:

```python
#!/usr/bin/env python3
"""Genera lo screenshot del live viewer ADP per il README.

Avvia `adp serve` in background, emette quattro record ADP demo via stdin,
attende il rendering e cattura uno screenshot via Chromium headless gestito
da Playwright (isolato in cache utente, niente install di sistema).

Esecuzione:
    uv run --with playwright python scripts/screenshot_live_viewer.py

Pre-requisito una tantum (scarica il binario Chromium ~150 MB in
~/.cache/ms-playwright/):
    uv run --with playwright python -m playwright install chromium

Output: docs/img/live-viewer.png
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "ERRORE: playwright non disponibile. Esegui con:\n"
        "  uv run --with playwright python scripts/screenshot_live_viewer.py",
        file=sys.stderr,
    )
    sys.exit(1)

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img" / "live-viewer.png"

DEMO_RECORDS = [
    "task=encode;status=ok;input_size=1024;output_size=387;ratio=0.378",
    "agent=planner;step=1;intent=decompose;subtasks=[parse,validate,emit]",
    "users=#id,name,role|1i,alice,admin|2,bob,dev|3,carol,qa",
    "result=success;duration_ms=234;tokens={in=512;out=87}",
]


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    server = subprocess.Popen(
        ["uv", "run", "adp", "serve", "--port", str(PORT)],
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        cwd=str(ROOT),
    )
    try:
        time.sleep(1.2)  # tempo per binding del socket
        assert server.stdin is not None
        for rec in DEMO_RECORDS:
            server.stdin.write(rec + "\n")
            server.stdin.flush()
            time.sleep(0.2)
        time.sleep(0.6)  # buffer per SSE + render

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 900})
                page.goto(URL, wait_until="networkidle", timeout=10_000)
                page.wait_for_selector(".adp-log-entry", timeout=5_000)
                page.wait_for_timeout(800)  # smooth-scroll completion
                page.screenshot(path=str(OUT), full_page=False)
            finally:
                browser.close()
    finally:
        if server.stdin is not None:
            try:
                server.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()

    if not OUT.exists() or OUT.stat().st_size < 1000:
        print(f"ERRORE: screenshot non generato o troppo piccolo ({OUT})",
              file=sys.stderr)
        return 1

    print(f"Screenshot salvato: {OUT} ({OUT.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Rendere lo script eseguibile**

```bash
chmod +x scripts/screenshot_live_viewer.py
ls -l scripts/screenshot_live_viewer.py
```

Expected: il file appare con permessi `-rwxr-xr-x`.

- [ ] **Step 4: Commit dello script (senza eseguirlo ancora)**

```bash
git add scripts/screenshot_live_viewer.py
git commit -m "scripts: aggiunto screenshot_live_viewer.py per il README"
```

---

## Task 5 — Generare il PNG e embedderlo nel README (B, parte 2: asset)

**Files:**
- Create: `docs/img/live-viewer.png`
- Modify: `README.md` (sezione `### Pagina HTML dinamica`, attualmente attorno alla riga 164-186)

- [ ] **Step 1: Installazione one-time di Chromium per Playwright**

```bash
uv run --with playwright python -m playwright install chromium
```

Expected: log di download (~150 MB la prima volta) e messaggio finale di successo. Se già installato, è un no-op rapido.

- [ ] **Step 2: Eseguire lo script**

```bash
uv run --with playwright python scripts/screenshot_live_viewer.py
```

Expected output finale:
```
Screenshot salvato: /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/docs/img/live-viewer.png (NNNN byte)
```

con NNNN > 1000.

- [ ] **Step 3: Verifica visiva del PNG**

```bash
ls -lh docs/img/live-viewer.png
file docs/img/live-viewer.png
```

Expected: file PNG valido, dimensione > 10 KB. Aprilo con un image viewer (es. `xdg-open docs/img/live-viewer.png`) e conferma di vedere:
- header "ADP live stream" e contatore record = 4
- 4 entry con timestamp visibili
- indicatore "live" verde in basso a destra

Se l'output è bianco o vuoto, ri-eseguire lo script — può capitare per timing race del primo run.

- [ ] **Step 4: Edit README.md per embed dell'immagine**

Trova la sezione `### Pagina HTML dinamica (live viewer append-only)`. Identifica il primo paragrafo descrittivo:

```markdown
### Pagina HTML dinamica (live viewer append-only)

Per scenari in cui un agente emette record ADP a flusso continuo (log,
monitoring, output multi-step), il sottocomando `adp serve` avvia un
piccolo server HTTP che apre una **pagina unica** auto-aggiornata via
Server-Sent Events: ogni nuovo record viene renderizzato e accodato in
fondo senza ricaricare la pagina.
```

Subito dopo il blocco bash con l'esempio `my-agent-emitting-adp | uv run adp serve --port 8000` e prima della lista "Caratteristiche:", inserisci:

```markdown
![Live viewer SSE](docs/img/live-viewer.png)

```

Lascia una riga vuota prima e dopo l'immagine.

- [ ] **Step 5: Commit dell'asset + reference**

```bash
git add docs/img/live-viewer.png README.md
git commit -m "docs(readme): aggiunto screenshot del live viewer SSE"
```

---

## Task 6 — Verifica finale e push opzionale

- [ ] **Step 1: Re-render del README e check visivo completo**

Render finale (preview locale o GitHub branch):

```bash
uvx grip README.md --quiet &
# apri http://localhost:6419
```

Checklist visiva:
- [ ] Titolo seguito da DUE badge (MIT, Python ≥3.11) visibili
- [ ] Tabella TL;DR con 3 righe sopra l'indice
- [ ] Indice con 15 voci; ogni link cliccato porta alla sezione corretta
- [ ] Screenshot del live viewer renderizzato dentro la sezione "Pagina HTML dinamica"
- [ ] Tabella benchmark grande più sotto INVARIATA, stessi numeri della TL;DR

- [ ] **Step 2: Confronto numerico TL;DR vs benchmark**

```bash
grep -nE '\b(333|164|50,8|145|94|35,2|100|75|25,0)\b' README.md | head -20
```

Expected: ognuno dei tre numeri-chiave (`333,164,50,8` / `145,94,35,2` / `100,75,25,0`) appare **almeno due volte** (TL;DR + benchmark completo). Nessun valore inconsistente.

- [ ] **Step 3: Verificare gli ultimi commit**

```bash
git log --oneline -7
```

Expected: una sequenza di commit corrispondenti ai Task 1-5 (alcuni potrebbero essere stati saltati se non necessari, es. Task 1 step 5).

- [ ] **Step 4: Stop**

Non eseguire `git push` automaticamente. Comunica all'utente: "Batch README completato in N commit locali, pronto per `git push` quando vuoi."

---

## Self-review (eseguito dopo la stesura del plan)

**Coverage spec:**
- A (badge): Task 2 ✓
- B (screenshot): Task 4 (script) + Task 5 (PNG + embed) ✓
- C (TOC anchors): Task 1 ✓
- D (TL;DR table): Task 3 ✓
- Verifica finale: Task 6 ✓

**Placeholder scan:** nessun TBD/TODO; ogni step contiene codice o comandi concreti.

**Type consistency:** lo script usa `DEMO_RECORDS`, `PORT`, `URL`, `OUT` consistentemente; nessun nome di funzione/metodo divergente.

**Dipendenze esterne:** `playwright` solo via `uv run --with` (non aggiunge dipendenze permanenti al progetto); `grip` opzionale per preview locale, non bloccante.
