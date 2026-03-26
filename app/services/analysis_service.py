# app\services\analysis_service.py
# app/services/analysis_service.py
"""
PCR analysis pipeline orchestration service.

This module provides a high-level service for managing the complete PCR
analysis workflow. Coordinates pipeline execution with progress reporting
and cancellation support.

Workflow:
    1. CSV preprocessing (coordinate parsing, basic calculations)
    2. Reference-based calculation (standard ratio)
    3. Regression analysis (safe zone detection)
    4. Reference-free calculation (statistical ratio)
    5. Result CSV formatting

Usage:
    from app.services.analysis_service import AnalysisService, AnalysisConfig
    
    config = AnalysisConfig(referance_well="F12", checkbox_status=True)
    service = AnalysisService(config)
    
    success = service.run(
        progress_cb=lambda p, m: print(f"{p}%: {m}"),
        is_cancelled=lambda: user_cancelled
    )
    
    if success:
        result_df = service.last_df
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Final

import pandas as pd

from app.services.analysis_steps.calculate_regression import CalculateRegression
from app.services.analysis_steps.calculate_with_referance import CalculateWithReferance
from app.services.analysis_steps.calculate_without_reference import (
    CalculateWithoutReference
)
from app.services.analysis_steps.configurate_result_csv import ConfigurateResultCSV
from app.services.analysis_steps.csv_processor import CSVProcessor
from app.services.pipeline import CancelledError, Pipeline, Step

logger = logging.getLogger(__name__)


# ============================================================================
# TYPE ALIASES
# ============================================================================

ProgressCallback = Callable[[int, str], None]
"""Progress callback: (percentage, message) → None"""

CancellationCheck = Callable[[], bool]
"""Cancellation check: () → bool (True if cancelled)"""


# ============================================================================
# ANALYSIS CONFIGURATION
# ============================================================================

@dataclass
class AnalysisConfig:
    """
    PCR analysis pipeline configuration.
    
    Attributes:
        referance_well: Reference well ID (e.g., "F12")
                       Used for standard ratio calculation
        checkbox_status: True for statistical ratio, False for standard ratio
        carrier_range: Carrier upper threshold
                      Values ≤ this are classified as "Carrier"
        uncertain_range: Uncertain lower threshold
                        Values between carrier_range and this are "Uncertain"
    
    Raises:
        ValueError: If carrier_range >= uncertain_range or negative values
    
    Note:
        Expected ordering: 0 < carrier_range < uncertain_range < ∞
        
    Example:
        >>> config = AnalysisConfig(
        ...     referance_well="F12",
        ...     carrier_range=0.60,
        ...     uncertain_range=0.62
        ... )
    """
    
    referance_well: str = "F12"
    """Reference well ID"""
    
    checkbox_status: bool = True
    """Use statistical ratio (True) or standard ratio (False)"""
    
    carrier_range: float = 0.5999
    """Carrier classification upper threshold"""
    
    uncertain_range: float = 0.6199
    """Uncertain classification lower threshold"""
    
    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.carrier_range >= self.uncertain_range:
            raise ValueError(
                f"carrier_range ({self.carrier_range}) must be less than "
                f"uncertain_range ({self.uncertain_range})"
            )
        
        if self.carrier_range <= 0 or self.uncertain_range <= 0:
            raise ValueError(
                "carrier_range and uncertain_range must be positive values"
            )


# ============================================================================
# ANALYSIS SERVICE
# ============================================================================

class AnalysisService:
    """
    PCR analysis pipeline orchestration service.
    
    Coordinates the complete analysis workflow:
    1. CSV preprocessing
    2. Reference-based calculation
    3. Regression analysis
    4. Reference-free calculation
    5. Result formatting
    
    Thread Safety:
        Not thread-safe. Do not call from multiple threads.
    
    Attributes:
        config: Analysis configuration
        last_df: Result DataFrame from last successful analysis
        last_summary: Summary statistics (currently None, for future use)
    
    Example:
        >>> service = AnalysisService()
        >>> success = service.run(progress_cb=print_progress)
        >>> if success:
        ...     print(service.last_df.head())
    """
    
    def __init__(self, config: AnalysisConfig | None = None) -> None:
        """
        Create AnalysisService instance.
        
        Args:
            config: Analysis configuration. If None, uses default config.
        """
        self.config: AnalysisConfig = config or AnalysisConfig()
        self._cancelled: bool = False
        self.last_df: pd.DataFrame | None = None
        self.last_summary: object | None = None  # Type TBD in future
        
        logger.debug(f"AnalysisService initialized with config: {self.config}")
    
    # ========================================================================
    # CANCELLATION
    # ========================================================================
    
    def cancel(self) -> None:
        """
        Request cancellation of ongoing analysis.
        
        Note:
            This only sets the cancellation flag. Actual cancellation
            depends on run() method checking is_cancelled callback.
            Cancellation is cooperative, not immediate.
        """
        self._cancelled = True
        logger.info("Analysis cancellation requested")
    
    def _is_cancelled(self) -> bool:
        """Internal cancellation check."""
        return self._cancelled
    
    # ========================================================================
    # CONFIGURATION SETTERS
    # ========================================================================
    
    def set_referance_well(self, value: str) -> None:
        """
        Set reference well ID.
        
        Args:
            value: Well ID (e.g., "F12", "A01")
        """
        self.config.referance_well = str(value).strip().upper()
        logger.debug(f"Reference well set to: {self.config.referance_well}")
    
    def set_checkbox_status(self, value: bool) -> None:
        """
        Set statistical ratio usage.
        
        Args:
            value: True for statistical ratio, False for standard ratio
        """
        self.config.checkbox_status = bool(value)
        logger.debug(f"Checkbox status set to: {self.config.checkbox_status}")
    
    def set_carrier_range(self, value: float) -> None:
        """
        Set carrier classification upper threshold.
        
        Args:
            value: New carrier threshold
        
        Raises:
            ValueError: If value >= uncertain_range or negative
        """
        value = float(value)
        
        if value <= 0:
            raise ValueError(f"carrier_range must be positive, got {value}")
        
        if value >= self.config.uncertain_range:
            raise ValueError(
                f"carrier_range ({value}) must be less than "
                f"uncertain_range ({self.config.uncertain_range})"
            )
        
        self.config.carrier_range = value
        logger.debug(f"Carrier range set to: {value}")
    
    def set_uncertain_range(self, value: float) -> None:
        """
        Set uncertain classification lower threshold.
        
        Args:
            value: New uncertain threshold
        
        Raises:
            ValueError: If value <= carrier_range or negative
        """
        value = float(value)
        
        if value <= 0:
            raise ValueError(f"uncertain_range must be positive, got {value}")
        
        if value <= self.config.carrier_range:
            raise ValueError(
                f"uncertain_range ({value}) must be greater than "
                f"carrier_range ({self.config.carrier_range})"
            )
        
        self.config.uncertain_range = value
        logger.debug(f"Uncertain range set to: {value}")
    
    # ========================================================================
    # MAIN ANALYSIS PIPELINE
    # ========================================================================
    
    def run(
        self,
        progress_cb: ProgressCallback | None = None,
        is_cancelled: CancellationCheck | None = None,
    ) -> bool:
        """
        Execute complete PCR analysis pipeline.
        
        Runs all analysis steps sequentially and stores results.
        All steps work on DataStore data.
        
        Args:
            progress_cb: Progress callback (percent, message)
            is_cancelled: Cancellation check callback
        
        Returns:
            True: Analysis completed successfully
            False: Analysis cancelled or failed
        
        Side Effects:
            - Updates self.last_df
            - Updates DataStore
            - Resets self._cancelled
            - May set config.checkbox_status=True if reference fails
        
        Raises:
            None - Returns False instead of raising exceptions
        
        Example:
            >>> def progress(p: int, m: str):
            ...     print(f"{p}%: {m}")
            >>> 
            >>> service = AnalysisService()
            >>> success = service.run(progress_cb=progress)
        """
        # Reset state
        self._cancelled = False
        self.last_df = None
        
        logger.info("Starting analysis pipeline")
        
        # Default cancellation check
        is_cancelled_fn: CancellationCheck = is_cancelled or self._is_cancelled
        
        # Progress wrapper with error handling
        def progress(percent: int, message: str) -> None:
            """Safe progress reporting."""
            if progress_cb is not None:
                try:
                    progress_cb(int(percent), str(message))
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
        
        # ====================================================================
        # Build Pipeline Steps
        # ====================================================================
        
        ref_step = CalculateWithReferance(
            self.config.referance_well,
            self.config.carrier_range,
            self.config.uncertain_range,
        )
        
        reg_step = CalculateRegression()
        
        sw_step = CalculateWithoutReference(
            carrier_range=self.config.carrier_range,
            uncertain_range=self.config.uncertain_range,
        )
        
        post_step = ConfigurateResultCSV(self.config.checkbox_status)
        
        steps: list[Step] = [
            Step("CSV preprocessing", CSVProcessor.process),
            Step("Reference-based calculation", ref_step.process),
            Step("Regression analysis", reg_step.process),
            Step("Reference-free calculation", sw_step.process),
            Step("Result CSV formatting", post_step.process),
        ]
        
        logger.info(f"Pipeline configured with {len(steps)} steps")
        
        # ====================================================================
        # Execute Pipeline
        # ====================================================================
        
        try:
            output_df = Pipeline.run(
                steps,
                progress_cb=progress,
                is_cancelled=is_cancelled_fn,
                copy_input_each_step=False,
            )
            
            self.last_df = output_df
            logger.info(f"Analysis completed successfully: {output_df.shape}")
            
        except CancelledError:
            progress(0, "Analysis cancelled")
            logger.info("Analysis cancelled by user")
            return False
        
        except Exception as exc:
            progress(0, f"Analysis failed: {exc}")
            logger.error(f"Analysis failed: {exc}", exc_info=True)
            return False
        
        # ====================================================================
        # Post-processing
        # ====================================================================
        
        # If reference well failed, force statistical ratio usage
        if not getattr(ref_step, "last_success", True):
            self.config.checkbox_status = True
            logger.warning(
                "Reference well failed, forcing statistical ratio usage"
            )
            progress(100, "Reference well failed, using statistical ratio")
        
        return True


# ============================================================================
# MODULE-LEVEL CONSTANTS
# ============================================================================

DEFAULT_CONFIG: Final[AnalysisConfig] = AnalysisConfig()
"""Default analysis configuration"""

PIPELINE_STEP_COUNT: Final[int] = 5
"""Number of pipeline steps (for UI progress calculations)"""


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "AnalysisService",
    "AnalysisConfig",
    "DEFAULT_CONFIG",
    "PIPELINE_STEP_COUNT",
    "ProgressCallback",
    "CancellationCheck",
]