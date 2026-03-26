# app\constants\table_config.py
# app/constants/table_config.py
"""
Table and data grid configuration constants.

This module defines configuration for data tables, including:
- Column names and headers
- Dropdown options and their visual styling
- Numeric rounding precision
- Default well assignments (control samples)
- CSV export/import column mappings

Usage:
    from app.constants.table_config import TableConfig, ResultOption, ColumnName
    
    # Get dropdown options
    options = TableConfig.DROPDOWN_OPTIONS
    
    # Get color for result
    color = TableConfig.get_result_color(ResultOption.HEALTHY)
    
    # Check if column needs rounding
    if ColumnName.FAM_CT in TableConfig.ROUND_COLUMNS:
        precision = TableConfig.get_round_precision(ColumnName.FAM_CT)

Design:
    - All column names centralized to prevent typos
    - Result options typed with constants (no magic strings)
    - Color mapping validated and type-safe
    - Immutable configurations (frozen dataclasses)

Note:
    Column names are in Turkish as per domain requirements.
    Future versions may support i18n column name mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping
from typing import ClassVar
from PyQt5.QtGui import QColor


# ============================================================================
# COLUMN NAME CONSTANTS
# ============================================================================

@dataclass(frozen=True, )#slots=True
class ColumnName:
    """
    Standard column names used throughout the application.
    
    Centralizes all column name strings to prevent typos and enable
    IDE autocomplete. Used for table headers, CSV mapping, and DataFrame
    column access.
    
    Categories:
    - Identification: Patient/sample identifiers
    - Measurements: Raw Ct values
    - Analysis: Calculated metrics
    - Results: Final interpretations
    - Quality: Warnings and flags
    - Metadata: Coordinates and technical data
    """
    
    # ========================================================================
    # IDENTIFICATION
    # ========================================================================
    
    REACT_ID: Final[str] = "React ID"
    """Reaction identifier"""
    
    PATIENT_ID: Final[str] = "Hasta No"
    """Patient number/identifier"""
    
    PATIENT_NAME: Final[str] = "Hasta Adı"
    """Patient full name"""
    
    BARCODE: Final[str] = "Barkot No"
    """Sample barcode number"""
    
    WELL_ID: Final[str] = "Kuyu No"
    """PCR plate well identifier (e.g., A1, B2)"""
    
    # ========================================================================
    # MEASUREMENTS (Raw Ct Values)
    # ========================================================================
    
    FAM_CT: Final[str] = "FAM Ct"
    """FAM channel cycle threshold"""
    
    HEX_CT: Final[str] = "HEX Ct"
    """HEX channel cycle threshold"""
    
    DELTA_CT: Final[str] = "Δ Ct"
    """Delta Ct (ΔCt) - target vs reference difference"""
    
    DELTA_DELTA_CT: Final[str] = "Δ_Δ Ct"
    """Delta-delta Ct (ΔΔCt) - relative quantification"""
    
    # ========================================================================
    # ANALYSIS RESULTS
    # ========================================================================
    
    STATISTICAL_RATIO: Final[str] = "İstatistik Oranı"
    """Statistical analysis ratio (software algorithm result)"""
    
    STANDARD_RATIO: Final[str] = "Standart Oranı"
    """Standard ratio (reference method result)"""
    
    REGRESSION: Final[str] = "Regresyon"
    """Regression analysis result"""
    
    # ========================================================================
    # FINAL RESULTS
    # ========================================================================
    
    SOFTWARE_RESULT: Final[str] = "Yazılım Hasta Sonucu"
    """Software-calculated patient result"""
    
    REFERENCE_RESULT: Final[str] = "Referans Hasta Sonucu"
    """Reference method patient result"""
    
    FINAL_RESULT: Final[str] = "Nihai Sonuç"
    """Final clinical interpretation (user-editable dropdown)"""
    
    # ========================================================================
    # QUALITY CONTROL
    # ========================================================================
    
    WARNING: Final[str] = "Uyarı"
    """Quality control warning flag"""
    
    # ========================================================================
    # TECHNICAL METADATA
    # ========================================================================
    
    RFU_DIFF: Final[str] = "rfu_diff"
    """RFU (Relative Fluorescence Unit) difference"""
    
    FAM_END_RFU: Final[str] = "fam_end_rfu"
    """FAM channel end-point RFU"""
    
    HEX_END_RFU: Final[str] = "hex_end_rfu"
    """HEX channel end-point RFU"""
    
    FAM_COORDS: Final[str] = "FAM koordinat list"
    """FAM channel coordinate list (full curve data)"""
    
    HEX_COORDS: Final[str] = "HEX koordinat list"
    """HEX channel coordinate list (full curve data)"""


# ============================================================================
# RESULT OPTION CONSTANTS
# ============================================================================

class ResultOption:
    """
    Dropdown result option identifiers.
    
    Use these constants instead of string literals:
        if result == ResultOption.HEALTHY:
        # Better than: if result == "Sağlıklı"
    
    Prevents typos and enables IDE autocomplete.
    """
    
    HEALTHY: Final[str] = "Sağlıklı"
    """Healthy/normal genotype"""
    
    CARRIER: Final[str] = "Taşıyıcı"
    """Carrier/heterozygous genotype"""
    
    UNCERTAIN: Final[str] = "Belirsiz"
    """Uncertain/ambiguous result"""
    
    REPEAT_TEST: Final[str] = "Test Tekrarı"
    """Test repeat required"""
    
    NEW_SAMPLE: Final[str] = "Yeni Numune"
    """New sample required"""


# ============================================================================
# CONTROL WELL IDENTIFIERS
# ============================================================================

class ControlWellType:
    """
    Control well type identifiers.
    
    Used for default well assignment configuration.
    """
    
    HOMOZYGOUS: Final[str] = "homozigot_kontrol"
    """Homozygous control well"""
    
    HETEROZYGOUS: Final[str] = "hoterozigot_kontrol"
    """Heterozygous control well"""
    
    NTC: Final[str] = "ntc_kontrol"
    """No Template Control (NTC) well"""


# ============================================================================
# RESULT COLOR MAPPING
# ============================================================================

# Immutable color mapping for result options
_RESULT_COLORS: Final[Mapping[str, QColor]] = {
    ResultOption.HEALTHY: QColor("#81B563"),       # Green - healthy/normal
    ResultOption.CARRIER: QColor("#FFE599"),       # Yellow - carrier warning
    ResultOption.UNCERTAIN: QColor("#E87E2C"),     # Orange - uncertain/review
    ResultOption.REPEAT_TEST: QColor("#B4A7D6"),   # Purple - repeat required
    ResultOption.NEW_SAMPLE: QColor("#FF6B6B"),    # Red - new sample needed
}


# ============================================================================
# ROUNDING PRECISION CONFIGURATION
# ============================================================================

# Immutable rounding precision mapping
_ROUND_COLUMNS: Final[Mapping[str, int]] = {
    ColumnName.FAM_CT: 2,             # 2 decimal places for Ct values
    ColumnName.HEX_CT: 2,
    ColumnName.DELTA_CT: 2,
    ColumnName.STATISTICAL_RATIO: 4,  # 4 decimal places for ratios (higher precision)
    ColumnName.STANDARD_RATIO: 4,
}


# ============================================================================
# CSV COLUMN ORDER
# ============================================================================

# Complete CSV column order (for export/import)
_CSV_FILE_HEADERS: Final[tuple[str, ...]] = (
    ColumnName.REACT_ID,
    ColumnName.BARCODE,
    ColumnName.PATIENT_NAME,
    ColumnName.WARNING,
    ColumnName.WELL_ID,
    ColumnName.PATIENT_ID,
    ColumnName.STATISTICAL_RATIO,
    ColumnName.SOFTWARE_RESULT,
    ColumnName.FINAL_RESULT,
    ColumnName.STANDARD_RATIO,
    ColumnName.REFERENCE_RESULT,
    ColumnName.REGRESSION,
    ColumnName.FAM_CT,
    ColumnName.HEX_CT,
    ColumnName.DELTA_CT,
    ColumnName.DELTA_DELTA_CT,
    ColumnName.RFU_DIFF,
    ColumnName.FAM_END_RFU,
    ColumnName.HEX_END_RFU,
    ColumnName.FAM_COORDS,
    ColumnName.HEX_COORDS,
)


# ============================================================================
# TABLE WIDGET COLUMN ORDER
# ============================================================================

# Visible columns in UI table (user-facing subset)
_TABLE_WIDGET_HEADERS: Final[tuple[str, ...]] = (
    ColumnName.PATIENT_ID,
    ColumnName.WELL_ID,
    ColumnName.BARCODE,
    ColumnName.WARNING,
    ColumnName.PATIENT_NAME,
    ColumnName.DELTA_CT,
    ColumnName.REGRESSION,
    ColumnName.STATISTICAL_RATIO,
    ColumnName.STANDARD_RATIO,
    ColumnName.FINAL_RESULT,
)


# ============================================================================
# DEFAULT CONTROL WELL ASSIGNMENTS
# ============================================================================

# Default well positions for control samples
_DEFAULT_WELL_VALUES: Final[Mapping[str, str]] = {
    ControlWellType.HOMOZYGOUS: "F12",    # Homozygous control well
    ControlWellType.HETEROZYGOUS: "G12",  # Heterozygous control well
    ControlWellType.NTC: "H12",           # No Template Control well
}


# ============================================================================
# TABLE CONFIGURATION CLASS
# ============================================================================

@dataclass(frozen=True, )#slots=True
class TableConfig:
    """
    Table and data grid configuration manager.
    
    Provides centralized access to table configuration including:
    - Column names and ordering
    - Dropdown options and colors
    - Rounding precision
    - Control well assignments
    
    All configurations are immutable and validated.
    """
    
    # ========================================================================
    # DROPDOWN CONFIGURATION
    # ========================================================================
    
    DROPDOWN_COLUMN: ClassVar[str] = ColumnName.FINAL_RESULT
    """Column name for editable dropdown (Final Result)"""
    
    DROPDOWN_OPTIONS: ClassVar[tuple[str, ...]] = (
        ResultOption.HEALTHY,
        ResultOption.CARRIER,
        ResultOption.UNCERTAIN,
        ResultOption.REPEAT_TEST,
        ResultOption.NEW_SAMPLE,
    )
    """Available options in result dropdown (ordered)"""
    
    # ========================================================================
    # COLUMN CONFIGURATIONS
    # ========================================================================
    
    CSV_FILE_HEADERS: ClassVar[tuple[str, ...]] = _CSV_FILE_HEADERS
    """Complete CSV column order for export/import"""
    
    TABLE_WIDGET_HEADERS: ClassVar[tuple[str, ...]] = _TABLE_WIDGET_HEADERS
    """Visible columns in UI table widget"""
    
    ROUND_COLUMNS: ClassVar[Mapping[str, int]] = _ROUND_COLUMNS
    """Columns requiring numeric rounding with precision"""
    
    # ========================================================================
    # CONTROL WELL DEFAULTS
    # ========================================================================
    
    DEFAULT_WELL_VALUES: ClassVar[Mapping[str, str]] = _DEFAULT_WELL_VALUES
    """Default well assignments for control samples"""
    
    # ========================================================================
    # LEGACY COLUMN ALIASES
    # ========================================================================
    
    COLUMN_SOFTWARE_RESULT: ClassVar[str] = ColumnName.STATISTICAL_RATIO
    """Deprecated: Use ColumnName.STATISTICAL_RATIO instead"""
    
    COLUMN_REFERENCE_RESULT: ClassVar[str] = ColumnName.STANDARD_RATIO
    """Deprecated: Use ColumnName.STANDARD_RATIO instead"""
    
    COLUMN_WARNING: ClassVar[str] = ColumnName.WARNING
    """Deprecated: Use ColumnName.WARNING instead"""
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    @staticmethod
    def get_result_color(result: str) -> QColor | None:
        """
        Get QColor for a result option.
        
        Args:
            result: Result option (use ResultOption constants)
            
        Returns:
            QColor for the result, or None if not found
            
        Example:
            >>> color = TableConfig.get_result_color(ResultOption.HEALTHY)
            >>> color.name()
            '#81b563'
        """
        return _RESULT_COLORS.get(result)
    
    @staticmethod
    def get_round_precision(column: str) -> int | None:
        """
        Get rounding precision for a column.
        
        Args:
            column: Column name (use ColumnName constants)
            
        Returns:
            Number of decimal places, or None if no rounding configured
            
        Example:
            >>> TableConfig.get_round_precision(ColumnName.FAM_CT)
            2
            >>> TableConfig.get_round_precision(ColumnName.PATIENT_NAME)
            None
        """
        return _ROUND_COLUMNS.get(column)
    
    @staticmethod
    def should_round_column(column: str) -> bool:
        """
        Check if a column requires rounding.
        
        Args:
            column: Column name to check
            
        Returns:
            True if column should be rounded, False otherwise
            
        Example:
            >>> TableConfig.should_round_column(ColumnName.FAM_CT)
            True
            >>> TableConfig.should_round_column(ColumnName.PATIENT_NAME)
            False
        """
        return column in _ROUND_COLUMNS
    
    @staticmethod
    def get_control_well(control_type: str) -> str | None:
        """
        Get default well position for a control type.
        
        Args:
            control_type: Control type (use ControlWellType constants)
            
        Returns:
            Well position string (e.g., "F12"), or None if not configured
            
        Example:
            >>> TableConfig.get_control_well(ControlWellType.NTC)
            'H12'
        """
        return _DEFAULT_WELL_VALUES.get(control_type)
    
    @staticmethod
    def validate_result_option(result: str) -> bool:
        """
        Check if a result option is valid.
        
        Args:
            result: Result string to validate
            
        Returns:
            True if result is in DROPDOWN_OPTIONS, False otherwise
            
        Example:
            >>> TableConfig.validate_result_option(ResultOption.HEALTHY)
            True
            >>> TableConfig.validate_result_option("Invalid")
            False
        """
        return result in TableConfig.DROPDOWN_OPTIONS


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

# Deprecated: Direct access to constants
# Use TableConfig.* instead
DROPDOWN_COLUMN = TableConfig.DROPDOWN_COLUMN
DROPDOWN_OPTIONS = list(TableConfig.DROPDOWN_OPTIONS)
ITEM_STYLES = dict(_RESULT_COLORS)
ROUND_COLUMNS = dict(_ROUND_COLUMNS)
CSV_FILE_HEADERS = list(_CSV_FILE_HEADERS)
TABLE_WIDGET_HEADERS = list(_TABLE_WIDGET_HEADERS)
DEFAULT_WELL_VALUES = dict(_DEFAULT_WELL_VALUES)
COLUMN_SOFTWARE_RESULT = TableConfig.COLUMN_SOFTWARE_RESULT
COLUMN_REFERENCE_RESULT = TableConfig.COLUMN_REFERENCE_RESULT
COLUMN_WARNING = TableConfig.COLUMN_WARNING


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Recommended API
    "TableConfig",
    "ColumnName",
    "ResultOption",
    "ControlWellType",
    
    # Backward compatibility (deprecated)
    "DROPDOWN_COLUMN",
    "DROPDOWN_OPTIONS",
    "ITEM_STYLES",
    "ROUND_COLUMNS",
    "CSV_FILE_HEADERS",
    "TABLE_WIDGET_HEADERS",
    "DEFAULT_WELL_VALUES",
    "COLUMN_SOFTWARE_RESULT",
    "COLUMN_REFERENCE_RESULT",
    "COLUMN_WARNING",
]