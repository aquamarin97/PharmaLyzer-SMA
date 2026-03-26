# app\services\graph\pcr_graph_layout_service.py
# -*- coding: utf-8 -*-
"""PCR graph layout service for data preparation and coordinate management.

This module provides utilities for preparing PCR fluorescence data for visualization.
It handles coordinate splitting (static vs. animated regions), axis limit calculation,
and flexible data format handling (tuples, arrays, sequences).

The service is designed to work with various visualization backends and supports
both static plotting and animated frame-by-frame rendering scenarios.

Example:
    Splitting data for animation::

        from app.services.graph.pcr_graph_layout_service import PCRGraphLayoutService

        fam_coords = [(0, 100), (1, 200), (2, 300), (3, 400)]
        hex_coords = [(0, 150), (1, 250), (2, 350), (3, 450)]

        # Split at cycle 2 (cycles 0-1 static, 2+ animated)
        split_data = PCRGraphLayoutService.split_static_anim(
            fam_coords=fam_coords,
            hex_coords=hex_coords,
            start_x=2
        )

        print(f"Static FAM points: {len(split_data.static_fam_x)}")  # 2
        print(f"Animated FAM points: {len(split_data.anim_fam_x)}")  # 2
        print(f"Animation frames: {split_data.frames}")  # 3

    Computing Y-axis limits::

        from app.services.graph.pcr_graph_layout_service import PCRGraphLayoutService
        import numpy as np

        # Mixed format coordinates (tuples and arrays)
        fam_coords = [(0, 1000), (1, 2000), np.array([[2, 3000], [3, 4000]])]
        hex_coords = [(0, 1500), (1, 2500)]

        ylim = PCRGraphLayoutService.compute_ylim_for_static_draw(
            fam_coords=fam_coords,
            hex_coords=hex_coords
        )
        print(ylim)  # (0.0, 4500.0) - auto-calculated with padding

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Sequence, Union

import numpy as np

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Type Aliases
# ============================================================================

# Single coordinate pair: (cycle_number, rfu_value)
Coord = Tuple[int, float]

# NumPy array of coordinates with shape (N, 2): [[cycle, rfu], ...]
CoordArray = np.ndarray

# Flexible coordinate sequence: can contain tuples, arrays, or mixed
CoordsLike = Sequence[Union[Coord, CoordArray]]


# ============================================================================
# Constants
# ============================================================================

# Default minimum Y-axis limit for split_static_anim (ensures visibility)
DEFAULT_MIN_Y_SPLIT = 5000.0

# Default Y-axis padding for split_static_anim (added to max value)
DEFAULT_Y_PADDING_SPLIT = 500.0

# Default minimum Y-axis limit for compute_ylim_for_static_draw
DEFAULT_MIN_Y_STATIC = 4500.0

# Default Y-axis padding for compute_ylim_for_static_draw
DEFAULT_Y_PADDING_STATIC = 500.0


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PCRSplitData:
    """Container for split PCR coordinate data (static vs. animated regions).

    This data class separates coordinates into two regions based on a cycle threshold:
    - Static region: Cycles before the threshold (displayed immediately)
    - Animated region: Cycles from threshold onwards (revealed frame-by-frame)

    Both FAM and HEX channels are split independently. The class also provides
    pre-calculated axis limits and frame count for animation control.

    Attributes:
        static_fam_x: X-coordinates (cycles) for static FAM data
        static_fam_y: Y-coordinates (RFU) for static FAM data
        static_hex_x: X-coordinates (cycles) for static HEX data
        static_hex_y: Y-coordinates (RFU) for static HEX data
        anim_fam_x: X-coordinates (cycles) for animated FAM data
        anim_fam_y: Y-coordinates (RFU) for animated FAM data
        anim_hex_x: X-coordinates (cycles) for animated HEX data
        anim_hex_y: Y-coordinates (RFU) for animated HEX data
        xlim: X-axis limits as (min, max), or None if no data
        ylim: Y-axis limits as (min, max), or None if no data

    Example:
        >>> split_data = PCRSplitData(
        ...     static_fam_x=[0, 1],
        ...     static_fam_y=[100.0, 200.0],
        ...     static_hex_x=[0, 1],
        ...     static_hex_y=[150.0, 250.0],
        ...     anim_fam_x=[2, 3],
        ...     anim_fam_y=[300.0, 400.0],
        ...     anim_hex_x=[2, 3],
        ...     anim_hex_y=[350.0, 450.0],
        ...     xlim=(0, 4),
        ...     ylim=(0.0, 5000.0)
        ... )
        >>> split_data.frames
        3
    """
    static_fam_x: List[int]
    static_fam_y: List[float]
    static_hex_x: List[int]
    static_hex_y: List[float]
    anim_fam_x: List[int]
    anim_fam_y: List[float]
    anim_hex_x: List[int]
    anim_hex_y: List[float]

    xlim: Optional[Tuple[float, float]]
    ylim: Optional[Tuple[float, float]]

    @property
    def frames(self) -> int:
        """Calculate total number of animation frames needed.

        Returns:
            Maximum number of animated points plus one (for static frame)

        Note:
            Frame count is based on the longer of FAM or HEX animated sequences.
            The +1 accounts for the initial static frame (frame 0).
        """
        return max(len(self.anim_fam_x), len(self.anim_hex_x)) + 1


# ============================================================================
# Service Class
# ============================================================================

class PCRGraphLayoutService:
    """Service for preparing PCR graph data layouts and coordinate transformations.

    This stateless service provides utilities for:
    - Splitting coordinates into static and animated regions
    - Computing appropriate axis limits with padding
    - Handling flexible coordinate formats (tuples, arrays, sequences)

    The service does not depend on any specific plotting library and can be used
    with various visualization backends (PyQtGraph, Matplotlib, etc.).

    All methods are static and thread-safe.

    Design Philosophy:
        - Accept flexible input formats (tuples, numpy arrays, mixed)
        - Provide robust error handling for malformed data
        - Calculate sensible defaults for visualization parameters
        - Maintain separation between data preparation and rendering
    """

    @staticmethod
    def split_static_anim(
        fam_coords: List[Coord],
        hex_coords: List[Coord],
        start_x: int,
        min_y_floor: float = DEFAULT_MIN_Y_SPLIT,
        y_padding: float = DEFAULT_Y_PADDING_SPLIT,
    ) -> PCRSplitData:
        """Split coordinate lists into static and animated regions.

        Separates coordinates based on cycle number (x-coordinate). Coordinates
        with cycle < start_x go to static lists, others to animated lists.
        Also calculates appropriate axis limits for the complete dataset.

        Args:
            fam_coords: FAM channel coordinates as list of (cycle, rfu) tuples
            hex_coords: HEX channel coordinates as list of (cycle, rfu) tuples
            start_x: Cycle number where animation begins (threshold)
            min_y_floor: Minimum Y-axis upper limit (default: 5000.0)
            y_padding: Padding added to max RFU value (default: 500.0)

        Returns:
            PCRSplitData containing separated static/animated coordinates and axis limits

        Example:
            >>> fam = [(0, 100), (1, 200), (2, 300)]
            >>> hex = [(0, 150), (1, 250), (2, 350)]
            >>> result = PCRGraphLayoutService.split_static_anim(
            ...     fam_coords=fam,
            ...     hex_coords=hex,
            ...     start_x=2
            ... )
            >>> result.static_fam_x
            [0, 1]
            >>> result.anim_fam_x
            [2]

        Note:
            - Empty input lists are handled gracefully (return empty lists)
            - X-coordinates are cast to int, Y-coordinates to float
            - Y-axis upper limit is max(min_y_floor, max_rfu + y_padding)
        """
        logger.info(
            f"Splitting PCR coordinates: start_x={start_x}, "
            f"FAM points={len(fam_coords or [])}, HEX points={len(hex_coords or [])}"
        )

        # Handle None inputs
        fam_coords = fam_coords or []
        hex_coords = hex_coords or []

        # Initialize output lists
        static_fam_x: List[int] = []
        static_fam_y: List[float] = []
        static_hex_x: List[int] = []
        static_hex_y: List[float] = []
        anim_fam_x: List[int] = []
        anim_fam_y: List[float] = []
        anim_hex_x: List[int] = []
        anim_hex_y: List[float] = []

        # Split FAM coordinates
        for x, y in fam_coords:
            if x < start_x:
                static_fam_x.append(int(x))
                static_fam_y.append(float(y))
            else:
                anim_fam_x.append(int(x))
                anim_fam_y.append(float(y))

        # Split HEX coordinates
        for x, y in hex_coords:
            if x < start_x:
                static_hex_x.append(int(x))
                static_hex_y.append(float(y))
            else:
                anim_hex_x.append(int(x))
                anim_hex_y.append(float(y))

        logger.debug(
            f"Split results - Static: FAM={len(static_fam_x)}, HEX={len(static_hex_x)} | "
            f"Animated: FAM={len(anim_fam_x)}, HEX={len(anim_hex_x)}"
        )

        # Calculate axis limits
        xlim, ylim = PCRGraphLayoutService._calculate_axis_limits(
            fam_coords=fam_coords,
            hex_coords=hex_coords,
            min_y_floor=min_y_floor,
            y_padding=y_padding
        )

        return PCRSplitData(
            static_fam_x=static_fam_x,
            static_fam_y=static_fam_y,
            static_hex_x=static_hex_x,
            static_hex_y=static_hex_y,
            anim_fam_x=anim_fam_x,
            anim_fam_y=anim_fam_y,
            anim_hex_x=anim_hex_x,
            anim_hex_y=anim_hex_y,
            xlim=xlim,
            ylim=ylim,
        )

    @staticmethod
    def compute_ylim_for_static_draw(
        fam_coords: CoordsLike,
        hex_coords: CoordsLike,
        min_floor: float = DEFAULT_MIN_Y_STATIC,
        y_padding: float = DEFAULT_Y_PADDING_STATIC,
    ) -> Optional[Tuple[float, float]]:
        """Compute Y-axis limits for static plot rendering.

        Handles flexible coordinate formats including tuples, numpy arrays, and mixed
        sequences. Extracts all Y-values, finds maximum, and applies padding.

        Args:
            fam_coords: FAM channel coordinates (flexible format)
            hex_coords: HEX channel coordinates (flexible format)
            min_floor: Minimum Y-axis upper limit (default: 4500.0)
            y_padding: Padding added to max RFU value (default: 500.0)

        Returns:
            Tuple of (y_min, y_max) where y_min=0.0, or None if no data

        Example:
            >>> import numpy as np
            >>> fam = [(0, 1000), np.array([[1, 2000], [2, 3000]])]
            >>> hex = [(0, 1500)]
            >>> ylim = PCRGraphLayoutService.compute_ylim_for_static_draw(
            ...     fam_coords=fam,
            ...     hex_coords=hex
            ... )
            >>> ylim
            (0.0, 3500.0)

        Note:
            - Supports mixed input formats (tuples and numpy arrays in same list)
            - Malformed data items are silently skipped (logged at debug level)
            - Returns None if no valid Y-values can be extracted
            - Y-axis always starts at 0.0
        """
        logger.info("Computing Y-axis limits for static PCR plot")

        # Handle None inputs
        fam_coords = fam_coords or []
        hex_coords = hex_coords or []

        all_y: List[float] = []

        # Extract Y-values from flexible coordinate formats
        PCRGraphLayoutService._collect_y_values(fam_coords, all_y)
        PCRGraphLayoutService._collect_y_values(hex_coords, all_y)

        # No data case
        if not all_y:
            logger.warning("No Y-values found in coordinate data")
            return None

        # Calculate upper limit with padding
        ymax = max(all_y)
        top = max(min_floor, ymax + y_padding)

        logger.debug(
            f"Y-axis limits calculated: (0.0, {top:.2f}) from {len(all_y)} points "
            f"(ymax={ymax:.2f}, padding={y_padding:.2f})"
        )

        return (0.0, float(top))

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    @staticmethod
    def _calculate_axis_limits(
        fam_coords: List[Coord],
        hex_coords: List[Coord],
        min_y_floor: float,
        y_padding: float
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Calculate X and Y axis limits from coordinate lists.

        Args:
            fam_coords: FAM channel coordinates
            hex_coords: HEX channel coordinates
            min_y_floor: Minimum Y-axis upper limit
            y_padding: Padding added to max RFU value

        Returns:
            Tuple of (xlim, ylim), each as (min, max) or None if no data
        """
        all_coords = fam_coords + hex_coords

        if not all_coords:
            logger.debug("No coordinates provided, axis limits set to None")
            return None, None

        # Extract X and Y values
        all_x = [x for x, _ in all_coords]
        all_y = [y for _, y in all_coords]

        # Calculate X limits with padding
        xlim: Optional[Tuple[float, float]] = None
        if all_x:
            xlim = (min(all_x) - 1, max(all_x) + 1)
            logger.debug(f"X-axis limits: {xlim}")

        # Calculate Y limits with padding
        ylim: Optional[Tuple[float, float]] = None
        if all_y:
            ymax = max(all_y)
            target_top = max(min_y_floor, ymax + y_padding)
            ylim = (0.0, float(target_top))
            logger.debug(f"Y-axis limits: {ylim} (ymax={ymax:.2f})")

        return xlim, ylim

    @staticmethod
    def _collect_y_values(coords: CoordsLike, output: List[float]) -> None:
        """Extract Y-values from flexible coordinate formats.

        Handles both tuple coordinates (x, y) and numpy array coordinates [[x, y], ...].
        Malformed items are silently skipped with debug logging.

        Args:
            coords: Coordinate sequence (flexible format)
            output: List to append extracted Y-values to (modified in-place)

        Note:
            This method modifies the output list in-place for performance.
            Malformed data does not raise exceptions but is logged.
        """
        for item in coords:
            # Handle numpy array format: shape (N, 2)
            if isinstance(item, np.ndarray):
                if item.size == 0:
                    continue

                # Ensure 2D array with at least 2 columns
                if item.ndim == 2 and item.shape[1] >= 2:
                    y_values = item[:, 1].astype(float).tolist()
                    output.extend(y_values)
                    logger.debug(f"Extracted {len(y_values)} Y-values from numpy array")
                else:
                    logger.debug(
                        f"Skipping numpy array with unexpected shape: {item.shape}"
                    )
                continue

            # Handle tuple/list format: (x, y)
            try:
                x, y = item  # type: ignore[misc]
                output.append(float(y))
            except (TypeError, ValueError) as e:
                # Malformed coordinate - skip silently
                logger.debug(f"Skipping malformed coordinate: {item} ({type(e).__name__})")
                continue