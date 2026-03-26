# app\common\widgets\dialogs.py
# app/common/widgets/dialogs.py
"""
Standard dialog utilities for the application.

This module provides consistent, thread-safe dialog boxes with:
- Standard icons and styling
- Detailed text support (collapsible details)
- Keyboard shortcuts (Escape, Enter)
- Thread safety checks
- Configurable buttons and defaults

Usage:
    from app.common.widgets.dialogs import Dialogs
    
    # Critical error
    Dialogs.critical(
        parent=None,
        title="Error",
        text="Operation failed",
        detailed_text="Full stack trace..."
    )
    
    # Yes/No question
    result = Dialogs.question(
        parent=main_window,
        title="Confirm",
        text="Are you sure?"
    )
    if result == QMessageBox.Yes:
        proceed()

Design Principles:
    - Consistent API across all dialog types
    - Always show detailed text when provided (for debugging)
    - Sensible defaults (OK button, No as default for questions)
    - Thread-safe (checks main thread before showing)

Note:
    All dialogs are modal (block until user responds).
    Use QMessageBox.StandardButton for button specifications.
"""

from __future__ import annotations

import logging
from typing import Final

from PyQt5.QtCore import Qt, QThread
from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QStyle,
    QWidget,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

# Standard button combinations
BUTTON_OK: Final[QMessageBox.StandardButton] = QMessageBox.Ok
"""Single OK button"""

BUTTON_OK_CANCEL: Final[QMessageBox.StandardButton] = (
    QMessageBox.Ok | QMessageBox.Cancel
)
"""OK and Cancel buttons"""

BUTTON_YES_NO: Final[QMessageBox.StandardButton] = (
    QMessageBox.Yes | QMessageBox.No
)
"""Yes and No buttons"""

BUTTON_YES_NO_CANCEL: Final[QMessageBox.StandardButton] = (
    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
)
"""Yes, No, and Cancel buttons"""


# ============================================================================
# THREAD SAFETY
# ============================================================================

def _is_main_thread() -> bool:
    """
    Check if current thread is the main Qt GUI thread.
    
    Returns:
        True if main thread, False otherwise
        
    Note:
        Qt widgets must only be created/shown from the main thread.
    """
    app = QApplication.instance()
    if app is None:
        return False
    return QThread.currentThread() == app.thread()


def _check_thread_safety(method_name: str) -> bool:
    """
    Check and log if called from non-main thread.
    
    Args:
        method_name: Name of dialog method being called
        
    Returns:
        True if safe to show dialog, False otherwise
    """
    if not _is_main_thread():
        logger.error(
            f"{method_name} called from non-main thread. "
            f"Dialogs can only be shown from the main GUI thread."
        )
        return False
    return True


# ============================================================================
# DIALOG UTILITIES
# ============================================================================

class Dialogs:
    """
    Standard dialog utilities for the application.
    
    Provides static methods for common dialog types:
    - critical(): Critical error messages (red X icon)
    - warning(): Warning messages (yellow triangle icon)
    - information(): Informational messages (blue i icon)
    - question(): Yes/No questions (blue ? icon)
    
    All dialogs are modal and thread-safe. Detailed text is shown
    in a collapsible section when provided.
    
    Example:
        >>> # Show error
        >>> Dialogs.critical(None, "Error", "Operation failed")
        
        >>> # Ask question
        >>> if Dialogs.question(None, "Confirm", "Continue?") == QMessageBox.Yes:
        ...     proceed()
    """
    
    @staticmethod
    def critical(
        parent: QWidget | None,
        title: str,
        text: str,
        detailed_text: str | None = None,
        buttons: QMessageBox.StandardButton = BUTTON_OK,
    ) -> QMessageBox.StandardButton:
        """
        Show critical error dialog.
        
        Displays a modal dialog with a critical error icon (red X).
        Used for severe errors that require user attention.
        
        Args:
            parent: Parent widget (None for no parent)
            title: Window title
            text: Main error message
            detailed_text: Optional detailed error info (collapsible)
            buttons: Button combination (default: OK only)
            
        Returns:
            Button that was clicked (QMessageBox.Ok, etc.)
            
        Thread Safety:
            Must be called from main GUI thread. Returns QMessageBox.Ok
            if called from background thread (logs error).
        
        Example:
            >>> Dialogs.critical(
            ...     parent=main_window,
            ...     title="Database Error",
            ...     text="Cannot connect to database",
            ...     detailed_text="Connection timeout after 30s\\n" + traceback
            ... )
        
        Note:
            Escape key closes dialog and returns default button.
            Enter key presses default button (OK).
        """
        if not _check_thread_safety("Dialogs.critical"):
            return QMessageBox.Ok
        
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        if detailed_text:
            msg.setDetailedText(detailed_text.strip())
        
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(QMessageBox.Ok)
        
        # Use system critical icon for consistency
        if QApplication.instance():
            icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxCritical)
            msg.setWindowIcon(icon)
        
        return msg.exec_()
    
    @staticmethod
    def warning(
        parent: QWidget | None,
        title: str,
        text: str,
        detailed_text: str | None = None,
        buttons: QMessageBox.StandardButton = BUTTON_OK,
    ) -> QMessageBox.StandardButton:
        """
        Show warning dialog.
        
        Displays a modal dialog with a warning icon (yellow triangle).
        Used for non-critical issues that user should be aware of.
        
        Args:
            parent: Parent widget (None for no parent)
            title: Window title
            text: Main warning message
            detailed_text: Optional detailed info (collapsible)
            buttons: Button combination (default: OK only)
            
        Returns:
            Button that was clicked
            
        Example:
            >>> Dialogs.warning(
            ...     parent=None,
            ...     title="File Modified",
            ...     text="File has been modified externally",
            ...     buttons=QMessageBox.Ok | QMessageBox.Cancel
            ... )
        """
        if not _check_thread_safety("Dialogs.warning"):
            return QMessageBox.Ok
        
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        if detailed_text:
            msg.setDetailedText(detailed_text.strip())
        
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(QMessageBox.Ok)
        
        return msg.exec_()
    
    @staticmethod
    def information(
        parent: QWidget | None,
        title: str,
        text: str,
        detailed_text: str | None = None,
        buttons: QMessageBox.StandardButton = BUTTON_OK,
    ) -> QMessageBox.StandardButton:
        """
        Show information dialog.
        
        Displays a modal dialog with an information icon (blue i).
        Used for general informational messages.
        
        Args:
            parent: Parent widget (None for no parent)
            title: Window title
            text: Main information message
            detailed_text: Optional detailed info (collapsible)
            buttons: Button combination (default: OK only)
            
        Returns:
            Button that was clicked
            
        Example:
            >>> Dialogs.information(
            ...     parent=None,
            ...     title="Analysis Complete",
            ...     text="Analysis finished successfully",
            ...     detailed_text="Processed 100 samples in 2.5 seconds"
            ... )
        
        Note:
            Return value changed from None to StandardButton for consistency.
        """
        if not _check_thread_safety("Dialogs.information"):
            return QMessageBox.Ok
        
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        if detailed_text:
            msg.setDetailedText(detailed_text.strip())
        
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(QMessageBox.Ok)
        
        return msg.exec_()
    
    @staticmethod
    def question(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = BUTTON_YES_NO,
        default_button: QMessageBox.StandardButton = QMessageBox.No,
    ) -> QMessageBox.StandardButton:
        """
        Show question dialog.
        
        Displays a modal dialog with a question icon (blue ?).
        Used for yes/no questions requiring user decision.
        
        Args:
            parent: Parent widget (None for no parent)
            title: Window title
            text: Question text
            buttons: Button combination (default: Yes | No)
            default_button: Default button (default: No - safer)
            
        Returns:
            Button that was clicked
            
        Example:
            >>> result = Dialogs.question(
            ...     parent=main_window,
            ...     title="Confirm Delete",
            ...     text="Are you sure you want to delete this file?",
            ...     default_button=QMessageBox.No
            ... )
            >>> if result == QMessageBox.Yes:
            ...     delete_file()
        
        Note:
            Default button is No (safer for destructive actions).
            Enter key presses default button.
            Escape key is equivalent to No/Cancel.
        """
        if not _check_thread_safety("Dialogs.question"):
            return QMessageBox.No
        
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(buttons)
        msg.setDefaultButton(default_button)
        
        return msg.exec_()
    
    @staticmethod
    def confirm_action(
        parent: QWidget | None,
        title: str,
        text: str,
        action_button_text: str = "Continue",
        cancel_button_text: str = "Cancel",
    ) -> bool:
        """
        Show action confirmation dialog.
        
        Convenience method for confirming potentially destructive actions.
        Returns boolean instead of button enum for simpler usage.
        
        Args:
            parent: Parent widget
            title: Window title
            text: Confirmation question
            action_button_text: Text for action button (default: "Continue")
            cancel_button_text: Text for cancel button (default: "Cancel")
            
        Returns:
            True if action confirmed, False if cancelled
            
        Example:
            >>> if Dialogs.confirm_action(
            ...     parent=None,
            ...     title="Confirm Export",
            ...     text="Export all data to file?",
            ...     action_button_text="Export"
            ... ):
            ...     export_data()
        """
        if not _check_thread_safety("Dialogs.confirm_action"):
            return False
        
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(title)
        msg.setText(text)
        
        # Custom buttons
        action_button = msg.addButton(action_button_text, QMessageBox.AcceptRole)
        cancel_button = msg.addButton(cancel_button_text, QMessageBox.RejectRole)
        
        msg.setDefaultButton(cancel_button)  # Safer default
        
        msg.exec_()
        
        return msg.clickedButton() == action_button


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def show_error(
    title: str,
    message: str,
    details: str | None = None,
    parent: QWidget | None = None,
) -> None:
    """
    Show error dialog (convenience function).
    
    Args:
        title: Dialog title
        message: Error message
        details: Optional detailed error info
        parent: Parent widget
        
    Example:
        >>> show_error("Error", "Operation failed", details=traceback)
    """
    Dialogs.critical(parent, title, message, detailed_text=details)


def ask_yes_no(
    title: str,
    question: str,
    parent: QWidget | None = None,
) -> bool:
    """
    Ask yes/no question (convenience function).
    
    Args:
        title: Dialog title
        question: Question text
        parent: Parent widget
        
    Returns:
        True if Yes, False if No
        
    Example:
        >>> if ask_yes_no("Confirm", "Save changes?"):
        ...     save()
    """
    result = Dialogs.question(parent, title, question)
    return result == QMessageBox.Yes


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main class
    "Dialogs",
    
    # Convenience functions
    "show_error",
    "ask_yes_no",
    
    # Button constants
    "BUTTON_OK",
    "BUTTON_OK_CANCEL",
    "BUTTON_YES_NO",
    "BUTTON_YES_NO_CANCEL",
]