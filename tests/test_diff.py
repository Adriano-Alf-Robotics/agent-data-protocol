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


def test_decode_full_message_updates_baseline():
    s = ADPSession(path=None, auto_save=False)
    import adp as adp_mod
    msg = adp_mod.encode({"a": 1, "b": 2})
    out = s.decode(msg)
    assert out == {"a": 1, "b": 2}
    # baseline received aggiornato
    assert s._last_received_payload == {"a": 1, "b": 2}
    assert s._last_received_base_id is not None


def test_decode_diff_applies_to_baseline():
    s_sender = ADPSession(path=None, auto_save=False)
    s_receiver = ADPSession(path=None, auto_save=False)
    # Payload grande: diff di un solo campo deve essere molto più piccolo del full
    base = {
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
    update = dict(base)
    update["task_id"] = "task_002"  # solo questo cambia
    # First msg: full
    msg1 = s_sender.encode(base)
    out1 = s_receiver.decode(msg1)
    assert out1 == base
    # Second msg: diff
    msg2 = s_sender.encode(update)
    assert "_base=" in msg2  # encoder ha scelto diff
    out2 = s_receiver.decode(msg2)
    assert out2 == update


def test_decode_diff_sync_error_on_mismatch():
    s = ADPSession(path=None, auto_save=False)
    # Receiver non ha mai visto un payload → no baseline
    msg = "_base=deadbeef;_diff=set={a=1};"
    with pytest.raises(ADPDiffSyncError) as exc_info:
        s.decode(msg)
    assert exc_info.value.got == "deadbeef"
    # expected è None (no baseline) o ""
    assert exc_info.value.expected in (None, "")


def test_decode_diff_reset_clears_baseline():
    s = ADPSession(path=None, auto_save=False)
    s.decode("a=1;b=2")  # full msg, baseline ora settato
    assert s._last_received_payload is not None
    # Reset
    s.decode("_diff_reset=1;a=1")
    assert s._last_received_payload == {"a": 1}  # nuovo baseline (post-reset)


def test_encode_full_ignores_baseline():
    s = ADPSession(path=None, auto_save=False)
    s.encode({"a": 1})
    # Anche con baseline disponibile, encode_full produce full + emette _diff_reset
    msg = s.encode_full({"a": 1, "b": 2})
    assert "_diff_reset=1" in msg
    assert "_base=" not in msg
    assert "_diff={" not in msg


def test_encode_full_resets_local_baseline():
    s = ADPSession(path=None, auto_save=False)
    s.encode({"a": 1})
    s.encode_full({"a": 1, "b": 2})
    # Baseline locale aggiornato col nuovo payload
    assert s._last_sent_payload == {"a": 1, "b": 2}
    assert s._last_sent_base_id is not None


def test_encode_full_then_decode_clears_receiver_baseline():
    sender = ADPSession(path=None, auto_save=False)
    receiver = ADPSession(path=None, auto_save=False)
    msg1 = sender.encode({"a": 1, "b": 2})
    receiver.decode(msg1)
    # Sender forza full
    msg2 = sender.encode_full({"x": 1})
    out = receiver.decode(msg2)
    assert out == {"x": 1}
    # Receiver baseline ora == {"x": 1}
    assert receiver._last_received_payload == {"x": 1}


def test_combined_lut_and_diff_round_trip_20_messages():
    """Sessione 20 msg con dyn LUT + diff encoding entrambi attivi."""
    a = ADPSession(path=None, auto_save=False)
    b = ADPSession(path=None, auto_save=False)

    diff_count = 0
    full_count = 0
    for i in range(20):
        p = {
            "task_id": f"task_{i:03d}",
            "user": {"id": 42, "role": "administrator", "dept": "engineering"},
            "status": "in_progress" if i % 3 != 0 else "completed",
            "metrics": {"errors": i % 5, "latency_ms": 200 + i},
        }
        msg = a.encode(p)
        if "_diff=" in msg:
            diff_count += 1
        else:
            full_count += 1
        out = b.decode(msg)
        assert out == p, f"mismatch at msg {i}"

    # Almeno alcuni messaggi dopo il primo devono essere diff
    assert diff_count >= 5
    assert full_count >= 1  # primo msg almeno
    # Stati di entrambi sincronizzati
    assert a._last_sent_payload == b._last_received_payload


def test_sync_error_recovery_via_encode_full():
    """Dopo sync error, recovery con encode_full ristabilisce comunicazione."""
    sender = ADPSession(path=None, auto_save=False)
    receiver = ADPSession(path=None, auto_save=False)
    # Sender ha baseline, receiver no (simula receiver appena avviato)
    sender.encode({"a": 1})  # sender now has baseline
    sender.encode({"a": 1, "b": 2})  # sender will use diff

    # Manualmente forziamo: receiver è fresco
    receiver._last_received_payload = None
    receiver._last_received_base_id = None

    # Sender invia diff a receiver che non ha baseline
    msg = sender.encode({"a": 1, "b": 3})
    if "_diff=" in msg:
        with pytest.raises(ADPDiffSyncError):
            receiver.decode(msg)

        # Recovery: sender invia full
        recovery_msg = sender.encode_full({"a": 1, "b": 3})
        out = receiver.decode(recovery_msg)
        assert out == {"a": 1, "b": 3}
