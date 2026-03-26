# app\services\export\exporters\excel_exporter.py
# -*- coding: utf-8 -*-
"""Excel export functionality for PCR analysis data.

This module provides Excel (.xlsx) export capabilities for PCR analysis results.
It uses pandas to_excel() method with openpyxl engine for creating Excel files
with configurable headers and index inclusion.

The exporter validates input data and file paths before export to ensure
reliable file generation and clear error messages.

Example:
    Basic usage for exporting DataFrame to Excel::

        import pandas as pd
        from app.services.export.exporters.excel_exporter import ExcelExporter

        # Prepare data
        df = pd.DataFrame({
            'Kuyu No': ['A1', 'A2', 'A3'],
            'Nihai Sonuç': ['Sağlıklı', 'Taşıyıcı', 'Belirsiz'],
            'İstatistik Oranı': [0.85, 0.45, 0.65]
        })

        # Export to Excel
        exporter = ExcelExporter()
        exporter.export(
            df,
            'results.xlsx',
            include_headers=True,
            include_index=False
        )

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Expected file extension for Excel exports
EXCEL_EXTENSION = ".xlsx"

# Error messages
ERROR_EMPTY_DATAFRAME = "Export edilecek DataFrame boş"
ERROR_INVALID_EXTENSION = f"Excel export için dosya uzantısı {EXCEL_EXTENSION} olmalı"


# ============================================================================
# Exporter
# ============================================================================

class ExcelExporter:
    """Excel file exporter for PCR analysis data.
    
    This class handles exporting pandas DataFrames to Excel (.xlsx) format
    using the openpyxl engine. It provides validation for input data and
    file paths to ensure reliable export operations.
    
    The exporter uses pandas.DataFrame.to_excel() which requires the openpyxl
    library to be installed.
    """

    def export(
        self,
        df: pd.DataFrame,
        file_path: str,
        *,
        include_headers: bool,
        include_index: bool
    ) -> None:
        """Export DataFrame to Excel file.
        
        Exports the provided DataFrame to an Excel (.xlsx) file with configurable
        options for headers and index inclusion. The file is created using openpyxl
        engine with default formatting.
        
        Args:
            df: DataFrame to export. Must not be None or empty.
            file_path: Target file path for the Excel file. Must end with .xlsx extension.
            include_headers: If True, include column names as the first row.
            include_index: If True, include DataFrame index as the first column.
        
        Raises:
            ValueError: If DataFrame is None or empty, or if file_path doesn't end with .xlsx
            PermissionError: If the file path is not writable
            OSError: If there are file system issues during export
        
        Example:
            >>> df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
            >>> exporter = ExcelExporter()
            >>> exporter.export(df, 'output.xlsx', include_headers=True, include_index=False)
        
        Note:
            - Existing files at file_path will be overwritten without warning
            - The openpyxl library must be installed for this method to work
            - Default Excel formatting is applied (no custom styles)
        """
        # Validate DataFrame
        if df is None or df.empty:
            logger.error(f"{ERROR_EMPTY_DATAFRAME} (None={df is None}, empty={df.empty if df is not None else 'N/A'})")
            raise ValueError(ERROR_EMPTY_DATAFRAME)

        # Validate file extension
        if not file_path.lower().endswith(EXCEL_EXTENSION):
            logger.error(f"{ERROR_INVALID_EXTENSION}: received '{file_path}'")
            raise ValueError(ERROR_INVALID_EXTENSION)

        logger.info(
            f"Exporting DataFrame to Excel - Path: '{file_path}', "
            f"Shape: {df.shape}, Headers: {include_headers}, Index: {include_index}"
        )

        try:
            # Export to Excel using pandas
            df.to_excel(
                file_path,
                index=include_index,
                header=include_headers,
                engine='openpyxl'
            )
            
            # Verify file was created
            file_size = Path(file_path).stat().st_size
            logger.info(f"Excel export successful - File: '{file_path}', Size: {file_size} bytes")
            
        except PermissionError as e:
            logger.error(f"Permission denied writing to '{file_path}': {e}")
            raise
        except OSError as e:
            logger.error(f"File system error during Excel export to '{file_path}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Excel export to '{file_path}': {e}")
            raise