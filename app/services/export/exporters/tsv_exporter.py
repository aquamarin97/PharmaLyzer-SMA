# app\services\export\exporters\tsv_exporter.py
# -*- coding: utf-8 -*-
"""TSV (Tab-Separated Values) export functionality for PCR analysis data.

This module provides TSV export capabilities for PCR analysis results.
It uses pandas to_csv() method with tab delimiter to create text files
that can be opened in Excel, text editors, or imported into other systems.

TSV format is particularly useful for:
- Cross-platform data exchange
- Version control systems (Git-friendly text format)
- Import into statistical software (R, Python, MATLAB)
- Custom encoding support (especially for Turkish characters)

Example:
    Basic usage for exporting DataFrame to TSV::

        import pandas as pd
        from app.services.export.exporters.tsv_exporter import TSVExporter

        # Prepare data with Turkish characters
        df = pd.DataFrame({
            'Kuyu No': ['A1', 'A2', 'A3'],
            'Nihai Sonuç': ['Sağlıklı', 'Taşıyıcı', 'Belirsiz'],
            'İstatistik Oranı': [0.85, 0.45, 0.65]
        })

        # Export to TSV with UTF-8 encoding
        exporter = TSVExporter()
        exporter.export(
            df,
            'results.tsv',
            include_headers=True,
            include_index=False,
            encoding='utf-8'
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

# Expected file extension for TSV exports
TSV_EXTENSION = ".tsv"

# Tab character used as delimiter
TAB_DELIMITER = "\t"

# Common encodings for Turkish text
# utf-8: Universal Unicode encoding (recommended)
# cp1254: Windows Turkish code page
# iso-8859-9: Latin-5 Turkish encoding
ENCODING_UTF8 = "utf-8"
ENCODING_WINDOWS_TURKISH = "cp1254"
ENCODING_LATIN5 = "iso-8859-9"

# Error messages
ERROR_EMPTY_DATAFRAME = "Export edilecek DataFrame boş"
ERROR_INVALID_EXTENSION = f"TSV export için dosya uzantısı {TSV_EXTENSION} olmalı"


# ============================================================================
# Exporter
# ============================================================================

class TSVExporter:
    """TSV (Tab-Separated Values) file exporter for PCR analysis data.
    
    This class handles exporting pandas DataFrames to TSV format using tab
    characters as field delimiters. It provides configurable encoding support
    for proper handling of Turkish characters and other Unicode text.
    
    TSV format advantages:
    - Human-readable plain text
    - Git-friendly for version control
    - Easy to import into statistical software
    - Smaller file size than Excel
    - Cross-platform compatibility
    
    The exporter uses pandas.DataFrame.to_csv() with tab delimiter.
    """

    def export(
        self,
        df: pd.DataFrame,
        file_path: str,
        *,
        include_headers: bool,
        include_index: bool,
        encoding: str
    ) -> None:
        """Export DataFrame to TSV file.
        
        Exports the provided DataFrame to a tab-separated values file with
        configurable encoding to ensure proper character handling, especially
        for Turkish characters (ş, ğ, ı, ö, ü, ç).
        
        Args:
            df: DataFrame to export. Must not be None or empty.
            file_path: Target file path for the TSV file. Must end with .tsv extension.
            include_headers: If True, include column names as the first row.
            include_index: If True, include DataFrame index as the first column.
            encoding: Character encoding for the file. Common options:
                - 'utf-8': Unicode (recommended, supports all characters)
                - 'cp1254': Windows Turkish code page
                - 'iso-8859-9': Latin-5 Turkish encoding
        
        Raises:
            ValueError: If DataFrame is None or empty, or if file_path doesn't end with .tsv
            UnicodeEncodeError: If encoding cannot represent all characters in DataFrame
            PermissionError: If the file path is not writable
            OSError: If there are file system issues during export
        
        Example:
            >>> df = pd.DataFrame({'Sonuç': ['Sağlıklı', 'Taşıyıcı']})
            >>> exporter = TSVExporter()
            >>> exporter.export(df, 'output.tsv', 
            ...                 include_headers=True, 
            ...                 include_index=False,
            ...                 encoding='utf-8')
        
        Note:
            - Existing files at file_path will be overwritten without warning
            - Tab character (\\t) is used as field delimiter
            - Line endings are platform-specific (\\n on Unix, \\r\\n on Windows)
        """
        # Validate DataFrame
        if df is None or df.empty:
            logger.error(f"{ERROR_EMPTY_DATAFRAME} (None={df is None}, empty={df.empty if df is not None else 'N/A'})")
            raise ValueError(ERROR_EMPTY_DATAFRAME)

        # Validate file extension
        if not file_path.lower().endswith(TSV_EXTENSION):
            logger.error(f"{ERROR_INVALID_EXTENSION}: received '{file_path}'")
            raise ValueError(ERROR_INVALID_EXTENSION)

        logger.info(
            f"Exporting DataFrame to TSV - Path: '{file_path}', "
            f"Shape: {df.shape}, Headers: {include_headers}, Index: {include_index}, "
            f"Encoding: {encoding}"
        )

        try:
            # Export to TSV using pandas to_csv with tab delimiter
            df.to_csv(
                file_path,
                sep=TAB_DELIMITER,
                index=include_index,
                header=include_headers,
                encoding=encoding
            )
            
            # Verify file was created
            file_size = Path(file_path).stat().st_size
            logger.info(f"TSV export successful - File: '{file_path}', Size: {file_size} bytes")
            
        except UnicodeEncodeError as e:
            logger.error(
                f"Character encoding error with '{encoding}' for file '{file_path}': {e}. "
                f"Try using 'utf-8' encoding for full Unicode support."
            )
            raise
        except PermissionError as e:
            logger.error(f"Permission denied writing to '{file_path}': {e}")
            raise
        except OSError as e:
            logger.error(f"File system error during TSV export to '{file_path}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during TSV export to '{file_path}': {e}")
            raise