# app\views\plotting\pcr_graph_pg\items_pg.py
# -*- coding: utf-8 -*-
"""
PCR Graph Item Management.

This module provides curve item creation and management:
- PlotDataItem creation for FAM/HEX channels
- Spatial index rebuilding
- Axis limit calculation
- Performance tuning for large datasets
- Well center caching for fast queries

Performance optimizations:
- Clipping to viewport (large datasets)
- Automatic downsampling (>20k points)
- Efficient center point calculation
- Sorted well processing

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg

from app.services.graph.pcr_graph_layout_service import PCRGraphLayoutService
from app.services.pcr_data_service import PCRCoords
from app.utils import well_mapping

from .legend import refresh_legend
from .spatial_index import build_spatial_index

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Performance threshold for large datasets
LARGE_DATASET_THRESHOLD = 20000  # Total points across all curves


def update_items(renderer, data: dict[str, PCRCoords]) -> None:
    """
    Update renderer curve items from PCR data.

    Creates/updates PlotDataItem instances for each well's FAM/HEX channels.
    Manages item lifecycle (add/remove), geometry caching, and performance tuning.

    Args:
        renderer: Renderer instance with item caches
        data: Dictionary mapping well_id to PCRCoords

    Performance: O(wells × points_per_well), efficient for typical datasets

    Algorithm:
    1. Remove items for missing wells
    2. Create/update items for existing wells
    3. Cache well geometries for spatial queries
    4. Update center point cache
    5. Apply performance tuning for large datasets
    6. Refresh axes and legend
    """
    plot_item: pg.PlotItem = renderer._plot_item

    # Remove items for wells no longer in data
    _remove_missing_wells(renderer, data, plot_item)

    # Sort wells by patient number for consistent rendering order
    wells_sorted = sorted(
        data.keys(),
        key=lambda w: well_mapping.well_id_to_patient_no(w),
    )

    # Accumulate data for batch operations
    fam_all: list[np.ndarray] = []
    hex_all: list[np.ndarray] = []
    total_points = 0

    # Center point caching
    center_ids: list[str] = []
    center_points: list[tuple[float, float]] = []
    center_has_fam: list[bool] = []
    center_has_hex: list[bool] = []

    # Process each well
    for well in wells_sorted:
        coords = data.get(well)
        if coords is None:
            continue

        # Extract channel coordinates
        fam_coords = coords.fam
        hex_coords = coords.hex
        fam_has_data = fam_coords.size > 0
        hex_has_data = hex_coords.size > 0

        # Cache geometry for spatial queries
        renderer._well_geoms[well] = {
            "fam": fam_coords if fam_has_data else np.empty((0, 2), dtype=float),
            "hex": hex_coords if hex_has_data else np.empty((0, 2), dtype=float),
        }

        # Process FAM channel
        if fam_has_data:
            fam_all.append(fam_coords)
            total_points += fam_coords.shape[0]
            _update_or_create_item(
                renderer,
                renderer._fam_items,
                plot_item,
                well,
                fam_coords,
                renderer._fam_visible,
                "FAM",
            )
        else:
            _clear_item_data(renderer._fam_items, well)

        # Process HEX channel
        if hex_has_data:
            hex_all.append(hex_coords)
            total_points += hex_coords.shape[0]
            _update_or_create_item(
                renderer,
                renderer._hex_items,
                plot_item,
                well,
                hex_coords,
                renderer._hex_visible,
                "HEX",
            )
        else:
            _clear_item_data(renderer._hex_items, well)

        # Compute and cache center point
        center = _compute_well_center(
            fam_coords if fam_has_data else None,
            hex_coords if hex_has_data else None,
        )
        if center is not None:
            center_ids.append(well)
            center_points.append(center)
            center_has_fam.append(fam_has_data)
            center_has_hex.append(hex_has_data)

    # Performance tuning for large datasets
    renderer._large_dataset = total_points > LARGE_DATASET_THRESHOLD
    _apply_performance_tuning(renderer, renderer._large_dataset)

    logger.info(
        f"Items updated: {len(wells_sorted)} wells, {total_points} points, "
        f"large_dataset={renderer._large_dataset}"
    )

    # Update dependent components
    refresh_axes_limits(renderer, fam_all, hex_all)
    refresh_legend_pg(renderer)
    _update_center_cache(renderer, center_ids, center_points, center_has_fam, center_has_hex)


def refresh_axes_limits(
    renderer,
    fam_coords: list[np.ndarray],
    hex_coords: list[np.ndarray],
) -> None:
    """
    Calculate and apply axis limits based on data.

    Args:
        renderer: Renderer instance
        fam_coords: List of FAM channel coordinate arrays
        hex_coords: List of HEX channel coordinate arrays

    Performance: Single pass through data, efficient ylim calculation
    """
    ylim = PCRGraphLayoutService.compute_ylim_for_static_draw(
        fam_coords=fam_coords,
        hex_coords=hex_coords,
        min_floor=4500.0,
        y_padding=500.0,
    )

    target_ylim = ylim if ylim else renderer._style.axes.default_ylim

    renderer._apply_axis_ranges(
        xlim=renderer._style.axes.default_xlim,
        ylim=target_ylim,
    )

    logger.debug(f"Axes limits refreshed: xlim={renderer._style.axes.default_xlim}, ylim={target_ylim}")


def refresh_legend_pg(renderer) -> None:
    """
    Refresh legend based on visible channels.

    Args:
        renderer: Renderer instance

    Performance: Direct delegation to legend module
    """
    refresh_legend(renderer, renderer._legend)


def rebuild_spatial_index(renderer) -> None:
    """
    Rebuild spatial index from well geometries.

    Args:
        renderer: Renderer instance

    Performance: O(wells) bounding box calculation

    Use case: After data update or channel visibility change
    """
    renderer._spatial_index = build_spatial_index(
        renderer._well_geoms,
        fam_visible=renderer._fam_visible,
        hex_visible=renderer._hex_visible,
    )

    logger.debug(f"Spatial index rebuilt: {len(renderer._well_geoms)} wells")


# ---- Private Helper Functions ----


def _remove_missing_wells(renderer, data: dict, plot_item: pg.PlotItem) -> None:
    """
    Remove PlotDataItems for wells no longer in data.

    Args:
        renderer: Renderer instance
        data: Current data dictionary
        plot_item: PlotItem to remove items from

    Performance: O(removed_wells), efficient for typical updates
    """
    # Remove FAM items
    for well in list(renderer._fam_items.keys()):
        if well not in data:
            plot_item.removeItem(renderer._fam_items.pop(well))
            renderer._well_geoms.pop(well, None)

    # Remove HEX items
    for well in list(renderer._hex_items.keys()):
        if well not in data:
            plot_item.removeItem(renderer._hex_items.pop(well))
            renderer._well_geoms.pop(well, None)


def _update_or_create_item(
    renderer,
    items_dict: dict,
    plot_item: pg.PlotItem,
    well: str,
    coords: np.ndarray,
    visible: bool,
    channel_name: str,
) -> None:
    """
    Update existing PlotDataItem or create new one.

    Args:
        renderer: Renderer instance
        items_dict: Dictionary of well_id -> PlotDataItem (_fam_items or _hex_items)
        plot_item: PlotItem to add new items to
        well: Well ID
        coords: Curve coordinates (Nx2)
        visible: Channel visibility
        channel_name: "FAM" or "HEX"

    Performance: Single setData() call, efficient item creation
    """
    item = items_dict.get(well)

    if item is None:
        # Create new item
        item = pg.PlotDataItem(connect="finite", name=channel_name)
        plot_item.addItem(item)
        items_dict[well] = item

    # Update data and properties
    item.setData(coords[:, 0], coords[:, 1])
    item.setVisible(visible)
    item.setProperty("has_data", True)


def _clear_item_data(items_dict: dict, well: str) -> None:
    """
    Clear data for item that no longer has data.

    Args:
        items_dict: Dictionary of well_id -> PlotDataItem
        well: Well ID

    Performance: O(1) dictionary lookup
    """
    item = items_dict.get(well)
    if item is not None:
        item.setData([], [])
        item.setProperty("has_data", False)


def _compute_well_center(
    fam_coords: np.ndarray | None,
    hex_coords: np.ndarray | None,
) -> tuple[float, float] | None:
    """
    Compute center point of well curves.

    Args:
        fam_coords: FAM channel coordinates (Nx2) or None
        hex_coords: HEX channel coordinates (Nx2) or None

    Returns:
        (center_x, center_y) or None if no valid data

    Performance: O(points) mean calculation

    Algorithm: Combines all coordinates, filters invalid, computes mean
    """
    coords_list: list[np.ndarray] = []

    if fam_coords is not None and fam_coords.size > 0:
        coords_list.append(fam_coords)

    if hex_coords is not None and hex_coords.size > 0:
        coords_list.append(hex_coords)

    if not coords_list:
        return None

    # Stack all coordinates
    combined = np.vstack(coords_list)
    xs = combined[:, 0]
    ys = combined[:, 1]

    # Filter invalid values
    mask = np.isfinite(xs) & np.isfinite(ys)
    if not np.any(mask):
        return None

    # Compute center
    center_x = float(np.mean(xs[mask]))
    center_y = float(np.mean(ys[mask]))

    return center_x, center_y


def _update_center_cache(
    renderer,
    center_ids: list[str],
    center_points: list[tuple[float, float]],
    center_has_fam: list[bool],
    center_has_hex: list[bool],
) -> None:
    """
    Update well center point cache.

    Args:
        renderer: Renderer instance
        center_ids: List of well IDs
        center_points: List of (x, y) center coordinates
        center_has_fam: Boolean list indicating FAM presence
        center_has_hex: Boolean list indicating HEX presence

    Performance: O(n) numpy array creation, O(n) dictionary creation

    Use case: Fast center-based queries for approximate hit testing
    """
    if center_points:
        renderer._well_centers = np.array(center_points, dtype=float)
        renderer._well_center_ids = center_ids
        renderer._well_center_has_fam = np.array(center_has_fam, dtype=bool)
        renderer._well_center_has_hex = np.array(center_has_hex, dtype=bool)
        renderer._well_center_index = {
            well: idx for idx, well in enumerate(center_ids)
        }

        logger.debug(f"Center cache updated: {len(center_ids)} wells")
    else:
        # Clear cache
        renderer._well_centers = np.empty((0, 2), dtype=float)
        renderer._well_center_ids = []
        renderer._well_center_has_fam = np.array([], dtype=bool)
        renderer._well_center_has_hex = np.array([], dtype=bool)
        renderer._well_center_index = {}


def _apply_performance_tuning(renderer, enabled: bool) -> None:
    """
    Apply performance optimizations for large datasets.

    Args:
        renderer: Renderer instance
        enabled: Whether to enable performance optimizations

    Performance features:
    - ClipToView: Only renders visible portion (huge speedup for pan/zoom)
    - Downsampling: Peak detection downsampling for >20k points

    Algorithm:
    - enabled=True: Large dataset (>20k points) - enable optimizations
    - enabled=False: Small dataset - disable for maximum quality
    """
    all_items = list(renderer._fam_items.values()) + list(renderer._hex_items.values())

    for item in all_items:
        item.setClipToView(enabled)

        if enabled:
            # Enable downsampling with peak detection
            # Preserves curve shape while reducing points
            item.setDownsampling(auto=True, method="peak")
        else:
            # Disable downsampling for maximum quality
            item.setDownsampling(auto=False)

    logger.info(
        f"Performance tuning: {'enabled' if enabled else 'disabled'} "
        f"(ClipToView={enabled}, Downsampling={enabled})"
    )