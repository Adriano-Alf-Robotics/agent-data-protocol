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
