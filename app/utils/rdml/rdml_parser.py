# app\utils\rdml\rdml_parser.py
# app/utils/rdml/rdml_parser.py
"""
RDML XML data extraction and parsing.

This module extracts PCR data from RDML XML structure:
- Run data (FAM and HEX channels)
- Sample information (patient ID, barcode)
- Ct values (cycle threshold)
- Amplification curve coordinates (cycle, fluorescence)

Data Flow:
    1. Read RDML file → rdml_reader.read_rdml_root()
    2. Extract runs → extract_run()
    3. Parse reactions → parse_react()
    4. Merge FAM/HEX → merge_fam_hex_rows()

Usage:
    from app.utils.rdml.rdml_reader import read_rdml_root
    from app.utils.rdml.rdml_parser import merge_fam_hex_rows
    
    # Read and parse RDML file
    root = read_rdml_root("data.rdml")
    data_rows = merge_fam_hex_rows(root)
    
    # Each row contains:
    # - React ID
    # - Barkot No (barcode)
    # - Hasta Adı (patient name)
    # - FAM Ct, FAM koordinat list
    # - HEX Ct, HEX koordinat list

RDML Structure:
    <rdml>
      <run id="Amp Step 3_FAM">
        <react id="1">
          <sample id="Barcode123"/>
          <data>
            <tar id="PatientName"/>
            <cq>25.5</cq>
            <adp><cyc>1</cyc><fluor>100.5</fluor></adp>
            ...
          </data>
        </react>
      </run>
    </rdml>

Note:
    Column names are in Turkish (domain requirement).
    Coordinate lists are tuples of (cycle: int, fluorescence: float).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

RDML_NS: Final[dict[str, str]] = {"rdml": "http://www.rdml.org"}
"""RDML XML namespace for XPath queries"""

# Run IDs (fixed in RDML format from PCR machine)
RUN_ID_FAM: Final[str] = "Amp Step 3_FAM"
"""FAM channel run identifier"""

RUN_ID_HEX: Final[str] = "Amp Step 3_HEX"
"""HEX channel run identifier"""

# Column names (Turkish - domain requirement)
COL_REACT_ID: Final[str] = "React ID"
COL_BARCODE: Final[str] = "Barkot No"
COL_PATIENT_NAME: Final[str] = "Hasta Adı"
COL_FAM_CT: Final[str] = "FAM Ct"
COL_HEX_CT: Final[str] = "HEX Ct"
COL_FAM_COORDS: Final[str] = "FAM koordinat list"
COL_HEX_COORDS: Final[str] = "HEX koordinat list"

# Precision
CT_VALUE_PRECISION: Final[int] = 6
"""Decimal precision for Ct values"""

FLUORESCENCE_PRECISION: Final[int] = 6
"""Decimal precision for fluorescence values"""


# ============================================================================
# DATA TYPES
# ============================================================================

@dataclass(frozen=True, slots=True)
class Coordinate:
    """
    Amplification curve coordinate point.
    
    Attributes:
        cycle: PCR cycle number (1-40 typically)
        fluorescence: Fluorescence value (arbitrary units)
    """
    
    cycle: int
    fluorescence: float
    
    def to_tuple(self) -> tuple[int, float]:
        """Convert to (cycle, fluorescence) tuple."""
        return (self.cycle, self.fluorescence)


@dataclass
class ReactData:
    """
    Parsed reaction (well) data.
    
    Attributes:
        react_id: Well identifier (e.g., "1", "A1")
        barcode: Sample barcode number
        patient_name: Patient identifier
        ct_value: Cycle threshold value
        coordinates: List of (cycle, fluorescence) coordinates
    """
    
    react_id: str
    barcode: str
    patient_name: str
    ct_value: float | str  # Can be empty string if no Ct
    coordinates: list[Coordinate]


# ============================================================================
# EXCEPTIONS
# ============================================================================

class RDMLParseError(Exception):
    """Raised when RDML XML cannot be parsed."""
    pass


# ============================================================================
# RUN EXTRACTION
# ============================================================================

def extract_run(root: ET.Element, run_id: str) -> ET.Element:
    """
    Extract a specific run from RDML root.
    
    Args:
        root: RDML XML root element
        run_id: Run identifier (e.g., "Amp Step 3_FAM")
        
    Returns:
        Run XML element
        
    Raises:
        RDMLParseError: If run not found
        
    Example:
        >>> root = read_rdml_root("data.rdml")
        >>> fam_run = extract_run(root, "Amp Step 3_FAM")
    """
    run = root.find(f".//rdml:run[@id='{run_id}']", namespaces=RDML_NS)
    
    if run is None:
        raise RDMLParseError(f"Run not found: '{run_id}'")
    
    logger.debug(f"Extracted run: {run_id}")
    return run


# ============================================================================
# REACTION PARSING
# ============================================================================

def _extract_react_id(react: ET.Element) -> str:
    """Extract reaction ID from react element."""
    return react.get("id", "")


def _extract_barcode(react: ET.Element) -> str:
    """Extract sample barcode from react element."""
    sample = react.find("rdml:sample", namespaces=RDML_NS)
    return sample.get("id", "") if sample is not None else ""


def _extract_patient_name(react: ET.Element) -> str:
    """Extract patient name (target ID) from react element."""
    tar = react.find(".//rdml:tar", namespaces=RDML_NS)
    return tar.get("id", "") if tar is not None else ""


def _extract_ct_value(react: ET.Element) -> float | str:
    """
    Extract Ct value from react element.
    
    Returns:
        Rounded Ct value or empty string if not found
    """
    cq = react.find(".//rdml:cq", namespaces=RDML_NS)
    
    if cq is None or cq.text is None:
        return ""
    
    try:
        ct = float(cq.text)
        return round(ct, CT_VALUE_PRECISION)
    except (ValueError, TypeError):
        logger.warning(f"Invalid Ct value: {cq.text}")
        return ""


def _extract_coordinates(react: ET.Element) -> list[Coordinate]:
    """
    Extract amplification curve coordinates from react element.
    
    Returns:
        List of Coordinate objects (cycle, fluorescence)
    """
    adps = react.findall(".//rdml:adp", namespaces=RDML_NS)
    coordinates: list[Coordinate] = []
    
    for adp in adps:
        cyc_elem = adp.find("rdml:cyc", namespaces=RDML_NS)
        fluor_elem = adp.find("rdml:fluor", namespaces=RDML_NS)
        
        # Skip if missing data
        if (cyc_elem is None or fluor_elem is None or
            cyc_elem.text is None or fluor_elem.text is None):
            continue
        
        try:
            cycle = int(cyc_elem.text)
            fluorescence = round(float(fluor_elem.text), FLUORESCENCE_PRECISION)
            coordinates.append(Coordinate(cycle, fluorescence))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid coordinate data: {e}")
            continue
    
    return coordinates


def parse_react(react: ET.Element, run_id: str) -> dict[str, str | list[tuple[int, float]]]:
    """
    Parse a single reaction element into a dictionary.
    
    Args:
        react: React XML element
        run_id: Run identifier for column naming (FAM or HEX)
        
    Returns:
        Dictionary with parsed reaction data
        
    Dictionary Structure:
        {
            "React ID": "1",
            "Barkot No": "Barcode123",
            "Hasta Adı": "Patient001",
            "FAM Ct": 25.5,  # or "" if missing
            "FAM koordinat list": [(1, 100.5), (2, 150.3), ...]
        }
    
    Example:
        >>> react_elem = fam_run.find("rdml:react[@id='1']", namespaces=RDML_NS)
        >>> data = parse_react(react_elem, "FAM")
        >>> print(data["FAM Ct"])
        25.5
    """
    row: dict[str, str | list[tuple[int, float]]] = {}
    
    # Extract basic information
    row[COL_REACT_ID] = _extract_react_id(react)
    row[COL_BARCODE] = _extract_barcode(react)
    row[COL_PATIENT_NAME] = _extract_patient_name(react)
    
    # Extract Ct value
    ct_value = _extract_ct_value(react)
    row[f"{run_id} Ct"] = ct_value
    
    # Extract coordinates
    coordinates = _extract_coordinates(react)
    coord_tuples = [coord.to_tuple() for coord in coordinates]
    row[f"{run_id} koordinat list"] = coord_tuples
    
    return row


# ============================================================================
# FAM/HEX MERGING
# ============================================================================

def merge_fam_hex_rows(root: ET.Element) -> list[dict[str, str | list[tuple[int, float]]]]:
    """
    Merge FAM and HEX run data into combined rows.
    
    Extracts data from both FAM and HEX runs and combines them by React ID.
    Each output row contains both FAM and HEX data for the same well.
    
    Args:
        root: RDML XML root element
        
    Returns:
        List of dictionaries, each containing merged FAM/HEX data
        
    Raises:
        RDMLParseError: If required runs not found
        
    Example:
        >>> root = read_rdml_root("data.rdml")
        >>> rows = merge_fam_hex_rows(root)
        >>> for row in rows:
        ...     print(f"Well {row['React ID']}: "
        ...           f"FAM Ct={row['FAM Ct']}, HEX Ct={row['HEX Ct']}")
    
    Note:
        - FAM run is primary (all FAM reactions included)
        - HEX data is matched by React ID
        - Missing HEX data results in empty strings
    """
    # Extract runs
    try:
        fam_run = extract_run(root, RUN_ID_FAM)
        hex_run = extract_run(root, RUN_ID_HEX)
    except RDMLParseError as e:
        logger.error(f"Cannot extract runs: {e}")
        raise
    
    # Build HEX lookup map (O(1) access by React ID)
    hex_map: dict[str, ET.Element] = {}
    for hex_react in hex_run.findall("rdml:react", namespaces=RDML_NS):
        react_id = hex_react.get("id", "")
        if react_id:
            hex_map[react_id] = hex_react
    
    logger.debug(f"Found {len(hex_map)} HEX reactions")
    
    # Process FAM reactions and merge with HEX
    rows: list[dict] = []
    
    for fam_react in fam_run.findall("rdml:react", namespaces=RDML_NS):
        # Parse FAM data
        row = parse_react(fam_react, run_id="FAM")
        react_id = row[COL_REACT_ID]
        
        # Try to find matching HEX data
        hex_react = hex_map.get(react_id)
        
        if hex_react is not None:
            # Merge HEX data
            hex_row = parse_react(hex_react, run_id="HEX")
            row[COL_HEX_CT] = hex_row.get("HEX Ct", "")
            row[COL_HEX_COORDS] = hex_row.get("HEX koordinat list", [])
        else:
            # No HEX data for this reaction
            row[COL_HEX_CT] = ""
            row[COL_HEX_COORDS] = []
            logger.debug(f"No HEX data for React ID: {react_id}")
        
        rows.append(row)
    
    logger.info(f"Merged {len(rows)} FAM/HEX rows")
    return rows


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_all_react_ids(root: ET.Element) -> list[str]:
    """
    Get all reaction IDs from RDML root.
    
    Args:
        root: RDML XML root element
        
    Returns:
        List of unique reaction IDs
        
    Example:
        >>> root = read_rdml_root("data.rdml")
        >>> ids = get_all_react_ids(root)
        >>> print(f"Found {len(ids)} reactions")
    """
    react_ids: set[str] = set()
    
    for react in root.findall(".//rdml:react", namespaces=RDML_NS):
        react_id = react.get("id", "")
        if react_id:
            react_ids.add(react_id)
    
    return sorted(react_ids)


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Main parsing functions
    "extract_run",
    "parse_react",
    "merge_fam_hex_rows",
    
    # Utilities
    "get_all_react_ids",
    
    # Data types
    "Coordinate",
    "ReactData",
    
    # Constants
    "RDML_NS",
    "RUN_ID_FAM",
    "RUN_ID_HEX",
    "COL_REACT_ID",
    "COL_BARCODE",
    "COL_PATIENT_NAME",
    "COL_FAM_CT",
    "COL_HEX_CT",
    "COL_FAM_COORDS",
    "COL_HEX_COORDS",
    
    # Exceptions
    "RDMLParseError",
]