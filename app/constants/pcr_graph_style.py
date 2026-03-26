# app\constants\pcr_graph_style.py
# app/constants/pcr_graph_style.py
"""
PCR amplification curve graph styling configuration.

This module defines visual styling for PCR amplification plots, including:
- Axis styling (colors, grids, labels)
- Curve colors and line styles (FAM/HEX channels)
- Interactive overlay styles (hover, selection, ROI)
- Legend styling

Design Philosophy:
    - Medical-grade professional palette (non-neon, high contrast)
    - Retina/High-DPI display optimized line widths
    - Dark theme optimized colors (from ColorPalette)
    - Accessibility: FAM (turquoise) and HEX (amber) are distinguishable
      for color-blind users

Usage:
    from app.constants.pcr_graph_style import PCRGraphStyle, AxesStyle
    
    # Get default style configuration
    style = PCRGraphStyle()
    
    # Use in matplotlib
    ax.set_facecolor(style.axes.ax_facecolor)
    ax.plot(x, y, color=style.fam_color, **style.fam_pen.to_dict())
    
    # Use in PyQtGraph
    pen = pg.mkPen(
        color=style.fam_color,
        width=style.fam_pen.width,
        style=QtCore.Qt.SolidLine
    )

Note:
    All colors use hex format for cross-framework compatibility
    (matplotlib, PyQtGraph, Qt stylesheets).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# Use new ColorPalette API (COLOR_STYLES is deprecated)
from app.constants.app_styles import ColorPalette


# ============================================================================
# LINE STYLE CONFIGURATION
# ============================================================================

@dataclass(frozen=True, slots=True)
class PenStyle:
    """
    Line/pen drawing configuration.
    
    Encapsulates line drawing properties for matplotlib, PyQtGraph, and
    Qt painters. Provides type-safe access to pen properties.
    
    Attributes:
        width: Line width in pixels (Retina-aware: 1.0-3.0 typical)
        alpha: Opacity (0.0=transparent, 1.0=opaque)
        linestyle: Line style ("-" solid, "--" dashed, ":" dotted)
    """
    
    width: float = 1.0
    """Line width in pixels"""
    
    alpha: float = 1.0
    """Opacity (0.0 = transparent, 1.0 = opaque)"""
    
    linestyle: str = "-"
    """Line style: "-" (solid), "--" (dashed), ":" (dotted), "-." (dash-dot)"""
    
    def to_dict(self) -> dict[str, float | str]:
        """
        Convert to matplotlib kwargs dict.
        
        Returns:
            Dictionary suitable for ax.plot(**pen.to_dict())
            
        Example:
            >>> pen = PenStyle(width=2.0, alpha=0.8)
            >>> ax.plot(x, y, color="red", **pen.to_dict())
        """
        return {
            "linewidth": self.width,
            "alpha": self.alpha,
            "linestyle": self.linestyle,
        }


# ============================================================================
# AXES STYLING
# ============================================================================

@dataclass(frozen=True, slots=True)
class AxesStyle:
    """
    Axis and grid styling configuration.
    
    Defines the visual appearance of plot axes, grids, labels, and titles.
    Optimized for dark theme with subtle grid lines and high-contrast text.
    
    Attributes:
        fig_facecolor: Figure background color (outer canvas)
        ax_facecolor: Axes background color (plot area)
        grid_color: Grid line color (subtle, low contrast)
        grid_linestyle: Grid line style (solid recommended)
        grid_linewidth: Grid line width (thin for subtlety)
        tick_color: Tick mark and label color
        tick_width: Tick mark line width
        label_color: Axis label color
        title_color: Plot title color (brighter than labels)
        default_xlim: Default X-axis limits (cycles)
        default_ylim: Default Y-axis limits (fluorescence)
    """
    
    # Background colors
    fig_facecolor: str = ColorPalette.PLOT_BACKGROUND_HEX
    """Figure outer background - #0B0F14"""
    
    ax_facecolor: str = ColorPalette.PLOT_BACKGROUND_HEX
    """Axes plot area background - #0B0F14"""

    # Grid styling (subtle, non-distracting)
    grid_color: str = ColorPalette.PLOT_GRID_HEX
    """Grid line color (subtle) - #2A3441"""
    
    grid_linestyle: str = "-"
    """Grid line style (solid recommended for medical plots)"""
    
    grid_linewidth: float = 0.7
    """Grid line width (thin for subtlety)"""

    # Tick and label styling
    tick_color: str = ColorPalette.PLOT_TEXT_HEX
    """Tick marks and tick labels color - #D7DEE9"""
    
    tick_width: float = 0.8
    """Tick mark line width"""
    
    label_color: str = ColorPalette.PLOT_TEXT_HEX
    """Axis label color - #D7DEE9"""
    
    title_color: str = ColorPalette.PLOT_TITLE_HEX
    """Plot title color (brighter) - #EEF2F7"""

    # Default axis ranges
    default_xlim: tuple[int, int] = (0, 40)
    """Default X-axis limits: 0-40 PCR cycles"""
    
    default_ylim: tuple[int, int] = (0, 4500)
    """Default Y-axis limits: 0-4500 fluorescence units"""


# ============================================================================
# PCR GRAPH STYLE
# ============================================================================

@dataclass(frozen=True, slots=True)
class PCRGraphStyle:
    """
    Complete PCR amplification curve styling configuration.
    
    Provides comprehensive styling for PCR plots including channel colors,
    line widths, interactive overlays, and legend styling. Designed for
    medical-grade professional appearance with high accessibility.
    
    Color Philosophy:
        - FAM (turquoise #00F2C3): Eye's most sensitive color, stands out
        - HEX (amber #FFB03B): High contrast with FAM, warm complement
        - Accessible for color-blind users (turquoise-amber pair)
    
    Line Width Scale (Retina/High-DPI):
        - Base: 1.2px (normal curves)
        - Selected: 2.5px (emphasized selection)
        - Hover: 3.0px (maximum emphasis for interaction)
    
    Attributes:
        fam_color: FAM channel curve color (turquoise)
        hex_color: HEX channel curve color (amber)
        overlay_color: Interactive overlay color (selection, hover)
        inactive_alpha: Opacity for non-selected curves
        base_width: Normal curve line width
        selected_width: Selected curve line width
        overlay_hover_width: Hover overlay line width
        overlay_preview_width: Preview overlay line width
        overlay_roi_width: ROI (region of interest) overlay line width
        legend_frame_facecolor: Legend background color
        legend_frame_edgecolor: Legend border color
        legend_text_color: Legend text color
        axes: Axis styling configuration
        fam_pen: FAM channel pen configuration
        hex_pen: HEX channel pen configuration
    """
    
    # ========================================================================
    # CHANNEL COLORS (Professional Medical Palette)
    # ========================================================================
    
    fam_color: str = "#00F2C3"
    """
    FAM channel color (vibrant turquoise/green).
    
    Selected for maximum visibility - human eye is most sensitive to
    green-cyan wavelengths (~510nm). Stands out against dark background.
    """
    
    hex_color: str = "#FFB03B"
    """
    HEX channel color (amber/gold).
    
    High contrast with FAM (complementary warm color). Easily distinguishable
    for color-blind users (turquoise-amber is safe pair).
    """
    
    # ========================================================================
    # INTERACTION COLORS
    # ========================================================================
    
    overlay_color: str = "#FFFFFF"
    """
    Interactive overlay color (selection, hover).
    
    Pure white provides maximum contrast for selection feedback.
    """
    
    inactive_alpha: float = 0.15
    """
    Opacity for non-selected curves.
    
    Fades background curves to "ghost" appearance (15% opacity),
    emphasizing selected curves without hiding context.
    """
    
    # ========================================================================
    # LINE WIDTH STANDARDS (Retina/High-DPI Optimized)
    # ========================================================================
    
    base_width: float = 1.2
    """Normal curve line width (baseline state)"""
    
    selected_width: float = 2.5
    """Selected curve line width (emphasized, 2× base)"""
    
    overlay_hover_width: float = 3.0
    """Hover overlay line width (maximum emphasis, topmost layer)"""
    
    overlay_preview_width: float = 2.0
    """Preview overlay line width (intermediate emphasis)"""
    
    overlay_roi_width: float = 1.0
    """ROI (region of interest) overlay line width (subtle marker)"""
    
    # ========================================================================
    # LEGEND STYLING
    # ========================================================================
    
    legend_frame_facecolor: str = ColorPalette.PLOT_LEGEND_BACKGROUND_HEX
    """Legend background color (slightly elevated from plot) - #141A22"""
    
    legend_frame_edgecolor: str = ColorPalette.PLOT_GRID_HEX
    """Legend border color (subtle) - #2A3441"""
    
    legend_text_color: str = ColorPalette.PLOT_TEXT_HEX
    """Legend text color - #D7DEE9"""
    
    # ========================================================================
    # NESTED CONFIGURATIONS
    # ========================================================================
    
    axes: AxesStyle = field(default_factory=AxesStyle)
    """Axis and grid styling configuration"""
    
    # ========================================================================
    # CHANNEL PEN CONFIGURATIONS
    # ========================================================================
    
    fam_pen: PenStyle = field(
        default_factory=lambda: PenStyle(
            width=2.1,
            alpha=0.95,
            linestyle="-"
        )
    )
    """
    FAM channel pen style.
    
    Slightly thicker (2.1px) and nearly opaque (95%) for prominence
    as the primary diagnostic channel.
    """
    
    hex_pen: PenStyle = field(
        default_factory=lambda: PenStyle(
            width=2.0,
            alpha=0.7,
            linestyle="-"
        )
    )
    """
    HEX channel pen style.
    
    Slightly thinner and more transparent (70%) than FAM to differentiate
    secondary reference channel while maintaining visibility.
    """


# ============================================================================
# DEFAULT INSTANCE
# ============================================================================

# Global default style instance (immutable singleton)
DEFAULT_PCR_GRAPH_STYLE: Final[PCRGraphStyle] = PCRGraphStyle()
"""Default PCR graph style configuration (read-only)"""


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_channel_color(channel: str, style: PCRGraphStyle | None = None) -> str:
    """
    Get color for a specific channel.
    
    Args:
        channel: Channel name ("FAM", "HEX", case-insensitive)
        style: Style configuration (uses default if None)
        
    Returns:
        Hex color string for the channel
        
    Raises:
        ValueError: If channel is not recognized
        
    Example:
        >>> get_channel_color("FAM")
        '#00F2C3'
        >>> get_channel_color("hex")
        '#FFB03B'
    """
    if style is None:
        style = DEFAULT_PCR_GRAPH_STYLE
    
    channel_lower = channel.strip().lower()
    
    if channel_lower == "fam":
        return style.fam_color
    elif channel_lower == "hex":
        return style.hex_color
    else:
        raise ValueError(
            f"Unknown channel: {channel}. Expected 'FAM' or 'HEX'."
        )


def get_channel_pen(channel: str, style: PCRGraphStyle | None = None) -> PenStyle:
    """
    Get pen configuration for a specific channel.
    
    Args:
        channel: Channel name ("FAM", "HEX", case-insensitive)
        style: Style configuration (uses default if None)
        
    Returns:
        PenStyle configuration for the channel
        
    Raises:
        ValueError: If channel is not recognized
        
    Example:
        >>> pen = get_channel_pen("FAM")
        >>> pen.width
        2.1
    """
    if style is None:
        style = DEFAULT_PCR_GRAPH_STYLE
    
    channel_lower = channel.strip().lower()
    
    if channel_lower == "fam":
        return style.fam_pen
    elif channel_lower == "hex":
        return style.hex_pen
    else:
        raise ValueError(
            f"Unknown channel: {channel}. Expected 'FAM' or 'HEX'."
        )


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "PCRGraphStyle",
    "AxesStyle",
    "PenStyle",
    "DEFAULT_PCR_GRAPH_STYLE",
    "get_channel_color",
    "get_channel_pen",
]