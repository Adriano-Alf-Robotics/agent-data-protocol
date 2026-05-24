# Dynamic LUT — Tokenizer-aware cost estimation (Plan 4 di 6, Est. 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** sostituire la stima cost-benefit char-based di `ADPSession` con conteggio token reale (via `tiktoken`), permettendo decisioni più precise su quali entry promuovere nella dynamic LUT.

**Architecture:** nuovo modulo `src/adp/cost.py` con classe `TokenizerCostEstimator` che incapsula l'encoder tiktoken. `ADPSession` accetta un parametro opzionale `cost_estimator`; se passato, `_select_candidates` e `warmup` lo usano al posto di char-count. Fallback automatico a char-count se tiktoken non installato. Tiktoken come optional extra `pip install adp[tokenizer]`.

**Tech Stack:** Python 3.11+, `tiktoken>=0.7` (optional extra), stdlib, pytest.

---

## Scope

**Incluso:**
- `src/adp/cost.py`: modulo standalone
  - Funzione `estimate_cost(text, tokenizer)` — wrapper diretto
  - Classe `TokenizerCostEstimator(tokenizer="cl100k_base")` con metodo `saving_for_entry(alias, fullname, count) -> int`
  - Gestione `ImportError` per tiktoken assente (fallback a `len(text) // 4`)
- Integrazione `ADPSession`: nuovo param `cost_estimator: TokenizerCostEstimator | None = None`
  - `_select_candidates` usa estimator se presente, altrimenti char-count (default backward-compatible)
  - `warmup` stessa logica
- Export di `TokenizerCostEstimator` da `adp.__init__`
- 5 test categorie (3 spec + 2 integrazione)
- `pyproject.toml`: gruppo optional `[tokenizer]` con `tiktoken>=0.7`

**Escluso:**
- Caching dei conteggi token (premature optimization)
- Multi-tokenizer comparison (sceglie solo cl100k_base default)
- Auto-detection tokenizer da modello (es. "claude-opus" → cl100k_base)
- Tokenizer-aware decisioni anche per diff encoding (separate scope: il diff è già un win netto)

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `src/adp/cost.py` | crea | `TokenizerCostEstimator` + `estimate_cost` con fallback |
| `src/adp/session.py` | modifica | param `cost_estimator`, `_select_candidates` e `warmup` lo usano |
| `src/adp/__init__.py` | modifica | esporta `TokenizerCostEstimator`, `estimate_cost` |
| `tests/test_cost.py` | crea | 5 test categorie (test_cost_*) |
| `pyproject.toml` | modifica | aggiungi optional extra `[tokenizer] = ["tiktoken>=0.7"]` |
| `benchmarks/bench_dynamic_lut.py` | modifica | aggiungi variante "full stack + tokenizer-aware" |

---

## Task 1 — Modulo `cost.py` con `estimate_cost` + fallback

**Files:**
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/cost.py`
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_cost.py`

- [ ] **Step 1: Crea `tests/test_cost.py`**

```python
"""Test suite per adp.cost (tokenizer-aware cost estimation)."""
from __future__ import annotations

import pytest

from adp.cost import estimate_cost


def test_estimate_cost_returns_int():
    """estimate_cost ritorna sempre un int positivo per stringa non vuota."""
    n = estimate_cost("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_estimate_cost_empty_string_is_zero():
    assert estimate_cost("") == 0


def test_estimate_cost_consistent_for_same_input():
    """Stesso input → stesso conteggio (deterministico)."""
    s = "administrator engineering operations"
    assert estimate_cost(s) == estimate_cost(s)


def test_estimate_cost_longer_text_costs_more():
    """Testo più lungo → più token (in pratica monotono)."""
    short = estimate_cost("a")
    long = estimate_cost("administrator engineering operations marketing")
    assert long > short
```

- [ ] **Step 2: Run failing**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_cost.py -v
```

Expected: 4 FAIL (modulo `adp.cost` non esiste).

- [ ] **Step 3: Crea `src/adp/cost.py`**

```python
"""Tokenizer-aware cost estimation per ADPSession.

Offre conteggio token reale (via tiktoken) per decisioni cost-benefit più
precise rispetto al char-count default. Fallback automatico a `len(text) // 4`
se tiktoken non è installato.

Uso:
    from adp.cost import TokenizerCostEstimator
    est = TokenizerCostEstimator(tokenizer="cl100k_base")
    n_tok = est.estimate("administrator")  # conteggio token reale

    # Integrazione con ADPSession:
    session = adp.ADPSession(cost_estimator=est)

Dipendenza opzionale: tiktoken>=0.7 via `pip install adp[tokenizer]`.
"""
from __future__ import annotations

from typing import Any

try:
    import tiktoken as _tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _tiktoken = None
    _TIKTOKEN_AVAILABLE = False


_ENCODER_CACHE: dict[str, Any] = {}


def _get_encoder(tokenizer: str):
    """Lazy-cache di tiktoken encoders. None se tiktoken non installato."""
    if not _TIKTOKEN_AVAILABLE:
        return None
    if tokenizer not in _ENCODER_CACHE:
        _ENCODER_CACHE[tokenizer] = _tiktoken.get_encoding(tokenizer)
    return _ENCODER_CACHE[tokenizer]


def estimate_cost(text: str, tokenizer: str = "cl100k_base") -> int:
    """Conta i token che `text` produce nel tokenizer indicato.

    Se tiktoken non è installato: fallback a `len(text) // 4`
    (approssimazione comunemente accettata: ~4 char per token su testo EN).

    Empty string → 0.
    """
    if not text:
        return 0
    enc = _get_encoder(tokenizer)
    if enc is None:
        # Fallback char-based: ~4 char per token medio
        return max(1, len(text) // 4)
    return len(enc.encode(text))


class TokenizerCostEstimator:
    """Cost estimator basato su tiktoken (o fallback char-count).

    Espone `estimate(text)` per conteggio diretto e `saving_for_entry`
    per valutare se promuovere un entry in dynamic LUT vale il costo
    del header.
    """

    def __init__(self, tokenizer: str = "cl100k_base"):
        self._tokenizer = tokenizer
        # Pre-warm encoder per evitare latenza al primo uso
        _get_encoder(tokenizer)

    @property
    def tokenizer(self) -> str:
        return self._tokenizer

    @property
    def is_tiktoken_available(self) -> bool:
        """True se tiktoken è installato (cost preciso), False se fallback."""
        return _TIKTOKEN_AVAILABLE

    def estimate(self, text: str) -> int:
        return estimate_cost(text, self._tokenizer)

    def saving_for_entry(
        self, alias: str, fullname: str, count: int
    ) -> int:
        """Risparmio in token se promuoviamo fullname→alias per `count` occorrenze.

        saving = count × tok(fullname) − count × tok(alias) − tok(header_entry)

        Header entry format: "alias=fullname;" (ADP map syntax).
        """
        tok_fullname = self.estimate(fullname)
        tok_alias = self.estimate(alias)
        header_entry = f"{alias}={fullname};"
        tok_header = self.estimate(header_entry)
        return count * tok_fullname - count * tok_alias - tok_header
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_cost.py -v
```

Expected: 4 PASSED.

Full suite no regression:
```bash
uv run pytest -q
```
Expected: 204 PASSED (200 baseline + 4 nuovi).

- [ ] **Step 5: Commit**

```bash
git add src/adp/cost.py tests/test_cost.py
git commit -m "feat(cost): estimate_cost + TokenizerCostEstimator con fallback char-count"
```

---

## Task 2 — `TokenizerCostEstimator` class test approfondito

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_cost.py`

- [ ] **Step 1: Test failing per la classe**

Aggiungere a `tests/test_cost.py`:

```python
from adp.cost import TokenizerCostEstimator


def test_estimator_init_default_tokenizer():
    est = TokenizerCostEstimator()
    assert est.tokenizer == "cl100k_base"


def test_estimator_estimate_matches_estimate_cost():
    est = TokenizerCostEstimator("cl100k_base")
    assert est.estimate("administrator") == estimate_cost("administrator", "cl100k_base")


def test_estimator_saving_positive_for_frequent_long_string():
    """administrator (5 char) × 10 occorrenze vs alias _0 → saving positivo."""
    est = TokenizerCostEstimator()
    saving = est.saving_for_entry(alias="_0", fullname="administrator", count=10)
    assert saving > 0


def test_estimator_saving_negative_for_rare_short_string():
    """'ok' × 2 occorrenze: alias _0 + header overhead → saving negativo."""
    est = TokenizerCostEstimator()
    saving = est.saving_for_entry(alias="_0", fullname="ok", count=2)
    assert saving < 0


def test_estimator_tiktoken_availability_flag():
    """is_tiktoken_available riflette se tiktoken è importato."""
    est = TokenizerCostEstimator()
    # In CI/dev abbiamo tiktoken installato come dev dep → True attesa
    # Se False: significa che il fallback char-based è attivo, OK lo stesso
    assert isinstance(est.is_tiktoken_available, bool)
```

- [ ] **Step 2: Run**

```bash
uv run pytest tests/test_cost.py -v
```

Expected: 9 PASSED (4 esistenti + 5 nuovi).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cost.py
git commit -m "test(cost): TokenizerCostEstimator class behaviors"
```

---

## Task 3 — Integrazione `ADPSession`: param `cost_estimator` + `_select_candidates`

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/__init__.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_cost.py`

- [ ] **Step 1: Test failing per integrazione**

Aggiungere a `tests/test_cost.py`:

```python
from adp.session import ADPSession
from adp import TokenizerCostEstimator as TCE_alias  # nuovo export


def test_session_accepts_cost_estimator_param():
    est = TokenizerCostEstimator()
    s = ADPSession(path=None, auto_save=False, cost_estimator=est)
    assert s._cost_estimator is est


def test_session_default_cost_estimator_is_none():
    s = ADPSession(path=None, auto_save=False)
    assert s._cost_estimator is None


def test_session_with_estimator_uses_tokenizer_for_selection():
    """Quando cost_estimator passato, _select_candidates lo usa per saving.
    Caso pratico: una stringa che è 1 token in cl100k ma 6 char (es. 'abcdef')
    può dare saving diverso da char-count."""
    est = TokenizerCostEstimator()
    s = ADPSession(path=None, auto_save=False, k_threshold=2, cost_estimator=est)
    # "administrator" è verbose: sicuramente >1 token, saving positivo
    counts = {"administrator": 5}
    selected = s._select_candidates(counts)
    assert "administrator" in selected
```

- [ ] **Step 2: Run failing**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_cost.py -v -k "session_accepts or session_default or session_with_estimator"
```

Expected: 3 FAIL.

- [ ] **Step 3: Modificare `src/adp/session.py`**

A) Aggiungere import in cima al file (dopo gli altri import):

```python
from adp.cost import TokenizerCostEstimator
```

B) Modificare la firma di `ADPSession.__init__` per aggiungere `cost_estimator`. Trovare la firma e cambiarla in:

```python
    def __init__(
        self,
        path: str | Path | None = DEFAULT_PATH,
        max_entries: int = 256,
        static_lut: dict[str, str] | None = None,
        k_threshold: int = 2,
        auto_save: bool = True,
        enable_diff: bool = True,
        diff_threshold: float = 0.7,
        cost_estimator: TokenizerCostEstimator | None = None,
    ) -> None:
```

C) Nel corpo di `__init__`, dopo `self._diff_threshold = diff_threshold` (sezione diff state) aggiungere:

```python
        self._cost_estimator: TokenizerCostEstimator | None = cost_estimator
```

D) Modificare `_select_candidates` per usare l'estimator quando presente. Trovare il metodo e sostituire INTERAMENTE il corpo con:

```python
    def _select_candidates(self, counts: dict[str, int]) -> dict[str, int]:
        """Filtra candidati: soglia K, non in static LUT, saving non-negativo (break-even incluso).

        Se cost_estimator passato in __init__: usa conteggio token reale.
        Altrimenti: fallback a char-count approssimativo.
        """
        selected: dict[str, int] = {}
        next_id = self._next_alias_id
        for fullname, count in counts.items():
            if count < self._k_threshold:
                continue
            if fullname in self._static_lut:
                continue
            if fullname in self._inv:
                continue
            alias = f"_{next_id}"
            if self._cost_estimator is not None:
                saving = self._cost_estimator.saving_for_entry(
                    alias=alias, fullname=fullname, count=count
                )
            else:
                # Char-based fallback (backward-compatible)
                alias_len = len(alias)
                header_entry_len = alias_len + 1 + len(fullname) + 1
                saving = (count * len(fullname) - count * alias_len
                          - header_entry_len)
            if saving >= 0:
                selected[fullname] = count
                next_id += 1
        return selected
```

E) In `src/adp/__init__.py`, aggiungere import:

```python
from adp.cost import TokenizerCostEstimator, estimate_cost
```

E aggiungere `"TokenizerCostEstimator"` e `"estimate_cost"` a `__all__` se presente.

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_cost.py -v
uv run pytest -q
```

Expected: tests/test_cost.py 12 PASSED, full suite 212 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py src/adp/__init__.py tests/test_cost.py
git commit -m "feat(session): integrazione cost_estimator in ADPSession._select_candidates"
```

---

## Task 4 — Integrazione `warmup()` con cost_estimator

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_cost.py`

- [ ] **Step 1: Test failing**

Aggiungere a `tests/test_cost.py`:

```python
def test_warmup_uses_cost_estimator_when_present():
    """warmup() usa cost_estimator se ADPSession lo ha, per cost-benefit."""
    est = TokenizerCostEstimator()
    s = ADPSession(path=None, auto_save=False, k_threshold=2, cost_estimator=est)
    messages = [
        {"role": "administrator", "dept": "engineering"},
        {"role": "administrator", "dept": "engineering"},
    ]
    s.warmup(messages)
    # administrator e engineering sono token-cost positivi anche tokenizer-wise
    assert "administrator" in s._inv
    assert "engineering" in s._inv


def test_warmup_without_estimator_falls_back_to_charcount():
    """warmup() senza cost_estimator usa char-count (default backward-compat)."""
    s = ADPSession(path=None, auto_save=False, k_threshold=2, cost_estimator=None)
    messages = [
        {"role": "administrator", "dept": "engineering"},
        {"role": "administrator", "dept": "engineering"},
    ]
    s.warmup(messages)
    # Stesso risultato atteso del fallback
    assert "administrator" in s._inv
```

- [ ] **Step 2: Run failing**

Probabilmente già passano: il `_select_candidates` modificato in Task 3 viene usato anche da `warmup()` indirettamente? NO — `warmup()` ha la sua logica cost-benefit inline. Devo modificare anche quella.

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_cost.py -v -k warmup
```

Se passano già (perché char-count e tokenizer concordano su "administrator"/"engineering"): allora i test sono troppo deboli. Aggiungere assertion più stringente per dimostrare che il path tokenizer è preso.

Se falliscono: procedi a Step 3.

- [ ] **Step 3: Modificare `warmup()` in `src/adp/session.py`**

Trovare il metodo `warmup` e sostituire il blocco di cost-benefit interno. Cerca le righe:

```python
            next_id = self._next_alias_id
            alias_len = len(f"_{next_id}")
            header_entry_len = alias_len + 1 + len(fullname) + 1
            saving = count * len(fullname) - count * alias_len - header_entry_len
            if saving > 0:
                self._add_entry(fullname)
                added += 1
```

Sostituirle con:

```python
            alias = f"_{self._next_alias_id}"
            if self._cost_estimator is not None:
                saving = self._cost_estimator.saving_for_entry(
                    alias=alias, fullname=fullname, count=count
                )
            else:
                alias_len = len(alias)
                header_entry_len = alias_len + 1 + len(fullname) + 1
                saving = (count * len(fullname) - count * alias_len
                          - header_entry_len)
            if saving > 0:
                self._add_entry(fullname)
                added += 1
```

NOTA: il threshold `> 0` (non `>= 0`) qui è coerente con la versione precedente del warmup. Per coerenza con `_select_candidates` (che usa `>= 0`), il maintainer può uniformare in future ma per ora manteniamo il comportamento esistente.

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_cost.py -v
uv run pytest -q
```

Expected: tests/test_cost.py 14 PASSED, full suite 214 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_cost.py
git commit -m "feat(session): warmup() usa cost_estimator se passato"
```

---

## Task 5 — `pyproject.toml` extra `[tokenizer]` + benchmark variante

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/pyproject.toml`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/bench_dynamic_lut.py`

- [ ] **Step 1: Aggiungere optional extra `[tokenizer]`**

Aprire `pyproject.toml`. Trovare la sezione `[project.optional-dependencies]`. Aggiungere subito dopo le altre group keys:

```toml
tokenizer = [
    "tiktoken>=0.7",
]
```

Esempio dell'aspetto finale:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "tiktoken>=0.7",
]
bench = [
    "imagehash>=4.3.2",
    "msgpack>=1.1.2",
    # ... altre bench deps ...
]
tokenizer = [
    "tiktoken>=0.7",
]
```

- [ ] **Step 2: Verificare l'install funziona**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv sync --extra tokenizer
```

Expected: tiktoken installato (già presente da `dev`, ma deve risolvere il group senza errori).

- [ ] **Step 3: Modificare benchmark per usare cost_estimator**

Aprire `benchmarks/bench_dynamic_lut.py`. Trovare la sezione "Full stack" (`a_full`/`b_full`). Subito DOPO il loop `full_stack_tokens`, aggiungere una nuova configurazione:

```python
    # Full stack + tokenizer-aware cost estimator
    est = adp.TokenizerCostEstimator("cl100k_base")
    a_tok = adp.ADPSession(path=None, auto_save=False,
                            static_lut=adp.DEFAULT_AGENT_LUT,
                            enable_diff=True, cost_estimator=est)
    b_tok = adp.ADPSession(path=None, auto_save=False,
                            static_lut=adp.DEFAULT_AGENT_LUT,
                            enable_diff=True, cost_estimator=est)
    tokenizer_aware_tokens = 0
    for i, m in enumerate(msgs):
        sender, receiver = (a_tok, b_tok) if i % 2 == 0 else (b_tok, a_tok)
        encoded = sender.encode(m)
        decoded = receiver.decode(encoded)
        assert decoded == m, f"round-trip rotto (tokenizer-aware) msg {i}"
        tokenizer_aware_tokens += _tok(encoded)
```

E nella sezione di stampa risultati, aggiungere DOPO la riga `full_stack_tokens` e PRIMA di `TOON`:

```python
    print(f"{'ADP full stack + tokenizer-aware':<35} "
          f"{fmt(tokenizer_aware_tokens, baseline)}")
```

E nella tabella `Δ vs TOON`, dopo `full stack`:

```python
    print(f"{'ADP full stack + tokenizer-aware':<35} "
          f"{delta_toon(tokenizer_aware_tokens):>15}")
```

- [ ] **Step 4: Eseguire benchmark**

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
```

REPORTA L'OUTPUT COMPLETO. Vogliamo vedere se la versione tokenizer-aware migliora rispetto a char-count.

Aspettativa: marginale o nessun cambiamento. Su payload tipici, char-count e tiktoken concordano abbastanza spesso. Il vero valore del tokenizer-aware è la PRECISIONE (decisioni corrette su edge case), non il guadagno medio.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml benchmarks/bench_dynamic_lut.py
git commit -m "bench(cost): aggiunta variante full stack + tokenizer-aware estimator"
```

---

## Self-review (post-stesura del plan)

**1. Spec coverage (Est. 1):**

| Spec requirement | Task |
|---|---|
| Modulo `src/adp/cost.py` | Task 1 |
| `estimate_cost(text, tokenizer)` | Task 1 |
| `TokenizerCostEstimator` class | Task 1, 2 |
| `saving_for_entry(alias, fullname, count)` | Task 1, 2 |
| Fallback `len(text) // 4` se tiktoken assente | Task 1 |
| `ADPSession(cost_estimator=...)` param | Task 3 |
| `_select_candidates` usa estimator | Task 3 |
| `warmup` usa estimator | Task 4 |
| `pyproject.toml` extra `[tokenizer]` | Task 5 |
| Effort 50 LOC + 3 test | ✓ (≈80 LOC + 14 test) |

Tutto coperto. Numero test superiore allo spec (più copertura = meglio).

**2. Placeholder scan:** nessun TBD/TODO; tutti gli step contengono codice o comandi concreti.

**3. Type consistency:**

- `TokenizerCostEstimator(tokenizer: str = "cl100k_base")`
- `estimate(text: str) -> int`
- `saving_for_entry(alias: str, fullname: str, count: int) -> int`
- `is_tiktoken_available: bool`
- `cost_estimator: TokenizerCostEstimator | None = None` consistente in Task 3-4
- `_cost_estimator` attribute consistente

Nessuna divergenza.

## Note per Plan futuri

Dopo questo plan:
- Re-benchmark con tokenizer-aware
- Plan 5 (Est. 2 Capability negotiation): handshake `_caps=` tra agenti
- Plan 6 (Est. 3 TPD auto-promotion): unifica TPD e dyn LUT
- Considerare se passare il `cost_estimator` anche al diff encoding (out of scope v1: il diff è già un win netto, marginalmente migliorabile)
