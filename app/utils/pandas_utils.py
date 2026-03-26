# app\utils\pandas_utils.py
# app/utils/pandas_utils.py
"""
Pandas DataFrame utility functions.

Provides common DataFrame operations and validation utilities for
data processing and analysis workflows.

Usage:
    from app.utils.pandas_utils import (
        ensure_non_empty_df,
        validate_columns,
        safe_to_numeric
    )
    
    # Validate DataFrame
    df = ensure_non_empty_df(df, "Cannot process empty data")
    
    # Validate required columns
    validate_columns(df, ["Hasta No", "FAM Ct", "HEX Ct"])
    
    # Safe type conversion
    df["FAM Ct"] = safe_to_numeric(df["FAM Ct"])

Note:
    These utilities provide better error messages and type safety
    compared to raw pandas operations.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# DATAFRAME VALIDATION
# ============================================================================

def ensure_non_empty_df(
    df: pd.DataFrame | None,
    error_message: str = "DataFrame is empty or None"
) -> pd.DataFrame:
    """
    Validate that DataFrame is not None or empty.
    
    Args:
        df: DataFrame to validate
        error_message: Custom error message
        
    Returns:
        The validated DataFrame
        
    Raises:
        ValueError: If DataFrame is None or empty
        
    Example:
        >>> df = pd.DataFrame({"A": [1, 2, 3]})
        >>> validated = ensure_non_empty_df(df)
        >>> print(len(validated))
        3
        
        >>> empty_df = pd.DataFrame()
        >>> ensure_non_empty_df(empty_df)
        ValueError: DataFrame is empty or None
    """
    if df is None:
        logger.error("DataFrame is None")
        raise ValueError(error_message)
    
    if df.empty:
        logger.error("DataFrame is empty (0 rows)")
        raise ValueError(error_message)
    
    logger.debug(f"DataFrame validated: {len(df)} rows × {len(df.columns)} columns")
    return df


def validate_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    error_message: str | None = None
) -> pd.DataFrame:
    """
    Validate that DataFrame has required columns.
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        error_message: Custom error message (optional)
        
    Returns:
        The validated DataFrame
        
    Raises:
        ValueError: If required columns are missing
        
    Example:
        >>> df = pd.DataFrame({"A": [1], "B": [2]})
        >>> validate_columns(df, ["A", "B"])  # OK
        >>> validate_columns(df, ["A", "C"])  # Raises ValueError
    """
    missing = [col for col in required_columns if col not in df.columns]
    
    if missing:
        if error_message is None:
            error_message = (
                f"Missing required columns: {missing}. "
                f"Available: {list(df.columns)}"
            )
        logger.error(f"Column validation failed: {missing}")
        raise ValueError(error_message)
    
    logger.debug(f"All required columns present: {required_columns}")
    return df


# ============================================================================
# DATAFRAME OPERATIONS
# ============================================================================

def safe_to_numeric(
    series: pd.Series,
    errors: str = "coerce",
    default: Any = pd.NA
) -> pd.Series:
    """
    Safely convert series to numeric, handling errors gracefully.
    
    Args:
        series: Series to convert
        errors: How to handle errors ('coerce', 'raise', 'ignore')
        default: Default value for failed conversions (when errors='coerce')
        
    Returns:
        Converted numeric series
        
    Example:
        >>> s = pd.Series(["1.5", "2.3", "invalid", ""])
        >>> result = safe_to_numeric(s)
        >>> print(result.isna().sum())
        2  # "invalid" and "" became NA
    """
    try:
        result = pd.to_numeric(series, errors=errors)
        converted = (~result.isna()).sum()
        total = len(series)
        logger.debug(
            f"Converted {converted}/{total} values to numeric "
            f"({converted/total*100:.1f}%)"
        )
        return result
    except Exception as e:
        logger.error(f"Numeric conversion failed: {e}")
        raise


def drop_empty_rows(df: pd.DataFrame, how: str = "all") -> pd.DataFrame:
    """
    Remove rows with all or any NaN values.
    
    Args:
        df: DataFrame to clean
        how: 'all' (drop if all values NaN) or 'any' (drop if any NaN)
        
    Returns:
        DataFrame with empty rows removed
        
    Example:
        >>> df = pd.DataFrame({
        ...     "A": [1, None, 3],
        ...     "B": [None, None, 6]
        ... })
        >>> cleaned = drop_empty_rows(df, how="all")
        >>> len(cleaned)
        2  # Only middle row (all None) was dropped
    """
    before = len(df)
    cleaned = df.dropna(how=how)
    after = len(cleaned)
    
    if before != after:
        logger.info(f"Dropped {before - after} empty rows ({how})")
    
    return cleaned


def reset_index_clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reset DataFrame index without adding index column.
    
    Args:
        df: DataFrame to reset
        
    Returns:
        DataFrame with clean sequential index
        
    Example:
        >>> df = pd.DataFrame({"A": [1, 2]}, index=[5, 10])
        >>> clean = reset_index_clean(df)
        >>> list(clean.index)
        [0, 1]
    """
    return df.reset_index(drop=True)


# ============================================================================
# DATAFRAME INSPECTION
# ============================================================================

def get_column_info(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """
    Get summary information about DataFrame columns.
    
    Args:
        df: DataFrame to inspect
        
    Returns:
        Dictionary mapping column names to info dicts
        
    Info Dict Keys:
        - dtype: Column data type
        - null_count: Number of null values
        - null_pct: Percentage of null values
        - unique: Number of unique values
        
    Example:
        >>> df = pd.DataFrame({"A": [1, 2, None, 2]})
        >>> info = get_column_info(df)
        >>> print(info["A"]["null_pct"])
        25.0
    """
    info = {}
    
    for col in df.columns:
        null_count = df[col].isna().sum()
        total = len(df)
        
        info[col] = {
            "dtype": str(df[col].dtype),
            "null_count": int(null_count),
            "null_pct": round(null_count / total * 100, 2) if total > 0 else 0,
            "unique": int(df[col].nunique()),
        }
    
    return info


def log_dataframe_summary(df: pd.DataFrame, name: str = "DataFrame") -> None:
    """
    Log summary information about DataFrame.
    
    Args:
        df: DataFrame to summarize
        name: Name for logging output
        
    Example:
        >>> log_dataframe_summary(df, "Analysis Results")
        INFO: DataFrame 'Analysis Results': 100 rows × 5 columns
    """
    logger.info(
        f"{name}: {len(df)} rows × {len(df.columns)} columns"
    )
    
    # Log null counts if any
    null_counts = df.isna().sum()
    if null_counts.any():
        logger.debug(f"Null values: {null_counts[null_counts > 0].to_dict()}")


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Validation
    "ensure_non_empty_df",
    "validate_columns",
    
    # Operations
    "safe_to_numeric",
    "drop_empty_rows",
    "reset_index_clean",
    
    # Inspection
    "get_column_info",
    "log_dataframe_summary",
]