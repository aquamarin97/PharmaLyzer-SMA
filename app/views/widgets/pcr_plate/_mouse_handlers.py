# app/views/widgets/pcr_plate/_mouse_handlers.py
# -*- coding: utf-8 -*-
"""
Mouse Event Handlers for PCR Plate Widget.

Handles mouse movement, hover tracking, click and drag selection,
range selection (Shift+Click), and header selection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt

from app.utils import well_mapping
from app.views.widgets.pcr_plate.interaction.header_select import toggle_header_selection
from app.views.widgets.pcr_plate.interaction.range_select import apply_range_selection

if TYPE_CHECKING:
    from PyQt5.QtGui import QMouseEvent

logger = logging.getLogger(__name__)

HOVER_PREDICTION_ENABLED = False
HOVER_THRESHOLD_PIXELS = 5


def handle_mouse_move(widget, event: QMouseEvent | None) -> None:
    """Handle mouse move events for hover tracking."""
    if event is None:
        return _clear_hover(widget)

    idx = widget.table.indexAt(event.pos())

    if not idx.isValid():
        return _clear_hover(widget)

    row, col = idx.row(), idx.column()

    if HOVER_PREDICTION_ENABLED:
        if not _is_mouse_near_cell(widget, event.pos(), idx):
            return _clear_hover(widget)

    if widget._drag_selection.dragging and event.buttons() & Qt.LeftButton:
        if row > 0 and col > 0:
            _continue_drag(widget, row, col)

    if row == widget._hover_row and col == widget._hover_col:
        return

    widget._hover_row = row
    widget._hover_col = col

    if widget._store is not None:
        well = well_mapping.table_index_to_well_id(row, col) if (row > 0 and col > 0) else None
        if well != widget._last_hover_well_sent:
            widget._store.set_hover(well)
            widget._last_hover_well_sent = well

    widget.table.viewport().update()


def _is_mouse_near_cell(widget, mouse_pos, cell_index) -> bool:
    """Check if mouse is close enough to cell for hover prediction."""
    if not HOVER_PREDICTION_ENABLED:
        return True

    cell_rect = widget.table.visualRect(cell_index)
    if not cell_rect.isValid():
        return False

    if cell_rect.contains(mouse_pos):
        return True

    dx = max(0, cell_rect.left() - mouse_pos.x(), mouse_pos.x() - cell_rect.right())
    dy = max(0, cell_rect.top() - mouse_pos.y(), mouse_pos.y() - cell_rect.bottom())
    distance = (dx * dx + dy * dy) ** 0.5

    return distance <= HOVER_THRESHOLD_PIXELS


def handle_mouse_press(widget, event: QMouseEvent) -> None:
    """Handle mouse press events for selection."""
    if widget._store is None:
        return

    if event.button() != Qt.LeftButton:
        return

    idx = widget.table.indexAt(event.pos())
    if not idx.isValid():
        return

    row, col = idx.row(), idx.column()
    wells = well_mapping.wells_for_header(row, col)

    if not wells:
        widget._store.clear_selection()
        widget._anchor_cell = None
        return

    if event.modifiers() & Qt.ShiftModifier and row > 0 and col > 0:
        widget._anchor_cell = apply_range_selection(
            widget._store, widget._anchor_cell, row, col, event.modifiers(),
        )
        return

    if row == 0 or col == 0:
        toggle_header_selection(widget._store, wells)
        widget._anchor_cell = None
        return

    force_mode = None
    if event.modifiers() == Qt.NoModifier and row > 0 and col > 0:
        widget._store.set_selection(wells)
        force_mode = "add"

    _start_drag(widget, row, col, wells, force_mode)


def handle_mouse_release(widget, event: QMouseEvent) -> None:
    """Handle mouse release events to end drag selection."""
    if event.button() != Qt.LeftButton:
        return

    if widget._drag_selection.dragging and widget._store is not None:
        widget._store.set_preview(set())

    widget._drag_selection.reset()


def _start_drag(widget, row, col, wells, force_mode=None) -> None:
    if widget._store is None:
        return

    selection = widget._drag_selection.start(
        row, col, wells, set(widget._store.selected_wells), force_mode,
    )
    widget._anchor_cell = widget._drag_selection.anchor_cell

    if selection is not None:
        widget._store.set_selection(selection)


def _continue_drag(widget, row: int, col: int) -> None:
    if widget._store is None or not widget._drag_selection.dragging:
        return

    if not widget._drag_selection.continue_drag(row, col):
        return

    updated_selection = widget._drag_selection.apply_from_position(row, col)
    if updated_selection is not None:
        widget._store.set_selection(updated_selection)


def _clear_hover(widget) -> None:
    if widget._hover_row is None and widget._hover_col is None:
        return

    widget._hover_row = None
    widget._hover_col = None

    if widget._store is not None and widget._last_hover_well_sent is not None:
        widget._store.set_hover(None)
        widget._last_hover_well_sent = None

    widget.table.viewport().update()