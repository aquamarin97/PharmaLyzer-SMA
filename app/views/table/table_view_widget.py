# app\views\table\table_view_widget.py
# -*- coding: utf-8 -*-
"""
Custom Table View Widget with Dynamic Column Sizing.

This module provides a QTableView subclass with:
- Proportional column width distribution based on ratios
- Debounced resize events for smooth performance
- Event filter for viewport resize handling
- Custom styling with header formatting

Performance optimizations:
- QTimer debouncing for resize events (avoids layout thrashing)
- Single-shot timers for deferred initialization
- Cached column expansion ratios
- Efficient viewport update regions

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtWidgets import QTableView

if TYPE_CHECKING:
    from PyQt5.QtCore import QObject

logger = logging.getLogger(__name__)

# Performance thresholds (milliseconds)
RESIZE_DEBOUNCE_MS = 10  # Delay before applying column resize
COLUMN_ADJUST_DELAY_MS = 0  # Single-shot delay for initial column setup


class TableViewWidget(QTableView):
    """
    Enhanced QTableView with automatic column width management.

    Features:
    - Proportional column sizing based on configurable ratios
    - Debounced resize events to prevent layout thrashing
    - Custom header styling and formatting
    - Alternating row colors for readability

    Performance characteristics:
    - Resize events are debounced (10ms delay)
    - Column adjustments use single-shot timers
    - Viewport event filtering for efficient resize handling
    - Cached column ratios to avoid recalculation
    """

    def __init__(self, original_table: QTableView) -> None:
        """
        Initialize the table view widget.

        Args:
            original_table: Reference table to copy properties from
        """
        super().__init__(original_table.parent())

        # Copy properties from original table
        self.setObjectName(original_table.objectName())
        self.setSizePolicy(original_table.sizePolicy())
        self.setMinimumSize(original_table.minimumSize())
        self.setFont(original_table.font())

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self.setAlternatingRowColors(True)

        # Hide vertical header (row numbers)
        self.verticalHeader().setVisible(False)

        # Always show scrollbars for consistent layout
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Apply custom styles
        self._apply_styles_to_table()

        # Configure horizontal header
        header = self.horizontalHeader()
        header.setFixedHeight(50)
        header.setDefaultAlignment(Qt.AlignCenter)

        # Column sizing state
        self._resize_pending = False
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_resize)
        self.column_expansion_ratios: list[int] = []

        # Install event filter on viewport for resize handling
        self.viewport().installEventFilter(self)

        logger.debug(f"TableViewWidget initialized: {self.objectName()}")

    def setModel(self, model) -> None:
        """
        Set the model and trigger initial column width adjustment.

        Args:
            model: QAbstractItemModel to display

        Performance: Uses single-shot timer to defer column adjustment
        """
        super().setModel(model)

        # Defer column adjustment to allow model to fully initialize
        QTimer.singleShot(COLUMN_ADJUST_DELAY_MS, self.adjust_column_widths)

        if model:
            logger.debug(
                f"Model set: {model.rowCount()} rows, {model.columnCount()} columns"
            )

    def set_column_expansion_ratios(self, ratios: list[int]) -> None:
        """
        Set proportional width ratios for columns.

        Args:
            ratios: List of integers representing relative column widths
                   (e.g., [2, 1, 1] makes first column twice as wide)

        Performance: Caches ratios, defers adjustment with single-shot timer
        """
        if not ratios:
            logger.warning("Empty ratios provided, ignoring")
            return

        self.column_expansion_ratios = ratios
        QTimer.singleShot(COLUMN_ADJUST_DELAY_MS, self.adjust_column_widths)

        logger.debug(f"Column ratios set: {ratios}")

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Filter viewport events to handle resize with debouncing.

        Args:
            obj: Object that received the event
            event: Event to process

        Returns:
            True if event was handled, False to propagate

        Performance: Debounces resize events to prevent layout thrashing
        """
        if obj == self.viewport() and event.type() == QEvent.Resize:
            if not self._resize_pending:
                self._resize_pending = True
                # Debounce: wait RESIZE_DEBOUNCE_MS before applying resize
                self._resize_timer.start(RESIZE_DEBOUNCE_MS)

        return super().eventFilter(obj, event)

    def _apply_styles_to_table(self) -> None:
        """
        Apply custom stylesheets to table and header.

        Performance: Called once during initialization
        """
        # Table body styling
        self.setStyleSheet(
            """
            QTableView {
                background-color: #d9d9d9;
                border: 1px solid #d6d6d6;
                gridline-color: purple;
                color: #333333;
            }
            QTableView::item:selected {
                background-color: #2b78da;
                color: white;
            }
            QTableView::item:selected:!active {
                background-color: #2b78da;
                color: white;
            }
            """
        )

        # Header styling
        self.horizontalHeader().setStyleSheet(
            """
            QHeaderView::section {
                background-color: #4ca1af;
                font-family: 'Arial';
                color: white;
                font-size: 15px;
                font-weight: bold;
                border: 1px solid #d6d6d6;
                padding: 3px 0;
            }
            """
        )

        logger.debug("Styles applied to table and header")

    def adjust_column_widths(self) -> None:
        """
        Adjust column widths based on expansion ratios.

        Distributes available viewport width proportionally according to
        column_expansion_ratios. If ratios are not set, uses equal distribution.

        Performance: O(n) where n is column count, called on resize events
        """
        model = self.model()
        if model is None:
            return

        col_count = model.columnCount()
        if col_count <= 0:
            return

        # Use configured ratios or default to equal distribution
        ratios = self.column_expansion_ratios
        if not ratios or len(ratios) != col_count:
            ratios = [1] * col_count
            if not self.column_expansion_ratios:
                # Cache default ratios for future use
                self.column_expansion_ratios = ratios

        # Calculate total available width
        total_width = self.viewport().width()
        ratio_sum = sum(ratios) or 1  # Avoid division by zero

        # Distribute width proportionally
        used_width = 0
        for col_idx in range(col_count):
            if col_idx == col_count - 1:
                # Last column gets remaining width (avoids rounding errors)
                column_width = max(0, total_width - used_width)
            else:
                # Calculate proportional width
                column_width = int(total_width * (ratios[col_idx] / ratio_sum))
                used_width += column_width

            self.setColumnWidth(col_idx, column_width)

        logger.debug(
            f"Column widths adjusted: viewport={total_width}px, "
            f"ratios={ratios}, used={used_width}px"
        )

    def _apply_resize(self) -> None:
        """
        Apply deferred resize operation (called by debounce timer).

        Performance: This method is called after debounce delay to batch
        multiple resize events into a single column adjustment
        """
        self._resize_pending = False
        self.adjust_column_widths()

    def sizeHint(self):
        """
        Provide size hint for layout management.

        Returns:
            QSize representing preferred widget size

        Performance: Uses base class implementation with cached values
        """
        hint = super().sizeHint()
        logger.debug(f"sizeHint requested: {hint.width()}x{hint.height()}")
        return hint

    def minimumSizeHint(self):
        """
        Provide minimum size hint for layout management.

        Returns:
            QSize representing minimum acceptable widget size

        Performance: Uses base class implementation
        """
        hint = super().minimumSizeHint()
        logger.debug(f"minimumSizeHint requested: {hint.width()}x{hint.height()}")
        return hint