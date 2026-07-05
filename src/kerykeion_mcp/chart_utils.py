"""
Utility functions for chart generation and conversion.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .validation import ChartInputError

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



# Default output directory for charts
def get_chart_output_dir() -> Path:
    """Get the default output directory for chart files."""
    # Use user's home directory for persistent storage
    output_dir = Path.home() / ".kerykeion_charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _allowed_output_bases() -> list[Path]:
    bases = [(Path.home() / ".kerykeion_charts").resolve()]
    env_base = os.environ.get("KERYKEION_OUTPUT_BASE")
    if env_base:
        bases.append(Path(env_base).resolve())
    return bases


def resolve_output_dir(output_dir: Optional[str]) -> Path:
    """
    Resolve and confine the requested output directory to an allowed base.

    Without this, a client could ask for a chart to be written to any
    directory it can reach (output_dir was previously passed straight to
    Path(...).mkdir with no bounds check). Allowed bases: ~/.kerykeion_charts
    and, if set, the KERYKEION_OUTPUT_BASE environment variable.
    """
    if not output_dir:
        return get_chart_output_dir()

    requested = Path(output_dir).resolve()
    bases = _allowed_output_bases()
    if not any(requested == base or base in requested.parents for base in bases):
        allowed = ", ".join(str(b) for b in bases)
        raise ChartInputError(
            f"output_dir '{output_dir}' is outside the allowed base directories.",
            hint=(
                f"Use a path under one of: {allowed}. "
                "Set KERYKEION_OUTPUT_BASE to allow a different base directory."
            ),
        )
    requested.mkdir(parents=True, exist_ok=True)
    return requested


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
    # Sanitize chart name for filename
    safe_name = re.sub(r'[^\w\-]', '_', chart_name.lower())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_name}_{timestamp}"

    out_path = resolve_output_dir(output_dir)

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
