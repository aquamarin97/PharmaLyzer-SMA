# app\views\widgets\pcr_plate\pcr_plate_widget.py
# -*- coding: utf-8 -*-
"""
PCR Plate Widget - Main Component.

This module provides the main PCR plate visualization widget:
- 9×13 grid (1 header row + 8 data rows, 1 header col + 12 data cols)
- Bidirectional sync with InteractionStore
- Mouse interaction handling
- Visual state rendering

Performance optimizations:
- Deferred resize operations with QTimer.singleShot
- Efficient state caching to minimize updates
- Viewport-only repaints (not full widget)
- Single-pass initialization

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import pandas as pd
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QAbstractItemView, QVBoxLayout, QWidget

from app.services.interaction_store import InteractionStore
from app.views.widgets.pcr_plate.pcr_plate_table import PlateTable

from ._mouse_handlers import (
    handle_mouse_move,
    handle_mouse_press,
    handle_mouse_release,
)
from ._render_apply import (
    clear_all_visual_state,
    on_hover_changed,
    on_preview_changed,
    on_selection_changed,
)
from ._store_binding import bind_store
from ._ui_setup import (
    apply_analysis_result_styles,
    configure_headers,
    resize_columns_to_fit_safe,
    setup_grid,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PCRPlateWidget(QWidget):
    """
    PCR plate visualization widget.

    Displays a 9×13 grid representing a 96-well PCR plate with:
    - 1 header row (column labels: 01-12)
    - 1 header column (row labels: A-H)
    - 8×12 data cells (wells A1-H12)

    Features:
    - Interactive selection (click, drag, Shift+click)
    - Header selection (click row/column to select all)
    - Hover effects
    - Preview mode (drag preview)
    - Bidirectional sync with InteractionStore

    Performance characteristics:
    - Deferred resize operations (no blocking)
    - Cached state to minimize updates
    - Viewport-only repaints
    - Efficient signal handling
    """

    # Grid configuration
    HEADER_ROWS = 1
    HEADER_COLS = 1

    # Color scheme
    COLOR_SELECTED = QColor("#3A7AFE")  # Blue selection
    COLOR_BASE = QColor("#f2f2f2")      # Light gray base
    COLOR_HEADER = QColor("#d9d9d9")    # Gray headers

    # Sizing constants
    MIN_COLUMN_WIDTH = 40
    ROW_HEIGHT = 32

    def __init__(
        self,
        original_widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize PCR plate widget.

        Args:
            original_widget: Original widget to replace (copies properties)
            parent: Parent widget (optional)
        """
        super().__init__(parent or original_widget.parent())

        # Copy properties from original widget
        self.setObjectName(original_widget.objectName())
        self.setSizePolicy(original_widget.sizePolicy())
        self.setMinimumSize(original_widget.minimumSize())
        self.setMaximumSize(original_widget.maximumSize())

        # Initialize state
        self._init_state()

        # Create table with injected callbacks
        self._init_table()

        # Setup layout
        self._init_layout()

        # Initialize grid structure
        setup_grid(widget=self, table=self.table)

        # Defer initial resize to allow layout to settle
        self._resize_columns_to_fit()

        logger.info(
            f"PCRPlateWidget initialized: {self.objectName()}, "
            f"grid={self.table.rowCount()}×{self.table.columnCount()}"
        )

    def _init_state(self) -> None:
        """
        Initialize widget state variables.

        Performance: Called once during construction
        """
        # Store binding
        self._store: InteractionStore | None = None

        # Hover state
        self._hover_row: int | None = None
        self._hover_col: int | None = None

        # Preview state
        self._preview_cells: set[tuple[int, int]] = set()

        # Selection state
        self._anchor_cell: tuple[int, int] | None = None

        # Drag selection state
        from app.views.widgets.pcr_plate.interaction.drag_select import DragSelection
        self._drag_selection = DragSelection()

        # UI diff/cache for efficient updates
        self._last_selected_wells: set[str] = set()
        self._last_hover_well_sent: str | None = None
        self._well_base_colors: dict[tuple[int, int], QColor] = {}
        self._risky_cells: set[tuple[int, int]] = set()
        logger.debug("State initialized")

    def _init_table(self) -> None:
        """
        Initialize table widget with callbacks.

        Performance: Single table creation with all callbacks configured
        """
        self.table = PlateTable(
            parent=self,
            hover_index_getter=self._get_hover_index,
            on_hover_move=self._handle_mouse_move,
            on_mouse_press=self._handle_mouse_press,
            on_mouse_move=self._handle_mouse_move,
            on_mouse_release=self._handle_mouse_release,
        )

        # Configure table behavior
        self.table.setMouseTracking(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)

        # Hide default headers (we draw custom ones)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)

        # Disable scrollbars (fixed size grid)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Configure headers with fixed sizing
        configure_headers(
            self.table,
            min_col_width=self.MIN_COLUMN_WIDTH,
            row_height=self.ROW_HEIGHT,
        )

        logger.debug("Table initialized")

    def _init_layout(self) -> None:
        """
        Initialize widget layout.

        Performance: Single layout creation with zero margins
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

        logger.debug("Layout initialized")

    # ---- InteractionStore Binding ----

    def set_interaction_store(self, store: InteractionStore) -> None:
        """
        Bind InteractionStore to widget.

        Connects store signals to widget callbacks for bidirectional sync.

        Args:
            store: InteractionStore instance to bind

        Performance: Three signal connections, three initial state applications
        """
        bind_store(
            widget=self,
            store=store,
            on_selection_changed=self._on_selection_changed,
            on_hover_changed=self._on_hover_changed,
            on_preview_changed=self._on_preview_changed,
        )

        logger.info(
            f"Store bound: {len(store.selected_wells)} wells selected, "
            f"hover={store.hover_well}"
        )

    # ---- Mouse Event Delegates ----

    def _handle_mouse_move(self, event) -> None:
        """
        Delegate mouse move to handler.

        Args:
            event: Mouse move event

        Performance: Direct delegation, no processing here
        """
        handle_mouse_move(self, event)

    def _handle_mouse_press(self, event) -> None:
        """
        Delegate mouse press to handler.

        Args:
            event: Mouse press event

        Performance: Direct delegation, no processing here
        """
        handle_mouse_press(self, event)

    def _handle_mouse_release(self, event) -> None:
        """
        Delegate mouse release to handler.

        Args:
            event: Mouse release event

        Performance: Direct delegation, no processing here
        """
        handle_mouse_release(self, event)

    # ---- Store Callback Delegates ----

    def _on_selection_changed(self, selected_wells: set[str]) -> None:
        """
        Delegate selection change to renderer.

        Args:
            selected_wells: New set of selected wells

        Performance: Direct delegation with cached state
        """
        on_selection_changed(self, selected_wells)

    def _on_hover_changed(self, well: str | None) -> None:
        """
        Delegate hover change to renderer.

        Args:
            well: Well ID being hovered, or None

        Performance: Direct delegation
        """
        on_hover_changed(self, well)

    def _on_preview_changed(self, wells: set[str]) -> None:
        """
        Delegate preview change to renderer.

        Args:
            wells: Set of wells to preview

        Performance: Direct delegation
        """
        on_preview_changed(self, wells)

    # ---- Helpers ----

    def _get_hover_index(self) -> tuple[int | None, int | None]:
        """
        Get current hover position.

        Returns:
            Tuple of (row, col) or (None, None)

        Performance: O(1) attribute access
        """
        return self._hover_row, self._hover_col

    def _table_index_to_patient_no(self, row: int, column: int) -> int:
        """
        Convert table indices to patient number.

        Args:
            row: Table row index
            column: Table column index

        Returns:
            Patient number for this position

        Raises:
            ValueError: If indices are invalid

        Performance: Single well mapping lookup
        """
        from app.utils import well_mapping

        well_id = well_mapping.table_index_to_well_id(row, column)
        if well_id is None:
            raise ValueError(
                f"Invalid table index for patient number: ({row}, {column})"
            )

        return well_mapping.well_id_to_patient_no(well_id)
    def reset(self) -> None:
        """Reset plate widget visual and interaction state."""
        self._anchor_cell = None
        self._drag_selection.reset()

        if self._store is not None:
            self._store.clear_preview()
            self._store.clear_hover()
            self._store.clear_selection()
        # Normalize all well base colors back to default before visual clear.
        apply_analysis_result_styles(self, self.table, None)
        clear_all_visual_state(self)
        logger.debug("PCR plate widget reset complete")
    # ---- Resize Handling ----

    def resizeEvent(self, event) -> None:
        """
        Handle widget resize events.

        Args:
            event: Resize event

        Performance: Defers column resize to avoid blocking
        """
        super().resizeEvent(event)
        self._resize_columns_to_fit()

    def showEvent(self, event) -> None:
        """
        Handle widget show events.

        Args:
            event: Show event

        Performance: Defers column resize with single-shot timer
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._resize_columns_to_fit)

    def _resize_columns_to_fit(self) -> None:
        """
        Resize columns to fit viewport width.

        Performance: Deferred operation, single-pass calculation
        """
        resize_columns_to_fit_safe(self.table, self.MIN_COLUMN_WIDTH)

    # ---- State Inspection ----
    def apply_analysis_results(self, df: pd.DataFrame | None) -> None:
        """
        Apply analysis-based well colors and regression risk overlays.

        Args:
            df: Analysis dataframe from DataStore
        """
        apply_analysis_result_styles(self, self.table, df)
    def get_state_summary(self) -> dict:
        """
        Get summary of current widget state.

        Returns:
            Dictionary with state metrics

        Use case: Debugging, performance monitoring
        """
        return {
            "store_bound": self._store is not None,
            "selected_count": len(self._last_selected_wells),
            "hover_active": self._hover_row is not None,
            "hover_pos": (self._hover_row, self._hover_col),
            "preview_count": len(self._preview_cells),
            "dragging": self._drag_selection.dragging,
            "drag_mode": self._drag_selection.mode,
            "anchor_cell": self._anchor_cell,
        }