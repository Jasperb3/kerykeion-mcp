# CLAUDE.md - kerykeion-mcp

Project-specific instructions. Read alongside the global CLAUDE.md.

## What this is

An MCP server wrapping [Kerykeion](https://github.com/g-battaglia/kerykeion) (Swiss Ephemeris via pyswisseph) for astrological chart generation. Consumed primarily by a **Windows Claude Desktop** install; this WSL checkout is a dev/test clone. There is no way to drive the Windows Claude Desktop client from here — verify changes with `uv run pytest -q` and direct function calls against `kerykeion_mcp.server`, not by trying to launch the production client.

## Astrological commitments

- **Tropical zodiac, Placidus houses** are the defaults. Sidereal is supported everywhere but requires an explicit `sidereal_mode` — never let `zodiac_type="Sidereal"` silently resolve to an ayanamsha (kerykeion's own default is Fagan/Bradley, not the Lahiri that "Vedic" usually implies).
- **Never silently substitute a meaning-bearing parameter.** House system, zodiac type, sidereal mode, chart style: invalid values raise an educational `ChartInputError` (see `src/kerykeion_mcp/validation.py`), they are never coerced to a default. Cosmetic parameters (`theme`, `language`) may still coerce.
  - **The one documented exception: the polar house fallback.** Inside the polar circles (|lat| ≥ 90° − obliquity, about 66.56°) the Swiss Ephemeris refuses Placidus and Koch, and kerykeion 6 casts that subject's houses with Porphyry at the true latitude, recording it in `polar_house_fallbacks` / `effective_houses_system_identifier`; the server reports it (`fell_back` and `report_polar_fallback` in `server.py`). This is allowed because (1) it is never silent: `applied_settings.house_system` reads `"O (Porphyry, polar fallback from P Placidus)"`, a top-level `warnings` list says why, and the `text` starts with the same warning; (2) it is what the Swiss Ephemeris C library itself switches to, and what the immanuel MCP server does, so both engines' cusps agree; (3) Placidus is the default, so rejecting instead would fail every default polar call. Let kerykeion and the Swiss Ephemeris decide when to fall back. Don't add a latitude test of your own, and don't extend the fallback to any other parameter or failure. (A composite with one polar person casts both with Porphyry, also reported, because a composite has a single set of houses and kerykeion refuses mixed house systems. Synastry and transits instead keep each chart's own system, since each overlay reads the houses of the chart it lands in; `applied_settings.house_system` then reads `"mixed: person1 …; person2 …"`.)
- **Exactly at a pole (|lat| = 90) a timed chart is refused** (`validate_coordinates`, `type: "PoleError"`, as immanuel does): there is no horizon, and the Swiss Ephemeris would return a meaningless Ascendant.
- **Polar latitudes are cast at the true latitude** (kerykeion ≥6; 5.6 silently clamped |lat| > 66° to 66°, which the server used to patch out).
- **Ephemeris engine: the Swiss Ephemeris, with its data files, or nothing.** kerykeion 6 defaults to libephemeris; `src/kerykeion_mcp/engine.py` (imported by the package `__init__` before anything imports kerykeion) sets `KERYKEION_BACKEND=swisseph`, and `engine.check()` at server import refuses to start on another backend or without `sepl_18`/`semo_18`/`seas_18.se1` (kerykeion would silently use the lower-precision Moshier ephemeris). That keeps positions identical to the immanuel MCP server's. Get the files with `uv run python -m kerykeion.swisseph_setup` (to `~/.kerykeion/sweph`) or point `KERYKEION_EPHE_PATH` at them; tests need them too.
- **Aspect points and orbs are the 5.x set** (`ASPECT_SETTINGS` and `ACTIVE_POINTS` in `server.py`, passed to every subject, chart-data and aspects call). kerykeion 6's defaults are narrower and would silently drop Lilith, the South Node, Descendant, IC, the quintile and the wide orbs; don't rely on kerykeion's defaults for these.
- Every successful tool response includes `status: "success"` and an `applied_settings` block echoing exactly what was computed (`build_applied_settings` in `server.py`, adjusted by `report_polar_fallback`). A top-level `warnings` list appears only when it has entries, so ordinary responses are unchanged. Every error response is `{"status": "error", "error": ..., "hint": ...}` — no raw tracebacks reach the client (`handle_chart_errors` decorator).
- Interpretation text (`text` field) is Kerykeion's structured `to_context` output, not a synthesized reading — synthesis is the consuming LLM's job, framed by `SERVER_INSTRUCTIONS` (developmental framing, no fatalistic/medical predictions, birth-time-confidence caveats for house-dependent claims).

## Privacy posture

- All calculation is offline (`online=False` everywhere) — birth data never leaves the machine.
- Subject names log at DEBUG only; INFO-level logs (the default, and what MCP clients typically capture) never contain PII.
- `output_dir` is confined to `~/.kerykeion_charts` or the `KERYKEION_OUTPUT_BASE` env var — a client cannot make this server write files to an arbitrary path.
- HTTP transports (`--http`/`--sse`) default to loopback (`127.0.0.1`); binding wider requires an explicit `--host` flag and logs a warning.

## Testing

- `tests/` is the real test suite (`uv run pytest -q`). `test_tools.py` (a manual print-script) was removed — do not recreate that pattern.
- `tests/conftest.py` has `birth_rome`/`birth_london` fixtures for consistent golden-value tests, and `tmp_output_dir` (sets `KERYKEION_OUTPUT_BASE`, which is also the default image directory when set, so image-writing tests don't hit `~/.kerykeion_charts`).
- Golden-value tests pin known chart facts (e.g. Sun sign for a fixed birth) against the live Kerykeion install — treat these as regression guards on celestial mechanics, not on the server's own logic.

## Before trusting a Kerykeion API assumption

kerykeion is pinned to a minor series (`pyproject.toml`). Widen the pin only after `tests/test_polar.py` and `tests/test_engine.py` pass on the new release, and re-check the attributes the server reads (`effective_houses_system_identifier`, `polar_house_fallbacks`, `kerykeion.ephemeris_backend.backend`). `to_context` output is kerykeion's XML-like format since 6.0; text assertions in tests match its elements.

Verify against the installed library (`python -c "import inspect, kerykeion; print(inspect.signature(...))"`) rather than training-data memory — factory signatures and accepted `sidereal_mode`/`houses_system_identifier` literals have changed across versions and don't always match what's written in older docs or this file.
