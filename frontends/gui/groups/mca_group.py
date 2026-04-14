from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QSizePolicy,
)

from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.widgets.status_utils import set_status_badge


class MCAWorker(QObject):
    finished = pyqtSignal()
    status = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, controller, status_period_s: float, duration_s: float | None):
        super().__init__()
        self.controller = controller
        self.status_period_s = float(status_period_s)
        self.duration_s = duration_s

    def run(self):
        try:

            def status_callback(mca_manager, result):
                self.status.emit(self.controller.mca_summary())

            self.controller.start_mca(
                status_period_s=self.status_period_s,
                duration_s=self.duration_s,
                status_callback=None,
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class MCAGroup(CollapsibleGroupBox):
    def __init__(self, controller, log_callback, expanded: bool = False):
        self.controller = controller
        self.log_callback = log_callback

        self.channels_edit = None
        self.vmin_edit = None
        self.vmax_edit = None
        self.apply_btn = None

        self.duration_edit = None
        self.status_edit = None
        self.start_btn = None
        self.stop_btn = None
        self.clear_btn = None
        self.export_btn = None

        self.status_label = None
        self.summary_label = None

        self._thread = None
        self._worker = None
        self._running = False

        content = self._build_content()
        super().__init__("MCA", content, expanded=expanded)

        self.refresh_ui_enabled_state()
        self.refresh_passive()

    def _build_content(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        config_box = QGroupBox("MCA Configuration")
        config_layout = QGridLayout(config_box)
        config_layout.setHorizontalSpacing(10)
        config_layout.setVerticalSpacing(8)

        self.channels_edit = QLineEdit("4096")
        self.vmin_edit = QLineEdit("0")
        self.vmax_edit = QLineEdit("5")

        config_layout.addWidget(QLabel("Channels:"), 0, 0)
        config_layout.addWidget(self.channels_edit, 0, 1)

        config_layout.addWidget(QLabel("Voltage min [V]:"), 1, 0)
        config_layout.addWidget(self.vmin_edit, 1, 1)

        config_layout.addWidget(QLabel("Voltage max [V]:"), 2, 0)
        config_layout.addWidget(self.vmax_edit, 2, 1)

        self.apply_btn = QPushButton("Apply MCA config")
        self.apply_btn.clicked.connect(self._apply_config)
        config_layout.addWidget(self.apply_btn, 3, 0, 1, 2)

        layout.addWidget(config_box)

        run_box = QGroupBox("MCA Run")
        run_layout = QGridLayout(run_box)
        run_layout.setHorizontalSpacing(10)
        run_layout.setVerticalSpacing(8)

        self.duration_edit = QLineEdit("")
        self.duration_edit.setPlaceholderText("blank = continuous")

        self.status_edit = QLineEdit("1.0")

        run_layout.addWidget(QLabel("Duration [s]:"), 0, 0)
        run_layout.addWidget(self.duration_edit, 0, 1)

        run_layout.addWidget(QLabel("Status period [s]:"), 1, 0)
        run_layout.addWidget(self.status_edit, 1, 1)

        self.start_btn = QPushButton("Start MCA")
        self.stop_btn = QPushButton("Stop MCA")
        self.clear_btn = QPushButton("Clear MCA")
        self.start_btn = QPushButton("Start MCA")
        self.stop_btn = QPushButton("Stop MCA")
        self.clear_btn = QPushButton("Clear MCA")
        self.export_btn = QPushButton("Export TXT")

        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.clear_btn.clicked.connect(self._clear)
        self.export_btn.clicked.connect(self._export_txt)

        run_layout.addWidget(self.start_btn, 2, 0)
        run_layout.addWidget(self.stop_btn, 2, 1)
        run_layout.addWidget(self.clear_btn, 3, 0)
        run_layout.addWidget(self.export_btn, 3, 1)

        layout.addWidget(run_box)

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
        self.summary_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.summary_label)

        return container

    def _append_log(self, text: str):
        if self.log_callback is not None:
            self.log_callback(text)

    def _find_main_window(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "set_scope_busy") and hasattr(parent, "is_scope_busy"):
                return parent
            parent = parent.parent()
        return None

    def _load_form_from_config(self):
        cfg = self.controller.get_mca_config()
        if cfg is None:
            return

        self.channels_edit.setText(str(cfg.n_channels))
        self.vmin_edit.setText(f"{cfg.voltage_min:g}")
        self.vmax_edit.setText(f"{cfg.voltage_max:g}")

    def _read_config_values(self) -> dict:
        return {
            "n_channels": int(self.channels_edit.text().strip()),
            "voltage_min": float(self.vmin_edit.text().strip()),
            "voltage_max": float(self.vmax_edit.text().strip()),
        }

    def _read_duration_s(self) -> float | None:
        raw = self.duration_edit.text().strip()
        if raw == "":
            return None

        value = float(raw)
        if value <= 0:
            raise ValueError("Duration must be > 0 s.")
        return value

    def _read_status_period_s(self) -> float:
        raw = self.status_edit.text().strip()
        if raw == "":
            return 1.0

        value = float(raw)
        if value < 0.1:
            value = 0.1
            self._append_log("MCA status period clamped to minimum 0.1 s.")
        return value

    def refresh_ui_enabled_state(self):
        snapshot = self.controller.get_controller_status_snapshot()
        mca_snapshot = self.controller.get_mca_status_snapshot()

        scope_ready = snapshot.device_open and snapshot.scope_configured
        mca_configured = self.controller.get_mca_config() is not None
        running = self._running or mca_snapshot.running

        main_window = self._find_main_window()
        scope_busy = main_window.is_scope_busy() if main_window is not None else False

        can_edit_config = scope_ready and (not running) and (not scope_busy)
        for widget in (
            self.channels_edit,
            self.vmin_edit,
            self.vmax_edit,
            self.apply_btn,
        ):
            if widget is not None:
                widget.setEnabled(can_edit_config)

        can_start = (
            scope_ready and mca_configured and (not running) and (not scope_busy)
        )

        if self.duration_edit is not None:
            self.duration_edit.setEnabled(can_start)

        if self.status_edit is not None:
            self.status_edit.setEnabled(can_start)

        if self.start_btn is not None:
            self.start_btn.setEnabled(can_start)

        if self.stop_btn is not None:
            self.stop_btn.setEnabled(running)

        if self.clear_btn is not None:
            self.clear_btn.setEnabled(scope_ready and mca_configured and (not running))

        if self.export_btn is not None:
            self.export_btn.setEnabled(scope_ready and mca_configured and (not running))

    def _update_summary(self):
        cfg = self.controller.get_mca_config()
        summary = self.controller.mca_summary()

        if cfg is None:
            self.summary_label.setText("No MCA configuration applied yet.")
            return

        self.summary_label.setText(
            f"Configured: "
            f"Channels={cfg.n_channels}, "
            f"Vmin={cfg.voltage_min:.6f} V, "
            f"Vmax={cfg.voltage_max:.6f} V, "
            f"Runtime: "
            f"Events={summary['event_count']}, "
            f"Accepted={summary['accepted_count']}, "
            f"Rejected={summary['rejected_count']}, "
            f"Overflow={summary['overflow_count']}, "
            f"Underflow={summary['underflow_count']}, "
            f"Counts={summary['total_counts_in_spectrum']}, "
            f"Elapsed={summary['elapsed_time_s']:.3f} s, "
            f"AcceptedRate={summary['accepted_rate_cps']:.3f} cps, "
            f"InstantaneousDeadTime={summary['dead_time_instant_percent']:.1f}%, "
            f"AverageDeadTime={summary['dead_time_average_percent']:.1f}%, "
            f"Arms={summary['arm_count']}, "
            f"Reads={summary['triggered_read_count']}, "
            f"Processed={summary['processed_count']}, "
            f"Dropped={summary['dropped_buffers']}"
        )

    def _apply_config(self):
        try:
            cfg = self.controller.configure_mca(**self._read_config_values())
            # self._load_form_from_config()
            self.refresh_passive()

            main_window = self._find_main_window()
            if main_window is not None:
                main_window.refresh_plot_panel()

            self._append_log(
                "MCA configured: "
                f"channels={cfg.n_channels}, "
                f"vmin={cfg.voltage_min:.6f} V, "
                f"vmax={cfg.voltage_max:.6f} V, "
            )
        except Exception as e:
            self._append_log(f"Apply MCA config error: {e}")

    def _start(self):
        if self._running:
            return

        try:
            duration_s = self._read_duration_s()
            status_period_s = self._read_status_period_s()
        except Exception as e:
            self._append_log(f"Start MCA error: {e}")
            return

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(True)

        self._running = True
        self.refresh_ui_enabled_state()
        set_status_badge(self.status_label, "Running", "yellow")

        if duration_s is None:
            self._append_log(
                f"MCA started in continuous mode (status period {status_period_s:.3f} s)."
            )
        else:
            self._append_log(
                f"MCA started for {duration_s:.3f} s (status period {status_period_s:.3f} s)."
            )

        self._thread = QThread()
        self._worker = MCAWorker(
            self.controller,
            status_period_s=status_period_s,
            duration_s=duration_s,
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

        self._thread.start()

    def _stop(self):
        try:
            self.controller.stop_mca()
            self._append_log("MCA stop requested.")
        except Exception as e:
            self._append_log(f"Stop MCA error: {e}")

    def _clear(self):
        try:
            self.controller.clear_mca()
            self.refresh_passive()

            main_window = self._find_main_window()
            if main_window is not None:
                main_window.refresh_plot_panel()

            self._append_log("MCA cleared.")
        except Exception as e:
            self._append_log(f"Clear MCA error: {e}")

    def _on_status(self, summary: dict):
        self._update_summary()

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.refresh_plot_panel()

    def _on_done(self):
        self._running = False

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(False)
            main_window.refresh_plot_panel()

        self._append_log("MCA finished.")
        self.refresh_passive()

    def _on_error(self, msg: str):
        self._running = False

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(False)
            main_window.refresh_plot_panel()

        self._append_log(f"MCA error: {msg}")
        self.refresh_passive()

    def _cleanup(self):
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def refresh_after_connection_change(self):
        self.refresh_ui_enabled_state()
        self.refresh_passive()

    def refresh_passive(self):
        self.refresh_ui_enabled_state()

        snapshot = self.controller.get_controller_status_snapshot()
        mca_snapshot = self.controller.get_mca_status_snapshot()

        # self._load_form_from_config()

        if not snapshot.device_open:
            set_status_badge(self.status_label, "Disconnected", "red")
            self._update_summary()
            return

        if self._running or mca_snapshot.running:
            set_status_badge(self.status_label, "Running", "yellow")
            self._update_summary()
            return

        if not snapshot.scope_configured:
            set_status_badge(self.status_label, "Scope not configured", "red")
            self._update_summary()
            return

        if self.controller.get_mca_config() is None:
            set_status_badge(self.status_label, "MCA not configured", "red")
            self._update_summary()
            return

        summary = self.controller.mca_summary()
        if summary["event_count"] > 0 or summary["total_counts_in_spectrum"] > 0:
            set_status_badge(self.status_label, "Stopped", "gray")
        else:
            set_status_badge(self.status_label, "Ready", "blue")

        self._update_summary()

    def _export_txt(self):
        try:
            data = self.controller.get_mca_export_data()

            cfg = data.get("config")
            summary = data.get("summary") or {}
            spectrum = data.get("spectrum")

            if cfg is None:
                self._append_log("Export TXT error: MCA not configured.")
                return

            if spectrum is None:
                self._append_log("Export TXT error: spectrum is empty.")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save MCA spectrum as TXT",
                "mca_spectrum.txt",
                "Text files (*.txt);;All files (*)",
            )
            if not file_path:
                return

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# MCA Spectrum Export\n\n")

                f.write("[CONFIG]\n")
                f.write(f"n_channels={cfg['n_channels']}\n")
                f.write(f"voltage_min={cfg['voltage_min']}\n")
                f.write(f"voltage_max={cfg['voltage_max']}\n")
                f.write(f"baseline_width={cfg['baseline_width']}\n")
                f.write(f"baseline_center_offset={cfg['baseline_center_offset']}\n")
                f.write(f"trigger_index_estimate={cfg['trigger_index_estimate']}\n\n")

                f.write("[SUMMARY]\n")
                for key, value in summary.items():
                    f.write(f"{key}={value}\n")
                f.write("\n")

                f.write("[SPECTRUM]\n")
                f.write("channel\tcounts\n")
                for i, counts in enumerate(spectrum):
                    f.write(f"{i}\t{int(counts)}\n")

            self._append_log(f"MCA TXT exported: {file_path}")

        except Exception as e:
            self._append_log(f"Export TXT error: {e}")
