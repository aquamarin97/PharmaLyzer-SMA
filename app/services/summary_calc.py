# app\services\summary_calc.py
# app/services/summary_calc.py
"""
Statistical summary calculation from analysis DataFrame.

Computes quality metrics and classification statistics:
- Well counts (analyzed, safe zone, risky area)
- Classification counts (healthy, carrier, uncertain)
- Statistical measures (mean, std, CV) for healthy samples

Critical: Calculation logic is calibrated. Do not modify without validation.
"""

from __future__ import annotations

import logging
from typing import Final

import pandas as pd

from app.services.analysis_summary import AnalysisSummary

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS (CALIBRATED)
# ============================================================================

# Column names
COL_WARNING: Final[str] = "Uyarı"
COL_REGRESSION: Final[str] = "Regresyon"
COL_SOFTWARE_RESULT: Final[str] = "Yazılım Hasta Sonucu"
COL_REFERENCE_RESULT: Final[str] = "Referans Hasta Sonucu"
COL_STATISTICAL_RATIO: Final[str] = "İstatistik Oranı"
COL_STANDARD_RATIO: Final[str] = "Standart Oranı"

# Classification values
CLASS_HEALTHY: Final[str] = "Sağlıklı"
CLASS_CARRIER: Final[str] = "Taşıyıcı"
CLASS_UNCERTAIN: Final[str] = "Belirsiz"
REG_SAFE_ZONE: Final[str] = "Güvenli Bölge"
REG_RISKY_AREA: Final[str] = "Riskli Alan"
WARN_EMPTY_WELL: Final[str] = "Boş Kuyu"

# Statistical thresholds (CALIBRATED - DO NOT CHANGE)
HEALTHY_RATIO_MIN: Final[float] = 0.70
"""Minimum ratio for healthy statistics calculation"""

HEALTHY_RATIO_MAX: Final[float] = 1.30
"""Maximum ratio for healthy statistics calculation"""


# ============================================================================
# SUMMARY CALCULATION
# ============================================================================

def build_summary_from_df(
    df: pd.DataFrame,
    *,
    use_without_reference: bool,
) -> AnalysisSummary:
    """
    Build statistical summary from analysis DataFrame.
    
    CRITICAL: Calculation logic is calibrated. Do not modify formulas.
    
    Args:
        df: Analysis DataFrame (after pipeline completion)
        use_without_reference: True for reference-free, False for reference-based
        
    Returns:
        AnalysisSummary with pre-formatted string values
        
    Calculations:
        - Counts: Direct value counts
        - Mean/Std: Calculated from safe zone healthy samples (0.70-1.30 ratio)
        - CV: (std / mean) * 100
    
    Example:
        >>> summary = build_summary_from_df(df, use_without_reference=True)
        >>> print(summary.healthy_avg)
        : 1.025
    
    Note:
        All output values include leading ": " for display formatting.
    """
    if df is None or df.empty:
        logger.warning("Empty DataFrame provided, returning empty summary")
        return AnalysisSummary()
    
    # ========================================================================
    # Well Counts
    # ========================================================================
    
    # Total analyzed wells (excluding empty wells)
    analyzed_well_count = int(
        (df[COL_WARNING] != WARN_EMPTY_WELL).sum()
        if COL_WARNING in df.columns else len(df)
    )
    
    # Regression zone counts
    safezone_count = int(
        (df.get(COL_REGRESSION) == REG_SAFE_ZONE).sum()
        if COL_REGRESSION in df.columns else 0
    )
    
    riskyarea_count = int(
        (df.get(COL_REGRESSION) == REG_RISKY_AREA).sum()
        if COL_REGRESSION in df.columns else 0
    )
    
    # ========================================================================
    # Select Result Column (Reference-free vs Reference-based)
    # ========================================================================
    
    if use_without_reference:
        result_col = COL_SOFTWARE_RESULT
        ratio_col = COL_STATISTICAL_RATIO
    else:
        result_col = COL_REFERENCE_RESULT
        ratio_col = COL_STANDARD_RATIO
    
    # ========================================================================
    # Classification Counts
    # ========================================================================
    
    healthy_count = int((df.get(result_col) == CLASS_HEALTHY).sum())
    carrier_count = int((df.get(result_col) == CLASS_CARRIER).sum())
    uncertain_count = int((df.get(result_col) == CLASS_UNCERTAIN).sum())
    
    # ========================================================================
    # Statistical Calculations (CALIBRATED)
    # ========================================================================
    
    if COL_REGRESSION in df.columns and ratio_col in df.columns:
        # Filter criteria (CALIBRATED - DO NOT CHANGE):
        # - Regression safe zone
        # - Ratio between 0.70 and 1.30
        mask = (
            (df[COL_REGRESSION] == REG_SAFE_ZONE) &
            (df[ratio_col].between(HEALTHY_RATIO_MIN, HEALTHY_RATIO_MAX))
        )
        
        series = pd.to_numeric(df.loc[mask, ratio_col], errors="coerce").dropna()
    else:
        series = pd.Series(dtype=float)
    
    # Calculate statistics
    if series.empty:
        h_avg_val, std_val, cv_val = 0.0, 0.0, 0.0
        logger.debug("No data for statistical calculation")
    else:
        h_avg_val = float(series.mean())
        std_val = float(series.std(ddof=0))  # Population std (ddof=0)
        cv_val = float((std_val / h_avg_val) * 100) if h_avg_val != 0 else 0.0
        
        logger.debug(
            f"Statistics: n={len(series)}, mean={h_avg_val:.3f}, "
            f"std={std_val:.3f}, cv={cv_val:.2f}%"
        )
    
    # ========================================================================
    # Format Output (with leading ": ")
    # ========================================================================
    
    return AnalysisSummary(
        analyzed_well_count=f": {analyzed_well_count}",
        safezone_count=f": {safezone_count}",
        riskyarea_count=f": {riskyarea_count}",
        healthy_count=f": {healthy_count}",
        carrier_count=f": {carrier_count}",
        uncertain_count=f": {uncertain_count}",
        healthy_avg=f": {h_avg_val:.3f}",
        std=f": {std_val:.3f}",
        cv=f": {cv_val:.2f}",
    )


__all__ = ["build_summary_from_df"]