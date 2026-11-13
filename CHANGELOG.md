# Changelog

## Unreleased

### Fixed
- **A local time that happened twice, or never, now says what to do.** A birth at 01:30 on a clocks-back night is rejected by kerykeion with a message telling the caller to "specify is_dst", which no tool accepts, and the hint was empty. The error now reads "01:30 on 1990-10-28 occurred twice in Europe/London: the clocks went back across it", with `type: "AmbiguousTimeError"` and a hint that gives each reading in UTC to pass with `tz_str="UTC"` ("01:30 BST (UTC+1) is 1990-10-28 00:30 UTC; 01:30 GMT (UTC+0) is 1990-10-28 01:30 UTC"). A time skipped when the clocks went forward gets `type: "NonexistentTimeError"` and the UTC time it would be on a clock not yet put forward. Other library errors are unchanged.

## 0.3.2

### Changed
- **Contract change: the angles carry no `motion` or `speed`.** This reverses 0.3.1's retrograde flag. In every chart's text (natal, synastry, transit, composite, return, event, current positions), the Ascendant, Descendant, MC and IC `<point>` elements now have neither attribute. The speeds (e.g. 254°/day for London's Ascendant) are the sky's daily turn, not motion through the zodiac, and 0.3.1 marked a polar Ascendant that turns backwards `motion="retrograde"` (McMurdo: `speed="-238.5403"`). It also drew ℞ beside it on the wheel. Both are gone. Returns showed a hard-coded `motion="direct"` with the same kind of speed; that is gone too. Planets and nodes are unchanged. The speed stays in the model, so `movement="applying"`/`"separating"` on aspects to an angle is unchanged.

### Added
- **`exclude_derived_points`** on every tool that lists aspects: `get_aspects`, `get_synastry_aspects`, `get_chart_patterns`, and the text and wheel of the natal, synastry, transit, composite, return and event charts. With `true`, aspects to the Descendant, IC and South Node are dropped (each mirrors one to the Ascendant, MC or North Node), and so are aspects between two angles.
  - kerykeion already leaves out a chart's own Asc–Desc, MC–IC and node pairs. Across two charts it keeps every contact to both ends of each axis, so London × McMurdo goes from 116 synastry aspects to 76 (London's natal from 52 to 34).
  - **It defaults to `false`**, so default responses are unchanged. With `true`, `applied_settings` reports `exclude_derived_points: true`.
  - The one loss is a quintile to a derived point: its mirror is a 108° aspect, which isn't computed.
  - `relationship_score` is computed before the filter, so the option doesn't change it.
- Start-up logs each phase to stderr: `Starting Kerykeion MCP Server v0.3.2 (imports and engine check took N s)`, `Ephemeris: swisseph, data files in <path>`, `Warm-up done in N s` and `Ready after N s: serving stdio`.
- `scripts/startup_probe.py` launches the server as Claude Desktop does. It times `initialize`, `tools/list` and, with `--call`, a first tool call, and prints the server's stderr. `--cwd` launches it from another directory. README: a Windows troubleshooting section.

### Fixed
- Missing ephemeris files (or a wrong `KERYKEION_EPHE_PATH`) stop the server with one `ERROR: Cannot start: …` line naming the files, the path and the fix, and exit code 1. Before, the same message came at the end of a Python traceback.
- `kerykeion_mcp.__version__` had stayed at `0.3.0`.

### Considered, not changed
Windows measurements with Claude Desktop's command: `initialize` answers in 2.3–2.6 s warm, 8.8 s with the bytecode recompiled, and 28 s on the very first run.
- **Warm-up in a background thread after the handshake** was not adopted. On Windows the background warm-up never finished, still running after 20 s, because a native import blocks while the stdio reader waits on stdin (the 0.3.1 stall). The warm-up stays before serving.
- **Lazy cairosvg import** was not adopted. It would save about 0.3 s of the 2.5 s on Windows, but the start-up line `PNG conversion available` would become a guess.
- **uv overhead** is about 0.1 s per launch. The README suggests launching the venv's `python.exe` directly for robustness (no re-sync at launch), not for speed.

## 0.3.1

### Fixed
- **The first call to a fresh server no longer hangs on Windows.** It froze until the client sent another message, and a call with nothing after it got no reply at all (none within 30 s, 3 of 3 times). kerykeion loads numpy on the first chart, and on Windows that native load blocks while the stdio reader waits on stdin. The server now casts one chart at start-up, before it reads stdin. Batches of calls weren't affected: the next message unblocked the stall, and 10 of 10 three-call batches answered in about 10 s.
- **Composite houses are hung from the Ascendant, as immanuel does.** kerykeion's default anchor sometimes held the Midheaven instead. **About 7% of composites turn 180°**: Ascendant, MC and all twelve cusps (40 of 576 London/Svalbard pairs). With the same house system for both people, composites now match immanuel 0.12.2 to 0.0000°.
- **An angle moving backwards is flagged retrograde.** Inside the polar circles the Ascendant (and Descendant) really runs backwards through the zodiac for part of the day, but was marked `motion="direct"` beside its negative speed. The signed speed is kept, and the flag now follows it (speeds within 1e-6 of zero count as direct). immanuel 0.12.2 still reports these as not retrograde.
- **`transit_time` gives the moment actually cast**, in ISO format with the zone offset (e.g. `"2020-01-01T12:00:00+01:00"`), not `"current"`. `get_current_positions.timestamp` likewise.
- Return and event charts' text reads `<chart_analysis type="Solar Return">` / `"Lunar Return"` / `"Event"`, not `"Natal"`. Synastry and composite text is unchanged.

### Changed
- **Breaking:** a timed chart exactly at a pole (latitude ±90), for any subject or location, is refused with `{"status": "error", "type": "PoleError", ...}`. There is no horizon there, and the Ascendant came out as 0° Aries with speed 0. Use ±89.99. Other errors have no `type` key.
- **Contract change:** when a synastry or transit mixes house systems (one polar person, Placidus/Koch → Porphyry), `applied_settings.house_system` describes both, e.g. `"mixed: person1 P (Placidus); person2 O (Porphyry, polar fallback from P Placidus)"`, instead of naming only the fallback. A second warning names who has which. Each chart keeps its own houses because each overlay reads the houses of the chart it lands in; a composite has one set of houses, so it still casts both people with Porphyry.
- **Contract change:** with city or nation left blank, the text's `city`/`nation` fields stay empty (`city="" nation=""`) instead of holding coordinates; the element's `lat`/`lng` carry them. The wheel label still shows them ("41.90N, 12.50E").
- **Contract change:** `get_current_positions` text labels its block `<moment …>` instead of `<birth_data …>`.

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
