# app\services\colored_box_service.py
# -*- coding: utf-8 -*-
"""Colored box validation service for PCR control wells.

This module provides validation logic for PCR control wells (homozygote, heterozygote, and NTC).
It checks whether specific control wells meet expected criteria based on their ratio values
and warning statuses, typically used for visual indicators in the UI.

The service validates three types of control wells:
- **Homozygote** (F12): Should have ratio >= carrier threshold
- **Heterozygote** (G12): Should have ratio < carrier threshold  
- **NTC (No Template Control)** (H12): Should show "Yetersiz DNA" warning

Example:
    Basic usage for validating control wells::

        import pandas as pd
        from app.services.colored_box_service import ColoredBoxService, ColoredBoxConfig

        # Prepare DataFrame with analysis results
        df = pd.DataFrame({
            'Kuyu No': ['F12', 'G12', 'H12'],
            'İstatistik Oranı': [0.85, 0.45, 0.0],
            'Standart Oranı': [0.82, 0.48, 0.0],
            'Uyarı': ['', '', 'Yetersiz DNA']
        })

        # Configure control wells and threshold
        config = ColoredBoxConfig(
            homozigot_well='F12',
            heterozigot_well='G12',
            ntc_well='H12',
            use_statistic_column=True,
            carrier_threshold=0.5999
        )

        # Validate control wells
        service = ColoredBoxService()
        results = service.compute(df, config)
        # results = [True, True, True] if all controls are valid

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import pandas as pd

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Column names used in PCR analysis DataFrame
COLUMN_STATISTIC_RATIO = "İstatistik Oranı"
COLUMN_STANDARD_RATIO = "Standart Oranı"
COLUMN_WELL_NUMBER = "Kuyu No"
COLUMN_WARNING = "Uyarı"

# Default well positions for control samples in 96-well plate
DEFAULT_HOMOZYGOTE_WELL = "F12"
DEFAULT_HETEROZYGOTE_WELL = "G12"
DEFAULT_NTC_WELL = "H12"

# Default carrier threshold for classification
# Values >= threshold are considered homozygote
# Values < threshold are considered heterozygote/carrier
DEFAULT_CARRIER_THRESHOLD = 0.5999

# Expected warning message for NTC wells
NTC_EXPECTED_WARNING = "Yetersiz DNA"


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ColoredBoxConfig:
    """Configuration for colored box validation service.
    
    This configuration defines which wells to check and what thresholds to apply
    for validating PCR control samples.
    
    Attributes:
        homozigot_well: Well position for homozygote control (default: F12)
        heterozigot_well: Well position for heterozygote control (default: G12)
        ntc_well: Well position for NTC control (default: H12)
        use_statistic_column: If True, use 'İstatistik Oranı', else 'Standart Oranı'
        carrier_threshold: Threshold value for carrier classification (default: 0.5999)
            Values >= threshold indicate homozygote
            Values < threshold indicate heterozygote/carrier
    
    Note:
        The carrier_threshold value can be dynamically set from the analysis model
        or other configuration sources if needed.
    """
    homozigot_well: str = DEFAULT_HOMOZYGOTE_WELL
    heterozigot_well: str = DEFAULT_HETEROZYGOTE_WELL
    ntc_well: str = DEFAULT_NTC_WELL
    use_statistic_column: bool = True
    carrier_threshold: float = DEFAULT_CARRIER_THRESHOLD


# ============================================================================
# Service
# ============================================================================

class ColoredBoxService:
    """Service for validating PCR control wells.
    
    This service checks whether control wells (homozygote, heterozygote, NTC) meet
    expected validation criteria based on their ratio values and warning statuses.
    
    The validation logic:
    - Homozygote well: ratio >= carrier_threshold
    - Heterozygote well: ratio < carrier_threshold
    - NTC well: warning equals "Yetersiz DNA"
    
    Returns boolean flags indicating whether each control well passes validation.
    """

    def compute(
        self,
        df: pd.DataFrame | None,
        cfg: ColoredBoxConfig
    ) -> List[bool]:
        """Compute validation status for all control wells.
        
        Validates homozygote, heterozygote, and NTC control wells against expected
        criteria. Returns a list of boolean flags indicating pass/fail for each control.
        
        Args:
            df: PCR analysis DataFrame containing well data and ratios.
                Must include columns: 'Kuyu No', 'Uyarı', and either
                'İstatistik Oranı' or 'Standart Oranı'.
                Can be None or empty for safe fallback.
            cfg: Configuration specifying which wells to check and thresholds.
        
        Returns:
            List of three boolean values [homozygote_ok, heterozygote_ok, ntc_ok]:
            - homozygote_ok: True if homozygote well ratio >= threshold
            - heterozygote_ok: True if heterozygote well ratio < threshold
            - ntc_ok: True if NTC well shows "Yetersiz DNA" warning
            Returns [False, False, False] if DataFrame is invalid or missing required columns.
        
        Example:
            >>> config = ColoredBoxConfig()
            >>> service = ColoredBoxService()
            >>> results = service.compute(df, config)
            >>> if all(results):
            ...     print("All control wells passed validation")
        """
        # Handle invalid DataFrame
        if df is None or df.empty:
            logger.warning("Empty or None DataFrame provided, returning all False")
            return [False, False, False]

        # Determine which ratio column to use
        ratio_column = COLUMN_STATISTIC_RATIO if cfg.use_statistic_column else COLUMN_STANDARD_RATIO
        
        # Check for required columns
        required_columns = {COLUMN_WELL_NUMBER, COLUMN_WARNING, ratio_column}
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(
                f"Missing required columns: {missing_columns}. "
                f"Available columns: {list(df.columns)}"
            )
            return [False, False, False]

        logger.info(
            f"Validating control wells - Homozygote: {cfg.homozigot_well}, "
            f"Heterozygote: {cfg.heterozigot_well}, NTC: {cfg.ntc_well}, "
            f"Using column: {ratio_column}, Threshold: {cfg.carrier_threshold}"
        )

        # Validate each control well
        homozygote_ok = self._check_homozigot(
            df, ratio_column, cfg.homozigot_well, cfg.carrier_threshold
        )
        heterozygote_ok = self._check_heterozigot(
            df, ratio_column, cfg.heterozigot_well, cfg.carrier_threshold
        )
        ntc_ok = self._check_ntc(df, cfg.ntc_well)

        logger.debug(
            f"Validation results - Homozygote: {homozygote_ok}, "
            f"Heterozygote: {heterozygote_ok}, NTC: {ntc_ok}"
        )

        return [homozygote_ok, heterozygote_ok, ntc_ok]

    def _check_homozigot(
        self,
        df: pd.DataFrame,
        ratio_column: str,
        well: str,
        threshold: float
    ) -> bool:
        """Check if homozygote control well passes validation.
        
        Validates that the homozygote control well has a ratio value greater than
        or equal to the carrier threshold, indicating proper homozygote classification.
        
        Args:
            df: PCR analysis DataFrame
            ratio_column: Name of ratio column to check ('İstatistik Oranı' or 'Standart Oranı')
            well: Well position to check (e.g., 'F12')
            threshold: Carrier threshold value (ratio must be >= this value)
        
        Returns:
            True if well exists and ratio >= threshold, False otherwise
        """
        row = df[df[COLUMN_WELL_NUMBER] == well]
        
        if row.empty:
            logger.warning(f"Homozygote well '{well}' not found in DataFrame")
            return False
        
        try:
            ratio_value = float(row[ratio_column].iloc[0])
            is_valid = ratio_value >= threshold
            
            logger.debug(
                f"Homozygote well '{well}': ratio={ratio_value:.4f}, "
                f"threshold={threshold:.4f}, valid={is_valid}"
            )
            
            return is_valid
            
        except (TypeError, ValueError) as e:
            logger.error(
                f"Invalid ratio value for homozygote well '{well}': {e}"
            )
            return False

    def _check_heterozigot(
        self,
        df: pd.DataFrame,
        ratio_column: str,
        well: str,
        threshold: float
    ) -> bool:
        """Check if heterozygote control well passes validation.
        
        Validates that the heterozygote control well has a ratio value less than
        the carrier threshold, indicating proper heterozygote/carrier classification.
        
        Args:
            df: PCR analysis DataFrame
            ratio_column: Name of ratio column to check ('İstatistik Oranı' or 'Standart Oranı')
            well: Well position to check (e.g., 'G12')
            threshold: Carrier threshold value (ratio must be < this value)
        
        Returns:
            True if well exists and ratio < threshold, False otherwise
        """
        row = df[df[COLUMN_WELL_NUMBER] == well]
        
        if row.empty:
            logger.warning(f"Heterozygote well '{well}' not found in DataFrame")
            return False
        
        try:
            ratio_value = float(row[ratio_column].iloc[0])
            is_valid = ratio_value < threshold
            
            logger.debug(
                f"Heterozygote well '{well}': ratio={ratio_value:.4f}, "
                f"threshold={threshold:.4f}, valid={is_valid}"
            )
            
            return is_valid
            
        except (TypeError, ValueError) as e:
            logger.error(
                f"Invalid ratio value for heterozygote well '{well}': {e}"
            )
            return False

    def _check_ntc(self, df: pd.DataFrame, well: str) -> bool:
        """Check if NTC (No Template Control) well passes validation.
        
        Validates that the NTC control well shows the expected "Yetersiz DNA" warning,
        indicating proper NTC behavior (no DNA amplification).
        
        Args:
            df: PCR analysis DataFrame
            well: Well position to check (e.g., 'H12')
        
        Returns:
            True if well exists and warning equals "Yetersiz DNA", False otherwise
        """
        row = df[df[COLUMN_WELL_NUMBER] == well]
        
        if row.empty:
            logger.warning(f"NTC well '{well}' not found in DataFrame")
            return False
        
        warning_value = row[COLUMN_WARNING].iloc[0]
        is_valid = warning_value == NTC_EXPECTED_WARNING
        
        logger.debug(
            f"NTC well '{well}': warning='{warning_value}', "
            f"expected='{NTC_EXPECTED_WARNING}', valid={is_valid}"
        )
        
        return is_valid