# app\views\plotting\regression\interaction.py
# -*- coding: utf-8 -*-
"""
Regression Plot Interaction Handler.

This module manages mouse interactions for regression plots:
- Hover detection with distance threshold
- Click selection (single/multi with Ctrl)
- Hover text display
- Store synchronization

CRITICAL PERFORMANCE & UX FIX:
- Distance threshold prevents hover on distant points
- Rate-limited hover updates (60 FPS max)
- Efficient nearest-point search
- No ghost hover effects when mouse far from plot

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtGui
from PyQt5.QtCore import Qt

from app.i18n import t
from app.views.plotting.regression.adapters import HoverPoints

if TYPE_CHECKING:
    from app.services.interaction_store import InteractionStore

logger = logging.getLogger(__name__)

# Hover configuration
HOVER_RATE_LIMIT_FPS = 60  # Maximum hover update rate
HOVER_DISTANCE_THRESHOLD_PERCENT = 0.01  # 1% of visible range


class RegressionInteraction:
    """
    Interaction handler for regression plots.

    Manages:
    - Hover detection with distance threshold
    - Click selection (replace or toggle with Ctrl)
    - Hover text display with styled HTML
    - Signal proxy for rate-limited hover updates

    Performance characteristics:
    - Rate-limited hover (60 FPS max)
    - Distance threshold prevents false positives
    - Efficient numpy nearest-neighbor search
    - Single store update per interaction
    """

    def __init__(self) -> None:
        """Initialize regression interaction handler."""
        self._hover_proxy = None
        self._click_proxy = None
        self._store: InteractionStore | None = None
        self._hover_points: HoverPoints = HoverPoints.empty()

        logger.debug("RegressionInteraction initialized")

    def attach(
        self,
        plot_item: pg.PlotItem,
        hover_text_item: pg.TextItem,
        hover_points: HoverPoints,
        interaction_store: InteractionStore | None,
    ) -> None:
        """
        Attach interaction handlers to plot.

        Args:
            plot_item: PyQtGraph PlotItem to attach to
            hover_text_item: TextItem for hover display
            hover_points: HoverPoints for nearest-point search
            interaction_store: InteractionStore for state management

        Performance: Two signal connections, one for hover (rate-limited),
        one for click
        """
        # Detach any existing handlers
        self.detach()

        self._store = interaction_store
        self._hover_points = hover_points

        # Early return if no hover points
        if hover_points.is_empty:
            hover_text_item.hide()
            logger.debug("No hover points, interaction disabled")
            return

        # Attach hover and click handlers
        self._attach_hover(plot_item, hover_text_item)
        self._attach_click(plot_item, hover_text_item)

        logger.info(
            f"Interaction attached: {hover_points.x.size} hover points, "
            f"rate_limit={HOVER_RATE_LIMIT_FPS} FPS"
        )

    def detach(self) -> None:
        """
        Detach all interaction handlers.

        Safely disconnects signals and clears state.

        Performance: Handles exceptions gracefully, no crashes on missing signals
        """
        for proxy in (self._hover_proxy, self._click_proxy):
            if proxy is None:
                continue

            try:
                if hasattr(proxy, "disconnect"):
                    proxy.disconnect()
                elif isinstance(proxy, tuple) and len(proxy) == 2:
                    signal, slot = proxy
                    signal.disconnect(slot)
            except Exception as e:
                logger.debug(f"Error disconnecting proxy: {e}")

        self._hover_proxy = None
        self._click_proxy = None
        self._store = None
        self._hover_points = HoverPoints.empty()

        logger.debug("Interaction detached")

    # ---- Hover Handling ----

    def _attach_hover(
        self,
        plot_item: pg.PlotItem,
        hover_text_item: pg.TextItem,
    ) -> None:
        """
        Attach hover handler with rate limiting.

        Args:
            plot_item: PlotItem to monitor
            hover_text_item: TextItem to display hover info

        Performance: Rate-limited to HOVER_RATE_LIMIT_FPS via SignalProxy
        """
        view_box = plot_item.vb

        def on_mouse_moved(evt):
            """
            Handle mouse move events for hover.

            Args:
                evt: Mouse event tuple from SignalProxy

            Performance: Distance check prevents false positives
            """
            pos = evt[0]

            # Check if mouse is inside plot area
            if not view_box.sceneBoundingRect().contains(pos):
                hover_text_item.hide()
                if self._store is not None:
                    self._store.set_hover(None)
                return

            # Map scene coordinates to view coordinates
            mouse_point = view_box.mapSceneToView(pos)
            mx, my = float(mouse_point.x()), float(mouse_point.y())

            # Find nearest well with distance threshold
            well_idx = self._nearest_well_index(mx, my, plot_item)

            if well_idx is None:
                # No well within threshold distance
                hover_text_item.hide()
                if self._store is not None:
                    self._store.set_hover(None)
                return

            # Get well ID
            well = (
                self._hover_points.wells[well_idx]
                if well_idx < self._hover_points.wells.size
                else ""
            )

            # Update hover text with styled HTML
            self._show_hover_text(
                hover_text_item,
                well,
                self._hover_points.x[well_idx],
                self._hover_points.y[well_idx],
            )

            # Update store
            if self._store is not None:
                self._store.set_hover(well)

        # Create rate-limited signal proxy
        self._hover_proxy = pg.SignalProxy(
            plot_item.scene().sigMouseMoved,
            rateLimit=HOVER_RATE_LIMIT_FPS,
            slot=on_mouse_moved,
        )

        logger.debug("Hover handler attached with rate limiting")

    def _show_hover_text(
        self,
        hover_text_item: pg.TextItem,
        well: str,
        x: float,
        y: float,
    ) -> None:
        """
        Display hover text with styled HTML.

        Args:
            hover_text_item: TextItem to update
            well: Well ID to display
            x: X coordinate for text position
            y: Y coordinate for text position

        Performance: HTML string creation, single setHtml call
        """
        # Style configuration
        text_color = "#FFFFFF"  # White text
        bg_color = "rgba(40, 44, 52, 200)"  # Semi-transparent dark
        border_color = "#FFD700"  # Gold border

        # Get translated well text
        well_text = t("regression.plot.hover.well_no", well=well)

        # Build styled HTML
        html_text = (
            f'<div style="background-color: {bg_color}; '
            f'border: 1px solid {border_color}; '
            f'border-radius: 4px; '
            f'padding: 3px 6px;">'
            f'<span style="color: {text_color}; font-weight: bold; font-family: Arial;">'
            f'{well_text}'
            f'</span></div>'
        )

        hover_text_item.setHtml(html_text)
        hover_text_item.setPos(float(x), float(y))
        hover_text_item.show()

    # ---- Click Handling ----

    def _attach_click(
        self,
        plot_item: pg.PlotItem,
        hover_text_item: pg.TextItem,
    ) -> None:
        """
        Attach click handler for well selection.

        Args:
            plot_item: PlotItem to monitor
            hover_text_item: TextItem to update on click

        Performance: Direct signal connection, no rate limiting needed
        """
        view_box = plot_item.vb

        def on_mouse_clicked(mouse_evt: QtGui.QGraphicsSceneMouseEvent):
            """
            Handle mouse click events for selection.

            Args:
                mouse_evt: Mouse click event

            Behavior:
            - Left click: Replace selection with clicked well
            - Ctrl+Left click: Toggle clicked well in selection

            Performance: Distance check, single store update
            """
            # Only handle left clicks
            if mouse_evt.button() != Qt.LeftButton:
                return

            pos = mouse_evt.scenePos()

            # Check if click is inside plot area
            if not view_box.sceneBoundingRect().contains(pos):
                return

            # Map scene coordinates to view coordinates
            mouse_point = view_box.mapSceneToView(pos)
            mx, my = float(mouse_point.x()), float(mouse_point.y())

            # Find nearest well with distance threshold
            well_idx = self._nearest_well_index(mx, my, plot_item)

            if well_idx is not None:
                # Well clicked within threshold
                well = (
                    self._hover_points.wells[well_idx]
                    if well_idx < self._hover_points.wells.size
                    else ""
                )

                if self._store is not None:
                    # Check for Ctrl modifier
                    if mouse_evt.modifiers() & Qt.ControlModifier:
                        # Toggle well in selection
                        self._store.toggle_wells({well})
                    else:
                        # Replace selection with this well
                        self._store.set_selection({well})

                    # Update hover to clicked well
                    self._store.set_hover(well)

                # Update hover text at click position
                self._show_hover_text(
                    hover_text_item,
                    well,
                    self._hover_points.x[well_idx],
                    self._hover_points.y[well_idx],
                )

                mouse_evt.accept()
                logger.debug(f"Well clicked: {well}, ctrl={bool(mouse_evt.modifiers() & Qt.ControlModifier)}")
                return

            # Click on empty area - clear selection
            if self._store is not None:
                self._store.clear_selection()
                self._store.set_hover(None)

            hover_text_item.hide()
            logger.debug("Empty area clicked, selection cleared")

        # Connect click signal
        plot_item.scene().sigMouseClicked.connect(on_mouse_clicked)
        self._click_proxy = (plot_item.scene().sigMouseClicked, on_mouse_clicked)

        logger.debug("Click handler attached")

    # ---- Nearest Point Search ----

    def _nearest_well_index(
        self,
        mx: float,
        my: float,
        plot_item: pg.PlotItem,
    ) -> int | None:
        """
        Find nearest well index to mouse position with distance threshold.

        CRITICAL: Distance threshold prevents hover on distant points.
        This fixes ghost hover effects when mouse is far from plot.

        Args:
            mx: Mouse X coordinate (view space)
            my: Mouse Y coordinate (view space)
            plot_item: PlotItem for view range calculation

        Returns:
            Well index if within threshold, None otherwise

        Performance: O(n) numpy operations where n is number of points,
        but typically fast due to vectorization

        Algorithm:
        1. Calculate squared distance to all points
        2. Find minimum distance point
        3. Check if distance < threshold (1% of visible range)
        4. Return index if within threshold, None otherwise
        """
        # Calculate squared distances (avoid expensive sqrt)
        dx = self._hover_points.x - mx
        dy = self._hover_points.y - my
        d2 = dx * dx + dy * dy

        if d2.size == 0:
            return None

        # Find nearest point
        nearest_idx = int(np.argmin(d2))

        # Calculate distance threshold based on visible range
        x_range = plot_item.viewRange()[0]
        y_range = plot_item.viewRange()[1]

        # Threshold: 1% of visible range (squared for comparison)
        x_span = x_range[1] - x_range[0]
        y_span = y_range[1] - y_range[0]
        threshold_sq = (
            (x_span * HOVER_DISTANCE_THRESHOLD_PERCENT) ** 2 +
            (y_span * HOVER_DISTANCE_THRESHOLD_PERCENT) ** 2
        )

        # Check if nearest point is within threshold
        if float(d2[nearest_idx]) > float(threshold_sq):
            logger.debug(
                f"Nearest point too far: distance²={d2[nearest_idx]:.4f} > "
                f"threshold²={threshold_sq:.4f}"
            )
            return None

        return nearest_idx