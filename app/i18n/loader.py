# app\i18n\loader.py
# app/i18n/loader.py
"""
Translation loader and manager.

This module provides the core Translator class that handles:
- Loading translation files from JSON
- Resolving translation keys with dot notation
- Fallback to default language
- Parameter substitution in translations
- Thread-safe access to translations

Implementation:
    - Singleton pattern (class-level state)
    - Lazy loading (load on first access)
    - Idempotent loading (safe to call multiple times)
    - Thread-safe read access (immutable after load)

Note:
    Use the public API from app.i18n instead of accessing this directly:
        from app.i18n import t, t_list, init_i18n
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Final

from app.bootstrap.resources import resource_path

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_LANGUAGE: Final[str] = "tr"
"""Default/fallback language code (Turkish)"""

TRANSLATIONS_DIR_NAME: Final[str] = "translations"
"""Translation files directory name"""


# ============================================================================
# EXCEPTIONS
# ============================================================================

class TranslationError(Exception):
    """Base exception for translation errors."""
    pass


class TranslationLoadError(TranslationError):
    """Raised when translation file cannot be loaded."""
    pass


# ============================================================================
# TRANSLATOR CLASS
# ============================================================================

class Translator:
    """
    Translation manager (singleton pattern).
    
    Handles loading, storing, and retrieving translations with fallback
    support and parameter substitution.
    
    Class Attributes:
        _translations: Loaded translations {lang_code: translation_dict}
        _current_lang: Current active language code
        _fallback_lang: Fallback language code (used when key not found)
        _loaded: Whether translations have been loaded
        _lock: Thread lock for loading operations
    
    Thread Safety:
        - Loading is synchronized with _lock
        - Read operations are thread-safe after loading (immutable data)
        - set_language() is atomic (simple assignment)
    
    Usage:
        # Load translations
        Translator.load_all()
        
        # Get translation
        text = Translator.t("app.window_title")
        
        # Change language
        Translator.set_language("en")
    
    Note:
        Use the convenience functions from app.i18n instead:
            from app.i18n import t, init_i18n
    """
    
    # Class-level state (singleton pattern)
    _translations: dict[str, dict[str, Any]] = {}
    _current_lang: str = DEFAULT_LANGUAGE
    _fallback_lang: str = DEFAULT_LANGUAGE
    _loaded: bool = False
    _lock: Lock = Lock()
    
    @classmethod
    def load_all(cls) -> None:
        """
        Load all translation files from translations directory.
        
        Scans app/i18n/translations/*.json and loads each language file.
        Idempotent - safe to call multiple times (subsequent calls are no-ops).
        
        Thread-safe: Uses lock to prevent concurrent loading.
        
        Raises:
            TranslationLoadError: If critical error during loading
        
        Note:
            Missing or malformed files are logged as warnings but don't
            raise errors. At minimum, fallback language dict is created.
        """
        # Fast path: already loaded
        if cls._loaded:
            return
        
        # Thread-safe loading
        with cls._lock:
            # Double-check after acquiring lock
            if cls._loaded:
                return
            
            try:
                cls._load_translation_files()
                cls._loaded = True
                logger.info("Translations loaded successfully")
                
            except Exception as e:
                # Ensure fallback language exists even on error
                cls._translations.setdefault(cls._fallback_lang, {})
                cls._loaded = True
                logger.error(f"Translation loading failed: {e}", exc_info=True)
    
    @classmethod
    def _load_translation_files(cls) -> None:
        """
        Load translation JSON files from disk.
        
        Internal method - should only be called by load_all().
        
        Raises:
            TranslationLoadError: If translations directory not accessible
        """
        # Resolve translations directory path
        base_path = cls._resolve_translations_directory()
        
        if not base_path.is_dir():
            logger.warning(
                f"Translations directory not found: {base_path}. "
                "Using empty translations."
            )
            cls._translations.setdefault(cls._fallback_lang, {})
            return
        
        # Load all *.json files
        loaded_count = 0
        for json_path in base_path.glob("*.json"):
            try:
                cls._load_single_file(json_path)
                loaded_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to load translation file: {json_path.name}. "
                    f"Error: {e}"
                )
        
        # Ensure fallback language exists
        cls._translations.setdefault(cls._fallback_lang, {})
        
        logger.info(
            f"Loaded {loaded_count} translation file(s) from {base_path}"
        )
    
    @classmethod
    def _resolve_translations_directory(cls) -> Path:
        """
        Resolve path to translations directory.
        
        Handles both development and PyInstaller frozen modes.
        
        Returns:
            Path to translations directory
        """
        # Get loader.py file location
        loader_dir = Path(__file__).resolve().parent
        
        # translations directory is sibling to loader.py
        translations_rel_path = loader_dir / TRANSLATIONS_DIR_NAME
        
        # Use resource_path for PyInstaller support
        translations_path = resource_path(str(translations_rel_path))
        
        return Path(translations_path)
    
    @classmethod
    def _load_single_file(cls, file_path: Path) -> None:
        """
        Load a single translation JSON file.
        
        Args:
            file_path: Path to JSON translation file
            
        Raises:
            TranslationLoadError: If file cannot be parsed or is invalid
        """
        lang_code = file_path.stem  # e.g., "tr" from "tr.json"
        
        try:
            # Read and parse JSON
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            
            # Validate structure
            if not isinstance(data, dict):
                raise TranslationLoadError(
                    f"Translation file must contain JSON object, got: {type(data)}"
                )
            
            # Store translations
            cls._translations[lang_code] = data
            
            logger.debug(f"Loaded translation: {lang_code} ({file_path.name})")
            
        except json.JSONDecodeError as e:
            raise TranslationLoadError(
                f"Invalid JSON in {file_path.name}: {e}"
            ) from e
        except OSError as e:
            raise TranslationLoadError(
                f"Cannot read {file_path.name}: {e}"
            ) from e
    
    @classmethod
    def set_language(cls, lang_code: str) -> None:
        """
        Change current active language.
        
        Args:
            lang_code: Language code (e.g., "tr", "en")
        
        Note:
            If language not available, falls back to default language.
            This ensures application always has translations.
        
        Example:
            >>> Translator.set_language("en")
            >>> Translator.get_language()
            'en'
        """
        if not cls._loaded:
            cls.load_all()
        
        # Set language if available, otherwise use fallback
        if lang_code in cls._translations:
            cls._current_lang = lang_code
            logger.info(f"Language changed to: {lang_code}")
        else:
            cls._current_lang = cls._fallback_lang
            logger.warning(
                f"Language '{lang_code}' not available. "
                f"Using fallback: {cls._fallback_lang}"
            )
    
    @classmethod
    def get_language(cls) -> str:
        """
        Get current active language code.
        
        Returns:
            Current language code (e.g., "tr")
        
        Example:
            >>> Translator.get_language()
            'tr'
        """
        return cls._current_lang
    
    @classmethod
    def _get_bundle(cls, lang_code: str) -> dict[str, Any]:
        """
        Get translation bundle for a language.
        
        Args:
            lang_code: Language code
            
        Returns:
            Translation dictionary, or empty dict if not found
        """
        bundle = cls._translations.get(lang_code)
        return bundle if isinstance(bundle, dict) else {}
    
    @classmethod
    def _resolve_key(cls, data: dict[str, Any], key: str) -> Any | None:
        """
        Resolve dot-notation key in nested dictionary.
        
        Args:
            data: Dictionary to search
            key: Dot-notation key (e.g., "app.window_title")
            
        Returns:
            Value at key path, or None if not found
        
        Example:
            >>> data = {"app": {"window_title": "My App"}}
            >>> _resolve_key(data, "app.window_title")
            'My App'
            >>> _resolve_key(data, "app.missing")
            None
        """
        current: Any = data
        
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    @classmethod
    def t(cls, key: str, **params: Any) -> str:
        """
        Get translated string with optional parameter substitution.
        
        Performs fallback cascade:
        1. Try current language
        2. Try fallback language
        3. Return key itself (allows graceful degradation)
        
        Args:
            key: Dot-notation translation key (e.g., "app.window_title")
            **params: Format parameters for {placeholder} substitution
        
        Returns:
            Translated string with parameters substituted, or key if not found
        
        Example:
            >>> Translator.t("app.window_title")
            'PharmaLyser SMA'
            
            >>> Translator.t("errors.unexpected_with_type",
            ...              type="ValueError", msg="Bad input")
            'Beklenmeyen bir hata oluştu:\\nValueError: Bad input'
        
        Note:
            - Missing keys return the key itself (allows dev to see missing translations)
            - Format errors are caught silently (returns unformatted string)
        """
        # Ensure translations are loaded
        if not cls._loaded:
            cls.load_all()
        
        # Try current language
        current_bundle = cls._get_bundle(cls._current_lang)
        value = cls._resolve_key(current_bundle, key)
        
        # Fallback to default language
        if value is None:
            fallback_bundle = cls._get_bundle(cls._fallback_lang)
            value = cls._resolve_key(fallback_bundle, key)
        
        # Must be string to return
        if not isinstance(value, str):
            logger.debug(f"Translation key not found or not string: {key}")
            return key
        
        # Apply parameter substitution if requested
        if params:
            try:
                return value.format(**params)
            except (KeyError, ValueError) as e:
                logger.warning(
                    f"Translation format error for key '{key}': {e}. "
                    "Returning unformatted string."
                )
                return value
        
        return value
    
    @classmethod
    def t_list(cls, key: str) -> list[str]:
        """
        Get translated list of strings.
        
        Similar to t() but expects value to be a list of strings.
        
        Args:
            key: Dot-notation translation key
        
        Returns:
            List of translated strings, or empty list if not found/invalid
        
        Example:
            >>> Translator.t_list("loading.messages")
            ['Sistem başlatılıyor...', 'Arayüz hazırlanıyor...', ...]
            
            >>> Translator.t_list("invalid.key")
            []
        
        Note:
            - Non-string items in list are filtered out
            - Missing keys return empty list (not the key)
        """
        # Ensure translations are loaded
        if not cls._loaded:
            cls.load_all()
        
        # Try current language
        current_bundle = cls._get_bundle(cls._current_lang)
        value = cls._resolve_key(current_bundle, key)
        
        # Fallback to default language
        if value is None:
            fallback_bundle = cls._get_bundle(cls._fallback_lang)
            value = cls._resolve_key(fallback_bundle, key)
        
        # Must be list
        if not isinstance(value, list):
            logger.debug(f"Translation key not found or not list: {key}")
            return []
        
        # Filter to string items only
        return [item for item in value if isinstance(item, str)]
    
    @classmethod
    def get_available_languages(cls) -> list[str]:
        """
        Get list of available language codes.
        
        Returns:
            List of loaded language codes (e.g., ["tr", "en"])
        
        Example:
            >>> Translator.get_available_languages()
            ['tr']
        """
        if not cls._loaded:
            cls.load_all()
        return list(cls._translations.keys())
    
    @classmethod
    def is_loaded(cls) -> bool:
        """
        Check if translations have been loaded.
        
        Returns:
            True if load_all() has been called, False otherwise
        
        Example:
            >>> Translator.is_loaded()
            False
            >>> Translator.load_all()
            >>> Translator.is_loaded()
            True
        """
        return cls._loaded


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "Translator",
    "TranslationError",
    "TranslationLoadError",
]