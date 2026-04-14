from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontends.gui import main_window
from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.widgets.status_utils import set_status_badge


class TriggerScopeGroup(CollapsibleGroupBox):
    def __init__(self, controller, log_callback, expanded: bool = False):
        self.controller = controller
        self.log_callback = log_callback

        self.trigger_level_edit = None
        self.edge_combo = None
        self.polarity_combo = None
        self.channel_combo = None
        self.sample_rate_edit = None
        self.buffer_size_edit = None
        self.input_range_edit = None
        self.offset_edit = None
        self.pretrigger_edit = None
        self.holdoff_edit = None

        self.configure_btn = None
        self.arm_btn = None
        self.stop_btn = None

        self.scope_status_label = None
        self.scope_summary_label = None

        content = self._build_content()
        super().__init__("Trigger / Scope Setup", content, expanded=expanded)

        self._connect_signals()
        self.refresh_ui_enabled_state()
        self._update_pretrigger_from_buffer()
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

        row = 0

        grid.addWidget(QLabel("Trigger level [V]:"), row, 0)
        self.trigger_level_edit = QLineEdit("0.1")
        self.trigger_level_edit.setPlaceholderText("e.g. 0.1")
        grid.addWidget(self.trigger_level_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Edge:"), row, 0)
        self.edge_combo = QComboBox()
        self.edge_combo.addItems(["Rising", "Falling"])
        grid.addWidget(self.edge_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Pulse polarity:"), row, 0)
        self.polarity_combo = QComboBox()
        self.polarity_combo.addItems(["Positive", "Negative"])
        grid.addWidget(self.polarity_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Channel:"), row, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["0", "1"])
        grid.addWidget(self.channel_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Sample rate [Hz]:"), row, 0)
        self.sample_rate_edit = QLineEdit("5000000")
        self.sample_rate_edit.setPlaceholderText("e.g. 5000000")
        grid.addWidget(self.sample_rate_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Buffer size:"), row, 0)
        self.buffer_size_edit = QLineEdit("128")
        self.buffer_size_edit.setPlaceholderText("e.g. 128")
        grid.addWidget(self.buffer_size_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Input range [V]:"), row, 0)
        self.input_range_edit = QLineEdit("5.0")
        self.input_range_edit.setPlaceholderText("e.g. 5.0")
        grid.addWidget(self.input_range_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Offset [V]:"), row, 0)
        self.offset_edit = QLineEdit("0.0")
        self.offset_edit.setPlaceholderText("e.g. 0.0")
        grid.addWidget(self.offset_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Pretrigger samples:"), row, 0)
        self.pretrigger_edit = QLineEdit("64")
        self.pretrigger_edit.setReadOnly(True)
        grid.addWidget(self.pretrigger_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Hold-off [s]:"), row, 0)
        self.holdoff_edit = QLineEdit("0.0")
        self.holdoff_edit.setPlaceholderText("e.g. 0.0")
        grid.addWidget(self.holdoff_edit, row, 1)
        row += 1

        layout.addLayout(grid)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.configure_btn = QPushButton("Configure scope")
        self.arm_btn = QPushButton("Arm")
        self.stop_btn = QPushButton("Stop")

        buttons_row.addWidget(self.configure_btn, 2)
        # buttons_row.addWidget(self.arm_btn, 1)
        # buttons_row.addWidget(self.stop_btn, 1)

        layout.addLayout(buttons_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Status:"))

        self.scope_status_label = QLabel("Unknown")
        self.scope_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.scope_status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        summary_box = QWidget()
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)

        self.scope_summary_label = QLabel("No scope configuration yet.")
        self.scope_summary_label.setWordWrap(True)
        summary_layout.addWidget(self.scope_summary_label)

        layout.addWidget(summary_box)

        return container

    def _connect_signals(self):
        self.buffer_size_edit.editingFinished.connect(
            self._update_pretrigger_from_buffer
        )
        self.configure_btn.clicked.connect(self._configure_scope)
        self.arm_btn.clicked.connect(self._arm_scope)
        self.stop_btn.clicked.connect(self._stop_scope)

    def _append_log(self, text: str):
        if self.log_callback is not None:
            self.log_callback(text)

    def _update_pretrigger_from_buffer(self):
        raw = self.buffer_size_edit.text().strip()

        try:
            buffer_size = int(raw)
        except ValueError:
            return

        if buffer_size <= 0:
            return

        self.pretrigger_edit.setText(str(buffer_size // 2))

    def refresh_ui_enabled_state(self):
        snapshot = self.controller.get_controller_status_snapshot()
        device_open = snapshot.device_open

        main_window = self._find_main_window()
        scope_busy = main_window.is_scope_busy() if main_window is not None else False

        config_widgets = (
            self.trigger_level_edit,
            self.edge_combo,
            self.polarity_combo,
            self.channel_combo,
            self.sample_rate_edit,
            self.buffer_size_edit,
            self.input_range_edit,
            self.offset_edit,
            self.pretrigger_edit,
            self.holdoff_edit,
            self.configure_btn,
        )

        for widget in config_widgets:
            if widget is not None:
                widget.setEnabled(device_open and (not scope_busy))

        if self.pretrigger_edit is not None:
            self.pretrigger_edit.setReadOnly(True)

        if self.arm_btn is not None:
            self.arm_btn.setEnabled(
                device_open and snapshot.scope_configured and (not scope_busy)
            )

        if self.stop_btn is not None:
            self.stop_btn.setEnabled(
                device_open and snapshot.scope_configured and (not scope_busy)
            )

    def set_unknown(self):
        set_status_badge(self.scope_status_label, "Unknown", "gray")
        self.scope_summary_label.setText("No scope configuration yet.")

    def refresh_status_from_snapshot(self):
        snapshot = self.controller.get_controller_status_snapshot()

        if not snapshot.device_open:
            set_status_badge(self.scope_status_label, "Disconnected", "red")
            self.scope_summary_label.setText("")
            return

        if not snapshot.scope_configured:
            set_status_badge(self.scope_status_label, "Not configured", "red")
            self.scope_summary_label.setText("")
            return

        cfg = self.controller.get_scope_config()
        if cfg is None:
            set_status_badge(self.scope_status_label, "Not configured", "red")
            self.scope_summary_label.setText("")
            return

        set_status_badge(self.scope_status_label, "Configured", "blue")

        edge_text = "Rising" if cfg.trigger_rising else "Falling"
        polarity_text = "Positive" if cfg.pulse_polarity_positive else "Negative"

        self.scope_summary_label.setText(
            "Configured: "
            f"CH={cfg.channel}, "
            f"Fs={cfg.sample_rate_hz:.0f} Hz, "
            f"buffer={cfg.buffer_size}, "
            f"pretrigger={cfg.pretrigger_samples}, "
            f"holdoff={cfg.holdoff_s:.6g} s, "
            f"trigger={cfg.trigger_level_v:.6f} V, "
            f"edge={edge_text}, "
            f"polarity={polarity_text}, "
            f"range={cfg.input_range_v:.6f} V, "
            f"offset={cfg.offset_v:.6f} V"
        )

    def refresh_after_connection_change(self):
        self.refresh_ui_enabled_state()

        if not self.controller.get_controller_status_snapshot().device_open:
            self.set_unknown()
        else:
            self.refresh_status_from_snapshot()

    def refresh_passive(self):
        self.refresh_status_from_snapshot()
        self.refresh_ui_enabled_state()

    def _read_form_values(self) -> dict:
        buffer_size = int(self.buffer_size_edit.text().strip())
        pretrigger = buffer_size // 2
        self.pretrigger_edit.setText(str(pretrigger))

        return {
            "trigger_level_v": float(self.trigger_level_edit.text().strip()),
            "trigger_rising": self.edge_combo.currentText() == "Rising",
            "pulse_polarity_positive": self.polarity_combo.currentText() == "Positive",
            "channel": int(self.channel_combo.currentText()),
            "sample_rate_hz": float(self.sample_rate_edit.text().strip()),
            "buffer_size": buffer_size,
            "input_range_v": float(self.input_range_edit.text().strip()),
            "offset_v": float(self.offset_edit.text().strip()),
            "pretrigger_samples": pretrigger,
            "holdoff_s": float(self.holdoff_edit.text().strip()),
        }

    def _configure_scope(self):
        try:
            params = self._read_form_values()
            summary = self.controller.configure_scope(**params)

            self.pretrigger_edit.setText(str(summary.expected_trigger_index))
            self.refresh_status_from_snapshot()
            self.refresh_ui_enabled_state()

            edge_text = "rising" if summary.trigger_rising else "falling"
            polarity_text = (
                "positive" if summary.pulse_polarity_positive else "negative"
            )
            self._append_log(
                "Scope configured: "
                f"CH={summary.channel}, "
                f"Fs={summary.sample_rate_hz:.0f} Hz, "
                f"buffer={summary.buffer_size}, "
                f"pretrigger={summary.expected_trigger_index}, "
                f"holdoff={summary.holdoff_s:.6g} s, "
                f"trigger={summary.trigger_level_v:.6f} V, "
                f"edge={edge_text}, "
                f"polarity={polarity_text}, "
                f"range={summary.input_range_v:.6f} V, "
                f"offset={summary.offset_v:.6f} V."
            )
        except Exception as e:
            self._append_log(f"Configure scope error: {e}")

    def _arm_scope(self):
        try:
            self.controller.arm_scope()
            self.refresh_status_from_snapshot()
            self.refresh_ui_enabled_state()
            self._append_log("Scope armed and waiting for trigger.")
        except Exception as e:
            self._append_log(f"Arm scope error: {e}")

    def _stop_scope(self):
        try:
            self.controller.stop_scope()
            self.refresh_status_from_snapshot()
            self.refresh_ui_enabled_state()
            self._append_log("Scope stopped.")
        except Exception as e:
            self._append_log(f"Stop scope error: {e}")

    def _find_main_window(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "is_scope_busy"):
                return parent
            parent = parent.parent()
        return None
