"""
Start-up: every lazy native import happens before the stdio transport reads.

On Windows, loading a native extension (numpy, which kerykeion pulls in on
the first chart via its fixed-star catalog, libephemeris and erfa) blocks
while the stdio reader thread has a read pending on stdin. A tool call that
triggered the import froze the event loop until the client sent another
message, so a batch of calls timed out. main() casts one chart first.
"""

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
