# app/views/plotting/pcr_graph_pg/interaction_handlers_pg.py
# -*- coding: utf-8 -*-
"""
PCR Graph Interaction Handler Functions.

Handler functions for mouse interactions:
- Hover with distance threshold
- Click selection (single/multi with Ctrl)
- Drag rectangle selection with preview
- Store synchronization
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING

from .hit_test import nearest_well, wells_in_rect
from .overlays_pg import update_overlays
from .render_scheduler_pg import schedule_render

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def pixel_tol_in_data(renderer) -> tuple[float, float]:
    """Get tolerance in data space from viewport pixel size."""
    pixel = renderer._view_box.viewPixelSize()
    if pixel is None:
        return 0.0, 0.0
    return abs(pixel[0]), abs(pixel[1])


def collect_preview_wells(renderer) -> set[str]:
    """Collect preview wells from store or local state."""
    if renderer._store is not None:
        return set(renderer._store.preview_wells)
    return set(renderer._rect_preview_wells)


def set_rect_preview(renderer, wells: set[str]) -> None:
    """Update rectangle preview wells."""
    if wells == renderer._rect_preview_wells:
        return

    renderer._rect_preview_wells = wells

    if renderer._store is not None:
        renderer._store.set_preview(wells)

    renderer._update_preview_proxy(wells)

    change = renderer._apply_interaction_styles(
        hovered=renderer._hover_well,
        selected=set(renderer._store.selected_wells) if renderer._store else set(),
        preview=collect_preview_wells(renderer),
    )

    update_overlays(renderer, change)


def on_store_preview_changed(renderer, wells: set[str]) -> None:
    """Handle store preview change event."""
    renderer._rect_preview_wells = set(wells or set())
    renderer._update_preview_proxy(renderer._rect_preview_wells)

    change = renderer._apply_interaction_styles(
        hovered=renderer._hover_well,
        selected=set(renderer._store.selected_wells) if renderer._store else set(),
        preview=collect_preview_wells(renderer),
    )

    update_overlays(renderer, change)
    schedule_render(renderer, full=False, overlay=True)


def handle_hover(renderer, pos: tuple[float, float] | None) -> None:
    """Handle hover event with distance threshold."""
    if pos is None:
        _clear_hover(renderer)
        return

    x, y = pos
    tol_x, tol_y = pixel_tol_in_data(renderer)

    well = nearest_well(
        renderer._spatial_index,
        renderer._well_geoms,
        x, y, tol_x, tol_y,
        fam_visible=renderer._fam_visible,
        hex_visible=renderer._hex_visible,
    )

    if renderer._store is not None:
        if renderer._store.hover_well != well:
            renderer._store.set_hover(well)
    else:
        renderer.set_hover(well)


def _clear_hover(renderer):
    """Clear hover state."""
    if renderer._store is not None:
        renderer._store.set_hover(None)
    else:
        renderer.set_hover(None)


def handle_click(renderer, pos: tuple[float, float], *, ctrl_pressed: bool) -> None:
    """Handle click selection."""
    if renderer._store is None:
        return

    x, y = pos
    tol_x, tol_y = pixel_tol_in_data(renderer)

    well = nearest_well(
        renderer._spatial_index,
        renderer._well_geoms,
        x, y, tol_x, tol_y,
        fam_visible=renderer._fam_visible,
        hex_visible=renderer._hex_visible,
    )

    if well is None:
        return

    if ctrl_pressed:
        renderer._store.toggle_wells({well})
    else:
        current = set(renderer._store.selected_wells)
        if well in current:
            renderer._store.toggle_wells({well})
        else:
            renderer._store.set_selection({well})


def handle_drag(
    renderer,
    start: tuple[float, float],
    current: tuple[float, float],
    *,
    finished: bool,
) -> None:
    """Handle drag selection with throttling."""
    if finished:
        if renderer._drag_throttle_timer.isActive():
            renderer._drag_throttle_timer.stop()

        renderer._pending_drag = None
        renderer._last_drag_ts = perf_counter()
        _apply_drag_update(renderer, start, current, finished=True)
        return

    now = perf_counter()
    elapsed_ms = (now - renderer._last_drag_ts) * 1000.0

    if elapsed_ms < renderer._drag_throttle_ms:
        renderer._pending_drag = (start, current)
        if not renderer._drag_throttle_timer.isActive():
            wait_ms = max(0, int(renderer._drag_throttle_ms - elapsed_ms))
            renderer._drag_throttle_timer.start(wait_ms)
        return

    renderer._last_drag_ts = now
    _apply_drag_update(renderer, start, current, finished=False)


def flush_pending_drag(renderer) -> None:
    """Flush pending drag update (called by throttle timer)."""
    pending = renderer._pending_drag
    renderer._pending_drag = None

    if pending is None:
        return

    start, current = pending
    renderer._last_drag_ts = perf_counter()
    _apply_drag_update(renderer, start, current, finished=False)


def _apply_drag_update(
    renderer,
    start: tuple[float, float],
    current: tuple[float, float],
    *,
    finished: bool,
) -> None:
    """Apply drag rectangle update."""
    x0, y0 = start
    x1, y1 = current

    rect_x = min(x0, x1)
    rect_y = min(y0, y1)
    w = abs(x1 - x0)
    h = abs(y1 - y0)

    renderer._rect_roi.setPos((rect_x, rect_y))
    renderer._rect_roi.setSize((w, h))
    renderer._rect_roi.setVisible(not finished)

    if finished:
        set_rect_preview(renderer, set())
        schedule_render(renderer, full=False, overlay=True)
        return

    wells = wells_in_rect(
        renderer._spatial_index,
        renderer._well_geoms,
        x0, x1, y0, y1,
        fam_visible=renderer._fam_visible,
        hex_visible=renderer._hex_visible,
    )

    set_rect_preview(renderer, wells)
    schedule_render(renderer, full=False, overlay=True)