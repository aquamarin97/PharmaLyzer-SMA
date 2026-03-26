# app\views\widgets\pcr_graph_view.py
# -*- coding: utf-8 -*-
"""
PCR Graph View Widget.

Main widget for PCR amplification curve visualization:
- Inherits from PCRGraphRendererPG for rendering
- Integrates PCRGraphInteractor for store coordination
- Clean API for UI integration

Performance optimizations:
- Efficient renderer/interactor coordination
- Proper lifecycle management
- Clean signal routing

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.constants.pcr_graph_style import PCRGraphStyle
from app.services.interaction_store import InteractionStore
from app.services.pcr_data_service import PCRDataService
from app.views.plotting.pcr_graph_pg.renderer import PCRGraphRendererPG
from app.views.widgets.pcr_graph_interactor import PCRGraphInteractor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PCRGraphView(PCRGraphRendererPG):
    """
    Complete PCR graph widget with rendering and interaction.

    Combines:
    - PCRGraphRendererPG: High-performance rendering
    - PCRGraphInteractor: Store signal coordination

    This is the main widget to use in UI - provides complete functionality
    with clean API.

    Performance characteristics:
    - Inherits all renderer optimizations
    - Efficient store coordination
    - Proper lifecycle management

    Usage:
        view = PCRGraphView(parent, style)
        view.set_interaction_store(store, data_service)
        # Widget handles everything automatically
    """

    def __init__(
        self,
        parent=None,
        style: PCRGraphStyle | None = None,
    ) -> None:
        """
        Initialize PCR graph view.

        Args:
            parent: Parent widget
            style: PCRGraphStyle configuration (optional)
        """
        super().__init__(parent=parent, style=style)

        # Create interactor for store coordination
        self._interactor = PCRGraphInteractor(renderer=self)

        logger.debug("PCRGraphView initialized")

    def set_interaction_store(
        self,
        store: InteractionStore,
        data_service: PCRDataService,
    ) -> None:
        """
        Bind interaction store and data service.

        Connects store signals and enables automatic rendering
        based on selection/hover changes.

        Args:
            store: InteractionStore for selection/hover state
            data_service: PCRDataService for data access

        Performance: Efficient signal routing via interactor

        Use case: Connect graph to shared application state

        Example:
            store = InteractionStore()
            data_service = PCRDataService(...)
            view.set_interaction_store(store, data_service)
            # Now selection changes automatically update graph
        """
        self._interactor.set_interaction_store(
            store=store,
            data_service=data_service,
        )

        logger.info("Interaction store and data service bound")

    def dispose(self) -> None:
        """
        Clean up resources.

        Disconnects signals and clears state.

        Performance: Proper cleanup prevents memory leaks

        Use case: Widget destruction, application shutdown
        """
        self._interactor.dispose()

        logger.debug("PCRGraphView disposed")

    def get_stats(self) -> dict:
        """
        Get statistics about view state.

        Returns:
            Dictionary with view metrics

        Use case: Debugging, performance monitoring
        """
        stats = {
            "widget_type": "PCRGraphView",
            "has_interactor": self._interactor is not None,
            "has_store": self._interactor.store is not None,
            "has_data_service": self._interactor.data_service is not None,
        }

        # Add renderer stats if available
        if hasattr(super(), "get_stats"):
            stats.update(super().get_stats())

        return stats