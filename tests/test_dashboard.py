"""Tests for ADPSession per-message metrics (dashboard feature)."""
import json
import time
from pathlib import Path

import adp
from adp.session import ADPSession
from adp.cost import estimate_cost


def test_encode_records_history_entry():
    """After encode(), session.history has one entry with expected fields."""
    s = ADPSession(path=None, announce_caps=False)
    s.encode({"task": "hello", "value": 42})
    assert len(s.history) == 1
    entry = s.history[0]
    assert entry["direction"] == "encode"
    assert entry["tokens_adp"] > 0
    assert entry["tokens_json"] > 0
    assert entry["tokens_adp"] <= entry["tokens_json"]
    assert entry["bytes_adp"] > 0
    assert entry["bytes_json"] > 0
    assert entry["elapsed_ms"] >= 0
    assert "lut_entries" in entry
    assert "lut_hits" in entry
    assert "lut_misses" in entry
    assert isinstance(entry["used_diff"], bool)
    assert isinstance(entry["ts"], float)


def test_decode_records_history_entry():
    """After decode(), session.history has one entry for the decode."""
    s = ADPSession(path=None, announce_caps=False)
    msg = s.encode({"x": 1})
    s2 = ADPSession(path=None, announce_caps=False)
    s2.decode(msg)
    assert len(s2.history) == 1
    entry = s2.history[0]
    assert entry["direction"] == "decode"
    assert entry["tokens_adp"] > 0
    assert entry["elapsed_ms"] >= 0


def test_history_grows_with_messages():
    """Multiple encode/decode calls accumulate history entries."""
    s = ADPSession(path=None, announce_caps=False)
    for i in range(5):
        s.encode({"i": i})
    assert len(s.history) == 5


def test_diff_flag_in_history():
    """When diff encoding kicks in, used_diff is True."""
    s = ADPSession(path=None, announce_caps=False, enable_diff=True)
    s.encode({"task": "t1", "user": {"id": 42, "role": "administrator"}})
    s.encode({"task": "t2", "user": {"id": 42, "role": "administrator"}})
    assert s.history[0]["used_diff"] is False
    assert isinstance(s.history[1]["used_diff"], bool)


def test_history_persisted_and_loaded(tmp_path):
    """History survives save/load cycle."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.encode({"a": 1})
    s.encode({"b": 2})
    s.save()

    s2 = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    assert len(s2.history) == 2
    assert s2.history[0]["direction"] == "encode"


def test_history_in_stats():
    """stats() includes message_count."""
    s = ADPSession(path=None, announce_caps=False)
    s.encode({"x": 1})
    st = s.stats()
    assert st["message_count"] == 1


from adp.dashboard import render_dashboard


def _make_history(n: int = 10) -> list[dict]:
    """Generate synthetic history entries for testing."""
    history = []
    for i in range(n):
        history.append({
            "direction": "encode" if i % 2 == 0 else "decode",
            "ts": 1716600000.0 + i * 60,
            "tokens_adp": 50 + i,
            "tokens_json": 80 + i,
            "bytes_adp": 200 + i * 10,
            "bytes_json": 350 + i * 10,
            "elapsed_ms": 0.03 + i * 0.001,
            "lut_entries": min(i, 5),
            "lut_hits": i * 2,
            "lut_misses": i,
            "used_diff": i > 3,
        })
    return history


def test_render_dashboard_returns_html():
    """render_dashboard produces a valid HTML document."""
    html = render_dashboard(_make_history())
    assert "<!DOCTYPE html>" in html
    assert "<svg" in html
    assert "</svg>" in html
    assert "ADP Dashboard" in html


def test_render_dashboard_empty_history():
    """Empty history produces a page with a 'no data' message."""
    html = render_dashboard([])
    assert "<!DOCTYPE html>" in html
    assert "no data" in html.lower() or "nessun dato" in html.lower()


def test_render_dashboard_summary_cards():
    """Summary section shows total messages and savings."""
    html = render_dashboard(_make_history(20))
    assert "20" in html


def test_render_dashboard_has_dark_mode():
    """CSS includes prefers-color-scheme media query."""
    html = render_dashboard(_make_history())
    assert "prefers-color-scheme" in html


def test_render_dashboard_cost_estimate():
    """Cost section shows dollar estimates."""
    html = render_dashboard(_make_history())
    assert "$" in html


from click.testing import CliRunner
from adp.cli import main as cli_main


def test_cli_dashboard_generates_html(tmp_path):
    """adp dashboard --path <lut_file> writes HTML to stdout."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    for i in range(5):
        s.encode({"task": f"t{i}", "value": i})
    s.save()

    runner = CliRunner()
    result = runner.invoke(cli_main, ["dashboard", "--path", str(p)])
    assert result.exit_code == 0
    assert "<!DOCTYPE html>" in result.output
    assert "<svg" in result.output


def test_cli_dashboard_output_file(tmp_path):
    """adp dashboard --output writes to file instead of stdout."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.encode({"x": 1})
    s.save()

    out = tmp_path / "report.html"
    runner = CliRunner()
    result = runner.invoke(cli_main, ["dashboard", "--path", str(p), "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text()
    assert "<!DOCTYPE html>" in content


def test_cli_dashboard_no_history(tmp_path):
    """adp dashboard with no history shows empty state."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.save()

    runner = CliRunner()
    result = runner.invoke(cli_main, ["dashboard", "--path", str(p)])
    assert result.exit_code == 0
    assert "nessun dato" in result.output.lower() or "no data" in result.output.lower()


from adp.dashboard import discover_projects, render_multi_dashboard


def test_session_project_creates_directory(tmp_path):
    """ADPSession with explicit path saves to that path."""
    s = ADPSession(
        path=str(tmp_path / "projects" / "myapp" / "lut_state.json"),
        auto_save=False, announce_caps=False,
    )
    s.encode({"x": 1})
    s.save()
    assert (tmp_path / "projects" / "myapp" / "lut_state.json").exists()


def test_session_project_param(tmp_path, monkeypatch):
    """ADPSession(project='foo') stores under projects dir."""
    monkeypatch.setattr("adp.session.PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr("adp.session.DEFAULT_PATH", str(tmp_path / "default.json"))
    s = ADPSession(project="foo", auto_save=False, announce_caps=False)
    s.encode({"x": 1})
    s.save()
    assert (tmp_path / "projects" / "foo" / "lut_state.json").exists()
    assert s.project == "foo"


def test_discover_projects_finds_projects(tmp_path):
    """discover_projects finds projects with history."""
    for name in ["alpha", "beta"]:
        d = tmp_path / name
        d.mkdir()
        s = ADPSession(path=str(d / "lut_state.json"), auto_save=False, announce_caps=False)
        for i in range(3):
            s.encode({"project": name, "i": i})
        s.save()

    projects = discover_projects(str(tmp_path))
    assert len(projects) == 2
    names = [p[0] for p in projects]
    assert "alpha" in names
    assert "beta" in names


def test_discover_projects_empty_dir(tmp_path):
    """discover_projects returns empty list for empty dir."""
    assert discover_projects(str(tmp_path)) == []


def test_render_multi_dashboard(tmp_path):
    """render_multi_dashboard shows comparison table + per-project sections."""
    projects = [
        ("alpha", _make_history(10)),
        ("beta", _make_history(5)),
    ]
    html = render_multi_dashboard(projects)
    assert "<!DOCTYPE html>" in html
    assert "alpha" in html
    assert "beta" in html
    assert "Projects overview" in html
    assert "2 projects" in html


def test_render_multi_dashboard_empty():
    """Empty projects list shows no-data message."""
    html = render_multi_dashboard([])
    assert "nessun dato" in html.lower() or "no data" in html.lower()


def test_cli_dashboard_discovers_projects(tmp_path, monkeypatch):
    """CLI without --path discovers projects."""
    monkeypatch.setattr("adp.session.PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr("adp.session.DEFAULT_PATH", str(tmp_path / "nonexistent.json"))

    d = tmp_path / "testproj"
    d.mkdir()
    s = ADPSession(path=str(d / "lut_state.json"), auto_save=False, announce_caps=False)
    s.encode({"a": 1})
    s.save()

    runner = CliRunner()
    result = runner.invoke(cli_main, ["dashboard"])
    assert result.exit_code == 0
    assert "testproj" in result.output


def test_cli_dashboard_project_flag(tmp_path, monkeypatch):
    """CLI --project filters to one project."""
    monkeypatch.setattr("adp.session.PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr("adp.session.DEFAULT_PATH", str(tmp_path / "nonexistent.json"))

    d = tmp_path / "myapp"
    d.mkdir()
    s = ADPSession(path=str(d / "lut_state.json"), auto_save=False, announce_caps=False)
    s.encode({"task": "hello"})
    s.save()

    runner = CliRunner()
    result = runner.invoke(cli_main, ["dashboard", "--project", "myapp"])
    assert result.exit_code == 0
    assert "<!DOCTYPE html>" in result.output
