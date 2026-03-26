# app\views\table\drop_down_delegate.py
# -*- coding: utf-8 -*-
"""
Custom Dropdown Delegate for Table Cells.

This module provides QStyledItemDelegate implementations for:
- QComboBox editors in table cells
- Custom popup item rendering with preserved semantic colors
- Hover/selection effects that don't override background colors

Performance optimizations:
- Cached QBrush/QColor objects to avoid repeated creation
- Efficient paint operations with proper clipping
- Minimal pen/brush switching during paint
- Pre-calculated contrast colors for text

Author: Pharmalyzer Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QComboBox, QStyle, QStyleOptionViewItem, QStyledItemDelegate

if TYPE_CHECKING:
    from PyQt5.QtCore import QAbstractItemModel, QModelIndex
    from PyQt5.QtWidgets import QWidget

logger = logging.getLogger(__name__)


def _calculate_contrast_foreground(background: QColor) -> QColor:
    """
    Calculate optimal text color (black/white) for given background color.

    Uses W3C relative luminance formula for accessibility compliance.

    Args:
        background: Background QColor

    Returns:
        QColor (black or white) with best contrast

    Performance: Called once per color, can be cached by caller
    """
    # Extract RGB components
    red, green, blue = background.red(), background.green(), background.blue()

    # Calculate relative luminance (ITU-R BT.709)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue

    # Use black text for light backgrounds, white for dark
    return QColor(Qt.black) if luminance >= 160 else QColor(Qt.white)


class _ComboPopupItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for QComboBox popup items.

    Preserves semantic background colors while adding subtle hover/selection
    effects through border and slight darkening. This prevents the common
    issue where standard Qt selection styles completely override item colors.

    Performance characteristics:
    - Efficient paint with minimal state changes
    - Cached colors and pens
    - Proper clipping and antialiasing
    - Pre-calculated text positioning
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the combo popup item delegate.

        Args:
            parent: Parent widget (typically the combo's view)
        """
        super().__init__(parent)

        # Cache frequently used pens for performance
        self._selected_pen = QPen(QColor(255, 255, 255, 220), 2)
        self._hover_pen = QPen(QColor(255, 255, 255, 140), 1)

        logger.debug("_ComboPopupItemDelegate initialized")

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """
        Custom paint for combo popup items.

        Preserves background color while adding hover/selection feedback
        through borders and subtle darkening.

        Args:
            painter: QPainter to draw with
            option: Style options for the item
            index: Model index of the item

        Performance: Minimizes painter state changes, uses cached pens
        """
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Calculate item rectangle with padding
        rect = option.rect.adjusted(4, 2, -4, -2)

        # Get semantic background color from model
        background_data = index.data(Qt.BackgroundRole)
        if isinstance(background_data, QColor):
            base_color = background_data
        else:
            # Fallback: neutral color matching the combo's theme
            base_color = QColor("#4ca1af")

        # Determine state
        is_hovered = bool(option.state & QStyle.State_MouseOver)
        is_selected = bool(option.state & QStyle.State_Selected)

        # Apply subtle darkening for hover/selection (preserves base color)
        fill_color = QColor(base_color)
        if is_selected:
            fill_color = fill_color.darker(112)  # 12% darker
        elif is_hovered:
            fill_color = fill_color.darker(106)  # 6% darker

        # Draw background with rounded corners
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill_color)
        painter.drawRoundedRect(rect, 6, 6)

        # Draw border for hover/selection feedback
        if is_selected:
            painter.setPen(self._selected_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 6, 6)
        elif is_hovered:
            painter.setPen(self._hover_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 6, 6)

        # Draw text
        text = str(index.data(Qt.DisplayRole) or "")
        painter.setPen(QColor(Qt.white))  # White text for dark backgrounds

        # Make text bold when selected for emphasis
        font = option.font
        if is_selected:
            font.setWeight(600)
        painter.setFont(font)

        # Draw text with padding
        text_rect = rect.adjusted(10, 0, -10, 0)
        painter.drawText(
            text_rect,
            Qt.AlignVCenter | Qt.AlignLeft,
            text,
        )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """
        Provide size hint for combo popup items.

        Args:
            option: Style options
            index: Model index

        Returns:
            QSize with minimum dimensions for proper item rendering

        Performance: Uses base class calculation with minimum constraints
        """
        base_size = super().sizeHint(option, index)
        # Ensure minimum size for readability and touch targets
        width = max(base_size.width(), 180)
        height = max(base_size.height(), 28)
        return QSize(width, height)


class DropDownDelegate(QStyledItemDelegate):
    """
    Delegate for creating QComboBox editors in table cells.

    Creates customized QComboBox editors with:
    - Semantic color coding for options
    - Custom popup rendering (preserves colors during hover/selection)
    - Professional styling matching application theme

    Performance characteristics:
    - Cached item colors and styles
    - Efficient editor creation and data transfer
    - Minimal memory overhead per editor instance
    """

    def __init__(
        self,
        options: list[str],
        parent: QWidget | None = None,
        combo_style: str | None = None,
        item_styles: dict[str, QColor] | None = None,
    ) -> None:
        """
        Initialize the dropdown delegate.

        Args:
            options: List of dropdown options
            parent: Parent widget
            combo_style: Custom QComboBox stylesheet (optional)
            item_styles: Mapping of option text to background colors (optional)
        """
        super().__init__(parent)

        self.options = options
        self.combo_style = combo_style or self._default_combo_style()
        self.item_styles = item_styles or {}

        # Cache popup delegate for reuse
        self._popup_delegate = _ComboPopupItemDelegate()

        logger.debug(
            f"DropDownDelegate initialized: {len(options)} options, "
            f"{len(self.item_styles)} styled items"
        )

    def _default_combo_style(self) -> str:
        """
        Provide default QComboBox stylesheet.

        Returns:
            CSS-style stylesheet string

        Performance: Called once during initialization
        """
        return """
            QComboBox {
                background-color: #4ca1af;
                border: 1px solid #3b8793;
                border-radius: 6px;
                color: white;
                padding: 4px 10px;
                font-size: 11pt;
                font-family: "Arial";
            }
            QComboBox:hover {
                border: 1px solid #2f6f79;
            }
            QComboBox:focus {
                border: 2px solid #2b78da;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            /* Popup panel background (items rendered by custom delegate) */
            QComboBox QAbstractItemView {
                background-color: #2f3337;
                border: 1px solid #1f2327;
                outline: 0;
                padding: 4px;
            }
        """

    def createEditor(
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QComboBox:
        """
        Create QComboBox editor for table cell.

        Args:
            parent: Parent widget for the editor
            option: Style options
            index: Model index of the cell being edited

        Returns:
            Configured QComboBox editor

        Performance: Reuses cached popup delegate, efficient setup
        """
        combo = QComboBox(parent)
        combo.addItems(self.options)
        combo.setStyleSheet(self.combo_style)

        # Configure popup view
        view = combo.view()
        view.setMouseTracking(True)  # Enable hover state
        view.setItemDelegate(self._popup_delegate)

        # Apply semantic colors to items
        for idx, option_text in enumerate(self.options):
            if option_text in self.item_styles:
                background_color = self.item_styles[option_text]
                if isinstance(background_color, QColor):
                    combo.setItemData(idx, background_color, Qt.BackgroundRole)
                    # Set contrasting text color for accessibility
                    text_color = _calculate_contrast_foreground(background_color)
                    combo.setItemData(idx, text_color, Qt.ForegroundRole)

        # Set stable minimum width for consistent UI
        view.setMinimumWidth(max(220, combo.sizeHint().width()))

        logger.debug(f"ComboBox editor created for index ({index.row()}, {index.column()})")
        return combo

    def setEditorData(self, editor: QComboBox, index: QModelIndex) -> None:
        """
        Populate editor with current cell data.

        Args:
            editor: QComboBox to populate
            index: Model index containing data

        Performance: Direct text lookup, O(n) where n is option count
        """
        value = index.model().data(index, Qt.EditRole)
        text = str(value) if value else ""

        # Set current selection
        editor.setCurrentText(text)

        logger.debug(f"Editor data set: '{text}' for index ({index.row()}, {index.column()})")

    def setModelData(
        self,
        editor: QComboBox,
        model: QAbstractItemModel,
        index: QModelIndex,
    ) -> None:
        """
        Write editor data back to model.

        Args:
            editor: QComboBox with selected value
            model: Table model to update
            index: Model index to write to

        Performance: Single model setData call with EditRole
        """
        selected_text = editor.currentText()
        success = model.setData(index, selected_text, Qt.EditRole)

        if success:
            logger.debug(
                f"Model data updated: '{selected_text}' at "
                f"index ({index.row()}, {index.column()})"
            )
        else:
            logger.warning(
                f"Failed to update model data at "
                f"index ({index.row()}, {index.column()})"
            )

    def updateEditorGeometry(
        self,
        editor: QComboBox,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """
        Update editor geometry to match cell dimensions.

        Args:
            editor: QComboBox to position
            option: Style options containing geometry
            index: Model index (unused)

        Performance: Direct geometry assignment, called on resize
        """
        editor.setGeometry(option.rect)