# Dynamic LUT — Pre-warm da corpus (Plan 3 di 6, Est. 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implementare `ADPSession.warmup()` per pre-popolare la dynamic LUT da conversazioni passate (lista in-memory di payload o file newline-delimited), eliminando il "cold start weak" mostrato dal benchmark precedente.

**Architecture:** itera sui messaggi sorgente (decoded dict, raw ADP string, o file con ADP per riga), conta occorrenze cumulative di chiavi/valori string, applica soglia K e cost-benefit char-based, aggiunge entry rispettando `max_entries` di sessione. Usa `apply_lut_updates` esistente per gestire messaggi che contengono prefissi di sessione precedente.

**Tech Stack:** Python 3.11+, stdlib (`pathlib`), `pytest`. Nessuna dipendenza nuova.

---

## Scope

**Incluso:**
- `ADPSession.warmup(messages, max_entries=None) -> int` che accetta:
  - `Iterable[dict]`: payload già decodificati (path veloce)
  - `Iterable[str]`: raw ADP string (decoded internamente)
  - `Path`: file con un msg ADP per riga
- Algoritmo cumulative-count + soglia K + cost-benefit char-based
- Rispetto `max_entries` di sessione + parametro override (`min` dei due)
- Idempotenza: ri-eseguire stesso input non crea duplicati
- 4 test categorie
- Update benchmark con variante "warm start"

**Escluso:**
- Tokenizer-aware cost (Est. 1, plan separato)
- Auto-promozione TPD durante warmup (Est. 3, plan separato)
- Detection automatica del formato (l'utente passa dict/str/Path esplicito)

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `src/adp/session.py` | modifica | aggiungi metodo `warmup()` a `ADPSession` |
| `tests/test_warmup.py` | crea | 4 test categorie (test_warmup_*) |
| `benchmarks/bench_dynamic_lut.py` | modifica | aggiungi variante "warm start" |

---

## Task 1 — Scaffolding `warmup()` + test smoke con input dict

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_warmup.py`

- [ ] **Step 1: Crea `tests/test_warmup.py` con i primi 2 test**

```python
"""Test suite per ADPSession.warmup() (pre-warm da corpus)."""
from __future__ import annotations

from pathlib import Path

import pytest

from adp.session import ADPSession


def test_warmup_empty_returns_zero():
    s = ADPSession(path=None, auto_save=False)
    added = s.warmup([])
    assert added == 0
    assert s._entries == {}


def test_warmup_from_dict_list_populates_lut():
    """Lista di payload pre-decodificati: chiavi/valori ricorrenti
    (>= K=2 occorrenze cumulative) vanno in dynamic LUT."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    messages = [
        {"user": {"id": 1, "role": "administrator", "dept": "engineering"}},
        {"user": {"id": 2, "role": "administrator", "dept": "engineering"}},
        {"user": {"id": 3, "role": "developer", "dept": "engineering"}},
    ]
    added = s.warmup(messages)
    # Almeno una entry aggiunta (administrator, engineering compaiono >= 2 volte)
    assert added > 0
    # "administrator" appare 2 volte → candidato sopra soglia
    assert "administrator" in s._inv
    # "engineering" appare 3 volte → sicuramente in LUT
    assert "engineering" in s._inv
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_warmup.py -v
```

Expected: 2 FAIL (`warmup` non esiste in `ADPSession`).

- [ ] **Step 3: Implementare `warmup()` in `src/adp/session.py`**

Aggiungere il metodo dentro la classe `ADPSession`, dopo `encode_full()` e prima di `_encode_full_with_lut()`:

```python
    def warmup(self, messages, max_entries: int | None = None) -> int:
        """Pre-popola la dynamic LUT da conversazioni passate.

        Args:
            messages: corpus di partenza. Tre formati accettati:
                - Iterable[dict]: payload già decodificati (path veloce)
                - Iterable[str]: raw ADP strings (decodificati internamente,
                  prefissi di sessione `_lut_add`/`_lut_reset`/`_base`/`_diff`
                  ignorati via `apply_lut_updates`)
                - Path: file newline-delimited (una riga = un raw ADP msg)
            max_entries: cap effettivo per questo warmup (default: usa
                il `max_entries` della sessione). Il numero di entry totali
                non supera mai `min(session.max_entries, max_entries)`.

        Returns:
            Numero di nuove entry aggiunte alla dynamic LUT.

        Algoritmo:
            1. Itera sui messaggi (decoding implicito per str/Path).
            2. Conta occorrenze cumulative di chiavi dict e valori string scalari.
            3. Per ogni candidato con count >= k_threshold, non in static LUT,
               non già in dynamic LUT, e con cost-benefit char-based positivo:
               aggiunge un'entry tramite `_add_entry`.
            4. Rispetta `min(self._max_entries, max_entries)` come cap globale.
            5. Idempotente: ri-eseguire stesso input non duplica entry
               (i candidati già presenti vengono saltati).
        """
        if isinstance(messages, Path):
            text = messages.read_text(encoding="utf-8")
            messages = [line.strip() for line in text.splitlines() if line.strip()]

        cumulative_counts: dict[str, int] = {}
        for msg in messages:
            if isinstance(msg, str):
                # Rimuovi eventuali prefissi sessione, poi decoda payload
                payload_str, _ = apply_lut_updates(msg, {})
                if not payload_str:
                    continue
                try:
                    obj = adp.decode(payload_str,
                                     key_lut=self._static_lut or None)
                except adp.ADPParseError:
                    continue  # msg malformato, skippa
            else:
                obj = msg
            self._count_candidates(obj, cumulative_counts)

        # Cap effettivo
        if max_entries is None:
            cap = self._max_entries
        else:
            cap = min(self._max_entries, max_entries)

        # Aggiungi candidati ordinati per occorrenze (più frequenti prima)
        added = 0
        sorted_candidates = sorted(
            cumulative_counts.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )
        for fullname, count in sorted_candidates:
            if len(self._entries) >= cap:
                break
            if count < self._k_threshold:
                continue
            if fullname in self._static_lut:
                continue
            if fullname in self._inv:
                continue
            # Cost-benefit cumulative: header pagato 1 volta, saving su tutte
            # le N occorrenze future (qui usiamo count come proxy)
            next_id = self._next_alias_id
            alias_len = len(f"_{next_id}")
            header_entry_len = alias_len + 1 + len(fullname) + 1
            saving = count * len(fullname) - count * alias_len - header_entry_len
            if saving > 0:
                self._add_entry(fullname)
                added += 1
        return added
```

NOTA: il metodo usa `apply_lut_updates` (funzione module-level già importata in `session.py` perché definita lì). Non serve import aggiuntivo.

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_warmup.py -v
```

Expected: 2 PASSED.

Full suite no regression:
```bash
uv run pytest -q
```
Expected: 190 PASSED (188 baseline + 2 nuovi).

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_warmup.py
git commit -m "feat(session): warmup() per pre-popolare dynamic LUT da dict list"
```

---

## Task 2 — Input come str (raw ADP) + da Path file

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_warmup.py`

- [ ] **Step 1: Test failing per input str + Path**

Aggiungere a `tests/test_warmup.py`:

```python
import adp


def test_warmup_from_str_list_decodes_and_counts():
    """Lista di raw ADP strings: decoded internamente, conteggio identico."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    raw_msgs = [
        adp.encode({"user": {"role": "administrator", "dept": "engineering"}}),
        adp.encode({"user": {"role": "administrator", "dept": "engineering"}}),
        adp.encode({"user": {"role": "developer", "dept": "engineering"}}),
    ]
    added = s.warmup(raw_msgs)
    assert added > 0
    assert "administrator" in s._inv
    assert "engineering" in s._inv


def test_warmup_skips_malformed_str():
    """Messaggi malformati non bloccano il warmup."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    raw_msgs = [
        adp.encode({"user": {"role": "administrator"}}),
        "this is not valid ADP @@@",
        adp.encode({"user": {"role": "administrator"}}),
    ]
    added = s.warmup(raw_msgs)
    # I 2 msg validi danno administrator x2 → candidato sopra soglia
    assert "administrator" in s._inv


def test_warmup_from_path_file(tmp_path: Path):
    """Path a file newline-delimited: una riga = un raw ADP msg."""
    log_file = tmp_path / "session.ndjson"
    lines = [
        adp.encode({"user": {"role": "administrator", "dept": "engineering"}}),
        "",  # riga vuota va skippata
        adp.encode({"user": {"role": "administrator", "dept": "engineering"}}),
        adp.encode({"user": {"role": "developer", "dept": "engineering"}}),
    ]
    log_file.write_text("\n".join(lines), encoding="utf-8")

    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    added = s.warmup(log_file)
    assert added > 0
    assert "administrator" in s._inv
    assert "engineering" in s._inv


def test_warmup_handles_session_prefixes():
    """Messaggi con prefissi _lut_add (da sessione precedente) vengono
    spogliati via apply_lut_updates prima del decode."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    # Simula msg che contiene un prefisso _lut_add da una sessione passata
    raw_with_prefix = (
        "_lut_add={_0=role;_1=administrator};"
        "user={_0=_1;dept=engineering}"
    )
    raw_clean = adp.encode({"user": {"role": "administrator", "dept": "engineering"}})
    s.warmup([raw_with_prefix, raw_clean])
    # "engineering" appare 2 volte cumulative (1 in cleaned, 1 in raw)
    assert "engineering" in s._inv
```

- [ ] **Step 2: Eseguire test**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_warmup.py -v
```

Expected: 6 PASSED (2 esistenti + 4 nuovi). L'implementazione del Task 1 già supporta str e Path quindi questi test dovrebbero passare al primo run.

Se `test_warmup_handles_session_prefixes` fallisce: probabile che `apply_lut_updates` non gestisca correttamente la situazione. Investigare.

- [ ] **Step 3: Commit**

```bash
git add tests/test_warmup.py
git commit -m "test(warmup): input come str, Path e msg con session prefixes"
```

---

## Task 3 — `max_entries` cap, idempotenza, sorting per frequenza

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_warmup.py`

- [ ] **Step 1: Test failing per cap + idempotenza + sorting**

Aggiungere a `tests/test_warmup.py`:

```python
def test_warmup_respects_session_max_entries():
    """Warmup non aggiunge mai più di session.max_entries."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2, max_entries=2)
    # 5 strings distinte sopra threshold
    long_words = ["administrator", "engineering", "developer", "operations", "marketing"]
    messages = []
    for w in long_words:
        messages.append({"role": w})
        messages.append({"role": w})  # ripeti per K=2
    added = s.warmup(messages)
    # Cap = 2: solo 2 entry massimo
    assert len(s._entries) <= 2
    assert added <= 2


def test_warmup_respects_max_entries_override():
    """Parametro max_entries usa min(session, override)."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2, max_entries=10)
    long_words = ["administrator", "engineering", "developer", "operations", "marketing"]
    messages = []
    for w in long_words:
        messages.append({"role": w})
        messages.append({"role": w})
    added = s.warmup(messages, max_entries=3)
    assert len(s._entries) <= 3
    assert added <= 3


def test_warmup_prefers_more_frequent_candidates():
    """A parità di altre condizioni, candidati più frequenti vengono prima."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2, max_entries=2)
    messages = [
        {"role": "engineering"},  # 5 volte
        {"role": "engineering"},
        {"role": "engineering"},
        {"role": "engineering"},
        {"role": "engineering"},
        {"role": "administrator"},  # 3 volte
        {"role": "administrator"},
        {"role": "administrator"},
        {"role": "developer"},  # 2 volte (al limite di soglia)
        {"role": "developer"},
    ]
    s.warmup(messages)
    assert len(s._entries) == 2
    # Le due più frequenti devono essere in LUT
    assert "engineering" in s._inv
    assert "administrator" in s._inv
    # La meno frequente non c'è (escluso per cap)
    assert "developer" not in s._inv


def test_warmup_idempotent_no_duplicates():
    """Ri-eseguire warmup con stesso input non duplica entry."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2)
    messages = [
        {"role": "administrator", "dept": "engineering"},
        {"role": "administrator", "dept": "engineering"},
    ]
    first_added = s.warmup(messages)
    entries_after_first = dict(s._entries)
    second_added = s.warmup(messages)
    # Nessuna entry nuova al secondo run
    assert second_added == 0
    assert s._entries == entries_after_first
```

- [ ] **Step 2: Eseguire test**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_warmup.py -v
```

Expected: 10 PASSED (6 esistenti + 4 nuovi).

- [ ] **Step 3: Commit**

```bash
git add tests/test_warmup.py
git commit -m "test(warmup): cap max_entries, sorting per frequenza, idempotenza"
```

---

## Task 4 — Test integrazione: warmup + encode con LUT pre-popolata

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_warmup.py`

- [ ] **Step 1: Test di integrazione**

Aggiungere a `tests/test_warmup.py`:

```python
def test_warmup_then_encode_uses_prewarmed_entries():
    """Dopo warmup, encode di un nuovo msg usa subito gli alias pre-popolati
    senza dover aspettare K occorrenze nel msg corrente."""
    sender = ADPSession(path=None, auto_save=False, k_threshold=2)
    # Pre-warm da log
    past_messages = [
        {"user": {"role": "administrator", "dept": "engineering"}},
        {"user": {"role": "administrator", "dept": "engineering"}},
    ]
    sender.warmup(past_messages)
    pre_warmed = set(sender._inv.keys())
    assert "administrator" in pre_warmed
    assert "engineering" in pre_warmed

    # Nuovo msg con UNA sola occorrenza di "administrator" e "engineering"
    # (sotto K=2 nel msg corrente, ma già in LUT dal warmup → sostituito)
    msg = sender.encode({"new_user": {"role": "administrator",
                                       "dept": "engineering"}})
    # I valori sono stati sostituiti con alias
    assert "administrator" not in msg
    assert "engineering" not in msg
    # Almeno un alias _N presente
    import re
    assert re.search(r"_\d+", msg) is not None


def test_warmup_persistence_round_trip(tmp_path: Path):
    """Save dopo warmup, reload, le entry sono persistite."""
    path = tmp_path / "session.json"
    s1 = ADPSession(path=path, auto_save=False, k_threshold=2)
    s1.warmup([
        {"role": "administrator", "dept": "engineering"},
        {"role": "administrator", "dept": "engineering"},
    ])
    s1.save()
    entries_before = dict(s1._entries)
    next_id_before = s1._next_alias_id

    s2 = ADPSession(path=path, auto_save=False)
    assert s2._entries == entries_before
    assert s2._next_alias_id == next_id_before
```

- [ ] **Step 2: Eseguire test**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_warmup.py -v
```

Expected: 12 PASSED.

Full suite:
```bash
uv run pytest -q
```
Expected: 200 PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/test_warmup.py
git commit -m "test(warmup): integrazione warmup + encode + persistenza"
```

---

## Task 5 — Update benchmark con variante "warm start"

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/bench_dynamic_lut.py`

- [ ] **Step 1: Aggiungere variante warm-start al benchmark**

Aprire `benchmarks/bench_dynamic_lut.py`. Trovare la sezione dove vengono calcolate le metriche `dyn_diff_tokens` e `full_stack_tokens`. Aggiungere DOPO la sezione `full_stack_tokens` e PRIMA della stampa, una nuova configurazione "warm start":

```python
    # Warm start: pre-warm da prima metà della conversazione, misura solo seconda metà
    msgs_warmup = msgs[: len(msgs) // 2]
    msgs_measure = msgs[len(msgs) // 2 :]

    a_warm = adp.ADPSession(path=None, auto_save=False,
                             static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    b_warm = adp.ADPSession(path=None, auto_save=False,
                             static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    # Pre-warm: entrambe le sessions imparano dal corpus di prima metà
    a_warm.warmup(msgs_warmup)
    b_warm.warmup(msgs_warmup)
    warm_start_tokens = 0
    for i, m in enumerate(msgs_measure):
        sender, receiver = (a_warm, b_warm) if i % 2 == 0 else (b_warm, a_warm)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (warm start) msg {i}"
        warm_start_tokens += _tok(encoded)

    # Equivalente "cold" sulla seconda metà per confronto onesto
    a_cold_half = adp.ADPSession(path=None, auto_save=False,
                                   static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    b_cold_half = adp.ADPSession(path=None, auto_save=False,
                                   static_lut=adp.DEFAULT_AGENT_LUT, enable_diff=True)
    cold_half_tokens = 0
    for i, m in enumerate(msgs_measure):
        sender, receiver = (a_cold_half, b_cold_half) if i % 2 == 0 else (b_cold_half, a_cold_half)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (cold half) msg {i}"
        cold_half_tokens += _tok(encoded)
```

E nella sezione di stampa dei risultati (la prima tabella), aggiungere DOPO la riga `full_stack_tokens`:

```python
    print(f"{'-'*70}")
    print(f"Sotto-benchmark seconda metà (10 msg) — warm vs cold:")
    print(f"{'-'*70}")
    half_baseline = sum(_tok(encode_json_min(m)) for m in msgs_measure)
    print(f"{'JSON-min (10 msg)':<35} {fmt(half_baseline, half_baseline)}")
    print(f"{'full stack cold (10 msg)':<35} {fmt(cold_half_tokens, half_baseline)}")
    print(f"{'full stack WARM (10 msg)':<35} {fmt(warm_start_tokens, half_baseline)}")
    print(f"{'-'*70}")
    print(f"Δ warm vs cold sulla seconda metà:")
    cold_delta = (cold_half_tokens - warm_start_tokens) / cold_half_tokens * 100
    print(f"  warm risparmia {cold_delta:.1f}% dei token vs cold start")
```

- [ ] **Step 2: Eseguire benchmark**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
```

REPORTA L'OUTPUT COMPLETO. In particolare, vogliamo vedere:
- `warm_start_tokens` < `cold_half_tokens`?
- Quanto risparmia warm vs cold?

Aspettativa: warm start riduce i token sui primi msg della seconda metà (quelli dove la LUT cold-start sarebbe ancora vuota). Stima: 5-15% di risparmio extra.

Se NON migliora: dimostra che la dyn LUT cold-start era già near-ottimale grazie a static + diff. Warmup vale solo in contesti dove static non copre.

- [ ] **Step 3: Commit**

```bash
git add benchmarks/bench_dynamic_lut.py
git commit -m "bench(warmup): variante warm-start (prima metà → pre-warm, seconda → misurata)"
```

---

## Self-review (post-stesura del plan)

**1. Spec coverage (Est. 4):**

| Spec requirement | Task |
|---|---|
| API `warmup(messages, max_entries=None)` | Task 1 |
| Iterable[dict] input | Task 1 |
| Iterable[str] input | Task 2 |
| Path input (newline-delimited) | Task 2 |
| Algoritmo cumulative count + threshold | Task 1 |
| Rispetto `max_entries` di sessione | Task 3 |
| Override `max_entries` parametro | Task 3 |
| Idempotenza | Task 3 |
| Test categorie 24-27 | distribuiti Task 1-4 |
| Benchmark con warm-start | Task 5 |

Tutto coperto.

**2. Placeholder scan:** nessun TBD/TODO; tutti gli step contengono codice o comandi concreti.

**3. Type consistency:**

- `warmup(messages: Iterable[dict] | Iterable[str] | Path, max_entries: int | None = None) -> int`
- Ritorna numero entry aggiunte (`int`)
- Riusa `_count_candidates`, `_add_entry`, `_static_lut`, `_inv`, `_entries`, `_max_entries`, `_k_threshold` già definiti
- Riusa `apply_lut_updates` (funzione module-level già esportata)

Nessuna divergenza.

## Note per Plan futuri

Dopo questo plan:
- Re-benchmark per validare il valore aggiunto del warmup
- Procedere con Est. 1 (tokenizer-aware), Est. 2 (capability), Est. 3 (TPD promotion) se warmup ha mostrato valore
- Considerare un parametro `cost_estimator` opzionale a `warmup` per usare tokenizer reale (cross-link con Est. 1)
