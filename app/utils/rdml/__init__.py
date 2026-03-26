# app\utils\rdml\__init__.py
# app/utils/rdml/__init__.py
"""
RDML file reading and parsing utilities.

This module provides tools for working with RDML (Real-Time PCR Data Markup
Language) files. RDML is the standard format for PCR machine data exchange.

Usage:
    from app.utils.rdml import read_rdml_root, merge_fam_hex_rows
    
    # Read RDML file (handles both XML and ZIP formats)
    root = read_rdml_root("data.rdml")
    
    # Parse and merge FAM/HEX channel data
    data_rows = merge_fam_hex_rows(root)
    
    # Each row contains:
    # - React ID, Barkot No, Hasta Adı
    # - FAM Ct, FAM koordinat list
    # - HEX Ct, HEX koordinat list

Module Structure:
    - rdml_reader: File reading (XML/ZIP handling)
    - rdml_parser: Data extraction and parsing

Workflow:
    1. read_rdml_root() → XML Element
    2. merge_fam_hex_rows() → List of dicts
    3. Convert to DataFrame or process further

Note:
    RDML files can be either plain XML or ZIP archives.
    The reader automatically detects and handles both formats.
"""

from __future__ import annotations

# Reader functions
from .rdml_reader import (
    read_rdml_root,
    validate_rdml_root,
    get_rdml_version,
    RDMLReadError,
    RDML_NS,
    RDML_NAMESPACE,
)

# Parser functions
from .rdml_parser import (
    extract_run,
    parse_react,
    merge_fam_hex_rows,
    get_all_react_ids,
    RDMLParseError,
    Coordinate,
    ReactData,
    RUN_ID_FAM,
    RUN_ID_HEX,
    COL_REACT_ID,
    COL_BARCODE,
    COL_PATIENT_NAME,
    COL_FAM_CT,
    COL_HEX_CT,
    COL_FAM_COORDS,
    COL_HEX_COORDS,
)


__all__ = [
    # Reader
    "read_rdml_root",
    "validate_rdml_root",
    "get_rdml_version",
    "RDMLReadError",
    
    # Parser
    "extract_run",
    "parse_react",
    "merge_fam_hex_rows",
    "get_all_react_ids",
    "RDMLParseError",
    
    # Data types
    "Coordinate",
    "ReactData",
    
    # Constants
    "RDML_NS",
    "RDML_NAMESPACE",
    "RUN_ID_FAM",
    "RUN_ID_HEX",
    "COL_REACT_ID",
    "COL_BARCODE",
    "COL_PATIENT_NAME",
    "COL_FAM_CT",
    "COL_HEX_CT",
    "COL_FAM_COORDS",
    "COL_HEX_COORDS",
]