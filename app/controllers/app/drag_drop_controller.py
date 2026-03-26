# app\controllers\app\drag_drop_controller.py
# -*- coding: utf-8 -*-
"""Drag-and-drop controller for RDML file import.

This module provides a controller that manages drag-and-drop functionality
for importing RDML files into the application. It handles:
- Drag enter event validation (file type, count)
- Drop event processing and validation
- File path validation (existence, extension)
- Manual file selection support (via file dialog)
- Result signal emission to parent controller

The controller follows a clear separation of concerns:
- UI event handling (drag/drop)
- File validation (extension, existence)
- Result communication (signals)
- NO data parsing or storage (delegated to services)

Example:
    Basic usage in main controller::

        from app.controllers.app.drag_drop_controller import DragDropController
        from PyQt5.QtWidgets import QLabel

        # Create label for drag-drop area
        label = QLabel("Drag RDML file here")

        # Create controller
        controller = DragDropController(label)

        # Connect to result handler
        controller.drop_completed.connect(handle_drop_result)

        # User drags file → validation → signal emitted
        # Or manual import via file dialog:
        controller.manual_drop("/path/to/file.rdml", "file.rdml")

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
import os
from typing import Tuple

from PyQt5.QtCore import QEvent, QObject, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import QLabel

from app.i18n import t

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# RDML file extension
RDML_EXTENSION = ".rdml"

# Maximum number of files allowed in single drop
MAX_DROP_FILES = 1

# Error message keys (i18n)
ERROR_KEY_INVALID_FILE = "dragdrop.errors.invalid_file"
ERROR_KEY_INVALID_PATH = "dragdrop.errors.invalid_path"
ERROR_KEY_EXTENSION = "dragdrop.errors.extension"
ERROR_KEY_NOT_FOUND = "dragdrop.errors.not_found"
ERROR_KEY_VALIDATION_FAILED = "dragdrop.errors.validation_failed"

# Success message key (i18n)
SUCCESS_KEY_READY = "dragdrop.ready"

# Hardcoded error message for multiple files (not in i18n yet)
ERROR_MULTIPLE_FILES = "Lütfen yalnızca bir dosya bırakın."

# Default success message template
SUCCESS_MESSAGE_TEMPLATE = "Hazır: {file_name}"


# ============================================================================
# Controller
# ============================================================================

class DragDropController(QObject):
    """Controller managing drag-and-drop functionality for RDML file import.
    
    This controller handles all aspects of drag-and-drop file import:
    - Event filtering for drag enter and drop events
    - File validation (count, extension, existence)
    - Result signal emission
    - Manual file selection support
    
    Responsibilities:
    - UI event handling (drag/drop on label)
    - File path validation (extension, existence)
    - Result communication via signals
    
    NOT Responsible For:
    - RDML file parsing (delegated to RDMLService)
    - Data storage (delegated to DataStore)
    - Analysis execution (delegated to AnalysisService)
    
    The controller is stateless except for the label reference - all
    validation is performed per-event with immediate signal emission.
    
    Signals:
        drop_completed(bool, str, str, str): Emitted when drop completes
            - success: True if file is valid, False otherwise
            - rdml_path: Full path to RDML file (empty on failure)
            - file_name: Base filename (may be set even on failure)
            - message: Success or error message for UI display
    
    Attributes:
        label: QLabel widget accepting drag-and-drop events
    
    Example:
        >>> label = QLabel()
        >>> controller = DragDropController(label)
        >>> controller.drop_completed.connect(lambda s, p, n, m: print(m))
        >>> # User drags valid .rdml file
        >>> # Output: "Hazır: experiment.rdml"
    """

    # Signal emitted when drop operation completes (success or failure)
    # Args: (success: bool, rdml_path: str, file_name: str, message: str)
    drop_completed = pyqtSignal(bool, str, str, str)

    def __init__(self, label: QLabel):
        """Initialize drag-drop controller and setup event handling.
        
        Args:
            label: QLabel widget to enable drag-and-drop on
        
        Note:
            - Sets label to accept drops
            - Installs event filter for drag/drop events
            - No validation performed until events occur
        """
        super().__init__()
        
        self.label = label
        
        logger.debug("Initializing DragDropController")
        self._setup_drag_drop()
        logger.info("DragDropController initialized")

    def _setup_drag_drop(self) -> None:
        """Configure label for drag-and-drop functionality.
        
        Enables drop acceptance and installs event filter to intercept
        drag enter and drop events.
        """
        self.label.setAcceptDrops(True)
        self.label.installEventFilter(self)
        logger.debug("Drag-drop setup complete on label")

    # ========================================================================
    # Qt Event Filter
    # ========================================================================

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter Qt events for drag-and-drop handling.
        
        Intercepts DragEnter and Drop events on the label widget.
        Other events are passed through to parent handler.
        
        Args:
            watched: Object that received the event
            event: Qt event object
        
        Returns:
            True if event was handled (DragEnter/Drop on label)
            False to continue event propagation
        
        Event Handling:
            - DragEnter: Validate file and accept/reject drag
            - Drop: Process dropped file and emit signal
        """
        # Only handle events on our label
        if watched != self.label:
            return super().eventFilter(watched, event)

        event_type = event.type()

        # Handle drag enter (validation only)
        if event_type == QEvent.DragEnter and isinstance(event, QDragEnterEvent):
            self._handle_drag_enter(event)
            return True

        # Handle drop (validation + signal emission)
        if event_type == QEvent.Drop and isinstance(event, QDropEvent):
            self._handle_drop(event)
            return True

        # Other events pass through
        return super().eventFilter(watched, event)

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def _handle_drag_enter(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event (file validation for visual feedback).
        
        Validates dropped data to provide immediate visual feedback
        (cursor changes to indicate accept/reject).
        
        Validation:
        - Must have URLs (file paths)
        - Must be exactly 1 file
        - Must have .rdml extension
        - Must exist on filesystem
        
        Args:
            event: Drag enter event object
        
        Note:
            - Calls event.acceptProposedAction() if valid
            - Calls event.ignore() if invalid
            - No signal emission (validation only)
        """
        # Check for URL data (file paths)
        if not event.mimeData().hasUrls():
            logger.debug("Drag enter rejected: no URLs")
            event.ignore()
            return

        urls = event.mimeData().urls()
        
        # Check file count
        if len(urls) != MAX_DROP_FILES:
            logger.debug(f"Drag enter rejected: {len(urls)} files (expected {MAX_DROP_FILES})")
            event.ignore()
            return

        # Validate file path
        file_path = urls[0].toLocalFile()
        is_valid, _, _ = self._validate_rdml_path(file_path)
        
        if is_valid:
            logger.debug(f"Drag enter accepted: {file_path}")
            event.acceptProposedAction()
        else:
            logger.debug(f"Drag enter rejected: invalid file {file_path}")
            event.ignore()

    def _handle_drop(self, event: QDropEvent) -> None:
        """Handle drop event (file validation + signal emission).
        
        Validates dropped file and emits drop_completed signal with
        result. This is where actual file import begins.
        
        Validation Flow:
        1. Check for URL data
        2. Check file count (exactly 1)
        3. Validate file path (extension, existence)
        4. Emit drop_completed signal
        
        Args:
            event: Drop event object
        
        Note:
            Always emits drop_completed signal, even on failure.
            Success flag indicates validation result.
        """
        # Check for URL data
        if not event.mimeData().hasUrls():
            logger.warning("Drop rejected: no URLs in drop data")
            self.drop_completed.emit(
                False,
                "",
                "",
                t(ERROR_KEY_INVALID_FILE)
            )
            return

        urls = event.mimeData().urls()
        
        # Check file count
        if len(urls) != MAX_DROP_FILES:
            logger.warning(f"Drop rejected: {len(urls)} files (expected {MAX_DROP_FILES})")
            self.drop_completed.emit(
                False,
                "",
                "",
                ERROR_MULTIPLE_FILES
            )
            return

        # Validate and process file
        file_path = urls[0].toLocalFile()
        is_valid, file_name, error_message = self._validate_rdml_path(file_path)
        
        if not is_valid:
            logger.warning(f"Drop rejected: validation failed for {file_path} - {error_message}")
            self.drop_completed.emit(False, "", file_name, error_message)
            return

        # Success - emit with file details
        logger.info(f"Drop accepted: {file_path}")
        self.drop_completed.emit(
            True,
            file_path,
            file_name,
            t(SUCCESS_KEY_READY, file_name=file_name)
        )

    # ========================================================================
    # Public API
    # ========================================================================

    def manual_drop(self, file_path: str, file_name: str | None = None) -> None:
        """Simulate drop event for manual file selection (file dialog).
        
        Provides programmatic interface for file selection outside of
        drag-and-drop (e.g., via file dialog). Performs same validation
        as actual drop event.
        
        Args:
            file_path: Full path to RDML file
            file_name: Optional filename override. If None, extracted from path.
        
        Note:
            - Validates file path same as drop event
            - Emits drop_completed signal with result
            - Uses provided file_name or infers from path
        
        Example:
            >>> controller.manual_drop("/data/experiment.rdml")
            >>> # Emits: drop_completed(True, "/data/experiment.rdml", "experiment.rdml", "Hazır: experiment.rdml")
            
            >>> controller.manual_drop("/data/experiment.rdml", "My Experiment")
            >>> # Emits: drop_completed(True, "/data/experiment.rdml", "My Experiment", "Hazır: My Experiment")
        """
        logger.debug(f"Manual drop requested: {file_path}")
        
        # Validate file path (also infers filename)
        is_valid, inferred_name, error_message = self._validate_rdml_path(file_path)
        
        # Use provided filename or inferred one
        final_name = file_name or inferred_name
        
        if not is_valid:
            logger.warning(f"Manual drop rejected: {file_path} - {error_message}")
            self.drop_completed.emit(False, "", final_name, error_message)
            return

        # Success - emit with file details
        logger.info(f"Manual drop accepted: {file_path}")
        success_message = SUCCESS_MESSAGE_TEMPLATE.format(file_name=final_name)
        self.drop_completed.emit(True, file_path, final_name, success_message)

    # ========================================================================
    # Validation
    # ========================================================================

    def _validate_rdml_path(self, file_path: str) -> Tuple[bool, str, str]:
        """Validate RDML file path.
        
        Performs comprehensive validation:
        - Type checking (must be non-empty string)
        - Extension checking (must be .rdml)
        - Existence checking (must exist on filesystem)
        
        Args:
            file_path: Path to validate
        
        Returns:
            Tuple of (is_valid, file_name, error_message):
            - is_valid: True if all checks pass
            - file_name: Base filename extracted from path
            - error_message: Localized error message (empty if valid)
        
        Example:
            >>> controller._validate_rdml_path("/data/test.rdml")
            (True, "test.rdml", "")
            
            >>> controller._validate_rdml_path("/data/test.txt")
            (False, "test.txt", "Invalid extension")
            
            >>> controller._validate_rdml_path("")
            (False, "", "Invalid path")
        
        Note:
            - Exceptions during validation are caught and logged
            - Returns generic error message on exception
            - File name extraction attempted even on validation failure
        """
        try:
            # Extract filename for error reporting
            file_name = os.path.basename(file_path) if isinstance(file_path, str) else ""

            # Validate path is non-empty string
            if not isinstance(file_path, str) or not file_path.strip():
                logger.debug(f"Validation failed: invalid path type or empty - {file_path}")
                return False, file_name, t(ERROR_KEY_INVALID_PATH)

            # Validate .rdml extension
            if not file_path.lower().endswith(RDML_EXTENSION):
                logger.debug(f"Validation failed: wrong extension - {file_path}")
                return False, file_name, t(ERROR_KEY_EXTENSION)

            # Validate file exists
            if not os.path.exists(file_path):
                logger.warning(f"Validation failed: file not found - {file_path}")
                return False, file_name, t(ERROR_KEY_NOT_FOUND)

            # All checks passed
            logger.debug(f"Validation passed: {file_path}")
            return True, file_name, ""
            
        except Exception as e:
            # Catch unexpected errors during validation
            # Note: Logs are for debugging only, not shown to user
            logger.exception(f"Exception during validation: {e}")
            return False, "", t(ERROR_KEY_VALIDATION_FAILED)