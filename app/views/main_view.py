# app\views\main_view.py
from __future__ import annotations

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog

from app.views.ui.ui import Ui_MainWindow
from app.services.analysis_summary import AnalysisSummary


class MainView(QMainWindow):
    """
    View: UI kurar + UI günceller.
    Controller'ı bilmez. Eventleri Qt sinyalleri ile dışarı verir.
    """

    analyze_requested = QtCore.pyqtSignal()
    import_requested = QtCore.pyqtSignal()
    export_requested = QtCore.pyqtSignal()
    clear_requested = QtCore.pyqtSignal()
    stats_toggled = QtCore.pyqtSignal(bool)
    carrier_range_changed = QtCore.pyqtSignal(float)
    uncertain_range_changed = QtCore.pyqtSignal(float)
    close_requested = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._enabled_state = {
            "analyze": True,
            "import": True,
            "export": True,
            "clear": True,
        }

        self._wire_ui_signals()

    def _wire_ui_signals(self) -> None:
        ui = self.ui
        ui.pushButton_analiz_et.clicked.connect(self.analyze_requested)
        ui.pushButton_iceaktar.clicked.connect(self.import_requested)
        ui.pushButton_disaaktar.clicked.connect(self.export_requested)
        ui.pushButton_temizle.clicked.connect(self.clear_requested)

        ui.checkBox_istatistik.toggled.connect(self.stats_toggled)
        ui.doubleSpinBox_tasiyici.valueChanged.connect(self.carrier_range_changed)
        ui.doubleSpinBox_belirsiz.valueChanged.connect(self.uncertain_range_changed)

    # ---- UI helpers ----
    def set_title_label(self, text: str) -> None:
        self.ui.label_title.setText(text)

    def set_dragdrop_label(self, text: str) -> None:
        self.ui.label_drag_drop_area.setText(text)

    def set_analyze_enabled(self, enabled: bool) -> None:
        self._enabled_state["analyze"] = bool(enabled)
        self.ui.pushButton_analiz_et.setEnabled(bool(enabled))

    def set_busy(self, busy: bool) -> None:
        ui = self.ui
        if busy:
            ui.pushButton_analiz_et.setEnabled(False)
            ui.pushButton_iceaktar.setEnabled(False)
            ui.pushButton_disaaktar.setEnabled(False)
            ui.pushButton_temizle.setEnabled(False)
            return

        # ✅ busy bitince eski state'lere dön
        ui.pushButton_analiz_et.setEnabled(self._enabled_state["analyze"])
        ui.pushButton_iceaktar.setEnabled(self._enabled_state["import"])
        ui.pushButton_disaaktar.setEnabled(self._enabled_state["export"])
        ui.pushButton_temizle.setEnabled(self._enabled_state["clear"])

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # ✅ Controller/Model shutdown tetiklemek için
        self.close_requested.emit()
        super().closeEvent(event)

    def show_warning(self, message: str, title: str = "Hata") -> None:
        QMessageBox.warning(self, title, message)

    def show_error(self, message: str, title: str = "Hata") -> None:
        QMessageBox.critical(self, title, message)

    # ---- RDML selection ----
    def select_rdml_file_dialog(self) -> tuple[str, str]:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "RDML Dosyası Seç",
            "",
            "RDML Dosyaları (*.rdml);;Tüm Dosyalar (*)",
        )
        if not file_path:
            return "", ""
        # platform bağımsız:
        file_name = QtCore.QFileInfo(file_path).fileName()
        return file_path, file_name

    # ---- Colored boxes ----
    def set_widget_color(self, widget: QtWidgets.QWidget, color_code: str) -> None:
        if not isinstance(color_code, str) or not color_code.startswith("#"):
            raise ValueError(f"Geçersiz renk kodu: {color_code}")

        widget.setStyleSheet(
            f"""
            background-color: {color_code};
            border: 2px solid #333333;
            border-radius: 5px;
            """
        )

    def reset_box_colors(self) -> None:
        init_color = "#87CEEB"
        self.set_widget_color(self.ui.saglikli_kontrol_color_box, init_color)
        self.set_widget_color(self.ui.tasiyici_kontrol_color_box, init_color)
        self.set_widget_color(self.ui.ntc_kontrol_color_box, init_color)

    def reset_summary_labels(self) -> None:
        self.update_summary_labels(AnalysisSummary())  # hepsini "" yapar

    def update_colored_box_widgets(self, result: list) -> None:
        if len(result) != 3:
            # UI katmanında print yerine mesaj/log daha iyi ama min:
            return
        colors = ["#00FF00" if res else "#FF0000" for res in result]
        self.set_widget_color(self.ui.saglikli_kontrol_color_box, colors[0])
        self.set_widget_color(self.ui.tasiyici_kontrol_color_box, colors[1])
        self.set_widget_color(self.ui.ntc_kontrol_color_box, colors[2])

    # ---- Graph container setup ----
    def ensure_graph_drawer_layout(self) -> QtWidgets.QVBoxLayout:
        layout = self.ui.PCR_graph_container.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(self.ui.PCR_graph_container)
            self.ui.PCR_graph_container.setLayout(layout)

        # önceki widgetları temizle
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            w = item.widget() if item else None
            if w:
                w.deleteLater()

        layout.setContentsMargins(10, 10, 10, 10)
        return layout

    def update_summary_labels(self, s) -> None:
        if s is None:
            return
        ui = self.ui
        ui.total_sample_count_label.setText(str(s.analyzed_well_count))
        ui.safezone_count_label.setText(str(s.safezone_count))
        ui.riskyarea_count_label.setText(str(s.riskyarea_count))
        ui.healthy_count_label.setText(str(s.healthy_count))
        ui.carry_count_label.setText(str(s.carrier_count))
        ui.uncertain_count_label.setText(str(s.uncertain_count))
        ui.healthy_avg.setText(str(s.healthy_avg))
        ui.std.setText(str(s.std))
        ui.cv.setText(str(s.cv))
    
    def ensure_regression_graph_container(self):
        layout = self.ui.regration_container.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(self.ui.regration_container)
            self.ui.regration_container.setLayout(layout)

        for i in reversed(range(layout.count())):
            w = layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        layout.setContentsMargins(10, 10, 10, 10)
        return layout