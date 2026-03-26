# app\exceptions\__init__.py
# app/exceptions/__init__.py
"""
Exception handling infrastructure.

This module provides comprehensive exception handling for the application:
- Structured exception types with i18n support
- Global exception hooks (sys.excepthook, threading.excepthook)
- Thread-safe error dialogs
- Environment-aware behavior (dev vs production)
- Logging integration

Usage:
    # Install global exception hooks at startup
    from app.exceptions import install_global_exception_hook
    install_global_exception_hook()
    
    # Raise structured exceptions
    from app.exceptions import AppError, StartupError, LicenseError
    
    raise AppError(
        title_key="errors.data.title",
        message_key="errors.data.invalid",
        params={"filename": "data.csv"}
    )
    
    # Wrap external exceptions
    try:
        process_data()
    except ValueError as e:
        raise AppError.wrap(e, message_key="errors.data.processing_failed")

Module Structure:
    - base: Global exception hook installation
    - types: Exception class definitions (AppError, etc.)
    - handler: Exception handling logic (dialogs, logging)

Note:
    Call install_global_exception_hook() after QApplication is created
    but before main window initialization.
"""

from __future__ import annotations

# Base exception handling
from .base import (
    install_global_exception_hook,
    remove_global_exception_hook,
)

# Exception types
from .types import (
    LogLevel,
    AppError,
    StartupError,
    LicenseError,
    validate_error_keys,
)

# Handler (typically not imported directly)
from .handler import handle_exception


__all__ = [
    # Hook installation
    "install_global_exception_hook",
    "remove_global_exception_hook",
    
    # Exception types
    "LogLevel",
    "AppError",
    "StartupError",
    "LicenseError",
    
    # Utilities
    "validate_error_keys",
    "handle_exception",
]