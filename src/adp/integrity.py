"""ADP integrity layer — sign, verify, detect tampering.

Tre livelli di controllo integrità, applicabili a un messaggio ADP già
codificato. Tutti aggiungono al messaggio un trailer della forma:

    <messaggio_adp>;_chk=<algo>:<hex_digest>

L'algoritmo è opt-in: l'overhead va da 7 token (CRC32) a circa 20 token
(SHA-256 / HMAC). La verifica restituisce il messaggio pulito o
solleva `IntegrityError`.

Tre algoritmi disponibili:

    crc32     8 hex char  -> ~7 token. Detection errori casuali. NON crypto.
    sha256    64 hex char -> ~18-22 token. Detection robusta. NON autenticato.
    hmac      64 hex char -> ~18-22 token. Detection + autenticità (chiave).

API:

    s = adp.encode(obj)
    signed = adp.integrity.sign(s, algo="sha256")
    # ...trasmissione, possibili modifiche...
    verified = adp.integrity.verify(signed)   # raise IntegrityError se rotto
    obj_back = adp.decode(verified)

Per HMAC:

    signed = adp.integrity.sign(s, algo="hmac", key=b"shared-secret")
    verified = adp.integrity.verify(signed, key=b"shared-secret")
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import re
import zlib
from typing import Literal


Algo = Literal["crc32", "sha256", "hmac"]

_TRAILER_RE = re.compile(r";_chk=(crc32|sha256|hmac):([0-9a-fA-F]+)$")


class IntegrityError(ValueError):
    """Raised when an ADP message fails its integrity check."""


def _digest_crc32(payload: bytes) -> str:
    return f"{zlib.crc32(payload):08x}"


def _digest_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_hmac(payload: bytes, key: bytes) -> str:
    return _hmac.new(key, payload, hashlib.sha256).hexdigest()


def sign(adp_str: str, *, algo: Algo = "sha256", key: bytes | None = None) -> str:
    """Append an integrity trailer to an ADP document.

    The trailer takes the form `;_chk=<algo>:<hex>`.
    For algo='hmac', a non-empty `key` is required.
    """
    payload = adp_str.encode("utf-8")
    if algo == "crc32":
        digest = _digest_crc32(payload)
    elif algo == "sha256":
        digest = _digest_sha256(payload)
    elif algo == "hmac":
        if not key:
            raise ValueError("HMAC requires a non-empty `key`")
        digest = _digest_hmac(payload, key)
    else:
        raise ValueError(f"unknown algo: {algo}")
    return f"{adp_str};_chk={algo}:{digest}"


def verify(signed_str: str, *, key: bytes | None = None,
           strict: bool = True) -> str:
    """Validate the trailer and return the original ADP document.

    Raises IntegrityError if the digest mismatches.
    If `strict=False` and there is no trailer, returns the string unchanged.
    """
    m = _TRAILER_RE.search(signed_str)
    if not m:
        if strict:
            raise IntegrityError("no integrity trailer found")
        return signed_str
    algo: Algo = m.group(1)  # type: ignore[assignment]
    expected = m.group(2).lower()
    payload_str = signed_str[: m.start()]
    payload = payload_str.encode("utf-8")
    if algo == "crc32":
        actual = _digest_crc32(payload)
    elif algo == "sha256":
        actual = _digest_sha256(payload)
    elif algo == "hmac":
        if not key:
            raise IntegrityError("HMAC trailer present but no key provided")
        actual = _digest_hmac(payload, key)
    else:
        raise IntegrityError(f"unsupported algo: {algo}")
    if not _hmac.compare_digest(actual.lower(), expected):
        raise IntegrityError(
            f"{algo} mismatch: expected {expected[:16]}…, got {actual[:16]}…"
        )
    return payload_str


def is_signed(adp_str: str) -> bool:
    """Return True if the document carries an integrity trailer."""
    return bool(_TRAILER_RE.search(adp_str))


def strip(adp_str: str) -> str:
    """Remove any integrity trailer without verifying it."""
    return _TRAILER_RE.sub("", adp_str)
