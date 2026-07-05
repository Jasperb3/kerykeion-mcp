"""Tests for Phase 4 security/privacy hardening: output_dir confinement (F9)."""

from pathlib import Path

from kerykeion_mcp.chart_utils import resolve_output_dir
from kerykeion_mcp.validation import ChartInputError
from kerykeion_mcp.server import generate_natal_chart


def test_output_dir_outside_allowed_base_rejected():
    result = None
    try:
        resolve_output_dir("/etc")
    except ChartInputError as e:
        result = e
    assert result is not None
    assert "allowed base" in result.message


def test_output_dir_under_default_base_accepted():
    out_path = resolve_output_dir(None)
    assert out_path == (Path.home() / ".kerykeion_charts").resolve()


def test_output_dir_env_override_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("KERYKEION_OUTPUT_BASE", str(tmp_path))
    sub = tmp_path / "charts"
    resolved = resolve_output_dir(str(sub))
    assert resolved == sub.resolve()
    assert resolved.is_dir()


def test_natal_chart_rejects_output_dir_outside_allowed_base(birth_rome):
    result = generate_natal_chart(**birth_rome, output_format="all", output_dir="/etc")
    assert result["status"] == "error"
    assert "allowed base" in result["error"]
