# app\config\settings.py
# app/config/settings.py
"""
Application configuration and settings management.

This module provides centralized configuration for the Pharmalizer application,
including environment detection, feature flags, and logging configuration.
All settings can be overridden via environment variables for deployment flexibility.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final


# Constants for environment variable parsing
_ENV_TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "yes", "y", "on"})
_ENV_FALSE_VALUES: Final[frozenset[str]] = frozenset({"0", "false", "no", "n", "off"})

# Environment name mappings
_PRODUCTION_NAMES: Final[frozenset[str]] = frozenset({"prod", "production", "release"})
_TEST_NAMES: Final[frozenset[str]] = frozenset({"test", "testing"})

# Default values
DEFAULT_APP_NAME: Final[str] = "pharmalizer"
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_LOG_DIR: Final[str] = "logs"


class Environment(str, Enum):
    """
    Application runtime environment.
    
    Controls feature availability, logging behavior, and security settings.
    """
    
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"

    @classmethod
    def parse(cls, value: str | None) -> Environment:
        """
        Parse environment string from various formats.
        
        Args:
            value: Environment string (e.g., "prod", "production", "development")
                  Case-insensitive. None or empty defaults to DEVELOPMENT.
        
        Returns:
            Parsed Environment enum value
            
        Examples:
            >>> Environment.parse("prod")
            Environment.PRODUCTION
            >>> Environment.parse("DEVELOPMENT")
            Environment.DEVELOPMENT
            >>> Environment.parse(None)
            Environment.DEVELOPMENT
        """
        if not value:
            return cls.DEVELOPMENT
            
        normalized = value.strip().lower()
        
        if normalized in _PRODUCTION_NAMES:
            return cls.PRODUCTION
        if normalized in _TEST_NAMES:
            return cls.TEST
        return cls.DEVELOPMENT


class ConfigurationError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


def _parse_bool(value: str | None, default: bool) -> bool:
    """
    Parse boolean value from string with fallback.
    
    Args:
        value: String to parse (e.g., "true", "1", "yes")
               Case-insensitive. None returns default.
        default: Fallback value if parsing fails or value is None
        
    Returns:
        Parsed boolean value
        
    Examples:
        >>> _parse_bool("true", False)
        True
        >>> _parse_bool("0", True)
        False
        >>> _parse_bool("invalid", True)
        True
    """
    if value is None:
        return default
        
    normalized = value.strip().lower()
    
    if normalized in _ENV_TRUE_VALUES:
        return True
    if normalized in _ENV_FALSE_VALUES:
        return False
    
    return default


def _validate_log_level(level: str) -> str:
    """
    Validate and normalize log level.
    
    Args:
        level: Log level string (e.g., "INFO", "debug")
        
    Returns:
        Uppercase normalized level
        
    Raises:
        ConfigurationError: If level is invalid
    """
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    normalized = level.strip().upper()
    
    if normalized not in valid_levels:
        raise ConfigurationError(
            f"Invalid log level: {level}. Must be one of {valid_levels}"
        )
    
    return normalized


def _ensure_log_directory(path: Path) -> Path:
    """
    Ensure log directory exists and is writable.
    
    Args:
        path: Log directory path
        
    Returns:
        Resolved absolute path
        
    Raises:
        ConfigurationError: If directory cannot be created or is not writable
    """
    try:
        resolved = path.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        
        # Test write permission
        test_file = resolved / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError) as e:
            raise ConfigurationError(
                f"Log directory not writable: {resolved}"
            ) from e
            
        return resolved
        
    except OSError as e:
        raise ConfigurationError(
            f"Cannot create log directory: {path}"
        ) from e


@dataclass(frozen=True, slots=True)
class AppSettings:
    """
    Immutable application settings container.
    
    All settings can be overridden via environment variables:
    - ENVIRONMENT: Runtime environment (development/production/test)
    - WARMUP: Enable/disable startup warmup (true/false)
    - LICENSE_REQUIRED: Override license requirement (true/false)
    - LOG_LEVEL: Logging verbosity (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    - LOG_DIR: Log file directory path
    - LOG_TO_CONSOLE: Enable console logging (true/false)
    
    Attributes:
        app_name: Application identifier
        environment: Current runtime environment
        warmup_enabled: Whether to run startup warmup tasks
        license_required: Whether license validation is enforced
        log_level: Logging verbosity level
        log_dir: Directory for log files (created if missing)
        log_to_console: Whether to output logs to console
    """
    
    app_name: str = DEFAULT_APP_NAME
    environment: Environment = Environment.DEVELOPMENT

    # Feature flags
    warmup_enabled: bool = True
    license_required: bool = False

    # Logging configuration
    log_level: str = DEFAULT_LOG_LEVEL
    log_dir: Path = field(default_factory=lambda: Path(DEFAULT_LOG_DIR))
    log_to_console: bool = True

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        # Validate log level
        try:
            _validate_log_level(self.log_level)
        except ConfigurationError:
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, 'log_level', DEFAULT_LOG_LEVEL)
            
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
        
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
        
    @property
    def is_test(self) -> bool:
        """Check if running in test environment."""
        return self.environment == Environment.TEST

    @staticmethod
    def from_env() -> AppSettings:
        """
        Load settings from environment variables.
        
        Returns:
            Configured AppSettings instance
            
        Raises:
            ConfigurationError: If configuration is invalid
            
        Environment Variables:
            ENVIRONMENT: Runtime environment (default: development)
            WARMUP: Enable warmup (default: true)
            LICENSE_REQUIRED: Require license (default: true in production)
            LOG_LEVEL: Log level (default: INFO)
            LOG_DIR: Log directory (default: logs/)
            LOG_TO_CONSOLE: Console logging (default: true in dev, false in prod)
        """
        # Parse environment
        env = Environment.parse(os.getenv("ENVIRONMENT"))

        # Parse feature flags
        warmup_enabled = _parse_bool(os.getenv("WARMUP"), default=True)
        
        # License required by default in production, unless explicitly overridden
        license_env = os.getenv("LICENSE_REQUIRED")
        if license_env is not None:
            license_required = _parse_bool(license_env, default=False)
        else:
            license_required = (env == Environment.PRODUCTION)

        # Parse logging configuration
        log_level_raw = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper()
        try:
            log_level = _validate_log_level(log_level_raw)
        except ConfigurationError:
            log_level = DEFAULT_LOG_LEVEL

        log_dir_raw = os.getenv("LOG_DIR", DEFAULT_LOG_DIR)
        log_dir = Path(log_dir_raw)
        
        # Ensure log directory exists (only validate, don't raise on error here)
        try:
            log_dir = _ensure_log_directory(log_dir)
        except ConfigurationError:
            # Fall back to default if custom dir fails
            log_dir = Path(DEFAULT_LOG_DIR)
            try:
                log_dir = _ensure_log_directory(log_dir)
            except ConfigurationError:
                # Last resort: use temp directory
                log_dir = Path.home() / ".pharmalizer" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)

        # Console logging: default based on environment
        log_to_console = _parse_bool(
            os.getenv("LOG_TO_CONSOLE"),
            default=(env != Environment.PRODUCTION),
        )

        return AppSettings(
            environment=env,
            warmup_enabled=warmup_enabled,
            license_required=license_required,
            log_level=log_level,
            log_dir=log_dir,
            log_to_console=log_to_console,
        )

    @staticmethod
    def for_testing(**overrides) -> AppSettings:
        """
        Create test settings with safe defaults.
        
        Args:
            **overrides: Settings to override
            
        Returns:
            AppSettings configured for testing
            
        Example:
            >>> settings = AppSettings.for_testing(warmup_enabled=False)
            >>> settings.environment
            Environment.TEST
        """
        defaults = {
            "environment": Environment.TEST,
            "warmup_enabled": False,
            "license_required": False,
            "log_level": "DEBUG",
            "log_to_console": False,
        }
        defaults.update(overrides)
        return AppSettings(**defaults)


# Global settings instance (lazy-loaded)
_settings_instance: AppSettings | None = None


def get_settings() -> AppSettings:
    """
    Get the global settings instance.
    
    Lazily loads settings on first access. For testing, use reset_settings()
    to clear the cache.
    
    Returns:
        Global AppSettings instance
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AppSettings.from_env()
    return _settings_instance


def reset_settings() -> None:
    """
    Reset global settings instance.
    
    Useful for testing to force settings reload.
    """
    global _settings_instance
    _settings_instance = None