"""Test suite per ADPSession.warmup() (pre-warm da corpus)."""
from __future__ import annotations

from pathlib import Path

import pytest

import adp
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
