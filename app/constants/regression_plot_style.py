# app\constants\regression_plot_style.py
# app/constants/regression_plot_style.py
"""
Regression scatter plot styling configuration.

This module defines visual styling for regression analysis plots, including:
- Scatter point colors and sizes
- Regression line styling
- Safe band visualization
- Series-specific colors (Healthy, Carrier, Uncertain)
- Interactive selection styling

Design Philosophy:
    - High-contrast colors for clinical decision support
    - "Light bulb effect" on selection (bright highlight)
    - Color-coded series for quick interpretation
    - Dark theme optimized (from ColorPalette)

Usage:
    from app.constants.regression_plot_style import (
        RegressionPlotStyle,
        SeriesType,
        get_series_style
    )
    
    # Get default style
    style = RegressionPlotStyle()
    
    # Access series colors
    healthy_style = style.get_series(SeriesType.HEALTHY)
    brush_rgb = healthy_style.brush
    
    # Use in PyQtGraph
    scatter = pg.ScatterPlotItem(
        size=style.scatter_size,
        brush=pg.mkBrush(*healthy_style.brush)
    )

Note:
    All colors use RGB tuples (0-255) for PyQtGraph compatibility.
    For hex colors (matplotlib/CSS), use rgb_to_hex() utility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from app.constants.app_styles import ColorPalette


# ============================================================================
# TYPE ALIASES
# ============================================================================

RGB = tuple[int, int, int]
"""RGB color tuple: (red: 0-255, green: 0-255, blue: 0-255)"""

RGBA = tuple[int, int, int, int]
"""RGBA color tuple: (red: 0-255, green: 0-255, blue: 0-255, alpha: 0-255)"""


# ============================================================================
# COLOR UTILITIES
# ============================================================================

def hex_to_rgb(hex_color: str) -> RGB:
    """
    Convert hex color to RGB tuple.
    
    Args:
        hex_color: Hex color string ("#RRGGBB" or "RRGGBB")
        
    Returns:
        RGB tuple (0-255, 0-255, 0-255)
        
    Raises:
        ValueError: If hex_color is invalid format
        
    Example:
        >>> hex_to_rgb("#FF5733")
        (255, 87, 51)
        >>> hex_to_rgb("00FF00")
        (0, 255, 0)
    """
    hex_color = hex_color.lstrip("#")
    
    if len(hex_color) != 6:
        raise ValueError(
            f"Invalid hex color: {hex_color}. Expected 6 characters."
        )
    
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError as e:
        raise ValueError(
            f"Invalid hex color: {hex_color}. Must be valid hex digits."
        ) from e


def rgb_to_hex(rgb: RGB) -> str:
    """
    Convert RGB tuple to hex color string.
    
    Args:
        rgb: RGB tuple (0-255, 0-255, 0-255)
        
    Returns:
        Hex color string with leading "#"
        
    Example:
        >>> rgb_to_hex((255, 87, 51))
        '#FF5733'
    """
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def validate_rgb(rgb: RGB) -> bool:
    """
    Validate RGB tuple values are in valid range.
    
    Args:
        rgb: RGB tuple to validate
        
    Returns:
        True if all values are 0-255, False otherwise
        
    Example:
        >>> validate_rgb((255, 100, 50))
        True
        >>> validate_rgb((256, 0, 0))
        False
    """
    return all(0 <= val <= 255 for val in rgb)


# ============================================================================
# SERIES TYPE CONSTANTS
# ============================================================================

class SeriesType:
    """
    Series type identifiers for regression plots.
    
    Use these constants instead of string literals to prevent typos:
        style = plot_style.get_series(SeriesType.HEALTHY)
        # Better than: style = plot_style.get_series("Sağlıklı")
    """
    
    HEALTHY: Final[str] = "Sağlıklı"
    """Healthy/normal sample series"""
    
    CARRIER: Final[str] = "Taşıyıcı"
    """Carrier/heterozygous sample series"""
    
    UNCERTAIN: Final[str] = "Belirsiz"
    """Uncertain/ambiguous sample series"""


# ============================================================================
# SERIES STYLING
# ============================================================================

@dataclass(frozen=True, slots=True)
class SeriesStyle:
    """
    Visual styling for a data series in regression plots.
    
    Defines colors for scatter points in different states:
    - brush: Fill color (normal state)
    - pen: Border color (normal state)
    - selection_pen: Border color (selected state - "light bulb effect")
    
    Attributes:
        brush: Fill color RGB (0-255, 0-255, 0-255)
        pen: Border color RGB (normal state)
        selection_pen: Border color RGB (selected state, bright highlight)
    """
    
    brush: RGB
    """Scatter point fill color (normal state)"""
    
    pen: RGB
    """Scatter point border color (normal state)"""
    
    selection_pen: RGB
    """Scatter point border color (selected state - "light bulb" bright highlight)"""
    
    def __post_init__(self) -> None:
        """Validate RGB values are in valid range (0-255)."""
        if not validate_rgb(self.brush):
            raise ValueError(f"Invalid brush RGB: {self.brush}")
        if not validate_rgb(self.pen):
            raise ValueError(f"Invalid pen RGB: {self.pen}")
        if not validate_rgb(self.selection_pen):
            raise ValueError(f"Invalid selection_pen RGB: {self.selection_pen}")


# ============================================================================
# DEFAULT SERIES STYLES
# ============================================================================

# Healthy series: Deep blue fill, white border, ice blue selection
_HEALTHY_SERIES: Final[SeriesStyle] = SeriesStyle(
    brush=(0, 191, 255),        # Deep sky blue (DeepSkyBlue)
    pen=(255, 255, 255),        # White border (normal)
    selection_pen=(173, 216, 230)  # Light blue (LightBlue) - "light bulb" effect
)

# Carrier series: Orange fill, gold border, bright yellow selection
_CARRIER_SERIES: Final[SeriesStyle] = SeriesStyle(
    brush=(255, 165, 0),        # Orange
    pen=(255, 215, 0),          # Gold border (normal)
    selection_pen=(255, 255, 0)    # Bright yellow - "light bulb on"
)

# Uncertain series: Magenta fill, light gray border, yellow selection
_UNCERTAIN_SERIES: Final[SeriesStyle] = SeriesStyle(
    brush=(255, 0, 255),        # Magenta
    pen=(211, 211, 211),        # Light gray (normal)
    selection_pen=(255, 255, 0)    # Yellow highlight (high contrast on magenta)
)

# Default series mapping (immutable)
_DEFAULT_SERIES: Final[dict[str, SeriesStyle]] = {
    SeriesType.HEALTHY: _HEALTHY_SERIES,
    SeriesType.CARRIER: _CARRIER_SERIES,
    SeriesType.UNCERTAIN: _UNCERTAIN_SERIES,
}


# ============================================================================
# REGRESSION PLOT STYLE
# ============================================================================

@dataclass(frozen=True, slots=True)
class RegressionPlotStyle:
    """
    Complete regression scatter plot styling configuration.
    
    Provides comprehensive styling for regression analysis plots including
    scatter points, regression lines, safe bands, and interactive elements.
    
    Design Features:
        - Dark theme optimized background
        - High-contrast series colors for clinical decisions
        - "Light bulb effect" on selection (bright yellow/blue highlights)
        - Subtle safe band visualization
        - Professional medical-grade appearance
    
    Attributes:
        background_hex: Plot background color (hex string)
        widget_background_rgb: Widget background color (RGB tuple)
        grid_color_rgb: Grid line color
        grid_alpha: Grid line opacity
        axis_text_rgb: Axis label and tick text color
        reg_line_pen: Regression line color
        reg_line_width: Regression line width in pixels
        safe_band_brush_rgba: Safe band fill color with alpha
        scatter_size: Scatter point diameter in pixels
        scatter_pen_width: Scatter point border width
        series: Series-specific styling configurations
    """
    
    # ========================================================================
    # BACKGROUND COLORS
    # ========================================================================
    
    background_hex: str = ColorPalette.PLOT_BACKGROUND_HEX
    """Plot canvas background (hex) - #0B0F14"""
    
    widget_background_rgb: RGB = field(
        default_factory=lambda: hex_to_rgb(ColorPalette.PLOT_BACKGROUND_HEX)
    )
    """Widget background (RGB tuple) - matches plot background"""
    
    # ========================================================================
    # GRID STYLING
    # ========================================================================
    
    grid_color_rgb: RGB = field(
        default_factory=lambda: hex_to_rgb(ColorPalette.PLOT_GRID_HEX)
    )
    """Grid line color - subtle gray"""
    
    grid_alpha: float = 0.25
    """Grid line opacity (25% = very subtle, non-distracting)"""
    
    # ========================================================================
    # AXIS TEXT STYLING
    # ========================================================================
    
    axis_text_rgb: RGB = field(
        default_factory=lambda: hex_to_rgb(ColorPalette.PLOT_TEXT_HEX)
    )
    """Axis labels and tick text color - off-white"""
    
    # ========================================================================
    # REGRESSION LINE STYLING
    # ========================================================================
    
    reg_line_pen: RGB = (255, 60, 60)
    """
    Regression line color (bright red).
    
    High visibility red for the diagnostic threshold line.
    RGB(255, 60, 60) = #FF3C3C (slightly desaturated for eye comfort)
    """
    
    reg_line_width: int = 2
    """Regression line width in pixels (thicker for visibility)"""
    
    # ========================================================================
    # SAFE BAND STYLING
    # ========================================================================
    
    safe_band_brush_rgba: RGBA = (255, 255, 255, 40)
    """
    Safe band fill color with transparency.
    
    White with 40/255 alpha (~16% opacity) creates subtle "safe zone"
    visualization without obscuring data points.
    """
    
    # ========================================================================
    # SCATTER POINT STYLING
    # ========================================================================
    
    scatter_size: int = 8
    """Scatter point diameter in pixels (visible but not overwhelming)"""
    
    scatter_pen_width: int = 1
    """Scatter point border width in pixels (subtle outline)"""
    
    # ========================================================================
    # SERIES CONFIGURATIONS
    # ========================================================================
    
    series: dict[str, SeriesStyle] = field(default_factory=lambda: _DEFAULT_SERIES.copy())
    """
    Series-specific styling configurations.
    
    Maps series names (SeriesType constants) to their visual styles.
    Default includes: Healthy (blue), Carrier (orange), Uncertain (magenta).
    """
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_series(self, series_type: str) -> SeriesStyle:
        """
        Get styling for a specific series type.
        
        Args:
            series_type: Series identifier (use SeriesType constants)
            
        Returns:
            SeriesStyle configuration for the series
            
        Raises:
            KeyError: If series_type is not defined
            
        Example:
            >>> style = RegressionPlotStyle()
            >>> healthy = style.get_series(SeriesType.HEALTHY)
            >>> healthy.brush
            (0, 191, 255)
        """
        return self.series[series_type]
    
    def has_series(self, series_type: str) -> bool:
        """
        Check if a series type is defined.
        
        Args:
            series_type: Series identifier to check
            
        Returns:
            True if series exists, False otherwise
            
        Example:
            >>> style = RegressionPlotStyle()
            >>> style.has_series(SeriesType.HEALTHY)
            True
            >>> style.has_series("Unknown")
            False
        """
        return series_type in self.series
    
    def get_all_series_types(self) -> list[str]:
        """
        Get all defined series type names.
        
        Returns:
            List of series identifiers
            
        Example:
            >>> style = RegressionPlotStyle()
            >>> style.get_all_series_types()
            ['Sağlıklı', 'Taşıyıcı', 'Belirsiz']
        """
        return list(self.series.keys())


# ============================================================================
# DEFAULT INSTANCE
# ============================================================================

DEFAULT_REGRESSION_PLOT_STYLE: Final[RegressionPlotStyle] = RegressionPlotStyle()
"""Default regression plot style configuration (read-only singleton)"""


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_series_style(
    series_type: str,
    style: RegressionPlotStyle | None = None
) -> SeriesStyle:
    """
    Get series style with default fallback.
    
    Args:
        series_type: Series identifier (use SeriesType constants)
        style: Style configuration (uses default if None)
        
    Returns:
        SeriesStyle for the series
        
    Raises:
        KeyError: If series_type is not defined
        
    Example:
        >>> style = get_series_style(SeriesType.CARRIER)
        >>> style.brush
        (255, 165, 0)
    """
    if style is None:
        style = DEFAULT_REGRESSION_PLOT_STYLE
    return style.get_series(series_type)


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main classes
    "RegressionPlotStyle",
    "SeriesStyle",
    "SeriesType",
    
    # Type aliases
    "RGB",
    "RGBA",
    
    # Utilities
    "hex_to_rgb",
    "rgb_to_hex",
    "validate_rgb",
    "get_series_style",
    
    # Default instance
    "DEFAULT_REGRESSION_PLOT_STYLE",
]