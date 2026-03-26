# main.py
"""
Pharmalyzer application entry point.

Başlangıç sırası:
  1. Konfigürasyon yükle (ayarlar, i18n, loglama)
  2. Qt uygulaması oluştur
  3. Splash screen göster   <- mümkün olan en erken nokta
  4. Lisans doğrula         <- splash'te görünür
  5. Model başlat
  6. Warmup görevleri       <- splash'te görünür
  7. View & Controller başlat
  8. Ana pencereyi göster

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
import sys
import multiprocessing
import os

multiprocessing.freeze_support()

os.environ["LOKY_MAX_CPU_COUNT"] = "1"

# Loky yerine threading backend kullan
try:
    import joblib
    joblib.parallel.DEFAULT_BACKEND = "threading"
except Exception:
    pass
logger = logging.getLogger(__name__)


# ============================================================================
# KONFİGÜRASYON
# ============================================================================

def configure_app():
    """
    Ayarları, i18n'i, loglama ve exception hook'u başlatır.
    Sadece hafif import'lar — Qt veya C extension yok.

    Returns:
        Yapılandırılmış AppSettings örneği
    """
    from app.config.settings import AppSettings
    from app.i18n import init_i18n
    from app.logging.setup import LoggingConfig, setup_logging
    from app.exceptions.base import install_global_exception_hook

    settings = AppSettings.from_env()
    init_i18n()

    level = getattr(logging, settings.log_level, logging.INFO)

    # Frozen (dist) modunda stdout'a yazma — konsol flash önlenir
    is_frozen = getattr(sys, 'frozen', False)

    setup_logging(
        LoggingConfig(
            app_name=settings.app_name,
            level=level,
            log_dir=settings.log_dir,
            to_console=False if is_frozen else settings.log_to_console,
        )
    )

    logger.info("Pharmalyzer baslatiliyor — log seviyesi: %s", settings.log_level)
    install_global_exception_hook()

    return settings


# ============================================================================
# SPLASH YARDIMCISI
# ============================================================================

def _splash_msg(splash, message: str, percent: int) -> None:
    """
    Splash ekranında mesaj ve yüzde gösterir.
    """
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    try:
        from app.constants.app_styles import ColorPalette
        color = ColorPalette.PRIMARY_TEXT
    except Exception:
        color = Qt.black

    try:
        splash.showMessage(
            f"{message}  {percent}%",
            alignment=Qt.AlignBottom | Qt.AlignHCenter,
            color=color,
        )
        QApplication.processEvents()
    except Exception as exc:
        logger.debug("Splash guncelleme hatasi: %s", exc)


# ============================================================================
# LİSANS DOĞRULAMA
# ============================================================================

def handle_license(splash, app) -> None:
    """
    Lisansı splash screen üzerinde doğrular.

    Akış:
      - Kaydedilmiş geçerli lisans var → hızlıca geç
      - Geçersiz/eksik lisans → splash gizle, diyalog göster, splash geri getir
    """
    from PyQt5.QtWidgets import QApplication
    from app.licensing.manager import read_saved_license_path
    from app.licensing.validator import validate_license_file
    from app.licensing.ui import ensure_license_or_exit

    _splash_msg(splash, "Lisans kontrol ediliyor...", 8)

    saved_path = read_saved_license_path()
    if saved_path and validate_license_file(saved_path):
        _splash_msg(splash, "Lisans dogrulandi", 12)
        logger.info("Kaydedilmis lisans gecerli.")
        return

    logger.warning("Gecerli lisans bulunamadi, kullanicidan isteniyor.")

    splash.hide()
    QApplication.processEvents()

    try:
        ensure_license_or_exit(app)
    except SystemExit:
        raise

    splash.show()
    _splash_msg(splash, "Lisans dogrulandi", 12)
    logger.info("Yeni lisans dogrulandi ve kaydedildi.")


# ============================================================================
# UYGULAMA GİRİŞ NOKTASI
# ============================================================================

def main() -> int:
    """
    Ana başlangıç fonksiyonu.

    Returns:
        Çıkış kodu (0 = başarı)
    """
    # ---- Konfigürasyon (hafif, Qt yok) ----
    settings = configure_app()

    # ---- Qt uygulaması ----
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)

    # ---- Splash HEMEN aç — bundan sonraki her şey splash arkasında ----
    from app.bootstrap.splash import create_splash
    from app.bootstrap.resources import resource_path
    from app.constants.asset_paths import IMAGE_PATHS

    app.setWindowIcon(QIcon(resource_path(str(IMAGE_PATHS.APP_LOGO_PNG))))

    splash = create_splash()
    _splash_msg(splash, "Baslatiliyor...", 5)

    # ---- Lisans doğrulama ----
    handle_license(splash, app)

    # ---- Ağır import'lar (splash açıkken) ----
    _splash_msg(splash, "Modüller yükleniyor...", 16)
    from app.models.main_model import MainModel
    from app.bootstrap.warmup import run_warmup
    from app.controllers.main_controller import MainController
    from app.views.main_view import MainView

    # ---- Model ----
    _splash_msg(splash, "Model hazirlaniyor...", 18)
    model = MainModel()
    app.aboutToQuit.connect(model.shutdown)

    # ---- Warmup ----
    if settings.warmup_enabled:
        logger.info("Warmup baslatiliyor.")

        def warmup_progress(msg: str, pct: int) -> None:
            mapped_pct = 20 + int(pct * 0.75)
            base = msg.split("  ")[0] if "  " in msg else msg
            _splash_msg(splash, base, mapped_pct)

        try:
            run_warmup(warmup_progress)
            logger.info("Warmup tamamlandi.")
        except Exception as exc:
            logger.warning("Warmup basarisiz (devam ediliyor): %s", exc)
    else:
        logger.debug("Warmup devre disi.")

    # ---- View & Controller ----
    _splash_msg(splash, "Arayuz hazirlaniyor...", 97)
    view = MainView()
    controller = MainController(view, model)
    view.controller = controller  # GC'den koruma

    # ---- Ana pencereyi aç ----
    _splash_msg(splash, "Hazir!", 100)
    splash.finish(view)
    view.show()

    logger.info("Ana pencere gosterildi, olay dongusune girildi.")
    return app.exec_()


# ============================================================================
# GİRİŞ NOKTASI
# ============================================================================

if __name__ == "__main__":
    try:
        exit_code = main()
        logger.info("Uygulama %d koduyla kapandi.", exit_code)
        sys.exit(exit_code)
    except SystemExit as exc:
        sys.exit(exc.code)
    except Exception as exc:
        logger.critical("main() icinde islenmemis hata", exc_info=True)
        from app.exceptions.handler import handle_exception
        sys.exit(handle_exception(exc))