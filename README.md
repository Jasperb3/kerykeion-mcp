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

`generate_planetary_return` additionally accepts `return_month`/`return_day` (defaults to today, so lunar returns aren't stuck searching from January) and `return_lat`/`return_lng`/`return_tz_str` to cast the return chart for the person's current location instead of their birth location.

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

## License

MIT
