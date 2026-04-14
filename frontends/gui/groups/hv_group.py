from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.widgets.status_utils import set_status_badge


class HVGroup(CollapsibleGroupBox):
    ACTIVE_THRESHOLD_V = 0.001

    def __init__(self, controller, log_callback, expanded: bool = False):
        self.controller = controller
        self.log_callback = log_callback

        self.hv_voltage_edit = None
        self.set_hv_btn = None
        self.stop_hv_btn = None

        self.hv_status_label = None
        self.hv_voltage_label = None

        content = self._build_content()
        super().__init__("HV / Bias", content, expanded=expanded)

        self.refresh_ui_enabled_state()
        self.set_unknown()

    def _build_content(self) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("Control voltage [V]:"), 0, 0)

        self.hv_voltage_edit = QLineEdit("0.0")
        self.hv_voltage_edit.setPlaceholderText("0.0 .. 1.2")
        grid.addWidget(self.hv_voltage_edit, 0, 1)

        self.set_hv_btn = QPushButton("Set HV")
        self.stop_hv_btn = QPushButton("Stop HV")

        self.set_hv_btn.clicked.connect(self._set_hv_voltage)
        self.stop_hv_btn.clicked.connect(self._stop_hv)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        buttons_row.addWidget(self.set_hv_btn, 1)
        buttons_row.addWidget(self.stop_hv_btn, 1)
        grid.addLayout(buttons_row, 1, 0, 1, 2)

        grid.addWidget(QLabel("Status:"), 2, 0)
        self.hv_status_label = QLabel("Unknown")
        self.hv_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(0)
        status_row.addWidget(self.hv_status_label)
        status_row.addStretch()
        grid.addLayout(status_row, 2, 1)

        grid.addWidget(QLabel("Readback V:"), 3, 0)
        self.hv_voltage_label = QLabel("—")
        grid.addWidget(self.hv_voltage_label, 3, 1)

        layout.addLayout(grid)

        return container

    def _append_log(self, text: str):
        if self.log_callback is not None:
            self.log_callback(text)

    def refresh_ui_enabled_state(self):
        device_open = self.controller.get_controller_status_snapshot().device_open

        for widget in (
            self.hv_voltage_edit,
            self.set_hv_btn,
            self.stop_hv_btn,
        ):
            if widget is not None:
                widget.setEnabled(device_open)

    def set_unknown(self):
        set_status_badge(self.hv_status_label, "Unknown", "gray")
        self.hv_voltage_label.setText("—")

    def refresh_status_from_voltage(self, voltage_v: float):
        if voltage_v > self.ACTIVE_THRESHOLD_V:
            set_status_badge(self.hv_status_label, "Active", "green")
        else:
            set_status_badge(self.hv_status_label, "Stopped", "red")

        self.hv_voltage_label.setText(f"{voltage_v:.6f} V")

    def refresh_after_connection_change(self):
        self.refresh_ui_enabled_state()

        if not self.controller.get_controller_status_snapshot().device_open:
            self.set_unknown()

    def refresh_passive(self):
        snapshot = self.controller.get_controller_status_snapshot()
        if not snapshot.device_open:
            self.set_unknown()
            return

        try:
            voltage = self.controller.get_hv_voltage()
            self.refresh_status_from_voltage(voltage)
        except Exception:
            # refresh passivo: niente spam nel log
            pass

    def _set_hv_voltage(self):
        try:
            voltage = float(self.hv_voltage_edit.text().strip())
            actual = self.controller.set_hv_voltage(voltage)
            self.refresh_status_from_voltage(actual)
            self._append_log(f"HV control voltage set to {actual:.6f} V.")
        except Exception as e:
            self._append_log(f"Set HV error: {e}")

    def _stop_hv(self):
        try:
            self.controller.stop_hv(force_zero=True)
            actual = self.controller.get_hv_voltage()
            self.refresh_status_from_voltage(actual)
            self._append_log("HV control output stopped and forced to 0 V.")
        except Exception as e:
            self._append_log(f"Stop HV error: {e}")
