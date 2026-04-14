from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from frontends.gui.widgets.status_utils import set_status_badge


class ConnectionGroup(QGroupBox):
    def __init__(self, controller, log_callback):
        super().__init__("Connection")

        self.controller = controller
        self.log_callback = log_callback

        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")

        self.device_open_label = QLabel("Disconnected")
        self.device_open_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.connection_state_label = QLabel("Unknown")
        self.connection_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Polling controls
        self.polling_enabled_checkbox = QCheckBox("Enable polling controls")
        self.polling_period_edit = QLineEdit("1.0")
        self.polling_state_label = QLabel("Stopped")
        self.polling_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_polling_btn = QPushButton("Start polling")
        self.stop_polling_btn = QPushButton("Stop polling")

        self._build_ui()
        self._connect_signals()
        self.refresh_status()
        self.refresh_polling_controls()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(self.connect_btn)
        row.addWidget(self.disconnect_btn)
        layout.addLayout(row)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Device:"))
        device_row.addWidget(self.device_open_label)
        device_row.addStretch()
        layout.addLayout(device_row)

        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("Mode:"))
        state_row.addWidget(self.connection_state_label)
        state_row.addStretch()
        layout.addLayout(state_row)

        polling_box = QGroupBox("Polling")
        polling_grid = QGridLayout(polling_box)
        polling_grid.setHorizontalSpacing(10)
        polling_grid.setVerticalSpacing(8)

        polling_grid.addWidget(self.polling_enabled_checkbox, 0, 0, 1, 2)

        polling_grid.addWidget(QLabel("Period [s]:"), 1, 0)
        self.polling_period_edit.setPlaceholderText("minimum 1.0")
        polling_grid.addWidget(self.polling_period_edit, 1, 1)

        polling_grid.addWidget(QLabel("Status:"), 2, 0)

        polling_status_row = QHBoxLayout()
        polling_status_row.setContentsMargins(0, 0, 0, 0)
        polling_status_row.setSpacing(0)
        polling_status_row.addWidget(self.polling_state_label)
        polling_status_row.addStretch()
        polling_grid.addLayout(polling_status_row, 2, 1)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.start_polling_btn, 1)
        buttons_row.addWidget(self.stop_polling_btn, 1)
        polling_grid.addLayout(buttons_row, 3, 0, 1, 2)

        layout.addWidget(polling_box)

    def _connect_signals(self):
        self.connect_btn.clicked.connect(self._connect_device)
        self.disconnect_btn.clicked.connect(self._disconnect_device)

        self.start_polling_btn.clicked.connect(self._start_polling)
        self.stop_polling_btn.clicked.connect(self._stop_polling)
        self.polling_enabled_checkbox.toggled.connect(self.refresh_polling_controls)
        self.polling_period_edit.editingFinished.connect(
            self._apply_polling_period_from_ui
        )

    def _append_log(self, text: str):
        if self.log_callback is not None:
            self.log_callback(text)

    @staticmethod
    def _format_app_state_text(state_value: str) -> str:
        return state_value.replace("_", " ").title()

    def _find_main_window(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "start_polling") and hasattr(parent, "stop_polling"):
                return parent
            parent = parent.parent()
        return None

    def refresh_status(self):
        snapshot = self.controller.get_controller_status_snapshot()

        if snapshot.device_open:
            set_status_badge(self.device_open_label, "Connected", "green")
        else:
            set_status_badge(self.device_open_label, "Disconnected", "red")

        state_text = self._format_app_state_text(snapshot.state.value)

        if snapshot.state.value == "disconnected":
            state_kind = "red"
        elif snapshot.state.value == "idle":
            state_kind = "green"
        elif snapshot.state.value == "scope_configured":
            state_kind = "blue"
        elif snapshot.state.value == "mca_running":
            state_kind = "yellow"
        else:
            state_kind = "gray"

        set_status_badge(self.connection_state_label, state_text, state_kind)

        self.connect_btn.setEnabled(not snapshot.device_open)
        self.disconnect_btn.setEnabled(snapshot.device_open)

    def refresh_polling_controls(self):
        main_window = self._find_main_window()
        snapshot = self.controller.get_controller_status_snapshot()

        controls_enabled = self.polling_enabled_checkbox.isChecked()
        device_open = snapshot.device_open
        polling_active = (
            main_window.is_polling_active() if main_window is not None else False
        )

        self.polling_period_edit.setEnabled(controls_enabled)
        self.start_polling_btn.setEnabled(
            controls_enabled and device_open and not polling_active
        )
        self.stop_polling_btn.setEnabled(controls_enabled and polling_active)

        if main_window is not None:
            current_interval = main_window.get_poll_interval_s()
            self.polling_period_edit.setText(
                f"{current_interval:.3f}".rstrip("0").rstrip(".")
            )

        if polling_active:
            set_status_badge(self.polling_state_label, "Running", "green")
        else:
            set_status_badge(self.polling_state_label, "Stopped", "gray")

    def _apply_polling_period_from_ui(self):
        main_window = self._find_main_window()
        if main_window is None:
            return

        raw = self.polling_period_edit.text().strip()
        try:
            value = float(raw)
        except ValueError:
            value = main_window.get_poll_interval_s()
            self._append_log("Invalid polling period. Keeping previous value.")
        else:
            if value < 1.0:
                value = 1.0
                self._append_log("Polling period clamped to minimum 1.0 s.")

        main_window.set_poll_interval_s(value)
        self.refresh_polling_controls()

    def _connect_device(self):
        try:
            self.controller.open()
            self._append_log("Device connected.")
        except Exception as e:
            self._append_log(f"Connect error: {e}")
        finally:
            self.refresh_status()
            self.parent_refresh()

    def _disconnect_device(self):
        main_window = self._find_main_window()

        try:
            if main_window is not None and main_window.is_polling_active():
                main_window.stop_polling(log=True)

            self.controller.close()
            self._append_log("Device disconnected.")
        except Exception as e:
            self._append_log(f"Disconnect error: {e}")
        finally:
            self.refresh_status()
            self.refresh_polling_controls()
            self.parent_refresh()

    def _start_polling(self):
        main_window = self._find_main_window()
        if main_window is None:
            self._append_log("Polling controller not found.")
            return

        try:
            self._apply_polling_period_from_ui()
            main_window.start_polling()
        except Exception as e:
            self._append_log(f"Start polling error: {e}")
        finally:
            self.refresh_polling_controls()

    def _stop_polling(self):
        main_window = self._find_main_window()
        if main_window is None:
            self._append_log("Polling controller not found.")
            return

        try:
            main_window.stop_polling(log=True)
        except Exception as e:
            self._append_log(f"Stop polling error: {e}")
        finally:
            self.refresh_polling_controls()

    def parent_refresh(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "refresh_all_groups"):
                parent.refresh_all_groups()
                break
            parent = parent.parent()
