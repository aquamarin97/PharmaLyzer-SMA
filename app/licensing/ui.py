# app\licensing\ui.py
# app/licensing/ui.py
"""
License validation user interface.

Provides UI dialogs for license validation and file selection.
Exits application if valid license cannot be obtained.

Usage:
    from app.licensing.ui import ensure_license_or_exit
    
    # Check license at startup
    ensure_license_or_exit()
    
    # Application continues only if license is valid

Flow:
    1. Check saved license path
    2. If valid: Continue
    3. If invalid: Show warning and prompt for file
    4. Validate selected file
    5. If valid: Save path and continue
    6. If invalid: Exit application
"""

from __future__ import annotations

import logging
import os
from typing import Final

from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.constants.app_text_key import TextKey
from app.i18n import t
from app.licensing.manager import read_saved_license_path, save_license_path
from app.licensing.validator import validate_license_file

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

LICENSE_FILE_FILTER: Final[str] = "License Files (*.key *.json);;All Files (*)"
"""File dialog filter for license selection"""


# ============================================================================
# LICENSE VALIDATION UI
# ============================================================================

def ensure_license_or_exit(app: QApplication | None = None) -> None:
    """
    Ensure valid license exists or exit application.
    
    Validates saved license or prompts user to select one.
    Exits application (SystemExit) if valid license cannot be obtained.
    
    Args:
        app: QApplication instance (auto-detected if None)
        
    Raises:
        SystemExit: If no valid license provided
        
    Example:
        >>> app = QApplication(sys.argv)
        >>> ensure_license_or_exit(app)
        >>> # Only continues if license is valid
    """
    if app is None:
        app = QApplication.instance()
    
    parent = app.activeWindow() if app is not None else None
    
    # ========================================================================
    # Step 1: Check saved license
    # ========================================================================
    
    saved_path = read_saved_license_path()
    
    if saved_path and os.path.exists(saved_path) and validate_license_file(saved_path):
        # Saved license is valid
        logger.info("Using valid saved license")
        return
    
    # ========================================================================
    # Step 2: Saved license invalid - show warning
    # ========================================================================
    
    if saved_path:
        logger.warning("Saved license is invalid")
        QMessageBox.warning(
            parent,
            t(TextKey.TITLE_LICENSE_ERROR),
            t("errors.license.invalid_saved"),
        )
    
    # ========================================================================
    # Step 3: Prompt user to select license file
    # ========================================================================
    
    # Get localized filter text
    filter_text = t("filters.license_files")
    if filter_text == "filters.license_files":
        # Fallback if translation missing
        filter_text = LICENSE_FILE_FILTER
    
    license_file, _ = QFileDialog.getOpenFileName(
        parent,
        caption=t(TextKey.TITLE_SELECT_FILE),
        directory="",
        filter=filter_text,
    )
    
    if not license_file:
        # User cancelled
        logger.warning("License selection cancelled")
        QMessageBox.critical(
            parent,
            t(TextKey.TITLE_LICENSE_ERROR),
            t("errors.license.missing"),
        )
        raise SystemExit(1)
    
    # ========================================================================
    # Step 4: Validate selected file
    # ========================================================================
    
    if not validate_license_file(license_file):
        logger.error(f"Selected license is invalid: {license_file}")
        QMessageBox.critical(
            parent,
            t(TextKey.TITLE_LICENSE_ERROR),
            t("errors.license.invalid_selected"),
        )
        raise SystemExit(1)
    
    # ========================================================================
    # Step 5: Save valid license path
    # ========================================================================
    
    try:
        save_license_path(license_file)
        logger.info(f"License validated and saved: {license_file}")
        return
        
    except Exception as e:
        logger.error(f"Failed to save license path: {e}")
        QMessageBox.critical(
            parent,
            t(TextKey.TITLE_ERROR),
            f"{t('errors.license.save_failed')}\n\n{str(e)}",
        )
        raise SystemExit(1)


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "ensure_license_or_exit",
]