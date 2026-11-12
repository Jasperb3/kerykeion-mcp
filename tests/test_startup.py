"""
Start-up: every lazy native import happens before the stdio transport reads.

On Windows, loading a native extension (numpy, which kerykeion pulls in on
the first chart via its fixed-star catalog, libephemeris and erfa) blocks
while the stdio reader thread has a read pending on stdin. A tool call that
triggered the import froze the event loop until the client sent another
message, so a batch of calls timed out. main() casts one chart first.
"""

import re
import sys

from kerykeion_mcp import server


def test_main_warms_up_before_serving(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "warm_up", lambda: calls.append("warm_up"))
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append("run"))
    monkeypatch.setattr(sys, "argv", ["kerykeion-mcp"])
    server.main()
    assert calls == ["warm_up", "run"]


def test_warm_up_loads_the_lazy_native_modules():
    server.warm_up()
    assert "libephemeris" in sys.modules
    assert "numpy" in sys.modules


def run_server(tmp_path, **env):
    """Start the stdio server from another directory, stdin closed, and wait for it to exit."""
    import os
    import subprocess
    return subprocess.run(
        [sys.executable, "-m", "kerykeion_mcp.server"], cwd=tmp_path, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=120, env={**os.environ, **env})


def test_start_up_logs_each_phase_to_stderr(tmp_path):
    done = run_server(tmp_path)
    lines = done.stderr.splitlines()
    assert done.stdout == ""  # stdout is the protocol channel
    for pattern in (r"Starting Kerykeion MCP Server v[\d.]+ \(imports and engine check took \d+\.\d\ds\)",
                    r"Ephemeris: swisseph, data files in \S+",
                    r"Warm-up done in \d+\.\d\ds",
                    r"Ready after \d+\.\d\ds: serving stdio"):
        assert any(re.search(pattern, line) for line in lines), (pattern, done.stderr)


def test_missing_ephemeris_files_exit_with_one_readable_line(tmp_path):
    done = run_server(tmp_path, KERYKEION_EPHE_PATH=str(tmp_path))
    assert done.returncode == 1
    assert "Traceback" not in done.stderr, done.stderr
    errors = [line for line in done.stderr.splitlines() if line.startswith("ERROR:")]
    assert len(errors) == 1 and "sepl_18.se1" in errors[0] and str(tmp_path) in errors[0], done.stderr
    assert "swisseph_setup" in errors[0]
