"""Test suite per adp.diff (differential encoding)."""
from __future__ import annotations

import pytest

from adp.diff import compute_diff, apply_diff


def test_compute_diff_identical_returns_empty():
    base = {"a": 1, "b": 2}
    current = {"a": 1, "b": 2}
    d = compute_diff(base, current)
    assert d == {}


def test_compute_diff_value_changed():
    base = {"a": 1, "b": 2}
    current = {"a": 1, "b": 3}
    d = compute_diff(base, current)
    assert d == {"set": {"b": 3}}


def test_compute_diff_new_key():
    base = {"a": 1}
    current = {"a": 1, "b": 2}
    d = compute_diff(base, current)
    assert d == {"set": {"b": 2}}


def test_compute_diff_removed_key():
    base = {"a": 1, "b": 2}
    current = {"a": 1}
    d = compute_diff(base, current)
    assert d == {"del": ["b"]}


def test_compute_diff_both_set_and_del():
    base = {"a": 1, "b": 2, "c": 3}
    current = {"a": 1, "b": 9, "d": 4}
    d = compute_diff(base, current)
    assert d == {"set": {"b": 9, "d": 4}, "del": ["c"]}
