# app\controllers\table\table_interaction_controller.py
# -*- coding: utf-8 -*-
"""Table interaction controller synchronizing table selections with interaction store.

This module provides bidirectional synchronization between QTableView row selections
and the application-wide InteractionStore. It handles:
- Mouse clicks on table rows (single and multi-select)
- Keyboard navigation (Enter/Return keys)
- Ctrl+Click for toggle selection
- Store-to-view synchronization (external selection updates)
- View-to-store synchronization (user selection updates)

The controller prevents infinite update loops using a synchronization flag and
handles patient number to well ID mapping for PCR plate coordination.

Architecture:
- QTableView selections ↔ InteractionStore ↔ Other widgets (plate, graphs)
- Patient numbers in table mapped to well IDs (A1-H12)
- Bidirectional sync with loop prevention
- Keyboard and mouse event handling

Example:
    Basic usage in table setup::

        from app.controllers.table.table_interaction_controller import TableInteractionController
        from app.services.interaction_store import InteractionStore
        from PyQt5.QtWidgets import QTableView

        # Create table and store
        table = QTableView()
        store = InteractionStore()
        data_service = PCRDataService()

        # Create controller (wires everything)
        controller = TableInteractionController(
            table_widget=table,
            pcr_data_service=data_service,
            graph_drawer=graph_view,
            interaction_store=store
        )

        # Now table clicks update store → other widgets respond
        # And store changes update table selection

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from typing import Set

from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QAbstractItemView, QApplication

from app.services.interaction_store import InteractionStore
from app.utils import well_mapping

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Edit trigger modes for table
EDIT_TRIGGERS = QAbstractItemView.SelectedClicked | QAbstractItemView.CurrentChanged

# Selection modes
SELECTION_BEHAVIOR = QAbstractItemView.SelectRows
SELECTION_MODE = QAbstractItemView.ExtendedSelection

# Keyboard keys for selection confirmation
SELECTION_KEYS = (Qt.Key_Return, Qt.Key_Enter)


# ============================================================================
# Controller
# ============================================================================

class TableInteractionController(QObject):
    """Controller synchronizing table row selection with interaction store.
    
    This controller implements bidirectional synchronization between:
    - User selections in QTableView (mouse clicks, keyboard)
    - Application-wide InteractionStore (shared selection state)
    
    Key Features:
    - Click handling with Ctrl+Click toggle support
    - Enter/Return key navigation
    - Store → View synchronization (external updates)
    - View → Store synchronization (user updates)
    - Loop prevention via _syncing_from_store flag
    - Patient number ↔ well ID mapping
    
    Synchronization Flow:
        User clicks table row
        → _on_item_clicked()
        → InteractionStore.set_selection()
        → Store emits selectedChanged
        → _apply_store_selection()
        → Table selection updated
        
        External widget selects well
        → InteractionStore.set_selection()
        → Store emits selectedChanged
        → _apply_store_selection()
        → Table row selected
    
    Loop Prevention:
        _syncing_from_store flag prevents infinite loop:
        - Set to True when applying store selection to view
        - Checked in _on_view_selection_changed to skip store update
        - Reset to False after sync complete
    
    Attributes:
        table_widget: QTableView being controlled
        pcr_data_service: Service for PCR data retrieval
        graph_drawer: Optional graph view for visualization
        interaction_store: Shared interaction state store
    """

    def __init__(
        self,
        table_widget,
        pcr_data_service,
        graph_drawer=None,
        interaction_store: InteractionStore | None = None
    ):
        """Initialize table interaction controller.
        
        Sets up table widget with appropriate selection modes, edit triggers,
        and connects event handlers. If interaction_store is provided, wires
        it immediately; otherwise expects set_interaction_store() call later.
        
        Args:
            table_widget: QTableView or QTableWidget instance
            pcr_data_service: Service providing PCR data access
            graph_drawer: Optional graph view widget for visualization
            interaction_store: Optional interaction store (can be set later)
        
        Note:
            - Sets ExtendedSelection mode (multi-select with Ctrl/Shift)
            - Sets SelectRows behavior (entire row selected)
            - Installs event filter for keyboard handling
            - Connects selection model if available
        """
        super().__init__()
        
        self.table_widget = table_widget
        self.pcr_data_service = pcr_data_service
        self.graph_drawer = graph_drawer
        self.interaction_store: InteractionStore | None = interaction_store

        # Configure table selection behavior
        self.table_widget.setEditTriggers(EDIT_TRIGGERS)
        self.table_widget.setSelectionBehavior(SELECTION_BEHAVIOR)
        self.table_widget.setSelectionMode(SELECTION_MODE)

        # Synchronization state
        self._syncing_from_store = False
        self._selection_model = None

        # Connect signals
        self.table_widget.clicked.connect(self.on_item_clicked)
        self.table_widget.installEventFilter(self)
        
        # Attach selection model if available
        self.attach_selection_model()
        
        logger.debug("TableInteractionController initialized")

    def on_item_clicked(self, index):
        """Handle table row click events.
        
        Called when user clicks a table cell. Extracts patient number from
        clicked row, maps to well ID, and updates interaction store.
        
        Behavior:
        - Ctrl+Click: Toggle well selection (add/remove from selection)
        - Normal Click: Set well as sole selection (clear others)
        
        Args:
            index: QModelIndex of clicked cell
        
        Note:
            - Validates model has get_patient_no() method
            - Normalizes patient number (float → int)
            - Maps patient number to well ID (1-96 → A1-H12)
            - Skips update if interaction store not set
        """
        model = self.table_widget.model()
        if model is None or not index.isValid():
            logger.debug("Invalid model or index, skipping click")
            return

        row = index.row()

        # Validate model interface
        if not hasattr(model, "get_patient_no"):
            logger.warning(f"Table model doesn't provide get_patient_no(). Model type: {type(model).__name__}")
            return

        # Extract patient number
        raw_patient_no = model.get_patient_no(row)
        if raw_patient_no is None:
            logger.debug(f"Row {row} has no patient number, skipping")
            return

        patient_no = self._normalize_patient_no(raw_patient_no)
        if patient_no is None:
            logger.warning(f"Failed to normalize patient number: {raw_patient_no}")
            return

        # Map patient number to well ID
        try:
            wells = {well_mapping.patient_no_to_well_id(patient_no)}
        except ValueError as e:
            logger.warning(f"Invalid patient number for well mapping: {patient_no} - {e}")
            return

        # Update interaction store
        if self.interaction_store is None:
            logger.warning("InteractionStore not set, cannot process table selection")
            return

        # Check for Ctrl modifier (toggle vs set)
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            logger.debug(f"Ctrl+Click: toggling well {wells}")
            self.interaction_store.toggle_wells(wells)
        else:
            logger.debug(f"Click: setting selection to {wells}")
            self.interaction_store.set_selection(wells)

    @staticmethod
    def _normalize_patient_no(value) -> int | None:
        """Normalize patient number to integer.
        
        Handles both int and float inputs (Excel may return floats).
        
        Args:
            value: Patient number (int, float, or string)
        
        Returns:
            Integer patient number or None if invalid
        
        Example:
            >>> TableInteractionController._normalize_patient_no(42)
            42
            >>> TableInteractionController._normalize_patient_no(42.0)
            42
            >>> TableInteractionController._normalize_patient_no("42")
            42
            >>> TableInteractionController._normalize_patient_no("invalid")
            None
        """
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def eventFilter(self, obj, event):
        """Filter keyboard events for Enter/Return key handling.
        
        Intercepts Enter and Return keys to trigger selection on current row.
        This allows keyboard navigation with confirmation.
        
        Args:
            obj: Object receiving the event
            event: Qt event object
        
        Returns:
            True if event was handled, False to continue propagation
        
        Note:
            Only handles KeyPress events on the table widget itself.
        """
        if (
            obj == self.table_widget
            and event.type() == QEvent.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            if event.key() in SELECTION_KEYS:
                index = self.table_widget.currentIndex()
                if index.isValid():
                    logger.debug(f"Enter/Return pressed on row {index.row()}")
                    self.on_item_clicked(index)
                    return True  # Event handled
        
        return super().eventFilter(obj, event)

    def set_interaction_store(self, store: InteractionStore) -> None:
        """Set interaction store and wire signals.
        
        Called to connect this controller to the interaction store.
        Can be called during initialization or later. Connects to
        store's selectedChanged signal and applies current selection state.
        
        Args:
            store: InteractionStore instance to use
        
        Note:
            - Connects selectedChanged signal (may fail silently if already connected)
            - Immediately applies current store selection to table
        """
        self.interaction_store = store
        logger.debug("InteractionStore set, wiring signals")
        
        # Connect to store's selection changes
        try:
            self.interaction_store.selectedChanged.connect(self._apply_store_selection)
            logger.debug("Connected to InteractionStore.selectedChanged")
        except Exception as e:
            # Connection may fail if already connected (not an error)
            logger.debug(f"Could not connect to selectedChanged (may already be connected): {e}")

        # Apply current store state to table
        current_selection = self.interaction_store.selected_wells if self.interaction_store else set()
        self._apply_store_selection(current_selection)

    def attach_selection_model(self):
        """Attach to table's selection model for selection change events.
        
        Connects to QSelectionModel's selectionChanged signal to detect
        user selection changes (mouse drags, Shift+Click, etc.).
        
        Note:
            - Disconnects old selection model if present
            - Stores reference to prevent model from being garbage collected
            - Called during init and after model updates
        """
        sel_model = self.table_widget.selectionModel()
        if sel_model is None or sel_model is self._selection_model:
            logger.debug("Selection model unchanged or unavailable")
            return

        # Disconnect old selection model
        if self._selection_model is not None:
            try:
                self._selection_model.selectionChanged.disconnect(self._on_view_selection_changed)
                logger.debug("Disconnected old selection model")
            except Exception:
                pass

        # Connect new selection model
        self._selection_model = sel_model
        self._selection_model.selectionChanged.connect(self._on_view_selection_changed)
        logger.debug("Attached new selection model")

    def _on_view_selection_changed(self, selected, deselected):
        """Handle selection changes from view (user drags, Shift+Click, etc.).
        
        Called when table selection changes through mouse drags or keyboard.
        Updates interaction store with new selection unless currently syncing
        from store (prevents infinite loop).
        
        Args:
            selected: QItemSelection of newly selected items
            deselected: QItemSelection of newly deselected items
        
        Note:
            - Skips if _syncing_from_store is True (loop prevention)
            - Skips if Ctrl modifier active (handled by on_item_clicked)
            - Gathers all selected wells and updates store
        """
        # Prevent infinite loop during store-to-view sync
        if self.interaction_store is None or self._syncing_from_store:
            return

        # Ctrl+Click handling is done in on_item_clicked, skip here
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            logger.debug("Ctrl modifier active, skipping view selection change")
            return

        # Gather currently selected wells
        wells = self._gather_selected_wells()
        
        if wells:
            logger.debug(f"View selection changed: {wells}")
            self.interaction_store.set_selection(wells)
        else:
            logger.debug("View selection cleared")
            self.interaction_store.clear_selection()

    def _gather_selected_wells(self) -> Set[str]:
        """Gather well IDs for all currently selected table rows.
        
        Iterates through selected rows, extracts patient numbers,
        and maps them to well IDs.
        
        Returns:
            Set of well IDs (e.g., {"A1", "F12", "H9"})
        
        Note:
            - Skips rows with invalid patient numbers
            - Skips rows that can't be mapped to well IDs
            - Returns empty set if model is invalid
        """
        model = self.table_widget.model()
        if model is None or not hasattr(model, "get_patient_no"):
            logger.debug("Cannot gather wells: invalid model")
            return set()

        wells: Set[str] = set()
        
        for idx in self.table_widget.selectionModel().selectedRows():
            # Get patient number for this row
            pn = self._normalize_patient_no(model.get_patient_no(idx.row()))
            if pn is None:
                continue
            
            # Map to well ID
            try:
                well_id = well_mapping.patient_no_to_well_id(pn)
                wells.add(well_id)
            except ValueError as e:
                logger.debug(f"Skipping invalid patient number {pn}: {e}")
                continue
        
        logger.debug(f"Gathered {len(wells)} wells from selected rows")
        return wells

    def _apply_store_selection(self, wells: Set[str]) -> None:
        """Apply interaction store selection to table view.
        
        Syncs table row selection to match wells in interaction store.
        This is the store-to-view direction of synchronization.
        
        Args:
            wells: Set of well IDs to select in table
        
        Flow:
            1. Map well IDs to patient numbers
            2. Clear current table selection
            3. Select rows matching patient numbers
            4. Use _syncing_from_store flag to prevent loop
        
        Note:
            - Validates well IDs before mapping
            - Skips invalid or unmappable wells
            - Blocks view-to-store updates during sync
        """
        model = self.table_widget.model()
        sel_model = self.table_widget.selectionModel()
        
        if model is None or sel_model is None:
            logger.debug("Cannot apply store selection: model unavailable")
            return

        # Set sync flag to prevent infinite loop
        self._syncing_from_store = True
        
        try:
            # Clear current selection
            sel_model.clearSelection()
            
            # Map wells to patient numbers
            target_patients = set()
            for well in wells:
                if not well_mapping.is_valid_well_id(well):
                    logger.debug(f"Skipping invalid well ID: {well}")
                    continue
                
                try:
                    patient_no = well_mapping.well_id_to_patient_no(well)
                    target_patients.add(patient_no)
                except ValueError as e:
                    logger.debug(f"Skipping unmappable well {well}: {e}")
                    continue
            
            if not target_patients:
                logger.debug("No valid patients to select")
                return

            logger.debug(f"Applying store selection: {len(target_patients)} patients")
            
            # Select matching rows
            for row in range(model.rowCount()):
                pn_raw = model.get_patient_no(row) if hasattr(model, "get_patient_no") else None
                pn = self._normalize_patient_no(pn_raw)
                
                if pn in target_patients:
                    self.table_widget.selectRow(row)
                    
        finally:
            # Always reset sync flag
            self._syncing_from_store = False 
            
   #Karşılı tüm seçim İÇİN BUNU KULLANABİLİRSİN!!!!!!!!!!!!!         
        #     last_valid_index = QModelIndex()

        #     for row in range(model.rowCount()):
        #         pn_raw = model.get_patient_no(row) if hasattr(model, "get_patient_no") else None
        #         pn = self._normalize_patient_no(pn_raw)
                
        #         if pn in target_patients:
        #             row_index = model.index(row, 0) if hasattr(model, "index") else QModelIndex()
        #             if row_index.isValid():
        #                 sel_model.select(
        #                     row_index,
        #                     QItemSelectionModel.Select | QItemSelectionModel.Rows,
        #                 )
        #                 last_valid_index = row_index  # Son seçili satırı takip et

        #     # Multi-select korunur + son seçili satıra scroll
        #     if last_valid_index.isValid():
        #         self.table_widget.scrollTo(last_valid_index)

        # finally:
        #     self._syncing_from_store = False