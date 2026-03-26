# app\views\widgets\pcr_plate\interaction\drag_select.py
# -*- coding: utf-8 -*-
"""
Drag Selection State Management for PCR Plate.

This module manages drag-to-select behavior with:
- Add/remove selection modes
- Rectangular selection with anchor point
- Efficient well set operations
- Visited cell tracking to avoid redundant updates

Performance optimizations:
- Set-based operations (O(1) membership tests)
- Cached base selection to avoid recalculation
- Rectangle selection calculated once per drag event
- Minimal selection updates (only when changed)

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.utils import well_mapping

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class DragSelection:
    """
    State container for drag selection operations.

    Attributes:
        dragging: Whether drag operation is active
        mode: Selection mode ("add" or "remove")
        visited: Wells already processed in this drag (incremental mode)
        base_selection: Original selection at drag start (immutable during drag)
        current_selection: Current selection state (mutable during drag)
        last_cell: Last processed cell coordinates
        anchor_cell: Drag start cell coordinates (for rectangle selection)

    Performance characteristics:
    - Set operations are O(1) for membership, O(n) for union/difference
    - Visited tracking prevents redundant well processing
    - Base selection cached to avoid recalculating on every move
    """

    dragging: bool = False
    mode: str | None = None  # "add" or "remove"
    visited: set[str] = field(default_factory=set)
    base_selection: set[str] = field(default_factory=set)
    current_selection: set[str] = field(default_factory=set)
    last_cell: tuple[int, int] | None = None
    anchor_cell: tuple[int, int] | None = None

    def start(
        self,
        row: int,
        col: int,
        wells: set[str],
        selected_wells: set[str],
        force_mode: str | None = None,
    ) -> set[str] | None:
        """
        Start drag selection operation.

        Determines selection mode (add/remove) based on initial cell state,
        unless force_mode is specified.

        Args:
            row: Starting row index
            col: Starting column index
            wells: Wells under starting cell
            selected_wells: Currently selected wells
            force_mode: Force specific mode ("add" or "remove"), optional

        Returns:
            Updated selection set or None

        Performance: O(1) mode determination, O(n) set copy for base_selection
        """
        self.dragging = True
        self.last_cell = (row, col)
        self.anchor_cell = (row, col)

        # Determine mode: if any well in starting cell is selected, use remove mode
        if force_mode:
            self.mode = force_mode
        else:
            # Check if first well is selected to determine mode
            if wells:
                first_well = next(iter(wells))
                self.mode = "remove" if first_well in selected_wells else "add"
            else:
                self.mode = "add"

        # Cache base selection (will be restored/modified during drag)
        self.base_selection = set(selected_wells)
        self.current_selection = set(self.base_selection)
        self.visited.clear()

        logger.debug(
            f"Drag started at ({row},{col}), mode={self.mode}, "
            f"base_selection={len(self.base_selection)} wells"
        )

        # Apply initial wells
        return self._apply_wells(wells)

    def continue_drag(self, row: int, col: int) -> bool:
        """
        Check if drag should continue processing.

        Args:
            row: Current row index
            col: Current column index

        Returns:
            True if drag should continue, False if at same cell

        Performance: O(1) tuple comparison
        """
        if not self.dragging:
            return False

        # Skip processing if still on same cell (avoid redundant work)
        if (row, col) == self.last_cell:
            return False

        self.last_cell = (row, col)
        return True

    def apply_from_position(self, row: int, col: int) -> set[str] | None:
        """
        Apply rectangular selection from anchor to current position.

        Calculates rectangle bounds from anchor_cell to (row, col) and
        selects/deselects all wells within that rectangle.

        Args:
            row: Current row index
            col: Current column index

        Returns:
            Updated selection set or None if not dragging

        Performance: O(rows × cols × wells_per_cell) where rectangle size
        is typically small (few cells), and wells_per_cell is constant (1-4)

        Algorithm:
        1. Calculate rectangle bounds (min/max coordinates)
        2. Iterate cells in rectangle
        3. Collect all wells in rectangle
        4. Apply mode (add/remove) to base selection
        """
        if not self.dragging or self.anchor_cell is None:
            return None

        # Calculate rectangle bounds
        r_start, c_start = self.anchor_cell
        r_end, c_end = row, col

        # Support reverse dragging (min/max ensures correct bounds)
        row_range = range(min(r_start, r_end), max(r_start, r_end) + 1)
        col_range = range(min(c_start, c_end), max(c_start, c_end) + 1)

        # Collect all wells in rectangle
        rect_wells = set()
        for r in row_range:
            for c in col_range:
                wells = well_mapping.wells_for_header(r, c)
                if wells:
                    rect_wells |= wells  # Set union

        if not rect_wells:
            logger.debug(f"No wells found in rectangle ({r_start},{c_start}) to ({r_end},{c_end})")
            return None

        # Apply mode to base selection (not cumulative, rectangle replaces)
        if self.mode == "add":
            # Add all wells in rectangle to base selection
            self.current_selection = self.base_selection | rect_wells
        else:  # mode == "remove"
            # Remove all wells in rectangle from base selection
            self.current_selection = self.base_selection - rect_wells

        logger.debug(
            f"Rectangle selection: ({r_start},{c_start}) to ({r_end},{c_end}), "
            f"{len(rect_wells)} wells, mode={self.mode}, "
            f"result={len(self.current_selection)} selected"
        )

        return set(self.current_selection)

    def _apply_wells(self, wells: set[str]) -> set[str] | None:
        """
        Apply wells to current selection (incremental mode).

        Only processes wells not yet visited to avoid redundant updates.
        This is used for non-rectangular drag (incremental well-by-well).

        Args:
            wells: Wells to process

        Returns:
            Updated selection set or None if no new wells

        Performance: O(n) where n is len(wells), set operations are O(1)
        """
        if not self.dragging or not self.mode:
            return None

        # Filter out already visited wells
        new_wells = {w for w in wells if w not in self.visited}
        if not new_wells:
            return None

        # Mark wells as visited
        self.visited |= new_wells

        # Apply mode
        if self.mode == "add":
            self.current_selection |= new_wells
        else:  # mode == "remove"
            self.current_selection -= new_wells

        logger.debug(
            f"Applied {len(new_wells)} new wells, mode={self.mode}, "
            f"total_selected={len(self.current_selection)}"
        )

        return set(self.current_selection)

    def reset(self) -> None:
        """
        Reset drag state to initial values.

        Called when drag operation completes or is cancelled.

        Performance: O(n) to clear sets where n is number of elements
        """
        logger.debug(
            f"Drag reset: dragging={self.dragging}, "
            f"visited={len(self.visited)}, "
            f"final_selection={len(self.current_selection)}"
        )

        self.dragging = False
        self.mode = None
        self.visited.clear()
        self.base_selection.clear()
        self.current_selection.clear()
        self.last_cell = None
        self.anchor_cell = None

    def get_selection_stats(self) -> dict[str, int | str]:
        """
        Get statistics about current drag state.

        Returns:
            Dictionary with drag state metrics

        Use case: Debugging and performance monitoring
        """
        return {
            "dragging": self.dragging,
            "mode": self.mode or "none",
            "visited_count": len(self.visited),
            "base_selection_count": len(self.base_selection),
            "current_selection_count": len(self.current_selection),
            "delta": len(self.current_selection) - len(self.base_selection),
        }