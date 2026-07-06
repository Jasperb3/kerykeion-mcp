# CLAUDE.md - kerykeion-mcp

Project-specific instructions. Read alongside the global CLAUDE.md.

## What this is

An MCP server wrapping [Kerykeion](https://github.com/g-battaglia/kerykeion) (Swiss Ephemeris via pyswisseph) for astrological chart generation. Consumed primarily by a **Windows Claude Desktop** install; this WSL checkout is a dev/test clone. There is no way to drive the Windows Claude Desktop client from here — verify changes with `uv run pytest -q` and direct function calls against `kerykeion_mcp.server`, not by trying to launch the production client.

## Astrological commitments

- **Tropical zodiac, Placidus houses** are the defaults. Sidereal is supported everywhere but requires an explicit `sidereal_mode` — never let `zodiac_type="Sidereal"` silently resolve to an ayanamsha (kerykeion's own default is Fagan/Bradley, not the Lahiri that "Vedic" usually implies).
- **Never silently substitute a meaning-bearing parameter.** House system, zodiac type, sidereal mode, chart style: invalid values raise an educational `ChartInputError` (see `src/kerykeion_mcp/validation.py`), they are never coerced to a default. Cosmetic parameters (`theme`, `language`) may still coerce.
- Every successful tool response includes `status: "success"` and an `applied_settings` block echoing exactly what was computed (`build_applied_settings` in `server.py`). Every error response is `{"status": "error", "error": ..., "hint": ...}` — no raw tracebacks reach the client (`handle_chart_errors` decorator).
- Interpretation text (`text` field) is Kerykeion's structured `to_context` output, not a synthesized reading — synthesis is the consuming LLM's job, framed by `SERVER_INSTRUCTIONS` (developmental framing, no fatalistic/medical predictions, birth-time-confidence caveats for house-dependent claims).

## Privacy posture

- All calculation is offline (`online=False` everywhere) — birth data never leaves the machine.
- Subject names log at DEBUG only; INFO-level logs (the default, and what MCP clients typically capture) never contain PII.
- `output_dir` is confined to `~/.kerykeion_charts` or the `KERYKEION_OUTPUT_BASE` env var — a client cannot make this server write files to an arbitrary path.
- HTTP transports (`--http`/`--sse`) default to loopback (`127.0.0.1`); binding wider requires an explicit `--host` flag and logs a warning.

## Testing

- `tests/` is the real test suite (`uv run pytest -q`). `test_tools.py` (a manual print-script) was removed — do not recreate that pattern.
- `tests/conftest.py` has `birth_rome`/`birth_london` fixtures for consistent golden-value tests, and `tmp_output_dir` (sets `KERYKEION_OUTPUT_BASE` so image-writing tests don't hit `~/.kerykeion_charts`).
- Golden-value tests pin known chart facts (e.g. Sun sign for a fixed birth) against the live Kerykeion install — treat these as regression guards on celestial mechanics, not on the server's own logic.

## Before trusting a Kerykeion API assumption

Verify against the installed library (`python -c "import inspect, kerykeion; print(inspect.signature(...))"`) rather than training-data memory — factory signatures and accepted `sidereal_mode`/`houses_system_identifier` literals have changed across versions and don't always match what's written in older docs or this file.
