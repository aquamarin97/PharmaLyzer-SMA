# app\views\widgets\pcr_graph_interactor.py
# -*- coding: utf-8 -*-
"""
PCR Graph Interactor - Store Signal Coordinator.

This module coordinates InteractionStore signals with PCR graph rendering:
- Selection changes trigger data fetching and rendering
- Hover changes update visual feedback
- Cache token optimization prevents redundant renders
- Proper signal connection/disconnection lifecycle

Performance optimizations:
- Cache token comparison (skip render if data unchanged)
- Normalized well ID validation
- Safe signal disconnection
- Early returns for unchanged state

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.interaction_store import InteractionStore
from app.services.pcr_data_service import PCRDataService
from app.utils import well_mapping
from app.views.plotting.pcr_graph_pg.renderer import PCRGraphRendererPG

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PCRGraphInteractor:
    """
    Coordinator between InteractionStore and PCR graph renderer.

    Responsibilities:
    - Listen to store signals (selection, hover)
    - Fetch PCR data for selected wells
    - Trigger renderer updates
    - Manage signal connection lifecycle

    Performance characteristics:
    - Cache token optimization (skip redundant renders)
    - Early returns for unchanged state
    - Safe signal disconnection
    """

    def __init__(
        self,
        renderer: PCRGraphRendererPG,
        data_service: PCRDataService | None = None,
    ) -> None:
        """
        Initialize PCR graph interactor.

        Args:
            renderer: PCR graph renderer instance
            data_service: PCR data service (optional, can be set later)
        """
        self.renderer = renderer
        self.data_service = data_service
        self.store: InteractionStore | None = None

        # State tracking for optimization
        self._last_selection: set[str] = set()
        self._last_cache_token: int | None = None

        logger.debug("PCRGraphInteractor initialized")

    def set_interaction_store(
        self,
        store: InteractionStore,
        data_service: PCRDataService | None = None,
    ) -> None:
        """
        Bind interaction store and connect signals.

        Args:
            store: InteractionStore instance
            data_service: PCR data service (optional)

        Performance: Safe signal disconnection, proper cleanup
        """
        # Disconnect old store
        self._disconnect_store()

        self.store = store
        self.renderer.bind_interaction_store(store)

        if data_service is not None:
            self.data_service = data_service

        if self.store is None:
            logger.warning("Attempting to bind None store")
            return

        # Connect signals
        self.store.selectedChanged.connect(self._on_selection_changed)
        self.store.hoverChanged.connect(self._on_hover_changed)

        # Apply current state
        self._apply_current_state()

        logger.info("Interaction store bound and signals connected")

    def dispose(self) -> None:
        """
        Clean up resources and disconnect signals.

        Performance: Safe disconnection, proper cleanup
        """
        self._disconnect_store()
        self.store = None

        logger.debug("PCRGraphInteractor disposed")

    # ---- Signal Handlers ----

    def _on_selection_changed(self, wells: set[str]) -> None:
        """
        Handle selection change event.

        Fetches PCR data for selected wells and triggers render.

        Args:
            wells: Set of selected well IDs

        Performance: Cache token optimization, early returns
        """
        if self.data_service is None:
            logger.warning("data_service not set, cannot render")
            self.renderer.reset()
            return

        # Normalize and validate well IDs
        normalized_wells = {w for w in wells if well_mapping.is_valid_well_id(w)}

        if not normalized_wells:
            # Empty selection - reset renderer
            self._last_selection = set()
            self._last_cache_token = None
            self.renderer.reset()
            logger.debug("Selection cleared, renderer reset")
            return

        # Fetch PCR data
        try:
            data = self.data_service.get_coords_for_wells(normalized_wells)
            cache_token = self.data_service.get_cache_token()
        except ValueError as exc:
            # Expected before RDML is loaded; avoid noisy traceback logs.
            if "DataStore is empty" in str(exc):
                logger.info("PCR data is not loaded yet, skipping graph render")
            else:
                logger.warning(f"Failed to fetch PCR coordinates: {exc}")

            self._last_selection = set()
            self._last_cache_token = None
            self.renderer.reset()
            return
        except Exception as exc:
            logger.warning(f"Failed to fetch PCR coordinates: {exc}", exc_info=True)
            self._last_selection = set()
            self._last_cache_token = None
            self.renderer.reset()
            return

        # Check if data unchanged (cache optimization)
        if (
            normalized_wells == self._last_selection
            and cache_token == self._last_cache_token
        ):
            logger.debug("Selection unchanged, skipping render")
            return

        # Update state
        self._last_selection = normalized_wells
        self._last_cache_token = cache_token

        # Render
        self.renderer.render_wells(data, cache_token=cache_token)

        logger.debug(
            f"Selection changed: {len(normalized_wells)} wells, "
            f"cache_token={cache_token}"
        )
    def _on_hover_changed(self, well: str | None) -> None:
        """
        Handle hover change event.

        Updates renderer hover state.

        Args:
            well: Hovered well ID or None

        Performance: Early return for unchanged state
        """
        # Normalize well ID
        normalized = well if well_mapping.is_valid_well_id(well) else None

        # Early return if unchanged
        if normalized == self.renderer._hover_well:
            return

        # Update renderer
        self.renderer.set_hover(normalized)

        logger.debug(f"Hover changed: {normalized}")

    # ---- Helpers ----

    def _apply_current_state(self) -> None:
        """
        Apply current store state to renderer.

        Called after store binding to sync initial state.

        Performance: Two handler calls (selection, hover)
        """
        if self.store is None:
            return

        self._on_selection_changed(self.store.selected_wells)
        self._on_hover_changed(self.store.hover_well)

        logger.debug("Current store state applied")

    def _disconnect_store(self) -> None:
        """
        Disconnect signals from store.

        Safe disconnection with exception handling.

        Performance: Try-except for each signal, proper cleanup
        """
        if self.store is None:
            return

        try:
            self.store.selectedChanged.disconnect(self._on_selection_changed)
        except Exception:
            pass

        try:
            self.store.hoverChanged.disconnect(self._on_hover_changed)
        except Exception:
            pass

        try:
            self.renderer.bind_interaction_store(None)
        except Exception:
            pass

        # Clear state
        self._last_selection = set()
        self._last_cache_token = None

        logger.debug("Store disconnected")