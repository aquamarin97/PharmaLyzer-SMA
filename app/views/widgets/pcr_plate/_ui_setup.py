# app\views\widgets\pcr_plate\_ui_setup.py
# -*- coding: utf-8 -*-
"""
PCR Plate UI Setup Utilities.

This module provides initialization functions for PCR plate table widget:
- Header configuration (horizontal/vertical)
- Grid initialization with colors and patient numbers
- Column resizing with safety checks

Performance optimizations:
- Batch header configuration (minimize layout recalculations)
- Deferred resize operations
- Single-pass grid setup
- Efficient section resize mode setting

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import pandas as pd
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtGui import QColor
from app.utils import well_mapping
from app.views.widgets.pcr_plate.setup.grid_setup import initialize_grid
from app.views.widgets.pcr_plate.setup.resizing import resize_columns_to_fit

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QTableWidget

logger = logging.getLogger(__name__)


def configure_headers(
    table: QTableWidget,
    min_col_width: int,
    row_height: int,
) -> None:
    """
    Configure table headers with fixed sizing policies.

    Sets both horizontal and vertical headers to Fixed resize mode with
    specified minimum dimensions.

    Args:
        table: QTableWidget to configure
        min_col_width: Minimum column width (pixels)
        row_height: Fixed row height (pixels)

    Performance: Two header configuration calls, efficient batch setup
    """
    if table is None:
        logger.error("configure_headers called with None table")
        return

    # Configure horizontal header (columns)
    h_header = table.horizontalHeader()
    h_header.setSectionResizeMode(QHeaderView.Fixed)
    h_header.setMinimumSectionSize(1)  # Allow very narrow columns if needed
    h_header.setDefaultSectionSize(min_col_width)

    # Configure vertical header (rows)
    v_header = table.verticalHeader()
    v_header.setSectionResizeMode(QHeaderView.Fixed)
    v_header.setMinimumSectionSize(row_height)

    logger.debug(
        f"Headers configured: min_col_width={min_col_width}px, "
        f"row_height={row_height}px"
    )


def setup_grid(widget, table: QTableWidget) -> None:
    """
    Initialize PCR plate grid structure with data.

    Uses widget constants for configuration and delegates to initialize_grid.

    Args:
        widget: PCR plate widget instance (provides constants and callbacks)
        table: QTableWidget to initialize

    Performance: Single-pass grid initialization with updates disabled

    Required widget attributes:
        - HEADER_ROWS: Number of header rows
        - HEADER_COLS: Number of header columns
        - ROW_HEIGHT: Row height in pixels
        - COLOR_HEADER: Header cell color
        - COLOR_BASE: Base cell color
        - _table_index_to_patient_no: Callback for patient number mapping
    """
    if table is None or widget is None:
        logger.error("setup_grid called with None table or widget")
        return

    logger.debug(
        f"Setting up grid: {widget.HEADER_ROWS} header rows, "
        f"{widget.HEADER_COLS} header cols, "
        f"{widget.ROW_HEIGHT}px row height"
    )

    # Delegate to centralized grid initialization
    initialize_grid(
        table,
        header_rows=widget.HEADER_ROWS,
        header_cols=widget.HEADER_COLS,
        row_height=widget.ROW_HEIGHT,
        header_color=widget.COLOR_HEADER,
        base_color=widget.COLOR_BASE,
        table_index_to_patient_no=widget._table_index_to_patient_no,
    )

    logger.info("Grid setup completed successfully")


def resize_columns_to_fit_safe(
    table: QTableWidget,
    min_column_width: int,
) -> None:
    """
    Safely resize columns to fit viewport width.

    Wrapper around resize_columns_to_fit with error handling and validation.

    Args:
        table: QTableWidget to resize
        min_column_width: Minimum width per column (pixels)

    Performance: Single-pass column width calculation and application
    """
    if table is None:
        logger.error("resize_columns_to_fit_safe called with None table")
        return

    if min_column_width <= 0:
        logger.warning(
            f"Invalid min_column_width: {min_column_width}, using default 30px"
        )
        min_column_width = 30

    try:
        resize_columns_to_fit(table, min_column_width)
        logger.debug(
            f"Columns resized: {table.columnCount()} columns, "
            f"min_width={min_column_width}px"
        )
    except Exception as e:
        logger.error(f"Error during column resize: {e}", exc_info=True)


def apply_table_styles(table: QTableWidget) -> None:
    """
    Apply common table styling (selection, grid lines, etc.).

    Args:
        table: QTableWidget to style

    Performance: Single stylesheet application
    """
    if table is None:
        logger.error("apply_table_styles called with None table")
        return

    # Basic table styling
    table.setShowGrid(True)
    table.setAlternatingRowColors(False)  # We use custom coloring
    table.setSelectionMode(table.NoSelection)  # Custom selection handling
    table.setEditTriggers(table.NoEditTriggers)  # Read-only

    logger.debug("Table styles applied")


def reset_table_state(table: QTableWidget) -> None:
    """
    Reset table to default state (clear selection, scroll to top, etc.).

    Args:
        table: QTableWidget to reset

    Performance: Minimal operations, no data modification
    """
    if table is None:
        logger.error("reset_table_state called with None table")
        return

    # Clear any internal state
    table.clearSelection()
    table.scrollToTop()

    logger.debug("Table state reset")


def validate_table_structure(
    table: QTableWidget,
    expected_rows: int,
    expected_cols: int,
) -> bool:
    """
    Validate that table has expected structure.

    Args:
        table: QTableWidget to validate
        expected_rows: Expected row count
        expected_cols: Expected column count

    Returns:
        True if structure matches, False otherwise

    Use case: Debugging and testing
    """
    if table is None:
        logger.error("validate_table_structure called with None table")
        return False

    actual_rows = table.rowCount()
    actual_cols = table.columnCount()

    is_valid = (actual_rows == expected_rows and actual_cols == expected_cols)

    if not is_valid:
        logger.error(
            f"Table structure mismatch: expected {expected_rows}×{expected_cols}, "
            f"got {actual_rows}×{actual_cols}"
        )
    else:
        logger.debug(
            f"Table structure valid: {actual_rows}×{actual_cols}"
        )

    return is_valid 
def apply_analysis_result_styles(widget, table: QTableWidget, df: pd.DataFrame | None) -> None:
    """
    Color PCR plate wells by analysis results and regression risk.

    - "Sağlıklı"     -> rgb(129, 181, 99)
    - "Taşıyıcı"     -> rgb(255, 165, 0)
    - "Belirsiz"      -> rgb(255, 0, 255)
    - "Riskli Alan"   -> red diagonal overlay
    - "Boş Kuyu"      -> gray       (when result is empty)
    - "Yetersiz DNA"  -> reddish    (when result is empty)

    Args:
        widget: PCR plate widget instance
        table: Plate table instance
        df: Analysis DataFrame (must include well/result columns)
    """
    if widget is None or table is None:
        logger.error("apply_analysis_result_styles called with None widget/table")
        return

    status_colors = {
        "sağlıklı": QColor("#81B563"),
        "taşıyıcı": QColor(255, 165, 0),
        "belirsiz": QColor(255, 0, 255),
    }

    warning_colors = {
        "boş kuyu": QColor(180, 180, 180),
        "yetersiz dna": QColor(220, 80, 80),
    }

    # Reset defaults first
    widget._well_base_colors.clear()
    risky_cells: set[tuple[int, int]] = set()
    for row in range(1, table.rowCount()):
        for col in range(1, table.columnCount()):
            widget._well_base_colors[(row, col)] = widget.COLOR_BASE
            item = table.item(row, col)
            if item is not None:
                item.setBackground(widget.COLOR_BASE)

    if df is None or df.empty:
        table.set_risky_cells(set())
        return

    well_col = _find_first_column(df, ("Kuyu No", "Kuyu", "Well", "Well ID"))
    status_col = _find_first_column(
        df,
        ("Yazılım Hasta Sonucu", "Nihai Sonuç", "Sonuç", "İstatistik Oranı"),
    )
    regression_col = _find_first_column(df, ("Regresyon",))
    warning_col = _find_first_column(df, ("Uyarı", "Warning"))

    if well_col is None:
        logger.warning("No well column found for plate result styling")
        table.set_risky_cells(set())
        return

    for _, row_data in df.iterrows():
        well_raw = row_data.get(well_col)
        if pd.isna(well_raw):
            continue

        well_text = str(well_raw).strip().upper()
        try:
            row_idx, col_idx = well_mapping.well_id_to_table_index(well_text)
        except ValueError:
            continue

        item = table.item(row_idx, col_idx)
        if item is None:
            continue

        # --- Determine result status ---
        color = None
        if status_col is not None:
            status_raw = row_data.get(status_col)
            status_key = str(status_raw).strip().lower() if not pd.isna(status_raw) else ""
            color = status_colors.get(status_key)

        # --- Fallback: check warning column when result is empty ---
        if color is None and warning_col is not None:
            warning_raw = row_data.get(warning_col)
            warning_key = str(warning_raw).strip().lower() if not pd.isna(warning_raw) else ""
            color = warning_colors.get(warning_key)

        if color is not None:
            item.setBackground(color)
            widget._well_base_colors[(row_idx, col_idx)] = color

        # --- Regression risk overlay ---
        if regression_col is not None:
            regression_raw = row_data.get(regression_col)
            regression_text = (
                str(regression_raw).strip().lower() if not pd.isna(regression_raw) else ""
            )
            if regression_text == "riskli alan":
                risky_cells.add((row_idx, col_idx))

    widget._risky_cells = risky_cells
    table.set_risky_cells(risky_cells)
    table.viewport().update()


def _find_first_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None