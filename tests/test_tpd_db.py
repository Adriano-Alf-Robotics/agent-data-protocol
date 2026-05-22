"""Tests for TPD (Token-aware Phrase Dictionary) and ADP-DB."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from adp.tpd import encode_text, decode_text, learn_lut, BUSINESS_LUT_EN, BUSINESS_LUT_IT
from adp.db import ADPStore


# ---------------------------------------------------------------------------
# TPD
# ---------------------------------------------------------------------------

class TestTPD:
    def test_roundtrip_simple(self) -> None:
        lut = {" year over year": "§y", "Revenue grew": "§r"}
        text = "Revenue grew 12% year over year, driven by Y."
        c = encode_text(text, lut)
        assert decode_text(c, lut) == text

    def test_collision_free_codes(self) -> None:
        """Codes chosen must not appear naturally in the source text."""
        lut = {"hello": "Z9"}
        text = "I say hello to you"
        assert "Z9" not in text
        c = encode_text(text, lut)
        assert decode_text(c, lut) == text

    def test_no_lut_passthrough(self) -> None:
        assert encode_text("hello", {}) == "hello"
        assert decode_text("hello", {}) == "hello"

    def test_business_lut_en_compresses(self) -> None:
        text = "Revenue grew 12% year over year, driven primarily by enterprise sales in the EMEA region."
        c = encode_text(text, BUSINESS_LUT_EN)
        assert len(c) < len(text)
        assert decode_text(c, BUSINESS_LUT_EN) == text


# ---------------------------------------------------------------------------
# Learn LUT
# ---------------------------------------------------------------------------

class TestLearnLut:
    def test_learn_finds_repeated_phrases(self) -> None:
        # Build a text where "foo bar" appears multiple times
        text = (
            "foo bar is a common phrase. We use foo bar often. "
            "Indeed foo bar appears here. And foo bar again."
        )
        lut = learn_lut(text, max_codes=5, min_phrase_words=2)
        assert lut, "should learn at least one phrase"
        # The learned codes must round-trip
        c = encode_text(text, lut)
        assert decode_text(c, lut) == text


# ---------------------------------------------------------------------------
# ADP-DB
# ---------------------------------------------------------------------------

class TestADPStore:
    def test_put_and_get(self) -> None:
        s = ADPStore()
        i = s.put("hello world")
        assert s.get(i) == "hello world"
        assert s.put("hello world") == i  # same content -> same id

    def test_seed_with_dict(self) -> None:
        s = ADPStore()
        s.seed({"Revenue grew": "r1", "year over year": "y1"})
        assert "r1" in s
        assert s.get("r1") == "Revenue grew"

    def test_encode_decode_roundtrip(self) -> None:
        s = ADPStore()
        s.seed({"Revenue grew 12%": "r1", "year over year": "y1", "EMEA region": "g1"})
        original = "Report: Revenue grew 12% year over year in the EMEA region."
        compressed = s.encode(original)
        assert "^r1" in compressed
        assert "^y1" in compressed
        assert "^g1" in compressed
        assert s.decode(compressed) == original

    def test_caret_escape(self) -> None:
        s = ADPStore()
        s.seed({"hello": "a"})
        text = "5 ^ 2 = 25; hello"
        compressed = s.encode(text)
        # `^` was escaped to `^^`
        assert "^^" in compressed
        assert s.decode(compressed) == text

    def test_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.json"
            a = ADPStore(path=path)
            a.put("frase frequente")
            a.put("altra frase")
            a.save()

            b = ADPStore(path=path)
            assert len(b) == 2
            assert "frase frequente" in b._by_content   # type: ignore[attr-defined]

    def test_inline_definition(self) -> None:
        """A message that defines a new phrase inline must update receiver's DB."""
        sender = ADPStore()
        receiver = ADPStore()
        # Sender defines a new phrase inline:
        msg = "Report: ^+a|Revenue grew 12% year over year|^. Confirmed."
        # Receiver decodes:
        decoded = receiver.decode(msg)
        assert "Revenue grew 12% year over year" in decoded
        # And the receiver now has it in its DB
        assert receiver.id_of("Revenue grew 12% year over year") == "a"

    def test_followup_message_uses_reference_only(self) -> None:
        """After a definition, a follow-up message can reuse the ref."""
        store = ADPStore()
        store.seed({"Revenue grew 12% year over year": "a"})
        msg = "Q1 update: ^a. Q2 update: ^a."
        decoded = store.decode(msg)
        assert decoded.count("Revenue grew 12% year over year") == 2
