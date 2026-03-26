# app/views/plotting/pcr_graph_pg/spatial_index.py
# -*- coding: utf-8 -*-
"""
Spatial Index for PCR Graph Hover Detection.

Bounding box-based candidate filtering with vectorized numpy operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]


@dataclass
class WellSpatialIndex:
    """Spatial index for well curve segments using axis-aligned bounding boxes."""

    wells: list[str]
    boxes: np.ndarray  # shape (N, 4) => xmin, xmax, ymin, ymax

    def rect_candidates(self, x0: float, x1: float, y0: float, y1: float) -> list[str]:
        """Find wells whose bounding boxes intersect query rectangle."""
        if self.boxes.size == 0:
            return []

        xmin, xmax = self.boxes[:, 0], self.boxes[:, 1]
        ymin, ymax = self.boxes[:, 2], self.boxes[:, 3]

        mask = (xmax >= x0) & (xmin <= x1) & (ymax >= y0) & (ymin <= y1)

        if not np.any(mask):
            return []

        return [self.wells[i] for i in np.nonzero(mask)[0]]

    def point_candidates(self, x: float, y: float, tol_x: float, tol_y: float) -> list[str]:
        """Find wells whose expanded bounding boxes contain point."""
        if self.boxes.size == 0:
            return []

        xmin = self.boxes[:, 0] - tol_x
        xmax = self.boxes[:, 1] + tol_x
        ymin = self.boxes[:, 2] - tol_y
        ymax = self.boxes[:, 3] + tol_y

        mask = (xmin <= x) & (xmax >= x) & (ymin <= y) & (ymax >= y)

        if not np.any(mask):
            return []

        return [self.wells[i] for i in np.nonzero(mask)[0]]


def bounding_box(arrays: list[np.ndarray]) -> BBox | None:
    """Compute axis-aligned bounding box for curve arrays."""
    valid_arrays = [a for a in arrays if a is not None and a.size > 0]
    if not valid_arrays:
        return None

    stacked = np.vstack(valid_arrays)
    return (
        float(np.nanmin(stacked[:, 0])),
        float(np.nanmax(stacked[:, 0])),
        float(np.nanmin(stacked[:, 1])),
        float(np.nanmax(stacked[:, 1])),
    )


def build_spatial_index(
    well_geoms: dict[str, dict[str, np.ndarray]],
    *,
    fam_visible: bool,
    hex_visible: bool,
) -> WellSpatialIndex | None:
    """Build spatial index from well geometry data."""
    wells: list[str] = []
    boxes: list[BBox] = []

    for well_id, coords in well_geoms.items():
        arrays: list[np.ndarray] = []
        if fam_visible:
            fam = coords.get("fam")
            if fam is not None and fam.size > 0:
                arrays.append(fam)
        if hex_visible:
            hex_coords = coords.get("hex")
            if hex_coords is not None and hex_coords.size > 0:
                arrays.append(hex_coords)

        bbox = bounding_box(arrays)
        if bbox is None:
            continue
        wells.append(well_id)
        boxes.append(bbox)

    if not wells:
        return None

    logger.info("Spatial index built: %d wells, FAM=%s, HEX=%s", len(wells), fam_visible, hex_visible)
    return WellSpatialIndex(wells=wells, boxes=np.asarray(boxes, dtype=float))


def expand_bbox(bbox: BBox, margin: float) -> BBox:
    xmin, xmax, ymin, ymax = bbox
    return (xmin - margin, xmax + margin, ymin - margin, ymax + margin)


def bbox_area(bbox: BBox) -> float:
    xmin, xmax, ymin, ymax = bbox
    return max(0, xmax - xmin) * max(0, ymax - ymin)


def bbox_intersects(bbox1: BBox, bbox2: BBox) -> bool:
    xmin1, xmax1, ymin1, ymax1 = bbox1
    xmin2, xmax2, ymin2, ymax2 = bbox2
    return xmax1 >= xmin2 and xmin1 <= xmax2 and ymax1 >= ymin2 and ymin1 <= ymax2