# app/licensing/validator.py
"""
RSA İmza Tabanlı Offline Lisans Doğrulayıcı — İlk Kullanımda Cihaz Kilitleme.

Çalışma prensibi:
  - İmza doğrulandıktan sonra cihaz kimliği (MAC adresi) lisans dosyasına yazılır.
  - Sonraki açılışlarda bu cihaz kimliği kontrol edilir.
  - Farklı cihazda kullanmaya çalışılırsa reddedilir.

Güvenlik notu:
  - İlk aktivasyon öncesi kopyalanan dosya başka cihazda çalışabilir.
  - Aktivasyon sonrası kopyalanan dosya başka cihazda çalışmaz.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# GÖMÜLÜ PUBLIC KEY
# ============================================================================

_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA09RUVB1DZ9oQGqG4SV8I
1+/rlES/pMw9pEDDfsfNJWorGq9ExzioD+E0suhewHEI4a5RBYyzYFt377ddMU+f
ltKEtBroHHak/eidh5Gof6uKIGPDjpB5IBIS3TuWgaRFmJZyzXF6/pXf16xsaw4l
1Xb5Rjd5axXAX3EMFU9k3a3mWmifSJ2jRooUOMNBEPkJGgOMaXat4G/Dn/j4OyAt
KALbKFKXMum0WmsXrY7UDxIzC27AZMBKqGfZauc6uKrHcIs1ITe5ZUcRBVaGDG0e
IppHiWKVy9QXvBPGqiKYMRjf//oKs5SFTJTspG4W5iRkZ0ay9McvhUek/ciVVkdD
fQIDAQAB
-----END PUBLIC KEY-----"""


# ============================================================================
# CİHAZ KİMLİĞİ
# ============================================================================

def get_device_id() -> str:
    """Makineye özgü cihaz kimliği (MAC adresi tabanlı)."""
    return str(uuid.getnode())


# ============================================================================
# DOĞRULAMA
# ============================================================================

def validate_license_file(file_path: str | Path) -> bool:
    """
    Lisans dosyasını doğrular; ilk çalıştırmada cihaza kilitler.

    Doğrulama adımları:
      1. Dosya okunabilir ve geçerli JSON mi?
      2. Zorunlu alanlar mevcut mu?
      3. RSA-PSS imzası geçerli mi?
      4. Bitiş tarihi geçmemiş mi?
      5. Cihaz kilidi:
           - device_id yoksa  → ilk aktivasyon, mevcut cihazı yaz ve geç
           - device_id varsa  → bu cihazla eşleşiyor mu?

    Returns:
        True  → lisans geçerli
        False → lisans geçersiz, süresi dolmuş veya başka cihaza ait
    """
    try:
        return _validate(Path(file_path))
    except Exception as exc:
        logger.error("Lisans doğrulama hatası: %s", exc, exc_info=True)
        return False


def _validate(path: Path) -> bool:
    # 1. Dosyayı oku
    if not path.is_file():
        logger.warning("Lisans dosyası bulunamadı: %s", path)
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Lisans dosyası okunamadı: %s", exc)
        return False

    # 2. Zorunlu alan kontrolü
    required = ("customer", "expiry", "issued", "payload", "signature")
    missing = [k for k in required if not data.get(k)]
    if missing:
        logger.warning("Lisans alanları eksik: %s", missing)
        return False

    # 3. RSA imza doğrulama
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature

        public_key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM)
        payload    = base64.b64decode(data["payload"])
        signature  = base64.b64decode(data["signature"])

        public_key.verify(
            signature,
            payload,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        logger.debug("RSA imza doğrulandı")

    except InvalidSignature:
        logger.warning("Lisans imzası geçersiz (tahrif edilmiş olabilir).")
        return False
    except Exception as exc:
        logger.error("İmza doğrulama hatası: %s", exc)
        return False

    # 4. Bitiş tarihi kontrolü
    try:
        expiry = date.fromisoformat(data["expiry"])
    except ValueError:
        logger.warning("Geçersiz bitiş tarihi formatı: %s", data["expiry"])
        return False

    if date.today() > expiry:
        logger.warning("Lisans süresi dolmuş. Bitiş: %s", expiry)
        return False

    # 5. Cihaz kilidi
    current_device = get_device_id()
    locked_device  = data.get("device_id")

    if locked_device is None:
        # İlk aktivasyon: bu cihazı kaydet
        data["device_id"] = current_device
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                "Lisans bu cihaza kilitlendi. Cihaz ID: %s, Müşteri: %s",
                current_device,
                data.get("customer"),
            )
        except OSError as exc:
            logger.error("Cihaz kilidi yazılamadı: %s", exc)
            # Yazma başarısız olsa bile bu sefer geçir; sonraki açılışta tekrar dener
    else:
        # Aktivasyon sonrası: cihaz eşleşmesi kontrol
        if locked_device != current_device:
            logger.warning(
                "Cihaz uyuşmazlığı! Lisans başka cihaza ait. "
                "Beklenen: %s, Mevcut: %s",
                locked_device,
                current_device,
            )
            return False
        logger.debug("Cihaz kimliği doğrulandı")

    logger.info(
        "Lisans geçerli — Müşteri: %s, Bitiş: %s",
        data.get("customer"),
        expiry,
    )
    return True