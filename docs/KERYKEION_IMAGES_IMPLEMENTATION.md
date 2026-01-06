# Kerykeion-Charts MCP Tool: Direct Artifact Embedding
## Implementation Guide for Dev Team

---

## Summary

The kerykeion-charts tools currently return only file paths. This guide shows how to enable direct embedding in Claude artifacts by returning content and documenting the patterns.

**Time to implement:** ~2 hours  
**Impact:** Seamless chart embedding without manual file copying

---

## What Works (Verified)

### ✅ SVG Direct Embedding in HTML
```html
<html>
<body>
{full_svg_content}
</body>
</html>
```
Result: Interactive vector chart in artifact, scalable at any size.

### ✅ PNG Linked in Markdown with Local Paths
```markdown
![Chart](file:///C:/Users/BJJ/.kerykeion_charts/chart.png)
```
Result: When markdown file is downloaded, image renders from local Windows path.

---

## Implementation: Two Changes Required

### Change 1: Return Content in Response

Modify response to include `svg_content`:

```python
def generate_natal_chart(name, year, month, day, hour, minute, lat, lng, tz_str, ...):
    # ... existing generation code ...
    
    # Read SVG content for embedding
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()
    
    return {
        "chart_type": "Natal",
        "subject_name": name,
        "text": chart_text,
        "svg_path": str(svg_path),          # Keep for backwards compatibility
        "png_path": str(png_path),          # Keep for backwards compatibility
        "svg_content": svg_content,         # NEW: Full SVG for direct embedding
        "output_dir": str(output_dir)
    }
```

**Apply to all 7 tools:**
- `generate_natal_chart`
- `generate_synastry_chart`
- `generate_transit_chart`
- `generate_composite_chart`
- `generate_planetary_return`
- `generate_event_chart`
- `get_current_positions` (N/A - text only)

### Change 2: Update Docstrings

Add this section to each tool's docstring:

```python
"""
[existing docstring...]

EMBEDDING IN CLAUDE ARTIFACTS:

Method 1: SVG Embedded in HTML (Recommended)
  - Response includes 'svg_content' with full SVG markup
  - Create HTML artifact: <html><body>{svg_content}</body></html>
  - Chart renders interactively in artifact
  - Best for: Scalable vector graphics

Method 2: PNG with Local File Path
  - Response includes 'png_path' (e.g., "C:\\Users\\BJJ\\.kerykeion_charts\\chart.png")
  - Create markdown: ![Chart](file:///C:/Users/BJJ/.kerykeion_charts/chart.png)
  - Download markdown file - image renders from local path
  - Best for: Local document workflows

[rest of docstring...]
"""
```

---

## Example Docstring (Complete)

```python
def generate_natal_chart(name, year, month, day, hour, minute, lat, lng, tz_str, 
                        theme="classic", language="EN", house_system="P", 
                        zodiac_type="Tropical", output_format="all", output_dir=None):
    """
    Generate a natal (birth) chart for an individual.
    
    EMBEDDING IN CLAUDE ARTIFACTS:
    
    Method 1: SVG Embedded in HTML (Recommended)
      - Response includes 'svg_content' - full SVG markup
      - Create artifact code: <html><body>{response['svg_content']}</body></html>
      - Result: Interactive scalable chart in artifact
    
    Method 2: PNG with File Path
      - Response includes 'png_path' - Windows file path
      - Create markdown: ![Chart](file:///C:/Users/.../chart.png)
      - Download .md file - image renders from local path
    
    Args:
        name (str): Name of the chart subject
        year (int): Birth year (e.g., 1990)
        month (int): Birth month (1-12)
        day (int): Birth day (1-31)
        hour (int): Birth hour (0-23)
        minute (int): Birth minute (0-59)
        lat (float): Latitude (positive=North, negative=South)
        lng (float): Longitude (positive=East, negative=West)
        tz_str (str): IANA timezone (e.g., "Europe/London", "America/New_York")
        theme (str): Chart theme - "classic", "light", "dark", "strawberry", "dark-high-contrast"
        language (str): Output language - "EN", "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"
        house_system (str): House system - "P" (Placidus), "W" (Whole Sign), "K" (Koch)
        zodiac_type (str): "Tropical" (Western) or "Sidereal" (Vedic)
        output_format (str): "text", "images", or "all"
        output_dir (str): Directory to save images (optional)
    
    Returns:
        dict: Contains:
            - chart_type: "Natal"
            - subject_name: Chart subject name
            - text: Textual chart analysis
            - svg_path: File path to SVG (Windows path)
            - png_path: File path to PNG (Windows path)
            - svg_content: Full SVG markup for embedding in HTML artifacts
            - output_dir: Directory where files were saved
    """
```

---

## Code Changes Checklist

- [ ] Add `svg_content = open(svg_path).read()` to all 6 chart generation functions
- [ ] Add `svg_content` to return dict for each function
- [ ] Update docstrings for all 6 functions with embedding guide
- [ ] Keep existing `svg_path` and `png_path` returns (backward compatibility)
- [ ] Test that SVG content embeds correctly in HTML artifacts
- [ ] Test that PNG paths work in markdown with file:// URLs
- [ ] Verify all 6 tools work (skip get_current_positions - text only)

---

## Testing

### Test SVG Embedding
```python
response = generate_natal_chart("Test", 1990, 12, 15, 14, 30, 51.5, -0.1, "UTC")
svg = response['svg_content']
assert svg.startswith('<svg')
assert len(svg) > 10000  # Should be substantial
```

### Test PNG Path
```python
response = generate_natal_chart(...)
png_path = response['png_path']
assert png_path.endswith('.png')
assert 'C:\\Users' in png_path  # Windows path
```

### Test Artifact Rendering
1. Generate chart: `generate_natal_chart(...)`
2. Create HTML: `<html><body>{response['svg_content']}</body></html>`
3. Verify: Chart displays in artifact

### Test Markdown Download
1. Generate chart: `generate_natal_chart(...)`
2. Create markdown: `![Chart](file:///C:/Users/BJJ/.kerykeion_charts/chart.png)`
3. Download .md file
4. Open in markdown viewer - image renders from file path

---

## User-Facing Documentation

### Quick Start for Claude Users

**Embed Chart in Artifact:**
```
1. Generate: generate_natal_chart(name, year, month, day, hour, minute, lat, lng, tz_str)
2. Response has 'svg_content'
3. Create artifact HTML:
   <html><body>{svg_content}</body></html>
4. Chart displays ✓
```

**Create Downloadable Markdown:**
```
1. Generate: generate_natal_chart(...)
2. Response has 'png_path'
3. Create markdown:
   ![My Chart](file:///C:/Users/BJJ/.kerykeion_charts/chart.png)
4. Download .md
5. Open locally - chart renders ✓
```

---

## Benefits

✅ **No Manual Copying** - Content in response, ready to embed  
✅ **Two Options** - SVG for artifacts, PNG for local workflows  
✅ **Backward Compatible** - Old file paths still returned  
✅ **Clear Documentation** - Docstrings explain both patterns  
✅ **Minimal Overhead** - Just read file and add to response  

---

## Summary for Dev Lead

**What:** Add `svg_content` to response dict, update docstrings  
**Why:** Enable seamless chart embedding in artifacts  
**How:** Read SVG file, return as string, document in docstrings  
**Time:** ~2 hours  
**Lines of code:** ~50 (mostly boilerplate)  
**Testing:** Manual - generate chart, verify SVG renders in artifact  

This is a low-effort, high-impact improvement that eliminates manual file management for users.
