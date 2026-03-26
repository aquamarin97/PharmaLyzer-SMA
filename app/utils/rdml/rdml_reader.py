# app\utils\rdml\rdml_reader.py
# app/utils/rdml/rdml_reader.py
"""
RDML file reader with ZIP support.

This module handles reading RDML (Real-Time PCR Data Markup Language) files.
RDML files can be either:
- Plain XML files (.rdml, .xml)
- ZIP archives containing XML (.rdml, .zip)

The reader automatically detects the format and extracts the XML root element.

Usage:
    from app.utils.rdml.rdml_reader import read_rdml_root
    
    # Read RDML file (auto-detects plain XML or ZIP)
    root = read_rdml_root("/path/to/file.rdml")
    
    # Now parse with rdml_parser
    from app.utils.rdml.rdml_parser import merge_fam_hex_rows
    data = merge_fam_hex_rows(root)

RDML Format:
    - RDML 1.2 Specification: http://www.rdml.org
    - Namespace: http://www.rdml.org
    - Root element: <rdml>

Supported Formats:
    1. Plain XML: Direct XML file
    2. Zipped XML: ZIP archive containing .xml file

Note:
    RDML files from PCR machines are typically zipped for compression.
    This reader transparently handles both formats.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

RDML_NAMESPACE: Final[str] = "http://www.rdml.org"
"""RDML XML namespace URI"""

RDML_NS: Final[dict[str, str]] = {"rdml": RDML_NAMESPACE}
"""Namespace dict for ElementTree XPath queries"""

VALID_XML_EXTENSIONS: Final[tuple[str, ...]] = (".xml", ".rdml")
"""Valid XML file extensions"""


# ============================================================================
# EXCEPTIONS
# ============================================================================

class RDMLReadError(Exception):
    """Raised when RDML file cannot be read or parsed."""
    pass


# ============================================================================
# XML READING
# ============================================================================

def _try_read_plain_xml(file_path: Path) -> ET.Element | None:
    """
    Attempt to read file as plain XML.
    
    Args:
        file_path: Path to file
        
    Returns:
        XML root element if successful, None if file is not valid XML
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        logger.debug(f"Successfully parsed as plain XML: {file_path.name}")
        return root
    except ET.ParseError as e:
        logger.debug(f"Not a plain XML file: {e}")
        return None
    except OSError as e:
        logger.error(f"Cannot read file: {file_path}. Error: {e}")
        raise RDMLReadError(f"Cannot read file: {e}") from e


def _try_read_zipped_xml(file_path: Path) -> ET.Element | None:
    """
    Attempt to read file as ZIP containing XML.
    
    Args:
        file_path: Path to ZIP file
        
    Returns:
        XML root element if successful, None if not a valid ZIP
        
    Raises:
        RDMLReadError: If ZIP is valid but contains no XML or XML is invalid
    """
    # Check if file is a valid ZIP
    if not zipfile.is_zipfile(file_path):
        logger.debug("Not a ZIP file")
        return None
    
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            # Find XML file in ZIP
            xml_files = [
                name for name in zf.namelist()
                if name.lower().endswith(VALID_XML_EXTENSIONS)
            ]
            
            if not xml_files:
                raise RDMLReadError(
                    f"No XML file found in ZIP archive. "
                    f"Expected files with extensions: {VALID_XML_EXTENSIONS}"
                )
            
            if len(xml_files) > 1:
                logger.warning(
                    f"Multiple XML files in ZIP: {xml_files}. "
                    f"Using first: {xml_files[0]}"
                )
            
            xml_name = xml_files[0]
            logger.debug(f"Extracting XML from ZIP: {xml_name}")
            
            # Read and parse XML
            with zf.open(xml_name) as f:
                xml_data = f.read()
                
            try:
                root = ET.fromstring(xml_data)
                logger.info(f"Successfully parsed XML from ZIP: {file_path.name}")
                return root
            except ET.ParseError as e:
                raise RDMLReadError(
                    f"Invalid XML inside ZIP archive: {e}"
                ) from e
                
    except zipfile.BadZipFile as e:
        raise RDMLReadError(f"Corrupted ZIP file: {e}") from e
    except OSError as e:
        raise RDMLReadError(f"Cannot read ZIP file: {e}") from e


# ============================================================================
# PUBLIC API
# ============================================================================

def read_rdml_root(file_path: str | Path) -> ET.Element:
    """
    Read RDML file and return XML root element.
    
    Automatically detects whether the file is:
    - Plain XML (direct parse)
    - ZIP archive containing XML (extract and parse)
    
    Args:
        file_path: Path to RDML file
        
    Returns:
        XML root element
        
    Raises:
        RDMLReadError: If file cannot be read or is not valid RDML
        ValueError: If file path is empty or None
    
    Example:
        >>> root = read_rdml_root("data.rdml")
        >>> print(root.tag)
        '{http://www.rdml.org}rdml'
        
        >>> # Works with zipped files too
        >>> root = read_rdml_root("data.zip")
    
    Note:
        The function tries plain XML first, then ZIP.
        This is efficient because most RDML files are zipped.
    """
    # Validate input
    if not file_path:
        raise ValueError("RDML file path cannot be empty")
    
    path = Path(file_path)
    
    # Check file exists
    if not path.exists():
        raise RDMLReadError(f"RDML file not found: {path}")
    
    if not path.is_file():
        raise RDMLReadError(f"Path is not a file: {path}")
    
    logger.info(f"Reading RDML file: {path.name}")
    
    # Try reading as plain XML
    root = _try_read_plain_xml(path)
    if root is not None:
        return root
    
    # Try reading as ZIP
    root = _try_read_zipped_xml(path)
    if root is not None:
        return root
    
    # Neither format worked
    raise RDMLReadError(
        f"File is neither valid XML nor valid ZIP archive: {path}. "
        f"RDML files must be either plain XML or ZIP containing XML."
    )


def validate_rdml_root(root: ET.Element) -> bool:
    """
    Validate that XML root is a valid RDML document.
    
    Args:
        root: XML root element
        
    Returns:
        True if valid RDML root, False otherwise
        
    Validation Checks:
        - Root tag is {namespace}rdml
        - Namespace matches RDML specification
    
    Example:
        >>> root = read_rdml_root("data.rdml")
        >>> if validate_rdml_root(root):
        ...     print("Valid RDML document")
    """
    if root is None:
        return False
    
    # Check root tag
    expected_tag = f"{{{RDML_NAMESPACE}}}rdml"
    
    if root.tag != expected_tag:
        logger.warning(
            f"Invalid RDML root tag. "
            f"Expected: {expected_tag}, Got: {root.tag}"
        )
        return False
    
    return True


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_rdml_version(root: ET.Element) -> str | None:
    """
    Get RDML version from root element.
    
    Args:
        root: RDML XML root element
        
    Returns:
        Version string (e.g., "1.2") or None if not specified
        
    Example:
        >>> root = read_rdml_root("data.rdml")
        >>> version = get_rdml_version(root)
        >>> print(f"RDML version: {version}")
    """
    return root.get("version")


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main API
    "read_rdml_root",
    "validate_rdml_root",
    
    # Utilities
    "get_rdml_version",
    
    # Constants
    "RDML_NS",
    "RDML_NAMESPACE",
    
    # Exceptions
    "RDMLReadError",
]