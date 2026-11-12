"""
Run kerykeion on the Swiss Ephemeris, with its data files, or not at all.

kerykeion 6 picks its ephemeris backend at import time: libephemeris (JPL
DE440) unless KERYKEION_BACKEND says otherwise. This server uses the Swiss
Ephemeris so its positions and cusps agree with the immanuel MCP server's,
which the master-astrologer skill compares against. Importing this module
(kerykeion_mcp/__init__.py does, before anything imports kerykeion) sets
KERYKEION_BACKEND=swisseph unless the environment already chose.

The swisseph backend needs the .se1 data files. Without them it silently
falls back to the lower-precision Moshier ephemeris, logging only a warning.
check() turns that into a startup error instead.
"""

import os

os.environ.setdefault("KERYKEION_BACKEND", "swisseph")

BACKEND = "swisseph"
# Planets, Moon and main asteroids (Chiron is an active point) for 1800-2400.
REQUIRED_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")


def check() -> None:
    from kerykeion.ephemeris_backend.backend import BACKEND_NAME, EPHE_DATA_PATH

    if BACKEND_NAME != BACKEND:
        raise RuntimeError(
            f"kerykeion is using the {BACKEND_NAME!r} ephemeris backend; this server "
            f"requires {BACKEND!r} so its positions match the Swiss Ephemeris. Unset "
            f"KERYKEION_BACKEND or set it to {BACKEND!r}, and install kerykeion[swiss].")
    missing = [name for name in REQUIRED_FILES
               if not (EPHE_DATA_PATH and os.path.isfile(os.path.join(EPHE_DATA_PATH, name)))]
    if missing:
        raise RuntimeError(
            f"Swiss Ephemeris data files missing ({', '.join(missing)}) in "
            f"{EPHE_DATA_PATH or '(no path)'}; kerykeion would silently fall back to the "
            f"Moshier ephemeris. Run `uv run python -m kerykeion.swisseph_setup` "
            f"(downloads them to ~/.kerykeion/sweph) or set KERYKEION_EPHE_PATH to a "
            f"directory that contains them.")
