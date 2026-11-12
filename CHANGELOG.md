# Changelog

## 0.3.0

### Changed
- **kerykeion 6.0.x** (`kerykeion[swiss]>=6.0.5,<6.1`), on its **Swiss Ephemeris** backend. The server forces `KERYKEION_BACKEND=swisseph` (6.x defaults to libephemeris) so positions keep matching the immanuel MCP server.
- **Breaking:** Python 3.12+ (kerykeion 6 requires it).
- **Breaking:** the Swiss Ephemeris data files are required. Run `uv run python -m kerykeion.swisseph_setup` once, or set `KERYKEION_EPHE_PATH`. The server refuses to start without them; kerykeion would otherwise silently use the lower-precision Moshier ephemeris.
- The `text` field is kerykeion 6's XML-like `to_context` format (e.g. `<point name="Sun" … />`, `<config house_system="…" />`), and it now includes kerykeion's own `<polar_house_fallback …/>` element.
- Aspects, the chart text and the wheels keep the points and orbs of earlier releases: 18 points (with Mean Lilith, the South Node, Descendant and IC), conjunction/opposition 10°, trine 8°, sextile 6°, square 5°, quintile 1°, and no extra Sun/Moon orb. kerykeion 6's own defaults are narrower (14 points, five aspects at 5–6°, +1.5° for the Sun and Moon), so the server passes these explicitly (`ASPECT_SETTINGS` in `server.py`).
- The polar latitude shim (`polar.py`) is gone: kerykeion 6 keeps the true latitude and substitutes Porphyry itself. The response contract is unchanged (`applied_settings.house_system`, `house_system_by_subject`, `warnings`, the `Warning:` text prefix).

### Fixed
- **Planets and the Moon now come from the Swiss Ephemeris data files.** kerykeion 5.6 bundled only `seas_18.se1`, so the Sun, Moon and planets were computed with the Moshier ephemeris, differing from immanuel by arcseconds. The 2020 solar-return test moment moves from 20:41:15 to 20:41:13 (+02:00), matching `swe.solcross_ut`.
- **"Now" charts use the real current time.** kerykeion 5.6's `from_current_time` read the machine's local clock and interpreted it in `tz_str`, so current positions and current transits were off by the machine's offset from that zone.
- Regiomontanus and Campanus charts far inside the polar circles, whose cusps run backwards at some times, are cast instead of returning an error.
- An aspect is reported only within its orb. kerykeion 5.6 compared the whole-degree part of the separation, so aspects up to almost 1° past the orb (e.g. a 10.31° conjunction) were included when the separation was wider than exact.
- The synastry `relationship_score` uses Ciro Discepolo's own orbs (conjunction and opposition 8°, trine 7°, square 5°, sextile 4°; kerykeion 6). 5.6 used the chart orbs, so e.g. a 10.5° Sun–Moon conjunction scored 8 points; such scores now come out lower.
- PNG wheels render again: kerykeion 6's SVGs use CSS `var(--name, fallback)`, which the SVG→PNG converter didn't resolve.

## 0.2.1

### Fixed
- **No more "GB" in location labels.** kerykeion fills a blank `nation` with "GB" and prints "{city}, {nation}" on the wheel *and* in the text, so `city="Rome"` alone read "Rome, GB". Blank parts are now filled with coordinates: "Rome, 41.90N 12.50E", or "41.90N, 12.50E" with neither. Transit charts' transit place, which had no label at all and read "Greenwich, GB", now carries its coordinates.
- **`KERYKEION_OUTPUT_BASE` now sets the default image directory**, not only an extra allowed one. `~/.kerykeion_charts` stays allowed.
- **Planetary returns at latitude or longitude 0.0** (the equator, Greenwich) no longer fail: kerykeion 5.6's return factory treated 0.0 as missing.

### Changed
- kerykeion is pinned to `>=5.6.3,<5.7`. The polar shim refuses other versions, so an unpinned upgrade (5.7+, 6.x) stopped the server from starting.
- Dev dependencies moved from the deprecated `[tool.uv] dev-dependencies` to `[dependency-groups]`.

## 0.2.0

### Fixed
- **Polar-latitude charts are cast at their true latitude.** kerykeion silently moved every latitude beyond ±66° to ±66°, so polar charts had the wrong Ascendant (13° out at Tromsø, 138° at Longyearbyen) and houses, with no warning. The clamp is removed (`kerykeion_mcp/polar.py`).
- **Reported Porphyry fallback inside the polar circles.** Where the Swiss Ephemeris refuses Placidus or Koch (beyond about ±66.56°), the chart uses Porphyry cusps:
  - `applied_settings.house_system` reads `"O (Porphyry, polar fallback from P Placidus)"`;
  - a top-level `warnings` list says why, and `text` starts with the same warning;
  - two-subject tools add `applied_settings.house_system_by_subject`.
  This matches the immanuel MCP server. Responses outside the polar circles are unchanged.
- Regiomontanus/Campanus charts whose cusps run backwards (far inside the polar circles, at some times) return an educational error instead of kerykeion's raw exception.
- `swisseph.Error` now produces a structured error with a hint instead of "Internal error".

### Changed
- **Breaking:** `house_system="G"` (Gauquelin) is no longer advertised. kerykeion never accepted it, so it always failed; it now gets the server's own validation error.
