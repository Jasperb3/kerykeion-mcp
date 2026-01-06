"""
Utility functions for chart generation and conversion.
"""

import base64
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import cairosvg for PNG conversion
try:
    import cairosvg
    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False
    logger.warning("cairosvg not available - PNG conversion disabled")


def resolve_css_variables(svg_string: str) -> str:
    """
    Resolve CSS custom properties (variables) in SVG for CairoSVG compatibility.
    
    CairoSVG doesn't support CSS variables, so we need to inline the values.
    Handles nested variable references (e.g., --foo: var(--bar)).
    
    Args:
        svg_string: SVG content with CSS variables
        
    Returns:
        SVG with CSS variables replaced by their actual values
    """
    # Extract CSS variable definitions (--name: value;)
    var_defs = {}
    for match in re.finditer(r'--([\w-]+):\s*([^;]+);', svg_string):
        var_defs[match.group(1)] = match.group(2).strip()
    
    if not var_defs:
        return svg_string
    
    # First, resolve nested variable references in the definitions themselves
    # Some variables reference other variables, e.g., --foo: var(--bar)
    max_iterations = 10  # Prevent infinite loops
    for _ in range(max_iterations):
        updated = False
        for var_name, var_value in var_defs.items():
            if 'var(--' in var_value:
                # Replace var(--xxx) with the actual value
                def resolve_nested(match):
                    ref_name = match.group(1)
                    return var_defs.get(ref_name, '#000000')
                new_value = re.sub(r'var\(--([\w-]+)\)', resolve_nested, var_value)
                if new_value != var_value:
                    var_defs[var_name] = new_value
                    updated = True
        if not updated:
            break
    
    # Now replace var(--name) with actual values in the SVG
    def replace_var(match):
        var_name = match.group(1)
        return var_defs.get(var_name, '#000000')  # fallback to black
    
    # Multiple passes to catch any remaining nested references
    resolved = svg_string
    for _ in range(3):
        new_resolved = re.sub(r'var\(--([\w-]+)\)', replace_var, resolved)
        if new_resolved == resolved:
            break
        resolved = new_resolved
    
    logger.debug(f"Resolved {len(var_defs)} CSS variables in SVG")
    return resolved


def svg_to_png(svg_string: str, width: int = 1600, scale: float = 2.0) -> Optional[bytes]:
    """
    Convert SVG string to PNG bytes.
    
    Args:
        svg_string: SVG content as string
        width: Output width in pixels (height auto-calculated). Default 1600px.
        scale: Scale factor for higher DPI (2.0 = 192 DPI effective). Default 2.0.
        
    Returns:
        PNG bytes if conversion successful, None otherwise
    """
    if not HAS_CAIROSVG:
        logger.warning("PNG conversion not available - cairosvg not installed")
        return None
    
    try:
        # Resolve CSS variables for CairoSVG compatibility
        svg_resolved = resolve_css_variables(svg_string)
        
        png_bytes = cairosvg.svg2png(
            bytestring=svg_resolved.encode('utf-8'),
            output_width=width,
            scale=scale,
            background_color='white'
        )
        return png_bytes
    except Exception as e:
        logger.error(f"SVG to PNG conversion failed: {e}")
        return None



def svg_to_base64(svg_string: str) -> str:
    """Encode SVG string to base64 data URI."""
    encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded}"


def png_to_base64(png_bytes: bytes) -> str:
    """Encode PNG bytes to base64 data URI."""
    encoded = base64.b64encode(png_bytes).decode('utf-8')
    return f"data:image/png;base64,{encoded}"


def save_chart_file(content: str | bytes, filename: str, output_dir: Optional[Path] = None) -> Path:
    """
    Save chart content to a file.
    
    Args:
        content: SVG string or PNG bytes
        filename: Desired filename (with extension)
        output_dir: Directory to save to (defaults to temp directory)
        
    Returns:
        Path to saved file
    """
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / "kerykeion_charts"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    
    if isinstance(content, bytes):
        filepath.write_bytes(content)
    else:
        filepath.write_text(content, encoding='utf-8')
    
    return filepath


# Default output directory for charts
def get_chart_output_dir() -> Path:
    """Get the default output directory for chart files."""
    # Use user's home directory for persistent storage
    output_dir = Path.home() / ".kerykeion_charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def generate_and_save_images(
    svg_string: str,
    chart_name: str,
    output_dir: Optional[str] = None,
    save_svg: bool = True,
    save_png: bool = True,
) -> dict:
    """
    Save chart images to files and return file paths.
    
    NOTE: svg_content is intentionally NOT included in the response to keep
    tool results small (~1KB instead of ~200KB). This prevents MCP clients
    from showing confusing "Tool result too large for context" messages.
    The AI assistant can read the SVG file directly from svg_path if needed.
    
    Args:
        svg_string: SVG content string
        chart_name: Base name for files (will be sanitized)
        output_dir: Directory to save files (optional - defaults to ~/.kerykeion_charts)
        save_svg: Whether to save SVG file
        save_png: Whether to save PNG file
        
    Returns:
        Dictionary with:
        - status: "success" indicator
        - svg_path: Path to SVG file (if saved)
        - png_path: Path to PNG file (if saved)
        - output_dir: Directory where files were saved
        - summary: Human-readable success message
    """
    import re
    from datetime import datetime
    
    # Sanitize chart name for filename
    safe_name = re.sub(r'[^\w\-]', '_', chart_name.lower())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_name}_{timestamp}"
    
    # Use provided output_dir or default
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
    else:
        out_path = get_chart_output_dir()
    
    result = {
        "status": "success",
        "output_dir": str(out_path),
    }
    
    svg_path_str = None
    png_path_str = None
    
    if save_svg:
        svg_path = out_path / f"{base_name}.svg"
        svg_path.write_text(svg_string, encoding='utf-8')
        svg_path_str = str(svg_path)
        result["svg_path"] = svg_path_str
        logger.info(f"Saved SVG to {svg_path}")
    
    if save_png and HAS_CAIROSVG:
        png_bytes = svg_to_png(svg_string)
        if png_bytes:
            png_path = out_path / f"{base_name}.png"
            png_path.write_bytes(png_bytes)
            png_path_str = str(png_path)
            result["png_path"] = png_path_str
            logger.info(f"Saved PNG to {png_path}")
    
    # Add human-readable summary
    result["summary"] = (
        f"Chart generated successfully. "
        f"SVG: {svg_path_str or 'N/A'}, PNG: {png_path_str or 'N/A'}"
    )
    
    return result



# Validation helpers
VALID_THEMES = ["classic", "light", "dark", "strawberry", "dark-high-contrast"]
VALID_LANGUAGES = ["EN", "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"]
VALID_HOUSE_SYSTEMS = {
    "P": "Placidus",
    "W": "Whole Sign", 
    "K": "Koch",
    "A": "Equal",
    "C": "Campanus",
    "R": "Regiomontanus",
    "M": "Morinus",
    "O": "Porphyry",
    "G": "Gauquelin (Sectors)",
}
VALID_ZODIAC_TYPES = ["Tropical", "Sidereal"]
VALID_SIDEREAL_MODES = [
    "FAGAN_BRADLEY", "LAHIRI", "DELUCE", "RAMAN", "USHASHASHI", 
    "KRISHNAMURTI", "DJWHAL_KHOOL", "YUKTESWAR", "JN_BHASIN", "HINDU_LAHIRI"
]
VALID_PERSPECTIVE_TYPES = ["Apparent Geocentric", "Heliocentric", "Topocentric"]
VALID_CHART_STYLES = ["full", "wheel_only", "aspect_grid"]


def validate_theme(theme: str) -> str:
    """Validate and return theme, defaulting to 'classic'."""
    if theme.lower() in VALID_THEMES:
        return theme.lower()
    logger.warning(f"Invalid theme '{theme}', using 'classic'")
    return "classic"


def validate_language(language: str) -> str:
    """Validate and return language, defaulting to 'EN'."""
    lang_upper = language.upper()
    if lang_upper in VALID_LANGUAGES:
        return lang_upper
    logger.warning(f"Invalid language '{language}', using 'EN'")
    return "EN"


def validate_house_system(house_system: str) -> str:
    """Validate and return house system identifier, defaulting to 'P' (Placidus)."""
    hs_upper = house_system.upper()
    if hs_upper in VALID_HOUSE_SYSTEMS:
        return hs_upper
    logger.warning(f"Invalid house system '{house_system}', using 'P' (Placidus)")
    return "P"


def validate_sidereal_mode(sidereal_mode: Optional[str]) -> Optional[str]:
    """Validate sidereal mode, returns None if invalid."""
    if sidereal_mode is None:
        return None
    mode_upper = sidereal_mode.upper()
    if mode_upper in VALID_SIDEREAL_MODES:
        return mode_upper
    logger.warning(f"Invalid sidereal mode '{sidereal_mode}', ignoring")
    return None


def validate_perspective_type(perspective_type: str) -> str:
    """Validate perspective type, defaulting to 'Apparent Geocentric'."""
    # Allow partial/case-insensitive matching
    pt_lower = perspective_type.lower()
    for valid in VALID_PERSPECTIVE_TYPES:
        if pt_lower == valid.lower() or pt_lower in valid.lower():
            return valid
    logger.warning(f"Invalid perspective type '{perspective_type}', using 'Apparent Geocentric'")
    return "Apparent Geocentric"


def validate_chart_style(chart_style: str) -> str:
    """Validate chart style."""
    if chart_style.lower() in VALID_CHART_STYLES:
        return chart_style.lower()
    logger.warning(f"Invalid chart style '{chart_style}', using 'full'")
    return "full"
