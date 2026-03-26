# app\licensing\manager.py
# app/licensing/manager.py
"""
License file path storage and retrieval.

Manages persistent storage of license file path in user's home directory.
Allows application to remember which license was used previously.

Storage Location:
    ~/.pharmalizer/license_path.txt

Usage:
    from app.licensing.manager import save_license_path, read_saved_license_path
    
    # Save license path
    save_license_path("/path/to/license.json")
    
    # Read saved path
    path = read_saved_license_path()
    if path:
        validate_license_file(path)
"""

from __future__ import annotations

import logging
import os
from typing import Final

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_APP_FOLDER: Final[str] = ".pharmalizer"
"""Application data folder name in user's home directory"""

LICENSE_PATH_FILE: Final[str] = "license_path.txt"
"""Filename for storing license path"""


# ============================================================================
# DIRECTORY MANAGEMENT
# ============================================================================

def get_app_data_dir(app_folder_name: str = DEFAULT_APP_FOLDER) -> str:
    """
    Get application data directory path.
    
    Creates directory if it doesn't exist.
    
    Args:
        app_folder_name: Folder name (default: ".pharmalizer")
        
    Returns:
        Absolute path to app data directory
        
    Example:
        >>> get_app_data_dir()
        'C:\\Users\\Username\\.pharmalizer'
    """
    base_dir = os.path.expanduser("~")
    app_dir = os.path.join(base_dir, app_folder_name)
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_license_storage_path() -> str:
    """
    Get path to license storage file.
    
    Returns:
        Absolute path to license_path.txt
        
    Example:
        >>> get_license_storage_path()
        'C:\\Users\\Username\\.pharmalizer\\license_path.txt'
    """
    return os.path.join(get_app_data_dir(), LICENSE_PATH_FILE)


# ============================================================================
# LICENSE PATH OPERATIONS
# ============================================================================

def read_saved_license_path() -> str | None:
    """
    Read saved license file path.
    
    Returns:
        Saved path string, or None if not found or invalid
        
    Example:
        >>> path = read_saved_license_path()
        >>> if path:
        ...     print(f"Saved license: {path}")
    """
    path_file = get_license_storage_path()
    
    if not os.path.exists(path_file):
        logger.debug("No saved license path")
        return None
    
    try:
        with open(path_file, "r", encoding="utf-8") as f:
            saved_path = f.read().strip()
        
        if not saved_path:
            logger.debug("Saved license path is empty")
            return None
        
        logger.debug(f"Read saved license path: {saved_path}")
        return saved_path
        
    except Exception as e:
        logger.error(f"Cannot read license path file: {e}")
        return None


def save_license_path(license_file_path: str) -> None:
    """
    Save license file path for future use.
    
    Args:
        license_file_path: Path to license file
        
    Raises:
        OSError: If file cannot be written
        
    Example:
        >>> save_license_path("/path/to/license.json")
    """
    if not license_file_path:
        raise ValueError("License path cannot be empty")
    
    path_file = get_license_storage_path()
    
    try:
        with open(path_file, "w", encoding="utf-8") as f:
            f.write(license_file_path)
        
        logger.info(f"Saved license path: {license_file_path}")
        
    except OSError as e:
        logger.error(f"Cannot save license path: {e}")
        raise


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "get_app_data_dir",
    "get_license_storage_path",
    "read_saved_license_path",
    "save_license_path",
]