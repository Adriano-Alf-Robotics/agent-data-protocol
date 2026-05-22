"""ADP-DB — Content-addressed database of text fragments shared between agents.

Idea: due (o più) agenti condividono un database persistente di "blob testuali"
identificati da ID brevi. Quando una frase è già nel DB, il messaggio
trasporta solo l'ID (2-3 token) invece del testo intero (10-100 token).
La prima occorrenza è una **definizione** che aggiorna i DB di entrambi
gli agenti; le occorrenze successive sono **riferimenti**.

Differenza con TPD:
- TPD è statico: il dizionario è pre-concordato e non cambia.
- ADP-DB è dinamico e cresce: ogni messaggio può aggiungere nuove entry.
- ADP-DB è persistente: il database può essere salvato su file e riusato
  cross-session.

Grammatica delle stringhe compresse (estensione lossless al text payload):
    riferimento  := '^' BASE62
    definizione  := '^+' BASE62 '|' ...contenuto... '|^'
    escape       := '^^'         (per emettere '^' letterale nel testo)

Esempio:
    Primo invio:   "Quarterly summary: ^+r1|Revenue grew 12% year over year|^."
    Invio successivo (entrambi gli agenti hanno r1 nel DB):
                   "Quarterly summary: ^r1."

I codici sono assegnati in modo deterministico (lessicograficamente
crescente in base62) per garantire convergenza tra mittente e destinatario.

API principale:
    store = ADPStore(path='shared.db.json')
    store.seed(BUSINESS_LUT_EN)            # pre-popola con frasi comuni
    compressed = store.encode(text, define_unknown=True)
    original   = store.decode(compressed)
    store.save()                            # persisti su file
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


_MARKER = "^"
_REF_RE = re.compile(r"\^(?!\+)(?!\^)([A-Za-z0-9]+)")
_DEF_RE = re.compile(r"\^\+([A-Za-z0-9]+)\|(.*?)\|\^", re.DOTALL)
_PLACEHOLDER = ""  # PUA character, never in normal text


_BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base62(n: int) -> str:
    if n == 0:
        return "0"
    out = []
    while n:
        out.append(_BASE62[n % 62])
        n //= 62
    return "".join(reversed(out))


class ADPStore:
    """Bidirectional content-addressed store of text fragments."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._by_id: dict[str, str] = {}
        self._by_content: dict[str, str] = {}
        self._next: int = 0
        self.path = Path(path) if path else None
        if self.path and self.path.exists():
            self.load()

    # -----------------------------------------------------------------
    # state
    # -----------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, key: str) -> bool:
        return key in self._by_id or key in self._by_content

    def items(self) -> Iterable[tuple[str, str]]:
        return self._by_id.items()

    def get(self, ident: str) -> str:
        return self._by_id[ident]

    def id_of(self, content: str) -> str | None:
        return self._by_content.get(content)

    # -----------------------------------------------------------------
    # mutation
    # -----------------------------------------------------------------
    def put(self, content: str) -> str:
        if content in self._by_content:
            return self._by_content[content]
        ident = _to_base62(self._next)
        self._next += 1
        # avoid id collision with already-loaded fixed IDs
        while ident in self._by_id:
            ident = _to_base62(self._next)
            self._next += 1
        self._by_id[ident] = content
        self._by_content[content] = ident
        return ident

    def seed(self, phrases: Iterable[str] | dict[str, str]) -> None:
        """Pre-populate the store with a set of frequent phrases.

        Accepts either an iterable of phrases (auto-assigned IDs) or a
        mapping {phrase: explicit_id}. Both sides must agree on the same
        seed for the protocol to round-trip correctly.
        """
        if isinstance(phrases, dict):
            for content, ident in phrases.items():
                if content in self._by_content:
                    continue
                self._by_id[ident] = content
                self._by_content[content] = ident
        else:
            for p in phrases:
                self.put(p)

    # -----------------------------------------------------------------
    # persistence
    # -----------------------------------------------------------------
    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("No path provided for save()")
        data = {"next": self._next, "entries": self._by_id}
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.path
        if target is None or not target.exists():
            return
        data = json.loads(target.read_text(encoding="utf-8"))
        self._by_id = dict(data.get("entries", {}))
        self._by_content = {v: k for k, v in self._by_id.items()}
        self._next = int(data.get("next", len(self._by_id)))

    # -----------------------------------------------------------------
    # encoding
    # -----------------------------------------------------------------
    def encode(self, text: str, *, define_unknown: bool = False,
               min_phrase_chars: int = 4) -> str:
        """Compress text by substituting known content with refs.

        Per ogni frase nel DB ordinata per lunghezza decrescente, sostituisce
        le occorrenze nel testo con `^<id>`. Se define_unknown=True, non
        modifica nulla di nuovo (il learner sta separato in tpd.learn_lut).
        Il marker `^` nel testo viene escapato come `^^`.
        """
        if not self._by_id:
            return text
        text = text.replace(_MARKER, _MARKER + _MARKER)
        sorted_items = sorted(self._by_id.items(), key=lambda kv: -len(kv[1]))
        for ident, content in sorted_items:
            if len(content) < min_phrase_chars:
                continue
            text = text.replace(content, f"{_MARKER}{ident}")
        return text

    def decode(self, text: str) -> str:
        """Expand refs and (optionally) definitions back to original text.

        Order matters: first apply definitions (so new IDs are registered
        before being referenced later in the same message), then substitute
        plain references, then de-escape `^^` → `^`.
        """
        # Handle inline definitions first
        def _def_sub(m: re.Match) -> str:
            ident, content = m.group(1), m.group(2)
            self._by_id[ident] = content
            self._by_content[content] = ident
            return content

        text = _DEF_RE.sub(_def_sub, text)

        # Then plain references
        text = text.replace(_MARKER + _MARKER, _PLACEHOLDER)
        def _ref_sub(m: re.Match) -> str:
            ident = m.group(1)
            if ident in self._by_id:
                return self._by_id[ident]
            return m.group(0)
        text = _REF_RE.sub(_ref_sub, text)
        return text.replace(_PLACEHOLDER, _MARKER)

    def encode_with_definitions(self, text: str) -> str:
        """Encode a text emitting inline definitions for unknown content.

        Useful for the first message of a session: defines all phrases used.
        Recipients applying decode() will register them automatically.
        """
        from adp.tpd import learn_lut
        learned = learn_lut(text, max_codes=30)
        for phrase in learned.keys():
            self.put(phrase)
        return self.encode(text)
