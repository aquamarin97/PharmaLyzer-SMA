# app\controllers\well\well_edit_controller.py
# -*- coding: utf-8 -*-
"""Well position input controller with validation and auto-formatting.

This module provides a specialized controller for QLineEdit widgets that handle
well position inputs (e.g., A1, F12, H12) in a 96-well plate format. It implements:
- Real-time uppercase conversion during typing
- Auto-padding on focus loss (F1 → F01)
- Well position validation via QValidator
- Signal emission only for finalized, valid values

The controller follows a two-phase validation approach:
1. **Typing Phase**: Convert to uppercase, preserve cursor position
2. **Finalization Phase**: Apply padding, emit stabilized value

This prevents unnecessary signal spam and ensures downstream consumers
only receive valid, normalized well positions.

Example:
    Basic usage for reference well input::

        from PyQt5.QtWidgets import QLineEdit
        from app.controllers.well.well_edit_controller import WellEditController

        # Create line edit widget
        line_edit = QLineEdit()

        # Create controller with callback
        def on_well_changed(well_id: str):
            print(f"Well changed to: {well_id}")

        controller = WellEditController(
            line_edit=line_edit,
            default_value="F12",
            on_change=on_well_changed
        )

        # User types: "f1" → displays "F1" → on blur → "F01"
        # Callback receives: "F01"

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QObject, QSignalBlocker, pyqtSignal
from PyQt5.QtWidgets import QLineEdit

from app.utils.validators.well_validators import WellValidator

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Default well position
DEFAULT_WELL_POSITION = "F12"

# Well format specifications
WELL_ID_LENGTH_WITH_PADDING = 3  # e.g., "F01"
WELL_ID_LENGTH_WITHOUT_PADDING = 2  # e.g., "F1"


# ============================================================================
# Controller
# ============================================================================

class WellEditController(QObject):
    """Controller for well position input with validation and auto-formatting.
    
    This controller manages a QLineEdit widget for well position input, providing:
    - Automatic uppercase conversion during typing
    - Auto-padding on focus loss (F1 → F01)
    - Real-time validation via WellValidator
    - Cursor position preservation during formatting
    - Signal emission only for finalized values
    
    The controller uses a two-phase approach:
    1. **textEdited**: Convert to uppercase, maintain cursor position
    2. **editingFinished**: Apply padding, emit valueChanged signal
    
    This ensures:
    - Smooth typing experience (no cursor jumps)
    - No signal spam during typing
    - Only valid, stabilized values are emitted
    
    Signals:
        valueChanged(str): Emitted when well position is finalized (stabilized)
            Only emitted on editingFinished, never during typing
    
    Attributes:
        line_edit: QLineEdit widget being controlled
        on_change: Optional callback function called with stabilized value
        validator: WellValidator instance for input validation
    
    Example:
        >>> line_edit = QLineEdit()
        >>> controller = WellEditController(line_edit, default_value="A1")
        >>> # User types "h12"
        >>> # Line edit shows: "H12" (uppercase applied)
        >>> # User presses Enter or loses focus
        >>> # valueChanged emits: "H12" (already 3 chars, no padding needed)
        
        >>> # User types "f1"
        >>> # Line edit shows: "F1" (uppercase applied)
        >>> # User presses Enter or loses focus
        >>> # Line edit changes to: "F01" (padding applied)
        >>> # valueChanged emits: "F01"
    """

    # Signal emitted when well position is finalized
    valueChanged = pyqtSignal(str)  # well_id: str (stabilized format)

    def __init__(
        self,
        line_edit: QLineEdit,
        default_value: str = DEFAULT_WELL_POSITION,
        on_change=None
    ):
        """Initialize well edit controller.
        
        Sets up validation, connects signals, and initializes with default value.
        
        Args:
            line_edit: QLineEdit widget to control
            default_value: Initial well position (will be stabilized)
            on_change: Optional callback function(well_id: str) called when
                value is finalized. Receives stabilized well ID.
        
        Note:
            The default_value is immediately stabilized (e.g., "F1" → "F01")
            and set in the line edit.
        
        Example:
            >>> def handle_change(well_id):
            ...     print(f"Well changed: {well_id}")
            >>> controller = WellEditController(
            ...     line_edit,
            ...     default_value="A1",
            ...     on_change=handle_change
            ... )
        """
        super().__init__()
        
        self.line_edit = line_edit
        self.on_change = on_change

        # Set up validator for well position format
        self.validator = WellValidator()
        self.line_edit.setValidator(self.validator)

        # Set default value (stabilized format)
        stabilized_default = self._stabilize(default_value)
        self.line_edit.setText(stabilized_default)
        logger.debug(f"WellEditController initialized with default: '{stabilized_default}'")

        # Connect signals
        # textEdited: fired during typing (every keystroke)
        self.line_edit.textEdited.connect(self._on_text_edited)
        
        # editingFinished: fired on Enter key or focus loss
        self.line_edit.editingFinished.connect(self._on_editing_finished)

    def _on_text_edited(self, text: str) -> None:
        """Handle text changes during typing (real-time uppercase conversion).
        
        Called on every keystroke. Converts text to uppercase without applying
        padding or emitting signals. Preserves cursor position to maintain
        smooth typing experience.
        
        Args:
            text: Current text in line edit
        
        Note:
            - Does NOT call on_change callback (value not finalized yet)
            - Does NOT emit valueChanged signal
            - Only applies uppercase conversion
            - Preserves cursor position for backspace/typing
        """
        # Convert to uppercase
        upper = (text or "").upper()
        
        if upper != text:
            # Save cursor position before changing text
            cursor = self.line_edit.cursorPosition()
            
            # Block signals to prevent recursion
            with QSignalBlocker(self.line_edit):
                self.line_edit.setText(upper)
            
            # Restore cursor position (important for backspace/typing)
            self.line_edit.setCursorPosition(min(cursor, len(upper)))
            
            logger.debug(f"Text edited: '{text}' → '{upper}' (cursor at {cursor})")

    def _on_editing_finished(self) -> None:
        """Handle editing completion (apply padding and emit value).
        
        Called when user presses Enter or line edit loses focus. This method:
        1. Gets current text and converts to uppercase
        2. Applies stabilization (padding if needed: F1 → F01)
        3. Updates line edit if text changed
        4. Emits valueChanged signal with stabilized value
        5. Calls on_change callback if provided
        
        This is the only place where:
        - Padding is applied
        - valueChanged signal is emitted
        - on_change callback is called
        
        Note:
            Uses QSignalBlocker when updating text to prevent infinite
            recursion with editingFinished signal.
        """
        # Get current text (already uppercase from _on_text_edited)
        text = (self.line_edit.text() or "").upper()
        
        # Apply stabilization (padding)
        stabilized = self._stabilize(text)

        # Update line edit if stabilization changed the text
        if stabilized != text:
            logger.debug(f"Editing finished: '{text}' → '{stabilized}' (padding applied)")
            with QSignalBlocker(self.line_edit):
                self.line_edit.setText(stabilized)
        else:
            logger.debug(f"Editing finished: '{stabilized}' (no change)")

        # Emit signal and call callback only for non-empty stabilized values
        if stabilized:
            self.valueChanged.emit(stabilized)
            
            if self.on_change:
                try:
                    self.on_change(stabilized)
                except Exception as e:
                    logger.error(f"on_change callback failed for well '{stabilized}': {e}", exc_info=True)

    @staticmethod
    def _stabilize(text: str) -> str:
        """Stabilize well ID format by applying padding if needed.
        
        Converts 2-character well IDs to 3-character format by adding
        leading zero to single-digit column numbers.
        
        Args:
            text: Raw well ID text (may be 2 or 3 characters)
        
        Returns:
            Stabilized well ID with padding applied if needed
        
        Format Rules:
            - "F1" → "F01" (2 chars: letter + digit → add padding)
            - "F12" → "F12" (3 chars: already padded, no change)
            - "A9" → "A09" (2 chars: add padding)
            - "" → "" (empty input unchanged)
            - "ABC" → "ABC" (invalid format, but returned as-is for validator to reject)
        
        Example:
            >>> WellEditController._stabilize("F1")
            'F01'
            >>> WellEditController._stabilize("F12")
            'F12'
            >>> WellEditController._stabilize("a1")
            'A01'
            >>> WellEditController._stabilize("")
            ''
        
        Note:
            This method doesn't validate - it only applies formatting.
            Validation is handled by WellValidator on the QLineEdit.
        """
        # Normalize: uppercase and strip whitespace
        normalized = (text or "").upper().strip()
        
        # Check if padding needed: 2 chars with letter + digit pattern
        if (
            len(normalized) == WELL_ID_LENGTH_WITHOUT_PADDING
            and normalized[0].isalpha()
            and normalized[1].isdigit()
        ):
            # Add leading zero to column number
            padded = f"{normalized[0]}0{normalized[1]}"
            logger.debug(f"Padding applied: '{normalized}' → '{padded}'")
            return padded
        
        # Return as-is (already 3 chars, empty, or invalid format)
        return normalized