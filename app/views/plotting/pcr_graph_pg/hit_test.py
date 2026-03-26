# app/views/plotting/pcr_graph_pg/hit_test.py
# -*- coding: utf-8 -*-
"""
Hit Testing for PCR Graph Mouse Interactions.

Provides spatial queries for curve selection:
- Rectangle selection (drag to select multiple curves)
- Nearest curve detection with distance threshold (hover/click)
- Efficient candidate filtering via spatial index
- Vectorized distance calculations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from .spatial_index import WellSpatialIndex

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Hover configuration
HOVER_DISTANCE_MULTIPLIER = 10.0
HOVER_PIXEL_THRESHOLD = 5.0


def wells_in_rect(
    index: WellSpatialIndex | None,
    well_geoms: dict[str, dict[str, np.ndarray]],
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    *,
    fam_visible: bool,
    hex_visible: bool,
) -> set[str]:
    """Find wells with curves intersecting rectangle."""
    if index is None:
        return set()

    x0, x1 = sorted([x0, x1])
    y0, y1 = sorted([y0, y1])

    candidates = index.rect_candidates(x0, x1, y0, y1)
    if not candidates:
        return set()

    wells: set[str] = set()
    for well in candidates:
        coords = well_geoms.get(well)
        if coords is None:
            continue

        if fam_visible:
            fam = coords.get("fam")
            if fam is not None and fam.size > 0:
                if _any_point_in_rect(fam, x0, x1, y0, y1):
                    wells.add(well)
                    continue

        if hex_visible:
            hex_coords = coords.get("hex")
            if hex_coords is not None and hex_coords.size > 0:
                if _any_point_in_rect(hex_coords, x0, x1, y0, y1):
                    wells.add(well)
                    continue

    return wells


def nearest_well(
    index: WellSpatialIndex | None,
    well_geoms: dict[str, dict[str, np.ndarray]],
    x: float,
    y: float,
    tol_x: float,
    tol_y: float,
    *,
    fam_visible: bool,
    hex_visible: bool,
) -> str | None:
    """Find nearest well to point with distance threshold."""
    if index is None:
        return None

    expanded_tol_x = tol_x * HOVER_PIXEL_THRESHOLD
    expanded_tol_y = tol_y * HOVER_PIXEL_THRESHOLD

    candidates = [
        w for w in index.point_candidates(x, y, expanded_tol_x, expanded_tol_y)
        if _well_has_visible_channel(well_geoms, w, fam_visible, hex_visible)
    ]

    if not candidates:
        return None

    best_well = None
    best_norm_dist = float("inf")

    for well in candidates:
        norm_dist = _normalized_distance_to_well(
            well_geoms, well, x, y, tol_x, tol_y, fam_visible, hex_visible
        )
        if norm_dist < best_norm_dist:
            best_norm_dist = norm_dist
            best_well = well

    if best_well is None or best_norm_dist > HOVER_PIXEL_THRESHOLD:
        return None

    return best_well


def _normalized_distance_to_well(
    well_geoms: dict[str, dict[str, np.ndarray]],
    well: str,
    x: float,
    y: float,
    tol_x: float,
    tol_y: float,
    fam_visible: bool,
    hex_visible: bool,
) -> float:
    """Normalized minimum distance from point to well curves (in pixel units)."""
    coords = well_geoms.get(well)
    if not coords:
        return float("inf")

    distances: list[float] = []

    if fam_visible:
        fam = coords.get("fam")
        if fam is not None and fam.size > 0:
            distances.append(_min_normalized_distance(x, y, fam, tol_x, tol_y))

    if hex_visible:
        hex_coords = coords.get("hex")
        if hex_coords is not None and hex_coords.size > 0:
            distances.append(_min_normalized_distance(x, y, hex_coords, tol_x, tol_y))

    return min(distances) if distances else float("inf")


def _min_normalized_distance(
    x: float,
    y: float,
    coords: np.ndarray,
    tol_x: float,
    tol_y: float,
) -> float:
    """Normalized minimum distance from point to curve (pixel units)."""
    if coords.shape[0] == 0:
        return float("inf")

    if coords.shape[0] == 1:
        norm_dx = (coords[0, 0] - x) / (tol_x + 1e-12)
        norm_dy = (coords[0, 1] - y) / (tol_y + 1e-12)
        return float(np.sqrt(norm_dx ** 2 + norm_dy ** 2))

    xs = coords[:, 0]
    ys = coords[:, 1]
    dx = xs[1:] - xs[:-1]
    dy = ys[1:] - ys[:-1]
    px = x - xs[:-1]
    py = y - ys[:-1]

    denom = dx * dx + dy * dy + 1e-12
    t = np.clip((px * dx + py * dy) / denom, 0.0, 1.0)

    proj_x = xs[:-1] + t * dx
    proj_y = ys[:-1] + t * dy

    norm_dx = (x - proj_x) / (tol_x + 1e-12)
    norm_dy = (y - proj_y) / (tol_y + 1e-12)

    norm_dists = np.sqrt(norm_dx ** 2 + norm_dy ** 2)
    return float(np.min(norm_dists))


def wells_in_rect_centers(
    well_ids: list[str],
    centers: np.ndarray,
    has_fam: np.ndarray,
    has_hex: np.ndarray,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    *,
    fam_visible: bool,
    hex_visible: bool,
) -> set[str]:
    """Find wells by center point inside rectangle (fast approximation)."""
    if centers is None or centers.size == 0 or not well_ids:
        return set()

    x0, x1 = sorted([x0, x1])
    y0, y1 = sorted([y0, y1])

    xs = centers[:, 0]
    ys = centers[:, 1]

    visible = np.zeros(len(centers), dtype=bool)
    if fam_visible and has_fam.size == len(centers):
        visible |= has_fam
    if hex_visible and has_hex.size == len(centers):
        visible |= has_hex

    if not np.any(visible):
        return set()

    inside = (x0 <= xs) & (xs <= x1) & (y0 <= ys) & (ys <= y1) & visible

    if not np.any(inside):
        return set()

    indices = np.nonzero(inside)[0]
    return {well_ids[i] for i in indices}


def _any_point_in_rect(
    coords: np.ndarray,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
) -> bool:
    """Test if any part of curve intersects rectangle (Liang-Barsky clipping)."""
    if coords.ndim != 2 or coords.shape[1] != 2:
        if coords.ndim == 2 and coords.shape[0] == 2:
            coords = coords.T
        else:
            return False

    xs = coords[:, 0]
    ys = coords[:, 1]

    mask = np.isfinite(xs) & np.isfinite(ys)
    if np.count_nonzero(mask) < 2:
        return False

    xs = xs[mask]
    ys = ys[mask]

    if xs.size == 1:
        return bool((x0 <= xs[0] <= x1) and (y0 <= ys[0] <= y1))

    if xs.size < 2:
        return False

    x_start = xs[:-1]
    y_start = ys[:-1]
    x_end = xs[1:]
    y_end = ys[1:]

    x0, x1 = sorted([x0, x1])
    y0, y1 = sorted([y0, y1])

    inside_start = (x0 <= x_start) & (x_start <= x1) & (y0 <= y_start) & (y_start <= y1)
    inside_end = (x0 <= x_end) & (x_end <= x1) & (y0 <= y_end) & (y_end <= y1)

    if np.any(inside_start | inside_end):
        return True

    dx = x_end - x_start
    dy = y_end - y_start

    u1 = np.zeros_like(dx, dtype=float)
    u2 = np.ones_like(dx, dtype=float)
    valid = np.ones_like(dx, dtype=bool)

    def _clip(p: np.ndarray, q: np.ndarray) -> None:
        nonlocal u1, u2, valid
        parallel = p == 0
        valid &= ~(parallel & (q < 0))
        if not np.any(valid):
            return
        ratio = np.empty_like(p, dtype=float)
        ratio[~parallel] = q[~parallel] / p[~parallel]
        ratio[parallel] = 0.0
        neg = (p < 0) & ~parallel
        pos = (p > 0) & ~parallel
        u1 = np.where(neg, np.maximum(u1, ratio), u1)
        u2 = np.where(pos, np.minimum(u2, ratio), u2)
        valid &= u1 <= u2

    _clip(-dx, x_start - x0)
    _clip(dx, x1 - x_start)
    _clip(-dy, y_start - y0)
    _clip(dy, y1 - y_start)

    return bool(np.any(valid))


def _well_has_visible_channel(
    well_geoms: dict[str, dict[str, np.ndarray]],
    well: str,
    fam_visible: bool,
    hex_visible: bool,
) -> bool:
    """Check if well has at least one visible channel with data."""
    coords = well_geoms.get(well)
    if not coords:
        return False
    fam_ok = fam_visible and coords.get("fam") is not None and coords["fam"].size > 0
    hex_ok = hex_visible and coords.get("hex") is not None and coords["hex"].size > 0
    return fam_ok or hex_ok


def _min_distance_sq(x: float, y: float, coords: np.ndarray) -> float:
    """Minimum squared distance from point to curve via segment projection."""
    if coords.shape[0] == 0:
        return float("inf")

    if coords.shape[0] == 1:
        dx = coords[0, 0] - x
        dy = coords[0, 1] - y
        return float(dx * dx + dy * dy)

    xs = coords[:, 0]
    ys = coords[:, 1]
    dx = xs[1:] - xs[:-1]
    dy = ys[1:] - ys[:-1]
    px = x - xs[:-1]
    py = y - ys[:-1]
    denom = dx * dx + dy * dy + 1e-12
    t = np.clip((px * dx + py * dy) / denom, 0.0, 1.0)
    proj_x = xs[:-1] + t * dx
    proj_y = ys[:-1] + t * dy
    dist_sq = (x - proj_x) ** 2 + (y - proj_y) ** 2
    return float(np.min(dist_sq))