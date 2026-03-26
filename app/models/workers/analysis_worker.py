# app\models\workers\analysis_worker.py
# -*- coding: utf-8 -*-
"""Background worker for asynchronous PCR analysis execution.

This module provides a PyQt5-based worker class that executes PCR analysis
in a background thread, preventing UI freezing during long-running calculations.
It implements cooperative cancellation and progress reporting.

The worker follows the QThread worker pattern where:
- Worker is moved to a separate QThread
- Analysis runs in background without blocking UI
- Progress updates are emitted via signals
- Cancellation is cooperative (requires service support)

Example:
    Basic usage with QThread (typically done by MainModel)::

        from PyQt5.QtCore import QThread
        from app.models.workers.analysis_worker import AnalysisWorker
        from app.services.analysis_service import AnalysisService

        # Create worker and thread
        service = AnalysisService()
        worker = AnalysisWorker(service)
        thread = QThread()

        # Move worker to thread
        worker.moveToThread(thread)

        # Connect signals
        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)

        # Start execution
        thread.start()

        # Later: cancel if needed
        worker.cancel()

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
import traceback

import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from app.services.analysis_summary import AnalysisSummary
from app.services.summary_calc import build_summary_from_df

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Progress messages (Turkish)
PROGRESS_MSG_STARTING = "Analiz başlatılıyor..."
PROGRESS_MSG_COMPLETED = "Tamamlandı."

# Progress percentage bounds
PROGRESS_START = 1
PROGRESS_COMPLETE = 100

# Attribute names for accessing service internals
ATTR_LAST_DF = "last_df"
ATTR_CONFIG = "config"
ATTR_CHECKBOX_STATUS = "checkbox_status"
ATTR_CANCEL = "cancel"


# ============================================================================
# Worker
# ============================================================================

class AnalysisWorker(QObject):
    """Background worker for executing PCR analysis without blocking UI.
    
    This worker runs analysis in a separate thread and provides:
    - Progress reporting via signals
    - Cooperative cancellation support
    - Error handling with traceback reporting
    - Summary generation from analysis results
    
    The worker expects an analysis service that implements:
    - run(progress_cb, is_cancelled) -> bool: Main analysis method
    - cancel() [optional]: Explicit cancellation support
    - last_df: Final DataFrame after analysis
    - config.checkbox_status: Flag for reference-free mode
    
    Signals:
        finished(bool, object): Emitted when analysis completes
            - First arg: success flag (True/False)
            - Second arg: AnalysisSummary or None
        
        error(str): Emitted when exception occurs during analysis
            - Contains error message and full traceback
        
        progress(int, str): Emitted during analysis execution
            - First arg: progress percentage (0-100)
            - Second arg: status message in Turkish
    
    Thread Safety:
        - This class is designed to run in a QThread
        - Signals are thread-safe (Qt's signal/slot mechanism)
        - Internal state is protected by _running and _cancel_requested flags
    """

    # Signal definitions
    finished = pyqtSignal(bool, object)  # (success: bool, summary: AnalysisSummary | None)
    error = pyqtSignal(str)  # error_message_with_traceback: str
    progress = pyqtSignal(int, str)  # (percent: int, message: str)

    def __init__(self, analysis_service):
        """Initialize worker with analysis service.
        
        Args:
            analysis_service: Service instance that performs the actual analysis.
                Must implement run(progress_cb, is_cancelled) method.
                Optionally implements cancel() method for explicit cancellation.
        
        Note:
            The worker does not start automatically. Call run() slot after
            moving to QThread via thread.started.connect(worker.run).
        """
        super().__init__()
        self._service = analysis_service
        self._running = False
        self._cancel_requested = False
        logger.debug(f"AnalysisWorker initialized with service: {type(analysis_service).__name__}")

    @pyqtSlot()
    def cancel(self) -> None:
        """Request cooperative cancellation of running analysis.
        
        Sets internal cancellation flag and attempts to call service's cancel()
        method if available. The actual cancellation is cooperative - the analysis
        service must check is_cancelled() callback and exit gracefully.
        
        This method is thread-safe and can be called from UI thread while
        analysis runs in background thread.
        
        Note:
            - Cancellation is asynchronous and not immediate
            - Analysis service must support cooperative cancellation
            - If service doesn't implement cancel(), only flag is set
        
        Example:
            >>> worker = AnalysisWorker(service)
            >>> # ... start worker in thread ...
            >>> # User clicks cancel button
            >>> worker.cancel()  # Request cancellation
        """
        logger.info("Cancellation requested for analysis worker")
        self._cancel_requested = True

        # Try to call service's cancel method if it exists
        cancel_method = getattr(self._service, ATTR_CANCEL, None)
        if callable(cancel_method):
            try:
                logger.debug("Calling service cancel() method")
                cancel_method()
            except Exception as e:
                logger.warning(f"Service cancel() method raised exception: {e}")
                # Don't propagate - cancellation flag is already set
                return

    def _is_cancelled(self) -> bool:
        """Check if cancellation has been requested.
        
        This method is passed as callback to the analysis service's run()
        method, allowing the service to periodically check for cancellation
        and exit gracefully.
        
        Returns:
            True if cancel() has been called, False otherwise
        """
        return self._cancel_requested

    def _progress(self, percent: int, message: str) -> None:
        """Emit progress update if not cancelled.
        
        Internal callback passed to analysis service for progress reporting.
        Suppresses progress updates if cancellation has been requested to
        avoid confusing UI state.
        
        Args:
            percent: Progress percentage (0-100)
            message: Status message describing current operation
        """
        # Don't spam progress signals after cancellation
        if not self._cancel_requested:
            self.progress.emit(int(percent), str(message))

    @pyqtSlot()
    def run(self) -> None:
        """Execute analysis in background thread.
        
        This slot should be connected to QThread.started signal. It:
        1. Runs the analysis service with progress and cancellation callbacks
        2. Generates summary from analysis results if successful
        3. Emits finished signal with success status and summary
        4. Handles any exceptions and emits error signal with traceback
        
        The method is protected against re-entry - if already running, it returns
        immediately without doing anything.
        
        Flow:
            1. Check if already running (re-entry protection)
            2. Emit starting progress
            3. Call service.run(progress_cb, is_cancelled)
            4. Build summary from results if DataFrame available
            5. Emit completion progress
            6. Emit finished signal
            7. Handle exceptions -> emit error signal
            8. Always: reset running flag
        
        Signals Emitted:
            - progress: At start (1%) and completion (100%)
            - finished: Always, with (success, summary_or_none)
            - error: Only if exception occurs, with message and traceback
        
        Note:
            This method runs in the worker's thread, not the UI thread.
            All signal emissions are automatically queued to UI thread by Qt.
        """
        # Re-entry protection
        if self._running:
            logger.warning("AnalysisWorker.run() called while already running - ignoring")
            return

        self._running = True
        self._cancel_requested = False
        logger.info("Starting analysis worker execution")

        try:
            # Report analysis start
            self._progress(PROGRESS_START, PROGRESS_MSG_STARTING)

            # Execute main analysis with callbacks
            success = self._service.run(
                progress_cb=self._progress,
                is_cancelled=self._is_cancelled
            )

            logger.info(f"Analysis service completed - Success: {success}")

            # Extract results and configuration
            final_df = getattr(self._service, ATTR_LAST_DF, None)
            config = getattr(self._service, ATTR_CONFIG, None)
            use_without_reference = bool(getattr(config, ATTR_CHECKBOX_STATUS, False))

            logger.debug(
                f"Analysis results - DataFrame: {type(final_df).__name__}, "
                f"Config: {type(config).__name__}, "
                f"Use without reference: {use_without_reference}"
            )

            # Build summary from results if DataFrame is available
            summary: AnalysisSummary | None = None
            if isinstance(final_df, pd.DataFrame):
                logger.debug(f"Building summary from DataFrame with shape {final_df.shape}")
                try:
                    summary = build_summary_from_df(
                        final_df,
                        use_without_reference=use_without_reference
                    )
                    logger.info("Analysis summary generated successfully")
                except Exception as e:
                    logger.error(f"Failed to build summary: {e}", exc_info=True)
                    # Continue - summary will be None but analysis succeeded
            else:
                logger.warning("No DataFrame available for summary generation")

            # Report completion
            self._progress(PROGRESS_COMPLETE, PROGRESS_MSG_COMPLETED)
            self.finished.emit(bool(success), summary)

        except Exception as e:
            # Capture and report full exception with traceback
            tb = traceback.format_exc()
            error_msg = f"{e}\n{tb}"
            logger.error(f"Analysis worker failed with exception:\n{error_msg}")
            
            self.error.emit(error_msg)
            self.finished.emit(False, None)

        finally:
            # Always reset running flag
            self._running = False
            logger.debug("Analysis worker execution completed, running flag reset")