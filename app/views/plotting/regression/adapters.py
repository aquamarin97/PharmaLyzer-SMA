# app\views\plotting\regression\adapters.py
# -*- coding: utf-8 -*-
"""
Data Adapters for Regression Plot Rendering.

This module transforms regression plot data into PyQtGraph-compatible structures:
- Safe band curve generation
- Regression line preparation
- Scatter series with overlay architecture
- Hover point aggregation

Performance optimizations:
- Efficient numpy array operations
- Pre-allocated data structures
- Minimal data copying
- Z-ordering for proper layering

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg

from app.i18n import t
from app.views.plotting.regression.styles import (
    RegressionPlotStyle,
    get_series_style,
    make_brush,
    make_pen,
)

if TYPE_CHECKING:
    from app.services.regression_plot_service import RegressionLine, SafeBand, ScatterSeries

logger = logging.getLogger(__name__)


@dataclass
class ScatterHandle:
    """
    Handle for scatter plot with overlay architecture.

    Base item shows all points (visible in legend).
    Selected item shows selected points overlay (not in legend).
    Hover item shows single hovered point overlay (not in legend).

    This architecture allows independent styling of selection states
    without recreating the entire scatter plot.
    """

    # Main scatter plot items
    base_item: pg.ScatterPlotItem       # All points (in legend)
    selected_item: pg.ScatterPlotItem   # Selected overlay (not in legend)
    hover_item: pg.ScatterPlotItem      # Hover overlay (not in legend)

    # Data arrays (cached for efficient updates)
    x: np.ndarray
    y: np.ndarray
    wells: np.ndarray
    well_to_index: dict[str, int]  # Fast well -> index lookup

    # Style configuration
    base_brush: tuple[int, ...]
    base_pen: tuple[int, ...]
    selection_pen: tuple[int, ...]


@dataclass
class HoverPoints:
    """
    Aggregated hover points from all series.

    Used for efficient nearest-point lookup during mouse hover.
    """

    x: np.ndarray
    y: np.ndarray
    wells: np.ndarray

    @classmethod
    def empty(cls) -> HoverPoints:
        """
        Create empty HoverPoints.

        Returns:
            HoverPoints with empty arrays

        Performance: Minimal allocation for empty state
        """
        return cls(
            x=np.array([], dtype=float),
            y=np.array([], dtype=float),
            wells=np.array([], dtype=str),
        )

    @property
    def is_empty(self) -> bool:
        """
        Check if hover points are empty.

        Returns:
            True if no points, False otherwise

        Performance: O(1) size check
        """
        return self.x.size == 0


@dataclass
class SeriesBuildResult:
    """
    Result of building scatter series items.

    Contains:
    - All scatter plot items (base + overlays)
    - Handles for updating overlays
    - Aggregated hover points for interaction
    """

    scatter_items: list[pg.ScatterPlotItem]
    scatter_handles: list[ScatterHandle]
    hover_points: HoverPoints


def build_safe_band_items(
    safe_band: SafeBand,
    style: RegressionPlotStyle,
) -> list[pg.GraphicsObject]:
    """
    Build safe band visualization items.

    Creates upper and lower invisible curves with filled region between.

    Args:
        safe_band: SafeBand data with x_sorted, upper, lower arrays
        style: RegressionPlotStyle configuration

    Returns:
        List of [upper_curve, lower_curve, fill_between]

    Performance: Three item creation, efficient FillBetweenItem
    """
    if safe_band.x_sorted.size == 0:
        logger.warning("Empty safe band data, skipping")
        return []

    # Upper boundary (invisible line)
    upper_curve = pg.PlotDataItem(
        safe_band.x_sorted,
        safe_band.upper,
        pen=make_pen((255, 255, 255, 0)),  # Transparent
    )

    # Lower boundary (invisible line)
    lower_curve = pg.PlotDataItem(
        safe_band.x_sorted,
        safe_band.lower,
        pen=make_pen((255, 255, 255, 0)),  # Transparent
    )

    # Fill between curves
    fill = pg.FillBetweenItem(
        upper_curve,
        lower_curve,
        brush=make_brush(style.safe_band_brush_rgba),
    )
    fill.setZValue(0)  # Draw behind everything

    logger.debug(
        f"Safe band built: {safe_band.x_sorted.size} points, "
        f"brush={style.safe_band_brush_rgba}"
    )

    return [upper_curve, lower_curve, fill]


def build_regression_line_item(
    reg_line: RegressionLine,
    style: RegressionPlotStyle,
) -> pg.PlotDataItem:
    """
    Build regression line visualization item.

    Args:
        reg_line: RegressionLine data with x_sorted, y_pred_sorted arrays
        style: RegressionPlotStyle configuration

    Returns:
        PlotDataItem for regression line

    Performance: Single item creation, efficient line rendering
    """
    if reg_line.x_sorted.size == 0:
        logger.warning("Empty regression line data")
        # Return empty item
        return pg.PlotDataItem([], [])

    line = pg.PlotDataItem(
        reg_line.x_sorted,
        reg_line.y_pred_sorted,
        pen=make_pen(style.reg_line_pen, width=style.reg_line_width),
        name=t("regression.plot.regression_line"),
    )
    line.setZValue(2)  # Draw above safe band, below scatter

    logger.debug(
        f"Regression line built: {reg_line.x_sorted.size} points, "
        f"width={style.reg_line_width}"
    )

    return line


def _translate_label(label: str) -> str:
    """
    Translate series label to localized string.

    Args:
        label: Series label (e.g., "Sağlıklı", "Taşıyıcı", "Belirsiz")

    Returns:
        Translated label

    Performance: Dictionary lookup, O(1)
    """
    translation_map = {
        "Sağlıklı": t("regression.plot.legend.healthy"),
        "Taşıyıcı": t("regression.plot.legend.carrier"),
        "Belirsiz": t("regression.plot.legend.uncertain"),
    }

    return translation_map.get(label, label)


def build_series_items(
    series: list[ScatterSeries],
    style: RegressionPlotStyle,
) -> SeriesBuildResult:
    """
    Build scatter series visualization items with overlay architecture.

    Creates three items per series:
    1. Base scatter (all points, visible in legend)
    2. Selected overlay (highlighted selected points, not in legend)
    3. Hover overlay (highlighted hover point, not in legend)

    Args:
        series: List of ScatterSeries data
        style: RegressionPlotStyle configuration

    Returns:
        SeriesBuildResult with items, handles, and hover points

    Performance: O(n) where n is number of series, efficient numpy ops
    """
    scatter_items: list[pg.ScatterPlotItem] = []
    scatter_handles: list[ScatterHandle] = []

    # Accumulate hover points from all series
    hover_x: list[np.ndarray] = []
    hover_y: list[np.ndarray] = []
    hover_wells: list[np.ndarray] = []

    for series_data in series:
        # Look up series style
        series_style = get_series_style(style, series_data.label)

        if series_style is None:
            # Fallback colors if style not found
            brush = (200, 200, 200)
            pen = (255, 255, 255)
            sel_pen = (255, 255, 0)
            logger.warning(f"No style found for series: {series_data.label}")
        else:
            brush = series_style.brush
            pen = series_style.pen
            sel_pen = series_style.selection_pen

        # Translate label for legend
        label_name = _translate_label(series_data.label)

        # 1) Base scatter: all points (visible in legend)
        base_sc = pg.ScatterPlotItem(
            x=series_data.x,
            y=series_data.y,
            size=style.scatter_size,
            brush=make_brush(brush),
            pen=make_pen(pen, width=style.scatter_pen_width),
            name=label_name,  # Only base has name (appears in legend)
        )
        base_sc.setZValue(3)  # Draw above line, below overlays
        scatter_items.append(base_sc)

        # 2) Selected overlay: initially empty (not in legend)
        selected_sc = pg.ScatterPlotItem(
            x=[],
            y=[],
            size=style.scatter_size + 4,
            brush=make_brush(brush),
            pen=make_pen(sel_pen, width=4),
            # No name = not in legend
        )
        selected_sc.setZValue(50)  # Draw above base points
        scatter_items.append(selected_sc)

        # 3) Hover overlay: initially empty (not in legend)
        hover_sc = pg.ScatterPlotItem(
            x=[],
            y=[],
            size=style.scatter_size + 7,
            brush=make_brush(brush),
            pen=make_pen(sel_pen, width=4),
            # No name = not in legend
        )
        hover_sc.setZValue(100)  # Draw above everything
        scatter_items.append(hover_sc)

        # Convert to numpy arrays for efficient operations
        hx = np.asarray(series_data.x, dtype=float)
        hy = np.asarray(series_data.y, dtype=float)
        hw = np.asarray(series_data.wells, dtype=str)

        # Build well -> index lookup map
        well_to_index = {str(w): i for i, w in enumerate(hw)}

        # Accumulate hover points
        hover_x.append(hx)
        hover_y.append(hy)
        hover_wells.append(hw)

        # Create handle for this series
        scatter_handles.append(
            ScatterHandle(
                base_item=base_sc,
                selected_item=selected_sc,
                hover_item=hover_sc,
                x=hx,
                y=hy,
                wells=hw,
                well_to_index=well_to_index,
                base_brush=brush,
                base_pen=pen,
                selection_pen=sel_pen,
            )
        )

        logger.debug(
            f"Series built: {series_data.label}, {len(series_data.x)} points"
        )

    # Aggregate hover points from all series
    hover_points = HoverPoints.empty()
    if hover_x:
        hover_points = HoverPoints(
            x=np.concatenate(hover_x),
            y=np.concatenate(hover_y),
            wells=np.concatenate(hover_wells),
        )
        logger.debug(f"Hover points aggregated: {hover_points.x.size} total points")

    return SeriesBuildResult(
        scatter_items=scatter_items,
        scatter_handles=scatter_handles,
        hover_points=hover_points,
    )