"""Tests for v0.2 features: bytes, ample bare strings, nested table cells."""

from __future__ import annotations

import pytest

from adp import encode, decode, to_json, from_json, ADPParseError


# ---------------------------------------------------------------------------
# Bytes
# ---------------------------------------------------------------------------

class TestBytes:
    def test_empty_bytes(self) -> None:
        assert decode(encode({"b": b""})) == {"b": b""}

    def test_simple_bytes(self) -> None:
        obj = {"img": b"hello world"}
        s = encode(obj)
        assert "b!" in s
        assert decode(s) == obj

    def test_binary_bytes(self) -> None:
        payload = bytes(range(256))
        obj = {"raw": payload}
        s = encode(obj)
        assert decode(s) == obj

    def test_bytes_in_nested_map(self) -> None:
        obj = {"file": {"name": "x.bin", "data": b"\x00\x01\x02\xff"}}
        s = encode(obj)
        assert decode(s) == obj

    def test_bytes_in_list(self) -> None:
        obj = {"chunks": [b"a", b"bb", b"ccc"]}
        s = encode(obj)
        assert decode(s) == obj

    def test_bytes_json_roundtrip(self) -> None:
        obj = {"img": b"\x89PNG\r\n\x1a\n", "name": "logo.png"}
        s = encode(obj)
        j = to_json(s)
        s2 = from_json(j)
        assert decode(s2) == obj

    def test_bytearray_accepted_as_bytes(self) -> None:
        obj_in = {"data": bytearray(b"abc")}
        s = encode(obj_in)
        assert decode(s) == {"data": b"abc"}


# ---------------------------------------------------------------------------
# Ample bare strings (URL, email, path)
# ---------------------------------------------------------------------------

class TestAmpleBareStrings:
    def test_email_is_bare(self) -> None:
        s = encode({"email": "ops@acme.example"})
        assert '"' not in s, f"email should be bare, got: {s}"
        assert decode(s) == {"email": "ops@acme.example"}

    def test_url_is_bare(self) -> None:
        s = encode({"url": "https://acme.example/api/v2"})
        assert '"' not in s, f"URL should be bare, got: {s}"
        assert decode(s) == {"url": "https://acme.example/api/v2"}

    def test_path_with_dot_is_bare(self) -> None:
        s = encode({"file": "src/adp/parser.py"})
        assert '"' not in s
        assert decode(s) == {"file": "src/adp/parser.py"}

    def test_string_with_space_still_quoted(self) -> None:
        s = encode({"msg": "user con spazio"})
        assert '"' in s
        assert decode(s) == {"msg": "user con spazio"}

    def test_numeric_string_quoted(self) -> None:
        """A string that looks like a number must be quoted to avoid type collision."""
        s = encode({"x": "42"})
        assert '"42"' in s
        back = decode(s)
        assert back == {"x": "42"}
        assert isinstance(back["x"], str)


# ---------------------------------------------------------------------------
# Nested cells in tables
# ---------------------------------------------------------------------------

class TestNestedInTables:
    def test_table_with_list_cells(self) -> None:
        obj = {"users": [
            {"id": 1, "name": "alice", "roles": ["admin", "ops"]},
            {"id": 2, "name": "bob", "roles": ["dev"]},
            {"id": 3, "name": "carol", "roles": []},
        ]}
        s = encode(obj)
        assert "#id,name,roles|" in s   # encoded as table
        assert decode(s) == obj

    def test_table_with_map_cells(self) -> None:
        obj = {"machines": [
            {"id": 1, "spec": {"cpu": 4, "ram_gb": 16}},
            {"id": 2, "spec": {"cpu": 8, "ram_gb": 32}},
        ]}
        s = encode(obj)
        assert "#id,spec|" in s
        assert decode(s) == obj

    def test_table_mixed_nesting(self) -> None:
        obj = {"orders": [
            {"id": 1, "items": [{"sku": "A", "qty": 2}], "note": None},
            {"id": 2, "items": [{"sku": "B", "qty": 1}, {"sku": "C", "qty": 3}], "note": "rush"},
        ]}
        s = encode(obj)
        assert decode(s) == obj

    def test_table_with_bytes_cell(self) -> None:
        obj = {"docs": [
            {"id": 1, "content": b"PDF\x01"},
            {"id": 2, "content": b"PNG\x89"},
        ]}
        s = encode(obj)
        assert decode(s) == obj


# ---------------------------------------------------------------------------
# v0.2 top-level syntax (no & wrappers)
# ---------------------------------------------------------------------------

class TestTopLevelSyntax:
    def test_single_record_no_wrapper(self) -> None:
        assert encode({"a": 42}) == "a=42"

    def test_multiple_records_semicolon_separated(self) -> None:
        s = encode({"a": 42, "b": True})
        assert s == "a=42;b=1"

    def test_decode_with_trailing_semicolon(self) -> None:
        assert decode("a=42;b=1") == {"a": 42, "b": True}
        assert decode("a=42;b=1;") == {"a": 42, "b": True}

    def test_decode_empty_string(self) -> None:
        assert decode("") == {}

    def test_decode_only_whitespace(self) -> None:
        assert decode("   \n  ") == {}


# ---------------------------------------------------------------------------
# Aggressive savings — explicit checks
# ---------------------------------------------------------------------------

class TestSavings:
    def test_email_not_quoted(self) -> None:
        s = encode({"u": {"email": "a@b.c"}})
        assert '"a@b.c"' not in s

    def test_tabular_with_nested_uses_table_form(self) -> None:
        obj = {"x": [
            {"id": 1, "tags": ["a"]},
            {"id": 2, "tags": ["b", "c"]},
        ]}
        s = encode(obj)
        assert s.startswith("x=#id,tags|")


# ---------------------------------------------------------------------------
# Error cases for parser robustness
# ---------------------------------------------------------------------------

class TestErrors:
    def test_invalid_top_level_missing_equals(self) -> None:
        with pytest.raises(ADPParseError):
            decode("a:42")          # ':' is v0.1 syntax, must fail in v0.2

    def test_unterminated_string(self) -> None:
        with pytest.raises(ADPParseError):
            decode('a="unclosed')

    def test_invalid_base64(self) -> None:
        with pytest.raises(ADPParseError):
            decode("a=b!!!!notb64!!!")
