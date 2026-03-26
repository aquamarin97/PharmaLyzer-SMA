# app\utils\qt_table_utils.py
# app/utils/qt_table_utils.py
"""
Qt table ↔ pandas DataFrame conversion utilities.

Provides bidirectional conversion between Qt table models/views and
pandas DataFrames for data display and manipulation in the UI.

Usage:
    from app.utils.qt_table_utils import (
        table_view_to_dataframe,
        dataframe_to_table_model,
        update_table_cell
    )
    
    # Qt → DataFrame
    df = table_view_to_dataframe(table_widget)
    
    # DataFrame → Qt (using QStandardItemModel)
    model = dataframe_to_table_model(df)
    table_view.setModel(model)
    
    # Update single cell
    update_table_cell(table_widget, row=5, col=2, value="New Value")

Features:
    - Handles Qt.DisplayRole and Qt.EditRole
    - Preserves column headers
    - Type-aware cell creation
    - Null/empty cell handling

Note:
    These utilities work with QTableView, QTableWidget, and custom
    Qt table models that implement standard data() interface.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QTableView, QTableWidget

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class QtTableError(Exception):
    """Raised when Qt table operations fail."""
    pass


# ============================================================================
# QT → DATAFRAME CONVERSION
# ============================================================================

def table_view_to_dataframe(
    table_view: QTableView | QTableWidget,
    *,
    include_headers: bool = True
) -> pd.DataFrame:
    """
    Convert Qt table view to pandas DataFrame.
    
    Extracts data from Qt table model using Qt.DisplayRole.
    Supports both QTableView and QTableWidget.
    
    Args:
        table_view: Qt table widget or view
        include_headers: Whether to use model headers as column names
        
    Returns:
        DataFrame containing table data
        
    Raises:
        QtTableError: If table model is None or invalid
        
    Example:
        >>> # Convert table to DataFrame
        >>> df = table_view_to_dataframe(my_table)
        >>> print(df.head())
        
        >>> # Without headers (numeric column names)
        >>> df = table_view_to_dataframe(my_table, include_headers=False)
    
    Note:
        Uses Qt.DisplayRole for cell values.
        None/empty cells are preserved as pd.NA.
    """
    model = table_view.model()
    
    if model is None:
        raise QtTableError("Table model is None")
    
    rows = model.rowCount()
    cols = model.columnCount()
    
    logger.debug(f"Extracting {rows} rows × {cols} columns from Qt table")
    
    # Extract data
    data: list[list[Any]] = []
    for r in range(rows):
        row_data: list[Any] = []
        for c in range(cols):
            idx = model.index(r, c)
            value = model.data(idx, Qt.DisplayRole)
            
            # Handle None/empty values
            if value is None or value == "":
                value = pd.NA
            
            row_data.append(value)
        data.append(row_data)
    
    # Create DataFrame with or without headers
    if include_headers:
        headers = []
        for i in range(cols):
            header = model.headerData(i, Qt.Horizontal, Qt.DisplayRole)
            header_str = str(header) if header is not None else f"Col_{i}"
            headers.append(header_str)
        
        df = pd.DataFrame(data, columns=headers)
        logger.debug(f"DataFrame created with headers: {headers}")
    else:
        df = pd.DataFrame(data)
        logger.debug("DataFrame created with numeric column names")
    
    return df


def table_widget_to_dataframe(
    table_widget: QTableWidget,
    *,
    include_headers: bool = True
) -> pd.DataFrame:
    """
    Convert QTableWidget to DataFrame (specialized version).
    
    Args:
        table_widget: QTableWidget instance
        include_headers: Whether to use headers
        
    Returns:
        DataFrame containing table data
        
    Note:
        This is a convenience wrapper around table_view_to_dataframe
        specifically for QTableWidget.
    """
    return table_view_to_dataframe(table_widget, include_headers=include_headers)


# ============================================================================
# DATAFRAME → QT CONVERSION
# ============================================================================

def dataframe_to_table_model(
    df: pd.DataFrame,
    *,
    editable: bool = False
) -> QStandardItemModel:
    """
    Convert pandas DataFrame to QStandardItemModel.
    
    Creates a Qt table model from DataFrame that can be used with
    QTableView or other Qt table widgets.
    
    Args:
        df: DataFrame to convert
        editable: Whether cells should be editable
        
    Returns:
        QStandardItemModel with DataFrame data
        
    Example:
        >>> df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        >>> model = dataframe_to_table_model(df)
        >>> table_view.setModel(model)
        
        >>> # Editable model
        >>> model = dataframe_to_table_model(df, editable=True)
    
    Note:
        - Column headers are set from DataFrame columns
        - Cell flags control editability
        - NA/None values are displayed as empty strings
    """
    rows, cols = df.shape
    
    logger.debug(
        f"Creating Qt table model from DataFrame: "
        f"{rows} rows × {cols} columns"
    )
    
    model = QStandardItemModel(rows, cols)
    
    # Set column headers
    for col_idx, col_name in enumerate(df.columns):
        model.setHorizontalHeaderItem(col_idx, QStandardItem(str(col_name)))
    
    # Populate data
    for row_idx in range(rows):
        for col_idx in range(cols):
            value = df.iloc[row_idx, col_idx]
            
            # Handle NA/None values
            if pd.isna(value):
                value = ""
            
            item = QStandardItem(str(value))
            
            # Set editability
            if not editable:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            
            model.setItem(row_idx, col_idx, item)
    
    logger.debug(f"Qt table model created (editable={editable})")
    return model


# ============================================================================
# CELL OPERATIONS
# ============================================================================

def get_table_cell(
    table_view: QTableView | QTableWidget,
    row: int,
    column: int,
    role: int = Qt.DisplayRole
) -> Any:
    """
    Get value from table cell.
    
    Args:
        table_view: Qt table widget or view
        row: Row index (0-based)
        column: Column index (0-based)
        role: Qt role (default: DisplayRole)
        
    Returns:
        Cell value
        
    Raises:
        QtTableError: If model is None or indices invalid
        
    Example:
        >>> value = get_table_cell(table_widget, row=5, column=2)
        >>> print(f"Cell [5,2] = {value}")
    """
    model = table_view.model()
    
    if model is None:
        raise QtTableError("Table model is None")
    
    if row < 0 or row >= model.rowCount():
        raise QtTableError(f"Row index out of range: {row}")
    
    if column < 0 or column >= model.columnCount():
        raise QtTableError(f"Column index out of range: {column}")
    
    idx = model.index(row, column)
    return model.data(idx, role)


def update_table_cell(
    table_view: QTableView | QTableWidget,
    row: int,
    column: int,
    value: Any,
    role: int = Qt.EditRole
) -> bool:
    """
    Update value in table cell.
    
    Args:
        table_view: Qt table widget or view
        row: Row index (0-based)
        column: Column index (0-based)
        value: New cell value
        role: Qt role (default: EditRole)
        
    Returns:
        True if update successful, False otherwise
        
    Example:
        >>> success = update_table_cell(table_widget, 5, 2, "New Value")
        >>> if success:
        ...     print("Cell updated")
    """
    model = table_view.model()
    
    if model is None:
        logger.error("Cannot update cell: model is None")
        return False
    
    try:
        idx = model.index(row, column)
        success = model.setData(idx, value, role)
        
        if success:
            logger.debug(f"Updated cell [{row},{column}] = {value}")
        else:
            logger.warning(f"Failed to update cell [{row},{column}]")
        
        return success
        
    except Exception as e:
        logger.error(f"Error updating cell [{row},{column}]: {e}")
        return False


# ============================================================================
# TABLE UTILITIES
# ============================================================================

def clear_table(table_view: QTableView | QTableWidget) -> None:
    """
    Clear all data from table.
    
    Args:
        table_view: Qt table widget or view
        
    Example:
        >>> clear_table(my_table)
    """
    model = table_view.model()
    
    if model is None:
        logger.warning("Cannot clear table: model is None")
        return
    
    rows = model.rowCount()
    model.removeRows(0, rows)
    
    logger.info(f"Cleared {rows} rows from table")


def get_selected_rows(table_view: QTableView | QTableWidget) -> list[int]:
    """
    Get indices of selected rows.
    
    Args:
        table_view: Qt table widget or view
        
    Returns:
        List of selected row indices (sorted, unique)
        
    Example:
        >>> selected = get_selected_rows(table_widget)
        >>> print(f"Selected rows: {selected}")
    """
    selection = table_view.selectionModel()
    
    if selection is None:
        return []
    
    selected_rows = set()
    for index in selection.selectedIndexes():
        selected_rows.add(index.row())
    
    return sorted(selected_rows)


def get_table_dimensions(
    table_view: QTableView | QTableWidget
) -> tuple[int, int]:
    """
    Get table dimensions (rows, columns).
    
    Args:
        table_view: Qt table widget or view
        
    Returns:
        Tuple of (row_count, column_count)
        
    Raises:
        QtTableError: If model is None
        
    Example:
        >>> rows, cols = get_table_dimensions(table_widget)
        >>> print(f"Table size: {rows} × {cols}")
    """
    model = table_view.model()
    
    if model is None:
        raise QtTableError("Table model is None")
    
    return (model.rowCount(), model.columnCount())


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Qt → DataFrame
    "table_view_to_dataframe",
    "table_widget_to_dataframe",
    
    # DataFrame → Qt
    "dataframe_to_table_model",
    
    # Cell operations
    "get_table_cell",
    "update_table_cell",
    
    # Table utilities
    "clear_table",
    "get_selected_rows",
    "get_table_dimensions",
    
    # Exceptions
    "QtTableError",
]