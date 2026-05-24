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


def test_compute_diff_nested_dict():
    base = {"user": {"id": 42, "role": "admin", "dept": "eng"}}
    current = {"user": {"id": 42, "role": "admin", "dept": "ops"}}
    d = compute_diff(base, current)
    assert d == {"set": {"user": {"dept": "ops"}}}


def test_compute_diff_nested_add_remove():
    base = {"user": {"id": 42, "role": "admin"}, "x": 1}
    current = {"user": {"id": 42, "role": "admin", "new": "v"}, "y": 2}
    d = compute_diff(base, current)
    assert d == {"set": {"user": {"new": "v"}, "y": 2}, "del": ["x"]}


def test_compute_diff_list_full_replacement():
    base = {"items": [1, 2, 3]}
    current = {"items": [1, 2, 3, 4]}
    d = compute_diff(base, current)
    # Lista cambiata → sostituzione full
    assert d == {"set": {"items": [1, 2, 3, 4]}}


def test_apply_diff_set_only():
    base = {"a": 1, "b": {"c": 2}}
    diff = {"set": {"b": {"c": 3}}}
    new = apply_diff(base, diff)
    assert new == {"a": 1, "b": {"c": 3}}
    # Base non modificata
    assert base == {"a": 1, "b": {"c": 2}}


def test_apply_diff_del_only():
    base = {"a": 1, "b": 2}
    diff = {"del": ["b"]}
    new = apply_diff(base, diff)
    assert new == {"a": 1}


def test_apply_diff_set_and_del():
    base = {"a": 1, "b": 2, "c": 3}
    diff = {"set": {"b": 9, "d": 4}, "del": ["c"]}
    new = apply_diff(base, diff)
    assert new == {"a": 1, "b": 9, "d": 4}


def test_apply_diff_empty_returns_copy():
    base = {"a": 1}
    new = apply_diff(base, {})
    assert new == base
    assert new is not base  # deep copy


def test_diff_round_trip_realistic():
    base = {
        "task_id": "task_001",
        "user": {"id": 42, "role": "admin", "dept": "eng"},
        "metrics": {"errors": 0, "latency_ms": 200},
    }
    current = {
        "task_id": "task_002",  # changed
        "user": {"id": 42, "role": "admin", "dept": "ops"},  # dept changed
        "metrics": {"errors": 3, "latency_ms": 200},  # errors changed
        "new_field": "added",
    }
    d = compute_diff(base, current)
    rebuilt = apply_diff(base, d)
    assert rebuilt == current


def test_apply_diff_delete_nested_path():
    base = {"a": {"b": {"c": 1, "d": 2}}}
    diff = {"del": ["a.b.c"]}
    new = apply_diff(base, diff)
    assert new == {"a": {"b": {"d": 2}}}


def test_apply_diff_delete_missing_path_noop():
    base = {"a": 1}
    diff = {"del": ["nonexistent.path"]}
    new = apply_diff(base, diff)
    assert new == {"a": 1}
