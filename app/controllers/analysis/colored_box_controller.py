# app\controllers\analysis\colored_box_controller.py
# -*- coding: utf-8 -*-
"""Colored box controller for PCR control well validation indicators.

This module provides a controller that manages colored box validation indicators
for PCR control wells. It coordinates:
- Configuration updates from UI inputs (well positions, thresholds)
- Validation computation via ColoredBoxService
- Result signal emission to update UI indicators

The controller acts as a bridge between UI configuration inputs and the
validation service, emitting signals when validation results are ready.

Control Wells Validated:
- Homozygote control (typically F12): Should have high ratio
- Heterozygote control (typically G12): Should have low ratio
- NTC control (typically H12): Should show "Yetersiz DNA" warning

Example:
    Basic usage in main model::

        from app.controllers.analysis.colored_box_controller import ColoredBoxController

        # Create controller
        controller = ColoredBoxController()

        # Connect to UI updates
        controller.calculationCompleted.connect(update_ui_indicators)

        # Configure from UI
        controller.set_homozigot_line_edit("F12")
        controller.set_heterozigot_line_edit("G12")
        controller.set_NTC_line_edit("H12")
        controller.set_carrier_threshold(0.5999)

        # After analysis completes
        controller.define_box_color()
        # Signal emitted: calculationCompleted([True, True, True])

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QObject, pyqtSignal

from app.services.colored_box_service import ColoredBoxConfig, ColoredBoxService
from app.services.data_store import DataStore

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Default validation result (all controls invalid)
DEFAULT_VALIDATION_RESULT = [False, False, False]


# ============================================================================
# Controller
# ============================================================================

class ColoredBoxController(QObject):
    """Controller managing colored box validation indicators for control wells.
    
    This controller coordinates validation of PCR control wells by:
    - Maintaining configuration state (well positions, thresholds)
    - Providing UI setter methods for configuration updates
    - Running validation computation via ColoredBoxService
    - Emitting signals with validation results
    
    The controller follows the Model-View-Controller pattern where:
    - Model: ColoredBoxConfig (configuration state)
    - View: UI indicator widgets (colored boxes)
    - Controller: This class (coordination)
    - Service: ColoredBoxService (validation logic)
    
    Validation Flow:
        1. UI updates configuration via setters
        2. define_box_color() called after analysis
        3. Service validates control wells from DataStore
        4. Results cached in last_result
        5. calculationCompleted signal emitted
        6. UI updates colored box indicators
    
    Signals:
        calculationCompleted(list): Emitted when validation completes
            List contains [homozygote_ok, heterozygote_ok, ntc_ok]
            Each boolean indicates whether control well passed validation
    
    Attributes:
        service: ColoredBoxService instance performing validation
        cfg: ColoredBoxConfig with current validation settings
        last_result: Most recent validation result (cached)
    
    Example:
        >>> controller = ColoredBoxController()
        >>> controller.set_homozigot_line_edit("F12")
        >>> controller.set_carrier_threshold(0.5999)
        >>> controller.define_box_color()
        >>> # calculationCompleted emitted with [True/False, True/False, True/False]
    """

    # Signal emitted when validation completes
    # Argument: list of 3 booleans [homozygote_ok, heterozygote_ok, ntc_ok]
    calculationCompleted = pyqtSignal(list)

    def __init__(self, service: ColoredBoxService | None = None, parent=None):
        """Initialize colored box controller.
        
        Args:
            service: Optional ColoredBoxService instance. If None, creates default instance.
            parent: Optional parent QObject for Qt object hierarchy
        
        Note:
            - Creates default ColoredBoxConfig with standard settings
            - Initializes last_result to all-False (no controls valid)
        """
        super().__init__(parent)
        
        self.service = service or ColoredBoxService()
        self.cfg = ColoredBoxConfig()
        self.last_result = DEFAULT_VALIDATION_RESULT.copy()
        
        logger.debug("ColoredBoxController initialized with default configuration")

    # ========================================================================
    # Configuration Setters (UI Interface)
    # ========================================================================

    def set_check_box_status(self, status: bool):
        """Set column selection for ratio calculation.
        
        Determines which ratio column to use for validation:
        - True: Use "İstatistik Oranı" (statistical ratio)
        - False: Use "Standart Oranı" (standard ratio)
        
        Args:
            status: True for statistical ratio, False for standard ratio
        
        Note:
            This typically reflects a checkbox in the UI that lets users
            choose between statistical and standard calculation methods.
        """
        self.cfg.use_statistic_column = bool(status)
        logger.debug(f"Checkbox status set: use_statistic_column={self.cfg.use_statistic_column}")

    def set_homozigot_line_edit(self, value: str):
        """Set homozygote control well position.
        
        Updates the well position to check for homozygote control validation.
        
        Args:
            value: Well position (e.g., "F12", "A01")
        
        Example:
            >>> controller.set_homozigot_line_edit("F12")
        """
        self.cfg.homozigot_well = value
        logger.debug(f"Homozygote well position set: {value}")

    def set_heterozigot_line_edit(self, value: str):
        """Set heterozygote control well position.
        
        Updates the well position to check for heterozygote control validation.
        
        Args:
            value: Well position (e.g., "G12", "B01")
        
        Example:
            >>> controller.set_heterozigot_line_edit("G12")
        """
        self.cfg.heterozigot_well = value
        logger.debug(f"Heterozygote well position set: {value}")

    def set_NTC_line_edit(self, value: str):
        """Set NTC (No Template Control) well position.
        
        Updates the well position to check for NTC control validation.
        
        Args:
            value: Well position (e.g., "H12", "C01")
        
        Example:
            >>> controller.set_NTC_line_edit("H12")
        """
        self.cfg.ntc_well = value
        logger.debug(f"NTC well position set: {value}")

    def set_carrier_threshold(self, value: float):
        """Set carrier classification threshold.
        
        Updates the threshold value used to distinguish between
        homozygote and heterozygote/carrier samples.
        
        Args:
            value: Threshold value (typically 0.5999)
                - Ratios >= threshold → homozygote
                - Ratios < threshold → heterozygote/carrier
        
        Example:
            >>> controller.set_carrier_threshold(0.5999)
        """
        self.cfg.carrier_threshold = float(value)
        logger.debug(f"Carrier threshold set: {self.cfg.carrier_threshold}")

    # ========================================================================
    # Validation Execution
    # ========================================================================

    def define_box_color(self):
        """Execute control well validation and emit results.
        
        Main validation method that:
        1. Retrieves analysis results from DataStore
        2. Runs validation via ColoredBoxService
        3. Caches results in last_result
        4. Emits calculationCompleted signal with results
        
        The method uses current configuration (cfg) which should be
        set via setter methods before calling this.
        
        Validation Logic:
        - Homozygote: ratio >= carrier_threshold
        - Heterozygote: ratio < carrier_threshold
        - NTC: warning == "Yetersiz DNA"
        
        Results:
            List of 3 booleans: [homozygote_ok, heterozygote_ok, ntc_ok]
            Each True indicates control well passed validation
        
        Signal Emitted:
            calculationCompleted(list): Results list
        
        Example:
            >>> controller.define_box_color()
            >>> # If all controls valid, emits: [True, True, True]
            >>> # If homozygote failed, emits: [False, True, True]
        
        Note:
            - Safe to call even if DataStore is empty (service handles this)
            - Results are cached for later retrieval via last_result
            - This should be called after analysis completes
        """
        logger.info("Starting colored box validation")
        
        # Retrieve analysis results from DataStore
        df = DataStore.get_df_copy()
        
        if df is None or df.empty:
            logger.warning("DataStore is empty, validation will return all False")
        else:
            logger.debug(f"Retrieved DataFrame from DataStore - Shape: {df.shape}")
        
        # Log current configuration
        logger.debug(
            f"Validation configuration - "
            f"Homozygote: {self.cfg.homozigot_well}, "
            f"Heterozygote: {self.cfg.heterozigot_well}, "
            f"NTC: {self.cfg.ntc_well}, "
            f"Threshold: {self.cfg.carrier_threshold}, "
            f"Use statistic column: {self.cfg.use_statistic_column}"
        )
        
        # Execute validation
        try:
            self.last_result = self.service.compute(df, self.cfg)
            logger.info(f"Validation complete - Results: {self.last_result}")
        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            self.last_result = DEFAULT_VALIDATION_RESULT.copy()
        
        # Emit results to UI
        self.calculationCompleted.emit(self.last_result)
        logger.debug("calculationCompleted signal emitted")