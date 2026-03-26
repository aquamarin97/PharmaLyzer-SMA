# app\constants\asset_paths.py
# app/constants/asset_paths.py
"""
Static asset path constants.

This module provides centralized path management for application assets
(icons, images, logos, etc.). Supports both development and frozen (PyInstaller)
deployment scenarios.

Usage:
    from app.constants.asset_paths import AssetPaths
    
    # Get resolved paths
    icon_path = AssetPaths.APP_ICON_ICO
    logo_path = AssetPaths.BRAND_LOGO_SVG
    
    # Check if asset exists
    if AssetPaths.validate_asset(icon_path):
        load_icon(icon_path)
    
    # Get all asset paths for packaging validation
    all_assets = AssetPaths.get_all_paths()

Note:
    All paths are resolved relative to the application root, with automatic
    detection of PyInstaller frozen mode (_MEIPASS). Missing assets are logged
    but do not raise errors to allow graceful degradation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final


# ============================================================================
# BASE DIRECTORY RESOLUTION
# ============================================================================

def _get_base_dir() -> Path:
    """
    Resolve the application base directory.
    
    Handles both development and frozen (PyInstaller) environments:
    - Development: Uses the project root directory
    - Frozen: Uses PyInstaller's temporary extraction directory (_MEIPASS)
    
    Returns:
        Absolute path to application base directory
        
    Note:
        In frozen mode, PyInstaller extracts bundled files to sys._MEIPASS.
        See: https://pyinstaller.org/en/stable/runtime-information.html
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller frozen mode
        return Path(sys._MEIPASS)
    else:
        # Development mode: go up from this file's location
        # app/constants/asset_paths.py -> app/constants -> app -> project_root
        return Path(__file__).resolve().parent.parent.parent


# Constants
BASE_DIR: Final[Path] = _get_base_dir()
"""Application root directory (auto-detected for dev/frozen modes)"""

ASSETS_DIR_NAME: Final[str] = "assets"
"""Name of the assets directory"""

ASSETS_DIR: Final[Path] = BASE_DIR / ASSETS_DIR_NAME
"""Full path to assets directory"""


# ============================================================================
# ASSET PATH CONSTANTS
# ============================================================================

@dataclass(frozen=True, slots=True)
class AssetPaths:
    """
    Static asset path constants.
    
    All paths are resolved relative to the application root directory.
    Supports both development and PyInstaller frozen deployments.
    
    Categories:
    - Icons: Application window icons (.ico, .png)
    - Images: UI images and graphics
    - Logos: Brand logos and marketing assets (.svg, .png)
    
    Attributes:
        APP_ICON_ICO: Windows application icon (.ico format)
        APP_LOGO_PNG: Application logo in PNG format
        BRAND_LOGO_SVG: Brand logo in vector format (.svg)
    """
    
    # ========================================================================
    # ICONS (Application Window Icons)
    # ========================================================================
    
    APP_ICON_ICO: ClassVar[Path] = ASSETS_DIR / "appicon.ico"
    """Windows application icon (.ico) - Used for window title bar and taskbar"""

    # ========================================================================
    # IMAGES (UI Graphics)
    # ========================================================================
    
    APP_LOGO_PNG: ClassVar[Path] = ASSETS_DIR / "appicon.png"
    """Application logo PNG - Used for about dialog and splash screen"""

    # ========================================================================
    # LOGOS (Brand Assets)
    # ========================================================================
    
    BRAND_LOGO_SVG: ClassVar[Path] = ASSETS_DIR / "pharmalinelogo.svg"
    """Pharmaline brand logo in SVG format - Scalable vector graphic"""

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    @staticmethod
    def get_all_paths() -> dict[str, Path]:
        """
        Get all defined asset paths.
        
        Returns:
            Dictionary mapping asset names to their resolved paths
            
        Usage:
            # Validate all assets exist during packaging
            for name, path in AssetPaths.get_all_paths().items():
                if not path.exists():
                    print(f"Missing asset: {name} at {path}")
        """
        return {
            name: value
            for name, value in AssetPaths.__dict__.items()
            if isinstance(value, Path) and not name.startswith("_")
        }
    
    @staticmethod
    def validate_asset(path: Path) -> bool:
        """
        Check if an asset file exists.
        
        Args:
            path: Asset path to validate (typically from AssetPaths.*)
            
        Returns:
            True if file exists and is readable, False otherwise
            
        Example:
            >>> if AssetPaths.validate_asset(AssetPaths.APP_ICON_ICO):
            ...     window.setWindowIcon(QIcon(str(AssetPaths.APP_ICON_ICO)))
        """
        try:
            return path.exists() and path.is_file()
        except (OSError, PermissionError):
            return False
    
    @staticmethod
    def validate_all() -> dict[str, bool]:
        """
        Validate all defined assets.
        
        Returns:
            Dictionary mapping asset names to existence status
            
        Usage:
            # Check asset integrity at startup
            results = AssetPaths.validate_all()
            missing = [name for name, exists in results.items() if not exists]
            if missing:
                logger.warning(f"Missing assets: {missing}")
        """
        return {
            name: AssetPaths.validate_asset(path)
            for name, path in AssetPaths.get_all_paths().items()
        }
    
    @staticmethod
    def get_asset_or_default(path: Path, default: Path | None = None) -> Path:
        """
        Get asset path with fallback.
        
        Args:
            path: Primary asset path
            default: Fallback path if primary doesn't exist (optional)
            
        Returns:
            Primary path if exists, otherwise default (or primary if no default)
            
        Example:
            >>> icon = AssetPaths.get_asset_or_default(
            ...     AssetPaths.APP_ICON_ICO,
            ...     Path("/usr/share/icons/default.ico")
            ... )
        """
        if AssetPaths.validate_asset(path):
            return path
        if default is not None and AssetPaths.validate_asset(default):
            return default
        # Return original even if missing (caller should handle gracefully)
        return path


# ============================================================================
# BACKWARD COMPATIBILITY CLASSES
# ============================================================================

class ICON_PATHS:
    """
    Deprecated: Use AssetPaths.APP_ICON_ICO instead.
    
    Legacy class for backward compatibility. Will be removed in v2.0.
    """
    APP_ICON_ICO = AssetPaths.APP_ICON_ICO


class IMAGE_PATHS:
    """
    Deprecated: Use AssetPaths.APP_LOGO_PNG instead.
    
    Legacy class for backward compatibility. Will be removed in v2.0.
    """
    APP_LOGO_PNG = AssetPaths.APP_LOGO_PNG


class LOGO_PATHS:
    """
    Deprecated: Use AssetPaths.BRAND_LOGO_SVG instead.
    
    Legacy class for backward compatibility. Will be removed in v2.0.
    """
    BRAND_LOGO_SVG = AssetPaths.BRAND_LOGO_SVG


# ============================================================================
# MODULE-LEVEL EXPORTS
# ============================================================================

# Export base directory constants for advanced use cases
__all__ = [
    "AssetPaths",
    "BASE_DIR",
    "ASSETS_DIR",
    "ICON_PATHS",      # Deprecated
    "IMAGE_PATHS",     # Deprecated
    "LOGO_PATHS",      # Deprecated
]