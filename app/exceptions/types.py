# app\exceptions\types.py
# app/exceptions/types.py
"""
Application-specific exception types.

This module defines structured exception classes for controlled error handling:
- AppError: Base class for all application errors
- StartupError: Critical errors during application initialization
- LicenseError: License validation failures

Design Philosophy:
    - Structured exceptions with i18n support
    - Clear separation of concerns (title, message, params)
    - Logging level specification
    - Exit code for process termination
    - Exception chaining (cause) for debugging

Usage:
    from app.exceptions.types import AppError, StartupError, LicenseError
    
    # Raise a basic application error
    raise AppError(
        title_key="errors.data.title",
        message_key="errors.data.invalid",
        params={"filename": "data.csv"}
    )
    
    # Wrap external exceptions
    try:
        process_data()
    except ValueError as e:
        raise AppError.wrap(
            e,
            message_key="errors.data.processing_failed"
        )
    
    # Use specific error types
    raise StartupError(
        message_key="errors.startup.config_missing"
    )

Exception Hierarchy:
    BaseException
    └── Exception
        └── AppError
            ├── StartupError
            └── LicenseError

Note:
    All exception messages are i18n keys, not literal strings.
    Actual text is resolved at display time via app.i18n.t().
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final


# ============================================================================
# LOG LEVEL ENUMERATION
# ============================================================================

class LogLevel(str, Enum):
    """
    Logging severity levels.
    
    Maps to Python's logging module levels for consistency.
    Used to specify how AppError should be logged.
    
    Values:
        DEBUG: Detailed diagnostic information
        INFO: General informational messages
        WARNING: Warning about potential issues
        ERROR: Error that allows application to continue
        CRITICAL: Critical error requiring application shutdown
    """
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    
    def to_logging_level(self) -> int:
        """
        Convert to Python logging level constant.
        
        Returns:
            logging.DEBUG, logging.INFO, etc.
            
        Example:
            >>> LogLevel.ERROR.to_logging_level()
            40  # logging.ERROR
        """
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(self, logging.ERROR)


# ============================================================================
# BASE APPLICATION ERROR
# ============================================================================

@dataclass(slots=True)
class AppError(Exception):
    """
    Base class for all application-controlled errors.
    
    Provides structured error information with i18n support, logging
    configuration, and exit code specification.
    
    Attributes:
        title_key: i18n key for error dialog title
        message_key: i18n key for error message
        exit_code: Process exit code (0=success, >0=error)
        log_level: Logging severity level
        details: Optional technical details (shown in development)
        params: Format parameters for i18n strings
        cause: Original exception (for exception chaining)
    
    Example:
        >>> raise AppError(
        ...     title_key="errors.database.title",
        ...     message_key="errors.database.connection_failed",
        ...     params={"host": "localhost", "port": 5432},
        ...     exit_code=2,
        ...     log_level=LogLevel.ERROR
        ... )
    
    Note:
        - title_key and message_key are resolved via app.i18n.t()
        - params are passed to i18n format strings: "{host}:{port}"
        - details are only shown in development (not production)
    """
    
    title_key: str = "errors.title"
    """i18n key for error dialog title (default: "errors.title")"""
    
    message_key: str = "errors.unexpected"
    """i18n key for error message (default: "errors.unexpected")"""
    
    exit_code: int = 1
    """Process exit code (0=success, 1+=error, default: 1)"""
    
    log_level: LogLevel = LogLevel.ERROR
    """Logging severity level (default: ERROR)"""
    
    details: str | None = None
    """Optional technical details (shown in dev mode only)"""
    
    params: dict[str, Any] = field(default_factory=dict)
    """Format parameters for i18n strings (e.g., {"filename": "data.csv"})"""
    
    cause: BaseException | None = None
    """Original exception for exception chaining (optional)"""
    
    def __post_init__(self) -> None:
        """
        Initialize exception base class.
        
        Sets the exception message to message_key for debugging.
        Actual user-facing message is resolved via i18n.t().
        """
        # Store message_key as exception message for debugging
        super().__init__(self.message_key)
        
        # Validate params is a dict
        if not isinstance(self.params, dict):
            raise TypeError(f"params must be dict, got {type(self.params)}")
    
    @classmethod
    def wrap(
        cls,
        exc: BaseException,
        *,
        title_key: str | None = None,
        message_key: str | None = None,
        details: str | None = None,
        params: dict[str, Any] | None = None,
        exit_code: int | None = None,
        log_level: LogLevel | None = None,
    ) -> AppError:
        """
        Wrap an external exception into an AppError.
        
        Useful for converting standard Python exceptions (ValueError,
        OSError, etc.) into structured AppError instances with i18n
        support and consistent handling.
        
        Args:
            exc: Exception to wrap
            title_key: Optional custom title key
            message_key: Optional custom message key
            details: Optional technical details
            params: Optional format parameters
            exit_code: Optional custom exit code
            log_level: Optional custom log level
            
        Returns:
            AppError instance with original exception as cause
            
        Example:
            >>> try:
            ...     int("invalid")
            ... except ValueError as e:
            ...     raise AppError.wrap(
            ...         e,
            ...         message_key="errors.parse.invalid_number",
            ...         params={"value": "invalid"}
            ...     )
        
        Note:
            Original exception is preserved in the 'cause' field for
            debugging and logging purposes.
        """
        # Create AppError with cause
        error = cls(
            title_key=title_key or cls.title_key,
            message_key=message_key or cls.message_key,
            details=details,
            params=params or {},
            cause=exc,
        )
        
        # Override exit_code and log_level if provided
        if exit_code is not None:
            error.exit_code = exit_code
        if log_level is not None:
            error.log_level = log_level
        
        return error
    
    def with_params(self, **kwargs: Any) -> AppError:
        """
        Create a copy with additional/updated parameters.
        
        Args:
            **kwargs: Parameters to add/update
            
        Returns:
            New AppError instance with merged parameters
            
        Example:
            >>> base_error = AppError(
            ...     message_key="errors.file.not_found",
            ...     params={"filename": "data.csv"}
            ... )
            >>> detailed_error = base_error.with_params(path="/var/data/data.csv")
            >>> # params now: {"filename": "data.csv", "path": "/var/data/data.csv"}
        """
        new_params = {**self.params, **kwargs}
        return AppError(
            title_key=self.title_key,
            message_key=self.message_key,
            exit_code=self.exit_code,
            log_level=self.log_level,
            details=self.details,
            params=new_params,
            cause=self.cause,
        )


# ============================================================================
# SPECIFIC ERROR TYPES
# ============================================================================

@dataclass(slots=True)
class StartupError(AppError):
    """
    Critical error during application startup.
    
    Used when application cannot initialize properly and must exit.
    Examples: missing configuration, corrupted settings, incompatible environment.
    
    Attributes:
        title_key: Default "errors.startup.title"
        message_key: Default "errors.startup.failed"
        exit_code: Default 2 (startup failure)
        log_level: Default CRITICAL (application cannot continue)
    
    Example:
        >>> raise StartupError(
        ...     message_key="errors.startup.config_missing",
        ...     params={"config_file": "settings.ini"}
        ... )
    
    Note:
        Startup errors always cause application exit.
        Exit code 2 distinguishes from general errors (exit code 1).
    """
    
    title_key: str = "errors.startup.title"
    message_key: str = "errors.startup.failed"
    exit_code: int = 2
    log_level: LogLevel = LogLevel.CRITICAL


@dataclass(slots=True)
class LicenseError(AppError):
    """
    License validation failure.
    
    Raised when license is missing, invalid, or expired. Typically allows
    user to provide valid license without forcing application exit.
    
    Attributes:
        title_key: Default "errors.license.title"
        message_key: Default "errors.license.missing"
        exit_code: Default 3 (license failure)
        log_level: Default WARNING (recoverable, user can fix)
    
    Example:
        >>> raise LicenseError(
        ...     message_key="errors.license.expired",
        ...     params={"expiry_date": "2025-01-01"}
        ... )
    
    Note:
        Log level is WARNING (not ERROR) because license issues are
        typically recoverable by user action.
    """
    
    title_key: str = "errors.license.title"
    message_key: str = "errors.license.missing"
    exit_code: int = 3
    log_level: LogLevel = LogLevel.WARNING


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_error_keys(title_key: str, message_key: str) -> bool:
    """
    Validate that error keys exist in translation system.
    
    Args:
        title_key: Title i18n key to validate
        message_key: Message i18n key to validate
        
    Returns:
        True if both keys exist, False otherwise
        
    Example:
        >>> from app.i18n import t
        >>> validate_error_keys("errors.title", "errors.unexpected")
        True
    
    Note:
        This is a development-time check. In production, missing keys
        display the key itself as fallback.
    """
    try:
        from app.i18n import t
        # Try to resolve keys
        t(title_key)
        t(message_key)
        return True
    except Exception:
        return False


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "LogLevel",
    
    # Exceptions
    "AppError",
    "StartupError",
    "LicenseError",
    
    # Utilities
    "validate_error_keys",
]