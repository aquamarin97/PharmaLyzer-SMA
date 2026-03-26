# app\services\analysis_steps\csv_processor.py
# app/services/analysis_steps/csv_processor.py
"""
CSV data preprocessing and enrichment.

This step performs initial data preparation:
- Fill missing React IDs (ensure all 96 wells)
- Parse coordinate lists (FAM/HEX)
- Calculate RFU endpoints and differences
- Calculate Delta Ct (FAM Ct - HEX Ct)
- Generate well numbers (Kuyu No)
- Apply quality warnings

Critical: This is the first step in the analysis pipeline.
All downstream steps depend on these calculations.

Note:
    Calculation logic is preserved exactly as-is.
    Only code quality improvements applied.
"""

from __future__ import annotations

import ast
import logging
import string
from typing import Any, Final

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

# Quality thresholds (DO NOT CHANGE - calibrated values)
CT_THRESHOLD: Final[float] = 30.0
"""Ct value threshold for insufficient DNA warning"""

RFU_THRESHOLD: Final[float] = 1200.0
"""RFU threshold for low fluorescence warning"""

TOTAL_WELLS: Final[int] = 96
"""Total wells in 96-well plate"""

NUM_ROWS: Final[int] = 8
"""Number of rows (A-H)"""

NUM_COLS: Final[int] = 12
"""Number of columns (1-12)"""


# ============================================================================
# CSV PROCESSOR
# ============================================================================

class CSVProcessor:
    """
    Initial data preprocessing step.
    
    Critical calculations performed:
    - RFU endpoint extraction
    - Delta Ct calculation
    - Quality warnings
    
    Warning:
        This is a stateless processor. Do not modify calculation logic
        without validation against reference data.
    """
    
    @staticmethod
    def process(df: pd.DataFrame | None = None) -> pd.DataFrame:
        """
        Process DataFrame through preprocessing pipeline.
        
        Args:
            df: Input DataFrame from RDML service
            
        Returns:
            Preprocessed DataFrame with quality flags
            
        Raises:
            ValueError: If df is None or empty
        """
        if df is None:
            raise ValueError("DataFrame cannot be None. Called by pipeline.")
        
        if df.empty:
            raise ValueError("DataFrame is empty. No data to process.")
        
        logger.info("Starting CSV preprocessing")
        result = CSVProcessor.improved_preprocess(df)
        logger.info(f"Preprocessing complete: {len(result)} rows")
        
        return result
    
    @staticmethod
    def improved_preprocess(df: pd.DataFrame) -> pd.DataFrame:
        """
        Main preprocessing workflow.
        
        Steps:
        1. Clear analysis columns (if re-processing)
        2. Fill missing React IDs (ensure 96 wells)
        3. Parse coordinate lists
        4. Calculate RFU endpoints
        5. Calculate Delta Ct
        6. Generate well numbers
        7. Apply quality warnings
        
        Args:
            df: Input DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        # Safe coordinate parser
        def safe_literal_eval(val: Any) -> list | None:
            if isinstance(val, str):
                try:
                    return ast.literal_eval(val)
                except Exception:
                    return None
            return None
        
        # Step 1: Clear analysis columns (for re-processing)
        cols_to_clear = [
            "Δ Ct", "Δ_Δ Ct", "İstatistik Oranı", "Yazılım Hasta Sonucu",
            "rfu_diff", "fam_end_rfu", "hex_end_rfu", "Kuyu No", "Cluster"
        ]
        df = df.drop(columns=[c for c in cols_to_clear if c in df.columns], errors="ignore")
        
        # Step 2: Fill missing React IDs (ensure 96 wells)
        df = CSVProcessor.fill_missing_react_ids(df)
        
        # Step 3: Ensure coordinate columns exist
        df["FAM koordinat list"] = df.get("FAM koordinat list", "[]")
        df["HEX koordinat list"] = df.get("HEX koordinat list", "[]")
        
        df["FAM koordinat list"] = df["FAM koordinat list"].fillna("[]").astype(str).replace("", "[]")
        df["HEX koordinat list"] = df["HEX koordinat list"].fillna("[]").astype(str).replace("", "[]")
        
        # Step 4: Extract RFU endpoints
        fam_end = []
        hex_end = []
        
        for val in df["FAM koordinat list"].values:
            parsed = safe_literal_eval(val)
            fam_end.append(parsed[-1][-1] if parsed else None)
        
        for val in df["HEX koordinat list"].values:
            parsed = safe_literal_eval(val)
            hex_end.append(parsed[-1][-1] if parsed else None)
        
        df["fam_end_rfu"] = pd.to_numeric(pd.Series(fam_end), errors="coerce").fillna(0.0)
        df["hex_end_rfu"] = pd.to_numeric(pd.Series(hex_end), errors="coerce").fillna(0.0)
        df["rfu_diff"] = df["fam_end_rfu"] - df["hex_end_rfu"]
        
        # Step 5: Calculate Delta Ct
        df["FAM Ct"] = pd.to_numeric(df.get("FAM Ct"), errors="coerce")
        df["HEX Ct"] = pd.to_numeric(df.get("HEX Ct"), errors="coerce")
        df["Δ Ct"] = df["FAM Ct"] - df["HEX Ct"]
        
        # Step 6: Generate well numbers
        df["Kuyu No"] = CSVProcessor.generate_kuyu_no(len(df))
        
        # Step 7: Apply quality warnings
        df = CSVProcessor.apply_conditions(df)
        
        logger.debug(f"Preprocessing complete: {len(df)} wells processed")
        return df
    
    @staticmethod
    def generate_kuyu_no(num_rows: int) -> list[str]:
        """
        Generate well IDs in column-major order.
        
        Args:
            num_rows: Number of well IDs to generate
            
        Returns:
            List of well IDs (A01, B01, ..., H12)
        """
        kuyu_no_list: list[str] = []
        letters = string.ascii_uppercase[:NUM_ROWS]  # A-H
        
        for letter in letters:
            for number in range(1, NUM_COLS + 1):  # 1-12
                kuyu_no_list.append(f"{letter}{number:02}")
                if len(kuyu_no_list) >= num_rows:
                    return kuyu_no_list
        
        return kuyu_no_list[:num_rows]
    
    @staticmethod
    def fill_missing_react_ids(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure all React IDs 1-96 are present.
        
        Adds empty rows for missing React IDs to ensure
        96-well plate is complete.
        
        Args:
            df: DataFrame with partial React IDs
            
        Returns:
            DataFrame with all 96 React IDs
            
        Raises:
            ValueError: If React ID column missing
        """
        if "React ID" not in df.columns:
            raise ValueError("'React ID' column not found")
        
        # Convert to numeric
        df["React ID"] = pd.to_numeric(df["React ID"], errors="coerce")
        
        # Find existing IDs
        current_ids = set(df["React ID"].dropna().astype(int).tolist())
        
        # Find missing IDs
        missing_ids = set(range(1, TOTAL_WELLS + 1)) - current_ids
        
        if missing_ids:
            logger.debug(f"Filling {len(missing_ids)} missing React IDs")
            
            empty_rows = []
            for mid in sorted(missing_ids):
                row = {col: "" for col in df.columns}
                row["React ID"] = int(mid)
                empty_rows.append(row)
            
            df = pd.concat([df, pd.DataFrame(empty_rows)], ignore_index=True)
        
        # Sort by React ID
        return df.sort_values("React ID", kind="mergesort").reset_index(drop=True)
    
    @staticmethod
    def apply_conditions(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply quality warnings based on thresholds.
        
        Warning Types:
        - "Boş Kuyu": No barcode (empty well)
        - "Yetersiz DNA": Ct > 30 or missing
        - "Düşük RFU Değeri": RFU < 1200
        
        Args:
            df: DataFrame to check
            
        Returns:
            DataFrame with warning column
            
        Note:
            Thresholds are calibrated - do not change without validation.
        """
        df["Uyarı"] = None
        
        # Warning 1: Empty well (no barcode)
        if "Barkot No" in df.columns:
            df.loc[
                (df["Barkot No"].isna() | (df["Barkot No"] == "")) & (df["Uyarı"].isnull()),
                "Uyarı"
            ] = "Boş Kuyu"
        
        # Warning 2: Insufficient DNA (Ct > threshold)
        df.loc[
            (
                (df["FAM Ct"] > CT_THRESHOLD)
                | (df["HEX Ct"] > CT_THRESHOLD)
                | (df["FAM Ct"].isna())
                | (df["HEX Ct"].isna())
            )
            & (df["Uyarı"].isnull()),
            "Uyarı",
        ] = "Yetersiz DNA"
        
        # Warning 3: Low RFU value
        df.loc[
            ((df["fam_end_rfu"] < RFU_THRESHOLD) | (df["hex_end_rfu"] < RFU_THRESHOLD))
            & (df["Uyarı"].isnull()),
            "Uyarı",
        ] = "Düşük RFU Değeri"
        
        # Reorder columns for consistency
        column_order = [
            "React ID", "Barkot No", "Hasta Adı", "Uyarı", "Kuyu No",
            "FAM Ct", "HEX Ct", "Δ Ct", "rfu_diff", "fam_end_rfu", "hex_end_rfu",
            "FAM koordinat list", "HEX koordinat list",
        ]
        
        return df[[c for c in column_order if c in df.columns]]


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "CSVProcessor",
]