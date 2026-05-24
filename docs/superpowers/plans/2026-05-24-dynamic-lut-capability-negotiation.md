# Dynamic LUT — Capability negotiation (Plan 5 di 6, Est. 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implementare handshake `_caps={...}` tra agenti per scoprire se la controparte supporta dynamic LUT/diff, evitando errori silenziosi quando un receiver non-aware riceve `_lut_add`.

**Architecture:** sender prepende `_caps={dyn_lut=1;max_entries=N;diff=1}` al primo messaggio. Receiver risponde con il proprio `_caps=` nel primo reply. Se sender non vede caps di ritorno entro `caps_timeout_msgs` (default 3): assume controparte non-aware, disabilita automaticamente dyn LUT e diff per quel canale. Riusa prefix riservato top-level (esiste già il pattern con `_lut_reset`/`_lut_add`/`_base`/`_diff`/`_diff_reset`).

**Tech Stack:** Python 3.11+, stdlib, pytest. Nessuna dipendenza nuova.

---

## Scope

**Incluso:**
- Nuovi reserved keys: `_caps`
- Param `ADPSession(announce_caps: bool = True, caps_timeout_msgs: int = 3)`
- Stato: `_peer_caps`, `_caps_announced` (bool), `_caps_outbound_count` (counter)
- Encoder: prepende `_caps=` al primo messaggio se `announce_caps=True` AND non ancora annunciato
- Decoder: estrae `_caps=` se presente, salva in `_peer_caps`
- Auto-degrade: se dopo `caps_timeout_msgs` send senza vedere peer caps → disable `enable_diff` e `dyn_lut` localmente (passa a `no_lut=True` automatic)
- `reset_caps()` per forzare re-negoziazione
- 5 test categorie

**Escluso:**
- Multi-peer caps tracking (1 peer per session)
- Caps version negotiation (solo v1 hardcoded)
- Caps richiamabile a metà sessione oltre `reset_caps()`
- Capability per feature singola (es. solo dyn LUT ma non diff)

## File map

| Path | Operazione | Responsabilità |
|---|---|---|
| `src/adp/session.py` | modifica | `_caps` reserved key, params, state, auto-degrade logic |
| `tests/test_caps.py` | crea | 5 test categorie |

---

## Task 1 — Scaffolding: params, state, `reset_caps()`, `peer_caps` property

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Create: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_caps.py`

- [ ] **Step 1: Crea `tests/test_caps.py`**

```python
"""Test suite per capability negotiation (Est. 2)."""
from __future__ import annotations

import pytest

from adp.session import ADPSession


def test_session_default_caps_params():
    s = ADPSession(path=None, auto_save=False)
    assert s._announce_caps is True
    assert s._caps_timeout_msgs == 3


def test_session_caps_params_configurable():
    s = ADPSession(path=None, auto_save=False,
                   announce_caps=False, caps_timeout_msgs=5)
    assert s._announce_caps is False
    assert s._caps_timeout_msgs == 5


def test_session_peer_caps_initially_none():
    s = ADPSession(path=None, auto_save=False)
    assert s.peer_caps is None


def test_session_reset_caps_clears_state():
    s = ADPSession(path=None, auto_save=False)
    s._peer_caps = {"dyn_lut": 1, "max_entries": 256}
    s._caps_announced = True
    s._caps_outbound_count = 5
    s.reset_caps()
    assert s.peer_caps is None
    assert s._caps_announced is False
    assert s._caps_outbound_count == 0
```

- [ ] **Step 2: Run failing**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_caps.py -v
```

Expected: 4 FAIL (params + state non esistono).

- [ ] **Step 3: Modificare `src/adp/session.py`**

A) Modificare firma `ADPSession.__init__` per aggiungere `announce_caps` e `caps_timeout_msgs` dopo `cost_estimator`:

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
        announce_caps: bool = True,
        caps_timeout_msgs: int = 3,
    ) -> None:
```

B) Nel corpo di `__init__`, DOPO `self._cost_estimator = cost_estimator` aggiungere:

```python
        # Capability negotiation state (Est. 2)
        self._announce_caps = announce_caps
        self._caps_timeout_msgs = caps_timeout_msgs
        self._peer_caps: dict | None = None
        self._caps_announced = False
        self._caps_outbound_count = 0
```

C) Aggiungere subito dopo `stats()` (o vicino agli altri metodi pubblici della classe) la property + metodo:

```python
    @property
    def peer_caps(self) -> dict | None:
        """Capability annunciate dalla controparte (None se mai negoziato)."""
        return self._peer_caps

    def reset_caps(self) -> None:
        """Pulisce lo stato di capability negotiation; forza re-annuncio."""
        self._peer_caps = None
        self._caps_announced = False
        self._caps_outbound_count = 0
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_caps.py -v
uv run pytest -q
```

Expected: test_caps.py 4 PASSED, full suite 219 PASSED (215 baseline + 4 nuovi).

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_caps.py
git commit -m "feat(session): scaffolding capability negotiation (state + reset_caps)"
```

---

## Task 2 — Encoder: prepend `_caps=` al primo messaggio

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_caps.py`

- [ ] **Step 1: Test failing**

Aggiungere a `tests/test_caps.py`:

```python
def test_encode_first_message_includes_caps_prefix():
    """Primo encode include _caps={dyn_lut=1;max_entries=256;diff=1} prefix."""
    s = ADPSession(path=None, auto_save=False, announce_caps=True)
    msg = s.encode({"a": 1})
    assert "_caps={" in msg
    assert "dyn_lut=1" in msg
    assert "max_entries=256" in msg
    assert "diff=1" in msg
    # Stato aggiornato
    assert s._caps_announced is True


def test_encode_subsequent_messages_no_caps_prefix():
    """Solo il primo msg include _caps. Successivi no."""
    s = ADPSession(path=None, auto_save=False, announce_caps=True)
    s.encode({"a": 1})  # primo: include caps
    msg2 = s.encode({"b": 2})
    assert "_caps=" not in msg2


def test_encode_announce_caps_false_skips_prefix():
    """announce_caps=False non emette mai caps."""
    s = ADPSession(path=None, auto_save=False, announce_caps=False)
    msg = s.encode({"a": 1})
    assert "_caps=" not in msg
    assert s._caps_announced is False
```

- [ ] **Step 2: Run failing**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_caps.py -v -k "caps_prefix or subsequent or false"
```

Expected: 3 FAIL.

- [ ] **Step 3: Modificare `encode()` per emettere caps prefix al primo msg**

In `src/adp/session.py`, trovare il metodo `encode()`. Modificarlo per gestire l'annuncio caps:

Trova la riga `def encode(self, obj: Any, *, no_lut: bool = False) -> str:` e l'intero corpo del metodo. Modificare l'inizio del metodo (subito dopo la docstring esistente) PRIMA del blocco `if no_lut:` aggiungendo la generazione del prefisso caps:

Aggiungi un helper privato `_build_caps_prefix` e modifica encode per usarlo. Sostituisci INTERAMENTE il metodo `encode()` con:

```python
    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj a stringa ADP.

        - Se `announce_caps=True` AND non ancora annunciato: prepende
          `_caps={dyn_lut=1;max_entries=N;diff=1}` al messaggio.
        - Se `no_lut=True`: bypassa dynamic LUT (e diff encoding).
        - Se `enable_diff=True` e abbiamo un baseline last_sent: calcola diff,
          se conviene emette _base=ID;_diff={...}, altrimenti emette full.
        - Aggiorna sempre _last_sent_payload + _last_sent_base_id col payload corrente.
        """
        caps_prefix = self._build_caps_prefix()

        if no_lut:
            self._last_sent_payload = obj
            self._last_sent_base_id = self._compute_base_id(obj)
            if self._static_lut:
                payload = adp.encode(obj, key_lut=self._static_lut)
            else:
                payload = adp.encode(obj)
            self._caps_outbound_count += 1
            return caps_prefix + payload

        full_msg = self._encode_full_with_lut(obj)

        diff_msg: str | None = None
        if self._enable_diff and self._last_sent_payload is not None:
            diff_dict = compute_diff(self._last_sent_payload, obj)
            if diff_dict:
                diff_payload = adp.encode(diff_dict, key_lut=self._static_lut or None)
                candidate = f"_base={self._last_sent_base_id};_diff={diff_payload};"
                if len(candidate) < self._diff_threshold * len(full_msg):
                    diff_msg = candidate

        self._last_sent_payload = obj
        self._last_sent_base_id = self._compute_base_id(obj)

        chosen = diff_msg if diff_msg is not None else full_msg
        self._caps_outbound_count += 1
        return caps_prefix + chosen

    def _build_caps_prefix(self) -> str:
        """Costruisce il prefix _caps= se va annunciato, '' altrimenti.

        Marca _caps_announced=True dopo l'emissione.
        """
        if not self._announce_caps or self._caps_announced:
            return ""
        diff_flag = 1 if self._enable_diff else 0
        prefix = (
            f"_caps={{dyn_lut=1;max_entries={self._max_entries};"
            f"diff={diff_flag}}};"
        )
        self._caps_announced = True
        return prefix
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_caps.py -v
uv run pytest -q
```

Expected: test_caps.py 7 PASSED, full suite 222 PASSED.

NOTA: alcuni test pre-esistenti potrebbero rompersi se ora ogni primo encode include `_caps=`. Investigare e correggere. Soluzione probabile: i test pre-esistenti devono o passare `announce_caps=False`, oppure il loro decoder deve ignorare `_caps=` (Task 3 gestirà questo).

Se test pre-esistenti rotti: modificarli per passare `announce_caps=False` quando il prefix `_caps=` interferisce con assertion sul contenuto del msg. Documentare i fix nel commit message.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_caps.py
git commit -m "feat(session): encoder emette _caps= prefix al primo msg"
```

---

## Task 3 — Decoder: parse `_caps=` e popola `peer_caps`

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_caps.py`

- [ ] **Step 1: Test failing**

Aggiungere a `tests/test_caps.py`:

```python
def test_decode_extracts_caps_and_populates_peer_caps():
    """Receiver decode msg con _caps=, popola peer_caps."""
    sender = ADPSession(path=None, auto_save=False, announce_caps=True)
    receiver = ADPSession(path=None, auto_save=False, announce_caps=False)
    msg = sender.encode({"a": 1})
    out = receiver.decode(msg)
    assert out == {"a": 1}  # payload decodificato correttamente
    assert receiver.peer_caps is not None
    assert receiver.peer_caps.get("dyn_lut") == 1
    assert receiver.peer_caps.get("max_entries") == 256


def test_decode_caps_idempotent_subsequent_msgs():
    """Decoded msg senza _caps non altera peer_caps esistente."""
    sender = ADPSession(path=None, auto_save=False, announce_caps=True)
    receiver = ADPSession(path=None, auto_save=False, announce_caps=False)
    receiver.decode(sender.encode({"a": 1}))
    caps_before = dict(receiver.peer_caps)
    receiver.decode(sender.encode({"b": 2}))
    assert receiver.peer_caps == caps_before
```

- [ ] **Step 2: Run failing**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_caps.py -v -k "decode_extracts or decode_caps_idempotent"
```

Expected: 2 FAIL.

- [ ] **Step 3: Modificare `_RESERVED_KEYS` e `decode()` per gestire `_caps`**

A) Aggiungere `_caps` a `_RESERVED_KEYS`. Trovare:

```python
    _RESERVED_KEYS = ("_lut_reset", "_lut_add", "_diff_reset", "_base", "_diff")
```

Sostituire con:

```python
    _RESERVED_KEYS = ("_caps", "_lut_reset", "_lut_add", "_diff_reset", "_base", "_diff")
```

B) Nel metodo `decode()`, trovare il blocco `while True: prefix_match = ...`. Subito DOPO il check `if key == "_lut_reset":` (e prima di `elif key == "_lut_add":`), aggiungere il branch:

```python
            elif key == "_caps":
                # Parsa il valore come mappa ADP
                caps_payload_str = f"c={value_str}"
                parsed_caps = adp.decode(caps_payload_str,
                                         key_lut=self._static_lut or None)
                if isinstance(parsed_caps, dict) and "c" in parsed_caps:
                    self._peer_caps = parsed_caps["c"]
```

NOTA: posiziona questo `elif` DENTRO il loop while di parsing prefix, in modo che venga processato con gli altri reserved keys.

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_caps.py -v
uv run pytest -q
```

Expected: test_caps.py 9 PASSED, full suite 224 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_caps.py
git commit -m "feat(session): decoder estrae _caps e popola peer_caps"
```

---

## Task 4 — Auto-degrade: se peer non risponde con caps entro N msg, disabilita dyn LUT

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/src/adp/session.py`
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_caps.py`

- [ ] **Step 1: Test failing**

Aggiungere a `tests/test_caps.py`:

```python
def test_encode_auto_degrade_after_timeout():
    """Dopo `caps_timeout_msgs` send senza vedere peer_caps, sender
    automaticamente disabilita dyn LUT (passa a no_lut)."""
    s = ADPSession(path=None, auto_save=False,
                   announce_caps=True, caps_timeout_msgs=3)
    # Send 4 msg senza mai ricevere caps di ritorno
    s.encode({"role": "administrator", "role2": "administrator"})  # send #1
    s.encode({"role": "administrator", "role2": "administrator"})  # send #2
    s.encode({"role": "administrator", "role2": "administrator"})  # send #3
    msg4 = s.encode({"role": "administrator", "role2": "administrator"})
    # Al 4° messaggio (counter > timeout), encoder dovrebbe aver
    # automaticamente disabilitato dyn LUT
    # Indicatore: nessun _lut_add nel msg4
    assert "_lut_add" not in msg4


def test_encode_no_degrade_if_peer_caps_received():
    """Se peer_caps è popolato, no auto-degrade."""
    s = ADPSession(path=None, auto_save=False,
                   announce_caps=True, caps_timeout_msgs=2)
    # Simula peer caps ricevuto
    s._peer_caps = {"dyn_lut": 1, "max_entries": 256, "diff": 1}
    # Send 5 msg
    for _ in range(5):
        s.encode({"role": "administrator", "role2": "administrator"})
    # Dopo timeout, ma peer_caps presente → continua a usare dyn LUT
    msg = s.encode({"role": "administrator", "role2": "administrator"})
    # In questo caso _lut_add NON deve apparire perché "administrator" è già
    # stato aggiunto nei msg precedenti. Verifica indiretta: encode normale.
    # Verifichiamo l'invariante: il sender NON ha auto-degradato (no_lut implicito).
    # Se avesse auto-degradato, _lut_add o alias _N non apparirebbero. Verifica
    # presenza degli alias dynamic:
    assert "administrator" not in msg  # è sostituito da alias _N
```

- [ ] **Step 2: Run failing**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_caps.py -v -k "auto_degrade or no_degrade"
```

Expected: 2 FAIL.

- [ ] **Step 3: Implementare auto-degrade in `encode()`**

In `src/adp/session.py`, trovare il metodo `encode()`. Modificarlo per controllare l'auto-degrade in cima:

Sostituire INTERAMENTE il metodo `encode()` con la versione che include il check di degrado:

```python
    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        """Encode obj a stringa ADP.

        - Se `announce_caps=True` AND non ancora annunciato: prepende
          `_caps={dyn_lut=1;max_entries=N;diff=1}` al messaggio.
        - Auto-degrade: se dopo `caps_timeout_msgs` send senza ricevere
          peer_caps, sender bypassa dyn LUT e diff automaticamente.
        - Se `no_lut=True` (esplicito): bypassa dynamic LUT e diff.
        - Altrimenti: usa dynamic LUT + diff (se enable_diff).
        - Aggiorna baseline state.
        """
        caps_prefix = self._build_caps_prefix()

        # Auto-degrade check
        effective_no_lut = no_lut
        if (self._announce_caps
                and self._peer_caps is None
                and self._caps_outbound_count >= self._caps_timeout_msgs):
            effective_no_lut = True

        if effective_no_lut:
            self._last_sent_payload = obj
            self._last_sent_base_id = self._compute_base_id(obj)
            if self._static_lut:
                payload = adp.encode(obj, key_lut=self._static_lut)
            else:
                payload = adp.encode(obj)
            self._caps_outbound_count += 1
            return caps_prefix + payload

        full_msg = self._encode_full_with_lut(obj)

        diff_msg: str | None = None
        if self._enable_diff and self._last_sent_payload is not None:
            diff_dict = compute_diff(self._last_sent_payload, obj)
            if diff_dict:
                diff_payload = adp.encode(diff_dict, key_lut=self._static_lut or None)
                candidate = f"_base={self._last_sent_base_id};_diff={diff_payload};"
                if len(candidate) < self._diff_threshold * len(full_msg):
                    diff_msg = candidate

        self._last_sent_payload = obj
        self._last_sent_base_id = self._compute_base_id(obj)

        chosen = diff_msg if diff_msg is not None else full_msg
        self._caps_outbound_count += 1
        return caps_prefix + chosen
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_caps.py -v
uv run pytest -q
```

Expected: test_caps.py 11 PASSED, full suite 226 PASSED.

Se test pre-esistenti rompono: probabilmente altre test suite scambiano molti msg senza caps. Soluzione: nei test pre-esistenti aggiungere `announce_caps=False` ai costruttori, oppure aspettarsi auto-degrade in test di lunga durata.

- [ ] **Step 5: Commit**

```bash
git add src/adp/session.py tests/test_caps.py
git commit -m "feat(session): auto-degrade encoder dopo caps_timeout_msgs senza peer caps"
```

---

## Task 5 — Test integrazione: round-trip simmetrico + reset_caps

**Files:**
- Modify: `/home/adriano/Documenti/Git_XYZ/GoalLanguageAgents/tests/test_caps.py`

- [ ] **Step 1: Test integrazione**

Aggiungere a `tests/test_caps.py`:

```python
def test_caps_round_trip_two_aware_sessions():
    """Due ADPSession aware: handshake bidirezionale popola entrambi peer_caps."""
    a = ADPSession(path=None, auto_save=False, announce_caps=True)
    b = ADPSession(path=None, auto_save=False, announce_caps=True)

    # A invia primo msg con _caps=
    msg_a_to_b = a.encode({"task": "ping"})
    assert "_caps=" in msg_a_to_b
    b.decode(msg_a_to_b)
    # B ora conosce A
    assert b.peer_caps is not None

    # B risponde con il suo _caps=
    msg_b_to_a = b.encode({"task": "pong"})
    assert "_caps=" in msg_b_to_a
    a.decode(msg_b_to_a)
    # A ora conosce B
    assert a.peer_caps is not None

    # Da qui in poi, nessuno annuncia più caps
    msg_a_2 = a.encode({"task": "data"})
    assert "_caps=" not in msg_a_2


def test_reset_caps_forces_reannounce():
    """Dopo reset_caps, encode emette di nuovo _caps= al prossimo msg."""
    s = ADPSession(path=None, auto_save=False, announce_caps=True)
    s.encode({"a": 1})  # primo annuncio
    assert s._caps_announced is True
    msg2 = s.encode({"b": 2})
    assert "_caps=" not in msg2

    s.reset_caps()
    msg3 = s.encode({"c": 3})
    # Dopo reset, ri-annuncia caps
    assert "_caps=" in msg3
```

- [ ] **Step 2: Run**

```bash
cd /home/adriano/Documenti/Git_XYZ/GoalLanguageAgents
uv run pytest tests/test_caps.py -v
uv run pytest -q
```

Expected: test_caps.py 13 PASSED, full suite 228 PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/test_caps.py
git commit -m "test(caps): round-trip aware-aware + reset_caps forza re-annuncio"
```

---

## Self-review (post-stesura del plan)

**1. Spec coverage (Est. 2):**

| Spec requirement | Task |
|---|---|
| Nuovo `_caps={...}` prefix | Task 2, 3 |
| `_caps` come reserved key | Task 3 |
| Param `announce_caps`, `caps_timeout_msgs` | Task 1, 2 |
| Property `peer_caps` | Task 1, 3 |
| Metodo `reset_caps()` | Task 1, 5 |
| Auto-degrade dopo timeout | Task 4 |
| Bidirezionale handshake | Task 5 |
| Test categorie spec 16-19 | distribuiti Task 1-5 |

Tutto coperto. Effort stimato +30 LOC nello spec, qui ~80 LOC (più test + auto-degrade più completo).

**2. Placeholder scan:** nessun TBD/TODO; tutti gli step contengono codice o comandi concreti.

**3. Type consistency:**

- `_announce_caps: bool`, `_caps_timeout_msgs: int`, `_peer_caps: dict | None`, `_caps_announced: bool`, `_caps_outbound_count: int` consistenti
- `peer_caps -> dict | None` property
- `reset_caps() -> None`
- `_build_caps_prefix() -> str`
- `_RESERVED_KEYS` esteso con `_caps` come PRIMO elemento (ordine implementazione)

Nessuna divergenza.

## Note per Plan futuri

Dopo questo plan:
- Plan 6 (Est. 3 TPD auto-promotion): ultimo. Più complesso (ring buffer + integrazione tpd.learn_lut).
- Update README con menzione capability negotiation (opzionale, è una feature di produzione)
- Considerare aggiunta di un parametro `respect_peer_caps` per usare `peer.max_entries` come cap effettivo (out of scope v1)
