"""Shared fixtures for the Kerykeion MCP test suite."""

import pytest

BIRTH_ROME = dict(
    name="Rome Test",
    year=1990, month=6, day=15,
    hour=14, minute=30,
    lat=41.9028, lng=12.4964,
    tz_str="Europe/Rome",
)

BIRTH_LONDON = dict(
    name="London Test",
    year=1992, month=12, day=25,
    hour=16, minute=45,
    lat=51.5074, lng=-0.1278,
    tz_str="Europe/London",
)


@pytest.fixture
def birth_rome():
    return dict(BIRTH_ROME)


@pytest.fixture
def birth_london():
    return dict(BIRTH_LONDON)


@pytest.fixture
def tmp_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KERYKEION_OUTPUT_BASE", str(tmp_path))
    return str(tmp_path)
