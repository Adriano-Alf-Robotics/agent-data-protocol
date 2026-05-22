"""Tests for adp.integrity — sign / verify / tamper detection."""

from __future__ import annotations

import pytest

import adp
from adp.integrity import sign, verify, is_signed, strip, IntegrityError


PAYLOAD = "user={id=42;name=Adriano;active=1};msg=hello"


class TestCRC32:
    def test_sign_appends_trailer(self) -> None:
        s = sign(PAYLOAD, algo="crc32")
        assert s.startswith(PAYLOAD)
        assert ";_chk=crc32:" in s
        assert is_signed(s)

    def test_verify_roundtrip(self) -> None:
        s = sign(PAYLOAD, algo="crc32")
        assert verify(s) == PAYLOAD

    def test_detects_tampering(self) -> None:
        s = sign(PAYLOAD, algo="crc32")
        tampered = s.replace("Adriano", "Atriano")
        with pytest.raises(IntegrityError):
            verify(tampered)


class TestSHA256:
    def test_sign_and_verify(self) -> None:
        s = sign(PAYLOAD, algo="sha256")
        assert verify(s) == PAYLOAD

    def test_detects_single_char_change(self) -> None:
        s = sign(PAYLOAD, algo="sha256")
        tampered = s.replace("42", "43", 1)
        with pytest.raises(IntegrityError):
            verify(tampered)

    def test_strips_trailer(self) -> None:
        s = sign(PAYLOAD, algo="sha256")
        assert strip(s) == PAYLOAD


class TestHMAC:
    KEY = b"shared-secret-between-agents"

    def test_sign_and_verify(self) -> None:
        s = sign(PAYLOAD, algo="hmac", key=self.KEY)
        assert verify(s, key=self.KEY) == PAYLOAD

    def test_requires_key_for_sign(self) -> None:
        with pytest.raises(ValueError):
            sign(PAYLOAD, algo="hmac", key=None)

    def test_requires_key_for_verify(self) -> None:
        s = sign(PAYLOAD, algo="hmac", key=self.KEY)
        with pytest.raises(IntegrityError):
            verify(s, key=None)

    def test_wrong_key_fails(self) -> None:
        s = sign(PAYLOAD, algo="hmac", key=self.KEY)
        with pytest.raises(IntegrityError):
            verify(s, key=b"wrong-key")


class TestStrictness:
    def test_strict_raises_on_missing_trailer(self) -> None:
        with pytest.raises(IntegrityError):
            verify(PAYLOAD)

    def test_non_strict_passes_unchanged(self) -> None:
        assert verify(PAYLOAD, strict=False) == PAYLOAD


class TestIntegrationWithAdp:
    def test_signed_message_decodes_after_verify(self) -> None:
        obj = {"task": {"id": 7, "items": [1, 2, 3]}, "ok": True}
        s = adp.encode(obj)
        signed = sign(s, algo="sha256")
        verified = verify(signed)
        assert adp.decode(verified) == obj

    def test_signed_message_with_tampered_byte(self) -> None:
        obj = {"amount": 100.0, "currency": "EUR"}
        s = adp.encode(obj)
        signed = sign(s, algo="sha256")
        # Cambia un singolo byte nel mezzo del payload
        tampered = signed.replace("100.0", "999.0", 1)
        with pytest.raises(IntegrityError):
            verify(tampered)
