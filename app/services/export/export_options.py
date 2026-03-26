# app\services\export\export_options.py
# -*- coding: utf-8 -*-
"""Export configuration options for PCR analysis data.

This module defines the data structures used to configure export operations
for PCR analysis results. It provides flexible options for controlling export
format, column selection, headers, and encoding.

The ExportOptions class is used throughout the export pipeline to ensure
consistent configuration across different export formats (Excel, TSV).

Example:
    Creating export options for different scenarios::

        from app.services.export.export_options import ExportOptions

        # Full Excel export with headers
        excel_opts = ExportOptions(
            fmt='xlsx',
            include_headers=True,
            preset='full',
            include_index=False
        )

        # Minimal TSV export with UTF-8 encoding
        tsv_opts = ExportOptions(
            fmt='tsv',
            include_headers=False,
            preset='minimal',
            tsv_encoding='utf-8'
        )

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ============================================================================
# Type Aliases
# ============================================================================

# Supported export formats
# xlsx: Microsoft Excel format (.xlsx)
# tsv: Tab-separated values format (.tsv)
ExportFormat = Literal["xlsx", "tsv"]


# ============================================================================
# Default Values
# ============================================================================

DEFAULT_FORMAT = "xlsx"
DEFAULT_PRESET = "full"
DEFAULT_INCLUDE_HEADERS = True
DEFAULT_INCLUDE_INDEX = False
DEFAULT_TSV_ENCODING = "utf-8"


# ============================================================================
# Configuration
# ============================================================================

@dataclass(frozen=True)
class ExportOptions:
    """Configuration options for exporting PCR analysis data.
    
    This immutable configuration class controls various aspects of the export process,
    including file format, column selection via presets, header inclusion, and encoding.
    
    Attributes:
        fmt: Export file format. Either 'xlsx' (Excel) or 'tsv' (tab-separated values).
            Default: 'xlsx'
        
        include_headers: Whether to include column headers in the exported file.
            Default: True
        
        preset: Name of the column preset to use for export. Presets are defined in
            app.constants.export_presets.EXPORT_PRESETS. Common presets include:
            - 'full': All available columns
            - 'minimal': Essential columns only
            - 'summary': Summary statistics and results
            Default: 'full'
        
        include_index: Whether to include DataFrame index as a column in the export.
            Useful when the index contains meaningful information (e.g., well numbers).
            Default: False
        
        tsv_encoding: Character encoding for TSV exports. Common values:
            - 'utf-8': Unicode (recommended for Turkish characters)
            - 'cp1254': Windows Turkish
            - 'iso-8859-9': Latin-5 Turkish
            Only used when fmt='tsv'. Default: 'utf-8'
    
    Note:
        This class is immutable (frozen=True) to prevent accidental modification
        during the export pipeline and to enable safe sharing across threads.
    
    Example:
        >>> opts = ExportOptions(fmt='xlsx', preset='summary')
        >>> print(opts.fmt)
        'xlsx'
        >>> opts.fmt = 'tsv'  # Raises FrozenInstanceError
    """
    fmt: ExportFormat = DEFAULT_FORMAT
    include_headers: bool = DEFAULT_INCLUDE_HEADERS
    preset: str = DEFAULT_PRESET
    include_index: bool = DEFAULT_INCLUDE_INDEX
    tsv_encoding: str = DEFAULT_TSV_ENCODING