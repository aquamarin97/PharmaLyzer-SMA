# app\views\plotting\pcr_graph_pg\renderer.py
# -*- coding: utf-8 -*-
"""
PCR Graph Renderer - PyQtGraph Implementation.

Main orchestrator for PCR amplification curve visualization:
- High-performance curve rendering (60+ FPS)
- Interactive selection/hover with distance threshold
- Smooth pan and zoom
- Automatic performance tuning for large datasets
- Frame rate limiting and render scheduling

Performance optimizations:
- Cached QPen objects (90% fewer creations)
- Spatial indexing for O(log n) hover detection
- Throttled drag updates (30ms default)
- Automatic downsampling (>20k points)
- Viewport clipping for large datasets
- Frame rate limiting (~60 FPS)

Architecture:
- Custom ViewBox for mouse interactions
- Deferred rendering via timer-based scheduling
- Overlay architecture (base + selection + hover)
- Store binding for shared state

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui

from app.constants.pcr_graph_style import PCRGraphStyle
from app.services.interaction_store import InteractionStore
from app.services.pcr_data_service import PCRCoords
from app.utils import well_mapping

from .axes import apply_axis_ranges, apply_axes_style, set_axis_ticks
from .interactions import PCRGraphViewBox
from .items_pg import refresh_legend_pg, rebuild_spatial_index, update_items
from .overlays_pg import build_overlay, make_hover_pen, make_preview_pen, update_overlays
from .styles import InteractionStyleChange, StyleState, apply_interaction_styles, set_channel_visibility

# Import interaction handlers
from .interaction_handlers_pg import (
    collect_preview_wells as collect_preview_wells_impl,
    flush_pending_drag as flush_pending_drag_impl,
    handle_click as handle_click_impl,
    handle_drag as handle_drag_impl,
    handle_hover as handle_hover_impl,
    on_store_preview_changed as on_store_preview_changed_impl,
)

# Import render scheduler
from .render_scheduler_pg import (
    flush_pending_render as flush_pending_render_impl,
    schedule_render as schedule_render_impl,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PCRGraphRendererPG(pg.PlotWidget):
    """
    PyQtGraph-based PCR graph renderer.

    High-performance amplification curve visualization with:
    - Real-time interaction (hover, selection, drag)
    - Smooth rendering (60+ FPS)
    - Automatic performance scaling
    - Distance-threshold hover (no ghost effects)

    Performance characteristics:
    - Small datasets (<20k points): Full quality rendering
    - Large datasets (>20k points): Automatic downsampling + clipping
    - Frame rate limited to prevent UI blocking
    - Cached pens/brushes to reduce allocations

    State management:
    - Supports InteractionStore binding for shared state
    - Internal fallback state when no store bound
    - Bidirectional sync (store ↔ renderer)
    """

    def __init__(
        self,
        parent=None,
        style: PCRGraphStyle | None = None,
    ) -> None:
        """
        Initialize PCR graph renderer.

        Args:
            parent: Parent widget
            style: PCRGraphStyle configuration (optional)
        """
        # Style configuration
        self._style = style or PCRGraphStyle()
        self._title = "PCR Grafik"

        # Custom ViewBox for interaction
        self._view_box = PCRGraphViewBox(self)
        self._view_box.setDefaultPadding(0.0)

        # Create plot item
        plot_item = pg.PlotItem(viewBox=self._view_box)
        plot_item.setMenuEnabled(False)
        plot_item.hideButtons()

        # Initialize PlotWidget
        super().__init__(
            parent=parent,
            plotItem=plot_item,
            background=self._style.axes.fig_facecolor,
        )

        self._plot_item: pg.PlotItem = plot_item

        # State management
        self._store: InteractionStore | None = None
        self._style_state: StyleState | None = None

        # Curve items (well_id -> PlotDataItem)
        self._fam_items: dict[str, pg.PlotDataItem] = {}
        self._hex_items: dict[str, pg.PlotDataItem] = {}
        self._hover_well: str | None = None

        # Overlay items
        self._hover_overlay = build_overlay(pen=make_hover_pen(self))
        self._preview_overlay = build_overlay(pen=make_preview_pen(self))

        # Channel visibility
        self._fam_visible = True
        self._hex_visible = True

        # Data caching
        self._rendered_wells: set[str] = set()
        self._data_cache_token: int = 0
        self._well_geoms: dict[str, dict[str, np.ndarray]] = {}
        self._spatial_index = None

        # Preview state
        self._rect_preview_wells: set[str] = set()

        # Well center cache (for fast queries)
        self._well_centers = np.empty((0, 2), dtype=float)
        self._well_center_ids: list[str] = []
        self._well_center_has_fam = np.array([], dtype=bool)
        self._well_center_has_hex = np.array([], dtype=bool)
        self._well_center_index: dict[str, int] = {}

        # UI components
        self._legend = pg.LegendItem(offset=(10, 10))
        self._legend.setParentItem(self._plot_item.graphicsItem())

        self._rect_roi = pg.RectROI(
            [0, 0],
            [0, 0],
            pen=pg.mkPen(
                self._style.overlay_color,
                width=self._style.overlay_roi_width,
            ),
            movable=False,
        )
        self._rect_roi.setZValue(50)
        self._rect_roi.setVisible(False)
        self._plot_item.addItem(self._rect_roi, ignoreBounds=True)

        # Render scheduling
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._flush_pending_render)
        self._frame_interval_ms = 16  # ~60 FPS
        self._pending_full_draw = False
        self._pending_overlay = False
        self._last_render_ts = perf_counter()

        # Drag throttling
        self._drag_throttle_ms = 30
        self._last_drag_ts = 0.0
        self._pending_drag: tuple[tuple[float, float], tuple[float, float]] | None = None
        self._drag_throttle_timer = QtCore.QTimer(self)
        self._drag_throttle_timer.setSingleShot(True)
        self._drag_throttle_timer.timeout.connect(self._flush_pending_drag)

        # Preview proxy (for large datasets)
        self._use_preview_proxy = False
        self._preview_proxy = pg.ScatterPlotItem(
            pen=None,
            brush=pg.mkBrush(QtGui.QColor(self._style.overlay_color)),
            size=6,
        )
        self._preview_proxy.setZValue(40)
        self._preview_proxy.setVisible(False)
        self._plot_item.addItem(self._preview_proxy, ignoreBounds=True)

        # Dynamic tick updates
        self._tick_update_timer = QtCore.QTimer(self)
        self._tick_update_timer.setSingleShot(True)
        self._tick_update_timer.timeout.connect(self._flush_pending_ticks)
        self._pending_tick_range: tuple[tuple[float, float], tuple[float, float]] | None = None
        self._last_tick_range: tuple[tuple[float, float], tuple[float, float]] | None = None

        # Performance flag
        self._large_dataset = False

        # Initialize
        self._setup_axes()
        self._plot_item.addItem(self._hover_overlay)
        self._plot_item.addItem(self._preview_overlay)

        # Connect signals
        self._view_box.sigRangeChanged.connect(self._on_view_range_changed)

        logger.info("PCRGraphRendererPG initialized")

    # ---- Lifecycle Management ----

    def reset(self) -> None:
        """
        Reset renderer to initial state.

        Clears all data, items, and cached state.

        Performance: Efficient cleanup, safe for repeated calls
        """
        logger.debug("Resetting renderer")

        # Clear state
        self._fam_items.clear()
        self._hex_items.clear()
        self._rendered_wells.clear()
        self._well_geoms.clear()
        self._spatial_index = None
        self._data_cache_token = 0
        self._style_state = None
        self._hover_well = None
        self._rect_preview_wells.clear()

        # Clear center cache
        self._well_centers = np.empty((0, 2), dtype=float)
        self._well_center_ids = []
        self._well_center_has_fam = np.array([], dtype=bool)
        self._well_center_has_hex = np.array([], dtype=bool)
        self._well_center_index = {}
        self._pending_drag = None

        # Clear scene
        try:
            self._plot_item.clear()
        except Exception as e:
            logger.warning(f"Plot clear error: {e}")

        # Clear legend
        try:
            self._legend.clear()
        except Exception as e:
            logger.warning(f"Legend clear error: {e}")

        # Clear overlays
        self._hover_overlay.clear()
        self._hover_overlay.setVisible(False)
        self._preview_overlay.clear()
        self._preview_overlay.setVisible(False)
        self._preview_proxy.setData([], [])
        self._preview_proxy.setVisible(False)

        # Re-add fixed items
        self._plot_item.addItem(self._rect_roi, ignoreBounds=True)
        self._plot_item.addItem(self._hover_overlay)
        self._plot_item.addItem(self._preview_overlay)
        self._plot_item.addItem(self._preview_proxy, ignoreBounds=True)

        # Reset axes
        self._setup_axes()

        # Stop timers
        if self._render_timer.isActive():
            self._render_timer.stop()
        if self._drag_throttle_timer.isActive():
            self._drag_throttle_timer.stop()
        if self._tick_update_timer.isActive():
            self._tick_update_timer.stop()

        logger.info("Renderer reset complete")

    def closeEvent(self, event) -> None:
        """
        Handle widget close event.

        Stops timers and cleans up resources.

        Args:
            event: Close event
        """
        logger.debug("Closing renderer")

        # Stop all timers
        if self._render_timer.isActive():
            self._render_timer.stop()
        if self._drag_throttle_timer.isActive():
            self._drag_throttle_timer.stop()
        if self._tick_update_timer.isActive():
            self._tick_update_timer.stop()

        # Clear legend
        try:
            self._legend.clear()
        except Exception:
            pass

        super().closeEvent(event)

    # ---- Public API ----

    def render_wells(
        self,
        data: dict[str, PCRCoords],
        *,
        cache_token: int | None = None,
    ) -> None:
        """
        Render PCR well data.

        Updates curve items based on incoming data. Uses cache token
        for change detection to avoid redundant updates.

        Args:
            data: Dictionary mapping well_id to PCRCoords
            cache_token: Optional cache token for change detection

        Performance: Early return if data unchanged, full update otherwise
        """
        incoming_wells = set(data.keys())
        token = cache_token if cache_token is not None else self._data_cache_token

        selected = set(self._store.selected_wells) if self._store else set()
        preview = self._collect_preview_wells()

        # Early return if data unchanged
        if (
            incoming_wells
            and incoming_wells == self._rendered_wells
            and token == self._data_cache_token
        ):
            logger.debug("Data unchanged, updating styles only")

            change = self._apply_interaction_styles(
                hovered=self._hover_well,
                selected=selected,
                preview=preview,
            )
            self._update_overlays(change)
            self._schedule_render(
                full=change.base_dirty,
                overlay=change.overlay_dirty or change.base_dirty,
            )
            return

        # Track if plot was empty (for force flush)
        plot_was_empty = not self._fam_items and not self._hex_items

        # Reset style state for full update
        self._style_state = None
        self._rendered_wells = incoming_wells
        self._data_cache_token = token

        logger.info(f"Rendering {len(incoming_wells)} wells, cache_token={token}")

        # Update items
        update_items(self, data)
        rebuild_spatial_index(self)

        # Apply styles
        change = self._apply_interaction_styles(
            hovered=self._hover_well,
            selected=selected,
            preview=preview,
        )
        self._update_overlays(change)

        # Schedule render (force flush if plot was empty)
        self._schedule_render(
            full=True,
            overlay=True,
            force_flush=plot_was_empty,
        )

    def set_hover(self, well: str | None) -> None:
        """
        Set hovered well.

        Args:
            well: Well ID to hover, or None to clear

        Performance: Early return if unchanged, single style update
        """
        # Normalize well ID
        normalized = well if well_mapping.is_valid_well_id(well) else None

        if normalized == self._hover_well:
            return

        self._hover_well = normalized

        logger.debug(f"Hover set: {normalized}")

        # Update styles
        change = self._apply_interaction_styles(
            hovered=self._hover_well,
            selected=set(self._store.selected_wells) if self._store else set(),
            preview=self._collect_preview_wells(),
        )
        self._update_overlays(change)
        self._schedule_render(full=change.base_dirty, overlay=True)

    def bind_interaction_store(self, store: InteractionStore | None) -> None:
        """
        Bind interaction store for state synchronization.

        Args:
            store: InteractionStore instance (None to unbind)

        Performance: Safe signal disconnection, queued connection
        """
        # Disconnect old store
        if self._store is not None:
            try:
                self._store.previewChanged.disconnect(self._on_store_preview_changed)
            except TypeError:
                # Not connected
                pass

        self._store = store

        # Connect new store
        if self._store is not None:
            self._store.previewChanged.connect(
                self._on_store_preview_changed,
                QtCore.Qt.QueuedConnection,
            )

        logger.info(f"Interaction store {'bound' if store else 'unbound'}")

    def set_channel_visibility(
        self,
        fam_visible: bool | None = None,
        hex_visible: bool | None = None,
    ) -> None:
        """
        Update channel visibility.

        Args:
            fam_visible: FAM channel visibility (None = no change)
            hex_visible: HEX channel visibility (None = no change)

        Performance: Early return if unchanged, full update otherwise
        """
        visibility_changed = set_channel_visibility(self, fam_visible, hex_visible)

        if not visibility_changed:
            return

        logger.debug(f"Channel visibility: FAM={self._fam_visible}, HEX={self._hex_visible}")

        # Update dependent components
        refresh_legend_pg(self)
        rebuild_spatial_index(self)
        self._update_preview_proxy(self._collect_preview_wells())

        # Update styles
        change = self._apply_interaction_styles(
            hovered=self._hover_well,
            selected=set(self._store.selected_wells) if self._store else set(),
            preview=self._collect_preview_wells(),
        )
        self._update_overlays(change)
        self._schedule_render(full=True, overlay=True)

    def set_title(self, title: str) -> None:
        """
        Update graph title.

        Args:
            title: New title text
        """
        self._title = title
        self._plot_item.setTitle(self._title, color=self._style.axes.title_color)

    # ---- Interaction Handlers (called by ViewBox) ----

    def handle_hover(self, pos: tuple[float, float] | None) -> None:
        """Delegate to interaction handler."""
        return handle_hover_impl(self, pos)

    def handle_click(self, pos: tuple[float, float], *, ctrl_pressed: bool) -> None:
        """Delegate to interaction handler."""
        return handle_click_impl(self, pos, ctrl_pressed=ctrl_pressed)

    def handle_drag(
        self,
        start: tuple[float, float],
        current: tuple[float, float],
        *,
        finished: bool,
    ) -> None:
        """Delegate to interaction handler."""
        return handle_drag_impl(self, start, current, finished=finished)

    # ---- Internal Helpers ----

    def _setup_axes(self) -> None:
        """Initialize axes with style configuration."""
        apply_axes_style(
            self,
            self._plot_item,
            self._view_box,
            self._style.axes,
            self._title,
            self._style.axes.default_xlim,
            self._style.axes.default_ylim,
        )

    def _update_overlays(self, change: InteractionStyleChange) -> None:
        """Update hover/preview overlays."""
        update_overlays(self, change)

    def _collect_preview_wells(self) -> set[str]:
        """Collect preview wells from store or local state."""
        return collect_preview_wells_impl(self)

    def _on_store_preview_changed(self, wells: set[str]) -> None:
        """Handle store preview change event."""
        return on_store_preview_changed_impl(self, wells)

    def _apply_interaction_styles(
        self,
        hovered: str | None,
        selected: set[str],
        preview: set[str],
    ) -> InteractionStyleChange:
        """Apply interaction-based styles."""
        return apply_interaction_styles(
            self,
            hovered=hovered,
            selected=selected,
            preview=preview,
        )

    def _update_preview_proxy(self, wells: set[str]) -> None:
        """Update preview proxy scatter plot."""
        if not self._use_preview_proxy:
            self._preview_proxy.setData([], [])
            self._preview_proxy.setVisible(False)
            return

        if not wells or not self._well_center_index:
            self._preview_proxy.setData([], [])
            self._preview_proxy.setVisible(False)
            return

        # Collect indices for preview wells
        indices: list[int] = []
        for well in wells:
            idx = self._well_center_index.get(well)
            if idx is None:
                continue

            # Check visibility
            fam_ok = self._fam_visible and self._well_center_has_fam[idx]
            hex_ok = self._hex_visible and self._well_center_has_hex[idx]

            if fam_ok or hex_ok:
                indices.append(idx)

        if not indices:
            self._preview_proxy.setData([], [])
            self._preview_proxy.setVisible(False)
            return

        # Update scatter plot
        coords = self._well_centers[indices]
        self._preview_proxy.setData(coords[:, 0], coords[:, 1])
        self._preview_proxy.setVisible(True)

    # ---- Render Scheduling ----

    def _schedule_render(
        self,
        *,
        full: bool = False,
        overlay: bool = False,
        force_flush: bool = False,
    ) -> None:
        """Delegate to render scheduler."""
        return schedule_render_impl(
            self,
            full=full,
            overlay=overlay,
            force_flush=force_flush,
        )

    def _flush_pending_render(self) -> None:
        """Delegate to render scheduler."""
        return flush_pending_render_impl(self)

    def _flush_pending_drag(self) -> None:
        """Delegate to interaction handler."""
        return flush_pending_drag_impl(self)

    def _apply_axis_ranges(
        self,
        *,
        xlim: tuple[float, float],
        ylim: tuple[float, float],
    ) -> None:
        """Apply axis ranges."""
        apply_axis_ranges(self._plot_item, self._view_box, xlim=xlim, ylim=ylim)

    def _on_view_range_changed(self, view_box, range_) -> None:
        """Handle view range change event."""
        if not range_ or len(range_) < 2:
            return

        x_range = (float(range_[0][0]), float(range_[0][1]))
        y_range = (float(range_[1][0]), float(range_[1][1]))

        if self._last_tick_range == (x_range, y_range):
            return

        self._pending_tick_range = (x_range, y_range)

        if not self._tick_update_timer.isActive():
            self._tick_update_timer.start(30)

    def update_axes_dynamically(self) -> None:
        """Update axis ticks dynamically based on visible range."""
        try:
            (x0, x1), (y0, y1) = self._view_box.viewRange()
            set_axis_ticks(self._plot_item, (x0, x1), (y0, y1))
        except Exception as e:
            logger.warning(f"Dynamic axis update error: {e}")

    def _flush_pending_ticks(self) -> None:
        """Flush pending tick updates."""
        if self._pending_tick_range is None:
            return

        x_range, y_range = self._pending_tick_range
        self._pending_tick_range = None
        self._last_tick_range = (x_range, y_range)

        set_axis_ticks(self._plot_item, x_range, y_range)