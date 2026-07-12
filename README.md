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
- **House system**: Placidus (`"P"`) by default. Other systems (Whole Sign `"W"`, Koch `"K"`, Equal `"A"`, Campanus `"C"`, Regiomontanus `"R"`, Morinus `"M"`, Porphyry `"O"`, Gauquelin Sectors `"G"`) are available via `house_system`.
- **Interpretation text**: the `text` field in every response is Kerykeion's structured `to_context` output -- positions, aspects, and dignities. It is not a synthesized reading; synthesis happens in the consuming LLM, guided by the server's interpretation-framing instructions (developmental framing, no fatalistic/medical predictions, birth-time-confidence caveats for house-dependent claims).
- **Relationship score**: `generate_synastry_chart`'s `relationship_score` uses Ciro Discepolo's method -- a count of specific aspect contacts, not a holistic verdict on relationship viability.
- **Validation**: meaning-bearing parameters (house system, zodiac type, sidereal mode, chart style) are rejected with an educational error if invalid, never silently substituted. Every successful response includes `applied_settings`, echoing exactly what was computed.

## Privacy

- All calculation is local and offline (`online=False` everywhere) -- birth data never leaves the machine running this server.
- Subject names are logged at DEBUG only; INFO-level logs omit personal data.
- Chart files are written to `~/.kerykeion_charts` by default, or a custom directory (see `output_dir` / `KERYKEION_OUTPUT_BASE` below).
- The default HTTP bind is loopback-only (`127.0.0.1`); binding to all interfaces requires an explicit opt-in and logs a warning.

## Installation

### Requirements

- Python 3.10+
- [Kerykeion](https://github.com/g-battaglia/kerykeion) 5.6+ (Swiss Ephemeris via `pyswisseph`), `pytz`, `cairosvg` -- all installed automatically below.

### Using uv (Recommended)

```bash
cd kerykeion-mcp
uv sync
```

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
| `test_contracts.py` | Response shape -- `status`, `applied_settings`, error format |
| `test_patterns.py` | Pattern-detection logic in `patterns.py` (stelliums, T-squares, yods, etc.) against synthetic aspect fixtures |
| `test_security.py` | Output-path confinement, PII-in-logs, loopback-only HTTP bind |
| `test_validation.py` | Rejection behavior for invalid house systems, zodiac types, sidereal modes, chart styles |

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
- **theme**: "classic", "light", "dark", "strawberry", "dark-high-contrast"
- **language**: "EN" (default), "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"
- **house_system**: "P" (Placidus), "W" (Whole Sign), "K" (Koch), "M" (Morinus), etc.
- **zodiac_type** / **sidereal_mode**: "Tropical" (default) or "Sidereal" (requires `sidereal_mode`, e.g. "LAHIRI")
- **output_format**: "text", "images", or "all"
- **output_dir**: Custom directory to save chart images (optional; must resolve under `~/.kerykeion_charts` or `KERYKEION_OUTPUT_BASE`)
- **chart_style**: "full" (default), "wheel_only", or "aspect_grid"

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
