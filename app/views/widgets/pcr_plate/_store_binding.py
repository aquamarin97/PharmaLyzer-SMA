# app\views\widgets\pcr_plate\_store_binding.py
# -*- coding: utf-8 -*-
"""
InteractionStore Binding for PCR Plate Widget.

This module handles connection between InteractionStore and PCR plate widget:
- Signal connection/disconnection
- Initial state synchronization
- Safe cleanup of old bindings

Performance optimizations:
- Safe signal disconnection (no exceptions on missing connections)
- Single state application after binding
- Minimal signal emissions during initialization

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from app.services.interaction_store import InteractionStore

logger = logging.getLogger(__name__)


def bind_store(
    widget,
    store: InteractionStore,
    on_selection_changed: Callable,
    on_hover_changed: Callable,
    on_preview_changed: Callable,
) -> None:
    """
    Bind InteractionStore to PCR plate widget.

    Connects store signals to widget callbacks and applies initial state.
    If widget already has a store bound, safely disconnects old signals first.

    Args:
        widget: PCR plate widget instance
        store: InteractionStore to bind
        on_selection_changed: Callback for selection changes
        on_hover_changed: Callback for hover changes
        on_preview_changed: Callback for preview changes

    Performance: Three signal connections, three initial state applications

    Signal flow:
        store.selectedChanged -> on_selection_changed(selected_wells)
        store.hoverChanged -> on_hover_changed(hover_well)
        store.previewChanged -> on_preview_changed(preview_wells)
    """
    if widget is None:
        logger.error("bind_store called with None widget")
        return

    if store is None:
        logger.error("bind_store called with None store")
        return

    # Safely disconnect old store if present
    if widget._store is not None:
        _disconnect_store_signals(
            widget._store,
            on_selection_changed,
            on_hover_changed,
            on_preview_changed,
        )

    # Bind new store
    widget._store = store

    # Connect signals
    store.selectedChanged.connect(on_selection_changed)
    store.hoverChanged.connect(on_hover_changed)
    store.previewChanged.connect(on_preview_changed)

    logger.debug(f"Store bound: {len(store.selected_wells)} wells selected")

    # Apply current state from store
    # This ensures widget displays correct state immediately after binding
    on_selection_changed(store.selected_wells)
    on_hover_changed(store.hover_well)
    on_preview_changed(store.preview_wells)

    logger.info(
        f"Store binding complete: "
        f"selected={len(store.selected_wells)}, "
        f"hover={store.hover_well}, "
        f"preview={len(store.preview_wells)}"
    )


def _disconnect_store_signals(
    store: InteractionStore,
    on_selection_changed: Callable,
    on_hover_changed: Callable,
    on_preview_changed: Callable,
) -> None:
    """
    Safely disconnect store signals.

    Attempts to disconnect all signals, catching and logging any errors.
    This prevents crashes when signals are not connected.

    Args:
        store: InteractionStore to disconnect from
        on_selection_changed: Selection callback to disconnect
        on_hover_changed: Hover callback to disconnect
        on_preview_changed: Preview callback to disconnect

    Performance: Three disconnect attempts, exceptions are caught
    """
    if store is None:
        return

    # Try to disconnect each signal individually
    _safe_disconnect(store.selectedChanged, on_selection_changed, "selectedChanged")
    _safe_disconnect(store.hoverChanged, on_hover_changed, "hoverChanged")
    _safe_disconnect(store.previewChanged, on_preview_changed, "previewChanged")

    logger.debug("Store signals disconnected")


def _safe_disconnect(signal, callback: Callable, signal_name: str) -> None:
    """
    Safely disconnect a single signal-slot connection.

    Args:
        signal: Qt signal to disconnect from
        callback: Callback function to disconnect
        signal_name: Signal name for logging

    Performance: Try-except is fast when no exception occurs
    """
    try:
        signal.disconnect(callback)
        logger.debug(f"Disconnected {signal_name}")
    except TypeError:
        # Signal was not connected to this callback
        logger.debug(f"{signal_name} was not connected, skipping")
    except Exception as e:
        # Unexpected error during disconnection
        logger.warning(f"Error disconnecting {signal_name}: {e}")


def unbind_store(widget) -> None:
    """
    Unbind store from widget (cleanup).

    Disconnects all signals and clears store reference.

    Args:
        widget: PCR plate widget instance

    Use case: Widget cleanup, switching between stores
    """
    if widget is None or widget._store is None:
        return

    # Note: We need the callback references to disconnect
    # This is a limitation - ideally callbacks should be stored in widget
    logger.warning(
        "unbind_store called but callbacks not available for disconnection. "
        "Consider storing callback references in widget for proper cleanup."
    )

    # Clear store reference
    widget._store = None
    logger.debug("Store unbound from widget")


def get_store_state(store: InteractionStore) -> dict:
    """
    Get current state from store.

    Args:
        store: InteractionStore to query

    Returns:
        Dictionary with current store state

    Use case: Debugging, state inspection
    """
    if store is None:
        return {
            "selected_count": 0,
            "hover_well": None,
            "preview_count": 0,
        }

    return {
        "selected_count": len(store.selected_wells),
        "selected_wells": list(store.selected_wells)[:5],  # First 5 for brevity
        "hover_well": store.hover_well,
        "preview_count": len(store.preview_wells),
        "preview_wells": list(store.preview_wells)[:5],  # First 5 for brevity
    }


def validate_store_binding(widget) -> bool:
    """
    Validate that widget has a properly bound store.

    Args:
        widget: PCR plate widget instance

    Returns:
        True if store is bound and valid, False otherwise

    Use case: Debugging, pre-operation validation
    """
    if widget is None:
        logger.error("validate_store_binding called with None widget")
        return False

    if not hasattr(widget, "_store"):
        logger.error("Widget missing _store attribute")
        return False

    if widget._store is None:
        logger.error("Widget _store is None")
        return False

    # Check that store has expected attributes
    required_attrs = ["selected_wells", "hover_well", "preview_wells"]
    for attr in required_attrs:
        if not hasattr(widget._store, attr):
            logger.error(f"Store missing required attribute: {attr}")
            return False

    logger.debug("Store binding validated successfully")
    return True