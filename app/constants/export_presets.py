# app\constants\export_presets.py
# app/constants/export_presets.py
"""
Export column presets for data export functionality.

This module defines predefined column configurations for exporting analysis
results to various formats (Excel, TSV). Presets allow users to quickly
select common export layouts without manually configuring columns each time.

Usage:
    from app.constants.export_presets import ExportPresets, PresetName
    
    # Get preset columns
    columns = ExportPresets.get_preset(PresetName.REPORT_V1)
    if columns is None:
        columns = df.columns.tolist()  # Use all columns
    
    # Validate preset
    if ExportPresets.validate_preset(PresetName.REPORT_V1, available_columns):
        export_with_preset(preset_name)
    
    # Get all preset names
    preset_names = ExportPresets.get_preset_names()

Preset Types:
    - "full": Export all available columns (None = auto-detect)
    - "report_v1": Standard clinical report layout with key metrics

Note:
    Column names are in Turkish as per application requirements.
    Future versions may support i18n column name mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping


# ============================================================================
# COLUMN NAME CONSTANTS
# ============================================================================

@dataclass(frozen=True, slots=True)
class ColumnNames:
    """
    Standard column names used in export presets.
    
    Centralizes column name strings to prevent typos and enable
    refactoring. All names are in Turkish as per domain requirements.
    
    Categories:
    - Patient info: Demographic and identification data
    - Measurements: Raw PCR cycle threshold (Ct) values
    - Analysis: Calculated metrics and results
    - Quality: Warnings and validation flags
    """
    
    # ========================================================================
    # PATIENT INFORMATION
    # ========================================================================
    
    PATIENT_ID: Final[str] = "Hasta No"
    """Patient identifier number"""
    
    PATIENT_NAME: Final[str] = "Hasta Adı"
    """Patient full name"""
    
    BARCODE_ID: Final[str] = "Barkot No"
    """Sample barcode number"""
    
    # ========================================================================
    # WARNINGS & FLAGS
    # ========================================================================
    
    WARNING: Final[str] = "Uyarı"
    """Quality control warning flag"""
    
    # ========================================================================
    # RAW MEASUREMENTS (Ct Values)
    # ========================================================================
    
    FAM_CT: Final[str] = "FAM Ct"
    """FAM channel cycle threshold value"""
    
    HEX_CT: Final[str] = "HEX Ct"
    """HEX channel cycle threshold value"""
    
    # ========================================================================
    # CALCULATED METRICS
    # ========================================================================
    
    DELTA_CT: Final[str] = "Δ Ct"
    """Delta Ct (ΔCt) - difference between target and reference"""
    
    REGRESSION: Final[str] = "Regresyon"
    """Regression analysis result"""
    
    STATISTICAL_RATIO: Final[str] = "İstatistik Oranı"
    """Statistical ratio calculation"""
    
    STANDARD_RATIO: Final[str] = "Standart Oranı"
    """Standard ratio calculation"""
    
    # ========================================================================
    # FINAL RESULTS
    # ========================================================================
    
    FINAL_RESULT: Final[str] = "Nihai Sonuç"
    """Final clinical interpretation/result"""


# ============================================================================
# PRESET DEFINITIONS
# ============================================================================

class PresetName:
    """
    Preset identifier constants.
    
    Use these constants instead of string literals to prevent typos:
        preset = ExportPresets.get_preset(PresetName.REPORT_V1)
        # Better than: preset = ExportPresets.get_preset("report_v1")
    """
    
    FULL: Final[str] = "full"
    """Export all available columns (no filtering)"""
    
    REPORT_V1: Final[str] = "report_v1"
    """Standard clinical report layout (v1)"""


# Preset configuration (immutable after module load)
_EXPORT_PRESETS: Final[Mapping[str, list[str] | None]] = {
    PresetName.FULL: None,  # None = use all columns from DataFrame
    
    PresetName.REPORT_V1: [
        # Patient identification
        ColumnNames.PATIENT_ID,
        ColumnNames.PATIENT_NAME,
        ColumnNames.BARCODE_ID,
        
        # Quality control
        ColumnNames.WARNING,
        
        # Raw measurements
        ColumnNames.FAM_CT,
        ColumnNames.HEX_CT,
        
        # Calculated metrics
        ColumnNames.DELTA_CT,
        ColumnNames.REGRESSION,
        ColumnNames.STATISTICAL_RATIO,
        ColumnNames.STANDARD_RATIO,
        
        # Final output
        ColumnNames.FINAL_RESULT,
    ],
}


# ============================================================================
# PRESET ACCESSOR & UTILITIES
# ============================================================================

class ExportPresets:
    """
    Export preset manager with validation utilities.
    
    Provides access to predefined column configurations and validation
    methods to ensure preset integrity before export operations.
    """
    
    @staticmethod
    def get_preset(preset_name: str) -> list[str] | None:
        """
        Get column list for a preset.
        
        Args:
            preset_name: Preset identifier (use PresetName constants)
            
        Returns:
            List of column names to export, or None for "full" preset
            
        Raises:
            KeyError: If preset_name is not defined
            
        Example:
            >>> columns = ExportPresets.get_preset(PresetName.REPORT_V1)
            >>> print(columns[0])
            'Hasta No'
            
            >>> full_columns = ExportPresets.get_preset(PresetName.FULL)
            >>> print(full_columns)
            None
        """
        return _EXPORT_PRESETS[preset_name]
    
    @staticmethod
    def get_preset_names() -> list[str]:
        """
        Get all available preset names.
        
        Returns:
            List of preset identifiers
            
        Example:
            >>> names = ExportPresets.get_preset_names()
            >>> print(names)
            ['full', 'report_v1']
        """
        return list(_EXPORT_PRESETS.keys())
    
    @staticmethod
    def preset_exists(preset_name: str) -> bool:
        """
        Check if preset is defined.
        
        Args:
            preset_name: Preset identifier to check
            
        Returns:
            True if preset exists, False otherwise
            
        Example:
            >>> ExportPresets.preset_exists(PresetName.REPORT_V1)
            True
            >>> ExportPresets.preset_exists("invalid_preset")
            False
        """
        return preset_name in _EXPORT_PRESETS
    
    @staticmethod
    def validate_preset(
        preset_name: str,
        available_columns: list[str] | set[str],
    ) -> tuple[bool, list[str]]:
        """
        Validate that preset columns exist in available data.
        
        Args:
            preset_name: Preset to validate
            available_columns: Columns present in the DataFrame/data source
            
        Returns:
            Tuple of (is_valid, missing_columns)
            - is_valid: True if all preset columns are available
            - missing_columns: List of columns in preset but not in data
            
        Example:
            >>> df_columns = ["Hasta No", "FAM Ct", "HEX Ct", ...]
            >>> valid, missing = ExportPresets.validate_preset(
            ...     PresetName.REPORT_V1,
            ...     df_columns
            ... )
            >>> if not valid:
            ...     print(f"Missing columns: {missing}")
        """
        preset_columns = ExportPresets.get_preset(preset_name)
        
        # "full" preset is always valid (uses all available columns)
        if preset_columns is None:
            return (True, [])
        
        available_set = set(available_columns)
        missing = [col for col in preset_columns if col not in available_set]
        
        return (len(missing) == 0, missing)
    
    @staticmethod
    def get_available_columns(
        preset_name: str,
        available_columns: list[str],
    ) -> list[str]:
        """
        Get intersection of preset columns and available columns.
        
        Useful when you want to export as many preset columns as possible,
        skipping those that don't exist in the data.
        
        Args:
            preset_name: Preset identifier
            available_columns: Columns present in DataFrame
            
        Returns:
            List of columns that exist in both preset and data.
            For "full" preset, returns available_columns unchanged.
            
        Example:
            >>> df_columns = ["Hasta No", "FAM Ct"]  # Missing some columns
            >>> exportable = ExportPresets.get_available_columns(
            ...     PresetName.REPORT_V1,
            ...     df_columns
            ... )
            >>> print(exportable)
            ['Hasta No', 'FAM Ct']  # Only common columns
        """
        preset_columns = ExportPresets.get_preset(preset_name)
        
        if preset_columns is None:
            return available_columns
        
        available_set = set(available_columns)
        return [col for col in preset_columns if col in available_set]


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

# Deprecated: Direct access to preset dict
# Use ExportPresets.get_preset() instead
EXPORT_PRESETS = _EXPORT_PRESETS


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Recommended API
    "ExportPresets",
    "PresetName",
    "ColumnNames",
    
    # Backward compatibility
    "EXPORT_PRESETS",
]