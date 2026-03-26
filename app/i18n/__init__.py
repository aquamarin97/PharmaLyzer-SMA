# app\i18n\__init__.py
# app/i18n/__init__.py
"""
Internationalization (i18n) system for the application.

This module provides translation management with:
- Lazy loading (translations loaded on first use)
- Fallback support (missing keys use fallback language)
- Parameter substitution (format strings with variables)
- Dot notation key access ("app.window_title")

Usage:
    from app.i18n import init_i18n, t, t_list, set_lang, current_lang
    
    # Initialize translations (call once at startup)
    init_i18n()
    
    # Get translated string
    title = t("app.window_title")  # "PharmaLyser SMA"
    
    # Get translated string with parameters
    error = t("errors.unexpected_with_type", type="ValueError", msg="Invalid input")
    
    # Get translated list
    loading_messages = t_list("loading.messages")
    
    # Change language
    set_lang("en")
    current = current_lang()

Architecture:
    - Translator: Core translation engine (singleton pattern)
    - Lazy loading: Translations loaded on first t() call or init_i18n()
    - Fallback: Missing keys return fallback language or key itself
    - Resource path: Uses bootstrap.resource_path for PyInstaller support

Note:
    All translation keys should be defined in app/constants/app_text_key.py
    for type safety and IDE autocomplete.
"""

from __future__ import annotations


from .loader import Translator

# ============================================================================
# PUBLIC API
# ============================================================================

# Translation functions (delegated to Translator)
t = Translator.t
"""
Get translated string with optional parameter substitution.

Args:
    key: Dot-notation translation key (e.g., "app.window_title")
    **params: Format parameters for {placeholder} substitution

Returns:
    Translated string, or key itself if translation missing

Example:
    >>> t("app.name")
    'PharmaLyser SMA'
    >>> t("errors.unexpected_with_type", type="Error", msg="Failed")
    'Beklenmeyen bir hata oluştu:\\nError: Failed'
"""

t_list = Translator.t_list
"""
Get translated list of strings.

Args:
    key: Dot-notation translation key

Returns:
    List of translated strings, or empty list if not found/invalid

Example:
    >>> t_list("loading.messages")
    ['Sistem başlatılıyor...', 'Arayüz hazırlanıyor...', ...]
"""

set_lang = Translator.set_language
"""
Change current language.

Args:
    lang: Language code (e.g., "tr", "en")

Note:
    If language not available, falls back to default language.

Example:
    >>> set_lang("en")
    >>> current_lang()
    'en'
"""

current_lang = Translator.get_language
"""
Get current language code.

Returns:
    Current language code (e.g., "tr")

Example:
    >>> current_lang()
    'tr'
"""


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_i18n() -> None:
    """
    Initialize translation system.
    
    Loads all translation files from app/i18n/translations/*.json.
    Safe to call multiple times (idempotent).
    
    Should be called once at application startup before any t() calls.
    However, translations are lazily loaded if not initialized explicitly.
    
    Example:
        >>> # In main.py or app startup
        >>> from app.i18n import init_i18n
        >>> init_i18n()
        >>> # Now translations are ready
    
    Note:
        This is optional - translations will auto-load on first t() call.
        Explicit init_i18n() is recommended for predictable startup behavior.
    """
    Translator.load_all()


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Translation functions
    "t",
    "t_list",
    
    # Language management
    "set_lang",
    "current_lang",
    
    # Initialization
    "init_i18n",
    
    # Advanced (for testing/debugging)
    "Translator",
]