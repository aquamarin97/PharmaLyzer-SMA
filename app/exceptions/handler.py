# app\exceptions\handler.py
# app/exceptions/handler.py
"""
Central exception handling and user notification.

This module provides the core exception handling logic:
- Exception categorization (controlled vs unhandled)
- User-friendly error dialogs with i18n support
- Appropriate logging with severity levels
- Thread-safe UI interaction
- Production vs development behavior

Usage:
    from app.exceptions.handler import handle_exception
    from app.exceptions.types import AppError
    
    try:
        risky_operation()
    except Exception as e:
        # Handle with UI dialog + logging
        exit_code = handle_exception(e, allow_ui=True)
        sys.exit(exit_code)
    
    # Or use with global exception hook (automatic)
    install_global_exception_hook()
    # All exceptions now handled automatically

Architecture:
    - Distinguishes AppError (controlled) from unhandled exceptions
    - Shows appropriate UI dialogs (QMessageBox)
    - Logs all exceptions with proper severity
    - Respects allow_ui flag for thread safety
    - Hides sensitive info (tracebacks) in production

Thread Safety:
    - Only shows UI when allow_ui=True
    - Caller must check if in main thread
    - Safe to call from any thread (logs if UI unavailable)

Note:
    This is typically called by global exception hooks, not directly.
"""

from __future__ import annotations

import logging
import traceback
from typing import Final

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication, QMessageBox

from app.i18n import t
from .types import AppError, LogLevel

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_ERROR_TITLE: Final[str] = "errors.title"
"""Default i18n key for error dialog title"""

DEFAULT_ERROR_MESSAGE: Final[str] = "errors.unexpected"
"""Default i18n key for unexpected error message"""

DEFAULT_ERROR_WITH_TYPE: Final[str] = "errors.unexpected_with_type"
"""i18n key for unexpected error with type/message details"""


# ============================================================================
# STRING FORMATTING
# ============================================================================

def _safe_format(text: str, params: dict | None) -> str:
    """
    Safely format i18n string with parameters.
    
    Args:
        text: i18n text with {param} placeholders
        params: Format parameters dict
        
    Returns:
        Formatted string, or original text if formatting fails
        
    Example:
        >>> _safe_format("Error in {file}", {"file": "data.csv"})
        'Error in data.csv'
        >>> _safe_format("Error in {file}", None)
        'Error in {file}'
    
    Note:
        Never raises exceptions - returns unformatted text on error.
        This ensures error dialogs always show something, even if
        parameter formatting fails.
    """
    if params is None or not params:
        return text
    
    try:
        return text.format(**params)
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(
            f"Failed to format i18n string: {e}. "
            f"Text: {text!r}, Params: {params}"
        )
        return text


# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

def _is_production() -> bool:
    """
    Check if running in production environment.
    
    Returns:
        True if production, False if development/test
        
    Note:
        Uses AppSettings if available, falls back to environment variable.
        Production mode hides tracebacks and sensitive information.
    """
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        return settings.is_production
    except Exception:
        # Fallback: direct environment check
        import os
        env = (os.getenv("ENVIRONMENT") or "development").strip().lower()
        return env in {"production", "prod", "release"}


# ============================================================================
# THREAD SAFETY
# ============================================================================

def _is_main_gui_thread(app: QApplication) -> bool:
    """
    Check if current thread is the main Qt GUI thread.
    
    Args:
        app: QApplication instance
        
    Returns:
        True if current thread is main GUI thread, False otherwise
        
    Note:
        Qt widgets must only be created/shown from the main thread.
        This check prevents crashes from background thread UI access.
    """
    return QThread.currentThread() == app.thread()


# ============================================================================
# MESSAGE BOX DISPLAY
# ============================================================================

def _normalize_level(level: LogLevel | str) -> str:
    """
    Normalize log level to lowercase string.
    
    Args:
        level: LogLevel enum or string
        
    Returns:
        Lowercase level string ("error", "warning", "info")
        
    Example:
        >>> _normalize_level(LogLevel.ERROR)
        'error'
        >>> _normalize_level("WARNING")
        'warning'
    """
    # Handle LogLevel enum
    if hasattr(level, "value"):
        level = level.value
    
    return str(level).strip().lower()


def _icon_for_level(level: LogLevel | str) -> QMessageBox.Icon:
    """
    Get QMessageBox icon for log level.
    
    Args:
        level: LogLevel enum or string
        
    Returns:
        QMessageBox icon constant
        
    Mapping:
        - warning → QMessageBox.Warning (yellow triangle)
        - info → QMessageBox.Information (blue i)
        - error/critical → QMessageBox.Critical (red X)
    """
    level_str = _normalize_level(level)
    
    if level_str == "warning":
        return QMessageBox.Warning
    if level_str == "info":
        return QMessageBox.Information
    
    # Default: critical/error
    return QMessageBox.Critical


def _show_message_box(
    title: str,
    message: str,
    *,
    icon: QMessageBox.Icon,
    details: str | None = None,
    allow_ui: bool = True,
) -> None:
    """
    Show error message dialog with optional details.
    
    Args:
        title: Dialog title
        message: Main error message
        icon: Dialog icon (Critical, Warning, Information)
        details: Optional technical details (shown in collapsible section)
        allow_ui: Whether UI display is allowed
        
    Safety Checks:
        - Only shows if allow_ui=True
        - Checks QApplication exists
        - Checks application not closing down
        - Verifies current thread is main GUI thread
    
    Note:
        If details are provided, Qt automatically adds a "Show Details"
        button that expands to show the details text.
    """
    if not allow_ui:
        logger.debug("UI display disabled, skipping message box")
        return
    
    # Check QApplication exists
    app = QApplication.instance()
    if app is None:
        logger.warning("QApplication not initialized, cannot show message box")
        return
    
    # Check application not shutting down
    if app.closingDown():
        logger.debug("Application closing, skipping message box")
        return
    
    # Check in main GUI thread
    if not _is_main_gui_thread(app):
        logger.warning(
            f"Cannot show message box from thread {QThread.currentThread().objectName()}"
        )
        return
    
    # Get active window as parent (for proper modality)
    parent = app.activeWindow()
    
    # Create and configure message box
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(message)
    
    # Add details if provided (creates "Show Details" button)
    if details:
        box.setDetailedText(details)
    
    # Show modal dialog
    box.exec_()
    logger.debug(f"Message box shown: {title}")


# ============================================================================
# MAIN EXCEPTION HANDLER
# ============================================================================

def handle_exception(
    exc: BaseException,
    *,
    allow_ui: bool = True,
    show_traceback: bool = False,
) -> int:
    """
    Central exception handling entry point.
    
    Handles both controlled (AppError) and unhandled (Exception) errors:
    - Logs exception with appropriate severity
    - Shows user-friendly error dialog (if UI available)
    - Returns appropriate exit code
    
    Args:
        exc: Exception to handle
        allow_ui: Whether to show UI dialogs (False for background threads)
        show_traceback: Whether to show tracebacks in UI (dev mode only)
        
    Returns:
        Exit code:
        - 0: SystemExit with code 0 (success)
        - 1+: Error exit code (from AppError.exit_code or default 1)
    
    Behavior:
        - AppError: Uses structured error info (title_key, message_key, params)
        - Other exceptions: Shows generic error with type/message in dev mode
        - Production: Hides tracebacks and technical details
        - Development: Shows full tracebacks for debugging
    
    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     exit_code = handle_exception(e, allow_ui=True)
        ...     sys.exit(exit_code)
    
    Note:
        Typically called by global exception hooks, not directly.
        Thread-safe: can be called from any thread (UI only shown from main).
    """
    # ========================================================================
    # Handle SystemExit (normal program termination)
    # ========================================================================
    
    if isinstance(exc, SystemExit):
        code = exc.code
        exit_code = int(code) if isinstance(code, int) else 0
        logger.debug(f"SystemExit with code {exit_code}")
        return exit_code
    
    # ========================================================================
    # Environment Detection
    # ========================================================================
    
    is_prod = _is_production()
    
    # ========================================================================
    # Handle Controlled Application Errors (AppError)
    # ========================================================================
    
    if isinstance(exc, AppError):
        # Resolve i18n keys with parameters
        title = _safe_format(t(exc.title_key), exc.params)
        message = _safe_format(t(exc.message_key), exc.params)
        exit_code = int(exc.exit_code)
        
        # Convert LogLevel to Python logging level
        py_log_level = exc.log_level.to_logging_level()
        
        # Log exception with appropriate severity
        if exc.cause is not None:
            # Log with original exception traceback
            logger.log(
                py_log_level,
                f"AppError: {exc.message_key}",
                exc_info=exc.cause
            )
        else:
            # Log without traceback (controlled error)
            logger.log(
                py_log_level,
                f"AppError: {exc.message_key} (params: {exc.params})"
            )
        
        # Prepare UI details (only in development)
        details: str | None = None
        if not is_prod and show_traceback:
            # Show either custom details or full traceback
            if exc.details:
                details = exc.details
            else:
                details = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
        
        # Show error dialog
        _show_message_box(
            title,
            message,
            icon=_icon_for_level(exc.log_level),
            details=details,
            allow_ui=allow_ui,
        )
        
        return exit_code
    
    # ========================================================================
    # Handle Unhandled Exceptions
    # ========================================================================
    
    # Format full traceback for logging
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    # Log as critical (unhandled exception is always serious)
    logger.critical(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        exc_info=True
    )
    
    # Prepare user-facing message
    title = t(DEFAULT_ERROR_TITLE)
    
    if is_prod:
        # Production: Hide technical details for security
        message = t(DEFAULT_ERROR_MESSAGE)
        details = None
    else:
        # Development: Show exception type and message
        message = _safe_format(
            t(DEFAULT_ERROR_WITH_TYPE),
            {"type": type(exc).__name__, "msg": str(exc)}
        )
        details = tb if show_traceback else None
    
    # Show error dialog
    _show_message_box(
        title,
        message,
        icon=QMessageBox.Critical,
        details=details,
        allow_ui=allow_ui,
    )
    
    # Return generic error exit code
    return 1


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "handle_exception",
]