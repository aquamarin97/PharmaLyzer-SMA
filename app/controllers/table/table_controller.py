# app\controllers\table\table_controller.py
# -*- coding: utf-8 -*-
"""Main table controller for PCR analysis results display.

This module provides the primary controller for the results table widget,
coordinating data loading, model updates, formatting, and user interactions.
It manages:
- Table widget setup and lifecycle
- Data loading from DataStore to table model
- Column filtering and rounding
- Dropdown delegate configuration
- Table interaction coordination
- Column width management

The controller follows a build-once pattern where the table widget is
created once and data is updated through model replacement rather than
widget reconstruction.

Architecture:
- AppTableController: Main orchestration
- EditableTableModel: Data model with cell editing
- TableInteractionController: User interaction handling
- DropDownDelegate: Dropdown cell editor
- TableViewWidget: Custom view with column sizing

Example:
    Basic usage in main application::

        from app.controllers.table.table_controller import AppTableController
        from app.views.main_view import MainView
        from app.models.main_model import MainModel

        # Create controller
        controller = AppTableController(
            view=main_view,
            model=main_model,
            graph_drawer=graph_view,
            interaction_store=interaction_store
        )

        # Later: load analysis results
        controller.load_csv_to_table()

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

import pandas as pd
from PyQt5.QtGui import QStandardItemModel

from app.constants.table_config import (
    CSV_FILE_HEADERS,
    DROPDOWN_COLUMN,
    DROPDOWN_OPTIONS,
    ITEM_STYLES,
    ROUND_COLUMNS,
    TABLE_WIDGET_HEADERS,
)
from app.controllers.table.table_interaction_controller import TableInteractionController
from app.services.data_store import DataStore
from app.services.pcr_data_service import PCRDataService
from app.views.table.drop_down_delegate import DropDownDelegate
from app.views.table.editable_table_model import EditableTableModel
from app.views.table.table_view_widget import TableViewWidget

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Default threshold values
DEFAULT_CARRIER_RANGE = 0.5999
DEFAULT_UNCERTAIN_RANGE = 0.6199

# Column expansion ratios for proportional sizing
# Order matches TABLE_WIDGET_HEADERS columns
DEFAULT_COLUMN_RATIOS = [2, 2, 2, 10, 2, 3, 3, 3, 3]

# Error messages
ERROR_NO_DATA = "No data loaded. DataStore is empty."
ERROR_MISSING_DROPDOWN_COLUMN = "Dropdown kolonu bulunamadı"


# ============================================================================
# Controller
# ============================================================================

class AppTableController:
    """Main controller for PCR analysis results table.
    
    This controller manages the complete lifecycle of the results table:
    - Widget setup and replacement in UI
    - Data model creation and updates
    - Column filtering and rounding
    - Dropdown delegate configuration
    - Interaction controller wiring
    - Dynamic threshold updates
    
    The controller implements a build-once strategy:
    - Table widget created once in __init__
    - Data updates through model replacement
    - Column ratios reapplied after model changes
    
    Attributes:
        view: Main application view
        model: Main application model
        graph_drawer: PCR graph view widget
        interaction_store: Shared interaction state store
        dropdown_column: Column name for dropdown editor
        dropdown_options: Available dropdown options
        round_columns: Dict mapping column names to decimal places
        carrier_range: Current carrier classification threshold
        uncertain_range: Current uncertain classification threshold
        table_widget: TableViewWidget instance
        table_model: EditableTableModel instance
        table_interaction: TableInteractionController instance
    """

    def __init__(self, view, model, graph_drawer=None, interaction_store=None):
        """Initialize table controller and setup table widget.
        
        Args:
            view: Main application view containing UI elements
            model: Main application model with analysis data
            graph_drawer: Optional PCR graph view for visualization
            interaction_store: Optional interaction store for coordination
        
        Note:
            - Replaces placeholder table widget in view
            - Creates empty model initially
            - Sets up interaction controller
            - Configures column expansion ratios
        """
        logger.info("Initializing AppTableController")
        
        self.view = view
        self.model = model
        self.graph_drawer = graph_drawer
        self.interaction_store = interaction_store

        # Table configuration from constants
        self.dropdown_column = DROPDOWN_COLUMN
        self.dropdown_options = DROPDOWN_OPTIONS
        self.round_columns = ROUND_COLUMNS

        # Threshold values
        self.carrier_range = DEFAULT_CARRIER_RANGE
        self.uncertain_range = DEFAULT_UNCERTAIN_RANGE

        # Table components (created in setup)
        self.table_widget = None
        self.table_model = None
        self.table_interaction = None

        # Column sizing configuration (single source of truth)
        self._column_ratios = DEFAULT_COLUMN_RATIOS

        # Setup table widget in UI
        self.setup_table_in_main_window()
        
        logger.info("AppTableController initialization complete")

    def setup_table_in_main_window(self):
        """Setup table widget in main window UI.
        
        Replaces the placeholder table widget from UI designer with
        a custom TableViewWidget that supports proportional column sizing.
        
        Steps:
            1. Get original placeholder widget from UI
            2. Create new TableViewWidget
            3. Replace in layout
            4. Delete placeholder widget
            5. Set empty model with headers
            6. Apply column expansion ratios
            7. Create interaction controller
        
        Note:
            This is called once during initialization. The widget is
            reused for all subsequent data updates.
        """
        logger.debug("Setting up table widget in main window")
        ui = self.view.ui

        # Replace placeholder with custom table widget
        original_widget = ui.table_widget_resulttable
        ui.table_widget_resulttable = TableViewWidget(original_widget)
        ui.verticalLayout_3.replaceWidget(original_widget, ui.table_widget_resulttable)
        original_widget.deleteLater()

        self.table_widget = ui.table_widget_resulttable
        logger.debug("Table widget replaced in UI")

        # Set empty model with headers
        empty_model = QStandardItemModel()
        empty_model.setHorizontalHeaderLabels(TABLE_WIDGET_HEADERS)
        self.table_widget.setModel(empty_model)

        # Apply column expansion ratios
        self.table_widget.set_column_expansion_ratios(self._column_ratios)
        logger.debug(f"Column expansion ratios set: {self._column_ratios}")

        # Create interaction controller
        self.table_interaction = TableInteractionController(
            table_widget=self.table_widget,
            pcr_data_service=PCRDataService(),
            graph_drawer=self.graph_drawer,
            interaction_store=self.interaction_store
        )
        logger.debug("Table interaction controller created")

    def set_carrier_range(self, val: float):
        """Update carrier classification threshold.
        
        Updates the threshold value and propagates to table model if present.
        
        Args:
            val: New carrier range value (typically 0.5999)
        
        Note:
            Model updates are applied only if EditableTableModel is active.
        """
        self.carrier_range = float(val)
        logger.debug(f"Carrier range updated to: {self.carrier_range}")
        
        if isinstance(self.table_model, EditableTableModel):
            self.table_model.carrier_range = self.carrier_range
            logger.debug("Carrier range propagated to table model")

    def set_uncertain_range(self, val: float):
        """Update uncertain classification threshold.
        
        Updates the threshold value and propagates to table model if present.
        
        Args:
            val: New uncertain range value (typically 0.6199)
        
        Note:
            Model updates are applied only if EditableTableModel is active.
        """
        self.uncertain_range = float(val)
        logger.debug(f"Uncertain range updated to: {self.uncertain_range}")
        
        if isinstance(self.table_model, EditableTableModel):
            self.table_model.uncertain_range = self.uncertain_range
            logger.debug("Uncertain range propagated to table model")

    def load_csv_to_table(self):
        """Load analysis results from DataStore to table.
        
        Main data loading method that:
        1. Retrieves DataFrame from DataStore
        2. Applies column rounding
        3. Filters to display columns
        4. Updates or creates table model
        5. Configures dropdown delegate
        6. Reapplies column ratios
        
        Raises:
            ValueError: If DataStore is empty or dropdown column missing
        
        Flow:
            DataStore → get_df_copy()
            → _round_columns()
            → _filter_columns()
            → _update_model()
            → Apply column ratios
        
        Note:
            This method can be called multiple times (e.g., after analysis).
            It updates the existing table widget without reconstruction.
        """
        logger.info("Loading data from DataStore to table")
        
        # Retrieve data
        df = DataStore.get_df_copy()
        if df is None or df.empty:
            logger.error(ERROR_NO_DATA)
            raise ValueError(ERROR_NO_DATA)

        logger.debug(f"Retrieved DataFrame from DataStore - Shape: {df.shape}")

        # Apply transformations
        df = self._round_columns(df)
        df = self._filter_columns(df)
        
        logger.debug(f"Processed DataFrame - Shape: {df.shape}")

        # Update model
        self._update_model(df)
        
        logger.info("Table data loading complete")

    def _round_columns(self, df):
        """Round numeric columns to specified decimal places.
        
        Applies rounding configuration from ROUND_COLUMNS constant to
        ensure consistent numeric display precision.
        
        Args:
            df: Input DataFrame with raw values
        
        Returns:
            DataFrame with rounded numeric columns
        
        Note:
            - Only rounds columns present in both df and ROUND_COLUMNS
            - Handles NaN values gracefully (leaves unchanged)
        """
        logger.debug("Rounding numeric columns")
        
        for col, digits in self.round_columns.items():
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: round(x, digits) if pd.notna(x) else x
                )
                logger.debug(f"Rounded column '{col}' to {digits} decimal places")
        
        return df

    def _filter_columns(self, df):
        """Filter DataFrame to display columns only.
        
        Reduces DataFrame to columns that appear in both CSV_FILE_HEADERS
        and TABLE_WIDGET_HEADERS, ensuring only relevant columns are displayed.
        
        Args:
            df: Input DataFrame with all columns
        
        Returns:
            DataFrame with filtered columns in TABLE_WIDGET_HEADERS order
        
        Note:
            Column order matches TABLE_WIDGET_HEADERS for consistent display.
        """
        logger.debug("Filtering columns for display")
        
        csv_headers = CSV_FILE_HEADERS
        table_headers = TABLE_WIDGET_HEADERS
        
        # Get columns present in both sets
        filtered_columns = [col for col in table_headers if col in csv_headers and col in df.columns]    
            
        logger.debug(f"Filtered to {len(filtered_columns)} display columns: {filtered_columns}")
        
        return df[filtered_columns]

    def _update_model(self, df):
        """Update or create table model with new data.
        
        Updates existing EditableTableModel or creates new one if not present.
        Configures model with current threshold values and dropdown settings.
        
        Args:
            df: DataFrame with processed data ready for display
        
        Raises:
            ValueError: If dropdown column not found in DataFrame
        
        Note:
            - Reuses existing model when possible (better performance)
            - Reattaches selection model after model replacement
            - Configures dropdown delegate for classification column
            - Reapplies column expansion ratios
        """
        # Validate dropdown column exists
        if self.dropdown_column not in df.columns:
            logger.error(f"{ERROR_MISSING_DROPDOWN_COLUMN}: {self.dropdown_column}")
            raise ValueError(f"{ERROR_MISSING_DROPDOWN_COLUMN}: {self.dropdown_column}")

        # Get dropdown column index
        dropdown_column_index = df.columns.get_loc(self.dropdown_column)
        logger.debug(f"Dropdown column '{self.dropdown_column}' at index {dropdown_column_index}")

        # Update existing model or create new one
        if isinstance(self.table_model, EditableTableModel):
            logger.debug("Updating existing EditableTableModel")
            self.table_model.set_dataframe(
                df,
                dropdown_column=dropdown_column_index,
                dropdown_options=self.dropdown_options,
                carrier_range=self.carrier_range,
                uncertain_range=self.uncertain_range
            )
        else:
            logger.debug("Creating new EditableTableModel")
            self.table_model = EditableTableModel(
                data=df,
                dropdown_column=dropdown_column_index,
                dropdown_options=self.dropdown_options,
                carrier_range=self.carrier_range,
                uncertain_range=self.uncertain_range
            )
            self.table_widget.setModel(self.table_model)
            
            # Reattach selection model after model change
            if self.table_interaction is not None:
                self.table_interaction.attach_selection_model()
                logger.debug("Selection model reattached")

        # Configure dropdown delegate for classification column
        dropdown_delegate = DropDownDelegate(
            options=self.dropdown_options,
            parent=self.table_widget,
            item_styles=ITEM_STYLES
        )
        self.table_widget.setItemDelegateForColumn(dropdown_column_index, dropdown_delegate)
        logger.debug("Dropdown delegate configured")

        # Reapply column expansion ratios after model update
        # Model columnCount may have changed; TableViewWidget handles validation
        self.table_widget.set_column_expansion_ratios(self._column_ratios)
        logger.debug("Column expansion ratios reapplied")
    def reset(self) -> None:
        """Reset table widget to empty state."""
        logger.debug("Resetting table widget to empty model")

        empty_model = QStandardItemModel()
        empty_model.setHorizontalHeaderLabels(TABLE_WIDGET_HEADERS)

        self.table_model = None
        self.table_widget.setModel(empty_model)
        self.table_widget.set_column_expansion_ratios(self._column_ratios)

        if self.table_interaction is not None:
            self.table_interaction.attach_selection_model()

        logger.info("Table widget reset complete")