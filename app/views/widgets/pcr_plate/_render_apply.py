# app/views/widgets/pcr_plate/_render_apply.py
# -*- coding: utf-8 -*-
"""
Render State Application for PCR Plate Widget.

Applies InteractionStore state changes to the PCR plate table with
partial viewport updates for performance.
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt

from app.utils import well_mapping

logger = logging.getLogger(__name__)


def on_selection_changed(widget, selected_wells: set[str]) -> None:
    """Apply selection changes to table cells (only changed cells)."""
    if widget is None:
        return

    prev_selection = widget._last_selected_wells
    new_selection = set(selected_wells or set())

    added_wells = new_selection - prev_selection
    removed_wells = prev_selection - new_selection

    if not added_wells and not removed_wells:
        return

    for well_id in added_wells:
        _apply_well_selection(widget, well_id, is_selected=True)

    for well_id in removed_wells:
        _apply_well_selection(widget, well_id, is_selected=False)

    widget._last_selected_wells = new_selection
    _update_header_selection(widget, new_selection)


def _apply_well_selection(widget, well_id: str, is_selected: bool) -> None:
    """Apply selection state to a single well."""
    try:
        row, col = well_mapping.well_id_to_table_index(well_id)
    except ValueError:
        return

    item = widget.table.item(row, col)
    if item is None:
        return

    if is_selected:
        item.setBackground(widget.COLOR_SELECTED)
        item.setForeground(Qt.white)
    else:
        base_color = widget._well_base_colors.get((row, col), widget.COLOR_BASE)
        item.setBackground(base_color)
        item.setForeground(Qt.black)


def _update_header_selection(widget, selected_wells: set[str]) -> None:
    """Update header selection state for rows and columns."""
    selected_rows = set()
    selected_cols = set()

    for row_idx in range(1, len(well_mapping.ROWS) + 1):
        row_wells = well_mapping.wells_for_header(row_idx, 0)
        if row_wells and row_wells.issubset(selected_wells):
            selected_rows.add(row_idx)

    for col_idx in range(1, len(well_mapping.COLUMNS) + 1):
        col_wells = well_mapping.wells_for_header(0, col_idx)
        if col_wells and col_wells.issubset(selected_wells):
            selected_cols.add(col_idx)

    widget.table.set_selected_headers(selected_rows, selected_cols)


def on_hover_changed(widget, well: str | None) -> None:
    """Apply hover state change to widget."""
    if widget is None:
        return

    if well is None:
        if widget._hover_row is None and widget._hover_col is None:
            return
        widget._hover_row = None
        widget._hover_col = None
        widget.table.viewport().update()
        return

    try:
        row, col = well_mapping.well_id_to_table_index(well)
    except ValueError:
        row, col = None, None

    if row == widget._hover_row and col == widget._hover_col:
        return

    widget._hover_row = row
    widget._hover_col = col
    widget.table.viewport().update()


def on_preview_changed(widget, wells: set[str]) -> None:
    """Apply preview wells to widget."""
    if widget is None:
        return

    preview_cells = set()
    for well_id in (wells or set()):
        try:
            cell_pos = well_mapping.well_id_to_table_index(well_id)
            preview_cells.add(cell_pos)
        except ValueError:
            continue

    widget._preview_cells = preview_cells
    widget.table.set_preview_cells(preview_cells)


def clear_all_visual_state(widget) -> None:
    """Clear all visual state (selection, hover, preview)."""
    if widget is None:
        return

    widget._last_selected_wells.clear()
    widget._hover_row = None
    widget._hover_col = None
    widget._preview_cells.clear()

    widget.table.set_selected_headers(set(), set())
    widget.table.set_preview_cells(set())

    for row in range(1, len(well_mapping.ROWS) + 1):
        for col in range(1, len(well_mapping.COLUMNS) + 1):
            item = widget.table.item(row, col)
            if item:
                base_color = widget._well_base_colors.get((row, col), widget.COLOR_BASE)
                item.setBackground(base_color)
                item.setForeground(Qt.black)

    widget.table.viewport().update()