# app\services\analysis_steps\calculate_with_referance.py
# app/services/analysis_steps/calculate_with_referance.py
"""
Reference well-based calculation step.

Calculates ΔΔCt and patient classification using a reference well.
Classification based on calibrated carrier/uncertain range thresholds.

Note: Filename preserves original typo "referance" for backward compatibility.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class CalculateWithReferance:
    """
    Reference-based patient classification.
    
    Algorithm:
    1. Validate reference well exists
    2. Get reference ΔCt value
    3. Calculate ΔΔCt = ΔCt - reference_ΔCt
    4. Calculate ratio = 2^(-ΔΔCt)
    5. Classify based on ratio thresholds
    """
    
    def __init__(
        self,
        referance_well: str,
        carrier_range: float,
        uncertain_range: float
    ):
        self.df: pd.DataFrame | None = None
        self.referance_well = str(referance_well)
        self.carrier_range = float(carrier_range)
        self.uncertain_range = float(uncertain_range)
        self.last_success = True
        self.initial_static_value: float | None = None
    
    def process(self, df: pd.DataFrame | None = None) -> pd.DataFrame:
        """Process DataFrame with reference well calculation."""
        if df is None:
            raise ValueError("DataFrame cannot be None. Called by pipeline.")
        
        if df.empty:
            raise ValueError("No data to process.")
        
        self.df = df
        self.last_success = self._set_reference_value()
        
        # Split valid/invalid data
        valid_mask = (self.df["Uyarı"].isnull()) | (self.df["Uyarı"] == "Düşük RFU Değeri")
        valid_data = self.df[valid_mask].copy()
        invalid_data = self.df[~valid_mask].copy()
        
        # Process valid data
        valid_data = self._finalize_data(valid_data)
        
        # Merge back
        return pd.concat([valid_data, invalid_data], ignore_index=True)
    
    def _set_reference_value(self) -> bool:
        """Validate and extract reference well ΔCt value."""
        if not self.referance_well or pd.isna(self.referance_well):
            raise ValueError("Reference well is empty.")
        
        if self.df is None:
            raise ValueError("DataFrame is None.")
        
        if "Kuyu No" not in self.df.columns or "Δ Ct" not in self.df.columns:
            raise ValueError("Missing 'Kuyu No' or 'Δ Ct' column.")
        
        if self.referance_well not in set(self.df["Kuyu No"].astype(str).values):
            raise ValueError(f"Reference well '{self.referance_well}' not found.")
        
        vals = self.df.loc[self.df["Kuyu No"] == self.referance_well, "Δ Ct"].values
        
        if len(vals) == 0:
            raise ValueError(f"No Δ Ct value for reference well '{self.referance_well}'.")
        
        self.initial_static_value = vals[0]
        
        if pd.isna(self.initial_static_value):
            logger.warning("Reference well has NA ΔCt value")
            return False
        
        logger.info(f"Reference well {self.referance_well}: ΔCt = {self.initial_static_value:.3f}")
        return True
    
    def _finalize_data(self, valid_data: pd.DataFrame) -> pd.DataFrame:
        """Calculate ΔΔCt and classify patients."""
        if self.initial_static_value is None or pd.isna(self.initial_static_value):
            logger.warning("Reference value unavailable, skipping calculations")
            return valid_data
        
        # Calculate ΔΔCt
        valid_data["Δ_Δ Ct"] = valid_data["Δ Ct"] - self.initial_static_value
        
        # Calculate ratio = 2^(-ΔΔCt)
        valid_data["Standart Oranı"] = 2 ** -valid_data["Δ_Δ Ct"]
        
        # Calibrated adjustment (DO NOT CHANGE)
        valid_data.loc[valid_data["Standart Oranı"] <= 0.7, "Standart Oranı"] -= 0.00
        
        # Classify patients
        carrier_range = self.carrier_range
        uncertain_range = self.uncertain_range
        
        def classify(x: float) -> str:
            if x > uncertain_range:
                return "Sağlıklı"
            elif carrier_range < x <= uncertain_range:
                return "Belirsiz"
            elif 0.1 < x <= carrier_range:
                return "Taşıyıcı"
            else:
                return "Tekrar"
        
        valid_data["Referans Hasta Sonucu"] = valid_data["Standart Oranı"].apply(classify)
        
        return valid_data


__all__ = ["CalculateWithReferance"]