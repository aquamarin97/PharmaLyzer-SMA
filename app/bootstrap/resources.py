# app\bootstrap\resources.py
# app/bootstrap/resources.py
"""
Resource path resolution for development and PyInstaller frozen builds.

This module provides utilities to resolve file paths that work in both:
- Development mode (running from source)
- Frozen mode (PyInstaller bundled executable)

PyInstaller extracts bundled files to a temporary directory (sys._MEIPASS)
at runtime. This module handles the path resolution automatically.

Usage:
    from app.bootstrap.resources import resource_path, get_base_dir
    
    # Resolve path to a bundled asset
    logo_path = resource_path("assets/appicon.png")
    
    # Load resource
    with open(resource_path("config/settings.ini")) as f:
        config = f.read()
    
    # Get base directory
    base = get_base_dir()
    assets_dir = base / "assets"

Architecture:
    - Development: Uses project root directory
    - PyInstaller: Uses sys._MEIPASS temporary extraction directory
    - Auto-detection: No manual configuration needed

See also:
    - PyInstaller Runtime Information:
      https://pyinstaller.org/en/stable/runtime-information.html
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

# Marker for PyInstaller frozen mode
_PYINSTALLER_MARKER: Final[str] = "_MEIPASS"
"""Attribute name that PyInstaller sets on sys module in frozen mode"""


# ============================================================================
# BASE DIRECTORY RESOLUTION
# ============================================================================

def _detect_runtime_mode() -> tuple[bool, str]:
    """
    Detect if running in PyInstaller frozen mode.
    
    Returns:
        Tuple of (is_frozen, mode_description)
        - is_frozen: True if running from PyInstaller bundle
        - mode_description: Human-readable mode name
    
    Example:
        >>> is_frozen, mode = _detect_runtime_mode()
        >>> print(f"Running in {mode} mode")
        'Running in development mode'
    """
    if hasattr(sys, _PYINSTALLER_MARKER):
        return (True, "frozen (PyInstaller)")
    return (False, "development")


def _get_runtime_base_dir() -> Path:
    """
    Get the runtime base directory.
    
    Resolution strategy:
    1. PyInstaller frozen: Use sys._MEIPASS (temp extraction dir)
    2. Development: Use directory containing the main script
    
    Returns:
        Absolute path to runtime base directory
        
    Note:
        In frozen mode, PyInstaller creates a temporary directory and
        extracts bundled files there. This directory is available via
        sys._MEIPASS.
    """
    # Check if running from PyInstaller bundle
    if hasattr(sys, _PYINSTALLER_MARKER):
        meipass = getattr(sys, _PYINSTALLER_MARKER)
        base_dir = Path(meipass)
        logger.debug(f"PyInstaller mode: base_dir = {base_dir}")
        return base_dir
    
    # Development mode: use script directory
    # sys.argv[0] is the path to the executed script
    if sys.argv and sys.argv[0]:
        script_path = Path(sys.argv[0]).resolve()
        base_dir = script_path.parent
        logger.debug(f"Development mode: base_dir = {base_dir}")
        return base_dir
    
    # Fallback: current working directory
    base_dir = Path.cwd()
    logger.warning(
        f"Cannot determine script directory, using cwd: {base_dir}"
    )
    return base_dir


# ============================================================================
# PUBLIC API
# ============================================================================

def get_base_dir() -> Path:
    """
    Get application base directory.
    
    Returns the root directory for resolving relative paths:
    - Development: Directory containing the main script
    - Frozen: PyInstaller temporary extraction directory
    
    Returns:
        Absolute path to base directory
        
    Example:
        >>> base = get_base_dir()
        >>> assets = base / "assets"
        >>> logo = base / "assets" / "logo.png"
    
    Note:
        This is cached on first call for performance.
    """
    return _get_runtime_base_dir()


def resource_path(relative_path: str | Path) -> str:
    """
    Resolve resource path for both development and frozen modes.
    
    Converts a relative resource path to an absolute path that works
    in both development and PyInstaller frozen environments.
    
    Args:
        relative_path: Relative path to resource (e.g., "assets/logo.png")
                      Can be string or Path object
    
    Returns:
        Absolute path to resource as string
        
    Behavior:
        - Absolute paths are returned unchanged (pass-through)
        - Relative paths are resolved against base directory
        - Works in both development and frozen (PyInstaller) modes
    
    Example:
        >>> # Relative path (recommended)
        >>> logo = resource_path("assets/logo.png")
        >>> # Development: "/project/assets/logo.png"
        >>> # Frozen: "/tmp/_MEIxxxxxx/assets/logo.png"
        
        >>> # Absolute path (pass-through)
        >>> config = resource_path("/etc/app/config.ini")
        >>> # Returns: "/etc/app/config.ini" (unchanged)
    
    Note:
        Always use forward slashes or Path objects for cross-platform
        compatibility. Avoid backslashes.
    """
    path_obj = Path(relative_path)
    
    # Pass through absolute paths unchanged
    if path_obj.is_absolute():
        return str(path_obj)
    
    # Resolve relative paths against base directory
    base_dir = get_base_dir()
    resolved = base_dir / path_obj
    
    return str(resolved)


def validate_resource(relative_path: str | Path) -> bool:
    """
    Check if a resource file exists.
    
    Args:
        relative_path: Relative path to resource
    
    Returns:
        True if resource exists and is a file, False otherwise
    
    Example:
        >>> if validate_resource("assets/logo.png"):
        ...     logo = QPixmap(resource_path("assets/logo.png"))
        ... else:
        ...     logger.warning("Logo not found, using default")
    """
    try:
        resolved = resource_path(relative_path)
        return Path(resolved).is_file()
    except (OSError, ValueError):
        return False


def validate_resource_dir(relative_path: str | Path) -> bool:
    """
    Check if a resource directory exists.
    
    Args:
        relative_path: Relative path to directory
    
    Returns:
        True if directory exists, False otherwise
    
    Example:
        >>> if validate_resource_dir("translations"):
        ...     load_translations()
        ... else:
        ...     logger.error("Translations directory not found")
    """
    try:
        resolved = resource_path(relative_path)
        return Path(resolved).is_dir()
    except (OSError, ValueError):
        return False


def get_runtime_info() -> dict[str, str | Path]:
    """
    Get diagnostic information about runtime environment.
    
    Returns:
        Dictionary with runtime information:
        - mode: "development" or "frozen (PyInstaller)"
        - base_dir: Base directory path
        - is_frozen: Whether running from PyInstaller bundle
        - python_executable: Path to Python interpreter
    
    Example:
        >>> info = get_runtime_info()
        >>> print(f"Running in {info['mode']} mode")
        >>> print(f"Base directory: {info['base_dir']}")
    
    Note:
        Useful for debugging and logging during startup.
    """
    is_frozen, mode = _detect_runtime_mode()
    
    return {
        "mode": mode,
        "is_frozen": is_frozen,
        "base_dir": get_base_dir(),
        "python_executable": Path(sys.executable),
        "argv": sys.argv,
    }


# ============================================================================
# STARTUP LOGGING
# ============================================================================

def log_runtime_info() -> None:
    """
    Log runtime environment information.
    
    Logs diagnostic information about the runtime environment at INFO level.
    Useful to call at application startup for troubleshooting.
    
    Example:
        >>> # In main.py
        >>> from app.bootstrap.resources import log_runtime_info
        >>> log_runtime_info()
        INFO: Runtime mode: development
        INFO: Base directory: /project/root
    """
    info = get_runtime_info()
    
    logger.info("=" * 60)
    logger.info("Runtime Environment")
    logger.info("=" * 60)
    logger.info(f"Mode: {info['mode']}")
    logger.info(f"Base directory: {info['base_dir']}")
    logger.info(f"Python executable: {info['python_executable']}")
    logger.info(f"Frozen: {info['is_frozen']}")
    logger.info("=" * 60)


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Path resolution
    "resource_path",
    "get_base_dir",
    
    # Validation
    "validate_resource",
    "validate_resource_dir",
    
    # Diagnostics
    "get_runtime_info",
    "log_runtime_info",
]