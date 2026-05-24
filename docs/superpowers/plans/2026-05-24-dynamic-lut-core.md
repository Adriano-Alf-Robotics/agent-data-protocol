# Dynamic LUT — Core Implementation Plan (Plan 1 di 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implementare il **core** della LUT dinamica adattiva HPACK-style descritto nella spec `docs/superpowers/specs/2026-05-24-dynamic-lut-design.md` (senza le 5 estensioni, che hanno plan dedicati a seguire).

**Architecture:** nuovo modulo `src/adp/session.py` che incapsula `ADPSession` class. La sessione mantiene una LUT dinamica con LRU bounded, la persiste in `~/.adp/lut_state.json` (con `fcntl.flock`), genera prefissi `_lut_add={...}` / `_lut_reset=1` come chiavi top-level ADP standard, e si appoggia all'encoder/decoder esistenti senza modificarli.

**Tech Stack:** Python 3.11+, stdlib only (`pathlib`, `json`, `fcntl`, `atexit`, `tempfile`, `os`, `re`), `pytest` per i test. Nessuna dipendenza nuova.

---

## Deviazione consapevole dalla spec

La spec descrive prefissi `_lut+={...}` e `_lut!={}` che richiederebbero modifica del parser ADP per accettare i caratteri `+` e `!` in posizione identificatore. Per semplicità e per evitare modifiche invasive a `parser.py`/`serializer.py`, **questo plan usa nomi grammar-compliant**:

- `_lut_add={...}` invece di `_lut+={...}`
- `_lut_reset=1` (boolean) invece di `_lut!={}`

Questi sono identificatori ADP validi (`[A-Za-z_][A-Za-z0-9_-]*`), parsificabili senza modifiche al lessico. Costo in token aggiuntivo: 2-3 token per messaggio (`_lut_add` = 3 token vs `_lut+` = 2 token). Beneficio: zero rischio regressione sul parser, zero modifica a `parser.py`/`serializer.py`.

Se in futuro si vuole tornare alla sintassi simbolica, basta una migrazione del parser + bump version schema.

## Scope di questo plan (Core)

**Incluso:**
- `ADPSession` class: `__init__`, `encode`, `decode`, `save`, `reset`, `encode_reset`, `stats`
- Parametri core: `path`, `max_entries`, `static_lut`, `k_threshold`, `auto_save`
- Persistenza JSON con `fcntl.flock` e atomic write
- LRU eviction deterministica
- Eager learner con cost-benefit char-based
- `ADPLUTSyncError` exception per alias sconosciuti
- `_lut_add` / `_lut_reset` prefix injection/extraction
- 12 test (categorie 1-12 della spec)
- API low-level: `apply_lut_updates`, `encode_with_dyn_lut`

**Escluso (plan futuri):**
- Estensione 1 — Tokenizer-aware cost (`cost.py`)
- Estensione 2 — Capability negotiation (`_caps=` handshake)
- Estensione 3 — TPD auto-promotion
- Estensione 4 — Pre-warm da corpus (`warmup()` metodo)
- Estensione 5 — Differential encoding (`diff.py`, `_base`/`_diff`)
- Benchmark vs TOON (plan separato dopo Est. 5)
- Sezione README

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `src/adp/session.py` | crea | `ADPSession` class, persistence, learner, prefix handling |
| `src/adp/__init__.py` | modifica | esporta `ADPSession`, `ADPLUTSyncError`, `apply_lut_updates`, `encode_with_dyn_lut` |
| `tests/test_session.py` | crea | 12 test categorie core |

Niente modifiche a `parser.py`/`serializer.py`/`lut.py`/`tpd.py` (vedi "Deviazione consapevole").

---

## Task 1 — Scaffolding e exception class

**Files:**
- Create: `src/adp/session.py`
- Create: `tests/test_session.py`
- Modify: `src/adp/__init__.py`

- [ ] **Step 1: Creare lo scheletro `src/adp/session.py`**

```python
"""ADPSession — dynamic LUT adattiva HPACK-style.

Mantiene una LUT dinamica condivisa tra agenti, sincronizzata via prefissi
in-band nei messaggi ADP, persistita localmente.

Vedi spec: docs/superpowers/specs/2026-05-24-dynamic-lut-design.md
"""
from __future__ import annotations

import atexit
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

import adp


class ADPLUTSyncError(Exception):
    """Sollevata quando un alias dynamic LUT non è risolvibile."""

    def __init__(self, alias: str, message: str | None = None):
        self.alias = alias
        super().__init__(message or f"Alias dynamic LUT non risolvibile: {alias!r}")


__all__ = ["ADPSession", "ADPLUTSyncError",
           "apply_lut_updates", "encode_with_dyn_lut"]
```

- [ ] **Step 2: Creare `tests/test_session.py` con import smoke test**

```python
"""Test suite per ADPSession (dynamic LUT core)."""
from __future__ import annotations

import pytest

from adp.session import ADPSession, ADPLUTSyncError


def test_import_smoke():
    """Import OK, classi disponibili."""
    assert ADPSession is not None
    assert ADPLUTSyncError is not None


def test_lut_sync_error_carries_alias():
    err = ADPLUTSyncError("_42")
    assert err.alias == "_42"
    assert "_42" in str(err)
```

- [ ] **Step 3: Aggiungere export in `src/adp/__init__.py`**

Aprire `src/adp/__init__.py` e aggiungere alla fine (o nella sezione import esistente):

```python
from adp.session import ADPSession, ADPLUTSyncError  # noqa: E402
```

E nella lista `__all__` (se presente) aggiungere `"ADPSession"`, `"ADPLUTSyncError"`.

- [ ] **Step 4: Eseguire i due test smoke**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_session.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py src/adp/__init__.py tests/test_session.py
git commit -m "feat(session): scaffolding ADPSession + ADPLUTSyncError"
```

---

## Task 2 — Persistence layer (load/save con flock)

**Files:**
- Modify: `src/adp/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Scrivere test failing per load/save**

Aggiungere a `tests/test_session.py`:

```python
import json
from pathlib import Path


def test_persistence_save_creates_file(tmp_path: Path):
    session_path = tmp_path / "lut.json"
    session = ADPSession(path=session_path, auto_save=False)
    session.save()
    assert session_path.exists()
    data = json.loads(session_path.read_text())
    assert data["version"] == 1
    assert data["entries"] == {}
    assert data["lru_order"] == []
    assert data["next_alias_id"] == 0


def test_persistence_roundtrip(tmp_path: Path):
    session_path = tmp_path / "lut.json"
    s1 = ADPSession(path=session_path, auto_save=False)
    s1._entries = {"_0": "admin", "_1": "dev"}
    s1._lru_order = ["_0", "_1"]
    s1._next_alias_id = 2
    s1.save()

    s2 = ADPSession(path=session_path, auto_save=False)
    assert s2._entries == {"_0": "admin", "_1": "dev"}
    assert s2._lru_order == ["_0", "_1"]
    assert s2._next_alias_id == 2


def test_persistence_missing_file_starts_empty(tmp_path: Path):
    session_path = tmp_path / "doesnotexist.json"
    s = ADPSession(path=session_path, auto_save=False)
    assert s._entries == {}
    assert s._lru_order == []
    assert s._next_alias_id == 0


def test_persistence_atomic_write_uses_temp_file(tmp_path: Path):
    """Verifica che save() usi temp file + rename."""
    session_path = tmp_path / "lut.json"
    s = ADPSession(path=session_path, auto_save=False)
    s._entries = {"_0": "x"}
    s.save()
    # Nessun file temp residuo
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 4 FAIL (ADPSession non ha `__init__` né `save()`).

- [ ] **Step 3: Implementare `ADPSession.__init__` e `save()/_load()` in `src/adp/session.py`**

Aggiungere alla classe (subito dopo la dichiarazione, all'interno del file):

```python
DEFAULT_PATH = "~/.adp/lut_state.json"
SCHEMA_VERSION = 1


class ADPSession:
    """Sessione ADP con dynamic LUT adattiva.

    Mantiene una LUT in-memory persistita su disco. Encoder analizza payload,
    aggiunge alias per chiavi/valori string ricorrenti, dichiara updates via
    prefisso `_lut_add={...}` o `_lut_reset=1` nel messaggio.
    """

    def __init__(
        self,
        path: str | Path | None = DEFAULT_PATH,
        max_entries: int = 256,
        static_lut: dict[str, str] | None = None,
        k_threshold: int = 2,
        auto_save: bool = True,
    ) -> None:
        # Path resolution
        if path is None:
            self._path: Path | None = None  # in-memory only
        elif isinstance(path, str):
            override = os.environ.get("ADP_LUT_PATH")
            chosen = override if override else path
            self._path = Path(chosen).expanduser()
        else:
            self._path = Path(path).expanduser()

        self._max_entries = max_entries
        self._static_lut = static_lut or {}
        self._k_threshold = k_threshold
        self._auto_save = auto_save

        # Mutable state
        self._entries: dict[str, str] = {}       # alias -> fullname
        self._inv: dict[str, str] = {}           # fullname -> alias (cached)
        self._lru_order: list[str] = []          # least-recent first
        self._next_alias_id: int = 0
        self._stats = {
            "hit_count": 0,
            "miss_count": 0,
            "evictions": 0,
        }

        if self._path is not None and self._path.exists():
            self._load()

        if auto_save and self._path is not None:
            atexit.register(self._atexit_save)

    def _load(self) -> None:
        assert self._path is not None
        with self._path.open("r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        version = data.get("version", 1)
        if version != SCHEMA_VERSION:
            # Backup vecchio e ripartiti vuoto
            backup = self._path.with_suffix(self._path.suffix + ".bak")
            self._path.rename(backup)
            return

        self._entries = dict(data.get("entries", {}))
        self._lru_order = list(data.get("lru_order", []))
        self._next_alias_id = int(data.get("next_alias_id", 0))
        self._stats.update(data.get("stats", {}))
        self._inv = {v: k for k, v in self._entries.items()}

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": SCHEMA_VERSION,
            "entries": dict(self._entries),
            "lru_order": list(self._lru_order),
            "next_alias_id": self._next_alias_id,
            "stats": dict(self._stats),
        }
        # Atomic write: temp + rename in stessa directory
        fd, tmp_path_str = tempfile.mkstemp(
            prefix=".lut_", suffix=".json.tmp", dir=str(self._path.parent)
        )
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(tmp_path, self._path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _atexit_save(self) -> None:
        try:
            self.save()
        except Exception:
            pass  # atexit: mai sollevare
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 6 PASSED (2 smoke + 4 persistence).

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_session.py
git commit -m "feat(session): persistence layer con flock e atomic write"
```

---

## Task 3 — LRU + entries data structure

**Files:**
- Modify: `src/adp/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Scrivere test failing per LRU operations**

Aggiungere a `tests/test_session.py`:

```python
def test_lru_add_entry_increments_alias_id():
    s = ADPSession(path=None, auto_save=False)
    alias = s._add_entry("admin")
    assert alias == "_0"
    assert s._entries == {"_0": "admin"}
    assert s._lru_order == ["_0"]
    assert s._next_alias_id == 1


def test_lru_add_existing_returns_same_alias_and_bumps():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")
    s._add_entry("dev")
    # Re-using "admin" deve restituire stesso alias e bumpare in LRU
    alias = s._mark_used("_0")
    assert alias == "_0"
    assert s._lru_order == ["_1", "_0"]


def test_lru_eviction_when_full(tmp_path):
    s = ADPSession(path=None, max_entries=3, auto_save=False)
    s._add_entry("a")
    s._add_entry("b")
    s._add_entry("c")
    assert len(s._entries) == 3
    s._add_entry("d")
    # "a" era il meno recente, dovrebbe essere evicted
    assert "_0" not in s._entries  # _0 era "a"
    assert s._entries == {"_1": "b", "_2": "c", "_3": "d"}
    assert s._lru_order == ["_1", "_2", "_3"]
    assert s._stats["evictions"] == 1


def test_lru_use_existing_then_eviction_keeps_used():
    s = ADPSession(path=None, max_entries=3, auto_save=False)
    s._add_entry("a")  # _0
    s._add_entry("b")  # _1
    s._add_entry("c")  # _2
    s._mark_used("_0")  # promote _0 a most-recent
    s._add_entry("d")   # _3, evict _1 (meno recente)
    assert "_1" not in s._entries
    assert s._entries == {"_0": "a", "_2": "c", "_3": "d"}
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_session.py::test_lru_add_entry_increments_alias_id -v
```

Expected: FAIL (`_add_entry` non esiste).

- [ ] **Step 3: Implementare `_add_entry`, `_mark_used`, `_evict_lru`**

Aggiungere alla classe `ADPSession` in `src/adp/session.py`:

```python
    def _add_entry(self, fullname: str) -> str:
        """Aggiungi nuovo entry alla LUT dinamica. Ritorna alias assegnato.

        Se LUT piena: evict LRU front prima.
        Se fullname già presente: ritorna alias esistente e lo bumpa.
        """
        if fullname in self._inv:
            existing = self._inv[fullname]
            self._mark_used(existing)
            return existing

        if len(self._entries) >= self._max_entries:
            self._evict_lru()

        alias = f"_{self._next_alias_id}"
        self._next_alias_id += 1
        self._entries[alias] = fullname
        self._inv[fullname] = alias
        self._lru_order.append(alias)
        return alias

    def _mark_used(self, alias: str) -> str:
        """Bumpa alias a most-recently-used. Ritorna alias (per chaining)."""
        if alias in self._lru_order:
            self._lru_order.remove(alias)
            self._lru_order.append(alias)
        return alias

    def _evict_lru(self) -> str | None:
        """Rimuovi l'entry meno recente. Ritorna alias rimosso o None se LUT vuota."""
        if not self._lru_order:
            return None
        alias = self._lru_order.pop(0)
        fullname = self._entries.pop(alias, None)
        if fullname is not None:
            self._inv.pop(fullname, None)
        self._stats["evictions"] += 1
        return alias
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 10 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_session.py
git commit -m "feat(session): LRU bounded con _add_entry/_mark_used/_evict_lru"
```

---

## Task 4 — Encoder: analisi payload e selezione candidati

**Files:**
- Modify: `src/adp/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Test failing per candidate detection**

Aggiungere a `tests/test_session.py`:

```python
def test_candidate_count_keys_only():
    s = ADPSession(path=None, auto_save=False)
    obj = {
        "user": {"id": 1, "role": "admin"},
        "other": {"id": 2, "role": "admin"},
    }
    counts = s._count_candidates(obj)
    # Conta chiavi: user 1, other 1, id 2, role 2
    # Conta valori string: admin 2
    assert counts["user"] == 1
    assert counts["other"] == 1
    assert counts["id"] == 2
    assert counts["role"] == 2
    assert counts["admin"] == 2


def test_candidate_skips_non_string_values():
    s = ADPSession(path=None, auto_save=False)
    obj = {"a": 1, "b": True, "c": None, "d": "text", "e": 3.14}
    counts = s._count_candidates(obj)
    # Solo chiavi (a,b,c,d,e) e valori string ("text")
    assert counts.get("text", 0) == 1
    assert 1 not in counts  # nessun int
    assert True not in counts  # nessun bool


def test_candidate_recursive_into_lists():
    s = ADPSession(path=None, auto_save=False)
    obj = {"users": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]}
    counts = s._count_candidates(obj)
    assert counts["id"] == 2
    assert counts["name"] == 2


def test_select_candidates_above_threshold():
    s = ADPSession(path=None, max_entries=256, k_threshold=2, auto_save=False)
    counts = {"admin": 3, "x": 1, "long_repeated_key": 5}
    selected = s._select_candidates(counts)
    # x sotto soglia esce
    assert "x" not in selected
    # admin e long_repeated_key passano la soglia
    assert "admin" in selected
    assert "long_repeated_key" in selected


def test_select_candidates_skips_already_in_static_lut():
    static = {"user": "u", "id": "i"}
    s = ADPSession(path=None, static_lut=static, auto_save=False)
    counts = {"user": 5, "admin": 3}
    selected = s._select_candidates(counts)
    assert "user" not in selected  # gestita da static
    assert "admin" in selected


def test_select_candidates_skips_negative_saving():
    s = ADPSession(path=None, k_threshold=2, auto_save=False)
    # "ok" (2 char) × 3 vs alias "_0" (2 char) + header "_0=ok;" (6 char)
    # saving = 3*2 - 3*2 - 6 = -6 < 0 → escluso
    counts = {"ok": 3}
    selected = s._select_candidates(counts)
    assert "ok" not in selected
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_session.py -v -k candidate
```

Expected: 6 FAIL (funzioni non esistono).

- [ ] **Step 3: Implementare `_count_candidates`, `_select_candidates`**

Aggiungere alla classe `ADPSession`:

```python
    def _count_candidates(self, obj: Any, counts: dict[str, int] | None = None) -> dict[str, int]:
        """Conta occorrenze di chiavi dict e valori string scalari, ricorsivamente."""
        if counts is None:
            counts = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str):
                    counts[k] = counts.get(k, 0) + 1
                self._count_candidates(v, counts)
        elif isinstance(obj, list):
            for v in obj:
                self._count_candidates(v, counts)
        elif isinstance(obj, str):
            counts[obj] = counts.get(obj, 0) + 1
        # bool/int/float/None/bytes: ignorati
        return counts

    def _select_candidates(self, counts: dict[str, int]) -> dict[str, int]:
        """Filtra candidati: soglia K, non in static LUT, saving char positivo."""
        selected: dict[str, int] = {}
        next_id = self._next_alias_id
        for fullname, count in counts.items():
            if count < self._k_threshold:
                continue
            if fullname in self._static_lut:
                continue
            if fullname in self._inv:
                # Già in dynamic LUT: non re-aggiungere, ma il caller può bumpare LRU
                continue
            # Cost-benefit char-based
            alias_len = len(f"_{next_id}")
            header_entry_len = alias_len + 1 + len(fullname) + 1  # "_N=fullname;"
            saving = count * len(fullname) - count * alias_len - header_entry_len
            if saving > 0:
                selected[fullname] = count
                next_id += 1  # simula incremento per stima alias futuri (approx)
        return selected
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 16 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_session.py
git commit -m "feat(session): payload analyzer (_count_candidates, _select_candidates)"
```

---

## Task 5 — Encoder: emit `_lut_add` prefix + alias substitution

**Files:**
- Modify: `src/adp/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Test failing per encode end-to-end**

Aggiungere a `tests/test_session.py`:

```python
def test_encode_no_repeats_no_prefix():
    s = ADPSession(path=None, auto_save=False)
    msg = s.encode({"id": 42})
    # Nessuna chiave ripetuta sopra soglia → nessun _lut_add
    assert "_lut_add" not in msg
    # Round-trip via standard adp.decode
    import adp
    assert adp.decode(msg) == {"id": 42}


def test_encode_with_repeats_adds_prefix():
    s = ADPSession(path=None, auto_save=False)
    obj = {
        "user1": {"role": "admin", "dept": "engineering"},
        "user2": {"role": "admin", "dept": "engineering"},
    }
    msg = s.encode(obj)
    assert "_lut_add" in msg
    # Dopo encode la LUT deve contenere "role" o "admin" o "dept" o "engineering"
    assert len(s._entries) >= 2


def test_encode_substitutes_aliases_in_payload():
    s = ADPSession(path=None, auto_save=False)
    obj = {
        "a": {"role": "admin"},
        "b": {"role": "admin"},
    }
    msg = s.encode(obj)
    # _0=role o _0=admin deve apparire nel prefix
    assert "role" in msg or "admin" in msg  # in prefix
    # Nel payload, almeno un alias _N deve essere usato
    import re
    assert re.search(r"_\d+=", msg) is not None


def test_encode_no_lut_flag_bypasses():
    s = ADPSession(path=None, auto_save=False)
    obj = {"role": "admin", "role2": "admin"}
    msg = s.encode(obj, no_lut=True)
    assert "_lut_add" not in msg
    # Anche con ripetizioni, no_lut bypassa la dynamic LUT
    assert "admin" in msg  # valore bare, non sostituito
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_session.py -v -k encode
```

Expected: 4 FAIL (no method `encode`).

- [ ] **Step 3: Implementare `encode()` e helper di sostituzione**

Aggiungere alla classe `ADPSession`:

```python
    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj a stringa ADP. Se no_lut=True bypassa dynamic LUT."""
        if no_lut:
            if self._static_lut:
                return adp.encode(obj, key_lut=self._static_lut)
            return adp.encode(obj)

        # 1. Conta candidati
        counts = self._count_candidates(obj)

        # 2. Bumpa LRU per quelli già in dynamic LUT
        for fullname in counts:
            if fullname in self._inv:
                self._mark_used(self._inv[fullname])

        # 3. Seleziona nuovi candidati
        new_candidates = self._select_candidates(counts)

        # 4. Aggiungi entry per ognuno
        new_aliases: dict[str, str] = {}  # alias -> fullname (per il prefix)
        for fullname in new_candidates:
            alias = self._add_entry(fullname)
            new_aliases[alias] = fullname

        # 5. Sostituisci nel payload (chiavi+valori string ricorrenti) usando
        #    static LUT + dynamic LUT
        substituted = self._substitute(obj)

        # 6. Compone messaggio finale
        payload_adp = adp.encode(substituted, key_lut=self._static_lut or None)
        if not new_aliases:
            return payload_adp

        # Prefix: _lut_add={alias=fullname;...};payload
        prefix_pairs = ";".join(f"{a}={self._quote_if_needed(f)}"
                                for a, f in new_aliases.items())
        prefix = f"_lut_add={{{prefix_pairs}}};"
        return prefix + payload_adp

    def _substitute(self, obj: Any) -> Any:
        """Ricorsivamente sostituisci chiavi e valori string usando dynamic LUT."""
        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                new_k = self._inv.get(k, k) if isinstance(k, str) else k
                out[new_k] = self._substitute(v)
            return out
        if isinstance(obj, list):
            return [self._substitute(v) for v in obj]
        if isinstance(obj, str):
            return self._inv.get(obj, obj)
        return obj

    @staticmethod
    def _quote_if_needed(s: str) -> str:
        """Quote un valore se contiene caratteri ADP-speciali."""
        if not s:
            return '""'
        if re.search(r"[\s,;=\[\]\{\}|\"#&~]", s):
            escaped = s.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return s
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 20 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_session.py
git commit -m "feat(session): encode() con _lut_add prefix injection"
```

---

## Task 6 — Decoder: parse `_lut_add`/`_lut_reset` e expand aliases

**Files:**
- Modify: `src/adp/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Test failing per decode end-to-end**

Aggiungere a `tests/test_session.py`:

```python
def test_decode_without_prefix():
    s = ADPSession(path=None, auto_save=False)
    import adp
    msg = adp.encode({"id": 42})
    out = s.decode(msg)
    assert out == {"id": 42}


def test_decode_applies_lut_add():
    s = ADPSession(path=None, auto_save=False)
    msg = "_lut_add={_0=admin;_1=role};u={_1=_0;name=alice}"
    out = s.decode(msg)
    # Dopo decode, lut deve contenere le nuove entry
    assert s._entries == {"_0": "admin", "_1": "role"}
    # Payload espanso correttamente
    assert out == {"u": {"role": "admin", "name": "alice"}}


def test_decode_round_trip_two_sessions():
    a = ADPSession(path=None, auto_save=False)
    b = ADPSession(path=None, auto_save=False)

    obj = {
        "user": {"role": "admin", "dept": "eng"},
        "user2": {"role": "admin", "dept": "eng"},
    }
    msg = a.encode(obj)
    out = b.decode(msg)
    assert out == obj
    # Stato LUT sincronizzato
    assert a._entries == b._entries
    assert a._lru_order == b._lru_order


def test_decode_unknown_alias_raises_sync_error():
    s = ADPSession(path=None, auto_save=False)
    msg = "_0={id=42}"  # _0 non in lut
    with pytest.raises(ADPLUTSyncError) as exc_info:
        s.decode(msg)
    assert exc_info.value.alias == "_0"


def test_decode_lut_reset_clears_state():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")  # _0=admin
    s._add_entry("dev")    # _1=dev
    msg = "_lut_reset=1;id=42"
    out = s.decode(msg)
    assert s._entries == {}
    assert s._lru_order == []
    assert out == {"id": 42}
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_session.py -v -k decode
```

Expected: 5 FAIL.

- [ ] **Step 3: Implementare `decode()` e helper di expand**

Aggiungere alla classe `ADPSession`:

```python
    _PREFIX_RE = re.compile(r"^(_lut_(?:add|reset))=([^;]+);")

    def decode(self, msg: str) -> Any:
        """Decode messaggio ADP. Applica _lut_reset, _lut_add se presenti,
        poi espande gli alias dynamic LUT nel payload risultante."""
        rest = msg

        # Estrai tutti i prefissi riservati top-level (max 1 di ciascun tipo)
        seen: set[str] = set()
        while True:
            m = self._PREFIX_RE.match(rest)
            if not m:
                break
            key, value = m.group(1), m.group(2)
            if key in seen:
                # Duplicate prefix: errore di formato
                raise adp.ADPParseError(f"Prefisso duplicato: {key!r}")
            seen.add(key)
            if key == "_lut_reset":
                if value not in ("0", "1"):
                    raise adp.ADPParseError(f"_lut_reset valore invalido: {value!r}")
                if value == "1":
                    self._apply_lut_reset()
            elif key == "_lut_add":
                self._apply_lut_add(value)
            rest = rest[m.end():]

        # Decoda il payload rimanente con lo standard parser ADP
        if not rest:
            return {}
        payload = adp.decode(rest, key_lut=self._static_lut or None)

        # Espandi alias dynamic LUT nel risultato
        return self._expand(payload)

    def _apply_lut_reset(self) -> None:
        self._entries.clear()
        self._inv.clear()
        self._lru_order.clear()
        # next_alias_id NON resettato: garantisce uniqueness storica

    def _apply_lut_add(self, mapping_str: str) -> None:
        """mapping_str è il body di `{...}` (senza graffe esterne, da regex match).

        Esempio: `_0=admin;_1=role`
        """
        # Sintassi: la regex matcha tutto fino a `;` top-level. Recuperiamo il
        # blocco con le graffe: il match originale ha `{_0=admin;_1=role}` ma
        # il valore catturato è `{_0=admin;_1=role}` se la regex ammette tutto
        # tra `=` e `;`. Per parsing usiamo adp.decode su `{<mapping_str>}`.
        # Però la nostra regex stoppa al primo `;` interno, non funziona per
        # mappe annidate. Servono parentesi-aware parsing.
        raise NotImplementedError("Vedi Step 4 — _PREFIX_RE va sostituita")
```

- [ ] **Step 4: Sostituire la regex naïve con un estrattore parentesi-aware**

La regex `_PREFIX_RE` con `[^;]+` non gestisce mappe con `;` annidato. Sostituire l'approccio:

Modificare `src/adp/session.py`: rimpiazzare `_PREFIX_RE` e i blocchi in `decode()` con:

```python
    _RESERVED_KEYS = ("_lut_reset", "_lut_add")

    def decode(self, msg: str) -> Any:
        """Decode messaggio ADP. Applica prefissi _lut_reset/_lut_add se presenti,
        poi espande alias dynamic LUT nel payload risultante."""
        rest = msg
        seen: set[str] = set()
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
            rest = rest[consumed:]

        if not rest:
            return {}
        payload = adp.decode(rest, key_lut=self._static_lut or None)
        return self._expand(payload)

    def _match_reserved_prefix(self, s: str) -> tuple[str, str, int] | None:
        """Se `s` inizia con `<reserved_key>=<value>;`, ritorna
        (key, value_str, num_chars_consumed). Altrimenti None.

        Il valore può essere una mappa `{...}` con `;` interni: facciamo
        parentesi-tracking per trovare il `;` top-level finale.
        """
        for key in self._RESERVED_KEYS:
            head = f"{key}="
            if s.startswith(head):
                value_start = len(head)
                end = self._find_top_level_semicolon(s, value_start)
                if end is None:
                    return None
                value_str = s[value_start:end]
                return (key, value_str, end + 1)
        return None

    @staticmethod
    def _find_top_level_semicolon(s: str, start: int) -> int | None:
        """Trova il primo `;` a profondità zero (fuori da `{}`, `[]`, `""`).
        Ritorna l'indice del `;` o None se non trovato."""
        depth = 0
        in_string = False
        i = start
        while i < len(s):
            c = s[i]
            if in_string:
                if c == "\\" and i + 1 < len(s):
                    i += 2
                    continue
                if c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c in "{[":
                    depth += 1
                elif c in "}]":
                    depth -= 1
                elif c == ";" and depth == 0:
                    return i
            i += 1
        return None

    def _apply_lut_reset(self) -> None:
        self._entries.clear()
        self._inv.clear()
        self._lru_order.clear()

    def _apply_lut_add(self, value_str: str) -> None:
        """value_str è `{alias=fullname;alias=fullname}` (con graffe)."""
        if not (value_str.startswith("{") and value_str.endswith("}")):
            raise adp.ADPParseError(f"_lut_add value malformed: {value_str!r}")
        mapping = adp.decode(f"m={value_str}")
        if not isinstance(mapping, dict) or "m" not in mapping:
            raise adp.ADPParseError(f"_lut_add value not a mapping: {value_str!r}")
        for alias, fullname in mapping["m"].items():
            if not isinstance(alias, str) or not isinstance(fullname, str):
                raise adp.ADPParseError(
                    f"_lut_add entry malformed: {alias!r}={fullname!r}")
            if alias in self._entries:
                continue  # idempotente
            if len(self._entries) >= self._max_entries:
                self._evict_lru()
            self._entries[alias] = fullname
            self._inv[fullname] = alias
            self._lru_order.append(alias)
            # Tieni next_alias_id sincronizzato (massimo + 1)
            try:
                num = int(alias.lstrip("_"))
                if num >= self._next_alias_id:
                    self._next_alias_id = num + 1
            except ValueError:
                pass

    def _expand(self, obj: Any) -> Any:
        """Espandi alias dynamic LUT nelle chiavi e valori string del payload."""
        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                new_k = self._expand_token(k) if isinstance(k, str) else k
                out[new_k] = self._expand(v)
            return out
        if isinstance(obj, list):
            return [self._expand(v) for v in obj]
        if isinstance(obj, str):
            return self._expand_token(obj)
        return obj

    def _expand_token(self, token: str) -> str:
        """Se token è un alias `_N` in dynamic LUT, espandi a fullname.
        Se è un alias `_N` MA non in LUT, solleva ADPLUTSyncError.
        Altrimenti ritorna token invariato."""
        if not (token.startswith("_") and len(token) > 1):
            return token
        if token[1:].isdigit():
            if token in self._entries:
                self._stats["hit_count"] += 1
                self._mark_used(token)
                return self._entries[token]
            raise ADPLUTSyncError(token)
        return token
```

E rimuovere la dichiarazione precedente `_PREFIX_RE` (non più usata).

- [ ] **Step 5: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 25 PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/adp/session.py tests/test_session.py
git commit -m "feat(session): decode() con _lut_add/_lut_reset + alias expansion"
```

---

## Task 7 — `encode_reset` + `reset` + `stats`

**Files:**
- Modify: `src/adp/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Test failing**

Aggiungere a `tests/test_session.py`:

```python
def test_encode_reset_emits_reset_prefix():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")
    s._add_entry("dev")
    msg = s.encode_reset({"id": 1})
    assert msg.startswith("_lut_reset=1;")
    # Anche lato locale lo state è pulito (encode_reset pulisce SENDER)
    assert s._entries == {}


def test_reset_clears_only_local_state():
    s = ADPSession(path=None, auto_save=False)
    s._add_entry("admin")
    assert len(s._entries) == 1
    s.reset()
    assert s._entries == {}
    assert s._lru_order == []
    # next_alias_id NON resettato
    assert s._next_alias_id == 1


def test_stats_reports_real_events():
    a = ADPSession(path=None, auto_save=False)
    b = ADPSession(path=None, auto_save=False)
    obj = {"x": {"role": "admin", "k": "v"}, "y": {"role": "admin", "k": "v"}}
    msg = a.encode(obj)
    b.decode(msg)
    st = b.stats()
    assert st["entries_count"] >= 1
    assert st["hit_count"] >= 2  # almeno role o admin espanso 2 volte
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_session.py -v -k "encode_reset or reset or stats"
```

Expected: 3 FAIL.

- [ ] **Step 3: Implementare `encode_reset`, `reset`, `stats`**

Aggiungere alla classe `ADPSession`:

```python
    def reset(self) -> None:
        """Pulisci stato locale. NON propaga al receiver (usa encode_reset)."""
        self._entries.clear()
        self._inv.clear()
        self._lru_order.clear()

    def encode_reset(self, obj: Any) -> str:
        """Encode forzando _lut_reset=1 nel prefix.

        Pulisce ANCHE lo stato locale (mittente e destinatario allineati).
        Il payload risultante non usa alias dynamic.
        """
        self.reset()
        payload = adp.encode(obj, key_lut=self._static_lut or None)
        return "_lut_reset=1;" + payload

    def stats(self) -> dict:
        """Dict diagnostico."""
        return {
            "entries_count": len(self._entries),
            "max_entries": self._max_entries,
            "hit_count": self._stats["hit_count"],
            "miss_count": self._stats["miss_count"],
            "evictions": self._stats["evictions"],
        }
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 28 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_session.py
git commit -m "feat(session): encode_reset, reset, stats"
```

---

## Task 8 — API low-level + concurrent locking test

**Files:**
- Modify: `src/adp/session.py`
- Modify: `src/adp/__init__.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Test failing per low-level + locking**

Aggiungere a `tests/test_session.py`:

```python
def test_apply_lut_updates_extracts_prefix():
    from adp.session import apply_lut_updates
    msg = "_lut_add={_0=admin};u={i=42;r=_0}"
    payload_str, updated_lut = apply_lut_updates(msg, {})
    assert payload_str == "u={i=42;r=_0}"
    assert updated_lut == {"_0": "admin"}


def test_apply_lut_updates_handles_reset():
    from adp.session import apply_lut_updates
    msg = "_lut_reset=1;u={i=42}"
    payload_str, updated_lut = apply_lut_updates(msg, {"_0": "old"})
    assert payload_str == "u={i=42}"
    assert updated_lut == {}


def test_encode_with_dyn_lut_returns_msg_and_updated_lut():
    from adp.session import encode_with_dyn_lut
    obj = {"a": {"role": "admin"}, "b": {"role": "admin"}}
    msg, new_lut = encode_with_dyn_lut(obj, {}, k_threshold=2, max_entries=256)
    assert "_lut_add" in msg
    assert len(new_lut) >= 1


def test_concurrent_save_no_corruption(tmp_path):
    """Due session che scrivono in parallelo non corrompono il file."""
    import threading
    path = tmp_path / "lut.json"
    s1 = ADPSession(path=path, auto_save=False)
    s2 = ADPSession(path=path, auto_save=False)
    s1._add_entry("a")
    s2._add_entry("b")

    errors = []
    def writer(s):
        try:
            for _ in range(20):
                s.save()
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=writer, args=(s1,))
    t2 = threading.Thread(target=writer, args=(s2,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert errors == []
    # File parsabile
    data = json.loads(path.read_text())
    assert data["version"] == 1
```

- [ ] **Step 2: Eseguire test (devono fallire)**

```bash
uv run pytest tests/test_session.py -v -k "apply_lut or encode_with_dyn or concurrent"
```

Expected: 4 FAIL.

- [ ] **Step 3: Implementare le funzioni low-level (module-level)**

Aggiungere in `src/adp/session.py` (in fondo al file, fuori dalla classe):

```python
def apply_lut_updates(msg: str, lut: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Estrae prefissi _lut_reset/_lut_add da msg e ritorna (payload_pulito,
    lut_aggiornata).

    Helper stateless per integrazioni custom. Non valida né bumpa LRU.
    """
    # Riusa la logica della session creando una mini-istanza in-memory
    temp = ADPSession(path=None, auto_save=False, max_entries=10_000)
    temp._entries = dict(lut)
    temp._inv = {v: k for k, v in lut.items()}
    temp._lru_order = list(lut.keys())

    rest = msg
    while True:
        match = temp._match_reserved_prefix(rest)
        if match is None:
            break
        key, value_str, consumed = match
        if key == "_lut_reset" and value_str == "1":
            temp._apply_lut_reset()
        elif key == "_lut_add":
            temp._apply_lut_add(value_str)
        rest = rest[consumed:]

    return rest, dict(temp._entries)


def encode_with_dyn_lut(
    obj: Any,
    dyn_lut: dict[str, str],
    k_threshold: int = 2,
    max_entries: int = 256,
) -> tuple[str, dict[str, str]]:
    """Encode obj usando dyn_lut. Ritorna (msg_con_prefix, lut_aggiornata)."""
    temp = ADPSession(
        path=None,
        auto_save=False,
        max_entries=max_entries,
        k_threshold=k_threshold,
    )
    temp._entries = dict(dyn_lut)
    temp._inv = {v: k for k, v in dyn_lut.items()}
    temp._lru_order = list(dyn_lut.keys())
    if dyn_lut:
        max_id = max(
            (int(a.lstrip("_")) for a in dyn_lut if a.startswith("_") and a[1:].isdigit()),
            default=-1,
        )
        temp._next_alias_id = max_id + 1

    msg = temp.encode(obj)
    return msg, dict(temp._entries)
```

- [ ] **Step 4: Esportare in `src/adp/__init__.py`**

Aggiornare l'import in `src/adp/__init__.py`:

```python
from adp.session import (
    ADPSession,
    ADPLUTSyncError,
    apply_lut_updates,
    encode_with_dyn_lut,
)
```

E aggiungere a `__all__` se presente: `"apply_lut_updates"`, `"encode_with_dyn_lut"`.

- [ ] **Step 5: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 32 PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/adp/session.py src/adp/__init__.py tests/test_session.py
git commit -m "feat(session): API low-level + concurrent save safety"
```

---

## Task 9 — Round-trip stress test (sessione lunga 2 agenti)

**Files:**
- Modify: `tests/test_session.py`

- [ ] **Step 1: Test failing per stress test**

Aggiungere a `tests/test_session.py`:

```python
def test_round_trip_20_messages_two_agents(tmp_path):
    """Scambio bidirezionale 20 messaggi, LUT cresce, decode resta consistente."""
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a = ADPSession(path=a_path, max_entries=32, auto_save=False)
    b = ADPSession(path=b_path, max_entries=32, auto_save=False)

    payloads = []
    for i in range(20):
        if i % 2 == 0:
            obj = {
                "user": {"id": i, "role": "admin", "dept": "engineering"},
                "user2": {"id": i + 100, "role": "admin", "dept": "engineering"},
                "metadata": {"src": "agent_a", "src2": "agent_a"},
            }
            sender, receiver = a, b
        else:
            obj = {
                "status": "ok",
                "status2": "ok",
                "result": {"value": i, "kind": "report", "kind2": "report"},
            }
            sender, receiver = b, a
        msg = sender.encode(obj)
        out = receiver.decode(msg)
        assert out == obj, f"mismatch at msg {i}"
        payloads.append(obj)

    # Stati LUT sincronizzati
    assert a._entries == b._entries
    assert a._lru_order == b._lru_order


def test_persistence_after_long_session(tmp_path):
    """Save dopo 20 msg, reload, encode/decode usa stato persistito."""
    path = tmp_path / "lut.json"
    s = ADPSession(path=path, max_entries=32, auto_save=False)
    for i in range(20):
        s.encode({"user": {"id": i, "role": "admin"}, "u2": {"id": i + 1, "role": "admin"}})
    s.save()
    entries_before = dict(s._entries)
    lru_before = list(s._lru_order)

    s2 = ADPSession(path=path, max_entries=32, auto_save=False)
    assert s2._entries == entries_before
    assert s2._lru_order == lru_before
```

- [ ] **Step 2: Eseguire i test**

```bash
uv run pytest tests/test_session.py -v
```

Expected: 34 PASSED (tutti).

Se test 33 fallisce con dati mismatch, verificare logica eviction e bumping LRU.

- [ ] **Step 3: Commit**

```bash
git add tests/test_session.py
git commit -m "test(session): stress test round-trip 20 msg + persistenza lunga"
```

---

## Task 10 — Documentazione module-level + smoke test full suite

**Files:**
- Modify: `src/adp/session.py`

- [ ] **Step 1: Verificare che tutta la test suite del progetto passi**

```bash
uv run pytest -q
```

Expected: tutti i test esistenti + 34 nuovi → totale ≥ 156 passed (122 pre-esistenti + 34 nuovi).

Se test esistenti si rompono, indagare regressione: `ADPSession` è additiva, non deve toccare moduli esistenti.

- [ ] **Step 2: Aggiungere docstring di modulo arricchito a `src/adp/session.py`**

Sostituire il docstring iniziale di `src/adp/session.py` (le righe `"""ADPSession ... spec"""`) con:

```python
"""ADPSession — Dynamic LUT adattiva HPACK-style per ADP.

Mantiene una look-up table dinamica condivisa tra agenti, sincronizzata via
prefissi in-band (`_lut_add={...}`, `_lut_reset=1`) nei messaggi ADP,
persistita localmente in `~/.adp/lut_state.json` (override via parametro
`path` o env `ADP_LUT_PATH`).

Architettura: HPACK-style (RFC 7541). Eviction LRU bounded (default 256
entries), deterministica side-local. Cost-benefit char-based decide se
aggiungere un entry: candidato aggiunto solo se savings > overhead.

Esempio uso base:

    import adp

    session = adp.ADPSession()  # carica/crea ~/.adp/lut_state.json

    # Mittente A
    msg = session.encode({
        "user": {"id": 42, "role": "admin", "dept": "engineering"},
        "user2": {"id": 43, "role": "admin", "dept": "engineering"},
    })
    # msg contiene _lut_add={_0=role;_1=admin;...};u={...} ecc.

    # Destinatario B (con la propria ADPSession)
    obj = session.decode(msg)
    # Lo stato LUT di entrambi è ora sincronizzato

Spec: docs/superpowers/specs/2026-05-24-dynamic-lut-design.md
"""
```

- [ ] **Step 3: Esegui suite finale**

```bash
uv run pytest -q
```

Expected: tutto verde.

- [ ] **Step 4: Commit finale**

```bash
git add src/adp/session.py
git commit -m "docs(session): docstring modulo con esempio uso base"
```

---

## Self-review (eseguito post-stesura del plan)

**1. Spec coverage (Core only, escluse Est. 1-5):**

| Spec requirement | Task |
|---|---|
| `ADPSession.__init__` con parametri core | Task 2, 7 |
| `encode()`/`decode()` | Task 5, 6 |
| `save()`/`reset()`/`encode_reset()`/`stats()` | Task 2, 7 |
| Persistenza JSON con flock + atomic | Task 2 |
| LRU bounded + deterministica | Task 3 |
| Eager learner + cost-benefit char-based | Task 4, 5 |
| `_lut_add`/`_lut_reset` prefix injection | Task 5, 6 |
| `ADPLUTSyncError` | Task 1, 6 |
| API low-level `apply_lut_updates`, `encode_with_dyn_lut` | Task 8 |
| 12 categorie test core (spec) | distribuite Task 1-9 |
| Static LUT precedenza | Task 4 |
| Locking concorrente | Task 8 |
| Stress test 20 msg 2 agents | Task 9 |
| Docstring modulo | Task 10 |
| Esportazione `__init__.py` | Task 1, 8 |

Tutto coperto.

**2. Placeholder scan:**

- Nessun TBD/TODO
- Nessun "implement later"
- Tutti gli step hanno codice o comandi concreti
- Step 3 del Task 6 contiene una `raise NotImplementedError("Vedi Step 4")` come marker intenzionale di TDD-walking: lo Step 4 successivo lo sostituisce. Questo è un pattern legittimo (refactor incremental), non un placeholder.

**3. Type consistency:**

- `_entries: dict[str, str]` ovunque (alias -> fullname)
- `_inv: dict[str, str]` (fullname -> alias)
- `_lru_order: list[str]` con convention "meno recente first"
- `_next_alias_id: int` sequenziale, mai resettato salvo schema bump
- `_stats` dict con chiavi fisse: `hit_count`, `miss_count`, `evictions`
- `ADPLUTSyncError(alias: str)` consistente
- Funzioni low-level `apply_lut_updates` e `encode_with_dyn_lut` consistenti con la classe (riusano internamente)

Nessun bug di consistenza nominale.

**4. Deviazioni dalla spec:**

Documentate nella sezione "Deviazione consapevole" all'inizio del plan: uso di `_lut_add`/`_lut_reset` invece di `_lut+`/`_lut!` per evitare modifiche al parser. Costo: 2-3 token in più per messaggio con update. Beneficio: zero rischio regressione sul parser.

## Note per i plan successivi (Est. 1-5)

Quando si implementerà:

- **Est. 1 (Tokenizer-aware):** sostituire `_select_candidates` cost-benefit char-based con un `TokenizerCostEstimator` passato a `__init__`. Backward-compat: default resta char-based.
- **Est. 2 (Capability):** aggiungere `_caps` come terzo prefisso riservato in `_RESERVED_KEYS`, gestione `peer_caps`.
- **Est. 3 (TPD promotion):** aggiungere ring buffer di msg raw inviati e metodo `_run_tpd_promotion()`.
- **Est. 4 (Warmup):** aggiungere metodo `warmup()` che riusa `_count_candidates` su corpus.
- **Est. 5 (Diff encoding):** aggiungere `_base`/`_diff`/`_diff_reset` come prefissi riservati + modulo `diff.py`. Bumpare `SCHEMA_VERSION` a 2.

Tutti additivi: il core resta stabile.
