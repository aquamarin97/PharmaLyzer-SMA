# app\services\pipeline.py
# app/services/pipeline.py
"""
Sequential data transformation pipeline.

Executes analysis steps sequentially, passing DataFrame between steps.
Supports progress reporting and cancellation.

Usage:
    from app.services.pipeline import Pipeline, Step
    
    steps = [
        Step("Preprocessing", preprocess_fn),
        Step("Analysis", analyze_fn),
        Step("Postprocessing", postprocess_fn),
    ]
    
    result = Pipeline.run(
        steps,
        progress_cb=lambda p, m: print(f"{p}%: {m}"),
        is_cancelled=lambda: user_cancelled
    )

Features:
    - Sequential step execution
    - Progress reporting
    - Cancellation support
    - DataStore integration
    - Copy-on-write option
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.services.data_store import DataStore

logger = logging.getLogger(__name__)


# ============================================================================
# TYPE ALIASES
# ============================================================================

Transform = Callable[[pd.DataFrame], pd.DataFrame]
"""Step transformation function: DataFrame → DataFrame"""

ProgressCb = Callable[[int, str], None]
"""Progress callback: (percent, message) → None"""

IsCancelled = Callable[[], bool]
"""Cancellation check: () → bool (True if cancelled)"""


# ============================================================================
# EXCEPTIONS
# ============================================================================

class CancelledError(RuntimeError):
    """Raised when pipeline is cancelled by user."""
    pass


# ============================================================================
# PIPELINE STEP
# ============================================================================

@dataclass(frozen=True)
class Step:
    """
    Single pipeline step.
    
    Attributes:
        name: Human-readable step name (for progress reporting)
        fn: Transformation function (DataFrame → DataFrame)
    
    Example:
        >>> def preprocess(df: pd.DataFrame) -> pd.DataFrame:
        ...     return df.dropna()
        >>> 
        >>> step = Step("Preprocessing", preprocess)
    """
    
    name: str
    """Step name for progress reporting"""
    
    fn: Transform
    """Transformation function"""


# ============================================================================
# PIPELINE
# ============================================================================

class Pipeline:
    """
    Sequential DataFrame transformation pipeline.
    
    Executes steps in order, managing DataStore reads/writes and
    providing progress reporting with cancellation support.
    
    Features:
        - DataStore integration
        - Progress callbacks
        - Cancellation support
        - Optional copy-on-write
    
    Thread Safety:
        Not thread-safe. DataStore is thread-safe but pipeline
        execution should be single-threaded.
    
    Example:
        >>> steps = [
        ...     Step("Load", load_data),
        ...     Step("Clean", clean_data),
        ...     Step("Analyze", analyze_data),
        ... ]
        >>> 
        >>> result = Pipeline.run(
        ...     steps,
        ...     progress_cb=update_ui,
        ...     is_cancelled=check_cancel
        ... )
    """
    
    @staticmethod
    def apply(step: Step, copy_input: bool = False) -> pd.DataFrame:
        """
        Apply single step to DataStore data.
        
        Args:
            step: Step to execute
            copy_input: If True, pass copy to step (safer but slower)
        
        Returns:
            Transformed DataFrame
        
        Side Effects:
            Updates DataStore with result
        
        Example:
            >>> step = Step("Clean", lambda df: df.dropna())
            >>> result = Pipeline.apply(step)
        """
        # Get data from DataStore
        df = DataStore.get_df_copy() if copy_input else DataStore.get_df()
        
        if df is None:
            raise ValueError("DataStore is empty. Cannot apply pipeline step.")
        
        logger.debug(f"Executing step: {step.name}")
        
        # Execute transformation
        result_df = step.fn(df)
        
        # Store result
        DataStore.set_df(result_df)
        
        logger.debug(f"Step completed: {step.name} (output shape: {result_df.shape})")
        
        return result_df
    
    @staticmethod
    def run(
        steps: Iterable[Step],
        *,
        progress_cb: ProgressCb | None = None,
        is_cancelled: IsCancelled | None = None,
        copy_input_each_step: bool = False,
    ) -> pd.DataFrame:
        """
        Execute all pipeline steps sequentially.
        
        Args:
            steps: Steps to execute in order
            progress_cb: Progress callback (percent, message)
            is_cancelled: Cancellation check callback
            copy_input_each_step: If True, pass copy to each step
        
        Returns:
            Final transformed DataFrame
        
        Raises:
            ValueError: If steps is empty
            CancelledError: If pipeline is cancelled
        
        Progress Reporting:
            - 0%: Pipeline started
            - (i/n)*100%: Step i of n completed
            - 100%: Pipeline completed
        
        Cancellation:
            Checked before each step. If is_cancelled() returns True,
            raises CancelledError immediately.
        
        Example:
            >>> def progress(percent: int, msg: str):
            ...     print(f"{percent}%: {msg}")
            >>> 
            >>> result = Pipeline.run(
            ...     steps,
            ...     progress_cb=progress,
            ...     is_cancelled=lambda: should_cancel
            ... )
        """
        steps_list = list(steps)
        
        if not steps_list:
            raise ValueError("Pipeline has no steps")
        
        total = len(steps_list)
        logger.info(f"Starting pipeline with {total} steps")
        
        def report(i: int, msg: str) -> None:
            """Report progress (clamped to 0-100%)."""
            if progress_cb:
                # Clamp percentage to valid range
                percent = int((max(0, min(i, total)) / total) * 100)
                try:
                    progress_cb(percent, msg)
                except Exception as e:
                    # Don't crash pipeline if callback fails
                    logger.warning(f"Progress callback failed: {e}")
        
        last_df: pd.DataFrame | None = None
        
        # Execute steps
        for idx, step in enumerate(steps_list):
            # Check cancellation
            if is_cancelled and is_cancelled():
                report(idx, "Cancelled")
                logger.info("Pipeline cancelled by user")
                raise CancelledError("Pipeline cancelled by user")
            
            # Report step start
            report(idx, f"Starting: {step.name}")
            
            # Execute step
            try:
                last_df = Pipeline.apply(step, copy_input=copy_input_each_step)
            except Exception as e:
                logger.error(f"Step failed: {step.name} - {e}", exc_info=True)
                raise
            
            # Report step completion
            report(idx + 1, f"Completed: {step.name}")
        
        # Report pipeline completion
        report(total, "Pipeline completed")
        logger.info("Pipeline completed successfully")
        
        return last_df


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "Pipeline",
    "Step",
    "CancelledError",
    "Transform",
    "ProgressCb",
    "IsCancelled",
]