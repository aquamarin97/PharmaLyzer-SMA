# app\services\interaction_store.py
# app/services/interaction_store.py
"""
Centralized UI interaction state management.

This module provides a single source of truth for UI interaction state:
- Selected wells (multi-selection)
- Hovered well (single well under cursor)
- Preview wells (temporary visual feedback)

All widgets read and write interaction state through this store,
ensuring consistent UI behavior across the application.

Usage:
    from app.services.interaction_store import InteractionStore
    
    # Create store (typically singleton in app)
    store = InteractionStore()
    
    # Connect to signals
    store.selectedChanged.connect(on_selection_changed)
    store.hoverChanged.connect(on_hover_changed)
    
    # Update state
    store.set_selection(["A01", "A02", "A03"])
    store.toggle_wells(["B01"])  # Add or remove
    store.set_hover("C05")
    
    # Clear state
    store.clear_selection()

Signals:
    - selectedChanged(set): Emitted when selection changes
    - hoverChanged(str|None): Emitted when hover changes
    - previewChanged(set): Emitted when preview changes

Thread Safety:
    This class uses Qt signals which are thread-safe by design.
    However, set/get operations are not atomic - use from main thread only.
"""

from __future__ import annotations

import logging
from typing import Iterable

from PyQt5.QtCore import QObject, pyqtSignal

from app.utils.well_mapping import is_valid_well_id

logger = logging.getLogger(__name__)


# ============================================================================
# INTERACTION STORE
# ============================================================================

class InteractionStore(QObject):
    """
    Centralized UI interaction state manager.
    
    Tracks three types of interaction state:
    1. Selection: User-selected wells (persistent until cleared)
    2. Hover: Well currently under cursor (transient)
    3. Preview: Wells shown for visual feedback (transient)
    
    All state changes emit Qt signals for reactive UI updates.
    
    Signals:
        selectedChanged(set): Selection changed (set of well IDs)
        hoverChanged(object): Hover changed (well ID or None)
        previewChanged(set): Preview changed (set of well IDs)
    
    Example:
        >>> store = InteractionStore()
        >>> store.selectedChanged.connect(lambda wells: print(f"Selected: {wells}"))
        >>> store.set_selection(["A01", "B02"])
        Selected: {'A01', 'B02'}
    """
    
    # ---- Signals ----
    
    selectedChanged = pyqtSignal(set)
    """Emitted when selection changes. Parameter: set of well IDs."""
    
    hoverChanged = pyqtSignal(object)
    """Emitted when hover changes. Parameter: well ID (str) or None."""
    
    previewChanged = pyqtSignal(set)
    """Emitted when preview changes. Parameter: set of well IDs."""
    
    # ---- Initialization ----
    
    def __init__(self):
        """
        Initialize interaction store with empty state.
        
        Initial State:
            - selected_wells: empty set
            - hover_well: None
            - preview_wells: empty set
        """
        super().__init__()
        
        self.selected_wells: set[str] = set()
        """Currently selected wells (persistent)"""
        
        self.hover_well: str | None = None
        """Well under cursor (transient)"""
        
        self.preview_wells: set[str] = set()
        """Wells shown for preview (transient)"""
    
    # ============================================================================
    # SELECTION MANAGEMENT
    # ============================================================================
    
    def set_selection(self, wells: Iterable[str]) -> None:
        """
        Set selected wells (replaces current selection).
        
        Args:
            wells: Iterable of well IDs to select
        
        Behavior:
            - Invalid well IDs are filtered out
            - Well IDs are normalized (uppercase, stripped)
            - Signal emitted only if selection changed
        
        Example:
            >>> store.set_selection(["A01", "B02", "invalid"])
            >>> print(store.selected_wells)
            {'A01', 'B02'}  # 'invalid' filtered out
        """
        normalized = self._normalize_wells(wells)
        
        if normalized == self.selected_wells:
            logger.debug("Selection unchanged, skipping signal")
            return
        
        self.selected_wells = normalized
        logger.debug(f"Selection set: {len(self.selected_wells)} wells")
        self.selectedChanged.emit(set(self.selected_wells))
    
    def toggle_wells(self, wells: Iterable[str]) -> None:
        """
        Toggle wells in selection (add if not selected, remove if selected).
        
        Args:
            wells: Iterable of well IDs to toggle
        
        Behavior:
            - If well is selected: remove it
            - If well is not selected: add it
            - Signal emitted only if selection changed
        
        Example:
            >>> store.set_selection(["A01", "B02"])
            >>> store.toggle_wells(["B02", "C03"])  # Remove B02, add C03
            >>> print(store.selected_wells)
            {'A01', 'C03'}
        """
        normalized = self._normalize_wells(wells)
        
        if not normalized:
            logger.debug("No valid wells to toggle")
            return
        
        updated = set(self.selected_wells)
        
        for well in normalized:
            if well in updated:
                updated.remove(well)
            else:
                updated.add(well)
        
        if updated == self.selected_wells:
            logger.debug("Toggle resulted in no change")
            return
        
        self.selected_wells = updated
        logger.debug(f"Selection toggled: {len(self.selected_wells)} wells")
        self.selectedChanged.emit(set(self.selected_wells))
    
    def add_to_selection(self, wells: Iterable[str]) -> None:
        """
        Add wells to selection (without removing existing).
        
        Args:
            wells: Iterable of well IDs to add
        
        Example:
            >>> store.set_selection(["A01"])
            >>> store.add_to_selection(["B02", "C03"])
            >>> print(store.selected_wells)
            {'A01', 'B02', 'C03'}
        """
        normalized = self._normalize_wells(wells)
        
        if not normalized:
            return
        
        updated = self.selected_wells | normalized
        
        if updated == self.selected_wells:
            return
        
        self.selected_wells = updated
        logger.debug(f"Added to selection: {len(self.selected_wells)} wells total")
        self.selectedChanged.emit(set(self.selected_wells))
    
    def remove_from_selection(self, wells: Iterable[str]) -> None:
        """
        Remove wells from selection.
        
        Args:
            wells: Iterable of well IDs to remove
        
        Example:
            >>> store.set_selection(["A01", "B02", "C03"])
            >>> store.remove_from_selection(["B02"])
            >>> print(store.selected_wells)
            {'A01', 'C03'}
        """
        normalized = self._normalize_wells(wells)
        
        if not normalized:
            return
        
        updated = self.selected_wells - normalized
        
        if updated == self.selected_wells:
            return
        
        self.selected_wells = updated
        logger.debug(f"Removed from selection: {len(self.selected_wells)} wells remaining")
        self.selectedChanged.emit(set(self.selected_wells))
    
    def clear_selection(self) -> None:
        """
        Clear all selected wells.
        
        Example:
            >>> store.set_selection(["A01", "B02"])
            >>> store.clear_selection()
            >>> print(store.selected_wells)
            set()
        """
        if not self.selected_wells:
            logger.debug("Selection already empty, skipping signal")
            return
        
        self.selected_wells.clear()
        logger.debug("Selection cleared")
        self.selectedChanged.emit(set())
    
    # ============================================================================
    # HOVER MANAGEMENT
    # ============================================================================
    
    def set_hover(self, well: str | None) -> None:
        """
        Set hovered well (well under cursor).
        
        Args:
            well: Well ID or None (no hover)
        
        Behavior:
            - Invalid well IDs are normalized to None
            - Signal emitted only if hover changed
        
        Example:
            >>> store.set_hover("A01")
            >>> store.set_hover(None)  # Clear hover
        """
        normalized = self._normalize_hover(well)
        
        if normalized == self.hover_well:
            return
        
        self.hover_well = normalized
        logger.debug(f"Hover set: {self.hover_well}")
        self.hoverChanged.emit(self.hover_well)
    
    def clear_hover(self) -> None:
        """
        Clear hover state.
        
        Example:
            >>> store.set_hover("A01")
            >>> store.clear_hover()
            >>> print(store.hover_well)
            None
        """
        self.set_hover(None)
    
    # ============================================================================
    # PREVIEW MANAGEMENT
    # ============================================================================
    
    def set_preview(self, wells: Iterable[str]) -> None:
        """
        Set preview wells (temporary visual feedback).
        
        Args:
            wells: Iterable of well IDs to preview
        
        Behavior:
            - Invalid well IDs are filtered out
            - Signal emitted only if preview changed
        
        Example:
            >>> store.set_preview(["A01", "A02", "A03"])
            >>> store.set_preview([])  # Clear preview
        """
        normalized = self._normalize_wells(wells)
        
        if normalized == self.preview_wells:
            return
        
        self.preview_wells = normalized
        logger.debug(f"Preview set: {len(self.preview_wells)} wells")
        self.previewChanged.emit(set(self.preview_wells))
    
    def clear_preview(self) -> None:
        """
        Clear preview state.
        
        Example:
            >>> store.set_preview(["A01", "B02"])
            >>> store.clear_preview()
            >>> print(store.preview_wells)
            set()
        """
        self.set_preview([])
    
    # ============================================================================
    # QUERY METHODS
    # ============================================================================
    
    def is_selected(self, well: str) -> bool:
        """
        Check if well is selected.
        
        Args:
            well: Well ID to check
            
        Returns:
            True if well is in selection, False otherwise
        """
        return well.strip().upper() in self.selected_wells
    
    def get_selection_count(self) -> int:
        """
        Get number of selected wells.
        
        Returns:
            Number of selected wells
        """
        return len(self.selected_wells)
    
    # ============================================================================
    # NORMALIZATION HELPERS
    # ============================================================================
    
    @staticmethod
    def _normalize_wells(wells: Iterable[str]) -> set[str]:
        """
        Normalize well IDs (uppercase, validate, deduplicate).
        
        Args:
            wells: Iterable of well IDs
            
        Returns:
            Set of normalized valid well IDs
        """
        normalized: set[str] = set()
        
        for well in wells or []:
            if is_valid_well_id(well):
                normalized.add(well.strip().upper())
            else:
                logger.debug(f"Invalid well ID filtered out: {well}")
        
        return normalized
    
    @staticmethod
    def _normalize_hover(well: str | None) -> str | None:
        """
        Normalize hover well ID.
        
        Args:
            well: Well ID or None
            
        Returns:
            Normalized well ID or None
        """
        if well is None:
            return None
        
        if is_valid_well_id(well):
            return well.strip().upper()
        
        logger.debug(f"Invalid hover well ID: {well}")
        return None


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "InteractionStore",
]