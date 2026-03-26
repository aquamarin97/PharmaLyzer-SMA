# app/services/pcr_data_service.py
"""
PCR graph coordinate data service (performance optimized).

Reads, parses, and caches FAM/HEX channel coordinates from DataStore
for PCR graph rendering. Uses LRU cache and version-based invalidation.

Thread Safety:
    NOT thread-safe. DataStore's thread safety is sufficient for reads.
    Do not use the same instance concurrently.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.services.data_store import DataStore
from app.utils import well_mapping

logger = logging.getLogger(__name__)

# ---- Type Aliases ----
Coord = Tuple[int, float]
CoordList = List[Coord]
WellID = str
PatientNo = int


@dataclass(frozen=True)
class PCRCoords:
    """FAM and HEX channel coordinates for a single patient."""

    fam: NDArray[np.float_]
    hex: NDArray[np.float_]

    def __post_init__(self) -> None:
        for name, arr in [("fam", self.fam), ("hex", self.hex)]:
            if arr.ndim != 2 or arr.shape[1] != 2:
                raise ValueError(f"{name} array must be shape (n, 2), got {arr.shape}")


class PCRDataService:
    """
    PCR coordinate data access and cache service.

    Cache Strategy:
        - Coordinates cached in _coords_cache dict
        - literal_eval results cached via LRU (4096 items)
        - Invalidated automatically when DataStore version changes
    """

    HASTA_NO_COL: str = "Hasta No"
    FAM_COL: str = "FAM koordinat list"
    HEX_COL: str = "HEX koordinat list"

    # Class-level cache (shared across instances)
    _coords_cache: Dict[PatientNo, PCRCoords] = {}
    _cached_version: int = -1
    _cache_token: int = 0

    # ---- Public API ----

    @staticmethod
    def get_coords(patient_no: Any) -> PCRCoords:
        """
        Return PCR coordinates for the specified patient.

        Args:
            patient_no: Patient number (1-96). Accepts int, float, or str.

        Returns:
            PCRCoords with immutable FAM and HEX arrays.

        Raises:
            ValueError: If DataStore is empty, patient_no is invalid,
                        or patient not found.
        """
        df = DataStore.get_df()
        if df is None or df.empty:
            raise ValueError("DataStore is empty. Load RDML data before requesting coordinates.")

        PCRDataService._validate_columns(df)
        PCRDataService._ensure_cache(df)

        pn = PCRDataService._normalize_patient_no(patient_no)
        cached = PCRDataService._coords_cache.get(pn)

        if cached is None:
            raise ValueError(
                f"Patient number {pn} not found in dataset. "
                f"Valid range: 1-{len(PCRDataService._coords_cache)}"
            )

        return cached

    @staticmethod
    def get_coords_for_wells(wells: Iterable[WellID]) -> Dict[WellID, PCRCoords]:
        """
        Return coordinates for multiple wells in a single batch call.

        Invalid well IDs are silently skipped.
        """
        valid_wells = [
            w.strip().upper()
            for w in wells or []
            if well_mapping.is_valid_well_id(w)
        ]

        if not valid_wells:
            return {}

        df = DataStore.get_df()
        if df is None or df.empty:
            raise ValueError("DataStore is empty. Load RDML data before requesting coordinates.")

        PCRDataService._validate_columns(df)
        PCRDataService._ensure_cache(df)

        coords_map: Dict[WellID, PCRCoords] = {}

        for well_id in valid_wells:
            try:
                pn = well_mapping.well_id_to_patient_no(well_id)
            except ValueError:
                logger.warning("Invalid well_id: %s, skipping", well_id)
                continue

            cached = PCRDataService._coords_cache.get(pn)
            if cached is not None:
                coords_map[well_id] = cached

        return coords_map

    @staticmethod
    def get_cache_token() -> int:
        """Return current cache token for external change detection."""
        df = DataStore.get_df()
        if df is None or df.empty:
            return PCRDataService._cache_token

        PCRDataService._validate_columns(df)
        PCRDataService._ensure_cache(df)

        return PCRDataService._cache_token

    @staticmethod
    def clear_cache() -> None:
        """Clear all cached coordinate data."""
        PCRDataService._literal_eval_cached.cache_clear()
        PCRDataService._coords_cache.clear()
        PCRDataService._cached_version = -1
        PCRDataService._cache_token += 1
        logger.info("PCRDataService cache cleared (token=%d)", PCRDataService._cache_token)

    # ---- Private Helpers ----

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        required = [
            PCRDataService.HASTA_NO_COL,
            PCRDataService.FAM_COL,
            PCRDataService.HEX_COL,
        ]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(
                f"Required columns missing from DataFrame: {missing}. "
                f"Available columns: {df.columns.tolist()}"
            )

    @staticmethod
    def _normalize_patient_no(patient_no: Any) -> PatientNo:
        try:
            pn = int(float(patient_no))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid patient number: {patient_no!r}. Expected int-convertible value."
            ) from exc

        if pn < 1 or pn > 96:
            raise ValueError(f"Patient number out of range: {pn}. Expected: 1-96")

        return pn

    @staticmethod
    @lru_cache(maxsize=4096)
    def _literal_eval_cached(raw: str) -> Any:
        return ast.literal_eval(raw)

    @staticmethod
    def _parse_coords_from_str(raw: str, label: str) -> NDArray[np.float_]:
        if not raw or not raw.strip():
            return np.empty((0, 2), dtype=float)
        parsed = PCRDataService._literal_eval_cached(raw)
        return PCRDataService._coords_from_iterable(parsed, label)

    @staticmethod
    def _coords_from_iterable(raw: Any, label: str) -> NDArray[np.float_]:
        if raw is None:
            return np.empty((0, 2), dtype=float)

        if not isinstance(raw, (list, tuple)):
            raise ValueError(
                f"{label} coordinate list must be list/tuple, got {type(raw).__name__}"
            )

        out: CoordList = []

        for item in raw:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            try:
                cycle = int(item[0])
                fluor = float(item[1])
                out.append((cycle, fluor))
            except (TypeError, ValueError):
                continue

        if not out:
            arr = np.empty((0, 2), dtype=float)
        else:
            arr = np.asarray(out, dtype=float)

        arr.setflags(write=False)
        return arr

    @staticmethod
    def _parse_coords_cached(raw: Any, label: str) -> NDArray[np.float_]:
        if isinstance(raw, str):
            try:
                return PCRDataService._parse_coords_from_str(raw, label)
            except Exception as exc:
                raise ValueError(f"{label} coordinate parse failed: {exc}") from exc

        return PCRDataService._coords_from_iterable(raw, label)

    @staticmethod
    def _ensure_cache(df: pd.DataFrame) -> None:
        """Rebuild cache if DataStore version has changed."""
        current_version = DataStore.get_version()

        if (
            PCRDataService._cached_version == current_version
            and PCRDataService._coords_cache
        ):
            return  # Cache is current

        logger.info(
            "Rebuilding PCR coordinate cache: DataFrame shape=%s, version=%d",
            df.shape, current_version,
        )

        PCRDataService._coords_cache.clear()
        PCRDataService._cached_version = current_version
        PCRDataService._cache_token += 1
        PCRDataService._literal_eval_cached.cache_clear()

        for _, row in df.iterrows():
            try:
                pn = PCRDataService._normalize_patient_no(row[PCRDataService.HASTA_NO_COL])
            except ValueError:
                continue

            fam_raw = row[PCRDataService.FAM_COL]
            hex_raw = row[PCRDataService.HEX_COL]

            try:
                fam_coords = PCRDataService._parse_coords_cached(fam_raw, label="FAM")
            except ValueError as exc:
                logger.warning("Patient %s FAM parse failed: %s", pn, exc)
                fam_coords = np.empty((0, 2), dtype=float)
                fam_coords.setflags(write=False)

            try:
                hex_coords = PCRDataService._parse_coords_cached(hex_raw, label="HEX")
            except ValueError as exc:
                logger.warning("Patient %s HEX parse failed: %s", pn, exc)
                hex_coords = np.empty((0, 2), dtype=float)
                hex_coords.setflags(write=False)

            try:
                PCRDataService._coords_cache[pn] = PCRCoords(fam=fam_coords, hex=hex_coords)
            except ValueError as exc:
                logger.warning("Patient %s PCRCoords creation failed, skipping: %s", pn, exc)
                continue

        logger.info(
            "PCR coordinate cache rebuilt: %d patients (token=%d)",
            len(PCRDataService._coords_cache),
            PCRDataService._cache_token,
        )


# ---- Convenience Functions ----

def get_patient_coords(patient_no: int) -> PCRCoords:
    return PCRDataService.get_coords(patient_no)


def get_well_coords(well_id: str) -> Optional[PCRCoords]:
    if not well_mapping.is_valid_well_id(well_id):
        return None
    try:
        pn = well_mapping.well_id_to_patient_no(well_id)
        return PCRDataService.get_coords(pn)
    except (ValueError, KeyError):
        return None


def is_cache_valid() -> bool:
    return bool(PCRDataService._coords_cache)