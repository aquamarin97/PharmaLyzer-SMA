# app\views\widgets\pcr_plate\setup\grid_setup.py
# -*- coding: utf-8 -*-
"""
PCR Plate Grid Setup and Initialization.

This module provides functions for initializing the PCR plate table widget:
- Grid structure creation (rows, columns, headers)
- Cell population with patient numbers
- Base color application for headers and wells
- Row height configuration

Performance optimizations:
- Batch item creation to minimize layout recalculations
- setUpdatesEnabled(False) during bulk operations
- Single-pass color application
- Efficient well mapping lookup
- Pre-allocated item creation

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem

from app.utils import well_mapping

if TYPE_CHECKING:
    from PyQt5.QtGui import QBrush, QColor

logger = logging.getLogger(__name__)

# Performance thresholds
EXPECTED_WELL_COUNT = 96  # 8 rows × 12 columns


def initialize_grid(
    table: QTableWidget,
    header_rows: int,
    header_cols: int,
    row_height: int,
    header_color: QBrush | QColor,
    base_color: QBrush | QColor,
    table_index_to_patient_no: Callable[[int, int], int],
) -> None:
    """
    Initialize PCR plate grid with headers, cells, and colors.

    This is the main entry point for grid setup. Performs all initialization
    in a single batch operation with updates disabled for performance.

    Args:
        table: QTableWidget to initialize
        header_rows: Number of header rows (typically 1)
        header_cols: Number of header columns (typically 1)
        row_height: Height in pixels for each row
        header_color: Background color for headers
        base_color: Background color for data cells
        table_index_to_patient_no: Function mapping (row, col) to patient number

    Performance: All operations done with setUpdatesEnabled(False) to prevent
    intermediate repaints. Single-pass color application.
    """
    if table is None:
        logger.error("initialize_grid called with None table")
        return

    # Calculate dimensions
    total_rows = len(well_mapping.ROWS) + header_rows
    total_cols = len(well_mapping.COLUMNS) + header_cols

    logger.info(
        f"Initializing grid: {total_rows} rows × {total_cols} cols "
        f"(data: {len(well_mapping.ROWS)}×{len(well_mapping.COLUMNS)})"
    )

    # CRITICAL: Disable updates during bulk operations
    table.setUpdatesEnabled(False)
    try:
        # Set dimensions
        table.setRowCount(total_rows)
        table.setColumnCount(total_cols)

        # Create all items in single pass
        _create_all_items(table)

        # Populate with data
        _populate_headers(table)
        _populate_cells(table, table_index_to_patient_no)

        # Apply colors in single pass
        apply_base_colors(table, header_color, base_color)

        # Set uniform row heights
        set_row_heights(table, row_height)

        logger.info(f"Grid initialized successfully: {total_rows}×{total_cols} cells")

    finally:
        # Re-enable updates and trigger single repaint
        table.setUpdatesEnabled(True)
        table.viewport().update()


def _create_all_items(table: QTableWidget) -> None:
    """
    Create QTableWidgetItem objects for all cells.

    Pre-creates all items with center alignment to avoid lazy creation
    during rendering, which can cause performance issues.

    Args:
        table: QTableWidget to populate

    Performance: Single loop creates all items at once, minimizing
    intermediate layout calculations.
    """
    row_count = table.rowCount()
    col_count = table.columnCount()
    total_items = row_count * col_count

    logger.debug(f"Creating {total_items} table items")

    for row in range(row_count):
        for col in range(col_count):
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignCenter)
            # Note: setItem() is efficient when called during initialization
            table.setItem(row, col, item)

    logger.debug(f"All {total_items} items created")


def _populate_headers(table: QTableWidget) -> None:
    """
    Populate header row and column with well identifiers.

    Header layout:
    - Corner cell (0,0): Empty
    - Top row (0, 1-12): Column numbers "01", "02", ..., "12"
    - Left column (1-8, 0): Row letters "A", "B", ..., "H"

    Args:
        table: QTableWidget with pre-created items

    Performance: Direct item access via item(), no creation overhead
    """
    # Corner cell: empty
    corner = table.item(0, 0)
    if corner:
        corner.setText("")

    # Column headers: 01, 02, ..., 12
    for idx, col_num in enumerate(well_mapping.COLUMNS, start=1):
        item = table.item(0, idx)
        if item:
            # Format with leading zero for single digits
            item.setText(f"{col_num:02d}")

    # Row headers: A, B, ..., H
    for idx, row_label in enumerate(well_mapping.ROWS, start=1):
        item = table.item(idx, 0)
        if item:
            item.setText(row_label)

    logger.debug(
        f"Headers populated: {len(well_mapping.COLUMNS)} columns, "
        f"{len(well_mapping.ROWS)} rows"
    )


def _populate_cells(
    table: QTableWidget,
    table_index_to_patient_no: Callable[[int, int], int],
) -> None:
    """
    Populate data cells with patient numbers.

    Uses provided callback function to map table coordinates to patient numbers.
    Only populates data cells (skips header row/column).

    Args:
        table: QTableWidget with pre-created items
        table_index_to_patient_no: Function mapping (row_idx, col_idx) to patient number

    Performance: Direct item access, efficient callback invocation
    """
    cell_count = 0

    for row_idx, _ in enumerate(well_mapping.ROWS, start=1):
        for col_idx, _ in enumerate(well_mapping.COLUMNS, start=1):
            item = table.item(row_idx, col_idx)
            if item:
                # Get patient number from callback
                patient_no = table_index_to_patient_no(row_idx, col_idx)
                item.setText(str(patient_no))
                cell_count += 1

    logger.debug(f"Populated {cell_count} data cells with patient numbers")


def apply_base_colors(
    table: QTableWidget,
    header_color: QBrush | QColor,
    base_color: QBrush | QColor,
) -> None:
    """
    Apply background colors to all cells.

    Color scheme:
    - Headers (row 0 or column 0): header_color
    - Data cells: base_color

    Args:
        table: QTableWidget to colorize
        header_color: Background for header cells
        base_color: Background for data cells

    Performance: Single pass over all cells, direct setBackground() calls
    """
    row_count = table.rowCount()
    col_count = table.columnCount()
    header_cells = 0
    data_cells = 0

    for row in range(row_count):
        for col in range(col_count):
            item = table.item(row, col)
            if item is None:
                continue

            # Apply color based on position
            if row == 0 or col == 0:
                item.setBackground(header_color)
                header_cells += 1
            else:
                item.setBackground(base_color)
                data_cells += 1

    logger.debug(
        f"Colors applied: {header_cells} header cells, {data_cells} data cells"
    )


def set_row_heights(table: QTableWidget, row_height: int) -> None:
    """
    Set uniform height for all rows.

    Args:
        table: QTableWidget to configure
        row_height: Height in pixels for each row

    Performance: Efficient batch operation, Qt handles layout update
    """
    if row_height <= 0:
        logger.warning(f"Invalid row_height: {row_height}, skipping")
        return

    row_count = table.rowCount()

    for row in range(row_count):
        table.setRowHeight(row, row_height)

    logger.debug(f"Row heights set: {row_count} rows × {row_height}px")


def validate_grid_structure(table: QTableWidget) -> bool:
    """
    Validate that grid structure matches expected PCR plate dimensions.

    Args:
        table: QTableWidget to validate

    Returns:
        True if structure is valid, False otherwise

    Use case: Debugging and testing to ensure grid was initialized correctly
    """
    expected_rows = len(well_mapping.ROWS) + 1  # +1 for header
    expected_cols = len(well_mapping.COLUMNS) + 1  # +1 for header

    actual_rows = table.rowCount()
    actual_cols = table.columnCount()

    is_valid = (actual_rows == expected_rows and actual_cols == expected_cols)

    if not is_valid:
        logger.error(
            f"Grid structure mismatch: expected {expected_rows}×{expected_cols}, "
            f"got {actual_rows}×{actual_cols}"
        )
    else:
        logger.debug(
            f"Grid structure valid: {actual_rows}×{actual_cols} "
            f"({EXPECTED_WELL_COUNT} wells)"
        )

    return is_valid