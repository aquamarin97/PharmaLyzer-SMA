# app\views\widgets\pcr_plate\interaction\range_select.py
# -*- coding: utf-8 -*-
"""
Range Selection for PCR Plate (Shift-Click).

This module handles Shift+Click range selection with:
- Anchor-based rectangle selection
- Control modifier for toggle selection
- Efficient well collection in rectangle bounds

Performance optimizations:
- Minimal well_mapping lookups
- Single set operation for selection update
- Efficient rectangle bounds calculation
- Early returns for invalid states

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt

from app.utils import well_mapping

if TYPE_CHECKING:
    from app.services.interaction_store import InteractionStore

logger = logging.getLogger(__name__)


def apply_range_selection(
    store: InteractionStore,
    anchor_cell: tuple[int, int] | None,
    row: int,
    col: int,
    modifiers: Qt.KeyboardModifiers,
) -> tuple[int, int] | None:
    """
    Apply range selection from anchor to current cell.

    Creates rectangular selection from anchor_cell to (row, col).
    Behavior depends on keyboard modifiers:
    - No modifier: Replace selection with rectangle
    - Ctrl modifier: Toggle wells in rectangle (XOR operation)

    Args:
        store: InteractionStore instance
        anchor_cell: Anchor cell coordinates (or None to use current cell)
        row: Current row index
        col: Current column index
        modifiers: Keyboard modifiers (Qt.ControlModifier, etc.)

    Returns:
        New anchor cell coordinates (typically current cell)

    Performance: O(rows × cols) where rectangle size is typically small

    Example:
        anchor_cell = (1, 1)  # Cell A01
        current = (3, 5)      # Cell C05
        Result: Select rectangle A01:C05 (3 rows × 5 cols = 15 wells)
    """
    if store is None:
        logger.error("apply_range_selection called with None store")
        return anchor_cell

    # Use current cell as anchor if none provided
    anchor = anchor_cell or (row, col)

    # Calculate rectangle bounds (supports reverse selection)
    min_row = min(anchor[0], row)
    max_row = max(anchor[0], row)
    min_col = min(anchor[1], col)
    max_col = max(anchor[1], col)

    # Collect all wells in rectangle
    wells = _collect_wells_in_rectangle(min_row, max_row, min_col, max_col)

    if not wells:
        logger.debug(
            f"No wells found in range ({anchor[0]},{anchor[1]}) to ({row},{col})"
        )
        return (row, col)

    # Apply selection based on modifiers
    if modifiers & Qt.ControlModifier:
        # Ctrl+Shift: Toggle wells (XOR operation)
        _apply_toggle_selection(store, wells)
    else:
        # Shift only: Replace selection with rectangle
        _apply_replace_selection(store, wells)

    logger.debug(
        f"Range selection applied: ({min_row},{min_col}) to ({max_row},{max_col}), "
        f"{len(wells)} wells, ctrl={bool(modifiers & Qt.ControlModifier)}"
    )

    # Return current cell as new anchor for next range operation
    return (row, col)


def _collect_wells_in_rectangle(
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> set[str]:
    """
    Collect all wells within rectangle bounds.

    Args:
        min_row: Minimum row index (inclusive)
        max_row: Maximum row index (inclusive)
        min_col: Minimum column index (inclusive)
        max_col: Maximum column index (inclusive)

    Returns:
        Set of well IDs in the rectangle

    Performance: O(rows × cols) with typical small rectangle size
    """
    wells = set()

    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            # Get well ID for this table position
            well_id = well_mapping.table_index_to_well_id(r, c)
            if well_id:
                wells.add(well_id)

    logger.debug(
        f"Collected {len(wells)} wells in rectangle "
        f"({min_row},{min_col}) to ({max_row},{max_col})"
    )

    return wells


def _apply_replace_selection(
    store: InteractionStore,
    wells: set[str],
) -> None:
    """
    Replace current selection with rectangle wells.

    Args:
        store: InteractionStore instance
        wells: Wells to select

    Performance: Single store update
    """
    store.set_selection(wells)
    logger.debug(f"Selection replaced: {len(wells)} wells selected")


def _apply_toggle_selection(
    store: InteractionStore,
    wells: set[str],
) -> None:
    """
    Toggle wells in rectangle (XOR operation).

    Wells currently selected will be deselected, and vice versa.

    Args:
        store: InteractionStore instance
        wells: Wells to toggle

    Performance: O(n) where n is len(wells), set symmetric_difference is O(n)
    """
    current_selection = set(store.selected_wells)

    # XOR operation: symmetric difference
    # Alternatively: (current - wells) | (wells - current)
    new_selection = current_selection ^ wells

    store.set_selection(new_selection)

    added = len(wells - current_selection)
    removed = len(wells & current_selection)
    logger.debug(
        f"Selection toggled: +{added} wells, -{removed} wells, "
        f"total={len(new_selection)}"
    )


def calculate_range_bounds(
    anchor: tuple[int, int],
    current: tuple[int, int],
) -> tuple[int, int, int, int]:
    """
    Calculate normalized rectangle bounds from anchor to current.

    Args:
        anchor: Anchor cell (row, col)
        current: Current cell (row, col)

    Returns:
        Tuple of (min_row, max_row, min_col, max_col)

    Performance: O(1) min/max operations

    Example:
        anchor = (5, 8)
        current = (2, 3)
        Result: (2, 5, 3, 8)  # normalized bounds
    """
    min_row = min(anchor[0], current[0])
    max_row = max(anchor[0], current[0])
    min_col = min(anchor[1], current[1])
    max_col = max(anchor[1], current[1])

    return (min_row, max_row, min_col, max_col)


def get_range_dimensions(
    anchor: tuple[int, int],
    current: tuple[int, int],
) -> dict[str, int]:
    """
    Get dimensions of range selection rectangle.

    Args:
        anchor: Anchor cell (row, col)
        current: Current cell (row, col)

    Returns:
        Dictionary with width, height, cell_count

    Use case: UI feedback (e.g., show selection dimensions)
    """
    min_row, max_row, min_col, max_col = calculate_range_bounds(anchor, current)

    width = max_col - min_col + 1
    height = max_row - min_row + 1
    cell_count = width * height

    return {
        "width": width,
        "height": height,
        "cell_count": cell_count,
        "min_row": min_row,
        "max_row": max_row,
        "min_col": min_col,
        "max_col": max_col,
    }


def is_valid_range(
    anchor: tuple[int, int] | None,
    current: tuple[int, int],
    max_rows: int = 9,  # 8 data rows + 1 header
    max_cols: int = 13,  # 12 data cols + 1 header
) -> bool:
    """
    Validate that range selection coordinates are within bounds.

    Args:
        anchor: Anchor cell (row, col) or None
        current: Current cell (row, col)
        max_rows: Maximum valid row index
        max_cols: Maximum valid column index

    Returns:
        True if range is valid, False otherwise

    Performance: O(1) boundary checks
    """
    if anchor is None:
        return True  # No range, valid by default

    # Check bounds
    anchor_valid = (0 <= anchor[0] < max_rows and 0 <= anchor[1] < max_cols)
    current_valid = (0 <= current[0] < max_rows and 0 <= current[1] < max_cols)

    return anchor_valid and current_valid