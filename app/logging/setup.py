# app\logging\setup.py
# app/logging/setup.py
"""
Centralized logging configuration and setup.

This module provides idempotent logging initialization with support for:
- File logging with automatic rotation
- Console logging (optional)
- Configurable log levels
- Integration with AppSettings
- Test-friendly reset utilities

Usage:
    from app.logging.setup import setup_logging, LoggingConfig
    
    # Simple setup with defaults
    config = LoggingConfig(app_name="pharmalizer")
    setup_logging(config)
    
    # Custom configuration
    config = LoggingConfig(
        app_name="pharmalizer",
        level=logging.DEBUG,
        log_dir=Path("/var/log/pharmalizer"),
        to_console=True
    )
    setup_logging(config)
    
    # Use from AppSettings
    from app.config.settings import get_settings
    from app.logging.setup import setup_logging_from_settings
    
    settings = get_settings()
    setup_logging_from_settings(settings)

Safety:
    - Idempotent: Safe to call multiple times (no duplicate handlers)
    - Thread-safe: Uses root logger configuration
    - Error handling: Gracefully handles directory creation failures

Note:
    Call setup_logging() once at application startup, before any logging.
    For tests, use reset_logging_for_tests() to clear handlers.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final


# ============================================================================
# CONSTANTS
# ============================================================================

# Flag to track if logging has been configured (prevents duplicate setup)
_CONFIGURED_FLAG: Final[str] = "_pharmalizer_logging_configured_v2"

# Default values
DEFAULT_APP_NAME: Final[str] = "pharmalizer"
DEFAULT_LOG_LEVEL: Final[int] = logging.INFO
DEFAULT_LOG_DIR: Final[Path] = Path("logs")
DEFAULT_MAX_BYTES: Final[int] = 2_000_000  # 2 MB per log file
DEFAULT_BACKUP_COUNT: Final[int] = 5  # Keep 5 rotated log files

# Log format template
LOG_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """
    Logging configuration parameters.
    
    Defines all settings for logging setup including file rotation,
    console output, and log levels.
    
    Attributes:
        app_name: Application name (used for log filename)
        level: Logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (created if missing)
        to_console: Whether to output logs to console/stdout
        max_bytes: Maximum size per log file before rotation (bytes)
        backup_count: Number of rotated log files to keep
    
    Example:
        >>> config = LoggingConfig(
        ...     app_name="pharmalizer",
        ...     level=logging.DEBUG,
        ...     log_dir=Path("/var/log/pharmalizer"),
        ...     to_console=True,
        ...     max_bytes=5_000_000,  # 5 MB
        ...     backup_count=10
        ... )
    """
    
    app_name: str = DEFAULT_APP_NAME
    """Application name (used for log filename: {app_name}.log)"""
    
    level: int = DEFAULT_LOG_LEVEL
    """Logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)"""
    
    log_dir: Path = DEFAULT_LOG_DIR
    """Directory for log files (created automatically if missing)"""
    
    to_console: bool = True
    """Whether to output logs to console (stdout)"""
    
    max_bytes: int = DEFAULT_MAX_BYTES
    """
    Maximum bytes per log file before rotation (default: 2 MB).
    When exceeded, current log is renamed to .log.1 and new file starts.
    """
    
    backup_count: int = DEFAULT_BACKUP_COUNT
    """
    Number of rotated backup files to keep (default: 5).
    Older backups are automatically deleted.
    """
    
    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        # Validate log level
        valid_levels = {
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        }
        if self.level not in valid_levels:
            raise ValueError(
                f"Invalid log level: {self.level}. "
                f"Must be one of: {sorted(valid_levels)}"
            )
        
        # Validate rotation parameters
        if self.max_bytes <= 0:
            raise ValueError(f"max_bytes must be positive, got: {self.max_bytes}")
        
        if self.backup_count < 0:
            raise ValueError(
                f"backup_count must be non-negative, got: {self.backup_count}"
            )


# ============================================================================
# LOGGING SETUP
# ============================================================================

class LoggingSetupError(Exception):
    """Raised when logging setup fails."""
    pass


def setup_logging(config: LoggingConfig) -> None:
    """
    Initialize application logging (idempotent).
    
    Sets up file and console handlers with rotation. Safe to call multiple
    times - subsequent calls are no-ops if logging already configured.
    
    Args:
        config: Logging configuration parameters
        
    Raises:
        LoggingSetupError: If logging setup fails (e.g., cannot create log dir)
        
    Example:
        >>> config = LoggingConfig(app_name="pharmalizer", level=logging.INFO)
        >>> setup_logging(config)
        >>> logging.info("Logging is now configured!")
        
    Note:
        Should be called once at application startup, before any logging occurs.
        Uses root logger, so all loggers inherit this configuration.
    """
    root = logging.getLogger()
    
    # Check if already configured (idempotent)
    if getattr(root, _CONFIGURED_FLAG, False):
        return
    
    # Mark as configured before setup (prevent recursion)
    setattr(root, _CONFIGURED_FLAG, True)
    
    try:
        # Set root logger level
        root.setLevel(config.level)
        
        # Create formatter
        formatter = logging.Formatter(LOG_FORMAT)
        
        # Setup file handler with rotation
        _setup_file_handler(root, config, formatter)
        
        # Setup console handler (optional)
        if config.to_console:
            _setup_console_handler(root, config, formatter)
            
    except Exception as e:
        # Unmark if setup failed
        if hasattr(root, _CONFIGURED_FLAG):
            delattr(root, _CONFIGURED_FLAG)
        raise LoggingSetupError(f"Failed to setup logging: {e}") from e


def _setup_file_handler(
    root_logger: logging.Logger,
    config: LoggingConfig,
    formatter: logging.Formatter,
) -> None:
    """
    Setup rotating file handler.
    
    Args:
        root_logger: Root logger instance
        config: Logging configuration
        formatter: Log message formatter
        
    Raises:
        LoggingSetupError: If log directory cannot be created or is not writable
    """
    try:
        # Create log directory if missing
        config.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Verify directory is writable
        if not config.log_dir.is_dir():
            raise LoggingSetupError(
                f"Log directory is not a directory: {config.log_dir}"
            )
        
        # Test write permission
        test_file = config.log_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError) as e:
            raise LoggingSetupError(
                f"Log directory not writable: {config.log_dir}"
            ) from e
        
        # Create log file path
        log_file = config.log_dir / f"{config.app_name}.log"
        
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(config.level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
    except OSError as e:
        raise LoggingSetupError(
            f"Cannot create log directory: {config.log_dir}"
        ) from e


def _setup_console_handler(
    root_logger: logging.Logger,
    config: LoggingConfig,
    formatter: logging.Formatter,
) -> None:
    """
    Setup console (stdout) handler.
    
    Args:
        root_logger: Root logger instance
        config: Logging configuration
        formatter: Log message formatter
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# ============================================================================
# INTEGRATION WITH APPSETTINGS
# ============================================================================

def setup_logging_from_settings(settings) -> None:
    """
    Setup logging from AppSettings instance.
    
    Convenience function that extracts logging configuration from
    AppSettings and calls setup_logging().
    
    Args:
        settings: AppSettings instance (from app.config.settings)
        
    Raises:
        LoggingSetupError: If logging setup fails
        
    Example:
        >>> from app.config.settings import get_settings
        >>> from app.logging.setup import setup_logging_from_settings
        >>> 
        >>> settings = get_settings()
        >>> setup_logging_from_settings(settings)
        >>> logging.info("Logging configured from settings!")
    
    Note:
        This is the recommended way to setup logging in the application.
        It ensures consistency with environment configuration.
    """
    # Convert log level string to logging constant
    level_str = settings.log_level.upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    level = level_map.get(level_str, logging.INFO)
    
    config = LoggingConfig(
        app_name=settings.app_name,
        level=level,
        log_dir=settings.log_dir,
        to_console=settings.log_to_console,
    )
    
    setup_logging(config)


# ============================================================================
# TEST UTILITIES
# ============================================================================

def reset_logging_for_tests() -> None:
    """
    Reset logging configuration (for testing only).
    
    Removes all handlers from the root logger and clears the configuration
    flag. This allows tests to reconfigure logging with different settings.
    
    Warning:
        DO NOT call this in production code. It will break logging for
        the entire application. Only use in test tearDown/cleanup.
        
    Example:
        >>> # In test tearDown
        >>> def tearDown(self):
        ...     reset_logging_for_tests()
        ...     # Now can setup_logging() again with different config
    """
    root = logging.getLogger()
    
    # Remove all handlers
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            # Ignore errors during cleanup
            pass
    
    # Clear configuration flag
    if hasattr(root, _CONFIGURED_FLAG):
        delattr(root, _CONFIGURED_FLAG)
    
    # Reset log level to default
    root.setLevel(logging.WARNING)


def is_logging_configured() -> bool:
    """
    Check if logging has been configured.
    
    Returns:
        True if setup_logging() has been called, False otherwise
        
    Example:
        >>> is_logging_configured()
        False
        >>> setup_logging(LoggingConfig(app_name="test"))
        >>> is_logging_configured()
        True
    """
    root = logging.getLogger()
    return getattr(root, _CONFIGURED_FLAG, False)


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "LoggingConfig",
    "setup_logging",
    "setup_logging_from_settings",
    "reset_logging_for_tests",
    "is_logging_configured",
    "LoggingSetupError",
]