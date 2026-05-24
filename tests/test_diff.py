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


from adp.session import ADPSession
from adp import ADPDiffSyncError  # nuovo export


def test_diff_sync_error_carries_expected_and_got():
    err = ADPDiffSyncError(expected="abc12345", got="def67890")
    assert err.expected == "abc12345"
    assert err.got == "def67890"
    assert "abc12345" in str(err)
    assert "def67890" in str(err)


def test_session_diff_state_initialized():
    s = ADPSession(path=None, auto_save=False)
    assert s._last_sent_payload is None
    assert s._last_sent_base_id is None
    assert s._last_received_payload is None
    assert s._last_received_base_id is None
    # Default enable_diff True
    assert s._enable_diff is True
    assert s._diff_threshold == 0.7


def test_session_diff_params_configurable():
    s = ADPSession(path=None, auto_save=False,
                   enable_diff=False, diff_threshold=0.5)
    assert s._enable_diff is False
    assert s._diff_threshold == 0.5


def test_encode_first_message_full_no_diff_prefix():
    s = ADPSession(path=None, auto_save=False)
    msg = s.encode({"a": 1, "b": 2})
    assert "_base=" not in msg
    assert "_diff=" not in msg
    # State aggiornato
    assert s._last_sent_payload == {"a": 1, "b": 2}
    assert s._last_sent_base_id is not None


def test_encode_second_message_small_change_uses_diff():
    # Payload grande con un solo campo che cambia: diff deve essere molto più piccolo del full
    base_payload = {
        "task_id": "task_001",
        "user": {
            "id": 42,
            "role": "administrator_long_role_string",
            "dept": "engineering_department_name",
            "org": "main_organization_unit_long",
            "location": "datacenter_eu_west_1_location",
        },
        "metadata": {
            "source": "agent_controller_main_instance",
            "target": "worker_node_eu_west_1_primary",
            "priority": "high_priority_task_execution",
        },
    }
    next_payload = dict(base_payload)
    next_payload["task_id"] = "task_002"  # solo questo cambia
    s = ADPSession(path=None, auto_save=False)
    s.encode(base_payload)
    msg2 = s.encode(next_payload)
    assert "_base=" in msg2
    assert "_diff=" in msg2


def test_encode_massive_change_falls_back_to_full():
    s = ADPSession(path=None, auto_save=False, diff_threshold=0.7)
    # Primo msg: piccolo
    s.encode({"a": 1})
    # Secondo msg: totalmente diverso e molto più grande
    big_payload = {f"key_{i}": f"value_administrator_long_{i}" for i in range(50)}
    msg2 = s.encode(big_payload)
    # Diff sarebbe enorme rispetto al full → fallback a full
    assert "_base=" not in msg2
    assert "_diff=" not in msg2


def test_encode_diff_disabled_never_emits():
    s = ADPSession(path=None, auto_save=False, enable_diff=False)
    s.encode({"a": 1})
    msg2 = s.encode({"a": 1, "b": 2})
    assert "_base=" not in msg2
    assert "_diff=" not in msg2
