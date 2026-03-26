# app\utils\well_mapping.py
# app/utils/well_mapping.py
"""
96-well plate coordinate mapping utilities.

Provides conversion functions between different well coordinate systems:
- Well ID (A01-H12)
- Patient number (1-96, column-major ordering)
- Table index (row, column with header offsets)

Coordinate Systems:
    1. Well ID: Human-readable format (A01, B05, H12)
    2. Patient Number: Sequential numbering 1-96
    3. Table Index: Visual table coordinates (row, col)

Column-Major Ordering:
    Patient numbers increment down columns, then across:
    A01=1, B01=2, ..., H01=8, A02=9, ..., H12=96

Usage:
    from app.utils.well_mapping import (
        patient_no_to_well_id,
        well_id_to_patient_no,
        is_valid_well_id
    )
    
    # Convert patient number to well ID
    well = patient_no_to_well_id(1)  # "A01"
    well = patient_no_to_well_id(96)  # "H12"
    
    # Convert well ID to patient number
    patient = well_id_to_patient_no("A01")  # 1
    patient = well_id_to_patient_no("H12")  # 96
    
    # Validate well ID
    if is_valid_well_id("A05"):
        process_well("A05")

Table Indexing:
    - (0, 0): Header cell (all wells)
    - (0, c): Column header (entire column)
    - (r, 0): Row header (entire row)
    - (r, c): Data cell (single well)

Note:
    All functions use column-major ordering for patient numbers.
    This matches the typical PCR plate layout and data collection order.
"""

from __future__ import annotations

import logging
import string
from typing import Final

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

ROWS: Final[tuple[str, ...]] = tuple(string.ascii_uppercase[:8])
"""Valid row letters: ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H')"""

COLUMNS: Final[tuple[int, ...]] = tuple(range(1, 13))
"""Valid column numbers: (1, 2, 3, ..., 12)"""

NUM_ROWS: Final[int] = len(ROWS)
"""Number of rows in 96-well plate (8)"""

NUM_COLUMNS: Final[int] = len(COLUMNS)
"""Number of columns in 96-well plate (12)"""

TOTAL_WELLS: Final[int] = NUM_ROWS * NUM_COLUMNS
"""Total number of wells (96)"""

MIN_PATIENT_NO: Final[int] = 1
"""Minimum patient number (inclusive)"""

MAX_PATIENT_NO: Final[int] = TOTAL_WELLS
"""Maximum patient number (inclusive, 96)"""


# ============================================================================
# WELL ID VALIDATION
# ============================================================================

def is_valid_well_id(well_id: str | None) -> bool:
    """
    Check if well ID is valid (A01-H12).
    
    Args:
        well_id: Well identifier to validate
        
    Returns:
        True if valid, False otherwise
        
    Validation:
        - Not None/empty
        - First char is A-H
        - Remaining chars parse to int 1-12
    
    Example:
        >>> is_valid_well_id("A01")
        True
        >>> is_valid_well_id("H12")
        True
        >>> is_valid_well_id("A13")
        False
        >>> is_valid_well_id("Z01")
        False
    """
    if not well_id or not isinstance(well_id, str):
        return False
    
    well_id = well_id.strip().upper()
    
    if len(well_id) < 2:
        return False
    
    # Validate row letter
    row = well_id[0]
    if row not in ROWS:
        return False
    
    # Validate column number
    try:
        col = int(well_id[1:])
    except ValueError:
        return False
    
    return col in COLUMNS


# ============================================================================
# WELL ID GENERATION
# ============================================================================

def all_well_ids() -> set[str]:
    """
    Generate all 96 well IDs in column-major order.
    
    Returns:
        Set of all well IDs (A01-H12)
        
    Order:
        A01, B01, C01, ..., H01,
        A02, B02, C02, ..., H02,
        ...
        A12, B12, C12, ..., H12
    
    Example:
        >>> wells = all_well_ids()
        >>> len(wells)
        96
        >>> "A01" in wells
        True
    """
    wells: list[str] = []
    
    for col in COLUMNS:
        for row in ROWS:
            wells.append(_format_well(row, col))
    
    return set(wells)


def _format_well(row: str, column: int) -> str:
    """
    Format well ID with zero-padded column.
    
    Args:
        row: Row letter (A-H)
        column: Column number (1-12)
        
    Returns:
        Formatted well ID (e.g., "A01", "H12")
    """
    return f"{row}{column:02d}"


# ============================================================================
# PATIENT NUMBER ↔ WELL ID CONVERSION
# ============================================================================

def patient_no_to_well_id(patient_no: int) -> str:
    """
    Convert patient number (1-96) to well ID.
    
    Uses column-major ordering: patient numbers increment down rows,
    then across columns.
    
    Args:
        patient_no: Patient number (1-96)
        
    Returns:
        Well ID (A01-H12)
        
    Raises:
        ValueError: If patient_no is invalid (not int or out of range)
        
    Example:
        >>> patient_no_to_well_id(1)
        'A01'
        >>> patient_no_to_well_id(8)
        'H01'
        >>> patient_no_to_well_id(9)
        'A02'
        >>> patient_no_to_well_id(96)
        'H12'
    
    Column-Major Order:
        1-8: A01-H01 (column 1)
        9-16: A02-H02 (column 2)
        ...
        89-96: A12-H12 (column 12)
    """
    if not isinstance(patient_no, int):
        raise ValueError(
            f"Patient number must be int, got {type(patient_no).__name__}"
        )
    
    if patient_no < MIN_PATIENT_NO or patient_no > MAX_PATIENT_NO:
        raise ValueError(
            f"Patient number out of range: {patient_no}. "
            f"Valid range: {MIN_PATIENT_NO}-{MAX_PATIENT_NO}"
        )
    
    # Convert to zero-based index
    zero_based = patient_no - 1
    
    # Column-major ordering
    col_idx = zero_based // NUM_ROWS
    row_idx = zero_based % NUM_ROWS
    
    well_id = _format_well(ROWS[row_idx], COLUMNS[col_idx])
    logger.debug(f"Patient {patient_no} → {well_id}")
    
    return well_id


def well_id_to_patient_no(well_id: str) -> int:
    """
    Convert well ID to patient number (1-96).
    
    Uses column-major ordering.
    
    Args:
        well_id: Well identifier (A01-H12)
        
    Returns:
        Patient number (1-96)
        
    Raises:
        ValueError: If well_id is invalid
        
    Example:
        >>> well_id_to_patient_no("A01")
        1
        >>> well_id_to_patient_no("H01")
        8
        >>> well_id_to_patient_no("A02")
        9
        >>> well_id_to_patient_no("H12")
        96
    """
    if not is_valid_well_id(well_id):
        raise ValueError(f"Invalid well ID: {well_id}")
    
    well_id = well_id.strip().upper()
    
    # Parse row and column
    row = well_id[0]
    col = int(well_id[1:])
    
    # Get indices
    row_idx = ROWS.index(row)
    col_idx = COLUMNS.index(col)
    
    # Column-major ordering
    patient_no = col_idx * NUM_ROWS + row_idx + 1
    
    logger.debug(f"Well {well_id} → Patient {patient_no}")
    
    return patient_no


# ============================================================================
# TABLE INDEX CONVERSION
# ============================================================================

def well_id_to_table_index(well_id: str) -> tuple[int, int]:
    """
    Convert well ID to table coordinates with header offsets.
    
    Table layout:
          0   1   2   3  ...  12
        +---+---+---+---+---+---+
      0 |   | 1 | 2 | 3 | ... |12|  (column headers)
        +---+---+---+---+---+---+
      1 | A |A01|A02|A03| ... |A12|
      2 | B |B01|B02|B03| ... |B12|
      ...
      8 | H |H01|H02|H03| ... |H12|
        +---+---+---+---+---+---+
    
    Args:
        well_id: Well identifier (A01-H12)
        
    Returns:
        Tuple of (row, column) with 1-based header offset
        
    Raises:
        ValueError: If well_id is invalid
        
    Example:
        >>> well_id_to_table_index("A01")
        (1, 1)
        >>> well_id_to_table_index("H12")
        (8, 12)
    """
    patient_no = well_id_to_patient_no(well_id)
    zero_based = patient_no - 1
    
    # Column-major to row/col
    row_idx = zero_based % NUM_ROWS
    col_idx = zero_based // NUM_ROWS
    
    # Add header offset (1-based)
    return (row_idx + 1, col_idx + 1)


def table_index_to_well_id(row: int, column: int) -> str | None:
    """
    Convert table coordinates to well ID.
    
    Args:
        row: Table row index (1-8 for data, 0 for header)
        column: Table column index (1-12 for data, 0 for header)
        
    Returns:
        Well ID if valid data cell, None for header cells
        
    Example:
        >>> table_index_to_well_id(1, 1)
        'A01'
        >>> table_index_to_well_id(0, 1)  # Column header
        None
        >>> table_index_to_well_id(1, 0)  # Row header
        None
    """
    # Header cells
    if row <= 0 or column <= 0:
        return None
    
    # Convert to zero-based
    row_idx = row - 1
    col_idx = column - 1
    
    # Validate range
    if row_idx >= NUM_ROWS or col_idx >= NUM_COLUMNS:
        return None
    
    return _format_well(ROWS[row_idx], COLUMNS[col_idx])


# ============================================================================
# WELL GROUPS
# ============================================================================

def wells_for_header(row: int, column: int) -> set[str]:
    """
    Get wells represented by a header/index position.
    
    Header Semantics:
        - (0, 0): All wells (entire plate)
        - (0, c): Entire column c
        - (r, 0): Entire row r
        - (r, c): Single well at (r, c)
    
    Args:
        row: Table row index (0=header, 1-8=data)
        column: Table column index (0=header, 1-12=data)
        
    Returns:
        Set of well IDs represented by this position
        
    Example:
        >>> wells_for_header(0, 0)  # All wells
        {'A01', 'A02', ..., 'H12'}  # (96 wells)
        
        >>> wells_for_header(0, 1)  # Column 1
        {'A01', 'B01', 'C01', ..., 'H01'}  # (8 wells)
        
        >>> wells_for_header(1, 0)  # Row A
        {'A01', 'A02', 'A03', ..., 'A12'}  # (12 wells)
        
        >>> wells_for_header(1, 1)  # Single well
        {'A01'}
    """
    # (0, 0): All wells
    if row == 0 and column == 0:
        return all_well_ids()
    
    # (0, c): Entire column
    if row == 0 and column > 0:
        if column not in COLUMNS:
            return set()
        return {_format_well(r, column) for r in ROWS}
    
    # (r, 0): Entire row
    if column == 0 and row > 0:
        row_idx = row - 1
        if row_idx >= NUM_ROWS:
            return set()
        row_label = ROWS[row_idx]
        return {_format_well(row_label, c) for c in COLUMNS}
    
    # (r, c): Single well
    well = table_index_to_well_id(row, column)
    return {well} if well else set()


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Validation
    "is_valid_well_id",
    
    # Well ID generation
    "all_well_ids",
    
    # Conversion
    "patient_no_to_well_id",
    "well_id_to_patient_no",
    "well_id_to_table_index",
    "table_index_to_well_id",
    
    # Well groups
    "wells_for_header",
    
    # Constants
    "ROWS",
    "COLUMNS",
    "NUM_ROWS",
    "NUM_COLUMNS",
    "TOTAL_WELLS",
    "MIN_PATIENT_NO",
    "MAX_PATIENT_NO",
]