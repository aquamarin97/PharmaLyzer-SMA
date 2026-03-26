# app\views\table\editable_table_model.py
# -*- coding: utf-8 -*-
"""
Editable Table Model for PCR Analysis Results.

This module provides a custom QAbstractTableModel implementation with:
- Efficient data change signaling (minimal dataChanged emissions)
- Cached color calculations for performance
- Conditional background coloring based on data thresholds
- Editable dropdown column support
- Patient number lookup helpers for controller integration

Performance optimizations:
- Signal batching via blockSignals()
- Early return on unchanged data (setData)
- Cached QBrush objects to avoid repeated QColor creation
- Shallow DataFrame copy for UI layer

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QBrush, QColor

logger = logging.getLogger(__name__)


class EditableTableModel(QAbstractTableModel):
    """
    Custom table model for PCR analysis results with conditional formatting.

    Features:
    - Background color coding based on value thresholds
    - Editable dropdown column for status selection
    - Efficient data change signals (only emit when data actually changes)
    - Patient number lookup for controller coordination

    Performance characteristics:
    - O(1) data access via pandas iloc
    - Cached QBrush objects for repeated colors
    - Minimal dataChanged signal emissions
    - Shallow DataFrame copy to avoid memory overhead
    """

    # Display constants
    INSUFFICIENT_DNA = "Yetersiz DNA"
    EMPTY_WELL = "Boş Kuyu"
    OUTLIER = "Riskli Alan"
    SAFE_ZONE = "Güvenli Bölge"
    PATIENT_NO_COL = "Hasta No"

    def __init__(
        self,
        data: pd.DataFrame,
        dropdown_column: int,
        dropdown_options: list[str],
        carrier_range: float,
        uncertain_range: float,
    ) -> None:
        """
        Initialize the editable table model.

        Args:
            data: Source DataFrame (shallow copied for UI)
            dropdown_column: Column index for editable dropdown
            dropdown_options: List of dropdown choices
            carrier_range: Lower threshold for carrier detection
            uncertain_range: Upper threshold for uncertain zone
        """
        super().__init__()
        
        # Shallow copy is sufficient for UI layer (no deep data mutation)
        self._data = data.copy(deep=False)
        self.headers = list(self._data.columns)

        self.dropdown_column = dropdown_column
        self.dropdown_options = dropdown_options

        # Threshold configuration
        self.carrier_range = float(carrier_range)
        self.uncertain_range = float(uncertain_range)

        # Cached brushes for performance (avoid repeated QColor/QBrush creation)
        self._brush_cache = self._initialize_brush_cache()

        logger.debug(
            f"EditableTableModel initialized: {len(self._data)} rows, "
            f"{len(self._data.columns)} columns, dropdown_column={dropdown_column}"
        )

    def _initialize_brush_cache(self) -> dict[str, QBrush]:
        """
        Pre-create QBrush objects to avoid repeated instantiation.

        Returns:
            Dictionary mapping color keys to QBrush objects

        Performance: Creates brushes once instead of on every paint event.
        """
        return {
            "green": QBrush(QColor("#A9D08E")),  # Safe/Pass
            "yellow": QBrush(QColor("#FFE599")),  # Warning/Carrier
            "orange": QBrush(QColor("#E87E2C")),  # Caution/Uncertain
            "red": QBrush(QColor("#FF6B6B")),     # Critical
            "purple": QBrush(QColor("#B4A7D6")),  # Special
            "red_orange": QBrush(QColor(230, 90, 50)),  # Outlier warning
        }

    def setHorizontalHeaderLabels(self, headers: list[str]) -> None:
        """
        Update horizontal header labels.

        Args:
            headers: New header labels (must match column count)
        """
        if len(headers) != self.columnCount():
            logger.warning(
                f"Header count mismatch: expected {self.columnCount()}, "
                f"got {len(headers)}"
            )
            return

        self.headers = headers
        # Emit header data change for proper UI update
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(headers) - 1)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        """
        Return header data for the given section.

        Args:
            section: Row or column index
            orientation: Horizontal or vertical
            role: Data role (DisplayRole, etc.)

        Returns:
            Header label or None
        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.headers):
                return self.headers[section]
        return super().headerData(section, orientation, role)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of rows (data records)."""
        if parent.isValid():  # Flat table, no tree structure
            return 0
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of columns."""
        if parent.isValid():  # Flat table, no tree structure
            return 0
        return len(self._data.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """
        Return data for the given index and role.

        Args:
            index: Cell position
            role: Data role (DisplayRole, BackgroundRole, etc.)

        Returns:
            Requested data or None

        Performance: Early return on invalid index, role-based dispatch
        """
        if not index.isValid():
            return None

        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._get_display_data(index)

        if role == Qt.BackgroundRole:
            return self._get_background_brush(index)

        return None

    def _get_display_data(self, index: QModelIndex) -> str:
        """
        Get display text for a cell.

        Args:
            index: Cell position

        Returns:
            Formatted string for display

        Performance: Direct iloc access is O(1)
        """
        value = self._data.iloc[index.row(), index.column()]

        # Handle missing values with context-aware placeholders
        if pd.isna(value):
            column_name = self._data.columns[index.column()]
            if column_name in ("İstatistik Oranı", "Standart Oranı"):
                return "-"
            return ""

        return str(value)

    def _get_background_brush(self, index: QModelIndex) -> QBrush | None:
        """
        Determine background color for a cell based on value and column type.

        Args:
            index: Cell position

        Returns:
            QBrush for background or None for default

        Performance: Uses cached brushes, early returns
        """
        col = index.column()
        value = self._data.iloc[index.row(), col]

        # Dropdown column: status-based coloring
        if col == self.dropdown_column:
            return self._get_dropdown_brush(str(value))

        # Threshold columns: numeric range coloring
        for column_name in ("İstatistik Oranı", "Standart Oranı"):
            if column_name in self._data.columns:
                if col == self._data.columns.get_loc(column_name):
                    return self._get_threshold_brush(value)

        # Regression column: categorical coloring
        if "Regresyon" in self._data.columns:
            if col == self._data.columns.get_loc("Regresyon"):
                return self._get_regression_brush(str(value))

        return None

    def _get_dropdown_brush(self, value: str) -> QBrush | None:
        """
        Get background brush for dropdown column based on selected option.

        Args:
            value: Selected dropdown value

        Returns:
            Cached QBrush or None

        Performance: Dictionary lookup + cached brushes
        """
        if not self.dropdown_options:
            return None

        # Map dropdown index to color semantics
        try:
            idx = self.dropdown_options.index(value)
            color_map = {
                0: "green",    # Pass/Safe
                1: "yellow",   # Warning
                2: "orange",   # Caution
                3: "purple",   # Special
                4: "red",      # Critical
            }
            color_key = color_map.get(idx)
            return self._brush_cache.get(color_key) if color_key else None
        except ValueError:
            return None

    def _get_threshold_brush(self, value: Any) -> QBrush | None:
        """
        Get background brush based on numeric threshold ranges.

        Args:
            value: Numeric value to evaluate

        Returns:
            Cached QBrush or None

        Performance: Try-except faster than type checking, cached brushes
        """
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return None

        # Threshold logic: uncertain_range > uncertain > carrier_range
        if numeric_value >= self.uncertain_range:
            return self._brush_cache["green"]  # Safe zone
        if self.carrier_range < numeric_value < self.uncertain_range:
            return self._brush_cache["orange"]  # Uncertain zone
        if numeric_value <= self.carrier_range:
            return self._brush_cache["yellow"]  # Carrier zone

        return None

    def _get_regression_brush(self, value: str) -> QBrush | None:
        """
        Get background brush for regression analysis results.

        Args:
            value: Regression result string

        Returns:
            Cached QBrush or None
        """
        if value == self.OUTLIER:
            return self._brush_cache["red_orange"]
        if value == self.SAFE_ZONE:
            return self._brush_cache["green"]
        return None

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.EditRole,
    ) -> bool:
        """
        Update cell data (only for editable dropdown column).

        Args:
            index: Cell position
            value: New value
            role: Edit role

        Returns:
            True if data changed, False otherwise

        Performance: Early returns, minimal signal emission
        """
        if role != Qt.EditRole or not index.isValid():
            return False

        # Only dropdown column is editable
        if index.column() != self.dropdown_column:
            return False

        # CRITICAL: Check if data actually changed before emitting signal
        old_value = self._data.iloc[index.row(), index.column()]
        if old_value == value:
            logger.debug(f"setData: No change for row {index.row()}, skipping signal")
            return False

        # Update data
        self._data.iloc[index.row(), index.column()] = value

        # Emit dataChanged with all affected roles (display, edit, background)
        # This ensures dropdown color updates correctly
        self.dataChanged.emit(
            index,
            index,
            [Qt.DisplayRole, Qt.EditRole, Qt.BackgroundRole],
        )

        logger.debug(
            f"setData: Updated row {index.row()}, col {index.column()} "
            f"from '{old_value}' to '{value}'"
        )
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """
        Return item flags for the given index.

        Args:
            index: Cell position

        Returns:
            Qt.ItemFlags indicating enabled/editable state
        """
        if not index.isValid():
            return Qt.ItemIsEnabled

        flags = super().flags(index)

        # Only dropdown column is editable
        if index.column() == self.dropdown_column:
            flags |= Qt.ItemIsEditable

        return flags

    def set_dataframe(
        self,
        df: pd.DataFrame,
        *,
        dropdown_column: int | None = None,
        carrier_range: float | None = None,
        uncertain_range: float | None = None,
        dropdown_options: list[str] | None = None,
    ) -> None:
        """
        Replace entire DataFrame and optionally update configuration.

        Args:
            df: New DataFrame
            dropdown_column: New dropdown column index (optional)
            carrier_range: New carrier threshold (optional)
            uncertain_range: New uncertain threshold (optional)
            dropdown_options: New dropdown options (optional)

        Performance: Uses beginResetModel/endResetModel for efficient bulk update
        """
        # Signal model reset (efficient for bulk data changes)
        self.beginResetModel()

        self._data = df.copy(deep=False)
        self.headers = list(self._data.columns)

        # Update configuration if provided
        if dropdown_column is not None:
            self.dropdown_column = dropdown_column
        if dropdown_options is not None:
            self.dropdown_options = dropdown_options
        if carrier_range is not None:
            self.carrier_range = float(carrier_range)
        if uncertain_range is not None:
            self.uncertain_range = float(uncertain_range)

        self.endResetModel()

        logger.info(
            f"DataFrame replaced: {len(self._data)} rows, {len(self._data.columns)} cols"
        )

    # ---- Controller Helper Methods ----

    def get_patient_no(self, row: int) -> str | None:
        """
        Get patient number for the given row.

        Args:
            row: Row index

        Returns:
            Patient number or None if not found/invalid

        Used by: TableInteractionController for patient selection coordination
        """
        if not (0 <= row < len(self._data)):
            return None

        if self.PATIENT_NO_COL not in self._data.columns:
            return None

        col_idx = self._data.columns.get_loc(self.PATIENT_NO_COL)
        value = self._data.iloc[row, col_idx]

        # Treat empty/placeholder values as None
        # Note: pd.isna() handles pd.NA, None, NaN properly
        if pd.isna(value) or value in ("", "-"):
            return None

        return str(value)

    def get_patient_no_column_index(self) -> int | None:
        """
        Get column index of patient number column.

        Returns:
            Column index or None if column doesn't exist

        Used by: Controllers for patient number column identification
        """
        if self.PATIENT_NO_COL not in self._data.columns:
            return None

        return int(self._data.columns.get_loc(self.PATIENT_NO_COL))