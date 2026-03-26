# app\models\main_model.py
# -*- coding: utf-8 -*-
"""Main application model for PCR analysis application.

This module implements the central model class that coordinates:
- Application state management (file paths, loaded data)
- RDML file import and data storage
- Asynchronous analysis execution with thread management
- Service orchestration (analysis, data, export)
- Configuration management (thresholds, reference wells)

The model follows the Model-View-Controller pattern and uses PyQt5 signals
for decoupled communication with UI components. It implements thread-per-analysis
pattern for robust concurrent execution without resource leaks.

Architecture:
    - Single MainModel instance per application
    - Each analysis runs in a dedicated QThread
    - Automatic thread cleanup after completion
    - Cooperative cancellation support
    - Thread-safe signal-based communication

Example:
    Basic usage in application initialization::

        from PyQt5.QtWidgets import QApplication
        from app.models.main_model import MainModel

        app = QApplication(sys.argv)
        model = MainModel()

        # Connect signals to UI
        model.analysis_busy.connect(ui.show_busy_indicator)
        model.analysis_progress.connect(ui.update_progress)
        model.analysis_finished.connect(ui.handle_completion)
        model.analysis_error.connect(ui.show_error)

        # Import data
        model.import_rdml('/path/to/data.rdml')
        model.set_file_name_from_rdml('data.rdml')

        # Configure analysis
        model.set_carrier_range(0.5999)
        model.set_uncertain_range(0.20)

        # Run analysis
        model.run_analysis()

        # Shutdown cleanly
        app.aboutToQuit.connect(model.shutdown)

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app.controllers.analysis.colored_box_controller import ColoredBoxController
from app.services.analysis_service import AnalysisService
from app.services.data_store import DataStore
from app.services.pcr_data_service import PCRDataService
from app.services.rdml_service import RDMLService
from app.models.workers.analysis_worker import AnalysisWorker

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# File extensions
RDML_EXTENSION = ".rdml"

# Thread wait timeout (milliseconds)
THREAD_SHUTDOWN_TIMEOUT_MS = 3000

# Default state values
DEFAULT_FILE_NAME = ""
DEFAULT_RDML_PATH = ""


# ============================================================================
# State
# ============================================================================

@dataclass
class MainState:
    """Application state container.
    
    Holds the current state of loaded files and paths. This is a simple
    data class that can be easily serialized for state persistence if needed.
    
    Attributes:
        file_name: Display name of loaded file (without .rdml extension)
        rdml_path: Full file system path to loaded RDML file
    
    Example:
        >>> state = MainState()
        >>> state.file_name = "experiment_2024"
        >>> state.rdml_path = "/data/experiment_2024.rdml"
    """
    file_name: str = DEFAULT_FILE_NAME
    rdml_path: str = DEFAULT_RDML_PATH


# ============================================================================
# Main Model
# ============================================================================

class MainModel(QObject):
    """Main application model coordinating state, services, and async analysis.
    
    This class serves as the central model in the MVC architecture, managing:
    - Application state (loaded files, paths)
    - RDML data import and storage
    - Analysis execution with dedicated threads
    - Service lifecycle and configuration
    - Thread-safe cleanup on shutdown
    
    Thread Management Strategy:
    - **Thread-per-analysis**: Each analysis gets a fresh QThread + AnalysisWorker
    - **Automatic cleanup**: Threads are destroyed after completion
    - **Non-blocking shutdown**: UI-triggered cleanup doesn't freeze interface
    - **Blocking shutdown**: Application shutdown ensures thread termination
    
    Signals:
        analysis_busy(bool): Emitted when analysis starts (True) or ends (False)
        analysis_progress(int, str): Progress updates (percent, message)
        analysis_finished(bool): Emitted when analysis completes (success flag)
        analysis_summary_ready(object): Emitted with AnalysisSummary when available
        analysis_error(str): Emitted when analysis fails with error message
    
    Thread Safety:
        - All signals are thread-safe via Qt's signal/slot mechanism
        - State modifications should occur only in UI thread
        - Analysis runs in background thread, communicates via signals
    """

    # Signal definitions
    analysis_busy = pyqtSignal(bool)  # busy: bool
    analysis_progress = pyqtSignal(int, str)  # (percent: int, message: str)
    analysis_finished = pyqtSignal(bool)  # success: bool
    analysis_summary_ready = pyqtSignal(object)  # summary: AnalysisSummary
    analysis_error = pyqtSignal(str)  # error_message: str

    def __init__(self):
        """Initialize main model with services and state.
        
        Creates service instances and initializes application state.
        No threads are created until run_analysis() is called.
        
        Services initialized:
        - ColoredBoxController: Validates control well indicators
        - AnalysisService: Performs PCR analysis calculations
        - PCRDataService: Manages PCR data caching and retrieval
        """
        super().__init__()

        # Application state
        self.state = MainState()
        self.rdml_df: Optional[pd.DataFrame] = None

        # Service instances
        self.colored_box_controller = ColoredBoxController()
        self.analysis_service = AnalysisService()
        self.data_manager = PCRDataService()

        # Thread-per-analysis state
        self._analysis_thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None
        self._busy = False

        logger.info("MainModel initialized")

    # ========================================================================
    # State Management
    # ========================================================================

    def set_file_name_from_rdml(self, file_name: str) -> None:
        """Set display file name from RDML file path.
        
        Extracts the base name without .rdml extension for display purposes.
        This is typically called after importing an RDML file.
        
        Args:
            file_name: File name or path, with or without .rdml extension
        
        Example:
            >>> model.set_file_name_from_rdml("experiment.rdml")
            >>> print(model.state.file_name)
            'experiment'
            
            >>> model.set_file_name_from_rdml("/path/to/data.rdml")
            >>> print(model.state.file_name)
            '/path/to/data'
        """
        if file_name.lower().endswith(RDML_EXTENSION):
            file_name = file_name[: -len(RDML_EXTENSION)]
        
        self.state.file_name = file_name
        logger.debug(f"File name set to: '{file_name}'")

    def reset_data(self) -> None:
        """Reset all loaded data and clear state.
        
        Clears:
        - Global DataStore
        - Cached RDML DataFrame
        - RDML path in state
        - PCRDataService cache
        
        This should be called before importing a new file or when closing
        the current analysis.
        
        Note:
            This does NOT cancel running analysis. Call cancel_analysis() first
            if an analysis is in progress.
        """
        logger.info("Resetting all data and state")
        DataStore.clear()
        self.rdml_df = None
        self.state.rdml_path = DEFAULT_RDML_PATH
        logger.debug("Data reset complete")

    def import_rdml(self, file_path: str) -> None:
        """Import RDML file and populate data stores.
        
        Reads RDML file, converts to DataFrame, and stores in:
        - Global DataStore (singleton)
        - Instance rdml_df attribute
        - State rdml_path
        
        Also clears PCRDataService cache to ensure fresh data.
        
        Args:
            file_path: Full path to RDML file
        
        Raises:
            FileNotFoundError: If file_path doesn't exist
            ValueError: If file is not valid RDML format
            Exception: Other RDML parsing errors
        
        Example:
            >>> model.import_rdml('/data/experiment.rdml')
            >>> print(model.rdml_df.shape)
            (96, 15)  # 96 wells, 15 columns
        
        Note:
            This operation is synchronous and may take time for large files.
            Consider showing a loading indicator in the UI.
        """
        logger.info(f"Importing RDML file: '{file_path}'")
        
        try:
            df = RDMLService.rdml_to_dataframe(file_path)
            logger.debug(f"RDML parsed successfully - Shape: {df.shape}")
            
            DataStore.set_df(df)
            PCRDataService.clear_cache()
            
            self.rdml_df = df
            self.state.rdml_path = file_path
            
            logger.info(f"RDML import complete - {len(df)} wells loaded")
            
        except Exception as e:
            logger.error(f"Failed to import RDML file '{file_path}': {e}", exc_info=True)
            raise

    # ========================================================================
    # Analysis Execution (Thread-per-run Pattern)
    # ========================================================================

    def run_analysis(self) -> None:
        """Start PCR analysis in a new background thread.
        
        Creates a new QThread and AnalysisWorker for this analysis run.
        The thread-per-analysis pattern ensures:
        - No resource leaks from thread reuse
        - Clean state for each analysis
        - Automatic cleanup after completion
        
        If an analysis is already running, this method returns immediately
        without starting a new one (busy flag protection).
        
        Signals Emitted:
            - analysis_busy(True): Immediately when starting
            - Later signals from worker: progress, finished, error, summary_ready
        
        Thread Lifecycle:
            1. Create QThread and AnalysisWorker
            2. Move worker to thread
            3. Connect signals
            4. Start thread (triggers worker.run())
            5. Worker emits progress/finished/error signals
            6. Thread auto-cleanup via finished signal
        
        Example:
            >>> model.run_analysis()
            # ... analysis runs in background ...
            # Signals are emitted as progress occurs
        
        Note:
            Call cancel_analysis() to stop a running analysis cooperatively.
        """
        if self._busy:
            logger.warning("Analysis already running - ignoring run_analysis() call")
            return

        self._busy = True
        self.analysis_busy.emit(True)
        logger.info("Starting new analysis execution")

        self._start_new_analysis_thread()

    def cancel_analysis(self) -> None:
        """Request cooperative cancellation of running analysis.
        
        Attempts to cancel the currently running analysis worker.
        Cancellation is cooperative - the worker must check cancellation
        flag and exit gracefully.
        
        This method is safe to call even if no analysis is running.
        Exceptions during cancellation are silently caught.
        
        Note:
            Cancellation is asynchronous. The worker may take time to
            respond and emit finished signal.
        
        Example:
            >>> model.run_analysis()
            >>> # User clicks cancel button
            >>> model.cancel_analysis()
        """
        if self._worker is not None:
            logger.info("Requesting analysis cancellation")
            try:
                self._worker.cancel()
            except Exception as e:
                logger.warning(f"Exception during cancel request: {e}")
                # Don't propagate - best effort cancellation
        else:
            logger.debug("cancel_analysis() called but no worker active")

    def _start_new_analysis_thread(self) -> None:
        """Internal: Create and start new analysis thread with worker.
        
        Thread Lifecycle Setup:
        1. Cleanup any leftover thread (defensive)
        2. Create fresh QThread and AnalysisWorker
        3. Move worker to thread
        4. Connect all signals (progress, error, finished)
        5. Setup auto-cleanup on thread.finished
        6. Start thread (triggers worker.run() via thread.started)
        
        Auto-cleanup ensures:
        - Worker is deleted when thread finishes (deleteLater)
        - Thread is deleted when it finishes (deleteLater)
        - References are cleared in _cleanup_analysis_thread()
        """
        # Defensive cleanup of any leftover thread
        logger.debug("Cleaning up any previous analysis thread")
        self._cleanup_analysis_thread(non_blocking=True)

        # Create new thread and worker
        thread = QThread(self)
        worker = AnalysisWorker(self.analysis_service)
        worker.moveToThread(thread)

        logger.debug("New analysis thread and worker created")

        # Connect worker signals
        worker.progress.connect(self.analysis_progress)
        worker.error.connect(self.analysis_error)
        worker.finished.connect(self._on_worker_finished)

        # Start worker when thread starts
        thread.started.connect(worker.run)

        # Auto-cleanup: delete worker and thread when done
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Store references
        self._analysis_thread = thread
        self._worker = worker

        # Start thread execution
        logger.info("Starting analysis thread")
        thread.start()

    def _on_worker_finished(self, success: bool, summary) -> None:
        """Internal: Handle worker completion and emit final signals.
        
        Called when AnalysisWorker emits finished signal. This method:
        1. Updates busy state
        2. Emits UI signals (busy, finished, summary_ready)
        3. Triggers thread cleanup
        
        Args:
            success: True if analysis completed successfully, False if failed/cancelled
            summary: AnalysisSummary object or None if not available
        
        Signal Emission Order:
            1. analysis_busy(False) - UI can re-enable controls
            2. analysis_finished(success) - UI knows final status
            3. analysis_summary_ready(summary) - UI can display results (if available)
        
        Note:
            Thread cleanup is non-blocking to avoid freezing UI.
        """
        logger.info(f"Worker finished - Success: {success}, Summary: {summary is not None}")

        # Update busy state and notify UI (order matters for UI responsiveness)
        self._busy = False
        self.analysis_busy.emit(False)
        self.analysis_finished.emit(bool(success))
        
        if summary is not None:
            self.analysis_summary_ready.emit(summary)
            logger.debug("Analysis summary emitted to UI")

        # Cleanup thread (non-blocking to avoid UI freeze)
        self._cleanup_analysis_thread(non_blocking=True)

    def _cleanup_analysis_thread(self, *, non_blocking: bool) -> None:
        """Internal: Clean up analysis thread and worker references.
        
        Handles thread lifecycle cleanup with two modes:
        
        Non-blocking mode (UI-triggered cleanup):
        - Calls quit() to stop event loop
        - Does NOT wait for thread termination
        - Prevents UI freezing during normal operation
        
        Blocking mode (shutdown cleanup):
        - Calls quit() and wait() to ensure termination
        - Guarantees thread is stopped before proceeding
        - Used during application shutdown
        
        Args:
            non_blocking: If True, quit without waiting. If False, wait for termination.
        
        Thread Safety:
            - Safe to call from UI thread or worker thread
            - Handles RuntimeError if Qt objects already deleted
            - Clears references even if thread operations fail
        
        Example:
            >>> # During normal operation (e.g., after analysis)
            >>> model._cleanup_analysis_thread(non_blocking=True)
            
            >>> # During application shutdown
            >>> model._cleanup_analysis_thread(non_blocking=False)
        """
        thread = self._analysis_thread
        
        if thread is None:
            logger.debug("No analysis thread to cleanup")
            self._worker = None
            return

        logger.debug(f"Cleaning up analysis thread (non_blocking={non_blocking})")

        try:
            if thread.isRunning():
                thread.quit()
                logger.debug("Thread quit() called")
                
                if not non_blocking:
                    # Blocking wait during shutdown
                    wait_success = thread.wait(THREAD_SHUTDOWN_TIMEOUT_MS)
                    if wait_success:
                        logger.info("Thread terminated successfully")
                    else:
                        logger.warning(
                            f"Thread did not terminate within {THREAD_SHUTDOWN_TIMEOUT_MS}ms timeout"
                        )
            else:
                logger.debug("Thread not running, no quit needed")
                
        except RuntimeError as e:
            # Qt object may already be deleted
            logger.debug(f"RuntimeError during thread cleanup (expected if object deleted): {e}")

        # Always clear references
        self._analysis_thread = None
        self._worker = None
        logger.debug("Thread references cleared")

    # ========================================================================
    # Application Lifecycle
    # ========================================================================

    def shutdown(self) -> None:
        """Perform graceful shutdown of model and cleanup resources.
        
        This method should be called during application shutdown (e.g., connected
        to QApplication.aboutToQuit signal). It ensures:
        - Analysis is cancelled if running
        - Analysis thread is properly terminated
        - No resource leaks from background threads
        
        Shutdown Sequence:
            1. Request analysis cancellation (cooperative)
            2. Wait for thread termination (blocking, with timeout)
            3. Clear thread references
        
        Thread Termination:
            Uses blocking cleanup with timeout to ensure thread stops before
            application exits. If thread doesn't stop within timeout, a warning
            is logged but shutdown proceeds.
        
        Example:
            >>> app = QApplication(sys.argv)
            >>> model = MainModel()
            >>> app.aboutToQuit.connect(model.shutdown)
            >>> # ... application runs ...
            >>> app.quit()  # Triggers model.shutdown()
        
        Note:
            This is the only place where thread cleanup is blocking.
            All other cleanups use non-blocking mode to prevent UI freezes.
        """
        logger.info("MainModel shutdown initiated")

        # Request analysis cancellation
        try:
            self.cancel_analysis()
        except Exception as e:
            logger.error(f"Exception during shutdown cancellation: {e}", exc_info=True)

        # Ensure thread is terminated (blocking wait)
        self._cleanup_analysis_thread(non_blocking=False)
        
        logger.info("MainModel shutdown complete")

    # ========================================================================
    # Configuration Passthrough
    # ========================================================================

    def set_checkbox_status(self, value: bool) -> None:
        """Set reference-free analysis mode.
        
        Args:
            value: If True, analysis runs without reference well normalization
        """
        self.analysis_service.set_checkbox_status(value)
        logger.debug(f"Checkbox status set to: {value}")

    def set_referance_well(self, value: str) -> None:
        """Set reference well position for normalization.
        
        Args:
            value: Well position (e.g., 'A1', 'H12')
        """
        self.analysis_service.set_referance_well(value)
        logger.debug(f"Reference well set to: '{value}'")

    def set_carrier_range(self, value: float) -> None:
        """Set carrier classification threshold.
        
        Args:
            value: Threshold value for carrier detection (typically 0.5999)
        """
        self.analysis_service.set_carrier_range(value)
        logger.debug(f"Carrier range set to: {value}")

    def set_uncertain_range(self, value: float) -> None:
        """Set uncertain result threshold range.
        
        Args:
            value: Threshold range for uncertain classification (typically 0.20)
        """
        self.analysis_service.set_uncertain_range(value)
        logger.debug(f"Uncertain range set to: {value}")

    def get_carrier_range(self) -> float:
        """Get current carrier classification threshold.
        
        Returns:
            Current carrier range value
        """
        return float(self.analysis_service.config.carrier_range)

    def get_uncertain_range(self) -> float:
        """Get current uncertain result threshold range.
        
        Returns:
            Current uncertain range value
        """
        return float(self.analysis_service.config.uncertain_range)