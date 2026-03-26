# app\bootstrap\splash.py
# app/bootstrap/splash.py
"""
Splash screen creation and management.

This module provides a branded splash screen displayed during application
startup while heavy imports and initialization occur in the background.

Features:
    - Branded splash screen with logo and text
    - Progress indicator with localized messages
    - Graceful fallback if logo image missing
    - Integration with i18n system
    - PyInstaller-compatible resource loading

Usage:
    from app.bootstrap.splash import create_splash, update_splash_progress
    
    # Create and show splash screen
    splash = create_splash()
    
    # Update progress during initialization
    update_splash_progress(splash, "Loading modules...", 25)
    
    # Close when done
    splash.finish(main_window)

Design:
    - 800x300px canvas with light gray background
    - Logo on left (250x250px scaled)
    - App name and brand text on right
    - Progress message at bottom center
    - Uses application style constants for consistency

Note:
    Call create_splash() before any heavy imports to show splash ASAP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QSplashScreen, QApplication

from app.bootstrap.resources import resource_path, validate_resource
from app.constants.app_styles import FontStyles, ColorPalette
from app.constants.app_text_key import TextKey
from app.constants.asset_paths import AssetPaths
from app.i18n import t, t_list

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

@dataclass(frozen=True, slots=True)
class SplashConfig:
    """
    Splash screen layout configuration.
    
    Attributes:
        canvas_width: Splash screen width in pixels
        canvas_height: Splash screen height in pixels
        logo_size: Logo image size (width=height) in pixels
        logo_x: Logo X position (left margin)
        logo_y_offset: Logo Y offset from center
        text_x_offset: Text X offset from logo right edge
        text_y_base: Text baseline Y position
        text_spacing: Vertical spacing between text lines
    """
    
    canvas_width: int = 800
    """Splash screen canvas width (pixels)"""
    
    canvas_height: int = 300
    """Splash screen canvas height (pixels)"""
    
    logo_size: int = 250
    """Logo image size - width and height (pixels)"""
    
    logo_x: int = 60
    """Logo left margin (pixels)"""
    
    logo_y_offset: int = 0
    """Logo vertical offset from center (0 = centered)"""
    
    text_x_offset: int = -60
    """Text left margin from logo right edge (pixels)"""
    
    text_y_base: int = 120
    """Text baseline Y position from logo top (pixels)"""
    
    text_spacing: int = 60
    """Vertical spacing between text lines (pixels)"""


# Default splash configuration
DEFAULT_SPLASH_CONFIG: Final[SplashConfig] = SplashConfig()


# ============================================================================
# SPLASH SCREEN CREATION
# ============================================================================

class SplashCreationError(Exception):
    """Raised when splash screen cannot be created."""
    pass


def create_splash(
    config: SplashConfig | None = None
) -> QSplashScreen:
    """
    Create and display application splash screen.
    
    Creates a branded splash screen with logo, app name, and brand name.
    The splash is displayed immediately and stays on top during startup.
    
    Args:
        config: Optional splash layout configuration (uses defaults if None)
    
    Returns:
        QSplashScreen instance (already visible)
        
    Raises:
        SplashCreationError: If splash creation fails critically
    
    Example:
        >>> from app.bootstrap.splash import create_splash
        >>> splash = create_splash()
        >>> # Do heavy initialization...
        >>> splash.finish(main_window)
    
    Note:
        - Call before heavy imports to show splash ASAP
        - Gracefully handles missing logo (uses blank canvas)
        - Progress message shows first loading message from i18n
    """
    if config is None:
        config = DEFAULT_SPLASH_CONFIG
    
    try:
        # Create canvas
        canvas = _create_canvas(config)
        
        # Draw logo and text
        _draw_splash_content(canvas, config)
        
        # Create splash screen widget
        splash = QSplashScreen(canvas, Qt.WindowStaysOnTopHint)
        splash.setFont(FontStyles.SPLASH_MESSAGE)
        splash.show()
        
        # Show initial loading message
        _update_initial_message(splash)
        
        # Process events to ensure splash is visible
        QApplication.processEvents()
        
        logger.info("Splash screen created successfully")
        return splash
        
    except Exception as e:
        logger.error(f"Splash screen creation failed: {e}", exc_info=True)
        raise SplashCreationError(f"Cannot create splash screen: {e}") from e


def _create_canvas(config: SplashConfig) -> QPixmap:
    """
    Create splash screen canvas.
    
    Args:
        config: Splash layout configuration
    
    Returns:
        QPixmap canvas filled with background color
    """
    canvas = QPixmap(config.canvas_width, config.canvas_height)
    canvas.fill(ColorPalette.SPLASH_BACKGROUND)
    return canvas


def _draw_splash_content(canvas: QPixmap, config: SplashConfig) -> None:
    """
    Draw logo and text on splash canvas.
    
    Args:
        canvas: QPixmap canvas to draw on
        config: Splash layout configuration
    """
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    
    try:
        # Draw logo (with fallback if missing)
        _draw_logo(painter, canvas, config)
        
        # Draw text (app name and brand)
        _draw_text(painter, config)
        
    finally:
        painter.end()


def _draw_logo(
    painter: QPainter,
    canvas: QPixmap,
    config: SplashConfig
) -> None:
    """
    Draw application logo on canvas.
    
    Args:
        painter: QPainter instance
        canvas: Canvas being drawn on
        config: Splash layout configuration
    """
    try:
        # Resolve logo path
        logo_path_str = str(AssetPaths.APP_LOGO_PNG)
        
        # Validate logo exists
        if not validate_resource(logo_path_str):
            logger.warning(f"Logo not found: {logo_path_str}. Skipping logo.")
            return
        
        # Load and scale logo
        logo_resolved = resource_path(logo_path_str)
        logo = QPixmap(logo_resolved).scaled(
            config.logo_size,
            config.logo_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Calculate centered position
        x_logo = config.logo_x
        y_logo = (canvas.height() - logo.height()) // 2 + config.logo_y_offset
        
        # Draw logo
        painter.drawPixmap(x_logo, y_logo, logo)
        
        logger.debug(f"Logo drawn at ({x_logo}, {y_logo})")
        
    except Exception as e:
        logger.warning(f"Failed to draw logo: {e}. Continuing without logo.")


def _draw_text(painter: QPainter, config: SplashConfig) -> None:
    """
    Draw app name and brand name text.
    
    Args:
        painter: QPainter instance
        config: Splash layout configuration
    """
    # Get translated text
    app_name = t(TextKey.APP_NAME)
    brand_name = t(TextKey.BRAND_NAME)
    
    # Calculate text position (right of logo)
    x_text = config.logo_x + config.logo_size + config.text_x_offset
    y_text_base = config.logo_x + config.text_y_base
    
    # Draw app name (large, black)
    painter.setFont(FontStyles.SPLASH_APP_NAME)
    painter.setPen(ColorPalette.PRIMARY_TEXT)
    painter.drawText(x_text, y_text_base, app_name)
    
    # Draw brand name (medium, brand color)
    painter.setFont(FontStyles.SPLASH_BRAND_NAME)
    painter.setPen(ColorPalette.BRAND_PRIMARY)
    painter.drawText(x_text, y_text_base + config.text_spacing, brand_name)
    
    logger.debug(f"Text drawn: app='{app_name}', brand='{brand_name}'")


def _update_initial_message(splash: QSplashScreen) -> None:
    """
    Show initial loading message on splash screen.
    
    Args:
        splash: QSplashScreen instance to update
    """
    # Get loading messages from i18n
    messages = t_list(TextKey.LOADING_MESSAGES)
    
    # Fallback if no messages available
    if not messages:
        messages = [t(TextKey.LOADING)]
    
    # Show first message with 1% progress
    initial_message = f"{messages[0]} 1%"
    
    splash.showMessage(
        initial_message,
        alignment=Qt.AlignBottom | Qt.AlignHCenter,
        color=ColorPalette.PRIMARY_TEXT
    )
    
    logger.debug(f"Initial splash message: {initial_message}")


# ============================================================================
# SPLASH SCREEN UPDATES
# ============================================================================

def update_splash_progress(
    splash: QSplashScreen | None,
    message: str,
    percent: int
) -> None:
    """
    Update splash screen progress message.
    
    Args:
        splash: QSplashScreen instance (None is safe - no-op)
        message: Progress message to display
        percent: Progress percentage (0-100)
    
    Example:
        >>> splash = create_splash()
        >>> update_splash_progress(splash, "Loading modules...", 25)
        >>> update_splash_progress(splash, "Initializing UI...", 50)
    
    Note:
        - Safe to pass None (allows conditional splash usage)
        - Clamps percent to 0-100 range
        - Calls QApplication.processEvents() to update display
    """
    if splash is None:
        return
    
    # Clamp percent to valid range
    percent = max(0, min(100, percent))
    
    try:
        # Format message with percent
        full_message = f"{message}  {percent}%"
        
        # Update splash message
        splash.showMessage(
            full_message,
            alignment=Qt.AlignBottom | Qt.AlignHCenter,
            color=ColorPalette.PRIMARY_TEXT
        )
        
        # Process events to update display
        QApplication.processEvents()
        
    except Exception as e:
        logger.warning(f"Failed to update splash message: {e}")


def close_splash(
    splash: QSplashScreen | None,
    main_window: object | None = None
) -> None:
    """
    Close splash screen.
    
    Args:
        splash: QSplashScreen instance to close (None is safe - no-op)
        main_window: Optional main window to finish() with
    
    Example:
        >>> splash = create_splash()
        >>> # ... initialization ...
        >>> close_splash(splash, main_window)
    
    Note:
        - If main_window provided, calls splash.finish(main_window)
        - Otherwise calls splash.close()
        - Safe to pass None (no-op)
    """
    if splash is None:
        return
    
    try:
        if main_window is not None:
            splash.finish(main_window)
            logger.info("Splash screen finished with main window")
        else:
            splash.close()
            logger.info("Splash screen closed")
            
    except Exception as e:
        logger.warning(f"Error closing splash screen: {e}")


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

def show_splash() -> QSplashScreen:
    """
    Deprecated: Use create_splash() instead.
    
    Legacy function for backward compatibility.
    
    Returns:
        QSplashScreen instance
    """
    logger.warning(
        "show_splash() is deprecated. Use create_splash() instead."
    )
    return create_splash()


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main API
    "create_splash",
    "update_splash_progress",
    "close_splash",
    
    # Configuration
    "SplashConfig",
    "DEFAULT_SPLASH_CONFIG",
    
    # Exceptions
    "SplashCreationError",
    
    # Legacy (deprecated)
    "show_splash",
]

