# app\views\plotting\pcr_graph_pg\view.py
# -*- coding: utf-8 -*-
"""
PCR Graph View Widget.

This module provides a QWidget wrapper for PCRGraphRendererPG:
- Clean API for UI integration
- Lifecycle management
- Encapsulates renderer internals
- Simple delegation pattern

Performance optimizations:
- Zero-margin layout (no wasted space)
- Direct delegation (no processing)
- Proper cleanup on destruction

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5 import QtWidgets

from app.constants.pcr_graph_style import PCRGraphStyle
from app.services.interaction_store import InteractionStore
from app.services.pcr_data_service import PCRCoords

from .renderer import PCRGraphRendererPG

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PCRGraphView(QtWidgets.QWidget):
    """
    Thin QWidget wrapper for PCRGraphRendererPG.

    Provides clean API for UI integration without exposing renderer internals.

    Public API:
    - set_title(): Update graph title
    - bind_interaction_store(): Connect to interaction state
    - set_channel_visibility(): Toggle FAM/HEX channels
    - render_wells(): Render PCR data

    Performance characteristics:
    - Zero-margin layout (maximizes graph area)
    - Direct delegation (no processing overhead)
    - Efficient renderer access
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        style: PCRGraphStyle | None = None,
    ) -> None:
        """
        Initialize PCR graph view.

        Args:
            parent: Parent widget
            style: PCRGraphStyle configuration (optional)
        """
        super().__init__(parent)

        # Create renderer
        self.renderer = PCRGraphRendererPG(parent=self, style=style)

        # Setup layout with zero margins
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.renderer)

        logger.debug("PCRGraphView initialized")

    def set_title(self, title: str) -> None:
        """
        Update graph title.

        Args:
            title: New title text

        Performance: Direct delegation to renderer
        """
        self.renderer.set_title(title)
        logger.debug(f"Title set: {title}")

    def bind_interaction_store(self, store: InteractionStore | None) -> None:
        """
        Bind interaction store for state synchronization.

        Args:
            store: InteractionStore instance (None to unbind)

        Performance: Direct delegation to renderer

        Use case: Connect graph to shared selection/hover state
        """
        self.renderer.bind_interaction_store(store)
        logger.debug(f"Interaction store bound: {store is not None}")

    def set_channel_visibility(
        self,
        fam_visible: bool | None = None,
        hex_visible: bool | None = None,
    ) -> None:
        """
        Update channel visibility (FAM/HEX).

        Args:
            fam_visible: FAM channel visibility (None = no change)
            hex_visible: HEX channel visibility (None = no change)

        Performance: Direct delegation to renderer, efficient style update

        Use case: Toggle channels via checkboxes in UI
        """
        self.renderer.set_channel_visibility(
            fam_visible=fam_visible,
            hex_visible=hex_visible,
        )
        logger.debug(f"Channel visibility: FAM={fam_visible}, HEX={hex_visible}")

    def render_wells(
        self,
        data: dict[str, PCRCoords],
        *,
        cache_token: int | None = None,
    ) -> None:
        """
        Render PCR well data.

        Args:
            data: Dictionary mapping well_id to PCRCoords
            cache_token: Optional cache token for change detection

        Performance: Direct delegation to renderer

        Use case: Update graph with new PCR data

        Note: Renderer handles caching and change detection internally
        """
        self.renderer.render_wells(data, cache_token=cache_token)
        logger.debug(f"Wells rendered: {len(data)} wells, cache_token={cache_token}")

    def clear(self) -> None:
        """
        Clear graph content.

        Performance: Delegates to renderer cleanup

        Use case: Reset graph to empty state
        """
        if hasattr(self.renderer, 'clear'):
            self.renderer.clear()
            logger.debug("Graph cleared")

    def get_visible_range(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """
        Get current visible range.

        Returns:
            Tuple of ((xmin, xmax), (ymin, ymax))

        Performance: O(1) view box query

        Use case: Save/restore viewport state
        """
        if hasattr(self.renderer, 'get_visible_range'):
            return self.renderer.get_visible_range()

        return ((0, 100), (0, 100))  # Default fallback

    def set_visible_range(
        self,
        x_range: tuple[float, float],
        y_range: tuple[float, float],
    ) -> None:
        """
        Set visible range.

        Args:
            x_range: (xmin, xmax)
            y_range: (ymin, ymax)

        Performance: O(1) view box update

        Use case: Restore viewport state, zoom to region
        """
        if hasattr(self.renderer, 'set_visible_range'):
            self.renderer.set_visible_range(x_range, y_range)
            logger.debug(f"Visible range set: x={x_range}, y={y_range}")

    def cleanup(self) -> None:
        """
        Clean up resources.

        Unbinds store, stops timers, clears cached data.

        Performance: Proper cleanup prevents memory leaks

        Use case: Widget destruction, application shutdown
        """
        if hasattr(self.renderer, 'cleanup'):
            self.renderer.cleanup()
            logger.debug("PCRGraphView cleanup complete")

    def get_stats(self) -> dict:
        """
        Get statistics about graph state.

        Returns:
            Dictionary with graph metrics

        Use case: Debugging, performance monitoring
        """
        stats = {
            "widget_visible": self.isVisible(),
            "widget_size": (self.width(), self.height()),
        }

        if hasattr(self.renderer, 'get_stats'):
            stats.update(self.renderer.get_stats())

        return stats