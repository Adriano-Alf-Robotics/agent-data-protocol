"""Tests for ADP <-> JSON and ADP -> Markdown converters."""

from __future__ import annotations

import json

from adp import from_json, to_json, to_markdown, decode, encode


def test_json_roundtrip_simple() -> None:
    src = {"user": {"id": 42, "name": "Adriano"}, "tags": ["a", "b"]}
    adp = encode(src)
    j = to_json(adp)
    assert json.loads(j) == src
    gla2 = from_json(j)
    assert decode(gla2) == src


def test_json_top_level_must_be_object() -> None:
    import pytest
    with pytest.raises(ValueError):
        from_json("[1, 2, 3]")


def test_to_markdown_renders_fields() -> None:
    adp = encode({
        "user": {"id": 42, "name": "Adriano", "active": True},
        "metrics": [{"id": 1, "v": 10.0}, {"id": 2, "v": 20.0}],
        "report": "linea1\nlinea2",
    })
    md = to_markdown(adp)
    assert "## user" in md
    assert "**id**: 42" in md
    assert "## metrics" in md
    assert "| id | v |" in md
    assert "## report" in md
    assert "```" in md
    assert "linea1\nlinea2" in md


def test_to_markdown_null_renders() -> None:
    adp = encode({"task": {"owner": None}})
    md = to_markdown(adp)
    assert "**owner**: —" in md


def test_to_markdown_pipe_escape_in_table() -> None:
    adp = encode({"data": [
        {"name": "a|b", "val": "x"},
        {"name": "c", "val": "y|z"},
    ]})
    md = to_markdown(adp)
    assert "a\\|b" in md
    assert "y\\|z" in md
