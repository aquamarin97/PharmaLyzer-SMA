# app\views\plotting\pcr_graph_pg\legend.py
# -*- coding: utf-8 -*-
"""
PCR Graph Legend Management.

This module provides legend configuration for PCR graphs:
- Dynamic legend updates based on channel visibility
- Professional styling (compact, non-intrusive)
- Color-coded channel samples
- Fixed positioning

Performance optimizations:
- Minimal layout recalculation
- Single-pass legend population
- Efficient clear and rebuild

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pyqtgraph as pg

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def refresh_legend(renderer, legend_item: pg.LegendItem) -> None:
    """
    Refresh legend content based on visible channels.

    Rebuilds legend from scratch:
    1. Clear existing items
    2. Configure layout (compact margins and spacing)
    3. Add visible channel rows (FAM, HEX)
    4. Position legend in top-right corner

    Args:
        renderer: Renderer instance with channel visibility and style
        legend_item: PyQtGraph LegendItem to populate

    Performance: O(channels) where channels is typically 2 (FAM, HEX).
    Clear and rebuild is fast for small legends.

    Note: Legend positioned at offset (57, 38) to avoid overlap with axes.
    """
    # Clear existing legend items
    legend_item.clear()

    # Configure layout for compact appearance
    # Tight margins and spacing prevent legend from occupying too much space
    legend_item.layout.setContentsMargins(1, 1, 1, 1)
    legend_item.layout.setSpacing(4)

    # Define text style (subtle, readable)
    label_style = {
        'color': renderer._style.legend_text_color,
        'size': '9pt',
        'bold': False,
    }

    # Add visible channels to legend
    if renderer._fam_visible and renderer._fam_items:
        _add_legend_row(legend_item, "FAM", renderer._style.fam_color, label_style)
        logger.debug("FAM added to legend")

    if renderer._hex_visible and renderer._hex_items:
        _add_legend_row(legend_item, "HEX", renderer._style.hex_color, label_style)
        logger.debug("HEX added to legend")

    # Position legend (top-right corner with offset)
    # offset=(x, y): positive x = from left, negative x = from right
    #                positive y = from top, negative y = from bottom
    legend_item.setOffset((57, 38))

    logger.info(
        f"Legend refreshed: FAM={renderer._fam_visible}, HEX={renderer._hex_visible}"
    )


def _add_legend_row(
    legend: pg.LegendItem,
    name: str,
    color: str,
    label_style: dict,
) -> None:
    """
    Add single row to legend with styled icon and text.

    Creates a sample PlotDataItem with the channel color and adds it
    to the legend with formatted text.

    Args:
        legend: LegendItem to add row to
        name: Channel name (e.g., "FAM", "HEX")
        color: Channel color string (e.g., "#00FF00")
        label_style: Text styling dictionary

    Performance: Single item creation, efficient legend update

    Note: Sample pen width is 3 for visibility in legend (wider than graph).
    """
    # Create sample line for legend (bright, thick for visibility)
    sample_pen = pg.mkPen(color=color, width=3)
    sample_item = pg.PlotDataItem(pen=sample_pen)

    # Add row to legend
    legend.addItem(sample_item, name)

    # Apply custom text styling
    # Legend stores items as [(sample, label), ...] tuples
    for item_tuple in legend.items:
        label = item_tuple[1]  # LabelItem
        if label.text == name:
            label.setText(name, **label_style)
            logger.debug(f"Legend row styled: {name}, color={color}")
            break


def configure_legend_position(
    legend_item: pg.LegendItem,
    anchor: tuple[float, float] = (1, 0),  # Top-right
    offset: tuple[float, float] = (57, 38),
) -> None:
    """
    Configure legend position with anchor and offset.

    Args:
        legend_item: LegendItem to position
        anchor: Anchor point (0-1 for each axis, (1,0) = top-right)
        offset: Pixel offset from anchor (x, y)

    Performance: O(1) positioning

    Use case: Reposition legend without rebuilding content
    """
    legend_item.setOffset(offset)
    logger.debug(f"Legend positioned: anchor={anchor}, offset={offset}")


def hide_legend(legend_item: pg.LegendItem) -> None:
    """
    Hide legend completely.

    Args:
        legend_item: LegendItem to hide

    Performance: O(1) visibility toggle

    Use case: Temporarily hide legend without destroying it
    """
    legend_item.setVisible(False)
    logger.debug("Legend hidden")


def show_legend(legend_item: pg.LegendItem) -> None:
    """
    Show previously hidden legend.

    Args:
        legend_item: LegendItem to show

    Performance: O(1) visibility toggle

    Use case: Restore legend visibility
    """
    legend_item.setVisible(True)
    logger.debug("Legend shown")


def get_legend_stats(legend_item: pg.LegendItem) -> dict:
    """
    Get statistics about legend state.

    Args:
        legend_item: LegendItem to inspect

    Returns:
        Dictionary with legend metrics

    Use case: Debugging, performance monitoring
    """
    return {
        "item_count": len(legend_item.items),
        "visible": legend_item.isVisible(),
        "offset": legend_item.offset,
    }