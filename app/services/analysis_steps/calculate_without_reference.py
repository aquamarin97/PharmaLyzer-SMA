# app\services\analysis_steps\calculate_without_reference.py
# app/services/analysis_steps/calculate_without_reference.py
"""
Reference-free (static value optimization) calculation step.

CRITICAL: This module contains calibrated algorithms. Do not modify without validation.

Algorithm:
1. Select optimal cluster count k (3–9) via full optimization per candidate
2. Cluster ΔCt values (KMeans, k=selected)
3. Compute initial static value (weighted average with penalty)
4. Optimize static value (minimize log-MSE via L-BFGS-B)
5. Calculate statistical ratio
6. Classify patients
7. Apply gradient-based statistical adjustment
8. Reclassify patients

k Selection Criteria (evaluated on Güvenli Bölge samples only):
  Valid k  : ≥8 wells in [0.80, 1.20] AND ≤2 wells in [1.60, 2.40]
  Best k   : valid k whose mean ratio (in [0.80, 1.20]) is closest to 1.0
  Tie-break: minimum std of [0.80, 1.20] ratios
  Fallback : k=5 when no valid k found
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from joblib import parallel_backend

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import OptimizeResult, minimize
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)

# ============================================================================
# Constants (CALIBRATED – DO NOT CHANGE)
# ============================================================================

DEFAULT_STATIC_VALUE: Final[float] = 2.00
OPTIMIZATION_BOUNDS: Final[tuple[tuple[float, float], ...]] = ((-4.0, 4.0),)
GRADIENT_ATTRACTION: Final[float] = 0.5

# k-selection
K_RANGE: Final[tuple[int, ...]] = tuple(range(3, 10))   # 3, 4, …, 9
K_FALLBACK: Final[int] = 5
BAND_NEAR_ONE: Final[tuple[float, float]] = (0.80, 1.20)
BAND_NEAR_TWO: Final[tuple[float, float]] = (1.60, 2.40)
MIN_WELLS_NEAR_ONE: Final[int] = 8
MAX_WELLS_NEAR_TWO: Final[int] = 2

# Column names
_COL_DELTA_CT: Final[str] = "Δ Ct"
_COL_DELTA_DELTA_CT: Final[str] = "Δ_Δ Ct"
_COL_STAT_RATIO: Final[str] = "İstatistik Oranı"
_COL_SW_RESULT: Final[str] = "Yazılım Hasta Sonucu"
_COL_REGRESSION: Final[str] = "Regresyon"
_COL_WARNING: Final[str] = "Uyarı"
_COL_CLUSTER: Final[str] = "Cluster"

_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {_COL_REGRESSION, _COL_WARNING, _COL_DELTA_CT}
)
_VALID_REGRESSION: Final[str] = "Güvenli Bölge"
_REPEAT_LOWER_BOUND: Final[float] = 0.1

# Gradient zones (CALIBRATED – DO NOT CHANGE)
# Each tuple: (zone_min, zone_max, target, max_dist)
_GRADIENT_ZONES: Final[tuple[tuple[float, float, float, float], ...]] = (
    (0.25, 0.50, 0.50, 0.25),
    (0.50, 0.65, 0.50, 0.15),
    (0.78, 1.00, 1.00, 0.22),
    (1.00, 1.25, 1.00, 0.25),
    (1.25, 1.75, 1.50, 0.25),
)


# ============================================================================
# Data-classes
# ============================================================================

@dataclass(frozen=True)
class ClusterInfo:
    center: float
    count: int


@dataclass
class _KResult:
    """Internal result container for one k candidate evaluation."""
    k: int
    static_value: float
    count_near_one: int
    count_near_two: int
    mean_near_one: float    # mean of ratios in BAND_NEAR_ONE; inf if none
    std_near_one: float     # std  of ratios in BAND_NEAR_ONE; inf if none
    is_valid: bool


# ============================================================================
# Main class
# ============================================================================

class CalculateWithoutReference:
    """
    Reference-free patient classification.

    CRITICAL: Contains calibrated algorithms – do not modify core methods
    without validation against reference data.
    """

    def __init__(
        self,
        carrier_range: float,
        uncertain_range: float,
    ) -> None:
        """
        Args:
            carrier_range:   Upper threshold for carrier detection  (e.g. 0.5999).
            uncertain_range: Lower threshold for uncertain zone     (e.g. 0.6199).

        Raises:
            ValueError: On invalid threshold values.
        """
        if carrier_range <= 0 or uncertain_range <= 0:
            raise ValueError(
                f"carrier_range and uncertain_range must be positive; "
                f"got carrier_range={carrier_range}, uncertain_range={uncertain_range}"
            )
        if carrier_range >= uncertain_range:
            raise ValueError(
                f"carrier_range ({carrier_range}) must be less than "
                f"uncertain_range ({uncertain_range})"
            )

        self.carrier_range = float(carrier_range)
        self.uncertain_range = float(uncertain_range)

        # Populated after process() is called; exposed for diagnostics.
        self.df: pd.DataFrame | None = None
        self.selected_k: int = K_FALLBACK

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def process(self, df: pd.DataFrame | None = None) -> pd.DataFrame:
        """
        Execute reference-free calculation step.

        Args:
            df: Input DataFrame from previous pipeline step.

        Returns:
            DataFrame with İstatistik Oranı and Yazılım Hasta Sonucu columns.

        Raises:
            ValueError: If df is None, empty, or missing required columns.
        """
        if df is None:
            raise ValueError("DataFrame cannot be None. Called by pipeline.")
        if df.empty:
            raise ValueError("No data to process.")

        missing = _REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        self.df = df

        valid_for_stats, _ = self._split_valid_invalid(df)

        if valid_for_stats.empty:
            logger.warning(
                "No valid samples for statistical optimization; skipping."
            )
            return df

        static_value = self.optimize_static_value(valid_for_stats)

        empty_well_mask = df[_COL_WARNING] == "Boş Kuyu"
        valid_data = df.loc[~empty_well_mask].copy()
        invalid_data = df.loc[empty_well_mask].copy()

        valid_data = self._finalize_data(valid_data, static_value)
        return pd.concat([valid_data, invalid_data], ignore_index=True)

    def optimize_static_value(self, valid_data: pd.DataFrame) -> float:
        """
        Select optimal k and return the corresponding optimized static ΔCt value.

        Side-effect: updates self.selected_k.

        Args:
            valid_data: DataFrame containing only valid (Güvenli Bölge) samples.

        Returns:
            Optimized static value as float.
        """
        if valid_data.empty:
            logger.debug(
                f"Empty valid_data; returning default static value {DEFAULT_STATIC_VALUE}"
            )
            return DEFAULT_STATIC_VALUE

        selected_k, static_value = self._select_cluster_number(valid_data)
        self.selected_k = selected_k

        logger.info(
            f"optimize_static_value complete: "
            f"k={selected_k}, static_value={static_value:.6f}"
        )
        return static_value

    # ------------------------------------------------------------------ #
    # k-selection                                                          #
    # ------------------------------------------------------------------ #

    def _select_cluster_number(
        self, valid_data: pd.DataFrame
    ) -> tuple[int, float]:
        """
        Evaluate every k in K_RANGE (3–9) with a full optimization pass and
        select the one whose distribution best matches the expected pattern.

        Selection rules:
          1. Valid k : ≥MIN_WELLS_NEAR_ONE wells in BAND_NEAR_ONE
                       AND ≤MAX_WELLS_NEAR_TWO wells in BAND_NEAR_TWO
          2. Best k  : among valid candidates, minimise |mean(near_one) – 1.0|
          3. Tie-break: minimum std(near_one)
          4. Fallback : k=K_FALLBACK when no valid k exists

        Args:
            valid_data: Güvenli Bölge samples used for all sub-optimizations.

        Returns:
            (selected_k, static_value_for_selected_k)
        """
        results: list[_KResult] = []

        for k in K_RANGE:
            try:
                result = self._evaluate_k(k, valid_data)
                results.append(result)
                logger.debug(
                    f"k={k}: static={result.static_value:.4f}, "
                    f"near_one={result.count_near_one}, "
                    f"near_two={result.count_near_two}, "
                    f"mean={result.mean_near_one:.4f}, "
                    f"std={result.std_near_one:.4f}, "
                    f"valid={result.is_valid}"
                )
            except Exception as exc:
                logger.warning(f"k={k} evaluation failed: {exc}", exc_info=True)

        valid_results = [r for r in results if r.is_valid]

        if valid_results:
            best = min(
                valid_results,
                key=lambda r: (abs(r.mean_near_one - 1.0), r.std_near_one),
            )
            logger.info(
                f"Selected k={best.k}: "
                f"mean_near_one={best.mean_near_one:.4f}, "
                f"std_near_one={best.std_near_one:.4f}, "
                f"near_one={best.count_near_one}, "
                f"near_two={best.count_near_two}"
            )
            return best.k, best.static_value

        # Fallback: use pre-computed result for K_FALLBACK if available
        logger.warning(
            f"No valid k found in {K_RANGE}; falling back to k={K_FALLBACK}"
        )
        fallback_result = next((r for r in results if r.k == K_FALLBACK), None)
        if fallback_result is not None:
            return K_FALLBACK, fallback_result.static_value

        # Last resort
        logger.error(
            "Fallback k evaluation also missing; using DEFAULT_STATIC_VALUE"
        )
        return K_FALLBACK, DEFAULT_STATIC_VALUE

    def _evaluate_k(self, k: int, valid_data: pd.DataFrame) -> _KResult:
        """
        Run a full optimization for one k candidate and measure the resulting
        ratio distribution against BAND_NEAR_ONE and BAND_NEAR_TWO.

        Args:
            k:          Cluster count to evaluate.
            valid_data: Güvenli Bölge samples.

        Returns:
            _KResult populated with distribution statistics and validity flag.
        """
        clusters, clustered_df = self._cluster_delta_ct(valid_data, k=k)
        initial_static = self._compute_initial_static_value(clusters, clustered_df)
        static_value = self._optimize_delta_ct(clustered_df, initial_static)

        # Compute ratios on valid_data (k-independent, same sample set)
        delta_delta = valid_data[_COL_DELTA_CT] - static_value
        ratios: pd.Series = (
            (2.0 ** -delta_delta)
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        near_one_mask = ratios.between(*BAND_NEAR_ONE)
        near_two_mask = ratios.between(*BAND_NEAR_TWO)

        count_near_one = int(near_one_mask.sum())
        count_near_two = int(near_two_mask.sum())

        near_one_values = ratios[near_one_mask]
        mean_near_one = (
            float(near_one_values.mean()) if count_near_one > 0 else float("inf")
        )
        std_near_one = (
            float(near_one_values.std(ddof=0)) if count_near_one > 1 else float("inf")
        )

        is_valid = (
            count_near_one >= MIN_WELLS_NEAR_ONE
            and count_near_two <= MAX_WELLS_NEAR_TWO
        )

        return _KResult(
            k=k,
            static_value=static_value,
            count_near_one=count_near_one,
            count_near_two=count_near_two,
            mean_near_one=mean_near_one,
            std_near_one=std_near_one,
            is_valid=is_valid,
        )

    # ------------------------------------------------------------------ #
    # Calibrated core – DO NOT CHANGE                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def objective(
        x: NDArray[np.float64],
        df: pd.DataFrame,
        use_log_mse: bool = True,
    ) -> float:
        """CRITICAL: Calibrated objective function. x is a 1-element numpy array."""
        scalar_x = float(x[0])
        temp = df.copy()
        temp[_COL_DELTA_DELTA_CT] = temp[_COL_DELTA_CT] - scalar_x
        temp[_COL_STAT_RATIO] = 2.0 ** -temp[_COL_DELTA_DELTA_CT]

        if use_log_mse:
            log_ratios = np.log2(temp[_COL_STAT_RATIO])
            return float(np.mean((log_ratios - 0.0) ** 2))
        return float(np.mean((temp[_COL_STAT_RATIO] - 1.0) ** 2))

    def penalize_third_center(
        self,
        third_center: float,
        min_center: float,
        min_count: int,
        valid_data: pd.DataFrame,
        alpha: float = 1.0,
        threshold: float = 1.4,
        exp_base: float = 1.1,
    ) -> float:
        """CRITICAL: Calibrated penalty function."""
        ratio = third_center / min_center if min_center else float("inf")
        ct_std = float(np.std(valid_data[_COL_DELTA_CT]))
        beta = 1.0 + (ct_std / 2.0)
        exp_penalty_factor = float(exp_base ** min_count)

        if ratio <= threshold:
            return float(third_center)

        penalty = (
            alpha * ((ratio - threshold) ** beta) * min_center * exp_penalty_factor
        )
        return float(third_center - penalty)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _split_valid_invalid(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        valid_mask = (df[_COL_REGRESSION] == _VALID_REGRESSION) & (
            df[_COL_WARNING].isnull() | (df[_COL_WARNING] == "Düşük RFU Değeri")
        )
        return df.loc[valid_mask].copy(), df.loc[~valid_mask].copy()

    def _finalize_data(
        self, valid_data: pd.DataFrame, static_value: float
    ) -> pd.DataFrame:
        df = self._calculate_statistics(valid_data, static_value)
        df[_COL_SW_RESULT] = self._classify_patients(df)
        df = self._adjust_statistics(df)
        df[_COL_SW_RESULT] = self._classify_patients(df)
        return df


    def _cluster_delta_ct(
        self,
        valid_data: pd.DataFrame,
        k: int | None = None,
    ) -> tuple[list[ClusterInfo], pd.DataFrame]:
        """
        K-Means clustering with explicit threading backend to prevent 
        console window spawning on Windows frozen environments.
        """
        n_clusters = k if k is not None else self.selected_k
        delta_ct_values = valid_data[[_COL_DELTA_CT]].to_numpy()

        # Açıkça threading backend kullanımı: 
        # Bu blok KMeans'in yeni process (ve dolayısıyla pencere) açmasını engeller.
        with parallel_backend("threading"):
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
            df = valid_data.copy()
            df[_COL_CLUSTER] = kmeans.fit_predict(delta_ct_values)

        centers = kmeans.cluster_centers_.flatten()
        counts = df[_COL_CLUSTER].value_counts().sort_index()
        
        clusters = sorted(
            [
                ClusterInfo(center=float(c), count=int(counts.get(i, 0)))
                for i, c in enumerate(centers)
            ],
            key=lambda ci: ci.center,
        )
        return clusters, df

    def _compute_initial_static_value(
        self,
        clusters: list[ClusterInfo],
        valid_data: pd.DataFrame,
    ) -> float:
        if len(clusters) < 3:
            centers = [c.center for c in clusters]
            return float(np.mean(centers)) if centers else DEFAULT_STATIC_VALUE

        min_c, second_c, third_c = clusters[0], clusters[1], clusters[2]
        third_adjusted = self.penalize_third_center(
            third_center=third_c.center,
            min_center=min_c.center,
            min_count=min_c.count,
            valid_data=valid_data,
        )

        denominator = (min_c.count + second_c.count + third_c.count) or 1
        numerator = (
            min_c.center * min_c.count
            + second_c.center * second_c.count
            + third_adjusted * third_c.count
        )
        return float(numerator / denominator)

    def _optimize_delta_ct(
        self,
        valid_data: pd.DataFrame,
        initial_static_value: float,
    ) -> float:
        temp = valid_data.copy()
        temp[_COL_DELTA_DELTA_CT] = temp[_COL_DELTA_CT] - initial_static_value
        temp[_COL_STAT_RATIO] = (2.0 ** -temp[_COL_DELTA_DELTA_CT]).round(6)

        filtered = temp[temp[_COL_STAT_RATIO].between(0.7, 1.3)]
        if filtered.empty:
            logger.debug(
                "No samples in 0.8–1.2 ratio range; "
                f"returning initial static value {initial_static_value:.6f}"
            )
            return float(initial_static_value)

        result: OptimizeResult = minimize(
            fun=self.objective,
            x0=np.array([initial_static_value], dtype=float),
            args=(filtered, True),
            bounds=OPTIMIZATION_BOUNDS,
            method="L-BFGS-B",
        )

        if not result.success:
            logger.warning(
                f"scipy.optimize.minimize did not converge: {result.message}. "
                f"Falling back to initial static value {initial_static_value:.6f}"
            )
            return float(initial_static_value)

        return float(round(float(result.x[0]), 6))

    def _calculate_statistics(
        self, df: pd.DataFrame, static_value: float
    ) -> pd.DataFrame:
        out = df.copy()
        out[_COL_DELTA_DELTA_CT] = out[_COL_DELTA_CT] - static_value
        out[_COL_STAT_RATIO] = 2.0 ** -out[_COL_DELTA_DELTA_CT]
        return out

    def _classify_patients(self, df: pd.DataFrame) -> pd.Series:
        def _classify(val: float) -> str:
            if pd.isna(val):
                return ""
            if val > self.uncertain_range:
                return "Sağlıklı"
            if self.carrier_range < val <= self.uncertain_range:
                return "Belirsiz"
            if _REPEAT_LOWER_BOUND < val <= self.carrier_range:
                return "Taşıyıcı"
            return "Tekrar"

        return df[_COL_STAT_RATIO].apply(_classify)

    def _adjust_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """CRITICAL: Gradient-based statistical adjustment. Calibrated."""
        out = df.copy()

        healthy_mask = (
            (out[_COL_SW_RESULT] == "Sağlıklı")
            & (out[_COL_REGRESSION] == _VALID_REGRESSION)
            & (out[_COL_STAT_RATIO].between(0.8, 1.2))
        )

        if not healthy_mask.any():
            return out

        out[_COL_STAT_RATIO] = out[_COL_STAT_RATIO].apply(_gradient_adjust)
        return out


# ============================================================================
# Module-level pure helper (easier to unit-test independently)
# ============================================================================

def _gradient_adjust(val: float) -> float:
    """CRITICAL: Gradient-based adjustment. Calibrated zones."""
    if pd.isna(val):
        return val

    for zone_min, zone_max, target, max_dist in _GRADIENT_ZONES:
        if zone_min <= val <= zone_max:
            distance = abs(val - target)
            if max_dist > 0:
                ratio = min(1.0, distance / max_dist)
                weight = ratio ** (1.0 / (GRADIENT_ATTRACTION + 0.5))
                return val + (target - val) * weight * GRADIENT_ATTRACTION
            return val

    return val


__all__ = ["CalculateWithoutReference", "ClusterInfo"]