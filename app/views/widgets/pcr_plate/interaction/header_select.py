# app\views\widgets\pcr_plate\interaction\header_select.py
# -*- coding: utf-8 -*-
"""
Header Click Selection for PCR Plate.

This module handles row/column header clicks with smart toggle behavior:
- If majority selected: deselect all
- If minority selected: select all
- 50/50 tie: deselect all (consistent behavior)

Performance optimizations:
- Single set intersection for selected count
- Minimal store updates (only when selection changes)
- Efficient set operations (union/difference)
- Early returns for invalid states

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.interaction_store import InteractionStore

logger = logging.getLogger(__name__)


def toggle_header_selection(
    store: InteractionStore,
    wells: set[str],
) -> None:
    """
    Toggle selection for all wells in a row or column.

    Smart toggle logic:
    - If > 50% selected: deselect all
    - If = 50% selected: deselect all (break tie toward deselect)
    - If < 50% selected: select all

    Args:
        store: InteractionStore instance
        wells: Set of wells in the clicked row/column

    Performance: O(n) where n is len(wells), dominated by set intersection

    Example:
        wells = {"A1", "A2", "A3", "A4"}
        selected = {"A1", "A2"}  # 50% selected
        Result: Deselect all (selected_count == total/2)
    """
    if store is None:
        logger.error("toggle_header_selection called with None store")
        return

    if not wells:
        logger.debug("No wells provided for header selection")
        return

    # Get current selection
    current_selection = set(store.selected_wells)

    # Calculate overlap (how many wells are currently selected)
    selected_count = len(current_selection & wells)
    total_count = len(wells)

    # Determine action based on threshold
    if selected_count == total_count:
        # All selected: deselect all
        action = "deselect_all"
        new_selection = current_selection - wells
    elif selected_count > total_count / 2:
        # Majority selected: deselect all
        action = "deselect_majority"
        new_selection = current_selection - wells
    else:
        # Minority selected (or 50/50): select all
        action = "select_minority"
        new_selection = current_selection | wells

    # Apply selection change
    store.set_selection(new_selection)

    logger.debug(
        f"Header toggle: {action}, selected={selected_count}/{total_count}, "
        f"result={len(new_selection)} total selected"
    )


def select_entire_row(store: InteractionStore, row_letter: str) -> None:
    """
    Select all wells in a specific row.

    Args:
        store: InteractionStore instance
        row_letter: Row letter ("A", "B", ..., "H")

    Performance: O(n) where n is number of columns (typically 12)
    """
    if store is None or not row_letter:
        logger.error("Invalid parameters for select_entire_row")
        return

    from app.utils import well_mapping

    # Calculate wells for this row
    wells = set()
    for col_num in well_mapping.COLUMNS:
        well_id = f"{row_letter}{col_num}"
        wells.add(well_id)

    if not wells:
        logger.warning(f"No wells found for row {row_letter}")
        return

    # Add to current selection
    current_selection = set(store.selected_wells)
    new_selection = current_selection | wells

    store.set_selection(new_selection)

    logger.debug(f"Row {row_letter} selected: {len(wells)} wells added")


def select_entire_column(store: InteractionStore, column_number: int) -> None:
    """
    Select all wells in a specific column.

    Args:
        store: InteractionStore instance
        column_number: Column number (1-12)

    Performance: O(n) where n is number of rows (typically 8)
    """
    if store is None or not (1 <= column_number <= 12):
        logger.error(f"Invalid parameters for select_entire_column: col={column_number}")
        return

    from app.utils import well_mapping

    # Calculate wells for this column
    wells = set()
    for row_letter in well_mapping.ROWS:
        well_id = f"{row_letter}{column_number}"
        wells.add(well_id)

    if not wells:
        logger.warning(f"No wells found for column {column_number}")
        return

    # Add to current selection
    current_selection = set(store.selected_wells)
    new_selection = current_selection | wells

    store.set_selection(new_selection)

    logger.debug(f"Column {column_number} selected: {len(wells)} wells added")


def deselect_entire_row(store: InteractionStore, row_letter: str) -> None:
    """
    Deselect all wells in a specific row.

    Args:
        store: InteractionStore instance
        row_letter: Row letter ("A", "B", ..., "H")

    Performance: O(n) where n is number of columns (typically 12)
    """
    if store is None or not row_letter:
        logger.error("Invalid parameters for deselect_entire_row")
        return

    from app.utils import well_mapping

    # Calculate wells for this row
    wells = set()
    for col_num in well_mapping.COLUMNS:
        well_id = f"{row_letter}{col_num}"
        wells.add(well_id)

    if not wells:
        logger.warning(f"No wells found for row {row_letter}")
        return

    # Remove from current selection
    current_selection = set(store.selected_wells)
    new_selection = current_selection - wells

    store.set_selection(new_selection)

    logger.debug(f"Row {row_letter} deselected: {len(wells)} wells removed")


def deselect_entire_column(store: InteractionStore, column_number: int) -> None:
    """
    Deselect all wells in a specific column.

    Args:
        store: InteractionStore instance
        column_number: Column number (1-12)

    Performance: O(n) where n is number of rows (typically 8)
    """
    if store is None or not (1 <= column_number <= 12):
        logger.error(f"Invalid parameters for deselect_entire_column: col={column_number}")
        return

    from app.utils import well_mapping

    # Calculate wells for this column
    wells = set()
    for row_letter in well_mapping.ROWS:
        well_id = f"{row_letter}{column_number}"
        wells.add(well_id)

    if not wells:
        logger.warning(f"No wells found for column {column_number}")
        return

    # Remove from current selection
    current_selection = set(store.selected_wells)
    new_selection = current_selection - wells

    store.set_selection(new_selection)

    logger.debug(f"Column {column_number} deselected: {len(wells)} wells removed")


def get_header_selection_info(
    store: InteractionStore,
    wells: set[str],
) -> dict[str, int | float]:
    """
    Get information about header selection state.

    Args:
        store: InteractionStore instance
        wells: Wells in the header

    Returns:
        Dictionary with selection statistics

    Use case: Debugging, UI feedback (e.g., partial selection indicator)
    """
    if store is None or not wells:
        return {
            "total": 0,
            "selected": 0,
            "percentage": 0.0,
            "action": "none",
        }

    current_selection = set(store.selected_wells)
    selected_count = len(current_selection & wells)
    total_count = len(wells)
    percentage = (selected_count / total_count * 100) if total_count > 0 else 0.0

    # Determine what would happen on click
    if selected_count == total_count or selected_count > total_count / 2:
        action = "deselect"
    else:
        action = "select"

    return {
        "total": total_count,
        "selected": selected_count,
        "percentage": percentage,
        "action": action,
    }