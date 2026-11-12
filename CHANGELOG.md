# Changelog

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
