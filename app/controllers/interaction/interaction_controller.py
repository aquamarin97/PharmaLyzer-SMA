# app\controllers\interaction\interaction_controller.py
# -*- coding: utf-8 -*-
"""Interaction controller coordinating widget interactions through shared store.

This module provides a lightweight wiring layer that connects UI widgets to a
shared InteractionStore. It does not contain state or business logic - it merely
establishes the connections between widgets and the interaction store.

The controller follows a hub-and-spoke pattern where:
- InteractionStore acts as the central hub
- Widgets (plate, table, graphs) are connected as spokes
- All interaction state flows through the central store
- Widgets communicate indirectly via store updates

This architecture provides:
- Decoupled widget communication
- Centralized interaction state management
- Easy testing (mock store to test widgets)
- Clear data flow (all through store)

Example:
    Basic usage in application setup::

        from app.controllers.interaction.interaction_controller import InteractionController
        from app.services.interaction_store import InteractionStore
        from app.services.pcr_data_service import PCRDataService

        # Create shared store
        store = InteractionStore()
        data_service = PCRDataService()

        # Create widgets (plate, table, graphs)
        plate_widget = PCRPlateWidget()
        table_interaction = TableInteractionController(...)
        regression_view = RegressionGraphView()
        pcr_view = PCRGraphView()

        # Wire everything together
        interaction_controller = InteractionController(
            store,
            plate_widget=plate_widget,
            table_interaction=table_interaction,
            regression_graph_view=regression_view,
            pcr_graph_view=pcr_view,
            pcr_data_service=data_service
        )

        # Now all widgets communicate via store:
        # plate_widget clicks -> store updates -> graphs/table respond

Author: Pharmalyzer Development Team
License: Proprietary
"""

from __future__ import annotations

import logging

from app.controllers.table.table_interaction_controller import TableInteractionController
from app.services.interaction_store import InteractionStore
from app.services.pcr_data_service import PCRDataService
from app.views.widgets.pcr_graph_view import PCRGraphView
from app.views.widgets.pcr_plate.pcr_plate_widget import PCRPlateWidget
from app.views.widgets.regression_graph_view import RegressionGraphView

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# Controller
# ============================================================================

class InteractionController:
    """Lightweight wiring controller connecting widgets to interaction store.
    
    This controller establishes connections between UI widgets and the shared
    InteractionStore without implementing any business logic. It follows the
    dependency injection pattern where all dependencies are provided at construction.
    
    The wiring process:
    1. Receives all widget instances and store
    2. Calls set_interaction_store() on each widget
    3. Widgets connect to store signals internally
    4. Interaction state flows through store
    
    Attributes:
        store: Shared interaction state store
        plate_widget: PCR plate visualization widget
        table_interaction: Table interaction controller
        regression_graph_view: Regression plot visualization
        pcr_graph_view: PCR amplification curve graph
        pcr_data_service: Service for PCR data retrieval
    
    Design Notes:
        - No state management (state lives in store)
        - No business logic (widgets handle their own logic)
        - Single responsibility: wire widgets to store
        - Initialization only (no runtime methods)
    """

    def __init__(
        self,
        store: InteractionStore,
        *,
        plate_widget: PCRPlateWidget,
        table_interaction: TableInteractionController,
        regression_graph_view: RegressionGraphView,
        pcr_graph_view: PCRGraphView,
        pcr_data_service: PCRDataService
    ):
        """Initialize controller and wire all widgets to interaction store.
        
        Args:
            store: Shared interaction store for all widgets
            plate_widget: PCR plate widget (96-well visualization)
            table_interaction: Controller managing table selection interactions
            regression_graph_view: Widget displaying regression analysis plot
            pcr_graph_view: Widget displaying PCR amplification curves
            pcr_data_service: Service providing PCR data to graphs
        
        Note:
            All wiring happens in __init__ via _wire() method. After construction,
            widgets are fully connected and ready to interact through the store.
        
        Example:
            >>> store = InteractionStore()
            >>> controller = InteractionController(
            ...     store,
            ...     plate_widget=plate,
            ...     table_interaction=table_ctrl,
            ...     regression_graph_view=reg_view,
            ...     pcr_graph_view=pcr_view,
            ...     pcr_data_service=data_svc
            ... )
            >>> # Widgets are now wired and communicating via store
        """
        self.store = store
        self.plate_widget = plate_widget
        self.table_interaction = table_interaction
        self.regression_graph_view = regression_graph_view
        self.pcr_graph_view = pcr_graph_view
        self.pcr_data_service = pcr_data_service

        logger.info("InteractionController initializing widget wiring")
        self._wire()
        logger.debug("InteractionController wiring complete")

    def _wire(self) -> None:
        """Wire all widgets to the interaction store.
        
        Calls set_interaction_store() on each widget, passing the shared store
        and any additional dependencies. Widgets will internally connect to
        store signals and start responding to interaction events.
        
        Wiring Order:
            1. Plate widget - visualizes well selection
            2. Table interaction - handles table row selection
            3. Regression graph - displays selected well on plot
            4. PCR graph - shows amplification curves for selected wells
        
        Note:
            Order doesn't matter functionally (all use signals), but this order
            follows the UI flow: plate → table → graphs.
        """
        logger.debug("Wiring plate widget to interaction store")
        self.plate_widget.set_interaction_store(self.store)

        logger.debug("Wiring table interaction controller to interaction store")
        self.table_interaction.set_interaction_store(self.store)

        logger.debug("Wiring regression graph view to interaction store")
        self.regression_graph_view.set_interaction_store(self.store)

        logger.debug("Wiring PCR graph view to interaction store with data service")
        self.pcr_graph_view.set_interaction_store(self.store, self.pcr_data_service)