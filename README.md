# Kerykeion MCP Server

An MCP (Model Context Protocol) server for astrological chart generation using the [Kerykeion](https://github.com/g-battaglia/kerykeion) library. Compatible with **Claude Desktop** and **ChatGPT Desktop**.

## Features

- **Natal Charts** - Birth chart generation with planetary positions, aspects, and house placements
- **Synastry Charts** - Relationship compatibility analysis between two people
- **Transit Charts** - Current transits to natal positions
- **Composite Charts** - Midpoint composite for relationship dynamics
- **Planetary Returns** - Solar, Lunar, and other planetary return charts (with relocation support)
- **Event Charts** - Charts for specific moments (electional, horary)
- **Current Positions** - Quick lookup of current planetary positions
- **Aspects** - Structured natal and synastry aspect lists for AI analysis
- **Chart Patterns** - Stelliums, T-squares, grand trines/crosses, yods, kites, and element/mode balance, each with a neutral, growth-oriented note

### Output Formats
- **Text** - AI-readable descriptions optimized for LLM interpretation
- **SVG** - Vector chart images saved to files (path returned in response)
- **PNG** - High-resolution (1600px) raster images (requires `cairosvg`)

## Astrological Foundations

- **Zodiac**: Tropical by default. Sidereal is supported on every chart tool via `zodiac_type="Sidereal"`, but requires an explicit `sidereal_mode` (e.g. `"LAHIRI"`, the standard ayanamsha for Vedic/Jyotish work) -- the server will reject a sidereal request with no mode rather than silently picking one.
- **House system**: Placidus (`"P"`) by default. Other systems (Whole Sign `"W"`, Koch `"K"`, Equal `"A"`, Campanus `"C"`, Regiomontanus `"R"`, Morinus `"M"`, Porphyry `"O"`) are available via `house_system`.
- **Polar latitudes**: charts are cast at their true latitude. Inside the polar circles (beyond about ±66.56°) Placidus and Koch houses don't exist, so kerykeion uses Porphyry cusps, as the Swiss Ephemeris itself does, and the server **reports it**: `applied_settings.house_system` reads `"O (Porphyry, polar fallback from P Placidus)"`, a `warnings` list explains why, and the `text` starts with the same warning. Two-subject tools add `applied_settings.house_system_by_subject`. Synastry and transit charts keep each chart's own houses, because each house overlay reads the houses of the chart it lands in: with one polar person, `applied_settings.house_system` reads e.g. `"mixed: person1 P (Placidus); person2 O (Porphyry, polar fallback from P Placidus)"` and a second warning names who has which. A composite has a single set of houses, so it casts both people with Porphyry instead (also reported). Every other system (Porphyry, Regiomontanus, Campanus, Equal, Whole Sign, Morinus) is cast as asked. The Ascendant, MC, planets, planet-to-planet aspects and patterns don't depend on the house system.
- **Interpretation text**: the `text` field in every response is Kerykeion's structured `to_context` output -- positions, aspects, and dignities. It is not a synthesized reading; synthesis happens in the consuming LLM, guided by the server's interpretation-framing instructions (developmental framing, no fatalistic/medical predictions, birth-time-confidence caveats for house-dependent claims).
- **Relationship score**: `generate_synastry_chart`'s `relationship_score` uses Ciro Discepolo's method -- a count of specific aspect contacts, not a holistic verdict on relationship viability.
- **Validation**: meaning-bearing parameters (house system, zodiac type, sidereal mode, chart style) are rejected with an educational error if invalid, never silently substituted. The one exception is the reported polar fallback above. Every successful response includes `applied_settings`, echoing exactly what was computed.

## Privacy

- All calculation is local and offline (`online=False` everywhere) -- birth data never leaves the machine running this server.
- Subject names are logged at DEBUG only; INFO-level logs omit personal data.
- Chart files are written to `KERYKEION_OUTPUT_BASE` if that environment variable is set, otherwise `~/.kerykeion_charts`; an `output_dir` must resolve under one of those two.
- The default HTTP bind is loopback-only (`127.0.0.1`); binding to all interfaces requires an explicit opt-in and logs a warning.

## Installation

### Requirements

- Python 3.12+
- [Kerykeion](https://github.com/g-battaglia/kerykeion) 6.0.x with its Swiss Ephemeris backend (`kerykeion[swiss]`, i.e. `pyswisseph`), `pytz`, `cairosvg` -- all installed automatically below.
- **The Swiss Ephemeris data files**, once per machine (see below). The server refuses to start without them rather than silently computing with the lower-precision Moshier ephemeris.

### Using uv (Recommended)

```bash
cd kerykeion-mcp
uv sync
uv run python -m kerykeion.swisseph_setup   # one-time: downloads the .se1 files to ~/.kerykeion/sweph
```

`swisseph_setup` asks you to accept the Swiss Ephemeris data licence (AGPL-3.0, Astrodienst AG) and downloads from github.com/aloistr/swisseph. On Windows the files go to `%USERPROFILE%\.kerykeion\sweph`; run it there too before starting Claude Desktop. If you already have the files elsewhere, set `KERYKEION_EPHE_PATH` to that directory instead (also in the Claude Desktop server `env`). The server sets `KERYKEION_BACKEND=swisseph` itself.

### Using pip

```bash
pip install -e .
```

### System Dependencies for PNG Support

For PNG conversion, you need Cairo graphics library:

```bash
# Ubuntu/Debian
sudo apt install libcairo2-dev

# macOS
brew install cairo

# Windows - See cairosvg documentation
```

### Development

```bash
uv sync --extra dev
uv run pytest -q
```

| Test file | Guards |
|---|---|
| `test_astrological_correctness.py` | Golden-value regression checks against the live Kerykeion/Swiss Ephemeris install (e.g. known Sun sign for a fixed birth) |
| `test_contracts.py` | Response shape -- `status`, `applied_settings`, error format, `exclude_derived_points` |
| `test_polar.py` | Polar latitudes: true latitude kept, cusps match the Swiss Ephemeris at the true latitude, the Placidus/Koch → Porphyry fallback is reported by every tool, pole charts are refused, the angles carry no motion or speed in any output |
| `test_composite.py` | Composite houses hang from the Ascendant (immanuel's construction) over a London/Svalbard grid: cusp midpoints, Asc on cusp 1, MC on cusp 10, planet houses |
| `test_startup.py` | `main()` loads kerykeion's lazy native imports before serving stdio (the Windows first-call stall), logs each start-up phase, exits with one line when the ephemeris files are missing |
| `test_engine.py` | The Swiss Ephemeris backend with its data files (not libephemeris, not Moshier); planets match the immanuel engine |
| `test_patterns.py` | Pattern-detection logic in `patterns.py` (stelliums, T-squares, yods, etc.) against synthetic aspect fixtures |
| `test_security.py` | Output-path confinement, PII-in-logs, loopback-only HTTP bind |
| `test_validation.py` | Rejection behavior for invalid house systems, zodiac types, sidereal modes, chart styles; structured Swiss Ephemeris errors |

## Usage

### Development Mode (MCP Inspector)

```bash
uv run mcp dev src/kerykeion_mcp/server.py
```

The MCP Inspector opens its own local UI (typically `http://localhost:6274`) -- it does not serve at `:8000/mcp`.

### Claude Desktop Configuration

Add to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`  
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "kerykeion-charts": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/kerykeion-mcp",
        "python", "-m", "kerykeion_mcp.server"
      ]
    }
  }
}
```

Or install directly:

```bash
uv run mcp install src/kerykeion_mcp/server.py --name "Kerykeion Charts"
```

### Windows troubleshooting

**Logs.** The server logs to stderr, which Claude Desktop is documented to write to `%APPDATA%\Claude\logs\mcp-server-kerykeion-charts.log`. It never writes to stdout, which carries the protocol. A healthy start looks like this:

```
INFO:kerykeion_mcp.server:Starting Kerykeion MCP Server v0.3.2 (imports and engine check took 2.04s)
INFO:kerykeion_mcp.server:Ephemeris: swisseph, data files in C:\Users\<you>\.kerykeion\sweph
INFO:kerykeion_mcp.server:PNG conversion available: True
INFO:kerykeion_mcp.server:Warm-up done in 0.38s
INFO:kerykeion_mcp.server:Ready after 2.46s: serving stdio (use --http for HTTP mode)
```

With the ephemeris files missing (`sepl_18.se1`, `semo_18.se1` and `seas_18.se1` in `%USERPROFILE%\.kerykeion\sweph`, or in `KERYKEION_EPHE_PATH`), it stops with exit code 1 and one line, `ERROR:...:Cannot start: Swiss Ephemeris data files missing (...) in <path>; ...`, which names the fix.

If that log has nothing recent, check its date before concluding the server didn't start. On one install, every `mcp-server-*.log` (for all servers) and `main.log` stopped updating on the same day while the servers kept running.

**See it start for yourself.** `scripts/startup_probe.py` launches the server the way Claude Desktop does, sends `initialize` and `tools/list`, and prints the time to each reply with the server's stderr:

```
python scripts\startup_probe.py                     # Desktop's uv command
python scripts\startup_probe.py --cwd C:\ --call     # from another directory, plus one tool call
python scripts\startup_probe.py -- .venv\Scripts\python.exe -m kerykeion_mcp.server
```

On a Windows 11 desktop, `initialize` answers in about 2.3–2.6 s warm. After a reboot or an update it can take 9 s (the `.pyc` files recompiled) to 28 s (the disk cache cold as well). `uv run` itself adds about 0.1 s.

**Skipping uv at launch.** `uv run` checks the environment on every launch and re-syncs it after a `git pull` that changes `uv.lock` or the version. Claude Desktop may run more than one copy of the server, and a re-sync while another copy holds the venv's DLLs open can fail. To rule that out, point Desktop at the venv's Python and run `uv sync` yourself, with Claude Desktop quit, after each update:

```json
"kerykeion-charts": {
  "command": "C:\\path\\to\\kerykeion-mcp\\.venv\\Scripts\\python.exe",
  "args": ["-m", "kerykeion_mcp.server"],
  "env": {"KERYKEION_EPHE_PATH": "C:\\Users\\<you>\\.kerykeion\\sweph"}
}
```

`env` is optional (the server finds `%USERPROFILE%\.kerykeion\sweph` by itself). Give `KERYKEION_EPHE_PATH` and `KERYKEION_OUTPUT_BASE` as absolute paths. Claude Desktop chooses the working directory, so a relative path would resolve somewhere unexpected.

### ChatGPT Desktop Configuration

> **Important**: ChatGPT requires HTTPS URLs for MCP connectors. You'll need to tunnel your local server.

1. **Start the server with Streamable HTTP transport**:
   ```bash
   uv run python -m kerykeion_mcp.server --http
   ```
   Server runs at `http://127.0.0.1:8000` by default. Pass `--host 0.0.0.0` to bind on all interfaces if you need the tunnel to reach it -- this exposes the server (which accepts birth data and writes files) to your local network, so only do it on a trusted network.

2. **Create an HTTPS tunnel** using ngrok (or similar):
   ```bash
   ngrok http 8000
   ```
   You'll get a URL like: `https://abc123.ngrok-free.app`

3. **Add to ChatGPT**:
   - Enable Developer Mode: Settings → Connectors → Advanced → Developer mode
   - Add MCP Server URL: `https://abc123.ngrok-free.app`

`--sse` (legacy HTTP+SSE transport) is still available for older clients but is deprecated in favor of `--http`.

## Available Tools

| Tool | Description |
|------|-------------|
| `generate_natal_chart` | Create a birth chart |
| `generate_synastry_chart` | Relationship compatibility analysis |
| `generate_transit_chart` | Current or specified transits to natal |
| `generate_composite_chart` | Midpoint composite for a couple |
| `generate_planetary_return` | Solar/Lunar returns, with optional relocation |
| `generate_event_chart` | Chart for any specific moment |
| `get_current_positions` | Current planetary positions (text only) |
| `get_aspects` | Get natal chart aspects without images |
| `get_synastry_aspects` | Get inter-chart aspects for compatibility |
| `get_chart_patterns` | Detect stelliums, T-squares, grand trines/crosses, yods, kites, and element/mode balance |

### Common Parameters

Most chart tools accept:
- **lat/lng**: Coordinates (positive N/E, negative S/W)
- **tz_str**: IANA timezone (e.g., "Europe/Rome", "America/New_York")
- **city/nation**: Optional labels for the chart header (calculation always uses lat/lng; if omitted, a coordinate-derived label like `"41.90N, 12.50E"` is used instead of defaulting to Greenwich)
- **theme**: "classic" (default), "dark" or "black-and-white". Any other name gives "classic", and `applied_settings.theme` says so
- **language**: "EN" (default), "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"
- **house_system**: "P" (Placidus), "W" (Whole Sign), "K" (Koch), "M" (Morinus), etc.
- **zodiac_type** / **sidereal_mode**: "Tropical" (default) or "Sidereal" (requires `sidereal_mode`, e.g. "LAHIRI")
- **output_format**: "text", "images", or "all"
- **output_dir**: Custom directory to save chart images (optional; must resolve under `~/.kerykeion_charts` or `KERYKEION_OUTPUT_BASE`; defaults to `KERYKEION_OUTPUT_BASE` if set, else `~/.kerykeion_charts`)
- **city** / **nation**: labels only. Whatever is left blank is filled with coordinates ("Rome, 41.90N 12.50E", or just "41.90N, 12.50E"), never with kerykeion's default "Greenwich, GB".
- **chart_style**: "full" (default), "wheel_only", or "aspect_grid"
- **exclude_derived_points**: `false` (default) or `true`, on every tool that lists aspects. `true` drops aspects to the Descendant, IC and South Node, which mirror aspects to the Ascendant, MC and North Node (a trine to one end of an axis is a sextile to the other), and aspects between two angles. A single chart already leaves out its own Asc–Desc, MC–IC and node pairs. Across two charts every contact appears to both ends of each axis, so the London × McMurdo synastry in the tests goes from 116 aspects to 76. The one loss is a quintile to a derived point: its mirror is a 108° aspect, which the server doesn't compute. The response echoes `applied_settings.exclude_derived_points: true`.

`generate_planetary_return` additionally accepts `return_month`/`return_day` (defaults to today, so lunar returns aren't stuck searching from January), `return_lat`/`return_lng`/`return_tz_str` to cast the return chart for the person's current location instead of their birth location, and `return_city`/`return_nation` to label that location (relocated returns default to a coordinate label). Sidereal return charts are rejected with an explanatory error — see Roadmap.

`generate_synastry_chart` returns `relationship_score` as an object (`value`, `description`, `is_destiny_sign`, `breakdown`, `scale`, `note`) using Ciro Discepolo's method — one lens among many, not a verdict on relationship viability.

`get_chart_patterns` returns `patterns` (a list of `{type, planets, note}` -- plus `apex`/`trine_planets` for T-squares/kites), and `element_balance`/`mode_balance` as `{counts, missing}`, e.g.:

```json
{
  "patterns": [
    {"type": "grand_trine", "planets": ["Jupiter", "Moon", "Venus"], "note": "an easeful circuit of talent that rewards conscious activation rather than passive reliance"}
  ],
  "element_balance": {"counts": {"Fire": 2, "Earth": 3, "Air": 4, "Water": 1}, "missing": []},
  "mode_balance": {"counts": {"Cardinal": 3, "Fixed": 4, "Mutable": 3}, "missing": []}
}
```

### Response Format

Every tool returns `status` ("success" or "error") and, on success, `applied_settings` reporting exactly what was computed:

```json
{
  "status": "success",
  "chart_type": "Natal",
  "subject_name": "Test",
  "applied_settings": {
    "house_system": "P (Placidus)",
    "zodiac_type": "Tropical",
    "sidereal_mode": null,
    "theme": "classic",
    "language": "EN",
    "chart_style": "full"
  },
  "text": "AI-readable chart analysis...",
  "svg_path": "/home/user/.kerykeion_charts/natal_test_20260106.svg",
  "png_path": "/home/user/.kerykeion_charts/natal_test_20260106.png",
  "output_dir": "/home/user/.kerykeion_charts"
}
```

A chart inside a polar circle cast with Placidus or Koch also carries a `warnings` list (present only when it has entries):

```json
{
  "status": "success",
  "applied_settings": {"house_system": "O (Porphyry, polar fallback from P Placidus)", "...": "..."},
  "warnings": ["A chart in this response lies inside a polar circle, where Placidus houses are undefined, so the Swiss Ephemeris used Porphyry cusps instead. The Ascendant and MC are unaffected. Pass house_system=\"W\" (or another non-polar system) to avoid the fallback."],
  "text": "Warning: A chart in this response lies inside a polar circle, ..."
}
```

Exactly at a pole (latitude ±90) there is no horizon, so a timed chart is refused for every subject and location with `"type": "PoleError"`; use ±89.99.

A local time that happened twice (the clocks went back) or never (they went forward) is refused, because the tools take no daylight-saving flag. The error has `"type": "AmbiguousTimeError"` or `"NonexistentTimeError"`, and its hint gives each reading in UTC, to pass with `tz_str="UTC"` and the same coordinates: for 01:30 on 28 October 1990 in London, "01:30 BST (UTC+1) is 1990-10-28 00:30 UTC; 01:30 GMT (UTC+0) is 1990-10-28 01:30 UTC".

Invalid input returns a structured error instead of a raw exception:

```json
{
  "status": "error",
  "error": "Longitude 500.0 is outside the valid range -180 to +180 (positive = East).",
  "hint": ""
}
```

> **Note**: Chart images are saved to files rather than returned inline. This keeps responses small and prevents MCP clients from showing "Tool result too large" messages. The AI assistant can read SVG files directly from `svg_path` if needed for embedding.

## Embedding Charts in Claude Artifacts

### Method 1: Read SVG File (Recommended)

The AI assistant can read the SVG file directly from `svg_path` and embed its contents in an HTML artifact.

### Method 2: PNG with File Path

Response includes `png_path` for local file linking:

```markdown
![Chart](file:///C:/Users/.../chart.png)
```

Download the markdown file - image renders from local path.

## Example Usage

Ask Claude or ChatGPT:

> "Generate a natal chart for someone born June 15, 1990 at 2:30 PM in Rome 
> (lat: 41.9028, lng: 12.4964, timezone: Europe/Rome)"

> "Create a synastry chart comparing Person A (born Jan 1, 1985 in NYC) 
> and Person B (born Dec 25, 1987 in London)"

> "What are the current planetary transits to my natal chart?"

## Prompts

The server includes pre-defined prompts to guide conversations:
- **natal_chart_prompt** - Template for creating natal charts
- **synastry_prompt** - Template for relationship compatibility
- **transit_prompt** - Template for transit analysis

## Roadmap

- **Unknown-birth-time support** — noon default with suppressed angles/houses, so house-dependent claims are never presented for an unknown time.
- **Annual profections tool** — time-lord technique that pairs naturally with the existing return charts.
- **Solar-arc directions** — a widely used predictive technique not covered by transits or returns.
- **Sidereal return charts** — blocked upstream: kerykeion's return search matches the natal sidereal longitude against transiting *tropical* longitudes (verified by probe, ~25 days off for LAHIRI), so the server rejects sidereal returns rather than shipping silently wrong charts.
- **Transit-aspect list tool** — deliberately deferred; the Immanuel MCP's `transit_to_natal` tools already cover fast transit aspect analysis in this stack.

## License

MIT
