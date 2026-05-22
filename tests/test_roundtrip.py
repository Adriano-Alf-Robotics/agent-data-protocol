"""Round-trip tests: decode(encode(obj)) == obj for every supported value."""

from __future__ import annotations

import pytest

from adp import encode, decode


PAYLOADS = [
    pytest.param({}, id="empty"),
    pytest.param({"a": True, "b": False}, id="booleans"),
    pytest.param({"a": 1, "b": 0, "c": 42, "d": -7}, id="integers"),
    pytest.param({"a": 1.5, "b": -3.14, "c": 0.0, "d": 1.0e10}, id="floats"),
    pytest.param({"a": None}, id="null"),
    pytest.param({"name": "Adriano", "city": "Padova"}, id="bare-strings"),
    pytest.param({"msg": "con spazio"}, id="quoted-string-space"),
    pytest.param({"msg": 'contiene "virgolette" e \\backslash'}, id="quoted-escapes"),
    pytest.param({"text": "linea1\nlinea2\nlinea3"}, id="multiline-literal"),
    pytest.param({"empty_str": "", "one": "1", "zero": "0", "null_str": "~"},
                 id="reserved-strings"),
    pytest.param({"nums_as_str": "42", "float_as_str": "3.14"}, id="numeric-strings"),
    pytest.param({"list": [1, 2, 3, 4, 5]}, id="int-list"),
    pytest.param({"list": ["a", "b", "c con spazio"]}, id="string-list"),
    pytest.param({"list": []}, id="empty-list"),
    pytest.param({"list": [True, False, None]}, id="mixed-list"),
    pytest.param({"nested": {"a": {"b": {"c": 42}}}}, id="deep-nesting"),
    pytest.param({"map": {}}, id="empty-map"),
    pytest.param(
        {"users": [
            {"id": 1, "name": "alice", "active": True},
            {"id": 2, "name": "bob", "active": False},
            {"id": 3, "name": "carol", "active": True},
        ]},
        id="table-homogeneous",
    ),
    pytest.param(
        {"mixed": [{"id": 1, "name": "a"}, {"id": 2, "different": "key"}]},
        id="non-table-heterogeneous",
    ),
    pytest.param(
        {"unicode": "città €$ñ 中文 🎉"},
        id="unicode",
    ),
    pytest.param(
        {"order": {"items": [{"sku": "A1", "qty": 2, "price": 9.99}],
                   "total": 19.98, "paid": True, "notes": None}},
        id="real-world-order",
    ),
    pytest.param(
        {"task": {
            "id": 7,
            "intent": "review",
            "agent_from": "planner",
            "agent_to": "executor",
            "payload": {
                "file": "main.py",
                "diff": "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new",
            },
        }},
        id="agent-task",
    ),
]


@pytest.mark.parametrize("obj", PAYLOADS)
def test_roundtrip_python(obj: dict) -> None:
    """decode(encode(obj)) must equal obj."""
    s = encode(obj)
    back = decode(s)
    assert back == obj, f"round-trip mismatch\ninput:  {obj!r}\nADP:    {s!r}\noutput: {back!r}"


@pytest.mark.parametrize("obj", PAYLOADS)
def test_roundtrip_string(obj: dict) -> None:
    """encode(decode(encode(obj))) must equal encode(obj). Encoder must be deterministic."""
    s1 = encode(obj)
    s2 = encode(decode(s1))
    assert s1 == s2


def test_top_level_non_dict_rejected() -> None:
    import pytest as _p
    with _p.raises(TypeError):
        encode([1, 2, 3])  # type: ignore[arg-type]
    with _p.raises(TypeError):
        encode("hello")  # type: ignore[arg-type]


def test_invalid_identifier_rejected() -> None:
    import pytest as _p
    with _p.raises(ValueError):
        encode({"has space": 1})
    with _p.raises(ValueError):
        encode({"1starts_with_digit": 1})


def test_unicode_emoji_roundtrip() -> None:
    obj = {"msg": "Hello 👋 world 🌍 ciao"}
    assert decode(encode(obj)) == obj


def test_zero_one_int_vs_bool() -> None:
    obj = {"flag": True, "count": 1, "off": False, "zero": 0}
    s = encode(obj)
    back = decode(s)
    assert back["flag"] is True
    assert back["count"] == 1 and isinstance(back["count"], int) and not isinstance(back["count"], bool)
    assert back["off"] is False
    assert back["zero"] == 0 and isinstance(back["zero"], int) and not isinstance(back["zero"], bool)


def test_float_precision() -> None:
    obj = {"pi": 3.141592653589793, "small": 1e-10, "big": 1e20}
    back = decode(encode(obj))
    assert back == obj
