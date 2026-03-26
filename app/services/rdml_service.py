# app\services\rdml_service.py
# app/services/rdml_service.py
"""
RDML file processing service.

This service orchestrates RDML file reading, parsing, and DataFrame conversion.
Provides a clean boundary between RDML data format and application data model.

Workflow:
    1. Validate file path and existence
    2. Read RDML file (XML/ZIP handling)
    3. Parse FAM/HEX run data
    4. Convert to DataFrame
    5. Normalize columns and types
    6. Validate output

Usage:
    from app.services.rdml_service import RDMLService
    
    # Convert RDML to DataFrame
    service = RDMLService()
    df = service.rdml_to_dataframe("/path/to/data.rdml")
    
    # DataFrame is ready for analysis
    print(df.columns)  # Standard columns guaranteed

Column Normalization:
    - React ID: Numeric (patient number)
    - Barkot No: String (barcode)
    - Hasta Adı: String (patient name)
    - FAM Ct, HEX Ct: Numeric (cycle threshold)
    - Coordinate lists: String representation of list

Note:
    This service is stateless - each call is independent.
    No UI dependencies - pure data processing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import pandas as pd

from app.utils.rdml.rdml_reader import read_rdml_root, RDMLReadError
from app.utils.rdml.rdml_parser import (
    merge_fam_hex_rows,
    RDMLParseError,
    COL_REACT_ID,
    COL_BARCODE,
    COL_PATIENT_NAME,
    COL_FAM_CT,
    COL_HEX_CT,
    COL_FAM_COORDS,
    COL_HEX_COORDS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_COLUMNS: Final[tuple[str, ...]] = (
    COL_REACT_ID,
    COL_BARCODE,
    COL_PATIENT_NAME,
    COL_FAM_CT,
    COL_HEX_CT,
    COL_FAM_COORDS,
    COL_HEX_COORDS,
)
"""Standard output column order"""

VALID_FILE_EXTENSIONS: Final[tuple[str, ...]] = (".rdml", ".xml", ".zip")
"""Accepted file extensions for RDML files"""


# ============================================================================
# EXCEPTIONS
# ============================================================================

class RDMLServiceError(Exception):
    """Raised when RDML service operations fail."""
    pass


# ============================================================================
# RDML SERVICE
# ============================================================================

class RDMLService:
    """
    RDML file processing service.
    
    Converts RDML files to standardized pandas DataFrames with:
    - Column normalization
    - Type conversion
    - Data validation
    
    Features:
        - Stateless operation (thread-safe)
        - Comprehensive error handling
        - Type-safe DataFrame output
        - Column order guarantee
    
    Example:
        >>> # Use as static method (no instance needed)
        >>> df = RDMLService.rdml_to_dataframe("data.rdml")
        >>> print(df.columns)
        ['React ID', 'Barkot No', 'Hasta Adı', 'FAM Ct', ...]
    
    Note:
        All methods are static - no need to instantiate the class.
    """
    
    @staticmethod
    def rdml_to_dataframe(file_path: str | Path) -> pd.DataFrame:
        """
        Convert RDML file to standardized DataFrame.
        
        Complete workflow:
        1. Validate file path and existence
        2. Read RDML XML structure
        3. Parse FAM/HEX reaction data
        4. Convert to DataFrame
        5. Ensure standard columns exist
        6. Normalize data types
        7. Order columns consistently
        
        Args:
            file_path: Path to RDML file (.rdml, .xml, .zip)
            
        Returns:
            Standardized DataFrame with guaranteed columns
            
        Raises:
            RDMLServiceError: If conversion fails
            RDMLReadError: If file cannot be read
            RDMLParseError: If XML structure is invalid
            
        Example:
            >>> service = RDMLService()
            >>> df = service.rdml_to_dataframe("experiment.rdml")
            >>> print(df.shape)
            (96, 7)  # 96 wells × 7 columns
        
        Note:
            - Missing columns are added with appropriate defaults
            - Data types are normalized (numeric for Ct, string for IDs)
            - Column order is guaranteed to match DEFAULT_COLUMNS
        """
        # Step 1: Validate input
        path = RDMLService._validate_file_path(file_path)
        
        try:
            # Step 2: Read RDML file
            logger.info(f"Reading RDML file: {path.name}")
            root = read_rdml_root(path)
            
            # Step 3: Parse reaction data
            logger.debug("Parsing FAM/HEX reaction data")
            rows = merge_fam_hex_rows(root)
            
            if not rows:
                raise RDMLServiceError("No reaction data found in RDML file")
            
            # Step 4: Create DataFrame
            df = pd.DataFrame(rows)
            logger.debug(f"Created DataFrame: {df.shape}")
            
            # Step 5: Ensure standard columns
            RDMLService._ensure_standard_columns(df)
            
            # Step 6: Normalize data types
            df = RDMLService._normalize_data_types(df)
            
            # Step 7: Order columns
            df = df[list(DEFAULT_COLUMNS)]
            
            # Validate output
            if df.empty:
                raise RDMLServiceError("DataFrame is empty after processing")
            
            logger.info(
                f"RDML processed successfully: {path.name} "
                f"({len(df)} reactions)"
            )
            
            return df
            
        except (RDMLReadError, RDMLParseError) as e:
            logger.error(f"RDML processing failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing RDML: {e}", exc_info=True)
            raise RDMLServiceError(f"Failed to process RDML file: {e}") from e
    
    @staticmethod
    def _validate_file_path(file_path: str | Path) -> Path:
        """
        Validate RDML file path.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Validated Path object
            
        Raises:
            RDMLServiceError: If path is invalid
        """
        if not file_path:
            raise RDMLServiceError("File path is empty")
        
        path = Path(file_path)
        
        # Check file exists
        if not path.exists():
            raise RDMLServiceError(f"File not found: {path}")
        
        if not path.is_file():
            raise RDMLServiceError(f"Path is not a file: {path}")
        
        # Check extension (warning only, not blocking)
        if path.suffix.lower() not in VALID_FILE_EXTENSIONS:
            logger.warning(
                f"Unexpected file extension: {path.suffix}. "
                f"Expected: {VALID_FILE_EXTENSIONS}"
            )
        
        return path
    
    @staticmethod
    def _ensure_standard_columns(df: pd.DataFrame) -> None:
        """
        Ensure DataFrame has all standard columns.
        
        Adds missing columns with appropriate defaults:
        - Text columns: Empty string
        - Numeric columns: pd.NA
        - Coordinate lists: "[]" (empty list string)
        
        Args:
            df: DataFrame to update (modified in-place)
        """
        # Text columns with empty string default
        text_columns = (COL_BARCODE, COL_PATIENT_NAME)
        for col in text_columns:
            if col not in df.columns:
                df[col] = ""
                logger.debug(f"Added missing column: {col} (default: '')")
        
        # Numeric columns with NA default
        numeric_columns = (COL_FAM_CT, COL_HEX_CT, COL_REACT_ID)
        for col in numeric_columns:
            if col not in df.columns:
                df[col] = pd.NA
                logger.debug(f"Added missing column: {col} (default: NA)")
        
        # Coordinate list columns with "[]" default
        coord_columns = (COL_FAM_COORDS, COL_HEX_COORDS)
        for col in coord_columns:
            if col not in df.columns:
                df[col] = "[]"
                logger.debug(f"Added missing column: {col} (default: [])")
    
    @staticmethod
    def _normalize_data_types(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame column data types.
        
        Type conversions:
        - React ID: Numeric (coerce errors to NA)
        - FAM Ct, HEX Ct: Numeric (coerce errors to NA)
        - Coordinate lists: String (NA → "[]")
        - Barkot No, Hasta Adı: String (NA → "")
        
        Args:
            df: DataFrame to normalize
            
        Returns:
            DataFrame with normalized types
        """
        # Create copy to avoid modifying original
        normalized = df.copy(deep=False)
        
        # Convert React ID to numeric
        normalized[COL_REACT_ID] = pd.to_numeric(
            normalized[COL_REACT_ID],
            errors="coerce"
        )
        
        # Convert Ct values to numeric
        for col in (COL_FAM_CT, COL_HEX_CT):
            normalized[col] = pd.to_numeric(
                normalized[col],
                errors="coerce"
            )
        
        # Convert coordinate lists to string (handle NA)
        for col in (COL_FAM_COORDS, COL_HEX_COORDS):
            normalized[col] = (
                normalized[col]
                .fillna("[]")
                .astype(str)
            )
        
        # Convert text columns to string (handle NA)
        for col in (COL_BARCODE, COL_PATIENT_NAME):
            normalized[col] = (
                normalized[col]
                .fillna("")
                .astype(str)
            )
        
        logger.debug("Data types normalized")
        return normalized


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def load_rdml_file(file_path: str | Path) -> pd.DataFrame:
    """
    Load RDML file as DataFrame (convenience function).
    
    Args:
        file_path: Path to RDML file
        
    Returns:
        Standardized DataFrame
        
    Example:
        >>> df = load_rdml_file("data.rdml")
        >>> print(df.columns)
    """
    return RDMLService.rdml_to_dataframe(file_path)


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Service
    "RDMLService",
    
    # Convenience
    "load_rdml_file",
    
    # Constants
    "DEFAULT_COLUMNS",
    
    # Exceptions
    "RDMLServiceError",
]