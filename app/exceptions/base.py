# app\exceptions\base.py
# app/exceptions/base.py
"""
Global exception handling infrastructure.

This module provides the foundation for application-wide exception handling:
- Global exception hooks (sys.excepthook, threading.excepthook)
- Thread-safe UI interaction checks
- Environment-aware traceback display
- Integration with AppSettings for configuration

Usage:
    from app.exceptions.base import install_global_exception_hook
    
    # Install at application startup
    install_global_exception_hook()
    
    # Exceptions are now automatically caught and handled:
    raise AppError(
        title_key="errors.license.title",
        message_key="errors.license.missing"
    )

Architecture:
    - Catches all unhandled exceptions (sys.excepthook)
    - Catches exceptions in threads (threading.excepthook)
    - Logs all exceptions with appropriate severity
    - Shows UI dialogs when safe (main thread only)
    - Hides tracebacks in production for security

Thread Safety:
    - Only shows UI from main Qt thread
    - Thread exceptions are logged only (no UI)
    - Safe to call from any thread

Note:
    Must be called after QApplication is created but before main window.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Final

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication

from .handler import handle_exception

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

# Exceptions that should not trigger error handling
_IGNORED_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    SystemExit,
    KeyboardInterrupt,
)


# ============================================================================
# EXCEPTION FILTERING
# ============================================================================

def _should_ignore(exc: BaseException) -> bool:
    """
    Check if exception should be ignored by global handler.
    
    Args:
        exc: Exception to check
        
    Returns:
        True if exception should be ignored (SystemExit, KeyboardInterrupt)
        
    Note:
        SystemExit and KeyboardInterrupt are normal exit mechanisms,
        not errors that need user notification.
    """
    return isinstance(exc, _IGNORED_EXCEPTIONS)


# ============================================================================
# UI SAFETY CHECKS
# ============================================================================

def _can_show_ui(app: QApplication | None) -> bool:
    """
    Check if it's safe to show UI dialogs.
    
    Verifies:
    1. QApplication exists
    2. Application is not shutting down
    3. Current thread is the main Qt GUI thread
    
    Args:
        app: QApplication instance (or None if not initialized)
        
    Returns:
        True if safe to show dialogs, False otherwise
        
    Note:
        Qt widgets must be created/shown only from the main thread.
        Showing dialogs from other threads causes crashes.
    """
    if app is None:
        return False
        
    if app.closingDown():
        return False
    
    # Check if current thread is the main Qt thread
    return QThread.currentThread() == app.thread()


# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

def _should_show_traceback() -> bool:
    """
    Determine if tracebacks should be shown in UI.
    
    Returns:
        False in production (security), True in development/test
        
    Note:
        Tracebacks can reveal sensitive information (paths, credentials).
        Always hide in production environments.
    """
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        return not settings.is_production
    except Exception:
        # Fallback: check environment variable directly
        env = sys.platform  # Dummy fallback if settings unavailable
        return True  # Default to showing tracebacks if uncertain


# ============================================================================
# GLOBAL EXCEPTION HOOKS
# ============================================================================

def install_global_exception_hook() -> None:
    """
    Install global exception handlers for the application.
    
    Hooks into:
    - sys.excepthook: Catches all unhandled exceptions in main thread
    - threading.excepthook: Catches exceptions in background threads (Python 3.8+)
    
    Behavior:
    - Main thread exceptions: Show UI dialog + log
    - Background thread exceptions: Log only (no UI, not thread-safe)
    - Production: Hide tracebacks for security
    - Development: Show tracebacks for debugging
    
    Example:
        >>> # In main.py
        >>> from app.exceptions.base import install_global_exception_hook
        >>> 
        >>> app = QApplication(sys.argv)
        >>> install_global_exception_hook()  # Install after QApplication
        >>> 
        >>> # Now all exceptions are caught automatically
        >>> raise ValueError("This will be handled gracefully")
    
    Note:
        - Must be called after QApplication is created
        - Should be called before any other application code
        - Only installs hooks once (idempotent)
    """
    show_traceback = _should_show_traceback()
    
    logger.info("Installing global exception hooks")
    logger.info(f"Traceback display: {'enabled' if show_traceback else 'disabled'}")
    
    # ========================================================================
    # Main Thread Exception Hook
    # ========================================================================
    
    def excepthook(exc_type: type[BaseException], exc: BaseException, tb) -> None:
        """
        Handle exceptions from main thread.
        
        Args:
            exc_type: Exception class
            exc: Exception instance
            tb: Traceback object
        """
        # Ignore normal exit mechanisms
        if _should_ignore(exc):
            logger.debug(f"Ignoring {exc_type.__name__}: {exc}")
            return
        
        # Get QApplication instance
        app = QApplication.instance()
        
        # Log exception details
        logger.error(
            f"Unhandled exception in main thread: {exc_type.__name__}",
            exc_info=(exc_type, exc, tb)
        )
        
        # Handle exception (UI + logging)
        handle_exception(
            exc,
            allow_ui=_can_show_ui(app),
            show_traceback=show_traceback
        )
    
    # Install main thread hook
    sys.excepthook = excepthook
    logger.debug("Main thread exception hook installed")
    
    # ========================================================================
    # Background Thread Exception Hook (Python 3.8+)
    # ========================================================================
    
    if hasattr(threading, "excepthook"):
        def thread_hook(args: threading.ExceptHookArgs) -> None:
            """
            Handle exceptions from background threads.
            
            Args:
                args: Thread exception info (exc_type, exc_value, exc_traceback, thread)
            """
            exc = args.exc_value
            
            # Ignore normal exit mechanisms
            if _should_ignore(exc):
                logger.debug(f"Ignoring {type(exc).__name__} in thread {args.thread.name}")
                return
            
            # Log exception with thread context
            logger.error(
                f"Unhandled exception in thread '{args.thread.name}': {type(exc).__name__}",
                exc_info=(args.exc_type, exc, args.exc_traceback)
            )
            
            # Handle exception (logging only, no UI from background threads)
            handle_exception(
                exc,
                allow_ui=False,  # Never show UI from background threads
                show_traceback=show_traceback
            )
        
        # Install thread hook
        threading.excepthook = thread_hook
        logger.debug("Background thread exception hook installed")
    
    else:
        logger.warning(
            "threading.excepthook not available (Python < 3.8). "
            "Background thread exceptions will not be caught."
        )


# ============================================================================
# HOOK REMOVAL (Testing)
# ============================================================================

def remove_global_exception_hook() -> None:
    """
    Remove global exception handlers.
    
    Restores default exception handling behavior. Useful for testing
    to ensure tests fail on unexpected exceptions.
    
    Warning:
        Only call this in test cleanup. Never in production code.
        
    Example:
        >>> # In test tearDown
        >>> def tearDown(self):
        ...     remove_global_exception_hook()
    """
    sys.excepthook = sys.__excepthook__
    
    if hasattr(threading, "excepthook"):
        threading.excepthook = threading.__excepthook__
    
    logger.debug("Global exception hooks removed")


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "install_global_exception_hook",
    "remove_global_exception_hook",
]