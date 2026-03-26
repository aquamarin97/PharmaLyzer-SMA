# app/constants/app_text_key.py
from dataclasses import dataclass


@dataclass(frozen=True)
class TextKey:
    # === UYGULAMA BAŞLIKLARI ===
    WINDOW_TITLE: str = "app.window_title"
    APP_NAME: str = "app.name"
    BRAND_NAME: str = "app.brand"

    # === BUTONLAR ===
    BUTTON_ANALYZE = "button_analyze"
    BUTTON_CLEAR = "button_clear"
    BUTTON_IMPORT = "button_import"
    BUTTON_EXPORT = "button_export"

    # === HATA VE UYARI MESAJLARI ===
    LICENSE_MISSING = "license_missing"
    LOADING = "loading"
    MSG_INVALID_SAVED = "msg_invalid_saved"
    MSG_INVALID_SELECTED = "msg_invalid_selected"
    MSG_PATH_SAVE_FAILED = "msg_path_save_failed"

    TITLE_LICENSE_ERROR = "errors.license.title"
    TITLE_ERROR = "errors.title"
    TITLE_SELECT_FILE = "title_select_file"

    # === YÜKLEME EKRANI ===
    LOADING_MESSAGES: str = "loading.messages"
    LOADING_PROGRESS: str = "loading.progress"