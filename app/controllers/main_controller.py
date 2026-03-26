# app\controllers\main_controller.py
# -*- coding: utf-8 -*-
"""Main controller orchestrating the PCR analysis application.

This module implements the central controller that coordinates all UI components,
models, services, and sub-controllers in the PCR analysis application. It follows
the Model-View-Controller pattern and implements release-grade lifecycle management.

Key Design Principles:
1. **Build Once**: Widgets and controllers created once in __init__, never rebuilt
2. **Wire Once**: Signal connections established once to prevent duplicates
3. **Reset Cheaply**: State clearing without object reconstruction
4. **Safe Shutdown**: Graceful cleanup preventing post-close UI updates
5. **Non-Blocking**: Heavy operations delegated to background threads

Architecture:
- MainController: Orchestrates all components
- MainModel: Manages data and analysis execution
- MainView: PyQt5 UI presentation layer
- Sub-controllers: Specialized controllers (table, graph, export, etc.)
- Services: Business logic and data management

Lifecycle Phases:
1. Construction: Build all components once
2. Wiring: Connect signals once
3. Operation: Handle user interactions
4. Reset: Clear state without rebuilding
5. Shutdown: Clean disconnect and resource release

Example:
    Basic usage in application initialization::

        from PyQt5.QtWidgets import QApplication
        from app.controllers.main_controller import MainController
        from app.models.main_model import MainModel
        from app.views.main_view import MainView

        app = QApplication(sys.argv)
        
        # Create view and model
        view = MainView()
        model = MainModel()
        
        # Create controller (wires everything)
        controller = MainController(view, model)
        
        # Show UI
        view.show()
        
        # Run application
        sys.exit(app.exec_())

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging
from typing import Optional

from app.controllers.app.drag_drop_controller import DragDropController
from app.controllers.app.export_controller import ExportController
from app.controllers.graph.graph_controller import GraphController
from app.controllers.interaction.interaction_controller import InteractionController
from app.controllers.table.table_controller import AppTableController
from app.controllers.well.well_edit_controller import WellEditController
from app.models.main_model import MainModel
from app.services.data_store import DataStore
from app.services.export.export_options import ExportOptions
from app.services.interaction_store import InteractionStore
from app.services.pcr_data_service import PCRDataService
from app.views.main_view import MainView
from app.views.widgets.pcr_graph_view import PCRGraphView
from app.views.widgets.pcr_plate.pcr_plate_widget import PCRPlateWidget
from app.views.widgets.regression_graph_view import RegressionGraphView

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Default well positions for control samples
DEFAULT_REFERENCE_WELL = "F12"
DEFAULT_HOMOZYGOTE_WELL = "F12"
DEFAULT_HETEROZYGOTE_WELL = "G12"
DEFAULT_NTC_WELL = "H12"

# Default UI messages (Turkish)
DEFAULT_DRAG_DROP_MESSAGE = "RDML dosyanızı sürükleyip bırakınız"
ERROR_ANALYSIS_FAILED = "Analiz başarısız oldu."
ERROR_RANGE_ADJUSTMENT = "Aralık ayarlanırken beklenmeyen bir hata oluştu."
ERROR_CARRIER_RANGE_CONSTRAINT = "Taşıyıcı aralığı belirsiz aralığından düşük olmalıdır."
ERROR_UNCERTAIN_RANGE_CONSTRAINT = "Belirsiz aralığı taşıyıcı aralığından yüksek olmalıdır."

# Export configuration
DEFAULT_EXPORT_FORMAT = "xlsx"
DEFAULT_EXPORT_PRESET = "full"

# Tolerance for floating point comparison (avoid redundant updates)
FLOAT_COMPARISON_EPSILON = 1e-12


# ============================================================================
# Main Controller
# ============================================================================

class MainController:
    """Main application controller coordinating all components.
    
    This controller implements the orchestration layer that connects:
    - UI components (views, widgets)
    - Business logic (models, services)
    - Sub-controllers (table, graph, export, etc.)
    
    Release-Grade Design Goals:
    - Avoid re-creating QObject widgets/controllers (prevents signal duplication, leaks, UI jank)
    - Wire signals exactly once
    - Provide safe close/shutdown behavior (no UI updates after closing)
    - Keep reset cheap: clear state + reset views, don't rebuild object tree
    
    The controller follows a strict lifecycle:
    1. __init__: Build all components once and wire signals once
    2. Operation: Handle user interactions through event handlers
    3. reset_state(): Clear data without rebuilding UI
    4. _on_close_requested(): Safe shutdown with cleanup
    
    Thread Safety:
        - All UI operations run in main Qt thread
        - Analysis runs in background thread (via MainModel)
        - _closing flag prevents post-shutdown UI updates
    
    Attributes:
        view: Main application view (UI)
        model: Main application model (data + analysis)
        export_controller: Export functionality controller
        drag_drop_controller: Drag-and-drop file import controller
        table_controller: Table view and interaction controller
        graph_controller: Graph visualization controller
        interaction_controller: Widget interaction wiring controller
        interaction_store: Shared interaction state store
        pcr_data_service: PCR data retrieval service
        graph_drawer: PCR amplification curve graph widget
        regression_graph_view: Regression plot widget
        plate_widget: 96-well plate visualization widget
        referans_kuyu_manager: Reference well input controller
        homozigot_manager: Homozygote control well input controller
        heterozigot_manager: Heterozygote control well input controller
        ntc_manager: NTC control well input controller
    """

    def __init__(self, view: MainView, model: MainModel):
        """Initialize controller and build all components.
        
        This method:
        1. Stores view and model references
        2. Creates export controller
        3. Initializes service instances
        4. Wires model and view signals (once)
        5. Builds all UI components (once)
        6. Resets initial state
        
        Args:
            view: Main application view instance
            model: Main application model instance
        
        Note:
            After construction, the application is fully initialized and ready
            for user interaction. All signals are connected and UI is built.
        """
        logger.info("Initializing MainController")
        
        self.view = view
        self.model = model

        # Export controller (stateless, reusable)
        self.export_controller = ExportController()

        # Sub-controllers (created once, reused)
        self.drag_drop_controller: Optional[DragDropController] = None
        self.table_controller: Optional[AppTableController] = None
        self.graph_controller: Optional[GraphController] = None
        self.interaction_controller: Optional[InteractionController] = None

        # Services (shared state)
        self.interaction_store = InteractionStore()
        self.pcr_data_service = PCRDataService()

        # View widgets (heavy QObjects created once)
        self.graph_drawer: Optional[PCRGraphView] = None
        self.regression_graph_view: Optional[RegressionGraphView] = None
        self.plate_widget: Optional[PCRPlateWidget] = None

        # Well input controllers
        self.referans_kuyu_manager: Optional[WellEditController] = None
        self.homozigot_manager: Optional[WellEditController] = None
        self.heterozigot_manager: Optional[WellEditController] = None
        self.ntc_manager: Optional[WellEditController] = None

        # Lifecycle and safety flags
        self._closing: bool = False
        self._view_wired: bool = False
        self._model_wired: bool = False
        self._components_built: bool = False

        # Wire signals once (before building components)
        logger.debug("Wiring model and view signals")
        self._wire_model_signals_once()
        self._wire_view_signals_once()

        # Build all components once
        logger.debug("Building UI components")
        self._build_components_once()
        
        # Initialize to clean state
        logger.debug("Resetting initial state")
        self.reset_state()
        
        logger.info("MainController initialization complete")

    # ========================================================================
    # Signal Wiring (ONCE)
    # ========================================================================

    def _wire_view_signals_once(self) -> None:
        """Wire view signals to controller handlers (called once).
        
        Connects UI signals to appropriate handler methods:
        - User actions (analyze, import, export, clear)
        - Configuration changes (checkboxes, range sliders)
        - Application lifecycle (close)
        
        Uses guard flag to prevent duplicate connections.
        """
        if self._view_wired:
            logger.debug("View signals already wired, skipping")
            return
        
        self._view_wired = True
        logger.debug("Wiring view signals")

        v = self.view
        v.analyze_requested.connect(self._on_analyze_requested)
        v.import_requested.connect(self._on_import_requested)
        v.export_requested.connect(self._on_export_requested)
        v.clear_requested.connect(self.reset_state)  # Reset without re-creating objects
        v.stats_toggled.connect(self._on_stats_toggled)
        v.carrier_range_changed.connect(lambda val: self._validate_and_set_range(val, "carrier"))
        v.uncertain_range_changed.connect(lambda val: self._validate_and_set_range(val, "uncertain"))
        v.close_requested.connect(self._on_close_requested)
        
        logger.debug("View signal wiring complete")

    def _wire_model_signals_once(self) -> None:
        """Wire model signals to view/controller handlers (called once).
        
        Connects model signals to appropriate handlers:
        - Colored box calculation updates
        - Analysis lifecycle (busy, progress, finished, error)
        - Analysis results (summary ready)
        
        Uses guard flag to prevent duplicate connections.
        """
        if self._model_wired:
            logger.debug("Model signals already wired, skipping")
            return
        
        self._model_wired = True
        logger.debug("Wiring model signals")

        m = self.model

        # Colored box validation updates
        m.colored_box_controller.calculationCompleted.connect(self.view.update_colored_box_widgets)

        # Analysis lifecycle signals
        m.analysis_busy.connect(self.view.set_busy)
        m.analysis_progress.connect(self._on_analysis_progress)
        m.analysis_finished.connect(self._on_async_analysis_finished)
        m.analysis_error.connect(self.view.show_warning)
        m.analysis_summary_ready.connect(self._on_analysis_summary_ready)
        
        logger.debug("Model signal wiring complete")

    def _disconnect_model_signals_safely(self) -> None:
        """Safely disconnect model signals during shutdown.
        
        Attempts to disconnect all model-to-view/controller connections.
        Uses try-except for each disconnect since Qt throws if signal
        wasn't connected. This is called during shutdown to prevent
        callbacks after UI starts closing.
        
        Note:
            Disconnection failures are silently ignored (expected behavior).
        """
        if not self._model_wired:
            logger.debug("Model signals not wired, nothing to disconnect")
            return
        
        logger.debug("Disconnecting model signals")
        
        m = self.model
        v = self.view
        
        # Disconnect colored box signal
        try:
            m.colored_box_controller.calculationCompleted.disconnect(v.update_colored_box_widgets)
        except Exception:
            pass
        
        # Disconnect analysis lifecycle signals
        try:
            m.analysis_busy.disconnect(v.set_busy)
        except Exception:
            pass
        try:
            m.analysis_progress.disconnect(self._on_analysis_progress)
        except Exception:
            pass
        try:
            m.analysis_finished.disconnect(self._on_async_analysis_finished)
        except Exception:
            pass
        try:
            m.analysis_error.disconnect(v.show_warning)
        except Exception:
            pass
        try:
            m.analysis_summary_ready.disconnect(self._on_analysis_summary_ready)
        except Exception:
            pass

        self._model_wired = False
        logger.debug("Model signal disconnection complete")

    # ========================================================================
    # Component Building (ONCE)
    # ========================================================================

    def _build_components_once(self) -> None:
        """Build all UI components and controllers once.
        
        Creates heavy QObject widgets and controllers in a specific order:
        1. Graphics widgets (PCR graph, regression graph, plate)
        2. Drag-and-drop controller
        3. Table controller
        4. Well input managers
        5. Interaction controller (wires everything together)
        
        Uses guard flag to ensure components are built exactly once.
        """
        if self._components_built:
            logger.debug("Components already built, skipping")
            return
        
        self._components_built = True
        logger.info("Building UI components")

        self._build_graphics_once()
        self._build_drag_and_drop_once()
        self._build_table_controller_once()
        self._build_well_managers_once()
        self._build_interaction_controller_once()
        
        logger.info("UI component building complete")

    def _build_graphics_once(self) -> None:
        """Create graphics widgets once.
        
        Builds heavy visualization widgets:
        - PCR amplification curve graph
        - Regression plot graph
        - 96-well plate visualization
        
        These widgets are created once and reused. State is reset via
        clear/reset methods rather than widget reconstruction.
        
        Note:
            Plate widget replacement uses replaceWidget() which may fail
            if layout structure differs. Failures are caught and logged.
        """
        logger.debug("Building graphics widgets")

        # PCR amplification curve graph
        layout_graph = self.view.ensure_graph_drawer_layout()
        self.graph_drawer = PCRGraphView(parent=self.view.ui.PCR_graph_container)
        layout_graph.addWidget(self.graph_drawer)
        logger.debug("PCR graph view created")

        # Graph controller (manages curve visibility checkboxes)
        self.graph_controller = GraphController(ui=self.view.ui, graph_view=self.graph_drawer)
        logger.debug("Graph controller created")

        # Regression plot graph
        layout_reg = self.view.ensure_regression_graph_container()
        self.regression_graph_view = RegressionGraphView(parent=self.view.ui.regration_container)
        layout_reg.addWidget(self.regression_graph_view)
        logger.debug("Regression graph view created")

        # PCR plate: create once, avoid replaceWidget on each reset
        # If UI has a placeholder widget, replace it once here
        original_plate = getattr(self.view.ui, "PCR_plate_container", None)
        if original_plate is not None and not isinstance(original_plate, PCRPlateWidget):
            logger.debug("Replacing placeholder plate widget with PCRPlateWidget")
            new_plate = PCRPlateWidget(original_plate)
            self.view.ui.PCR_plate_container = new_plate
            
            try:
                self.view.ui.verticalLayout_2.replaceWidget(original_plate, new_plate)
                logger.debug("Plate widget replaced in layout")
            except Exception as e:
                logger.warning(f"Failed to replace plate widget in layout: {e}")
            
            try:
                original_plate.deleteLater()
            except Exception as e:
                logger.warning(f"Failed to delete original plate widget: {e}")

        self.plate_widget = self.view.ui.PCR_plate_container
        logger.debug("Plate widget initialized")

    def _build_drag_and_drop_once(self) -> None:
        """Create drag-and-drop controller once.
        
        Sets up file drag-and-drop functionality for RDML import.
        Connects drop_completed signal to handle import results.
        """
        logger.debug("Building drag-and-drop controller")
        self.drag_drop_controller = DragDropController(self.view.ui.label_drag_drop_area)
        self.drag_drop_controller.drop_completed.connect(self.handle_drop_result)
        logger.debug("Drag-and-drop controller created")

    def _build_table_controller_once(self) -> None:
        """Create table controller once.
        
        Builds the main table controller that manages:
        - Table view and data display
        - Row selection and interaction
        - Column updates and formatting
        """
        logger.debug("Building table controller")
        self.table_controller = AppTableController(
            view=self.view,
            model=self.model,
            graph_drawer=self.graph_drawer,
            interaction_store=self.interaction_store
        )
        logger.debug("Table controller created")

    def _build_well_managers_once(self) -> None:
        """Create well input controllers once.
        
        Creates controllers for well position inputs:
        - Reference well (for normalization)
        - Homozygote control (F12)
        - Heterozygote control (G12)
        - NTC control (H12)
        
        Each controller manages validation and change callbacks.
        """
        logger.debug("Building well input managers")
        ui = self.view.ui

        self.referans_kuyu_manager = WellEditController(
            line_edit=ui.lineEdit_standart_kuyu,
            default_value=DEFAULT_REFERENCE_WELL,
            on_change=self.model.set_referance_well
        )

        self.homozigot_manager = WellEditController(
            line_edit=ui.line_edit_saglikli_kontrol,
            default_value=DEFAULT_HOMOZYGOTE_WELL,
            on_change=self.model.colored_box_controller.set_homozigot_line_edit
        )

        self.heterozigot_manager = WellEditController(
            line_edit=ui.line_edit_tasiyici_kontrol,
            default_value=DEFAULT_HETEROZYGOTE_WELL,
            on_change=self.model.colored_box_controller.set_heterozigot_line_edit
        )

        self.ntc_manager = WellEditController(
            line_edit=ui.line_edit_NTC_kontrol,
            default_value=DEFAULT_NTC_WELL,
            on_change=self.model.colored_box_controller.set_NTC_line_edit
        )
        
        logger.debug("Well input managers created")

    def _build_interaction_controller_once(self) -> None:
        """Create interaction controller once.
        
        Wires all interactive widgets (plate, table, graphs) to the
        shared interaction store. Skips creation if prerequisites
        (table controller, widgets) are missing.
        
        Note:
            This must be called after all widgets are created.
        """
        # Validate prerequisites
        if (
            self.table_controller is None
            or getattr(self.table_controller, "table_interaction", None) is None
            or self.graph_drawer is None
            or self.regression_graph_view is None
            or self.plate_widget is None
        ):
            logger.warning("InteractionController prerequisites missing, skipping build")
            return

        logger.debug("Building interaction controller")
        self.interaction_controller = InteractionController(
            store=self.interaction_store,
            plate_widget=self.plate_widget,
            table_interaction=self.table_controller.table_interaction,
            regression_graph_view=self.regression_graph_view,
            pcr_graph_view=self.graph_drawer,
            pcr_data_service=self.pcr_data_service
        )
        logger.debug("Interaction controller created")

    # ========================================================================
    # State Reset (Cheap, No Rebuild)
    # ========================================================================

    def reset_state(self) -> None:
        """Reset application state without rebuilding components.
        
        Release-grade reset strategy:
        - DO: Clear data, reset views, clear selections
        - DON'T: Recreate widgets, rewire signals, rebuild controllers
        
        This method:
        1. Clears interaction selections and hover state
        2. Resets model data (DataStore, file paths)
        3. Resets view widgets (colors, labels, graphs)
        4. Calls reset() on controllers that support it
        5. Resets graph controller checkboxes
        
        Performance:
            Fast - no object construction, only state clearing
        
        Thread Safety:
            Safe to call from UI thread only (modifies UI state)
        """
        if self._closing:
            logger.debug("Application closing, skipping state reset")
            return

        logger.info("Resetting application state")

        # Clear interaction state
        self.interaction_store.clear_selection()
        self.interaction_store.set_hover(None)
        self.interaction_store.clear_preview()
        logger.debug("Interaction state cleared")

        # Reset model data
        self.model.state.file_name = ""
        self.model.reset_data()
        logger.debug("Model data reset")

        # Reset view widgets and labels
        self.view.reset_box_colors()
        self.view.reset_summary_labels()
        self.view.set_analyze_enabled(False)
        self.view.set_dragdrop_label(DEFAULT_DRAG_DROP_MESSAGE)
        self._reset_graphs()
        logger.debug("View reset complete")

        # Reset controllers/services (if they expose reset API)
        self._safe_reset(self.drag_drop_controller)
        self._safe_reset(self.table_controller)
        self._safe_reset(self.referans_kuyu_manager)
        self._safe_reset(self.homozigot_manager)
        self._safe_reset(self.heterozigot_manager)
        self._safe_reset(self.ntc_manager)
        self._safe_reset(self.interaction_controller)
        logger.debug("Controllers reset")

        # Reset graph controller checkboxes
        if self.graph_controller is not None:
            try:
                self.graph_controller.reset_checkboxes()
            except Exception as e:
                logger.error(f"GraphController.reset_checkboxes failed: {e}", exc_info=True)

        logger.info("State reset complete")

    def _safe_reset(self, obj) -> None:
        """Safely call reset/clear method on object if it exists.
        
        Tries to find and call common reset methods:
        - reset()
        - clear()
        - reset_state()
        
        Failures are logged but don't propagate.
        
        Args:
            obj: Object to reset (can be None)
        """
        if obj is None:
            return
        
        for method_name in ("reset", "clear", "reset_state"):
            if hasattr(obj, method_name):
                try:
                    getattr(obj, method_name)()
                    logger.debug(f"{type(obj).__name__}.{method_name}() called")
                except Exception as e:
                    logger.error(
                        f"{type(obj).__name__}.{method_name}() failed: {e}",
                        exc_info=True
                    )
                break

    def _reset_graphs(self) -> None:
        """Reset all graph widgets to clean state.
        
        Calls reset/clear methods on:
        - Regression graph view
        - PCR graph view
        - Plate widget
        
        Each widget may have different reset method names,
        so tries common variants. Failures are logged but don't propagate.
        """
        # Reset regression graph
        if self.regression_graph_view is not None:
            try:
                self.regression_graph_view.reset()
                logger.debug("Regression graph view reset")
            except Exception as e:
                logger.error(f"RegressionGraphView.reset failed: {e}", exc_info=True)

        # Reset PCR graph view
        if self.graph_drawer is not None:
            for method_name in ("reset", "clear", "clear_plot"):
                if hasattr(self.graph_drawer, method_name):
                    try:
                        getattr(self.graph_drawer, method_name)()
                        logger.debug(f"PCR graph view {method_name}() called")
                    except Exception as e:
                        logger.error(f"PCRGraphView.{method_name} failed: {e}", exc_info=True)
                    break

        # Reset plate widget
        if self.plate_widget is not None:
            for method_name in ("reset", "clear", "reset_state"):
                if hasattr(self.plate_widget, method_name):
                    try:
                        getattr(self.plate_widget, method_name)()
                        logger.debug(f"Plate widget {method_name}() called")
                    except Exception as e:
                        logger.error(f"PCRPlateWidget.{method_name} failed: {e}", exc_info=True)
                    break

    # ========================================================================
    # Shutdown
    # ========================================================================

    def _on_close_requested(self) -> None:
        """Handle application close request with safe shutdown.
        
        Release-grade shutdown procedure:
        1. Set closing flag to prevent further UI updates
        2. Disconnect model signals to prevent callbacks
        3. Shut down model (stops analysis thread)
        
        All operations use best-effort approach - failures are logged
        but don't prevent shutdown.
        
        Thread Safety:
            Safe to call from UI thread. Model shutdown waits for
            analysis thread termination with timeout.
        """
        if self._closing:
            logger.debug("Already closing, ignoring duplicate close request")
            return
        
        self._closing = True
        logger.info("Application close requested, beginning shutdown")

        # Disconnect signals to prevent post-close callbacks
        self._disconnect_model_signals_safely()

        # Shutdown model (stops analysis thread if running)
        try:
            self.model.shutdown()
            logger.debug("Model shutdown complete")
        except Exception as e:
            logger.error(f"Model shutdown failed: {e}", exc_info=True)
        
        logger.info("Shutdown complete")

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def handle_drop_result(
        self,
        success: bool,
        rdml_path: str,
        file_name: str,
        message: str
    ) -> None:
        """Handle drag-and-drop file import result.
        
        Called when user drops an RDML file on the drag-drop area.
        Updates UI and imports data if successful.
        
        Args:
            success: True if file was valid RDML, False otherwise
            rdml_path: Full path to dropped file
            file_name: Display name of file
            message: Status message for UI display
        """
        if self._closing:
            return

        self.view.set_dragdrop_label(message)

        if success:
            logger.info(f"Drag-drop import successful: '{file_name}'")
            self.view.set_analyze_enabled(True)
            self.model.import_rdml(rdml_path)
            self.model.set_file_name_from_rdml(file_name)
            self.view.set_title_label(self.model.state.file_name)
        else:
            logger.warning(f"Drag-drop import failed: '{file_name}'")
            self.view.set_analyze_enabled(False)

    def _on_import_requested(self) -> None:
        """Handle manual RDML import via file dialog.
        
        Shows file selection dialog and imports chosen RDML file.
        Uses drag-drop controller to handle actual import logic.
        """
        if self._closing:
            return

        file_path, file_name = self.view.select_rdml_file_dialog()
        if not file_path or self.drag_drop_controller is None:
            logger.debug("Import cancelled or drag-drop controller unavailable")
            return

        logger.info(f"Manual import requested: '{file_name}'")
        self.model.set_file_name_from_rdml(file_name)
        self.view.set_title_label(self.model.state.file_name)
        self.drag_drop_controller.manual_drop(file_path, file_name)

    def _on_export_requested(self) -> None:
        """Handle export request from user.
        
        Exports current table view data to Excel file using
        export controller.
        """
        if self._closing:
            return
        if self.table_controller is None:
            logger.warning("Export requested but table controller unavailable")
            return

        logger.info("Export requested")
        self.export_controller.export_table_view(
            self.table_controller.table_widget,
            file_name=self.model.state.file_name,
            options=ExportOptions(
                fmt=DEFAULT_EXPORT_FORMAT,
                preset=DEFAULT_EXPORT_PRESET,
                include_headers=True
            )
        )

    def _on_analyze_requested(self) -> None:
        """Handle analysis start request from user.
        
        Triggers asynchronous analysis execution in model.
        Analysis runs in background thread, emits progress signals.
        """
        if self._closing:
            return
        
        logger.info("Analysis requested")
        self.model.run_analysis()

    def _on_stats_toggled(self, checked: bool) -> None:
        """Handle statistics checkbox toggle.
        
        Updates both colored box controller and model with new
        checkbox status (affects reference-free mode).
        
        Args:
            checked: True if checkbox is checked, False otherwise
        """
        if self._closing:
            return
        
        logger.debug(f"Statistics checkbox toggled: {checked}")
        self.model.colored_box_controller.set_check_box_status(bool(checked))
        self.model.set_checkbox_status(bool(checked))

    def _validate_and_set_range(self, val: float, range_type: str) -> None:
        """Validate and set carrier/uncertain range values.
        
        Implements business rules:
        - Carrier range must be < uncertain range
        - Uncertain range must be > carrier range
        
        Performance optimization:
        - Skips update if value hasn't changed (epsilon comparison)
        - Prevents redundant signals from sliders/spinboxes
        
        Args:
            val: New range value
            range_type: Either "carrier" or "uncertain"
        
        Raises:
            ValueError: If validation constraint violated
        """
        if self._closing:
            return
        if self.table_controller is None:
            logger.warning("Range change requested but table controller unavailable")
            return

        try:
            if range_type == "carrier":
                current = self.model.get_carrier_range()
                # Skip if value hasn't changed (avoid redundant updates)
                if abs(val - float(current)) < FLOAT_COMPARISON_EPSILON:
                    return
                
                if val < self.model.get_uncertain_range():
                    logger.debug(f"Setting carrier range to: {val}")
                    self.model.set_carrier_range(val)
                    self.table_controller.set_carrier_range(val)
                else:
                    raise ValueError(ERROR_CARRIER_RANGE_CONSTRAINT)

            elif range_type == "uncertain":
                current = self.model.get_uncertain_range()
                # Skip if value hasn't changed (avoid redundant updates)
                if abs(val - float(current)) < FLOAT_COMPARISON_EPSILON:
                    return
                
                if val > self.model.get_carrier_range():
                    logger.debug(f"Setting uncertain range to: {val}")
                    self.model.set_uncertain_range(val)
                    self.table_controller.set_uncertain_range(val)
                else:
                    raise ValueError(ERROR_UNCERTAIN_RANGE_CONSTRAINT)

        except ValueError as e:
            logger.warning(f"Range validation failed: {e}")
            self.view.show_warning(str(e))
        except Exception as e:
            # Release-grade: never crash UI from range change
            logger.error(f"Range validation/set failed: {e}", exc_info=True)
            self.view.show_warning(ERROR_RANGE_ADJUSTMENT)

    def _on_analysis_progress(self, percent: int, message: str) -> None:
        """Handle analysis progress updates.
        
        Currently a no-op, but can be extended to update statusbar
        or progress indicators.
        
        Args:
            percent: Progress percentage (0-100)
            message: Progress status message
        """
        if self._closing:
            return
        
        # Optional: Update statusbar/label
        # self.view.ui.statusbar.showMessage(f"{message} ({percent}%)")
        logger.debug(f"Analysis progress: {percent}% - {message}")

    def _on_async_analysis_finished(self, success: bool) -> None:
        """Handle analysis completion callback.
        
        This is the main analysis completion handler that:
        1. Checks success status
        2. Runs colored box validation
        3. Loads results into table
        4. Updates regression graph
        
        All operations are wrapped in try-except to ensure
        UI remains functional even if individual steps fail.
        
        Args:
            success: True if analysis completed successfully
        
        Note:
            Keep this callback fast - heavy operations should be
            done in background or deferred.
        """
        if self._closing:
            return

        if not success:
            logger.warning("Analysis finished with failure status")
            self.view.show_warning(ERROR_ANALYSIS_FAILED)
            return

        logger.info("Analysis finished successfully")

        # Run colored box calculation
        try:
            self.model.colored_box_controller.define_box_color()
            logger.debug("Colored box calculation complete")
        except Exception as e:
            logger.error(f"define_box_color failed: {e}", exc_info=True)

        # Load results into table
        if self.table_controller is not None:
            try:
                self.table_controller.load_csv_to_table()
                logger.debug("Results loaded to table")
            except Exception as e:
                logger.error(f"load_csv_to_table failed: {e}", exc_info=True)

        # Update regression graph
        try:
            df = DataStore.get_df_copy()
        except Exception as e:
            logger.error(f"DataStore.get_df_copy failed: {e}", exc_info=True)
            df = None

        if self.regression_graph_view is not None and df is not None:
            try:
                self.regression_graph_view.update(df)
                logger.debug("Regression graph updated")
            except Exception as e:
                logger.error(f"RegressionGraphView.update failed: {e}", exc_info=True)
        if self.plate_widget is not None:
            try:
                self.plate_widget.apply_analysis_results(df)
                logger.debug("PCR plate analysis styles updated")
            except Exception as e:
                logger.error(f"PCRPlateWidget.apply_analysis_results failed: {e}", exc_info=True)
    def _on_analysis_summary_ready(self, summary) -> None:
        """Handle analysis summary availability.
        
        Updates view with summary statistics (healthy, carrier,
        uncertain counts, etc.).
        
        Args:
            summary: AnalysisSummary object with result statistics
        """
        if self._closing:
            return
        
        try:
            self.view.update_summary_labels(summary)
            logger.debug("Summary labels updated")
        except Exception as e:
            logger.error(f"update_summary_labels failed: {e}", exc_info=True)