# app\views\widgets\pcr_plate\setup\resizing.py
# -*- coding: utf-8 -*-
"""
PCR Plate Column Resizing Utilities.

This module provides efficient column width calculation and application:
- Proportional width distribution across columns
- Minimum width constraints
- Remainder distribution for pixel-perfect fitting
- Viewport-aware calculations

Performance optimizations:
- Cached width calculations
- Single-pass column width application
- Efficient integer division with remainder handling
- Early returns for invalid states

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QTableWidget

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Performance constants
MIN_COLUMN_WIDTH_ABSOLUTE = 1  # Minimum viable column width (pixels)
EXPECTED_PCR_COLUMNS = 13  # 12 data columns + 1 header column


def resize_columns_to_fit(
    table: QTableWidget,
    min_column_width: int,
) -> None:
    """
    Resize all columns to fit available viewport width.

    Distributes viewport width evenly across all columns while respecting
    minimum width constraint. Handles remainder pixels to avoid gaps.

    Args:
        table: QTableWidget to resize
        min_column_width: Minimum width per column (pixels)

    Performance: Single-pass column width application, efficient division
    with remainder handling.

    Example:
        Viewport width: 650px
        Columns: 13
        Base width: 650 // 13 = 50px
        Remainder: 650 % 13 = 0
        Result: All columns get 50px
    """
    if table is None:
        logger.error("resize_columns_to_fit called with None table")
        return

    column_count = table.columnCount()
    if column_count == 0:
        logger.debug("No columns to resize")
        return

    # Get available width (prefer viewport, fallback to widget width)
    available_width = _get_available_width(table)
    if available_width <= 0:
        logger.warning(f"Invalid available width: {available_width}, skipping resize")
        return

    # Calculate column widths
    widths = _calculate_column_widths(
        column_count=column_count,
        available_width=available_width,
        min_width=min_column_width,
    )

    # Apply widths in single pass
    _apply_column_widths(table, widths)

    logger.debug(
        f"Columns resized: {column_count} cols, "
        f"available={available_width}px, "
        f"base_width={widths[0] if widths else 0}px"
    )


def _get_available_width(table: QTableWidget) -> int:
    """
    Get available width for column distribution.

    Prefers viewport width (excludes scrollbar), falls back to widget width.

    Args:
        table: QTableWidget to measure

    Returns:
        Available width in pixels, or 0 if invalid

    Performance: Two attribute lookups maximum
    """
    # Prefer viewport width (accounts for scrollbar)
    viewport_width = table.viewport().width()
    if viewport_width > 0:
        return viewport_width

    # Fallback to widget width
    widget_width = table.width()
    if widget_width > 0:
        logger.debug(
            f"Using widget width ({widget_width}px) instead of "
            f"viewport width ({viewport_width}px)"
        )
        return widget_width

    return 0


def _calculate_column_widths(
    column_count: int,
    available_width: int,
    min_width: int,
) -> list[int]:
    """
    Calculate width for each column with minimum constraint.

    Algorithm:
    1. Calculate base width: available_width // column_count
    2. Ensure base width meets minimum
    3. Distribute remainder pixels across first N columns

    Args:
        column_count: Number of columns
        available_width: Total available width (pixels)
        min_width: Minimum width per column (pixels)

    Returns:
        List of widths for each column

    Performance: O(n) where n is column_count, efficient integer arithmetic

    Example:
        column_count=13, available_width=650, min_width=40
        base_width = 650 // 13 = 50
        remainder = 650 % 13 = 0
        Result: [50, 50, 50, ..., 50] (13 columns)
    """
    # Calculate base width per column
    target_width = max(min_width, available_width // column_count)

    # Check if target width fits
    total_width = target_width * column_count
    if total_width > available_width:
        # Reduce to minimum viable width
        target_width = max(MIN_COLUMN_WIDTH_ABSOLUTE, available_width // column_count)
        logger.warning(
            f"Target width ({target_width * column_count}px) exceeds available "
            f"({available_width}px), reduced to {target_width}px per column"
        )

    # Calculate remainder for distribution
    remainder = available_width - (target_width * column_count)

    # Build width list with remainder distribution
    widths = []
    for col_idx in range(column_count):
        # First 'remainder' columns get +1 pixel
        width = target_width + (1 if col_idx < remainder else 0)
        widths.append(width)

    # Validation
    actual_total = sum(widths)
    if actual_total != available_width:
        logger.warning(
            f"Width calculation mismatch: expected {available_width}px, "
            f"got {actual_total}px (difference: {actual_total - available_width}px)"
        )

    return widths


def _apply_column_widths(table: QTableWidget, widths: list[int]) -> None:
    """
    Apply calculated widths to table columns.

    Args:
        table: QTableWidget to modify
        widths: List of widths for each column

    Performance: Single pass, direct setColumnWidth() calls
    """
    if len(widths) != table.columnCount():
        logger.error(
            f"Width count mismatch: {len(widths)} widths for "
            f"{table.columnCount()} columns"
        )
        return

    for col_idx, width in enumerate(widths):
        table.setColumnWidth(col_idx, width)


def resize_columns_proportional(
    table: QTableWidget,
    ratios: list[int],
    min_column_width: int = MIN_COLUMN_WIDTH_ABSOLUTE,
) -> None:
    """
    Resize columns using proportional ratios.

    Distributes available width according to provided ratios while
    respecting minimum width constraints.

    Args:
        table: QTableWidget to resize
        ratios: List of integers representing relative widths
               (e.g., [2, 1, 1] makes first column 2x wider)
        min_column_width: Minimum width per column (pixels)

    Performance: O(n) calculation, single-pass application

    Example:
        ratios=[2, 1, 1], available_width=400
        ratio_sum = 4
        widths = [200, 100, 100]
    """
    if table is None or not ratios:
        logger.error("Invalid parameters for resize_columns_proportional")
        return

    column_count = table.columnCount()
    if len(ratios) != column_count:
        logger.error(
            f"Ratio count mismatch: {len(ratios)} ratios for "
            f"{column_count} columns"
        )
        return

    available_width = _get_available_width(table)
    if available_width <= 0:
        return

    # Calculate widths based on ratios
    ratio_sum = sum(ratios) or 1  # Avoid division by zero
    widths = []
    used_width = 0

    for idx, ratio in enumerate(ratios):
        if idx == column_count - 1:
            # Last column gets remainder
            width = max(min_column_width, available_width - used_width)
        else:
            # Calculate proportional width
            width = max(min_column_width, int(available_width * (ratio / ratio_sum)))
            used_width += width

        widths.append(width)

    # Apply widths
    _apply_column_widths(table, widths)

    logger.debug(
        f"Proportional resize applied: ratios={ratios}, "
        f"widths={widths[:3]}{'...' if len(widths) > 3 else ''}"
    )


def get_column_width_stats(table: QTableWidget) -> dict[str, int]:
    """
    Get statistics about current column widths.

    Args:
        table: QTableWidget to analyze

    Returns:
        Dictionary with min, max, avg, total widths

    Use case: Debugging and performance monitoring
    """
    if table is None or table.columnCount() == 0:
        return {"min": 0, "max": 0, "avg": 0, "total": 0}

    widths = [table.columnWidth(col) for col in range(table.columnCount())]

    stats = {
        "min": min(widths),
        "max": max(widths),
        "avg": sum(widths) // len(widths),
        "total": sum(widths),
        "count": len(widths),
    }

    logger.debug(
        f"Column width stats: min={stats['min']}px, max={stats['max']}px, "
        f"avg={stats['avg']}px, total={stats['total']}px"
    )

    return stats