from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.widgets.status_utils import set_status_badge


class SuppliesGroup(CollapsibleGroupBox):
    def __init__(self, controller, log_callback, expanded: bool = False):
        self.controller = controller
        self.log_callback = log_callback

        self.read_supplies_btn = None
        self.disable_all_supplies_btn = None

        self.pos_supply_voltage_edit = None
        self.enable_pos_supply_btn = None
        self.disable_pos_supply_btn = None
        self.pos_supply_status_label = None
        self.pos_supply_voltage_label = None
        self.pos_supply_current_label = None

        self.neg_supply_voltage_edit = None
        self.enable_neg_supply_btn = None
        self.disable_neg_supply_btn = None
        self.neg_supply_status_label = None
        self.neg_supply_voltage_label = None
        self.neg_supply_current_label = None

        self.supplies_master_label = None

        content = self._build_content()
        super().__init__("Supplies", content, expanded=expanded)

        self.refresh_ui_enabled_state()
        self.set_unknown()

    def _build_content(self) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.read_supplies_btn = QPushButton("Read status")
        self.disable_all_supplies_btn = QPushButton("Disable all")

        self.read_supplies_btn.clicked.connect(self._read_supplies_status)
        self.disable_all_supplies_btn.clicked.connect(self._disable_all_supplies)

        top_row.addWidget(self.read_supplies_btn, 1)
        top_row.addWidget(self.disable_all_supplies_btn, 1)
        layout.addLayout(top_row)

        pos_box = QGroupBox("+ Supply")
        pos_grid = QGridLayout(pos_box)
        pos_grid.setHorizontalSpacing(10)
        pos_grid.setVerticalSpacing(8)
        pos_grid.setColumnStretch(0, 0)
        pos_grid.setColumnStretch(1, 1)

        pos_grid.addWidget(QLabel("Voltage setpoint [V]:"), 0, 0)

        self.pos_supply_voltage_edit = QLineEdit("5.0")
        self.pos_supply_voltage_edit.setPlaceholderText("e.g. 5.0")
        pos_grid.addWidget(self.pos_supply_voltage_edit, 0, 1)

        self.enable_pos_supply_btn = QPushButton("Enable +")
        self.disable_pos_supply_btn = QPushButton("Disable +")

        self.enable_pos_supply_btn.clicked.connect(self._enable_positive_supply)
        self.disable_pos_supply_btn.clicked.connect(self._disable_positive_supply)

        pos_buttons_row = QHBoxLayout()
        pos_buttons_row.setSpacing(8)
        pos_buttons_row.addWidget(self.enable_pos_supply_btn, 1)
        pos_buttons_row.addWidget(self.disable_pos_supply_btn, 1)
        pos_grid.addLayout(pos_buttons_row, 1, 0, 1, 2)

        pos_grid.addWidget(QLabel("Status:"), 2, 0)
        self.pos_supply_status_label = QLabel("Unknown")
        self.pos_supply_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pos_status_row = QHBoxLayout()
        pos_status_row.setContentsMargins(0, 0, 0, 0)
        pos_status_row.setSpacing(0)
        pos_status_row.addWidget(self.pos_supply_status_label)
        pos_status_row.addStretch()

        pos_grid.addLayout(pos_status_row, 2, 1)

        pos_grid.addWidget(QLabel("Readback V:"), 3, 0)
        self.pos_supply_voltage_label = QLabel("—")
        pos_grid.addWidget(self.pos_supply_voltage_label, 3, 1)

        layout.addWidget(pos_box)

        neg_box = QGroupBox("- Supply")
        neg_grid = QGridLayout(neg_box)
        neg_grid.setHorizontalSpacing(10)
        neg_grid.setVerticalSpacing(8)
        neg_grid.setColumnStretch(0, 0)
        neg_grid.setColumnStretch(1, 1)

        neg_grid.addWidget(QLabel("Voltage magnitude [V]:"), 0, 0)

        self.neg_supply_voltage_edit = QLineEdit("-5.0")
        self.neg_supply_voltage_edit.setPlaceholderText("e.g. -5.0")
        neg_grid.addWidget(self.neg_supply_voltage_edit, 0, 1)

        self.enable_neg_supply_btn = QPushButton("Enable -")
        self.disable_neg_supply_btn = QPushButton("Disable -")

        self.enable_neg_supply_btn.clicked.connect(self._enable_negative_supply)
        self.disable_neg_supply_btn.clicked.connect(self._disable_negative_supply)

        neg_buttons_row = QHBoxLayout()
        neg_buttons_row.setSpacing(8)
        neg_buttons_row.addWidget(self.enable_neg_supply_btn, 1)
        neg_buttons_row.addWidget(self.disable_neg_supply_btn, 1)
        neg_grid.addLayout(neg_buttons_row, 1, 0, 1, 2)

        neg_grid.addWidget(QLabel("Status:"), 2, 0)
        self.neg_supply_status_label = QLabel("Unknown")
        self.neg_supply_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        neg_status_row = QHBoxLayout()
        neg_status_row.setContentsMargins(0, 0, 0, 0)
        neg_status_row.setSpacing(0)
        neg_status_row.addWidget(self.neg_supply_status_label)
        neg_status_row.addStretch()

        neg_grid.addLayout(neg_status_row, 2, 1)

        neg_grid.addWidget(QLabel("Readback V:"), 3, 0)
        self.neg_supply_voltage_label = QLabel("—")
        neg_grid.addWidget(self.neg_supply_voltage_label, 3, 1)

        layout.addWidget(neg_box)

        master_row = QHBoxLayout()
        master_row.setSpacing(8)
        master_row.addWidget(QLabel("Master:"))

        self.supplies_master_label = QLabel("Unknown")
        self.supplies_master_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        master_row.addWidget(self.supplies_master_label)
        master_row.addStretch()

        layout.addLayout(master_row)

        return container

    def _append_log(self, text: str):
        if self.log_callback is not None:
            self.log_callback(text)

    def refresh_ui_enabled_state(self):
        device_open = self.controller.get_controller_status_snapshot().device_open

        for widget in (
            self.read_supplies_btn,
            self.disable_all_supplies_btn,
            self.pos_supply_voltage_edit,
            self.enable_pos_supply_btn,
            self.disable_pos_supply_btn,
            self.neg_supply_voltage_edit,
            self.enable_neg_supply_btn,
            self.disable_neg_supply_btn,
        ):
            if widget is not None:
                widget.setEnabled(device_open)

    def set_unknown(self):
        set_status_badge(self.pos_supply_status_label, "Unknown", "gray")
        set_status_badge(self.neg_supply_status_label, "Unknown", "gray")
        set_status_badge(self.supplies_master_label, "Unknown", "gray")

        self.pos_supply_voltage_label.setText("—")
        self.neg_supply_voltage_label.setText("—")

    def refresh_status_from_dict(self, status: dict):
        if status["positive"]["enabled"]:
            set_status_badge(self.pos_supply_status_label, "Enabled", "green")
        else:
            set_status_badge(self.pos_supply_status_label, "Disabled", "red")

        if status["negative"]["enabled"]:
            set_status_badge(self.neg_supply_status_label, "Enabled", "green")
        else:
            set_status_badge(self.neg_supply_status_label, "Disabled", "red")

        if status["master_enable"]:
            set_status_badge(self.supplies_master_label, "On", "green")
        else:
            set_status_badge(self.supplies_master_label, "Off", "red")

        self.pos_supply_voltage_label.setText(f"{status['positive']['voltage']:.6f} V")
        self.neg_supply_voltage_label.setText(f"{status['negative']['voltage']:.6f} V")

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
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
        except Exception:
            # refresh passivo: non spammiamo il log a ogni tick se qualcosa va storto
            pass

    def _read_supplies_status(self):
        try:
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
            self._append_log("Supplies status updated.")
        except Exception as e:
            self._append_log(f"Read supplies status error: {e}")

    def _enable_positive_supply(self):
        try:
            voltage = float(self.pos_supply_voltage_edit.text().strip())
            self.controller.enable_positive_supply(voltage)
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
            self._append_log(f"Positive supply enabled at {voltage:.6f} V.")
        except Exception as e:
            self._append_log(f"Enable positive supply error: {e}")

    def _disable_positive_supply(self):
        try:
            self.controller.disable_positive_supply()
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
            self._append_log("Positive supply disabled.")
        except Exception as e:
            self._append_log(f"Disable positive supply error: {e}")

    def _enable_negative_supply(self):
        try:
            voltage = float(self.neg_supply_voltage_edit.text().strip())
            self.controller.enable_negative_supply(voltage)
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
            self._append_log(f"Negative supply enabled at {voltage:.6f} V.")
        except Exception as e:
            self._append_log(f"Enable negative supply error: {e}")

    def _disable_negative_supply(self):
        try:
            self.controller.disable_negative_supply()
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
            self._append_log("Negative supply disabled.")
        except Exception as e:
            self._append_log(f"Disable negative supply error: {e}")

    def _disable_all_supplies(self):
        try:
            self.controller.disable_all_supplies()
            status = self.controller.read_supply_status()
            self.refresh_status_from_dict(status)
            self._append_log("All supplies disabled.")
        except Exception as e:
            self._append_log(f"Disable all supplies error: {e}")
