# app\licensing\__init__.py
# app/licensing/__init__.py
"""
License validation module.

Simple license management system with:
- License key validation
- Device binding (MAC address)
- Expiration checking
- Persistent license path storage
- User interface for license selection

Usage:
    from app.licensing import ensure_license_or_exit
    
    # At application startup
    ensure_license_or_exit()
    
    # Application continues only if license is valid

Module Structure:
    - validator: License file validation logic
    - manager: License path storage/retrieval
    - ui: User interface dialogs

Security Note:
    This is a basic implementation for demonstration.
    For production, consider:
    - Encrypted license files
    - RSA signatures
    - Hardware-bound licensing (multiple identifiers)
    - Remote validation server
"""

from __future__ import annotations

# Main UI entry point
from .ui import ensure_license_or_exit

# Low-level APIs (for advanced use)
from .validator import validate_license_file, get_device_id
from .manager import save_license_path, read_saved_license_path


__all__ = [
    # Main API
    "ensure_license_or_exit",
    
    # Advanced APIs
    "validate_license_file",
    "get_device_id",
    "save_license_path",
    "read_saved_license_path",
]