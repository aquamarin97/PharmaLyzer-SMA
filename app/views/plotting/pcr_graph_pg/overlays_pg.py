# app/views/plotting/pcr_graph_pg/overlays_pg.py
# -*- coding: utf-8 -*-
"""
PCR Graph Overlay Rendering.

Hover and preview overlay rendering with NaN-separated segment concatenation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def build_overlay(*, pen: QtGui.QPen) -> pg.PlotDataItem:
    """Create overlay PlotDataItem with specified pen."""
    item = pg.PlotDataItem(pen=pen, connect="finite")
    item.setZValue(30)
    item.setVisible(False)
    return item


def segments_to_xy_with_nans(segments: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate curve segments with NaN separators."""
    if not segments:
        return np.array([]), np.array([])

    xs_list = []
    ys_list = []

    for seg in segments:
        if seg is None or seg.size == 0:
            continue
        xs_list.append(seg[:, 0])
        ys_list.append(seg[:, 1])
        xs_list.append(np.array([np.nan]))
        ys_list.append(np.array([np.nan]))

    if not xs_list:
        return np.array([]), np.array([])

    return np.concatenate(xs_list), np.concatenate(ys_list)


def update_overlays(renderer, change) -> None:
    """Update hover and preview overlays based on interaction changes."""
    if change.hover_segments:
        xs, ys = segments_to_xy_with_nans(change.hover_segments)
        renderer._hover_overlay.setData(xs, ys)
        renderer._hover_overlay.setVisible(True)
    else:
        renderer._hover_overlay.setData([], [])
        renderer._hover_overlay.setVisible(False)

    if getattr(renderer, "_use_preview_proxy", False):
        renderer._preview_overlay.setData([], [])
        renderer._preview_overlay.setVisible(False)
        return

    if change.preview_segments:
        xs, ys = segments_to_xy_with_nans(change.preview_segments)
        renderer._preview_overlay.setData(xs, ys)
        renderer._preview_overlay.setVisible(True)
    else:
        renderer._preview_overlay.setData([], [])
        renderer._preview_overlay.setVisible(False)


def make_hover_pen(renderer) -> QtGui.QPen:
    return pg.mkPen(renderer._style.overlay_color, width=renderer._style.overlay_hover_width)


def make_preview_pen(renderer) -> QtGui.QPen:
    return pg.mkPen(renderer._style.overlay_color, width=renderer._style.overlay_preview_width, style=QtCore.Qt.DashLine)


def clear_overlays(renderer) -> None:
    """Clear all overlays."""
    renderer._hover_overlay.setData([], [])
    renderer._hover_overlay.setVisible(False)
    renderer._preview_overlay.setData([], [])
    renderer._preview_overlay.setVisible(False)