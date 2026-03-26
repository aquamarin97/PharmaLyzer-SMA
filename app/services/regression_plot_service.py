# app\services\regression_plot_service.py
# -*- coding: utf-8 -*-
"""Regression plot data generation service for PCR analysis.

This module provides functionality to generate regression plot data from PCR analysis results.
It handles data preprocessing, linear regression modeling, and safe band calculations without
any direct PyQtGraph dependencies, making it suitable for various visualization backends.

The service performs Min-Max scaling on RFU values and generates:
- Linear regression line
- Safe bands (±2.2σ from regression line)
- Scatter series grouped by classification labels

Example:
    Basic usage for generating plot data::

        import pandas as pd
        from app.services.regression_plot_service import RegressionPlotService

        # Prepare DataFrame with required columns
        df = pd.DataFrame({
            'hex_end_rfu': [1000, 2000, 3000],
            'fam_end_rfu': [1500, 2500, 3500],
            'Kuyu No': ['A1', 'A2', 'A3'],
            'Nihai Sonuç': ['Sağlıklı', 'Taşıyıcı', 'Belirsiz'],
            'Regresyon': ['Güvenli Bölge', 'Güvenli Bölge', 'Belirsiz']
        })

        # Generate plot data
        plot_data = RegressionPlotService.build(df)

        # Access components
        for series in plot_data.series:
            print(f"Label: {series.label}, Points: {len(series.x)}")

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Required DataFrame columns for regression analysis
REQUIRED_COLUMNS = [
    "hex_end_rfu",
    "fam_end_rfu",
    "Kuyu No",
    "Nihai Sonuç",
    "Regresyon"
]

# Allowed classification labels for plotting
ALLOWED_CLASSIFICATION_LABELS = [
    "Sağlıklı",
    "Taşıyıcı",
    "Belirsiz"
]

# Safe band width (σ multiplier)
# This matches the legacy CalculateRegression implementation (2.2 * sigma)
SAFE_BAND_SIGMA_MULTIPLIER = 2.2

# Safe region label used in training data filtering
SAFE_REGION_LABEL = "Güvenli Bölge"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass(frozen=True)
class ScatterSeries:
    """Represents a scatter plot series for a specific classification label.

    Attributes:
        label: Classification label (e.g., 'Sağlıklı', 'Taşıyıcı')
        x: X-axis coordinates (FAM channel RFU values, normalized)
        y: Y-axis coordinates (HEX channel RFU values, normalized)
        wells: Well identifiers for hover tooltips (e.g., 'A1', 'B2')
    """
    label: str
    x: np.ndarray
    y: np.ndarray
    wells: np.ndarray


@dataclass(frozen=True)
class SafeBand:
    """Represents the safe band boundaries around the regression line.

    The safe band is calculated as ±(SAFE_BAND_SIGMA_MULTIPLIER * σ) from the
    regression line, where σ is the standard deviation of training residuals.

    Attributes:
        x_sorted: X-axis coordinates (sorted)
        upper: Upper band boundary values
        lower: Lower band boundary values
    """
    x_sorted: np.ndarray
    upper: np.ndarray
    lower: np.ndarray


@dataclass(frozen=True)
class RegressionLine:
    """Represents the fitted linear regression line.

    Attributes:
        x_sorted: X-axis coordinates (sorted)
        y_pred_sorted: Predicted Y values along the regression line
    """
    x_sorted: np.ndarray
    y_pred_sorted: np.ndarray


@dataclass(frozen=True)
class RegressionPlotData:
    """Complete regression plot data package.

    This immutable container holds all components needed to render a regression plot:
    - Safe band boundaries
    - Regression line
    - Scatter series grouped by classification

    Attributes:
        safe_band: Safe band boundary data
        reg_line: Regression line data
        series: List of scatter series, one per classification label
    """
    safe_band: SafeBand
    reg_line: RegressionLine
    series: List[ScatterSeries]


# ============================================================================
# Service Class
# ============================================================================

class RegressionPlotService:
    """Service for generating regression plot data from PCR analysis results.

    This service transforms a DataFrame containing PCR analysis results into
    structured plot data suitable for visualization. It performs:

    1. Data validation and preprocessing
    2. Min-Max normalization of RFU values
    3. Linear regression modeling (trained on 'Güvenli Bölge' samples)
    4. Safe band calculation (±2.2σ)
    5. Data grouping by classification labels

    The service is stateless and uses only static methods.

    Note:
        This service does not depend on any specific plotting library.
        It provides pure data structures that can be consumed by any
        visualization backend (PyQtGraph, Matplotlib, etc.).

    Technical Details:
        - Min-Max scaling: (x - min) / (max - min)
        - Regression training: Only 'Güvenli Bölge' samples
        - Safe band width: 2.2 * σ (legacy compatibility)
        - Classification filtering: Only allowed labels are plotted
    """

    @staticmethod
    def build(df: pd.DataFrame) -> RegressionPlotData:
        """Build complete regression plot data from analysis DataFrame.

        This is the main entry point for the service. It orchestrates the entire
        data transformation pipeline from raw analysis results to plot-ready data.

        Args:
            df: DataFrame containing PCR analysis results with required columns:
                - hex_end_rfu: HEX channel endpoint RFU values
                - fam_end_rfu: FAM channel endpoint RFU values
                - Kuyu No: Well identifiers (e.g., 'A1', 'B2')
                - Nihai Sonuç: Final classification labels
                - Regresyon: Regression region labels

        Returns:
            RegressionPlotData containing:
                - safe_band: Safe band boundaries (±2.2σ)
                - reg_line: Fitted regression line
                - series: Scatter series grouped by classification

        Raises:
            ValueError: If DataFrame is empty or missing required columns

        Example:
            >>> df = pd.DataFrame({
            ...     'hex_end_rfu': [1000, 2000],
            ...     'fam_end_rfu': [1500, 2500],
            ...     'Kuyu No': ['A1', 'A2'],
            ...     'Nihai Sonuç': ['Sağlıklı', 'Taşıyıcı'],
            ...     'Regresyon': ['Güvenli Bölge', 'Güvenli Bölge']
            ... })
            >>> plot_data = RegressionPlotService.build(df)
            >>> len(plot_data.series)
            2
        """
        logger.info("Building regression plot data from DataFrame")
        RegressionPlotService._validate(df)

        # Work on a subset copy to minimize memory footprint
        work = df.loc[:, REQUIRED_COLUMNS].copy()
        logger.debug(f"Working with {len(work)} rows from input DataFrame")

        # Convert RFU columns to numeric, coercing errors to NaN
        work["fam_end_rfu"] = pd.to_numeric(work["fam_end_rfu"], errors="coerce")
        work["hex_end_rfu"] = pd.to_numeric(work["hex_end_rfu"], errors="coerce")

        # Apply Min-Max scaling to normalize RFU values
        RegressionPlotService._apply_min_max_scaling(work)

        # Drop rows with missing critical values
        initial_count = len(work)
        work.dropna(
            subset=["hex_end_rfu", "fam_end_rfu", "Kuyu No", "Nihai Sonuç"],
            inplace=True
        )
        dropped_count = initial_count - len(work)
        if dropped_count > 0:
            logger.debug(f"Dropped {dropped_count} rows with missing values")

        # Filter to allowed classification labels
        mask = work["Nihai Sonuç"].isin(ALLOWED_CLASSIFICATION_LABELS)
        work = work.loc[mask].copy()
        logger.debug(f"Filtered to {len(work)} rows with allowed classifications")

        # Prepare training data (only 'Güvenli Bölge' samples)
        train = work.loc[work["Regresyon"] == SAFE_REGION_LABEL].copy()
        logger.debug(f"Training regression model with {len(train)} safe region samples")

        # Return empty data if no training samples available
        if train.empty:
            logger.warning("No training data available for regression model")
            return RegressionPlotService._create_empty_plot_data()

        # Build and return regression plot data
        return RegressionPlotService._build_plot_data(train, work)

    @staticmethod
    def _validate(df: pd.DataFrame) -> None:
        """Validate input DataFrame for required structure.

        Args:
            df: DataFrame to validate

        Raises:
            ValueError: If DataFrame is None, empty, or missing required columns
        """
        if df is None or df.empty:
            raise ValueError("Regresyon grafiği için DataFrame boş.")

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Regresyon grafiği için eksik kolon(lar): {missing}"
            )

        logger.debug("DataFrame validation passed")

    @staticmethod
    def _apply_min_max_scaling(df: pd.DataFrame) -> None:
        """Apply Min-Max scaling to RFU columns in-place.

        Scales values to [0, 1] range using formula: (x - min) / (max - min)
        Handles edge case where max == min (no scaling applied).

        Args:
            df: DataFrame with 'fam_end_rfu' and 'hex_end_rfu' columns
                (modified in-place)

        Note:
            If a column has zero range (max == min), no scaling is applied
            to avoid division by zero.
        """
        # FAM channel scaling
        fam_min = df["fam_end_rfu"].min()
        fam_max = df["fam_end_rfu"].max()

        if fam_max > fam_min:
            df["fam_end_rfu"] = (df["fam_end_rfu"] - fam_min) / (fam_max - fam_min)
            logger.debug(f"FAM RFU scaled: [{fam_min:.2f}, {fam_max:.2f}] -> [0, 1]")
        else:
            logger.debug(f"FAM RFU has zero range ({fam_min:.2f}), skipping scaling")

        # HEX channel scaling
        hex_min = df["hex_end_rfu"].min()
        hex_max = df["hex_end_rfu"].max()

        if hex_max > hex_min:
            df["hex_end_rfu"] = (df["hex_end_rfu"] - hex_min) / (hex_max - hex_min)
            logger.debug(f"HEX RFU scaled: [{hex_min:.2f}, {hex_max:.2f}] -> [0, 1]")
        else:
            logger.debug(f"HEX RFU has zero range ({hex_min:.2f}), skipping scaling")

    @staticmethod
    def _create_empty_plot_data() -> RegressionPlotData:
        """Create empty plot data structure.

        Returns:
            RegressionPlotData with empty arrays and no series
        """
        empty = np.array([], dtype=float)
        return RegressionPlotData(
            safe_band=SafeBand(empty, empty, empty),
            reg_line=RegressionLine(empty, empty),
            series=[],
        )

    @staticmethod
    def _build_plot_data(
        train: pd.DataFrame,
        work: pd.DataFrame
    ) -> RegressionPlotData:
        """Build complete plot data from training and working DataFrames.

        Args:
            train: Training data (safe region samples only)
            work: All working data (filtered to allowed classifications)

        Returns:
            Complete RegressionPlotData structure
        """
        # Extract training arrays
        fam_train = train["fam_end_rfu"].astype(float).to_numpy()
        hex_train = train["hex_end_rfu"].astype(float).to_numpy()

        # Fit linear regression model
        X_train = fam_train.reshape(-1, 1)
        y_train = hex_train

        lr = LinearRegression()
        lr.fit(X_train, y_train)
        logger.debug(
            f"Linear regression fitted: "
            f"coef={lr.coef_[0]:.4f}, intercept={lr.intercept_:.4f}"
        )

        # Extract all plot points
        fam_all = work["fam_end_rfu"].astype(float).to_numpy()
        hex_all = work["hex_end_rfu"].astype(float).to_numpy()
        wells_all = work["Kuyu No"].astype(str).to_numpy()
        classification_all = work["Nihai Sonuç"].astype(str).to_numpy()

        # Safety check for empty data
        if fam_all.size == 0:
            logger.warning("No plot points available after filtering")
            return RegressionPlotService._create_empty_plot_data()

        # Calculate residual standard deviation from training data
        y_pred_train = lr.predict(X_train)
        residuals = y_train - y_pred_train
        sigma = float(np.std(residuals)) if residuals.size > 0 else 0.0
        logger.debug(f"Training residual σ = {sigma:.4f}")

        # Predict for all points
        X_all = fam_all.reshape(-1, 1)
        y_pred_all = lr.predict(X_all)

        # Calculate safe band boundaries
        band_width = SAFE_BAND_SIGMA_MULTIPLIER * sigma
        safe_upper = y_pred_all + band_width
        safe_lower = y_pred_all - band_width
        logger.debug(f"Safe band width: ±{band_width:.4f}")

        # Sort by X coordinate for clean line rendering
        sort_idx = np.argsort(fam_all)
        x_sorted = fam_all[sort_idx]

        # Create safe band object
        safe_band_obj = SafeBand(
            x_sorted=x_sorted,
            upper=safe_upper[sort_idx],
            lower=safe_lower[sort_idx],
        )

        # Create regression line object
        reg_line_obj = RegressionLine(
            x_sorted=x_sorted,
            y_pred_sorted=y_pred_all[sort_idx],
        )

        # Build scatter series grouped by classification label
        series: List[ScatterSeries] = []
        for label in ALLOWED_CLASSIFICATION_LABELS:
            idx = (classification_all == label)
            point_count = np.sum(idx)

            if point_count == 0:
                logger.debug(f"No points for classification '{label}', skipping series")
                continue

            series.append(
                ScatterSeries(
                    label=label,
                    x=fam_all[idx],
                    y=hex_all[idx],
                    wells=wells_all[idx],
                )
            )
            logger.debug(f"Created scatter series '{label}' with {point_count} points")

        logger.info(
            f"Regression plot data built successfully: "
            f"{len(series)} series, {len(x_sorted)} points total"
        )

        return RegressionPlotData(
            safe_band=safe_band_obj,
            reg_line=reg_line_obj,
            series=series,
        )