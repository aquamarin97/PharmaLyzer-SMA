# app\controllers\app\export_controller.py
# -*- coding: utf-8 -*-
"""Export controller managing table data export to files.

This module provides a controller that coordinates table data export operations
through a file save dialog. It handles:
- File save dialog presentation with appropriate filters
- Default filename generation with correct extension
- DataFrame extraction from table view
- Export service coordination
- User feedback (success/error dialogs)

The controller follows a coordinator pattern where it:
- Manages UI interactions (file dialog, message boxes)
- Coordinates between table view and export service
- Provides consistent user experience for exports

Example:
    Basic usage in main controller::

        from app.controllers.app.export_controller import ExportController
        from app.services.export.export_options import ExportOptions

        # Create controller
        controller = ExportController()

        # Export table view to Excel
        controller.export_table_view(
            table_view=table_widget,
            file_name="analysis_results",
            options=ExportOptions(fmt="xlsx", preset="full")
        )

        # File dialog shown → User saves → Success message displayed

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from app.services.export.export_options import ExportOptions
from app.services.export.export_service import ExportService
from app.utils.qt_table_utils import table_view_to_dataframe

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Export format constants
FORMAT_EXCEL = "xlsx"
FORMAT_TSV = "tsv"

# Default filename if none provided
DEFAULT_FILENAME_TEMPLATE = "exported_file.{ext}"

# File dialog filters
FILTER_EXCEL = "Excel Files (*.xlsx)"
FILTER_TSV = "TSV Files (*.tsv)"

# Dialog titles (Turkish)
DIALOG_TITLE_SAVE = "Dosyayı Kaydet"
DIALOG_TITLE_SUCCESS = "Başarılı"
DIALOG_TITLE_ERROR = "Hata"

# Success/Error message templates (Turkish)
MESSAGE_SUCCESS_TEMPLATE = "Dosya başarıyla kaydedildi:\n{file_path}"
MESSAGE_ERROR_TEMPLATE = "Dosya kaydedilirken hata oluştu:\n{error}"


# ============================================================================
# Controller
# ============================================================================

class ExportController:
    """Controller managing table data export operations.
    
    This controller coordinates the export of table view data to files by:
    - Presenting file save dialog with format-appropriate filters
    - Generating sensible default filenames
    - Converting table view to DataFrame
    - Delegating export to ExportService
    - Displaying success/error feedback to user
    
    The controller is stateless except for the export service instance,
    making it safe to reuse across multiple export operations.
    
    Workflow:
        1. export_table_view() called with table and options
        2. File save dialog shown with appropriate filter
        3. User selects save location
        4. Table view converted to DataFrame
        5. Export service performs export
        6. Success/error message shown to user
    
    Attributes:
        export_service: Service handling actual export operations
    
    Example:
        >>> controller = ExportController()
        >>> options = ExportOptions(fmt="xlsx", preset="summary")
        >>> controller.export_table_view(table, file_name="results", options=options)
        >>> # User sees dialog → selects location → sees success message
    """

    def __init__(self, export_service: ExportService | None = None):
        """Initialize export controller.
        
        Args:
            export_service: Optional ExportService instance. If None, creates default.
        
        Note:
            Controller is stateless except for service reference,
            so single instance can handle multiple exports.
        """
        self.export_service = export_service or ExportService()
        logger.debug("ExportController initialized")

    def export_table_view(
        self,
        table_view,
        *,
        file_name: str,
        options: ExportOptions
    ) -> None:
        """Export table view data to file via save dialog.
        
        Main export method that coordinates the complete export workflow:
        1. Determines default save location (desktop)
        2. Generates default filename with correct extension
        3. Shows file save dialog with format filter
        4. Converts table view to DataFrame (if user didn't cancel)
        5. Exports DataFrame to selected file
        6. Shows success or error message
        
        Args:
            table_view: QTableView or QTableWidget to export
            file_name: Base filename (without extension) for default name
            options: Export configuration (format, preset, headers, etc.)
        
        User Interaction:
            - File save dialog shown with format-specific filter
            - Default location: Desktop
            - Default name: {file_name}.{extension}
            - Success: Information dialog with file path
            - Error: Critical dialog with error message
        
        Example:
            >>> # Export with custom filename
            >>> controller.export_table_view(
            ...     table,
            ...     file_name="pcr_analysis_2024",
            ...     options=ExportOptions(fmt="xlsx", preset="full")
            ... )
            >>> # Dialog shows: Desktop/pcr_analysis_2024.xlsx
            
            >>> # Export with minimal preset
            >>> controller.export_table_view(
            ...     table,
            ...     file_name="summary",
            ...     options=ExportOptions(fmt="tsv", preset="minimal")
            ... )
            >>> # Dialog shows: Desktop/summary.tsv
        
        Note:
            - Method returns immediately if user cancels dialog
            - Table headers always included in DataFrame extraction
            - Export options control which columns are exported
            - All exceptions caught and shown to user
        """
        logger.info(f"Export requested - Format: {options.fmt}, Preset: {options.preset}")
        
        # Determine file extension and filter
        extension = FORMAT_EXCEL if options.fmt == FORMAT_EXCEL else FORMAT_TSV
        file_filter = FILTER_EXCEL if options.fmt == FORMAT_EXCEL else FILTER_TSV
        
        logger.debug(f"Export format: {extension}, Filter: {file_filter}")

        # Generate default filename with extension
        default_name = file_name if file_name else DEFAULT_FILENAME_TEMPLATE.format(ext=extension)
        if not default_name.lower().endswith(f".{extension}"):
            default_name = f"{default_name}.{extension}"
        
        logger.debug(f"Default filename: {default_name}")

        # Get desktop path for initial location
        desktop_path = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        initial_path = f"{desktop_path}/{default_name}"
        
        logger.debug(f"Initial save path: {initial_path}")

        # Show file save dialog
        selected_path, _ = QFileDialog.getSaveFileName(
            None,
            DIALOG_TITLE_SAVE,
            initial_path,
            file_filter
        )

        # Check if user cancelled
        if not selected_path:
            logger.info("Export cancelled by user")
            return

        logger.info(f"Export path selected: {selected_path}")

        # Perform export
        try:
            # Convert table view to DataFrame
            logger.debug("Converting table view to DataFrame")
            df = table_view_to_dataframe(table_view, include_headers=True)
            logger.debug(f"DataFrame created - Shape: {df.shape}")

            # Export DataFrame to file
            logger.debug("Calling export service")
            self.export_service.export_dataframe(df, selected_path, options)
            
            # Show success message
            success_message = MESSAGE_SUCCESS_TEMPLATE.format(file_path=selected_path)
            logger.info(f"Export successful: {selected_path}")
            
            QMessageBox.information(
                None,
                DIALOG_TITLE_SUCCESS,
                success_message
            )

        except Exception as e:
            # Catch and display any export errors
            error_message = MESSAGE_ERROR_TEMPLATE.format(error=str(e))
            logger.error(f"Export failed: {e}", exc_info=True)
            
            QMessageBox.critical(
                None,
                DIALOG_TITLE_ERROR,
                error_message
            )