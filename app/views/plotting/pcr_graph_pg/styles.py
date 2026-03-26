# app/views/plotting/pcr_graph_pg/styles.py
# -*- coding: utf-8 -*-
"""
PCR Graph Styling System.

Pen caching, interaction-based style updates, channel visibility management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

PenKey = tuple[str, float, float, QtCore.Qt.PenStyle]
_PEN_CACHE: dict[PenKey, QtGui.QPen] = {}


@dataclass
class InteractionStyleChange:
    """Result of applying interaction styles."""
    base_dirty: bool
    overlay_dirty: bool
    hover_segments: list[np.ndarray]
    preview_segments: list[np.ndarray]


@dataclass
class StyleState:
    """Cached style state for efficient diff calculation."""
    prev_selected: set[str] = field(default_factory=set)
    prev_preview: set[str] = field(default_factory=set)
    prev_hover: str | None = None
    initialized: bool = False


def build_pen(
    color: str,
    width: float,
    alpha: float,
    style: QtCore.Qt.PenStyle = QtCore.Qt.SolidLine,
) -> QtGui.QPen:
    """Build QPen with caching. Cosmetic pens maintain constant width during zoom."""
    key = (color, width, alpha, style)
    cached = _PEN_CACHE.get(key)
    if cached is not None:
        return cached

    color_obj = QtGui.QColor(color)
    color_obj.setAlphaF(alpha)

    pen = pg.mkPen(color=color_obj, width=width, style=style)
    pen.setCosmetic(True)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)

    _PEN_CACHE[key] = pen
    return pen


def clear_pen_cache() -> None:
    """Clear global pen cache."""
    _PEN_CACHE.clear()


def apply_interaction_styles(
    renderer,
    hovered: str | None,
    selected: set[str],
    preview: set[str],
) -> InteractionStyleChange:
    """Apply interaction-based styles to curve items."""
    if not renderer._fam_items and not renderer._hex_items:
        return InteractionStyleChange(False, False, [], [])

    if renderer._style_state is None:
        renderer._style_state = StyleState()

    state: StyleState = renderer._style_state

    base_dirty = _update_interaction_styles(renderer, selected, preview, state)

    hover_segments = _build_segments_for_wells(
        renderer, [hovered] if hovered else [],
    )

    preview_segments: list[np.ndarray] = []
    overlay_dirty = base_dirty or state.prev_hover != hovered

    state.prev_hover = hovered
    state.prev_preview = set(preview)
    state.prev_selected = set(selected)

    return InteractionStyleChange(
        base_dirty=base_dirty,
        overlay_dirty=overlay_dirty,
        hover_segments=hover_segments,
        preview_segments=preview_segments,
    )


def _update_interaction_styles(
    renderer, selected: set[str], preview: set[str], state: StyleState,
) -> bool:
    """Update base curve styles for changed wells only."""
    if not state.initialized:
        changed = set(renderer._fam_items.keys()) | set(renderer._hex_items.keys())
        state.initialized = True
    else:
        changed = (
            state.prev_selected.symmetric_difference(selected)
            | state.prev_preview.symmetric_difference(preview)
        )

    if not changed:
        return False

    for well in changed:
        _style_well(renderer, well, selected, preview)

    return True


def _style_well(
    renderer, well: str, selected: set[str], preview: set[str],
) -> None:
    """Apply style to a single well's curve items."""
    is_selected = well in selected
    is_preview = well in preview
    any_selection = len(selected) > 0

    if is_selected:
        target_alpha = 1.0
        target_width = renderer._style.selected_width
        z_value = 100
        target_style = QtCore.Qt.SolidLine
    elif is_preview:
        target_alpha = 1.0
        target_width = renderer._style.overlay_preview_width
        z_value = 80
        target_style = QtCore.Qt.DashLine
    elif any_selection:
        target_alpha = renderer._style.inactive_alpha
        target_width = renderer._style.base_width
        z_value = 1
        target_style = QtCore.Qt.SolidLine
    else:
        target_alpha = 0.8
        target_width = renderer._style.base_width
        z_value = 10
        target_style = QtCore.Qt.SolidLine

    fam_item = renderer._fam_items.get(well)
    if fam_item:
        pen = build_pen(renderer._style.fam_color, target_width, target_alpha, target_style)
        fam_item.setPen(pen)
        fam_item.setZValue(z_value)
        fam_item.setVisible(renderer._fam_visible and bool(fam_item.property("has_data")))

    hex_item = renderer._hex_items.get(well)
    if hex_item:
        pen = build_pen(renderer._style.hex_color, target_width, target_alpha, target_style)
        hex_item.setPen(pen)
        hex_item.setZValue(z_value)


def _build_segments_for_wells(renderer, wells: list[str]) -> list[np.ndarray]:
    """Build curve segments for specified wells (for hover overlay)."""
    segments: list[np.ndarray] = []

    for well in wells:
        coords = renderer._well_geoms.get(well)
        if not coords:
            continue

        if renderer._fam_visible:
            fam_coords = coords.get("fam")
            if fam_coords is not None and fam_coords.size > 0:
                segments.append(fam_coords)

        if renderer._hex_visible:
            hex_coords = coords.get("hex")
            if hex_coords is not None and hex_coords.size > 0:
                segments.append(hex_coords)

    return segments


def set_channel_visibility(
    renderer,
    fam_visible: bool | None = None,
    hex_visible: bool | None = None,
) -> bool:
    """Update channel visibility. Returns True if changed."""
    fam_changed = fam_visible is not None and bool(fam_visible) != renderer._fam_visible
    hex_changed = hex_visible is not None and bool(hex_visible) != renderer._hex_visible

    if not fam_changed and not hex_changed:
        return False

    if fam_changed:
        renderer._fam_visible = bool(fam_visible)

    if hex_changed:
        renderer._hex_visible = bool(hex_visible)

    for item in renderer._fam_items.values():
        item.setVisible(renderer._fam_visible and bool(item.property("has_data")))

    for item in renderer._hex_items.values():
        item.setVisible(renderer._hex_visible and bool(item.property("has_data")))

    logger.info("Channel visibility: FAM=%s, HEX=%s", renderer._fam_visible, renderer._hex_visible)
    return True