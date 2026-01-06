# Kerykeion MCP Server

An MCP (Model Context Protocol) server for astrological chart generation using the [Kerykeion](https://github.com/g-battaglia/kerykeion) library. Compatible with **Claude Desktop** and **ChatGPT Desktop**.

## Features

- **Natal Charts** - Birth chart generation with planetary positions, aspects, and house placements
- **Synastry Charts** - Relationship compatibility analysis between two people
- **Transit Charts** - Current transits to natal positions
- **Composite Charts** - Midpoint composite for relationship dynamics
- **Planetary Returns** - Solar, Lunar, and other planetary return charts
- **Event Charts** - Charts for specific moments (electional, horary)
- **Current Positions** - Quick lookup of current planetary positions

### Output Formats
- **Text** - AI-readable descriptions optimized for LLM interpretation
- **SVG** - Vector chart images saved to files (path returned in response)
- **PNG** - High-resolution (1600px) raster images (requires `cairosvg`)

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

Then open the MCP Inspector at `http://localhost:8000/mcp` to test tools.

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

1. **Start the server with SSE transport**:
   ```bash
   uv run python -m kerykeion_mcp.server --sse
   ```
   Server runs at `http://localhost:8000/sse`

2. **Create an HTTPS tunnel** using ngrok (or similar):
   ```bash
   ngrok http 8000
   ```
   You'll get a URL like: `https://abc123.ngrok-free.app`

3. **Add to ChatGPT**:
   - Enable Developer Mode: Settings → Connectors → Advanced → Developer mode
   - Add MCP Server URL: `https://abc123.ngrok-free.app/sse`

## Available Tools

| Tool | Description |
|------|-------------|
| `generate_natal_chart` | Create a birth chart |
| `generate_synastry_chart` | Relationship compatibility analysis |
| `generate_transit_chart` | Current or specified transits to natal |
| `generate_composite_chart` | Midpoint composite for a couple |
| `generate_planetary_return` | Solar/Lunar returns |
| `generate_event_chart` | Chart for any specific moment |
| `get_current_positions` | Current planetary positions (text only) |
| `get_aspects` | Get natal chart aspects without images |
| `get_synastry_aspects` | Get inter-chart aspects for compatibility |

### Common Parameters

All chart tools accept:
- **lat/lng**: Coordinates (positive N/E, negative S/W)
- **tz_str**: IANA timezone (e.g., "Europe/Rome", "America/New_York")
- **theme**: "classic", "light", "dark", "strawberry", "dark-high-contrast"
- **language**: "EN" (default), "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"
- **house_system**: "P" (Placidus), "W" (Whole Sign), "K" (Koch), "M" (Morinus), etc.
- **output_format**: "text", "images", or "all"
- **output_dir**: Custom directory to save chart images (optional)
- **chart_style**: "full" (default), "wheel_only", or "aspect_grid"


### Response Format

All chart tools return a compact response (~1KB) with file paths:
```json
{
  "status": "success",
  "summary": "Chart generated successfully. SVG: /path/to/file.svg, PNG: /path/to/file.png",
  "chart_type": "Natal",
  "subject_name": "Test",
  "text": "AI-readable chart analysis...",
  "svg_path": "/home/user/.kerykeion_charts/natal_test_20260106.svg",
  "png_path": "/home/user/.kerykeion_charts/natal_test_20260106.png",
  "output_dir": "/home/user/.kerykeion_charts"
}
```

> **Note**: Chart content is saved to files rather than returned inline. This keeps responses small and prevents MCP clients from showing "Tool result too large" messages. The AI assistant can read SVG files directly if needed for embedding.

## Embedding Charts in Claude Artifacts

### Method 1: Read SVG File (Recommended)

The AI assistant can read the SVG file directly from `svg_path` and embed it:

```html
<html>
<body>
<!-- SVG content read from svg_path file -->
</body>
</html>
```

Result: Interactive, scalable vector chart in artifact.

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
