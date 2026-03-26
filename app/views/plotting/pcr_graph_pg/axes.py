# app\views\plotting\pcr_graph_pg\axes.py
# -*- coding: utf-8 -*-
"""
PCR Graph Axes Configuration.

This module provides axis setup and styling for PCR graphs:
- Professional axis styling with fixed widths
- Smart tick generation with nice intervals
- Grid configuration with subtle appearance
- Padding and range management

Performance optimizations:
- Efficient tick calculation (minimal iterations)
- Cached axis configuration
- Single-pass tick generation
- Proper decimal precision handling

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import TYPE_CHECKING

import pyqtgraph as pg

if TYPE_CHECKING:
    from app.constants.pcr_graph_style import AxesStyle

logger = logging.getLogger(__name__)


def apply_axes_style(
    plot_widget: pg.PlotWidget,
    plot_item: pg.PlotItem,
    view_box: pg.ViewBox,
    style_axes: AxesStyle,
    title: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
) -> None:
    """
    Apply comprehensive axis styling to PCR graph.

    Configures:
    - Axis pens and colors
    - Fixed axis widths (prevents jumping)
    - Grid appearance
    - Title and labels
    - Padding and tick offsets

    Args:
        plot_widget: PlotWidget to configure
        plot_item: PlotItem for title/labels
        view_box: ViewBox for background
        style_axes: AxesStyle configuration
        title: Graph title
        xlim: X-axis limits (min, max)
        ylim: Y-axis limits (min, max)

    Performance: Single-pass configuration, efficient pen creation
    """
    # Get axis objects
    bottom_axis = plot_widget.getAxis("bottom")
    left_axis = plot_widget.getAxis("left")

    # CRITICAL: Fixed Y-axis width prevents graph jumping during updates
    # 55px accommodates 5-digit numbers comfortably
    left_axis.setWidth(55)

    # Configure axis pens and text colors
    for axis in [bottom_axis, left_axis]:
        axis.setPen(
            pg.mkPen(style_axes.tick_color, width=style_axes.tick_width)
        )
        axis.setTextPen(pg.mkPen(style_axes.label_color))

    # Set background color
    view_box.setBackgroundColor(style_axes.ax_facecolor)

    # Configure grid (subtle appearance)
    plot_widget.showGrid(x=True, y=True, alpha=0.2)  # Low alpha for subtlety

    # Set title with styling
    plot_item.setTitle(title, color=style_axes.title_color, size="12pt")

    # Configure tick text offset (prevents overlap with axis)
    left_axis.setStyle(tickTextOffset=10)
    bottom_axis.setStyle(tickTextOffset=8)

    # Apply axis ranges and ticks
    apply_axis_ranges(
        plot_item,
        view_box,
        xlim=xlim,
        ylim=ylim,
    )

    logger.debug(
        f"Axes styled: title='{title}', xlim={xlim}, ylim={ylim}"
    )


def set_axis_ticks(
    plot_item: pg.PlotItem,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
) -> None:
    """
    Generate and apply axis ticks with nice intervals.

    Args:
        plot_item: PlotItem to configure
        xlim: X-axis limits (min, max)
        ylim: Y-axis limits (min, max)

    Performance: O(ticks) generation, typically <20 ticks per axis
    """
    bottom_axis = plot_item.getAxis("bottom")
    left_axis = plot_item.getAxis("left")

    # Calculate ranges
    x_range = xlim[1] - xlim[0]
    y_range = ylim[1] - ylim[0]

    if x_range <= 0 or y_range <= 0:
        logger.warning(f"Invalid axis ranges: x_range={x_range}, y_range={y_range}")
        return

    # Calculate nice step sizes
    x_step = _nice_step(x_range, target_ticks=7)
    y_step = _nice_step(y_range, target_ticks=6)

    # Generate and apply ticks
    bottom_axis.setTicks([
        build_ticks(xlim[0], xlim[1], step=x_step, force_end=True, align_to=0)
    ])
    left_axis.setTicks([
        build_ticks(ylim[0], ylim[1], step=y_step, force_end=True, align_to=0)
    ])

    logger.debug(
        f"Ticks set: x_step={x_step}, y_step={y_step}, "
        f"x_ticks~{int(x_range/x_step)}, y_ticks~{int(y_range/y_step)}"
    )


def build_ticks(
    start: float,
    end: float,
    step: float,
    force_end: bool = False,
    align_to: float = 0,
) -> list[tuple[float, str]]:
    """
    Build tick list for axis range.

    Generates evenly spaced ticks with proper formatting.
    Ensures zero is included if within range.

    Args:
        start: Range start
        end: Range end
        step: Tick interval
        force_end: Whether to force end value as tick
        align_to: Value to align ticks to (typically 0)

    Returns:
        List of (value, label) tuples

    Performance: O(n) where n is number of ticks (typically <20)

    Example:
        build_ticks(0, 100, 25) -> [(0, "0"), (25, "25"), (50, "50"), ...]
    """
    ticks: list[tuple[float, str]] = []

    if step <= 0:
        logger.warning(f"Invalid step size: {step}")
        return ticks

    # Find first tick (aligned to step)
    first_tick = math.floor(start / step) * step
    if first_tick < start:
        first_tick += step

    # Generate ticks
    current = first_tick
    while current <= end + (step * 0.001):  # Small epsilon for float precision
        val = _round_to_step(current, step)
        ticks.append((val, format_tick_value(val, step)))
        current += step

    # Ensure zero is included if in range
    has_zero = any(t[0] == 0 for t in ticks)
    if not has_zero and start <= 0 <= end:
        ticks.append((0.0, "0"))
        ticks.sort()

    # Force end tick if requested
    if force_end and ticks:
        last_val = ticks[-1][0]
        if end - last_val > (step * 0.1):
            ticks.append((end, format_tick_value(end, step)))

    logger.debug(f"Built {len(ticks)} ticks: range=({start},{end}), step={step}")

    return ticks


def format_tick_value(value: float, step: float) -> str:
    """
    Format tick value for display.

    Handles:
    - Zero formatting
    - Integer formatting for large values
    - Decimal precision based on step size
    - Trailing zero removal

    Args:
        value: Tick value
        step: Tick step (determines precision)

    Returns:
        Formatted string

    Performance: O(1) string operations

    Examples:
        format_tick_value(0.0, 0.1) -> "0"
        format_tick_value(1234.0, 100) -> "1234"
        format_tick_value(1.5000, 0.5) -> "1.5"
    """
    # Handle near-zero values
    if abs(value) < 0.000001:
        return "0"

    # Integer formatting for large values with large steps
    if abs(value) >= 1000 and step >= 1:
        return f"{int(round(value))}"

    # Decimal formatting based on step precision
    decimals = _decimal_places(step)
    formatted = f"{value:.{decimals}f}"

    # Remove trailing zeros and decimal point if not needed
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")

    return formatted


def _nice_step(value_range: float, target_ticks: int = 7) -> float:
    """
    Calculate nice tick interval for given range.

    Chooses from standard intervals: 1, 2, 2.5, 5, 10 (× 10^n).

    Args:
        value_range: Axis range
        target_ticks: Target number of ticks

    Returns:
        Nice step size

    Performance: O(1) calculation

    Algorithm:
    1. Calculate raw step: range / target_ticks
    2. Find magnitude: 10^floor(log10(raw))
    3. Choose nice factor: 1, 2, 2.5, 5, or 10
    4. Return factor × magnitude

    Example:
        _nice_step(100, 7) -> 20  (100/7≈14.3, choose 2×10)
    """
    if value_range <= 0:
        return 1.0

    raw = value_range / max(target_ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw))

    # Try standard nice factors
    for factor in (1, 2, 2.5, 5, 10):
        step = factor * magnitude
        if step >= raw:
            return step

    return 10 * magnitude


def _decimal_places(step: float) -> int:
    """
    Calculate number of decimal places needed for step.

    Args:
        step: Step size

    Returns:
        Number of decimal places

    Performance: O(1) using Decimal module

    Example:
        _decimal_places(0.1) -> 1
        _decimal_places(0.01) -> 2
        _decimal_places(10.0) -> 0
    """
    dec = Decimal(str(step)).normalize()
    exp = -dec.as_tuple().exponent
    return max(0, exp)


def _round_to_step(value: float, step: float) -> float:
    """
    Round value to nearest step multiple.

    Args:
        value: Value to round
        step: Step size

    Returns:
        Rounded value

    Performance: O(1) arithmetic

    Example:
        _round_to_step(14.3, 5) -> 15.0
    """
    if step == 0:
        return value

    return round(value / step) * step


def apply_axis_ranges(
    plot_item: pg.PlotItem,
    view_box: pg.ViewBox,
    *,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
) -> None:
    """
    Apply axis ranges with custom limits and padding.

    Configures:
    - Axis limits (xMin, xMax, yMin, yMax)
    - View range with padding
    - Disable auto-ranging
    - Generate ticks for custom ranges

    Args:
        plot_item: PlotItem to configure
        view_box: ViewBox to set range
        xlim: Desired X-axis limits
        ylim: Desired Y-axis limits

    Performance: Single-pass configuration

    Note: Custom offsets (-500 for Y, 0 for X) provide breathing room
    around data.
    """
    # Custom minimum values for better visualization
    custom_ymin = -500.0  # Negative offset for Y-axis
    custom_xmin = 0.0     # Start X at zero

    # Disable auto-ranging
    plot_item.enableAutoRange(x=False, y=False)

    # Add 10% padding to Y-max to prevent data touching top edge
    actual_ymax = ylim[1] * 1.1

    # Set hard limits
    plot_item.setLimits(
        xMin=custom_xmin,
        xMax=xlim[1],
        yMin=custom_ymin,
        yMax=actual_ymax,
    )

    # Set view range (no additional padding needed)
    view_box.setRange(
        xRange=(custom_xmin, xlim[1]),
        yRange=(custom_ymin, ylim[1]),
        padding=0.0,
    )

    # Generate ticks for custom ranges
    set_axis_ticks(
        plot_item,
        (custom_xmin, xlim[1]),
        (custom_ymin, ylim[1]),
    )

    logger.debug(
        f"Axis ranges applied: x=({custom_xmin},{xlim[1]}), "
        f"y=({custom_ymin},{ylim[1]}), ymax_padded={actual_ymax}"
    )