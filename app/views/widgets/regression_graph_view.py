# app\views\widgets\regression_graph_view.py

from __future__ import annotations
from PyQt5.QtCore import Qt
import pandas as pd
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

from app.services.regression_plot_service import RegressionPlotService
from app.views.plotting.pyqtgraph_regression_renderer import PyqtgraphRegressionRenderer
from app.views.plotting.regression.styles import RegressionPlotStyle
from app.services.interaction_store import InteractionStore

class RegressionGraphView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)

        self._style = RegressionPlotStyle()
        self.plot_widget = pg.PlotWidget()
        
        # Taşmayı önleyen kritik ayarlar
        self.plot_widget.setMinimumSize(0, 0)
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.plot_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.plot_item = self.plot_widget.getPlotItem()
        self._hover_text = pg.TextItem(anchor=(0, 1), color=(255, 255, 255))
        self._hover_text.setZValue(999)
        self._hover_text.hide()
        self.plot_item.addItem(self._hover_text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot_widget)

        self._renderer = PyqtgraphRegressionRenderer(style=self._style)
        self._store: InteractionStore | None = None
        self._last_data = None
        self._view_box = self.plot_item.getViewBox()

        self._view_box.sigRangeChanged.connect(self._on_range_changed)

        self._apply_theme_and_setup()

    def set_interaction_store(self, store: InteractionStore) -> None:
        if self._store is not None:
            try:
                self._store.selectedChanged.disconnect(self._on_store_selection_changed)
                self._store.hoverChanged.disconnect(self._on_store_hover_changed)
            except Exception:
                pass

        self._store = store
        self._store.selectedChanged.connect(self._on_store_selection_changed)
        self._store.hoverChanged.connect(self._on_store_hover_changed)
        self._on_store_selection_changed(self._store.selected_wells)
        self._on_store_hover_changed(self._store.hover_well)

    def _apply_theme_and_setup(self) -> None:
        self.plot_widget.setBackground(self._style.widget_background_rgb)
        view_box = self._view_box
        view_box.setBackgroundColor(self._style.background_hex)

        view_box.setMouseEnabled(x=True, y=True)

        view_box.setLimits(
            xMin=0,
            xMax=1.1,
            yMin=0,
            yMax=1.1,
            maxXRange=1.1,
            maxYRange=1.1,
        )
        self.plot_item.setRange(xRange=(0, 1.1), yRange=(0, 1.1), padding=0.0)
        self.plot_item.setDefaultPadding(0.0)

        self.plot_item.showGrid(x=True, y=True, alpha=self._style.grid_alpha)


        for name in ("bottom", "left"):
            ax = self.plot_item.getAxis(name)
            ax.setPen(pg.mkPen(self._style.grid_color_rgb, width=1))
            ax.setTextPen(pg.mkPen(self._style.axis_text_rgb))
            if hasattr(ax, "setTickPen"):
                ax.setTickPen(pg.mkPen(self._style.grid_color_rgb, width=1))

        self.plot_item.setLabel("bottom", " ")
        self.plot_item.setLabel("left", " ")

        if self.plot_item.legend is None:
            self.plot_item.addLegend(offset=(10, 10))

    def update(self, df: pd.DataFrame):
        data = RegressionPlotService.build(df)
        self._last_data = data
        self._renderer.render(
            self.plot_item,
            data,
            enable_hover=True,
            hover_text_item=self._hover_text,
            interaction_store=self._store,
        )
        if self._store:
            self._renderer.update_styles(self._store.selected_wells, self._store.hover_well)
        
        self._enforce_max_zoom_out()

    def reset(self):
        self._renderer.detach_hover()
        self.plot_item.clear()
        self.plot_item.addItem(self._hover_text)
        self._hover_text.hide()
        self._apply_theme_and_setup()
    def _enforce_max_zoom_out(self) -> None:
        """Görünümün 0..1.1 aralığında kalmasını ve daha fazla uzaklaşmamasını sağlar."""
        x_range = self.plot_item.getAxis("bottom").range
        y_range = self.plot_item.getAxis("left").range
        self._set_range_clamped(x_range, y_range)

    def _on_range_changed(self, view_box, ranges) -> None:
        """Range değişikliklerini dinleyip sınırlar dışına çıkmayı engeller."""
        x_range, y_range = ranges
        self._set_range_clamped(x_range, y_range)

    def _set_range_clamped(self, x_range, y_range) -> None:
        x0, x1 = self._clamp_range(x_range)
        y0, y1 = self._clamp_range(y_range)
        # Range update'ı yeniden sinyal yaymasın diye sinyalleri geçici kapat
        self._view_box.blockSignals(True)
        self.plot_item.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0.0, disableAutoRange=True)
        self._view_box.blockSignals(False)

    @staticmethod
    def _clamp_range(rng):
        min_bound, max_bound = 0.0, 1.1
        max_span = max_bound - min_bound
        min_span = 1e-6
        span = max(rng[1] - rng[0], 0.0)
        span = min(span, max_span)
        span = max(span, min_span)
        start = max(min(rng[0], max_bound - span), min_bound)
        end = start + span
        if end > max_bound:
            end = max_bound
            start = end - span
        return start, end

    def _on_store_selection_changed(self, wells):
        self._renderer.update_styles(wells, self._store.hover_well if self._store else None)

    def _on_store_hover_changed(self, well):
        self._renderer.update_styles(self._store.selected_wells if self._store else set(), well)