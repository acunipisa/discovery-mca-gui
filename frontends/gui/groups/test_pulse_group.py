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

from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.widgets.status_utils import set_status_badge


class TestPulseGroup(CollapsibleGroupBox):
    def __init__(self, controller, log_callback, expanded: bool = False):
        self.controller = controller
        self.log_callback = log_callback

        self.mode_combo = None
        self.frequency_edit = None
        self.amplitude_edit = None
        self.offset_edit = None
        self.shape_label = None
        self.shape_edit = None
        self.phase_edit = None

        self.start_btn = None
        self.stop_btn = None

        self.status_label = None
        self.summary_label = None

        content = self._build_content()
        super().__init__("Test Pulse", content, expanded=expanded)

        self._connect_signals()
        self.refresh_ui_enabled_state()
        self._on_mode_changed()
        self.refresh_passive()

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

        grid.addWidget(QLabel("Mode:"), row, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Triangle", "triangle")
        self.mode_combo.addItem("Pulse", "pulse")
        grid.addWidget(self.mode_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Frequency [Hz]:"), row, 0)
        self.frequency_edit = QLineEdit("100")
        grid.addWidget(self.frequency_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Amplitude [V]:"), row, 0)
        self.amplitude_edit = QLineEdit("1.0")
        grid.addWidget(self.amplitude_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Offset [V]:"), row, 0)
        self.offset_edit = QLineEdit("0.0")
        grid.addWidget(self.offset_edit, row, 1)
        row += 1

        self.shape_label = QLabel("Symmetry [%]:")
        grid.addWidget(self.shape_label, row, 0)
        self.shape_edit = QLineEdit("0.0")
        grid.addWidget(self.shape_edit, row, 1)
        row += 1

        grid.addWidget(QLabel("Phase [deg]:"), row, 0)
        self.phase_edit = QLineEdit("0.0")
        grid.addWidget(self.phase_edit, row, 1)
        row += 1

        layout.addLayout(grid)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.start_btn = QPushButton("Start test pulse")
        self.stop_btn = QPushButton("Stop test pulse")

        buttons_row.addWidget(self.start_btn, 1)
        buttons_row.addWidget(self.stop_btn, 1)

        layout.addLayout(buttons_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Status:"))

        self.status_label = QLabel("—")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        return container

    def _connect_signals(self):
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)

    def _append_log(self, text: str):
        if self.log_callback is not None:
            self.log_callback(text)

    def _on_mode_changed(self):
        mode = self.mode_combo.currentData()

        if mode == "pulse":
            self.shape_label.setText("Duty cycle [%]:")
            self.shape_edit.setText("0.1")
        else:
            self.shape_label.setText("Symmetry [%]:")
            self.shape_edit.setText("0.0")

    def _read_form_values(self) -> dict:
        return {
            "mode": self.mode_combo.currentData(),
            "frequency_hz": float(self.frequency_edit.text().strip()),
            "amplitude_v": float(self.amplitude_edit.text().strip()),
            "offset_v": float(self.offset_edit.text().strip()),
            "shape_percent": float(self.shape_edit.text().strip()),
            "phase_deg": float(self.phase_edit.text().strip()),
        }

    def refresh_ui_enabled_state(self):
        snapshot = self.controller.get_controller_status_snapshot()
        device_open = snapshot.device_open

        config_widgets = (
            self.mode_combo,
            self.frequency_edit,
            self.amplitude_edit,
            self.offset_edit,
            self.shape_edit,
            self.phase_edit,
            self.start_btn,
            self.stop_btn,
        )

        for widget in config_widgets:
            if widget is not None:
                widget.setEnabled(device_open)

    def refresh_passive(self):
        snapshot = self.controller.get_controller_status_snapshot()

        if not snapshot.device_open:
            set_status_badge(self.status_label, "Disconnected", "red")
            self.summary_label.setText("")
            return

        tp = self.controller.test_pulse
        if tp is None:
            set_status_badge(self.status_label, "Unavailable", "red")
            self.summary_label.setText("")
            return

        summary = tp.get_config_summary()

        if summary["is_running"]:
            set_status_badge(self.status_label, "Running", "yellow")
        else:
            set_status_badge(self.status_label, "Stopped", "gray")

        mode = summary["mode"] if summary["mode"] is not None else "—"
        freq = summary["frequency_hz"]
        amp = summary["amplitude_v"]
        offset = summary["offset_v"]
        shape = summary["symmetry_percent"]
        phase = summary["phase_deg"]

        if freq is None:
            self.summary_label.setText("No test pulse configuration applied yet.")
            return

        shape_name = "Duty" if mode == "pulse" else "Symmetry"

        self.summary_label.setText(
            "Configured: "
            f"mode={mode}, "
            f"f={freq:.6g} Hz, "
            f"amp={amp:.6g} V, "
            f"offset={offset:.6g} V, "
            f"{shape_name.lower()}={shape:.6g} %, "
            f"phase={phase:.6g} deg"
        )

    def _start(self):
        try:
            params = self._read_form_values()

            self.controller.start_test_pulse(
                mode=params["mode"],
                frequency_hz=params["frequency_hz"],
                amplitude_v=params["amplitude_v"],
                offset_v=params["offset_v"],
                shape_percent=params["shape_percent"],
                phase_deg=params["phase_deg"],
            )

            mode = params["mode"]
            shape_name = "duty" if mode == "pulse" else "symmetry"

            self._append_log(
                "Test pulse started: "
                f"mode={mode}, "
                f"f={params['frequency_hz']:.6g} Hz, "
                f"amp={params['amplitude_v']:.6g} V, "
                f"offset={params['offset_v']:.6g} V, "
                f"{shape_name}={params['shape_percent']:.6g} %, "
                f"phase={params['phase_deg']:.6g} deg."
            )

            self.refresh_passive()
        except Exception as e:
            self._append_log(f"Start test pulse error: {e}")

    def _stop(self):
        try:
            self.controller.stop_test_pulse(force_zero=False)
            self._append_log("Test pulse stopped.")
            self.refresh_passive()
        except Exception as e:
            self._append_log(f"Stop test pulse error: {e}")

    def refresh_after_connection_change(self):
        self.refresh_ui_enabled_state()
        self.refresh_passive()
