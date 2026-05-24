"""ADPSession — Dynamic LUT adattiva HPACK-style per ADP.

Mantiene una look-up table dinamica condivisa tra agenti, sincronizzata via
prefissi in-band (`_lut_add={...}`, `_lut_reset=1`) nei messaggi ADP,
persistita localmente in `~/.adp/lut_state.json` (override via parametro
`path` o env `ADP_LUT_PATH`).

Architettura: HPACK-style (RFC 7541). Eviction LRU bounded (default 256
entries), deterministica side-local. Cost-benefit char-based decide se
aggiungere un entry: candidato aggiunto solo se savings >= 0.

Esempio uso base:

    import adp

    session = adp.ADPSession()  # carica/crea ~/.adp/lut_state.json

    # Mittente A
    msg = session.encode({
        "user": {"id": 42, "role": "administrator", "dept": "engineering"},
        "user2": {"id": 43, "role": "administrator", "dept": "engineering"},
    })
    # msg contiene _lut_add={_0=role;_1=administrator;...};u={...} ecc.

    # Destinatario B (con la propria ADPSession)
    obj = session.decode(msg)
    # Lo stato LUT di entrambi è ora sincronizzato

**IMPORTANTE — namespace alias riservato:**

Gli alias dynamic LUT usano il pattern `_N` (underscore seguito da soli
digit). Questo namespace è RISERVATO: chiavi/valori utente con questo
pattern (es. `{"_0": "literal"}`) sono ambigui e producono
`ADPLUTSyncError` al decode su sessione senza l'alias corrispondente.

Soluzioni:
- Non usare chiavi/valori che matchano `_\\d+` nei payload utente
- Per messaggi che devono coesistere con sistemi terzi che usano tale
  pattern, decodificare con `adp.decode()` diretto (no session) o con
  `session.encode(obj, no_lut=True)` + `adp.decode()` lato receiver

Spec: docs/superpowers/specs/2026-05-24-dynamic-lut-design.md
"""
from __future__ import annotations

import atexit
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import adp
from adp.cost import TokenizerCostEstimator
from adp.diff import compute_diff, apply_diff


class ADPLUTSyncError(Exception):
    """Sollevata quando un alias dynamic LUT non è risolvibile."""

    def __init__(self, alias: str, message: str | None = None):
        self.alias = alias
        super().__init__(message or f"Alias dynamic LUT non risolvibile: {alias!r}")


class ADPDiffSyncError(Exception):
    """Sollevata quando il base_id dichiarato in _base= non match con lo state locale."""

    def __init__(self, expected: str, got: str):
        self.expected = expected
        self.got = got
        super().__init__(
            f"Diff baseline mismatch: atteso {expected!r}, ricevuto {got!r}"
        )


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
        enable_diff: bool = True,
        diff_threshold: float = 0.7,
        cost_estimator: TokenizerCostEstimator | None = None,
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

        self._cost_estimator: TokenizerCostEstimator | None = cost_estimator

        # Differential encoding state (Est. 5)
        self._enable_diff = enable_diff
        self._diff_threshold = diff_threshold
        self._last_sent_payload: Any = None
        self._last_sent_base_id: str | None = None
        self._last_received_payload: Any = None
        self._last_received_base_id: str | None = None

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
            # Cost-benefit: tokenizer-aware se estimator presente, char-count altrimenti
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
        return added

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
        if re.search(r"[\s,;=\[\]\{\}|\"#&~\\\\]", s):
            escaped = s.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return s

    # ------------------------------------------------------------------
    # decode() e metodi helper
    # ------------------------------------------------------------------

    _RESERVED_KEYS = ("_lut_reset", "_lut_add", "_diff_reset", "_base", "_diff")

    def decode(self, msg: str) -> Any:
        """Decode messaggio ADP. Applica nell'ordine:
        1. _lut_reset / _lut_add — aggiorna dynamic LUT
        2. _diff_reset — pulisce baseline received
        3. _base + _diff — applica diff a baseline received
        4. Resto del payload — decode normale, aggiorna baseline received
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
                parsed = adp.decode(value_str,
                                    key_lut=self._static_lut or None)
                if not isinstance(parsed, dict):
                    raise adp.ADPParseError(
                        f"_diff malformed: {value_str!r}")
                diff_dict = parsed
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
        # next_alias_id NON resettato: garantisce uniqueness storica

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
                continue  # idempotente sull'alias
            if fullname in self._inv:
                continue  # fullname già mappato a un alias diverso, skip per evitare orfani
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
            self._stats["miss_count"] += 1
            raise ADPLUTSyncError(token)
        return token

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


def apply_lut_updates(msg: str, lut: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Estrae prefissi _lut_reset/_lut_add da msg e ritorna (payload_pulito,
    lut_aggiornata).

    Helper stateless per integrazioni custom. Non valida né bumpa LRU.
    """
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


__all__ = ["ADPSession", "ADPLUTSyncError", "ADPDiffSyncError", "DEFAULT_PATH",
           "SCHEMA_VERSION", "apply_lut_updates", "encode_with_dyn_lut"]
