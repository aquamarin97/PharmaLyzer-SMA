# app\views\plotting\pcr_graph_pg\interactions.py
# -*- coding: utf-8 -*-
"""
PCR Graph Custom ViewBox for Mouse Interactions.

Custom PyQtGraph ViewBox that handles:
- Hover events (delegates to renderer)
- Click selection
- Drag selection with rectangle preview
- Middle-button smooth panning
- Mouse wheel zooming

Performance optimizations:
- Direct event delegation (no processing in ViewBox)
- Smooth pan with configurable speed
- Proper event acceptance/propagation

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore

if TYPE_CHECKING:
    from .renderer import PCRGraphRendererPG

logger = logging.getLogger(__name__)


class PCRGraphViewBox(pg.ViewBox):
    """
    Custom ViewBox for PCR graph mouse interactions.

    Overrides default PyQtGraph behavior to provide:
    - Custom hover handling (no aggressive prediction)
    - Click selection with Ctrl modifier
    - Drag rectangle selection
    - Smooth middle-button panning
    - Wheel zooming with dynamic axis updates

    Performance characteristics:
    - Lightweight event delegation
    - No heavy processing in event handlers
    - Smooth pan with minimal redraws
    """

    def __init__(self, renderer: PCRGraphRendererPG) -> None:
        """
        Initialize custom ViewBox.

        Args:
            renderer: PCRGraphRendererPG instance for event delegation
        """
        super().__init__(enableMenu=False)

        self._renderer = renderer

        # Disable default mouse behavior
        self.setMouseEnabled(x=False, y=False)
        self.setAcceptHoverEvents(True)

        # State tracking
        self._drag_active = False
        self._pan_active = False
        self._pan_speed = 0.003  # Pan sensitivity
        self._last_pan_pos = None

        logger.debug("PCRGraphViewBox initialized")

    def hoverEvent(self, ev):
        """
        Handle hover events.

        Delegates to renderer for distance-threshold hover detection.

        CRITICAL: The renderer's handle_hover uses distance threshold
        via hit_test.nearest_well to prevent false hover when mouse
        is far from curves.

        Args:
            ev: Hover event

        Performance: Early returns, direct delegation
        """
        # Clear hover on exit or during drag/pan
        if ev.isExit() or self._drag_active or self._pan_active:
            self._renderer.handle_hover(None)
            return

        pos = ev.pos()
        if pos is None:
            self._renderer.handle_hover(None)
            return

        # Map to view coordinates and delegate
        # Renderer will check distance threshold in handle_hover -> nearest_well
        view_pos = self.mapToView(pos)
        self._renderer.handle_hover((view_pos.x(), view_pos.y()))

    def mouseClickEvent(self, ev):
        """
        Handle mouse click events.

        Args:
            ev: Mouse event

        Performance: Direct delegation to renderer
        """
        if ev.button() == QtCore.Qt.LeftButton:
            view = self.mapSceneToView(ev.scenePos())
            self._renderer.handle_click(
                (view.x(), view.y()),
                ctrl_pressed=bool(ev.modifiers() & QtCore.Qt.ControlModifier),
            )
            ev.accept()

    def mouseDragEvent(self, ev, axis=None):
        """
        Handle mouse drag events.

        Middle button: Smooth panning
        Left button: Rectangle selection

        Args:
            ev: Mouse drag event
            axis: Axis constraint (unused)

        Performance: Smooth pan via direct range setting
        """
        # Middle button: Smooth panning
        if ev.button() == QtCore.Qt.MiddleButton:
            if ev.isStart():
                self._pan_active = True
                self._last_pan_pos = ev.scenePos()
                ev.accept()
                return

            if not self._pan_active or self._last_pan_pos is None:
                return

            # Calculate pan delta
            delta_px = ev.scenePos() - self._last_pan_pos
            self._last_pan_pos = ev.scenePos()

            # Get current view range
            (x0, x1), (y0, y1) = self.viewRange()
            w = x1 - x0
            h = y1 - y0

            # Convert pixel delta to view space
            dx = -delta_px.x() * w * self._pan_speed
            dy = delta_px.y() * h * self._pan_speed

            # Apply pan
            self.setRange(
                xRange=(x0 + dx, x1 + dx),
                yRange=(y0 + dy, y1 + dy),
                padding=0,
            )

            ev.accept()

            if ev.isFinish():
                self._pan_active = False
                self._last_pan_pos = None

            return

        # Left button: Rectangle selection
        if ev.button() != QtCore.Qt.LeftButton:
            super().mouseDragEvent(ev, axis=axis)
            return

        self._drag_active = True

        # Map coordinates to view space
        start = self.mapSceneToView(ev.buttonDownScenePos())
        current = self.mapSceneToView(ev.scenePos())

        # Delegate to renderer
        self._renderer.handle_drag(
            (start.x(), start.y()),
            (current.x(), current.y()),
            finished=ev.isFinish(),
        )

        ev.accept()

        if ev.isFinish():
            self._drag_active = False

        # Update axes after drag
        self._renderer.update_axes_dynamically()

    def wheelEvent(self, ev, axis=None):
        """
        Handle mouse wheel events for zooming.

        Args:
            ev: Wheel event
            axis: Axis constraint (unused)

        Performance: Safe coordinate handling, dynamic axis updates
        """
        try:
            # Get wheel delta
            try:
                delta = ev.angleDelta().y()
            except AttributeError:
                delta = ev.delta() if hasattr(ev, 'delta') else 0

            if delta == 0:
                ev.ignore()
                return

            # Calculate zoom factor
            steps = delta / 120.0
            zoom_factor = 0.85 ** steps

            # Get mouse position in view space
            s_pos = ev.scenePos()
            if s_pos is None:
                return

            mouse_point = self.mapSceneToView(s_pos)

            # Validate coordinates
            if not (np.isfinite(mouse_point.x()) and np.isfinite(mouse_point.y())):
                return

            # Apply zoom
            self.scaleBy((zoom_factor, zoom_factor), center=mouse_point)

            # Update axes dynamically
            self._renderer.update_axes_dynamically()

            ev.accept()

        except Exception as e:
            logger.warning(f"wheelEvent error: {e}")
            ev.ignore()