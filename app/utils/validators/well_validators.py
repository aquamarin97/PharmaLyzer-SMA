# app\utils\validators\well_validators.py
# app/utils/validators/well_validators.py
"""
Well ID input validators for 96-well plate format.

Provides Qt validators for well ID input fields (e.g., A01-H12).
Enforces proper formatting and valid well ranges.

Well Format:
    - Row: A-H (8 rows)
    - Column: 01-12 (12 columns)
    - Examples: A01, B05, H12

Usage:
    from app.utils.validators.well_validators import WellValidator
    
    # Apply to QLineEdit
    line_edit = QLineEdit()
    validator = WellValidator()
    line_edit.setValidator(validator)
    
    # User types "A5" → auto-formatted to "A05"
    # User types "A13" → rejected (column out of range)

Validation Rules:
    1. First character must be A-H
    2. Second character must be digit
    3. If second char is 2-9: Format to X0X (e.g., A5 → A05)
    4. If second char is 0: Third char must be 1-9 (A01-A09)
    5. If second char is 1: Third char must be 0-2 (A10-A12)

Auto-formatting:
    - Input "A5" → "A05" (on validation)
    - Input "a7" → "A07" (uppercase + zero-padding)
    - Incomplete input "A" → "A01" (on fixup/focus out)
"""

from __future__ import annotations

import logging
from typing import Final

from PyQt5.QtGui import QValidator

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

VALID_ROWS: Final[str] = "ABCDEFGH"
"""Valid row letters (8 rows)"""

MIN_COLUMN: Final[int] = 1
"""Minimum column number"""

MAX_COLUMN: Final[int] = 12
"""Maximum column number"""

DEFAULT_WELL: Final[str] = "A01"
"""Default well ID for incomplete input"""


# ============================================================================
# WELL VALIDATOR
# ============================================================================

class WellValidator(QValidator):
    """
    Validator for 96-well plate well IDs (A01-H12).
    
    Features:
        - Auto-formatting (A5 → A05)
        - Uppercase conversion
        - Real-time validation
        - Fixup on focus out
    
    Validation States:
        - Acceptable: Valid complete well ID (A01, H12)
        - Intermediate: Partial but potentially valid (A, A0, A1)
        - Invalid: Cannot become valid (Z, A0, A13)
    
    Example:
        >>> validator = WellValidator()
        >>> line_edit.setValidator(validator)
        >>> # User types "a5" → displays "A05"
    
    Note:
        Qt automatically calls validate() on each keystroke.
        fixup() is called when focus leaves the input field.
    """
    
    def validate(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        """
        Validate well ID input.
        
        Args:
            text: Current input text
            pos: Cursor position
            
        Returns:
            Tuple of (state, formatted_text, cursor_position)
            - state: Acceptable, Intermediate, or Invalid
            - formatted_text: Auto-formatted text (if applicable)
            - cursor_position: Updated cursor position
            
        Validation Logic:
            1. Empty/whitespace → Intermediate (allow deletion)
            2. First char not A-H → Invalid
            3. Single char A-H → Intermediate (incomplete)
            4. Second char 2-9 → Auto-format to X0X (e.g., A5 → A05)
            5. Second char 0 → Wait for third char (1-9)
            6. Second char 1 → Wait for third char (0-2)
        """
        # Convert to uppercase for consistency
        normalized = text.upper()
        
        # Case 1: Empty or whitespace (allow user to delete)
        if not normalized.strip():
            return (QValidator.Intermediate, normalized, pos)
        
        # Case 2: First character validation (must be A-H)
        if normalized[0] not in VALID_ROWS:
            logger.debug(f"Invalid row letter: {normalized[0]}")
            return (QValidator.Invalid, text, pos)
        
        # Case 3: Single character (just the row letter)
        if len(normalized) == 1:
            return (QValidator.Intermediate, normalized, pos)
        
        # Case 4: Second character validation (must be digit)
        second_char = normalized[1]
        
        if not second_char.isdigit():
            logger.debug(f"Second char not digit: {second_char}")
            return (QValidator.Invalid, text, pos)
        
        # Case 5: Smart formatting based on second character
        return self._validate_column(normalized, pos)
    
    def _validate_column(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        """
        Validate column portion of well ID.
        
        Args:
            text: Normalized text (uppercase, validated row)
            pos: Cursor position
            
        Returns:
            Validation result tuple
        """
        second_char = text[1]
        
        # Quick formatting: 2-9 → X0X (e.g., A5 → A05)
        if second_char in "23456789":
            formatted = f"{text[0]}0{second_char}"
            logger.debug(f"Auto-formatted {text} → {formatted}")
            return (QValidator.Acceptable, formatted, 3)
        
        # Second char is "0" (e.g., A0_)
        if second_char == "0":
            return self._validate_zero_column(text, pos)
        
        # Second char is "1" (e.g., A1_)
        if second_char == "1":
            return self._validate_ten_column(text, pos)
        
        # Should not reach here (all digits 0-9 covered)
        return (QValidator.Invalid, text, pos)
    
    def _validate_zero_column(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        """
        Validate column starting with 0 (01-09).
        
        Args:
            text: Text starting with X0 (e.g., "A0")
            pos: Cursor position
            
        Returns:
            Validation result
        """
        if len(text) == 2:
            # Incomplete: waiting for third digit
            return (QValidator.Intermediate, text, pos)
        
        if len(text) == 3:
            third_char = text[2]
            # Valid columns: 01-09
            if third_char in "123456789":
                logger.debug(f"Valid column: {text[1:]}")
                return (QValidator.Acceptable, text, pos)
            
            logger.debug(f"Invalid third char for X0_: {third_char}")
            return (QValidator.Invalid, text, pos)
        
        # Too long (>3 characters)
        return (QValidator.Invalid, text, pos)
    
    def _validate_ten_column(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        """
        Validate column starting with 1 (10-12).
        
        Args:
            text: Text starting with X1 (e.g., "A1")
            pos: Cursor position
            
        Returns:
            Validation result
        """
        if len(text) == 2:
            # Incomplete: waiting for third digit
            return (QValidator.Intermediate, text, pos)
        
        if len(text) == 3:
            third_char = text[2]
            # Valid columns: 10, 11, 12
            if third_char in "012":
                logger.debug(f"Valid column: {text[1:]}")
                return (QValidator.Acceptable, text, pos)
            
            logger.debug(f"Invalid third char for X1_: {third_char}")
            return (QValidator.Invalid, text, pos)
        
        # Too long (>3 characters)
        return (QValidator.Invalid, text, pos)
    
    def fixup(self, text: str) -> str:
        """
        Fix incomplete well ID on focus out.
        
        Called automatically when user leaves input field.
        Completes partial input to valid well ID.
        
        Args:
            text: Current input text
            
        Returns:
            Completed/fixed well ID
            
        Fixup Rules:
            - Empty → "A01"
            - "A" → "A01"
            - "A0" → "A01"
            - "A1" → "A01" (ambiguous, use default)
            - "Z5" → "A01" (invalid row, use default)
        
        Example:
            >>> validator.fixup("A")
            'A01'
            >>> validator.fixup("B")
            'B01'
        """
        if not text:
            return DEFAULT_WELL
        
        normalized = text.upper()
        
        # Validate row
        row = normalized[0] if normalized[0] in VALID_ROWS else DEFAULT_WELL[0]
        
        # Incomplete input → default to column 01
        if len(normalized) < 3:
            logger.debug(f"Incomplete input '{text}' fixed to {row}01")
            return f"{row}01"
        
        return normalized


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_well_validator() -> WellValidator:
    """
    Create a new WellValidator instance.
    
    Returns:
        Configured WellValidator
        
    Example:
        >>> validator = create_well_validator()
        >>> line_edit.setValidator(validator)
    """
    return WellValidator()


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    "WellValidator",
    "create_well_validator",
    "VALID_ROWS",
    "MIN_COLUMN",
    "MAX_COLUMN",
    "DEFAULT_WELL",
]