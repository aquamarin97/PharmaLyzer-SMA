# app\controllers\graph\graph_controller.py
# -*- coding: utf-8 -*-
"""Graph controller managing PCR curve visibility through UI checkboxes.

This module provides a controller that bridges UI checkboxes and the PCR graph view,
managing the visibility of FAM and HEX channel curves. It handles:
- Checkbox state synchronization with graph visibility
- Default visibility state (both channels visible)
- Dynamic graph view replacement support

The controller follows a simple delegation pattern where checkbox state changes
are translated to graph view visibility updates.

Example:
    Basic usage in application setup::

        from app.controllers.graph.graph_controller import GraphController
        from app.views.widgets.pcr_graph_view import PCRGraphView

        # Create controller with UI and graph view
        controller = GraphController(
            ui=main_window.ui,
            graph_view=pcr_graph_view
        )

        # User clicks FAM checkbox -> graph updates automatically
        # User clicks HEX checkbox -> graph updates automatically

        # Reset to defaults (both visible)
        controller.reset_checkboxes()

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QObject

from app.views.ui.ui import Ui_MainWindow
from app.views.widgets.pcr_graph_view import PCRGraphView

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Default visibility state for channels
DEFAULT_FAM_VISIBLE = True
DEFAULT_HEX_VISIBLE = True


# ============================================================================
# Controller
# ============================================================================

class GraphController(QObject):
    """Controller managing PCR graph channel visibility via UI checkboxes.
    
    This controller connects UI checkbox widgets to PCR graph view channel
    visibility, providing automatic synchronization between user interface
    state and graph display.
    
    The controller manages:
    - FAM channel visibility (checkbox_FAM)
    - HEX channel visibility (checkbox_HEX)
    - Default state initialization (both channels visible)
    - Dynamic graph view replacement
    
    Signal Flow:
        User clicks checkbox
        → toggled signal
        → _on_fam_toggled / _on_hex_toggled
        → _sync_visibility
        → graph_view.set_channel_visibility()
        → Graph updates display
    
    Attributes:
        ui: Main window UI containing checkbox widgets
        graph_view: PCR graph view widget to control
    
    Example:
        >>> controller = GraphController(ui, graph_view)
        >>> # Both channels visible by default
        >>> controller.reset_checkboxes()  # Ensure default state
        >>> # Graph view now shows both FAM and HEX curves
    """

    def __init__(self, ui: Ui_MainWindow, graph_view: PCRGraphView | None = None):
        """Initialize graph controller and wire checkbox signals.
        
        Args:
            ui: Main window UI instance containing checkBox_FAM and checkBox_HEX
            graph_view: Optional PCR graph view to control. Can be set later
                via set_graph_view() if not available during initialization.
        
        Note:
            - Connects checkbox signals immediately
            - Calls reset_checkboxes() to establish default state
            - graph_view can be None initially (common during app startup)
        """
        super().__init__()
        
        self.ui = ui
        self.graph_view = graph_view

        logger.debug("GraphController initializing")
        
        # Connect checkbox signals
        self._connect_signals()
        
        # Set default state (both channels visible)
        self.reset_checkboxes()
        
        logger.info("GraphController initialized")

    def _connect_signals(self) -> None:
        """Connect UI checkbox signals to handler methods.
        
        Wires toggled signals from FAM and HEX checkboxes to their
        respective handler methods. This is called once during initialization.
        
        Connected Signals:
            - ui.checkBox_FAM.toggled → _on_fam_toggled
            - ui.checkBox_HEX.toggled → _on_hex_toggled
        """
        logger.debug("Connecting checkbox signals")
        
        self.ui.checkBox_FAM.toggled.connect(self._on_fam_toggled)
        self.ui.checkBox_HEX.toggled.connect(self._on_hex_toggled)
        
        logger.debug("Checkbox signals connected")

    def set_graph_view(self, graph_view: PCRGraphView) -> None:
        """Set or replace graph view and sync current checkbox state.
        
        Used when graph view is created after controller initialization
        or when graph view needs to be replaced (e.g., reset scenarios).
        
        Args:
            graph_view: New PCR graph view instance to control
        
        Note:
            Automatically syncs current checkbox state to new graph view,
            ensuring visibility state is consistent.
        
        Example:
            >>> # Controller created without graph view
            >>> controller = GraphController(ui, None)
            >>> # Later, graph view becomes available
            >>> controller.set_graph_view(new_graph_view)
            >>> # Graph view now reflects checkbox state
        """
        logger.debug(f"Setting graph view: {type(graph_view).__name__}")
        
        self.graph_view = graph_view
        
        # Sync current checkbox state to new graph view
        self._sync_visibility()
        
        logger.debug("Graph view set and synced")

    def reset_checkboxes(self) -> None:
        """Reset checkboxes to default state (both channels visible).
        
        Sets both FAM and HEX checkboxes to checked state and syncs
        visibility with graph view. This establishes the default application
        state where both PCR channels are displayed.
        
        Called during:
        - Controller initialization
        - Application reset/clear operations
        - Data loading reset
        
        Note:
            Setting checkbox state triggers toggled signals, which
            automatically call _sync_visibility through signal handlers.
        """
        logger.debug("Resetting checkboxes to default state")
        
        self.ui.checkBox_FAM.setChecked(DEFAULT_FAM_VISIBLE)
        self.ui.checkBox_HEX.setChecked(DEFAULT_HEX_VISIBLE)
        
        # Explicitly sync in case graph view was set after checkbox state
        self._sync_visibility()
        
        logger.debug("Checkboxes reset to default (both visible)")

    def _on_fam_toggled(self, checked: bool) -> None:
        """Handle FAM channel checkbox toggle event.
        
        Called when user clicks FAM checkbox. Updates graph visibility
        for FAM channel while preserving HEX channel state.
        
        Args:
            checked: New checkbox state (True = visible, False = hidden)
        """
        logger.debug(f"FAM checkbox toggled: {checked}")
        self._sync_visibility(fam_visible=bool(checked))

    def _on_hex_toggled(self, checked: bool) -> None:
        """Handle HEX channel checkbox toggle event.
        
        Called when user clicks HEX checkbox. Updates graph visibility
        for HEX channel while preserving FAM channel state.
        
        Args:
            checked: New checkbox state (True = visible, False = hidden)
        """
        logger.debug(f"HEX checkbox toggled: {checked}")
        self._sync_visibility(hex_visible=bool(checked))

    def _sync_visibility(
        self,
        fam_visible: bool | None = None,
        hex_visible: bool | None = None
    ) -> None:
        """Synchronize checkbox states with graph view channel visibility.
        
        Updates graph view to match checkbox states. If specific visibility
        values are provided, uses those; otherwise reads current checkbox state.
        
        Args:
            fam_visible: Optional FAM channel visibility override.
                If None, reads from ui.checkBox_FAM.isChecked()
            hex_visible: Optional HEX channel visibility override.
                If None, reads from ui.checkBox_HEX.isChecked()
        
        Note:
            - Does nothing if graph_view is None (safe to call)
            - Reads checkbox state if override not provided
            - Calls graph_view.set_channel_visibility() to update display
        
        Example:
            >>> # Sync current checkbox state
            >>> controller._sync_visibility()
            
            >>> # Override FAM visibility, read HEX from checkbox
            >>> controller._sync_visibility(fam_visible=False)
            
            >>> # Set both explicitly
            >>> controller._sync_visibility(fam_visible=True, hex_visible=False)
        """
        # Skip if graph view not available
        if self.graph_view is None:
            logger.debug("Graph view not set, skipping visibility sync")
            return

        # Determine visibility states (use overrides or read from checkboxes)
        fam_state = self.ui.checkBox_FAM.isChecked() if fam_visible is None else fam_visible
        hex_state = self.ui.checkBox_HEX.isChecked() if hex_visible is None else hex_visible

        logger.debug(f"Syncing visibility - FAM: {fam_state}, HEX: {hex_state}")

        # Update graph view
        self.graph_view.set_channel_visibility(
            fam_visible=fam_state,
            hex_visible=hex_state
        )
        
        logger.debug("Visibility sync complete")