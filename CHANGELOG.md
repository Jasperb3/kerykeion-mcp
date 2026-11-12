# Changelog

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
