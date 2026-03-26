# app\constants\app_styles.py
# app/constants/app_styles.py
"""
Visual styling constants for the application.

This module centralizes all visual design tokens (colors, fonts, spacing)
used throughout the UI. Provides a consistent design system and enables
future theming support.

Usage:
    from app.constants.app_styles import AppStyles, ColorPalette, FontStyles
    
    # Fonts
    title_font = FontStyles.SPLASH_APP_NAME
    message_font = FontStyles.SPLASH_MESSAGE
    
    # Colors
    brand_color = ColorPalette.BRAND_PRIMARY
    plot_bg = ColorPalette.PLOT_BACKGROUND_HEX
    
    # Apply to widget
    label.setFont(FontStyles.SPLASH_BRAND_NAME)
    label.setStyleSheet(f"color: {ColorPalette.PRIMARY_TEXT_HEX};")

Design System:
    - Fonts: Semantic naming (title, body, caption) with size scale
    - Colors: Hex strings for CSS, QColor for PyQt native usage
    - Spacing: Consistent scale (xs, sm, md, lg, xl)
    - Dark theme: Plot colors optimized for dark backgrounds

Note:
    Future versions will support dynamic theming (light/dark mode switching).
    Currently all values are constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont


# ============================================================================
# DESIGN TOKENS - Base Values
# ============================================================================

class DesignTokens:
    """
    Core design tokens (primitives).
    
    These are the foundational values. Higher-level constants (ColorPalette,
    FontStyles) reference these tokens for consistency.
    """
    
    # Font families
    FONT_FAMILY_PRIMARY: Final[str] = "Arial"
    FONT_FAMILY_MONOSPACE: Final[str] = "Consolas"
    
    # Font size scale (in points)
    FONT_SIZE_XS: Final[int] = 10
    FONT_SIZE_SM: Final[int] = 12
    FONT_SIZE_MD: Final[int] = 14
    FONT_SIZE_LG: Final[int] = 18
    FONT_SIZE_XL: Final[int] = 24
    FONT_SIZE_XXL: Final[int] = 28
    FONT_SIZE_XXXL: Final[int] = 36
    
    # Color primitives (hex)
    COLOR_BRAND_BLUE: Final[str] = "#244584"  # RGB(36, 69, 132)
    COLOR_WHITE: Final[str] = "#FFFFFF"
    COLOR_BLACK: Final[str] = "#000000"
    COLOR_LIGHT_GRAY: Final[str] = "#D3D3D3"
    
    # Dark theme colors (plot backgrounds)
    COLOR_DARK_BG: Final[str] = "#0B0F14"
    COLOR_DARK_BG_ELEVATED: Final[str] = "#141A22"
    COLOR_DARK_GRID: Final[str] = "#2A3441"
    COLOR_DARK_TEXT: Final[str] = "#D7DEE9"
    COLOR_DARK_TEXT_EMPHASIS: Final[str] = "#EEF2F7"


# ============================================================================
# FONT STYLES
# ============================================================================

@dataclass(frozen=True, slots=True)
class FontStyles:
    """
    Application font styles.
    
    Provides QFont instances for various UI elements. All fonts use the
    primary font family (Arial) with different sizes and weights.
    
    Categories:
    - Splash screen: Large display fonts for startup
    - UI elements: Standard interface fonts (future)
    - Monospace: Code/data display fonts (future)
    
    Attributes:
        SPLASH_APP_NAME: Large bold font for app name (36pt)
        SPLASH_BRAND_NAME: Medium bold font for brand (28pt)
        SPLASH_MESSAGE: Regular font for loading messages (12pt)
    """
    
    # ========================================================================
    # SPLASH SCREEN FONTS
    # ========================================================================
    
    SPLASH_APP_NAME: ClassVar[QFont] = QFont(
        DesignTokens.FONT_FAMILY_PRIMARY,
        DesignTokens.FONT_SIZE_XXXL,
        QFont.Bold
    )
    """Application name on splash screen (36pt bold)"""
    
    SPLASH_BRAND_NAME: ClassVar[QFont] = QFont(
        DesignTokens.FONT_FAMILY_PRIMARY,
        DesignTokens.FONT_SIZE_XXL,
        QFont.Bold
    )
    """Brand name on splash screen (28pt bold)"""
    
    SPLASH_MESSAGE: ClassVar[QFont] = QFont(
        DesignTokens.FONT_FAMILY_PRIMARY,
        DesignTokens.FONT_SIZE_SM
    )
    """Loading messages on splash screen (12pt regular)"""
    
    # ========================================================================
    # FUTURE: UI ELEMENT FONTS
    # ========================================================================
    # Uncomment when needed:
    #
    # BUTTON_LABEL: ClassVar[QFont] = QFont(
    #     DesignTokens.FONT_FAMILY_PRIMARY,
    #     DesignTokens.FONT_SIZE_MD,
    #     QFont.Normal
    # )
    # """Standard button label font"""
    #
    # TABLE_CELL: ClassVar[QFont] = QFont(
    #     DesignTokens.FONT_FAMILY_MONOSPACE,
    #     DesignTokens.FONT_SIZE_SM
    # )
    # """Monospace font for table data"""


# ============================================================================
# COLOR PALETTE
# ============================================================================

@dataclass(frozen=True, slots=True)
class ColorPalette:
    """
    Application color palette.
    
    Provides colors in multiple formats:
    - QColor: For PyQt native APIs (setBackground, etc.)
    - Hex strings: For stylesheets and matplotlib
    - Qt constants: For convenience (Qt.black, etc.)
    
    Color Categories:
    - Brand: Corporate identity colors
    - UI: General interface colors (text, backgrounds)
    - Plot: Chart and graph styling (dark theme)
    - Semantic: Status colors (success, warning, error) [future]
    
    Note:
        Use hex strings for stylesheets and matplotlib plots.
        Use QColor for native PyQt APIs (QPainter, setBackground, etc.).
    """
    
    # ========================================================================
    # BRAND COLORS
    # ========================================================================
    
    BRAND_PRIMARY: ClassVar[QColor] = QColor(36, 69, 132)
    """Primary brand color (Pharmaline blue)"""
    
    BRAND_PRIMARY_HEX: ClassVar[str] = DesignTokens.COLOR_BRAND_BLUE
    """Primary brand color as hex string"""
    
    # ========================================================================
    # UI COLORS (General Interface)
    # ========================================================================
    
    PRIMARY_TEXT: ClassVar[Qt.GlobalColor] = Qt.black
    """Primary text color (Qt constant for convenience)"""
    
    PRIMARY_TEXT_HEX: ClassVar[str] = DesignTokens.COLOR_BLACK
    """Primary text color as hex string"""
    
    SPLASH_BACKGROUND: ClassVar[Qt.GlobalColor] = Qt.lightGray
    """Splash screen background (Qt constant)"""
    
    SPLASH_BACKGROUND_HEX: ClassVar[str] = DesignTokens.COLOR_LIGHT_GRAY
    """Splash screen background as hex string"""
    
    # ========================================================================
    # PLOT COLORS (Dark Theme)
    # ========================================================================
    
    PLOT_BACKGROUND_HEX: ClassVar[str] = DesignTokens.COLOR_DARK_BG
    """Plot canvas background (dark) - #0B0F14"""
    
    PLOT_GRID_HEX: ClassVar[str] = DesignTokens.COLOR_DARK_GRID
    """Plot grid lines (subtle) - #2A3441"""
    
    PLOT_TEXT_HEX: ClassVar[str] = DesignTokens.COLOR_DARK_TEXT
    """Plot axis labels and ticks (off-white) - #D7DEE9"""
    
    PLOT_TITLE_HEX: ClassVar[str] = DesignTokens.COLOR_DARK_TEXT_EMPHASIS
    """Plot title text (bright off-white) - #EEF2F7"""
    
    PLOT_LEGEND_BACKGROUND_HEX: ClassVar[str] = DesignTokens.COLOR_DARK_BG_ELEVATED
    """Plot legend background (slightly elevated) - #141A22"""
    
    # ========================================================================
    # FUTURE: SEMANTIC COLORS
    # ========================================================================
    # Uncomment when status indicators are implemented:
    #
    # SUCCESS: ClassVar[QColor] = QColor(76, 175, 80)  # Green
    # SUCCESS_HEX: ClassVar[str] = "#4CAF50"
    #
    # WARNING: ClassVar[QColor] = QColor(255, 193, 7)  # Amber
    # WARNING_HEX: ClassVar[str] = "#FFC107"
    #
    # ERROR: ClassVar[QColor] = QColor(244, 67, 54)    # Red
    # ERROR_HEX: ClassVar[str] = "#F44336"
    #
    # INFO: ClassVar[QColor] = QColor(33, 150, 243)    # Blue
    # INFO_HEX: ClassVar[str] = "#2196F3"


# ============================================================================
# SPACING SCALE (Future)
# ============================================================================

class Spacing:
    """
    Consistent spacing scale for layouts.
    
    Use these constants for margins, padding, and gaps to maintain
    visual consistency across the application.
    
    Note: Currently unused. Will be applied during UI refactoring phase.
    """
    
    XS: Final[int] = 4   # Extra small spacing
    SM: Final[int] = 8   # Small spacing
    MD: Final[int] = 16  # Medium spacing (default)
    LG: Final[int] = 24  # Large spacing
    XL: Final[int] = 32  # Extra large spacing
    XXL: Final[int] = 48 # Extra extra large spacing


# ============================================================================
# CONVENIENCE AGGREGATOR
# ============================================================================

class AppStyles:
    """
    Convenience class aggregating all style components.
    
    Provides a single import point for all styling constants:
        from app.constants.app_styles import AppStyles
        
        font = AppStyles.Fonts.SPLASH_APP_NAME
        color = AppStyles.Colors.BRAND_PRIMARY_HEX
        spacing = AppStyles.Spacing.MD
    
    This is optional - you can import FontStyles, ColorPalette, etc. directly.
    """
    
    Fonts = FontStyles
    Colors = ColorPalette
    Spacing = Spacing


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

class FONT_STYLES:
    """
    Deprecated: Use FontStyles instead.
    
    Legacy class for backward compatibility. Will be removed in v2.0.
    """
    SPLASH_APP_NAME = FontStyles.SPLASH_APP_NAME
    SPLASH_BRAND_NAME = FontStyles.SPLASH_BRAND_NAME
    SPLASH_MESSAGE = FontStyles.SPLASH_MESSAGE


class COLOR_STYLES:
    """
    Deprecated: Use ColorPalette instead.
    
    Legacy class for backward compatibility. Will be removed in v2.0.
    """
    BRAND_COLOR = ColorPalette.BRAND_PRIMARY
    PRIMARY_TEXT = ColorPalette.PRIMARY_TEXT
    SPLASH_BG = ColorPalette.SPLASH_BACKGROUND
    
    PLOT_BG_HEX = ColorPalette.PLOT_BACKGROUND_HEX
    PLOT_GRID_HEX = ColorPalette.PLOT_GRID_HEX
    PLOT_TEXT_HEX = ColorPalette.PLOT_TEXT_HEX
    PLOT_TITLE_HEX = ColorPalette.PLOT_TITLE_HEX
    PLOT_LEGEND_BG_HEX = ColorPalette.PLOT_LEGEND_BACKGROUND_HEX


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Recommended (new API)
    "AppStyles",
    "FontStyles",
    "ColorPalette",
    "Spacing",
    "DesignTokens",
    
    # Deprecated (backward compatibility)
    "FONT_STYLES",
    "COLOR_STYLES",
]