# app\services\export\export_service.py
# -*- coding: utf-8 -*-
"""Main export service orchestrating PCR analysis data exports.

This module provides a unified interface for exporting PCR analysis results to
various file formats (Excel, TSV). It coordinates between format-specific exporters
and applies column presets to customize the export output.

The service architecture follows a strategy pattern where format-specific exporters
handle the low-level export mechanics while this service manages:
- Preset application and validation
- Format routing
- High-level error handling and logging
- DataFrame validation

Example:
    Basic usage for exporting analysis results::

        import pandas as pd
        from app.services.export.export_service import ExportService
        from app.services.export.export_options import ExportOptions

        # Prepare analysis results
        df = pd.DataFrame({
            'Kuyu No': ['A1', 'A2', 'A3'],
            'Nihai Sonuç': ['Sağlıklı', 'Taşıyıcı', 'Belirsiz'],
            'İstatistik Oranı': [0.85, 0.45, 0.65],
            'FAM Ct': [25.3, 28.1, 26.7],
            'HEX Ct': [24.8, 27.5, 26.2]
        })

        # Configure export
        options = ExportOptions(
            fmt='xlsx',
            preset='report_v1',
            include_headers=True,
            include_index=False
        )

        # Export
        service = ExportService()
        service.export_dataframe(df, 'results.xlsx', options)

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

import pandas as pd

from app.constants.export_presets import EXPORT_PRESETS
from app.services.export.export_options import ExportOptions
from app.services.export.exporters.excel_exporter import ExcelExporter
from app.services.export.exporters.tsv_exporter import TSVExporter

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Error messages
ERROR_EMPTY_DATAFRAME = "Export edilecek DataFrame boş"
ERROR_UNKNOWN_PRESET = "Bilinmeyen export preset"
ERROR_NO_COLUMNS_FOUND = "Preset için DataFrame'de hiçbir kolon bulunamadı"
ERROR_UNSUPPORTED_FORMAT = "Desteklenmeyen export formatı"

# Supported export formats
FORMAT_EXCEL = "xlsx"
FORMAT_TSV = "tsv"


# ============================================================================
# Service
# ============================================================================

class ExportService:
    """Main service for exporting PCR analysis data to files.
    
    This service orchestrates the export process by:
    1. Validating input DataFrame and options
    2. Applying column presets to filter/reorder columns
    3. Routing to format-specific exporters (Excel or TSV)
    4. Handling errors and logging throughout the process
    
    The service maintains instances of format-specific exporters and reuses
    them across multiple export operations for efficiency.
    
    Attributes:
        _excel: Excel exporter instance for .xlsx format
        _tsv: TSV exporter instance for .tsv format
    """

    def __init__(self):
        """Initialize export service with format-specific exporters.
        
        Creates and caches exporter instances for reuse across multiple
        export operations. This avoids repeated initialization overhead.
        """
        self._excel = ExcelExporter()
        self._tsv = TSVExporter()
        logger.debug("ExportService initialized with Excel and TSV exporters")

    def export_dataframe(
        self,
        df: pd.DataFrame,
        file_path: str,
        options: ExportOptions
    ) -> None:
        """Export DataFrame to file with specified format and options.
        
        This is the main entry point for all export operations. It validates
        inputs, applies column presets, and routes to the appropriate format
        exporter based on the options.
        
        Args:
            df: DataFrame containing PCR analysis results to export.
                Must not be None or empty.
            file_path: Target file path for export. Extension should match
                the format specified in options (.xlsx for Excel, .tsv for TSV).
            options: Export configuration specifying format, preset, headers,
                index inclusion, and encoding options.
        
        Raises:
            ValueError: If DataFrame is None/empty, preset is unknown, or
                format is unsupported
            FileNotFoundError: If the directory path doesn't exist
            PermissionError: If file path is not writable
            OSError: For other file system errors during export
        
        Example:
            >>> df = pd.DataFrame({'Kuyu No': ['A1'], 'Sonuç': ['Sağlıklı']})
            >>> opts = ExportOptions(fmt='xlsx', preset='full')
            >>> service = ExportService()
            >>> service.export_dataframe(df, 'output.xlsx', opts)
        
        Note:
            - Existing files will be overwritten without warning
            - Column order in output matches preset definition or DataFrame order
            - Missing preset columns are silently skipped (robust behavior)
        """
        # Validate DataFrame
        if df is None or df.empty:
            logger.error(
                f"{ERROR_EMPTY_DATAFRAME} - "
                f"None={df is None}, Empty={df.empty if df is not None else 'N/A'}"
            )
            raise ValueError(ERROR_EMPTY_DATAFRAME)

        logger.info(
            f"Starting export - Format: {options.fmt}, Preset: {options.preset}, "
            f"File: '{file_path}', DataFrame shape: {df.shape}"
        )

        # Apply preset to filter/reorder columns
        filtered_df = self._apply_preset(df, options.preset)
        
        logger.debug(
            f"Preset applied - Original columns: {len(df.columns)}, "
            f"Filtered columns: {len(filtered_df.columns)}"
        )

        # Route to appropriate exporter based on format
        if options.fmt == FORMAT_EXCEL:
            self._export_excel(filtered_df, file_path, options)
            return

        if options.fmt == FORMAT_TSV:
            self._export_tsv(filtered_df, file_path, options)
            return

        # Unsupported format
        logger.error(f"{ERROR_UNSUPPORTED_FORMAT}: '{options.fmt}'")
        raise ValueError(f"{ERROR_UNSUPPORTED_FORMAT}: {options.fmt}")

    def _export_excel(
        self,
        df: pd.DataFrame,
        file_path: str,
        options: ExportOptions
    ) -> None:
        """Export DataFrame to Excel format.
        
        Internal method that delegates to ExcelExporter with appropriate options.
        
        Args:
            df: Filtered DataFrame ready for export
            file_path: Target Excel file path (.xlsx)
            options: Export options containing header/index flags
        """
        logger.debug(f"Routing to Excel exporter for '{file_path}'")
        self._excel.export(
            df,
            file_path,
            include_headers=options.include_headers,
            include_index=options.include_index
        )

    def _export_tsv(
        self,
        df: pd.DataFrame,
        file_path: str,
        options: ExportOptions
    ) -> None:
        """Export DataFrame to TSV format.
        
        Internal method that delegates to TSVExporter with appropriate options
        including encoding configuration.
        
        Args:
            df: Filtered DataFrame ready for export
            file_path: Target TSV file path (.tsv)
            options: Export options containing header/index/encoding flags
        """
        logger.debug(
            f"Routing to TSV exporter for '{file_path}' "
            f"with encoding '{options.tsv_encoding}'"
        )
        self._tsv.export(
            df,
            file_path,
            include_headers=options.include_headers,
            include_index=options.include_index,
            encoding=options.tsv_encoding
        )

    def _apply_preset(self, df: pd.DataFrame, preset: str) -> pd.DataFrame:
        """Apply column preset to filter and reorder DataFrame columns.
        
        This method filters the DataFrame to include only columns specified
        in the preset configuration. It handles missing columns gracefully
        by including only columns that exist in both the preset and DataFrame.
        
        Args:
            df: Source DataFrame with all available columns
            preset: Preset name from EXPORT_PRESETS configuration
        
        Returns:
            New DataFrame containing only preset columns that exist in source.
            For 'full' preset (None value), returns copy of entire DataFrame.
        
        Raises:
            ValueError: If preset is not defined or if no preset columns
                exist in the DataFrame
        
        Example:
            >>> df = pd.DataFrame({'A': [1], 'B': [2], 'C': [3]})
            >>> # Preset defines columns ['A', 'C', 'D']
            >>> filtered = service._apply_preset(df, 'my_preset')
            >>> list(filtered.columns)
            ['A', 'C']  # 'D' missing, silently skipped
        
        Note:
            - Column order in output matches preset definition
            - Missing columns are logged at DEBUG level but don't raise errors
            - Original DataFrame is never modified (returns copy)
        """
        # Validate preset exists
        if preset not in EXPORT_PRESETS:
            logger.error(f"{ERROR_UNKNOWN_PRESET}: '{preset}'")
            raise ValueError(f"{ERROR_UNKNOWN_PRESET}: {preset}")

        preset_columns = EXPORT_PRESETS[preset]
        
        # 'full' preset: return all columns
        if preset_columns is None:
            logger.debug(f"Preset '{preset}' is 'full' - using all {len(df.columns)} columns")
            return df.copy()

        # Filter to existing columns only (robust to schema changes)
        existing_columns = [col for col in preset_columns if col in df.columns]
        
        # Log missing columns for debugging
        missing_columns = [col for col in preset_columns if col not in df.columns]
        if missing_columns:
            logger.debug(
                f"Preset '{preset}' - Missing columns (skipped): {missing_columns}"
            )
        
        # Validate at least one column exists
        if not existing_columns:
            logger.error(
                f"{ERROR_NO_COLUMNS_FOUND}: '{preset}'. "
                f"Preset columns: {preset_columns}, "
                f"Available columns: {list(df.columns)}"
            )
            raise ValueError(f"{ERROR_NO_COLUMNS_FOUND}: {preset}")

        logger.debug(
            f"Preset '{preset}' - Using {len(existing_columns)}/{len(preset_columns)} columns"
        )
        
        # Return filtered and reordered DataFrame
        return df[existing_columns].copy()