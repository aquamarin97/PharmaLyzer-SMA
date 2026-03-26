# app\views\plotting\regression\renderer.py
# -*- coding: utf-8 -*-
"""
Regression Plot Renderer.

This module provides the main rendering logic for regression plots:
- Combines safe band, regression line, and scatter series
- Manages overlay updates for selection/hover states
- Efficient style updates without full rerender

Performance optimizations:
- Overlay architecture (no item recreation for selection changes)
- Cached scatter handles for fast updates
- Efficient color brightening for selection/hover
- Single-pass rendering

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pyqtgraph as pg

from app.views.plotting.regression.adapters import (
    HoverPoints,
    ScatterHandle,
    SeriesBuildResult,
    build_regression_line_item,
    build_safe_band_items,
    build_series_items,
)
from app.views.plotting.regression.styles import RegressionPlotStyle, make_brush, make_pen

if TYPE_CHECKING:
    from app.services.regression_plot_service import RegressionPlotData

logger = logging.getLogger(__name__)


@dataclass
class RegressionRenderResult:
    """
    Result of rendering regression plot.

    Contains:
    - All graphics items to add to plot
    - Hover points for interaction
    - Scatter handles for style updates
    """

    items: list[pg.GraphicsObject]
    hover_points: HoverPoints
    scatter_handles: list[ScatterHandle]


class RegressionRenderer:
    """
    Renderer for regression plots.

    Manages creation and updating of regression plot items:
    - Safe band visualization
    - Regression line
    - Scatter series with selection/hover overlays

    Performance characteristics:
    - Initial render creates all items
    - Style updates only modify overlay items (no full rerender)
    - Cached handles for efficient updates
    """

    def __init__(self, style: RegressionPlotStyle) -> None:
        """
        Initialize regression renderer.

        Args:
            style: RegressionPlotStyle configuration
        """
        self._style = style
        self._scatter_handles: list[ScatterHandle] = []
        self._hover_points: HoverPoints = HoverPoints.empty()

        logger.debug("RegressionRenderer initialized")

    @property
    def hover_points(self) -> HoverPoints:
        """
        Get current hover points.

        Returns:
            HoverPoints for mouse interaction

        Performance: O(1) property access
        """
        return self._hover_points

    def render(self, data: RegressionPlotData) -> RegressionRenderResult:
        """
        Render regression plot from data.

        Creates all plot items in proper Z-order:
        1. Safe band (z=0, background)
        2. Regression line (z=2, middle)
        3. Scatter base points (z=3)
        4. Selected overlays (z=50)
        5. Hover overlays (z=100, top)

        Args:
            data: RegressionPlotData with all plot data

        Returns:
            RegressionRenderResult with items and handles

        Performance: Single-pass creation, efficient numpy ops
        """
        # Reset state
        self._scatter_handles = []
        self._hover_points = HoverPoints.empty()

        # Early return for empty data
        if data.reg_line.x_sorted.size == 0:
            logger.warning("Empty regression line data, skipping render")
            return RegressionRenderResult(
                items=[],
                hover_points=self._hover_points,
                scatter_handles=[],
            )

        # Build items in Z-order
        items: list[pg.GraphicsObject] = []

        # 1. Safe band (background)
        items.extend(build_safe_band_items(data.safe_band, self._style))

        # 2. Regression line (middle layer)
        items.append(build_regression_line_item(data.reg_line, self._style))

        # 3. Scatter series with overlays (foreground)
        series_result: SeriesBuildResult = build_series_items(
            data.series,
            self._style,
        )
        items.extend(series_result.scatter_items)

        # Cache handles and hover points for updates
        self._scatter_handles = series_result.scatter_handles
        self._hover_points = series_result.hover_points

        logger.info(
            f"Render complete: {len(items)} items, "
            f"{len(self._scatter_handles)} series, "
            f"{self._hover_points.x.size} hover points"
        )

        return RegressionRenderResult(
            items=items,
            hover_points=self._hover_points,
            scatter_handles=self._scatter_handles,
        )

    def update_styles(
        self,
        selected_wells: set[str] | None,
        hover_well: str | None,
    ) -> None:
        """
        Update selection and hover overlays without full rerender.

        Only modifies overlay items, leaving base items unchanged.

        Args:
            selected_wells: Set of selected well IDs (or None/empty)
            hover_well: Hovered well ID (or None)

        Performance: O(selected + 1) where selected is typically <10 wells.
        Much faster than recreating entire plot.

        Algorithm:
        1. For each scatter handle:
           - Find selected well indices
           - Update selected_item with brightened colors
           - Find hover well index
           - Update hover_item with brightened colors
        """
        selected_wells = selected_wells or set()

        for handle in self._scatter_handles:
            # Update selected overlay
            self._update_selected_overlay(handle, selected_wells)

            # Update hover overlay
            self._update_hover_overlay(handle, hover_well)

        logger.debug(
            f"Styles updated: {len(selected_wells)} selected, "
            f"hover={hover_well}"
        )

    def _update_selected_overlay(
        self,
        handle: ScatterHandle,
        selected_wells: set[str],
    ) -> None:
        """
        Update selected points overlay for a scatter handle.

        Args:
            handle: ScatterHandle to update
            selected_wells: Set of selected well IDs

        Performance: O(selected_wells) with early return if empty
        """
        if not selected_wells:
            # Clear selection overlay
            handle.selected_item.setData(x=[], y=[])
            return

        # Find indices of selected wells in this series
        selected_indices: list[int] = []
        for well in selected_wells:
            idx = handle.well_to_index.get(well)
            if idx is not None:
                selected_indices.append(idx)

        if not selected_indices:
            # No selected wells in this series
            handle.selected_item.setData(x=[], y=[])
            return

        # Extract coordinates of selected points
        sel_x = handle.x[selected_indices]
        sel_y = handle.y[selected_indices]

        # Brighten base color for selection
        bright_color = self._brighten_color(handle.base_brush, amount=60)

        # Update selected overlay item
        handle.selected_item.setData(
            x=sel_x,
            y=sel_y,
            size=self._style.scatter_size + 4,
            brush=make_brush(bright_color),
            pen=make_pen(handle.selection_pen, width=4),
        )

        logger.debug(
            f"Selected overlay updated: {len(selected_indices)} points"
        )

    def _update_hover_overlay(
        self,
        handle: ScatterHandle,
        hover_well: str | None,
    ) -> None:
        """
        Update hover point overlay for a scatter handle.

        Args:
            handle: ScatterHandle to update
            hover_well: Hovered well ID or None

        Performance: O(1) dictionary lookup
        """
        if hover_well is None:
            # Clear hover overlay
            handle.hover_item.setData(x=[], y=[])
            return

        # Find index of hovered well
        hover_idx = handle.well_to_index.get(hover_well)

        if hover_idx is None:
            # Hovered well not in this series
            handle.hover_item.setData(x=[], y=[])
            return

        # Extract coordinates of hover point
        hover_x = float(handle.x[hover_idx])
        hover_y = float(handle.y[hover_idx])

        # Brighten base color more for hover
        bright_color = self._brighten_color(handle.base_brush, amount=80)

        # Update hover overlay item (single point)
        handle.hover_item.setData(
            x=[hover_x],
            y=[hover_y],
            size=self._style.scatter_size + 7,
            brush=make_brush(bright_color),
            pen=make_pen(handle.selection_pen, width=4),
        )

        logger.debug(f"Hover overlay updated: well={hover_well}")

    def _brighten_color(
        self,
        color: tuple[int, ...],
        amount: int,
    ) -> tuple[int, ...]:
        """
        Brighten color by adding amount to each component.

        Args:
            color: RGB or RGBA tuple
            amount: Amount to add (clamped to 255)

        Returns:
            Brightened color tuple

        Performance: O(1) tuple comprehension

        Example:
            brighten_color((100, 150, 200), 50) -> (150, 200, 250)
        """
        if len(color) == 4:
            r, g, b, a = color
            return (
                min(r + amount, 255),
                min(g + amount, 255),
                min(b + amount, 255),
                a,  # Alpha unchanged
            )
        else:
            r, g, b = color
            return (
                min(r + amount, 255),
                min(g + amount, 255),
                min(b + amount, 255),
            )