# app\views\plotting\regression\styles.py
# -*- coding: utf-8 -*-
"""
Regression Plot Style Utilities.

This module provides style helpers for regression plot rendering:
- Pen and brush creation with PyQtGraph
- Series style lookup
- Color and line style configuration

Performance optimizations:
- Reusable pen/brush creation functions
- Type-safe style access
- Minimal object creation overhead

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pyqtgraph as pg

from app.constants.regression_plot_style import RegressionPlotStyle, SeriesStyle

if TYPE_CHECKING:
    from PyQt5.QtGui import QBrush, QPen

logger = logging.getLogger(__name__)


def make_pen(color: tuple[int, ...], width: int = 1) -> QPen:
    """
    Create QPen from color tuple.

    Args:
        color: RGB or RGBA tuple (e.g., (255, 0, 0) or (255, 0, 0, 128))
        width: Pen width in pixels

    Returns:
        QPen object

    Performance: Direct PyQtGraph mkPen call, efficient for plotting

    Example:
        pen = make_pen((255, 0, 0), width=2)  # Red pen, 2px wide
    """
    return pg.mkPen(*color, width=width)


def make_brush(color: tuple[int, ...]) -> QBrush:
    """
    Create QBrush from color tuple.

    Args:
        color: RGB or RGBA tuple (e.g., (0, 255, 0) or (0, 255, 0, 128))

    Returns:
        QBrush object

    Performance: Direct PyQtGraph mkBrush call, efficient for fills

    Example:
        brush = make_brush((0, 255, 0, 100))  # Green with alpha
    """
    return pg.mkBrush(*color)


def get_series_style(style: RegressionPlotStyle, label: str) -> SeriesStyle | None:
    """
    Look up series style by label.

    Args:
        style: RegressionPlotStyle configuration
        label: Series label (e.g., "Sağlıklı", "Taşıyıcı", "Belirsiz")

    Returns:
        SeriesStyle if found, None otherwise

    Performance: Dictionary lookup, O(1)

    Example:
        series_style = get_series_style(plot_style, "Sağlıklı")
        if series_style:
            brush = make_brush(series_style.brush)
    """
    if style is None or not hasattr(style, 'series'):
        logger.warning("Invalid style object or missing 'series' attribute")
        return None

    return style.series.get(label)


def validate_color_tuple(color: tuple[int, ...]) -> bool:
    """
    Validate color tuple format.

    Args:
        color: Color tuple to validate

    Returns:
        True if valid RGB or RGBA tuple, False otherwise

    Valid formats:
        - RGB: (r, g, b) where 0 <= r,g,b <= 255
        - RGBA: (r, g, b, a) where 0 <= r,g,b,a <= 255

    Use case: Input validation before pen/brush creation
    """
    if not isinstance(color, tuple):
        return False

    if len(color) not in (3, 4):
        return False

    return all(isinstance(c, int) and 0 <= c <= 255 for c in color)


def make_pen_safe(
    color: tuple[int, ...],
    width: int = 1,
    fallback_color: tuple[int, ...] = (128, 128, 128),
) -> QPen:
    """
    Create QPen with validation and fallback.

    Args:
        color: RGB or RGBA tuple
        width: Pen width in pixels
        fallback_color: Fallback color if validation fails

    Returns:
        QPen object (guaranteed valid)

    Performance: Validation overhead only on invalid input
    """
    if not validate_color_tuple(color):
        logger.warning(
            f"Invalid color tuple: {color}, using fallback {fallback_color}"
        )
        color = fallback_color

    return make_pen(color, width)


def make_brush_safe(
    color: tuple[int, ...],
    fallback_color: tuple[int, ...] = (128, 128, 128, 100),
) -> QBrush:
    """
    Create QBrush with validation and fallback.

    Args:
        color: RGB or RGBA tuple
        fallback_color: Fallback color if validation fails

    Returns:
        QBrush object (guaranteed valid)

    Performance: Validation overhead only on invalid input
    """
    if not validate_color_tuple(color):
        logger.warning(
            f"Invalid color tuple: {color}, using fallback {fallback_color}"
        )
        color = fallback_color

    return make_brush(color)


# Public API
__all__ = [
    "RegressionPlotStyle",
    "SeriesStyle",
    "get_series_style",
    "make_pen",
    "make_brush",
    "make_pen_safe",
    "make_brush_safe",
    "validate_color_tuple",
]