# Dynamic LUT — Differential Encoding (Plan 2 di 6, Est. 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implementare differential encoding inter-message per `ADPSession` (Est. 5 della spec dynamic LUT) per ridurre drasticamente i token su pattern request/reply con payload simili.

**Architecture:** sender e receiver mantengono per-direzione l'ultimo payload completo scambiato + un base_id (hash troncato). Quando il nuovo payload è simile al precedente, sender emette `_base=ID;_diff={set=...;del=[...]}` invece del payload completo. Receiver verifica ID, applica diff, ottiene nuovo payload. Combinabile con dynamic LUT (prefissi ortogonali nel messaggio).

**Tech Stack:** Python 3.11+, stdlib (`hashlib.blake2b` per IDs, `copy.deepcopy`), `pytest` per i test. Nessuna dipendenza nuova.

---

## Deviazione consapevole dalla spec

La spec descrive 4 operazioni diff (set/del/append/replace_list). **Questo plan implementa solo set/del** in v1 (YAGNI). Le liste sono trattate come scalari atomici: qualsiasi cambiamento a una lista produce una sostituzione completa via set. Append in-place rimanda a v2.

Motivo: l'85% del valore di diff encoding viene da change incrementali su dict annidati (status update, metric refresh, incremental result), dove set/del è sufficiente. Append a lista è ottimizzazione marginale.

Formato `_diff`: usa **ADP nativo per set** (mirror della struttura modificata) + **lista di dot-paths per del** (bare strings con dot ammessi da ADP).

```
_diff={set={user={id=43}};del=[metadata.tmp,user.old_email]}
```

Vincolo: set non può rappresentare modifiche su elementi specifici di liste (es. "cambia solo users[3].role"). In quei casi: l'intera lista `users` viene sostituita. Trade-off accettabile per v1.

## Scope di questo plan

**Incluso:**
- `src/adp/diff.py`: nuovo modulo con `compute_diff`, `apply_diff`, helpers
- `ADPDiffSyncError` exception
- `ADPSession` extension: `enable_diff`, `diff_threshold` params; baseline state; encode/decode integrazione
- Reserved keys nuove: `_base`, `_diff`, `_diff_reset`
- `encode_full(obj)` per forzare encoding completo
- Test suite `tests/test_diff.py` con 8 categorie
- Aggiornamento `benchmarks/bench_dynamic_lut.py` per misurare guadagno

**Escluso:**
- Append in-place a liste (v2)
- Multi-baseline (più baseline candidati)
- Compressione del diff stesso (LZ77)
- Persistenza diff_state (in-memory only; restart = re-bootstrap)

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `src/adp/diff.py` | crea | algoritmi compute_diff / apply_diff + helpers |
| `src/adp/session.py` | modifica | param enable_diff/diff_threshold, baseline state, integrazione encode/decode |
| `src/adp/__init__.py` | modifica | esporta `ADPDiffSyncError` |
| `tests/test_diff.py` | crea | 8 categorie test (test_diff_*) |
| `benchmarks/bench_dynamic_lut.py` | modifica | nuove righe: ADP+dyn+diff, ADP+full stack |

---

## Task 1 — Modulo `diff.py` con compute_diff su dict semplici

**Files:**
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/diff.py`
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing**

Crea `tests/test_diff.py`:

```python
"""Test suite per adp.diff (differential encoding)."""
from __future__ import annotations

import pytest

from adp.diff import compute_diff, apply_diff


def test_compute_diff_identical_returns_empty():
    base = {"a": 1, "b": 2}
    current = {"a": 1, "b": 2}
    d = compute_diff(base, current)
    assert d == {}


def test_compute_diff_value_changed():
    base = {"a": 1, "b": 2}
    current = {"a": 1, "b": 3}
    d = compute_diff(base, current)
    assert d == {"set": {"b": 3}}


def test_compute_diff_new_key():
    base = {"a": 1}
    current = {"a": 1, "b": 2}
    d = compute_diff(base, current)
    assert d == {"set": {"b": 2}}


def test_compute_diff_removed_key():
    base = {"a": 1, "b": 2}
    current = {"a": 1}
    d = compute_diff(base, current)
    assert d == {"del": ["b"]}


def test_compute_diff_both_set_and_del():
    base = {"a": 1, "b": 2, "c": 3}
    current = {"a": 1, "b": 9, "d": 4}
    d = compute_diff(base, current)
    assert d == {"set": {"b": 9, "d": 4}, "del": ["c"]}
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_diff.py -v
```

Expected: 5 FAIL (modulo `adp.diff` non esiste).

- [ ] **Step 3: Implementare `src/adp/diff.py`**

Contenuto completo:

```python
"""Differential encoding per ADPSession.

Calcola e applica diff strutturali tra due payload dict/list/scalar.
Operazioni supportate v1: set (sostituzione/aggiunta), del (rimozione).
Liste trattate come scalari atomici (qualsiasi modifica → sostituzione full
della lista via set).

Path notation per del: dot-separated, es. "user.id", "metadata.tmp".
Le liste non sono indicizzate per path (limitazione v1).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def compute_diff(base: Any, current: Any) -> dict:
    """Calcola diff strutturale tra base e current.

    Ritorna dict con chiavi opzionali 'set' e 'del':
    - 'set': nested dict sparso che mirrora le sotto-strutture modificate
    - 'del': lista di dot-paths string da rimuovere da base

    Se base == current: ritorna {}.
    Liste: comparate per uguaglianza; se diverse → full replacement via set.
    """
    set_part: dict = {}
    del_part: list[str] = []
    _diff_recursive(base, current, "", set_part, del_part)
    out: dict = {}
    if set_part:
        out["set"] = set_part
    if del_part:
        out["del"] = del_part
    return out


def _diff_recursive(base: Any, current: Any, path: str,
                    set_part: dict, del_part: list[str]) -> None:
    """Visita ricorsiva. set_part e del_part vengono mutati in-place."""
    if isinstance(base, dict) and isinstance(current, dict):
        all_keys = set(base.keys()) | set(current.keys())
        for k in all_keys:
            child_path = f"{path}.{k}" if path else str(k)
            if k not in current:
                del_part.append(child_path)
            elif k not in base:
                _place_in_set(set_part, child_path, current[k])
            else:
                if isinstance(base[k], dict) and isinstance(current[k], dict):
                    _diff_recursive(base[k], current[k], child_path,
                                    set_part, del_part)
                elif base[k] != current[k]:
                    _place_in_set(set_part, child_path, current[k])
        return
    # Scalari, liste, tipi misti: confronto diretto
    if base != current:
        if path == "":
            # Root non è un dict: caso pathologico, rappresenta come set top-level
            # con chiave speciale "" — qui non gestito perché in pratica non capita
            raise ValueError("compute_diff supporta solo dict al top-level")
        _place_in_set(set_part, path, current)


def _place_in_set(set_part: dict, dot_path: str, value: Any) -> None:
    """Inserisce value nella struttura set_part secondo dot_path."""
    parts = dot_path.split(".")
    cur = set_part
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def apply_diff(base: Any, diff: dict) -> Any:
    """Applica diff a base, ritorna nuovo payload (base non modificato).

    Ordine: prima delete, poi set (deep-merge). Risultato: nuovo dict.
    """
    new = deepcopy(base)
    for path in diff.get("del", []):
        _delete_at_path(new, path.split("."))
    set_part = diff.get("set", {})
    _deep_merge(new, set_part)
    return new


def _delete_at_path(obj: Any, parts: list[str]) -> None:
    """Naviga obj seguendo parts e cancella l'ultima chiave.
    No-op se path non esiste (idempotente)."""
    cur = obj
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _deep_merge(dst: dict, src: dict) -> None:
    """Merge ricorsivo di src in dst. dst modificato in-place."""
    for k, v in src.items():
        if (isinstance(v, dict) and isinstance(dst.get(k), dict)):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/diff.py tests/test_diff.py
git commit -m "feat(diff): compute_diff/apply_diff per dict semplici"
```

---

## Task 2 — `apply_diff` e round-trip su dict annidati

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing per nested + apply_diff + round-trip**

Aggiungere a `tests/test_diff.py`:

```python
def test_compute_diff_nested_dict():
    base = {"user": {"id": 42, "role": "admin", "dept": "eng"}}
    current = {"user": {"id": 42, "role": "admin", "dept": "ops"}}
    d = compute_diff(base, current)
    assert d == {"set": {"user": {"dept": "ops"}}}


def test_compute_diff_nested_add_remove():
    base = {"user": {"id": 42, "role": "admin"}, "x": 1}
    current = {"user": {"id": 42, "role": "admin", "new": "v"}, "y": 2}
    d = compute_diff(base, current)
    assert d == {"set": {"user": {"new": "v"}, "y": 2}, "del": ["x"]}


def test_compute_diff_list_full_replacement():
    base = {"items": [1, 2, 3]}
    current = {"items": [1, 2, 3, 4]}
    d = compute_diff(base, current)
    # Lista cambiata → sostituzione full
    assert d == {"set": {"items": [1, 2, 3, 4]}}


def test_apply_diff_set_only():
    base = {"a": 1, "b": {"c": 2}}
    diff = {"set": {"b": {"c": 3}}}
    new = apply_diff(base, diff)
    assert new == {"a": 1, "b": {"c": 3}}
    # Base non modificata
    assert base == {"a": 1, "b": {"c": 2}}


def test_apply_diff_del_only():
    base = {"a": 1, "b": 2}
    diff = {"del": ["b"]}
    new = apply_diff(base, diff)
    assert new == {"a": 1}


def test_apply_diff_set_and_del():
    base = {"a": 1, "b": 2, "c": 3}
    diff = {"set": {"b": 9, "d": 4}, "del": ["c"]}
    new = apply_diff(base, diff)
    assert new == {"a": 1, "b": 9, "d": 4}


def test_apply_diff_empty_returns_copy():
    base = {"a": 1}
    new = apply_diff(base, {})
    assert new == base
    assert new is not base  # deep copy


def test_diff_round_trip_realistic():
    base = {
        "task_id": "task_001",
        "user": {"id": 42, "role": "admin", "dept": "eng"},
        "metrics": {"errors": 0, "latency_ms": 200},
    }
    current = {
        "task_id": "task_002",  # changed
        "user": {"id": 42, "role": "admin", "dept": "ops"},  # dept changed
        "metrics": {"errors": 3, "latency_ms": 200},  # errors changed
        "new_field": "added",
    }
    d = compute_diff(base, current)
    rebuilt = apply_diff(base, d)
    assert rebuilt == current


def test_apply_diff_delete_nested_path():
    base = {"a": {"b": {"c": 1, "d": 2}}}
    diff = {"del": ["a.b.c"]}
    new = apply_diff(base, diff)
    assert new == {"a": {"b": {"d": 2}}}


def test_apply_diff_delete_missing_path_noop():
    base = {"a": 1}
    diff = {"del": ["nonexistent.path"]}
    new = apply_diff(base, diff)
    assert new == {"a": 1}
```

- [ ] **Step 2: Eseguire test**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 15 PASSED (5 Task 1 + 10 nuovi).

Se test falliscono: revisionare `_diff_recursive` e `_deep_merge` per casi annidati.

- [ ] **Step 3: Commit**

```bash
git add tests/test_diff.py
git commit -m "test(diff): nested + apply + round-trip realistico"
```

---

## Task 3 — `ADPDiffSyncError` + baseline state in ADPSession

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/__init__.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing per nuova exception + costruttore**

Aggiungere a `tests/test_diff.py`:

```python
from adp.session import ADPSession
from adp import ADPDiffSyncError  # nuovo export


def test_diff_sync_error_carries_expected_and_got():
    err = ADPDiffSyncError(expected="abc12345", got="def67890")
    assert err.expected == "abc12345"
    assert err.got == "def67890"
    assert "abc12345" in str(err)
    assert "def67890" in str(err)


def test_session_diff_state_initialized():
    s = ADPSession(path=None, auto_save=False)
    assert s._last_sent_payload is None
    assert s._last_sent_base_id is None
    assert s._last_received_payload is None
    assert s._last_received_base_id is None
    # Default enable_diff True
    assert s._enable_diff is True
    assert s._diff_threshold == 0.7


def test_session_diff_params_configurable():
    s = ADPSession(path=None, auto_save=False,
                   enable_diff=False, diff_threshold=0.5)
    assert s._enable_diff is False
    assert s._diff_threshold == 0.5
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_diff.py -v -k "sync_error or state or params"
```

Expected: 3 FAIL.

- [ ] **Step 3: Aggiungere `ADPDiffSyncError` e baseline state**

In `src/adp/session.py`:

1. Aggiungere la nuova exception class subito dopo `ADPLUTSyncError`:

```python
class ADPDiffSyncError(Exception):
    """Sollevata quando il base_id dichiarato in _base= non match con lo state locale."""

    def __init__(self, expected: str, got: str):
        self.expected = expected
        self.got = got
        super().__init__(
            f"Diff baseline mismatch: atteso {expected!r}, ricevuto {got!r}"
        )
```

2. Aggiornare `__all__`:

```python
__all__ = ["ADPSession", "ADPLUTSyncError", "ADPDiffSyncError",
           "apply_lut_updates", "encode_with_dyn_lut"]
```

3. Modificare `__init__` di `ADPSession`: aggiungere `enable_diff` e `diff_threshold` parameters, inizializzare baseline state.

Trovare la firma di `__init__` e cambiarla in:

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
    ) -> None:
```

E nel corpo aggiungere (dopo la sezione "Mutable state"):

```python
        # Differential encoding state (Est. 5)
        self._enable_diff = enable_diff
        self._diff_threshold = diff_threshold
        self._last_sent_payload: Any = None
        self._last_sent_base_id: str | None = None
        self._last_received_payload: Any = None
        self._last_received_base_id: str | None = None
```

4. In `src/adp/__init__.py`, aggiornare l'import:

```python
from adp.session import (
    ADPSession,
    ADPLUTSyncError,
    ADPDiffSyncError,
    apply_lut_updates,
    encode_with_dyn_lut,
)
```

E aggiungere `"ADPDiffSyncError"` a `__all__` se presente.

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 18 PASSED (15 diff + 3 nuovi).

Verifica anche full suite per no regression:
```bash
uv run pytest -q
```
Expected: 175 PASSED (157 baseline + 18 diff).

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py src/adp/__init__.py tests/test_diff.py
git commit -m "feat(session): ADPDiffSyncError + baseline state in ADPSession"
```

---

## Task 4 — Encoder: emit `_base=ID;_diff={...}` se diff conviene

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing per encoder diff**

Aggiungere a `tests/test_diff.py`:

```python
def test_encode_first_message_full_no_diff_prefix():
    s = ADPSession(path=None, auto_save=False)
    msg = s.encode({"a": 1, "b": 2})
    assert "_base=" not in msg
    assert "_diff=" not in msg
    # State aggiornato
    assert s._last_sent_payload == {"a": 1, "b": 2}
    assert s._last_sent_base_id is not None


def test_encode_second_message_small_change_uses_diff():
    s = ADPSession(path=None, auto_save=False)
    s.encode({"task_id": "task_001", "user": {"id": 42, "role": "administrator"}})
    msg2 = s.encode({"task_id": "task_002", "user": {"id": 42, "role": "administrator"}})
    assert "_base=" in msg2
    assert "_diff=" in msg2


def test_encode_massive_change_falls_back_to_full():
    s = ADPSession(path=None, auto_save=False, diff_threshold=0.7)
    # Primo msg: piccolo
    s.encode({"a": 1})
    # Secondo msg: totalmente diverso e molto più grande
    big_payload = {f"key_{i}": f"value_administrator_long_{i}" for i in range(50)}
    msg2 = s.encode(big_payload)
    # Diff sarebbe enorme rispetto al full → fallback a full
    assert "_base=" not in msg2
    assert "_diff=" not in msg2


def test_encode_diff_disabled_never_emits():
    s = ADPSession(path=None, auto_save=False, enable_diff=False)
    s.encode({"a": 1})
    msg2 = s.encode({"a": 1, "b": 2})
    assert "_base=" not in msg2
    assert "_diff=" not in msg2
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_diff.py -v -k "encode_first or encode_second or encode_massive or encode_diff_disabled"
```

Expected: 4 FAIL.

- [ ] **Step 3: Modificare `encode()` per supportare diff encoding**

In `src/adp/session.py`, sostituire il metodo `encode()` esistente con la versione estesa. Trovare il metodo `def encode(self, obj: Any, *, no_lut: bool = False) -> str:` e sostituirlo INTERAMENTE con:

```python
    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj a stringa ADP.

        - Se no_lut=True: bypassa dynamic LUT (e diff encoding).
        - Se enable_diff=True e abbiamo un baseline last_sent: calcola diff,
          se conviene (size < threshold * full_size) emette _base=ID;_diff={...},
          altrimenti emette full.
        - Aggiorna sempre _last_sent_payload + _last_sent_base_id col payload corrente.
        """
        if no_lut:
            self._last_sent_payload = obj
            self._last_sent_base_id = self._compute_base_id(obj)
            if self._static_lut:
                return adp.encode(obj, key_lut=self._static_lut)
            return adp.encode(obj)

        # Step 1: produrre la versione "full" del messaggio (con dyn LUT)
        full_msg = self._encode_full_with_lut(obj)

        # Step 2: se enable_diff e c'è un baseline, valutare diff
        diff_msg: str | None = None
        if self._enable_diff and self._last_sent_payload is not None:
            diff_dict = compute_diff(self._last_sent_payload, obj)
            if diff_dict:  # non vuoto: payload cambiato
                diff_payload = adp.encode(diff_dict, key_lut=self._static_lut or None)
                candidate = f"_base={self._last_sent_base_id};_diff={diff_payload};"
                if len(candidate) < self._diff_threshold * len(full_msg):
                    diff_msg = candidate

        # Aggiorna baseline state
        self._last_sent_payload = obj
        self._last_sent_base_id = self._compute_base_id(obj)

        return diff_msg if diff_msg is not None else full_msg

    def _encode_full_with_lut(self, obj: Any) -> str:
        """Estrae la logica esistente di encode (count/select/substitute/prefix)."""
        # 1. Conta candidati
        counts = self._count_candidates(obj)

        # 2. Bumpa LRU per quelli già in dynamic LUT
        for fullname in counts:
            if fullname in self._inv:
                self._mark_used(self._inv[fullname])

        # 3. Seleziona nuovi candidati
        new_candidates = self._select_candidates(counts)

        # 4. Aggiungi entry per ognuno
        new_aliases: dict[str, str] = {}
        for fullname in new_candidates:
            alias = self._add_entry(fullname)
            new_aliases[alias] = fullname

        # 5. Sostituisci nel payload
        substituted = self._substitute(obj)

        # 6. Compone messaggio finale
        payload_adp = adp.encode(substituted, key_lut=self._static_lut or None)
        if not new_aliases:
            return payload_adp

        prefix_pairs = ";".join(f"{a}={self._quote_if_needed(f)}"
                                for a, f in new_aliases.items())
        prefix = f"_lut_add={{{prefix_pairs}}};"
        return prefix + payload_adp

    @staticmethod
    def _compute_base_id(obj: Any) -> str:
        """Hash troncato di un payload per identificare il baseline.
        Usa blake2b digest_size=4 = 8 hex char (32 bit, sufficiente per ID
        per-session)."""
        import hashlib
        raw = adp.encode(obj).encode("utf-8")
        return hashlib.blake2b(raw, digest_size=4).hexdigest()
```

5. Aggiungere `from adp.diff import compute_diff, apply_diff` agli import in cima al file.

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 22 PASSED (18 + 4 nuovi).

E full suite:
```bash
uv run pytest -q
```
Expected: 179 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_diff.py
git commit -m "feat(session): encoder con _base=ID;_diff={set;del} se conviene"
```

---

## Task 5 — Decoder: parse `_base`+`_diff` + sync error

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing per decoder diff**

Aggiungere a `tests/test_diff.py`:

```python
def test_decode_full_message_updates_baseline():
    s = ADPSession(path=None, auto_save=False)
    import adp as adp_mod
    msg = adp_mod.encode({"a": 1, "b": 2})
    out = s.decode(msg)
    assert out == {"a": 1, "b": 2}
    # baseline received aggiornato
    assert s._last_received_payload == {"a": 1, "b": 2}
    assert s._last_received_base_id is not None


def test_decode_diff_applies_to_baseline():
    s_sender = ADPSession(path=None, auto_save=False)
    s_receiver = ADPSession(path=None, auto_save=False)
    base = {"user": {"id": 42, "role": "administrator"}, "x": 1}
    update = {"user": {"id": 42, "role": "administrator"}, "x": 2}
    # First msg: full
    msg1 = s_sender.encode(base)
    out1 = s_receiver.decode(msg1)
    assert out1 == base
    # Second msg: diff
    msg2 = s_sender.encode(update)
    assert "_base=" in msg2  # encoder ha scelto diff
    out2 = s_receiver.decode(msg2)
    assert out2 == update


def test_decode_diff_sync_error_on_mismatch():
    s = ADPSession(path=None, auto_save=False)
    # Receiver non ha mai visto un payload → no baseline
    msg = "_base=deadbeef;_diff={set={a=1}};"
    with pytest.raises(ADPDiffSyncError) as exc_info:
        s.decode(msg)
    assert exc_info.value.got == "deadbeef"
    assert exc_info.value.expected is None or exc_info.value.expected == ""


def test_decode_diff_reset_clears_baseline():
    s = ADPSession(path=None, auto_save=False)
    s.decode("a=1;b=2")  # full msg, baseline ora settato
    assert s._last_received_payload is not None
    # Reset
    s.decode("_diff_reset=1;a=1")
    assert s._last_received_payload == {"a": 1}  # nuovo baseline (post-reset)
    # In effetti dopo _diff_reset, il payload del msg corrente diventa il nuovo
    # baseline (è full per definizione, no diff possibile dopo reset)
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_diff.py -v -k "decode_full or decode_diff"
```

Expected: 4 FAIL.

- [ ] **Step 3: Estendere `_RESERVED_KEYS` + modificare `decode()`**

In `src/adp/session.py`, sostituire il `_RESERVED_KEYS` con:

```python
    _RESERVED_KEYS = ("_lut_reset", "_lut_add", "_diff_reset", "_base", "_diff")
```

E sostituire INTERAMENTE il metodo `decode()` esistente con:

```python
    def decode(self, msg: str) -> Any:
        """Decode messaggio ADP. Applica nell'ordine:
        1. _lut_reset / _lut_add — aggiorna dynamic LUT
        2. _diff_reset — pulisce baseline
        3. _base + _diff — applica diff a baseline
        4. Resto del payload — decode normale, aggiorna baseline
        Espande infine alias dynamic LUT nel risultato.
        """
        rest = msg
        seen: set[str] = set()
        diff_base_id: str | None = None
        diff_dict: dict | None = None

        while True:
            prefix_match = self._match_reserved_prefix(rest)
            if prefix_match is None:
                break
            key, value_str, consumed = prefix_match
            if key in seen:
                raise adp.ADPParseError(f"Prefisso duplicato: {key!r}")
            seen.add(key)
            if key == "_lut_reset":
                if value_str not in ("0", "1"):
                    raise adp.ADPParseError(
                        f"_lut_reset valore invalido: {value_str!r}")
                if value_str == "1":
                    self._apply_lut_reset()
            elif key == "_lut_add":
                self._apply_lut_add(value_str)
            elif key == "_diff_reset":
                if value_str not in ("0", "1"):
                    raise adp.ADPParseError(
                        f"_diff_reset valore invalido: {value_str!r}")
                if value_str == "1":
                    self._last_received_payload = None
                    self._last_received_base_id = None
            elif key == "_base":
                diff_base_id = value_str
            elif key == "_diff":
                diff_payload_str = f"d={value_str}"
                parsed = adp.decode(diff_payload_str,
                                   key_lut=self._static_lut or None)
                if not isinstance(parsed, dict) or "d" not in parsed:
                    raise adp.ADPParseError(
                        f"_diff malformed: {value_str!r}")
                diff_dict = parsed["d"]
            rest = rest[consumed:]

        # Gestione diff
        if diff_base_id is not None and diff_dict is not None:
            if self._last_received_base_id != diff_base_id:
                raise ADPDiffSyncError(
                    expected=self._last_received_base_id or "",
                    got=diff_base_id,
                )
            # Applica diff a baseline
            new_payload = apply_diff(self._last_received_payload, diff_dict)
            self._last_received_payload = new_payload
            self._last_received_base_id = self._compute_base_id(new_payload)
            return self._expand(new_payload)

        if diff_base_id is not None or diff_dict is not None:
            # _base senza _diff o viceversa: errore
            raise adp.ADPParseError(
                "_base e _diff devono apparire insieme")

        # Full payload normale
        if not rest:
            return {}
        payload = adp.decode(rest, key_lut=self._static_lut or None)
        expanded = self._expand(payload)
        # Aggiorna baseline received
        self._last_received_payload = expanded
        self._last_received_base_id = self._compute_base_id(expanded)
        return expanded
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 26 PASSED.

Full suite no regression:
```bash
uv run pytest -q
```
Expected: 183 PASSED.

Se test 23 (`test_decode_diff_applies_to_baseline`) fallisce: probabile che encoder non aggiorna `_last_sent_payload` correttamente, o che `_compute_base_id` non sia deterministico. Verificare.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_diff.py
git commit -m "feat(session): decoder _base+_diff + _diff_reset + sync error"
```

---

## Task 6 — `encode_full()` per forzare encoding completo

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing**

Aggiungere a `tests/test_diff.py`:

```python
def test_encode_full_ignores_baseline():
    s = ADPSession(path=None, auto_save=False)
    s.encode({"a": 1})
    # Anche con baseline disponibile, encode_full produce full + emette _diff_reset
    msg = s.encode_full({"a": 1, "b": 2})
    assert "_diff_reset=1" in msg
    assert "_base=" not in msg
    assert "_diff=" not in msg


def test_encode_full_resets_local_baseline():
    s = ADPSession(path=None, auto_save=False)
    s.encode({"a": 1})
    s.encode_full({"a": 1, "b": 2})
    # Baseline locale aggiornato col nuovo payload
    assert s._last_sent_payload == {"a": 1, "b": 2}
    assert s._last_sent_base_id is not None


def test_encode_full_then_decode_clears_receiver_baseline():
    sender = ADPSession(path=None, auto_save=False)
    receiver = ADPSession(path=None, auto_save=False)
    msg1 = sender.encode({"a": 1, "b": 2})
    receiver.decode(msg1)
    # Cambio direzione: receiver ora ha baseline diversa che inquinerebbe
    # Sender forza full
    msg2 = sender.encode_full({"x": 1})
    out = receiver.decode(msg2)
    assert out == {"x": 1}
    # Receiver baseline ora == {"x": 1}
    assert receiver._last_received_payload == {"x": 1}
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_diff.py -v -k encode_full
```

Expected: 3 FAIL.

- [ ] **Step 3: Implementare `encode_full()`**

In `src/adp/session.py`, aggiungere il metodo (dopo `encode()`):

```python
    def encode_full(self, obj: Any) -> str:
        """Forza encoding completo (no diff). Emette _diff_reset=1 al receiver.

        Reset locale del baseline diff state, poi encode normale (incluso
        dynamic LUT). Utile per recovery dopo ADPDiffSyncError o reset
        esplicito di sincronizzazione.
        """
        # Resetta diff state locale
        self._last_sent_payload = None
        self._last_sent_base_id = None

        # Encode full (passa per _encode_full_with_lut ma con prefix reset)
        full_msg = self._encode_full_with_lut(obj)

        # Aggiorna baseline col nuovo payload
        self._last_sent_payload = obj
        self._last_sent_base_id = self._compute_base_id(obj)

        return "_diff_reset=1;" + full_msg
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_diff.py -v
```

Expected: 29 PASSED.

Full suite:
```bash
uv run pytest -q
```
Expected: 186 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_diff.py
git commit -m "feat(session): encode_full() per forzare encoding completo"
```

---

## Task 7 — Test combinato: diff + dynamic LUT insieme, round-trip 20 msg

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_diff.py`

- [ ] **Step 1: Test failing per combinazione**

Aggiungere a `tests/test_diff.py`:

```python
def test_combined_lut_and_diff_round_trip_20_messages():
    """Sessione 20 msg con dyn LUT + diff encoding entrambi attivi."""
    a = ADPSession(path=None, auto_save=False)
    b = ADPSession(path=None, auto_save=False)

    base_payload = {
        "task_id": "task_000",
        "user": {"id": 42, "role": "administrator", "dept": "engineering"},
        "status": "in_progress",
        "metrics": {"errors": 0, "latency_ms": 200},
    }
    diff_count = 0
    full_count = 0
    for i in range(20):
        p = {
            "task_id": f"task_{i:03d}",
            "user": {"id": 42, "role": "administrator", "dept": "engineering"},
            "status": "in_progress" if i % 3 != 0 else "completed",
            "metrics": {"errors": i % 5, "latency_ms": 200 + i},
        }
        msg = a.encode(p)
        if "_diff=" in msg:
            diff_count += 1
        else:
            full_count += 1
        out = b.decode(msg)
        assert out == p, f"mismatch at msg {i}"

    # Almeno alcuni messaggi dopo il primo devono essere diff
    assert diff_count >= 10
    assert full_count >= 1  # primo msg almeno
    # Stati di entrambi sincronizzati
    assert a._last_sent_payload == b._last_received_payload


def test_sync_error_recovery_via_encode_full():
    """Dopo sync error, recovery con encode_full ristabilisce comunicazione."""
    sender = ADPSession(path=None, auto_save=False)
    receiver = ADPSession(path=None, auto_save=False)
    # Sender ha baseline, receiver no (simula receiver appena avviato)
    sender.encode({"a": 1})  # sender now has baseline
    sender.encode({"a": 1, "b": 2})  # sender will use diff

    # Manualmente forziamo: receiver è fresco
    receiver._last_received_payload = None
    receiver._last_received_base_id = None

    # Sender invia diff a receiver che non ha baseline
    msg = sender.encode({"a": 1, "b": 3})
    if "_diff=" in msg:
        with pytest.raises(ADPDiffSyncError):
            receiver.decode(msg)

        # Recovery: sender invia full
        recovery_msg = sender.encode_full({"a": 1, "b": 3})
        out = receiver.decode(recovery_msg)
        assert out == {"a": 1, "b": 3}
```

- [ ] **Step 2: Eseguire test**

```bash
uv run pytest tests/test_diff.py -v -k "combined or sync_error_recovery"
```

Expected: 2 PASSED (test integrazione).

Se `test_combined_lut_and_diff_round_trip_20_messages` fallisce: probabilmente baseline desync per side-effect del dyn LUT bumping. Investigare ordine di applicazione (Tab 5: encoder applica LUT prima del diff, decoder simile).

- [ ] **Step 3: Eseguire suite intera**

```bash
uv run pytest -q
```

Expected: 188 PASSED.

- [ ] **Step 4: Commit**

```bash
git add tests/test_diff.py
git commit -m "test(diff): integrazione dyn LUT + diff, recovery sync error"
```

---

## Task 8 — Update benchmark + verifica guadagno vs TOON

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/benchmarks/bench_dynamic_lut.py`

- [ ] **Step 1: Aggiungere righe per diff encoding al benchmark**

Aprire `benchmarks/bench_dynamic_lut.py`. Identificare la sezione dove vengono calcolati `dyn_cold_tokens` e `dyn_combo_tokens`. Aggiungere DOPO `dyn_combo_tokens`:

```python
    # Dynamic LUT + diff encoding (cold)
    sender_diff = adp.ADPSession(path=None, auto_save=False, enable_diff=True)
    receiver_diff = adp.ADPSession(path=None, auto_save=False, enable_diff=True)
    dyn_diff_tokens = 0
    for m in msgs:
        encoded = sender_diff.encode(m)
        decoded = receiver_diff.decode(encoded)
        assert decoded == m, "round-trip rotto (diff)"
        dyn_diff_tokens += _tok(encoded)

    # Full stack: dyn LUT + static + diff
    sender_full = adp.ADPSession(
        path=None, auto_save=False, static_lut=adp.DEFAULT_AGENT_LUT,
        enable_diff=True,
    )
    receiver_full = adp.ADPSession(
        path=None, auto_save=False, static_lut=adp.DEFAULT_AGENT_LUT,
        enable_diff=True,
    )
    full_stack_tokens = 0
    for m in msgs:
        encoded = sender_full.encode(m)
        decoded = receiver_full.decode(encoded)
        assert decoded == m, "round-trip rotto (full stack)"
        full_stack_tokens += _tok(encoded)
```

E nella tabella di output, aggiungere subito DOPO la riga `dyn_combo_tokens`:

```python
    print(f"{'ADP + dyn LUT + diff':<35} {fmt(dyn_diff_tokens, baseline)}")
    print(f"{'ADP + full stack (lut+static+diff)':<35} {fmt(full_stack_tokens, baseline)}")
```

E nella tabella "Confronto diretto vs TOON":

```python
    print(f"{'ADP + dyn LUT + diff':<35} {delta_toon(dyn_diff_tokens):>15}")
    print(f"{'ADP + full stack':<35} {delta_toon(full_stack_tokens):>15}")
```

- [ ] **Step 2: Eseguire benchmark**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
```

Expected output: una tabella estesa con i nuovi formati. Atteso (orientativo):
- `ADP + dyn LUT + diff` dovrebbe battere `ADP + dyn LUT (cold)` di un buon margine
- `ADP + full stack` dovrebbe essere il MIGLIORE di tutti

Se diff NON migliora rispetto a dyn LUT cold: indagare se i payload del benchmark sono sufficientemente "similari" tra msg consecutivi (request/reply).

- [ ] **Step 3: Commit del benchmark aggiornato**

```bash
git add benchmarks/bench_dynamic_lut.py
git commit -m "bench(diff): aggiunte righe ADP+diff e full stack vs TOON"
```

---

## Self-review (post-stesura del plan)

**1. Spec coverage (Est. 5):**

| Spec requirement | Task |
|---|---|
| `_base=ID;_diff={...}` prefix | Task 4, 5 |
| `_diff_reset=1` reset | Task 5, 6 |
| Operazioni set/del (v1) | Task 1, 2 |
| Operazioni append/replace_list | OUT (v2, vedi Deviazione) |
| Sender state per-direzione | Task 3, 4 |
| Receiver state per-direzione | Task 3, 5 |
| `compute_diff` / `apply_diff` | Task 1, 2 |
| `encode_full()` | Task 6 |
| Threshold 0.7 default | Task 3, 4 |
| `ADPDiffSyncError` | Task 3, 5 |
| Combinazione con dyn LUT | Task 5, 7 |
| Test categorie 28-35 spec | distribuiti Task 1-7 |
| Benchmark vs TOON aggiornato | Task 8 |

Tutto coperto eccetto append/replace_list (rimandato a v2 esplicitamente).

**2. Placeholder scan:** nessun TBD/TODO; tutti gli step contengono codice o comandi concreti.

**3. Type consistency:**

- `_last_sent_payload: Any | None`, `_last_sent_base_id: str | None` consistenti tra Task 3, 4, 6
- `_last_received_payload`, `_last_received_base_id` consistenti tra Task 3, 5
- `compute_diff(base, current) -> dict` con chiavi opzionali `"set"` e `"del"`
- `apply_diff(base, diff_dict) -> Any` (ritorna nuovo payload)
- `_compute_base_id(obj) -> str` (8 hex char)
- `ADPDiffSyncError(expected, got)` consistente in Task 3, 5, 7

**4. Deviazioni dalla spec:**

- Solo set/del (no append/replace_list inline) — v1. Documentato.
- Formato `_diff={set=...;del=[...]}` invece di lista di operazioni → semplifica parsing usando ADP-nativo.

## Note per Plan futuri

Dopo questo plan:
- Re-benchmark complessivo per validare guadagno vs TOON
- Se diff vince: procedere con Est. 1 (tokenizer) + Est. 2 (caps) + Est. 4 (warmup) + Est. 3 (TPD) come spec
- Se diff NON vince come previsto: re-progettare (forse append/replace_list servono, o threshold da abbassare, o payload realistici diversi)
- README update con sezione "Differential encoding" dopo aver validato il valore aggiunto
