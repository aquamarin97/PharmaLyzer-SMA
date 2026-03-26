# app\services\analysis_steps\calculate_regression.py
# app/services/analysis_steps/calculate_regression.py
"""
Regression-based outlier detection.

Classifies wells as "Güvenli Bölge" (safe zone) or "Riskli Alan" (risky area)
based on FAM/HEX RFU regression analysis.

Critical: Regression thresholds and algorithms are calibrated.
Do not modify without validation against reference data.
"""

from __future__ import annotations

import logging
from typing import Final

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS (CALIBRATED - DO NOT CHANGE)
# ============================================================================

LARGE_DATASET_THRESHOLD: Final[int] = 50
"""Use iterative regression if dataset > 50 samples"""

ITERATIVE_THRESHOLD: Final[float] = 2.0
"""Residual threshold for iterative regression"""

ITERATIVE_SIGMA_MULTIPLIER: Final[float] = 2.2
"""Sigma multiplier for iterative regression bounds"""

ITERATIVE_MAX_ITER: Final[int] = 10
"""Maximum iterations for iterative regression"""

MAD_THRESHOLD: Final[float] = 3.5
"""Modified Z-score threshold for MAD-based regression"""

MAD_MULTIPLIER: Final[float] = 0.6745
"""MAD to standard deviation conversion factor"""

MIN_SAFE_SAMPLES: Final[int] = 3
"""Minimum samples required for safe zone classification"""


# ============================================================================
# REGRESSION CALCULATOR
# ============================================================================

class CalculateRegression:
    """
    Regression-based outlier detection step.
    
    Algorithm:
    - Large datasets (>50): Iterative regression with outlier removal
    - Small datasets (≤50): MAD-based robust regression
    
    Warning:
        Thresholds are calibrated. Changing values requires
        validation against reference dataset.
    """
    
    def __init__(self):
        self.df: pd.DataFrame | None = None
    
    def process(self, df: pd.DataFrame | None = None) -> pd.DataFrame:
        """
        Execute regression analysis step.
        
        Args:
            df: Input DataFrame from previous step
            
        Returns:
            DataFrame with "Regresyon" column added
            
        Raises:
            ValueError: If df is None or empty
        """
        if df is None:
            raise ValueError("DataFrame cannot be None. Called by pipeline.")
        
        if df.empty:
            raise ValueError("No data to process.")
        
        self.df = df.copy(deep=False)
        self.calculate_regression()
        
        logger.info("Regression step completed")
        return self.df
    
    def calculate_regression(self) -> None:
        """Calculate regression and classify wells."""
        if self.df is None:
            raise ValueError("DataFrame is None")
        
        # Validate required columns
        required_columns = ["fam_end_rfu", "hex_end_rfu", "HEX Ct"]
        missing = [c for c in required_columns if c not in self.df.columns]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")
        
        # Filter valid data
        filtered_df = self.df.dropna(subset=["fam_end_rfu", "hex_end_rfu", "HEX Ct"])
        
        if filtered_df.empty:
            raise ValueError("No valid data for regression analysis")
        
        logger.debug(f"Regression analysis on {len(filtered_df)} samples")
        
        # Choose algorithm based on dataset size
        if len(filtered_df) > LARGE_DATASET_THRESHOLD:
            model, clean_df = self.iterative_regression(
                filtered_df, "fam_end_rfu", "hex_end_rfu"
            )
        else:
            model, clean_df = self.mad_based_regression(
                filtered_df, "fam_end_rfu", "hex_end_rfu"
            )
        
        # Default: risky area
        self.df["Regresyon"] = "Riskli Alan"
        
        # Mark safe zone samples
        self.df.loc[clean_df.index, "Regresyon"] = "Güvenli Bölge"
        
        # Override warnings: regression N/A for empty/insufficient DNA
        if "Uyarı" in self.df.columns:
            self.df.loc[
                self.df["Uyarı"].isin(["Yetersiz DNA", "Boş Kuyu"]),
                "Regresyon"
            ] = "-"
        
        logger.debug(
            f"Safe zone: {(self.df['Regresyon'] == 'Güvenli Bölge').sum()} wells"
        )
    
    def iterative_regression(
        self,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        threshold: float = ITERATIVE_THRESHOLD,
        max_iter: int = ITERATIVE_MAX_ITER
    ) -> tuple[LinearRegression, pd.DataFrame]:
        """
        Iterative regression with outlier removal.
        
        CRITICAL: Algorithm is calibrated. Do not modify.
        
        Args:
            df: Input data
            x_col: X variable column
            y_col: Y variable column
            threshold: Residual threshold
            max_iter: Maximum iterations
            
        Returns:
            Tuple of (model, clean_dataframe)
        """
        filtered_df = df.copy()
        model = LinearRegression()
        
        for iteration in range(max_iter):
            X = filtered_df[x_col].values.reshape(-1, 1)
            y = filtered_df[y_col].values
            
            model.fit(X, y)
            y_pred = model.predict(X)
            
            residuals = y - y_pred
            sigma = float(np.std(residuals))
            
            # Calibrated mask (DO NOT CHANGE)
            mask_upper = np.abs(residuals) <= (threshold + 10) + ITERATIVE_SIGMA_MULTIPLIER * sigma
            mask_lower = np.abs(residuals) >= (threshold) - ITERATIVE_SIGMA_MULTIPLIER * sigma
            mask = mask_upper & mask_lower
            
            new_filtered_df = filtered_df[mask]
            
            # Convergence check
            if new_filtered_df.shape[0] == filtered_df.shape[0]:
                logger.debug(f"Iterative regression converged at iteration {iteration}")
                break
            
            filtered_df = new_filtered_df
        
        return model, filtered_df
    
    def mad_based_regression(
        self,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        threshold: float = MAD_THRESHOLD
    ) -> tuple[LinearRegression, pd.DataFrame]:
        """
        MAD-based robust regression for small datasets.
        
        CRITICAL: Algorithm is calibrated. Do not modify.
        
        Args:
            df: Input data
            x_col: X variable column
            y_col: Y variable column
            threshold: Modified Z-score threshold
            
        Returns:
            Tuple of (model, clean_dataframe)
        """
        filtered_df = df.copy()
        
        if filtered_df.empty:
            return LinearRegression(), filtered_df
        
        X = filtered_df[x_col].values.reshape(-1, 1)
        y = filtered_df[y_col].values
        
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)
        
        residuals = y - y_pred
        median = float(np.median(residuals))
        abs_deviation = np.abs(residuals - median)
        mad = float(np.median(abs_deviation))
        
        if mad == 0:
            logger.debug("MAD=0, returning without filtering")
            return model, filtered_df
        
        # Modified Z-scores (DO NOT CHANGE)
        modified_z_scores = MAD_MULTIPLIER * (residuals - median) / mad
        mask = np.abs(modified_z_scores) <= threshold
        
        new_filtered_df = filtered_df[mask]
        
        # Safety check: minimum samples
        if new_filtered_df.shape[0] < MIN_SAFE_SAMPLES:
            logger.debug(
                f"Insufficient safe samples ({new_filtered_df.shape[0]}). "
                f"Using original dataset."
            )
            return model, filtered_df
        
        return model, new_filtered_df


__all__ = ["CalculateRegression"]