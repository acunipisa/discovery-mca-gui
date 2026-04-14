from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hardware.scope_manager import ScopeWaitCancelled
from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.widgets.status_utils import set_status_badge


class CaptureWorker(QObject):
    finished = pyqtSignal(object)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def run(self):
        try:
            result = self.controller.capture_once()
            self.finished.emit(result)
        except ScopeWaitCancelled:
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(str(e))


class CaptureGroup(CollapsibleGroupBox):
    def __init__(self, controller, log_callback, expanded: bool = False):
        self.controller = controller
        self.log_callback = log_callback

        self.capture_once_btn = None
        self.cancel_wait_btn = None

        self.capture_status_label = None
        self.peak_label = None
        self.baseline_label = None
        self.amplitude_label = None
        self.peak_index_label = None
        self.trigger_index_label = None
        self.baseline_window_label = None

        self._capture_thread = None
        self._capture_worker = None
        self._capture_in_progress = False
        self._last_capture_cancelled = False

        content = self._build_content()
        super().__init__("Capture", content, expanded=expanded)

        self.refresh_ui_enabled_state()
        self.set_unknown()

    def _build_content(self) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.capture_once_btn = QPushButton("Capture once")
        self.capture_once_btn.clicked.connect(self._capture_once)

        self.cancel_wait_btn = QPushButton("Cancel waiting")
        self.cancel_wait_btn.clicked.connect(self._cancel_waiting)

        buttons_row.addWidget(self.capture_once_btn, 1)
        buttons_row.addWidget(self.cancel_wait_btn, 1)
        buttons_row.addStretch()

        layout.addLayout(buttons_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Status:"))

        self.capture_status_label = QLabel("Unknown")
        self.capture_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.capture_status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        row = 0

        grid.addWidget(QLabel("Peak:"), row, 0)
        self.peak_label = QLabel("—")
        grid.addWidget(self.peak_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Baseline:"), row, 0)
        self.baseline_label = QLabel("—")
        grid.addWidget(self.baseline_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Amplitude:"), row, 0)
        self.amplitude_label = QLabel("—")
        grid.addWidget(self.amplitude_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Peak index:"), row, 0)
        self.peak_index_label = QLabel("—")
        grid.addWidget(self.peak_index_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Trigger index:"), row, 0)
        self.trigger_index_label = QLabel("—")
        grid.addWidget(self.trigger_index_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Baseline window:"), row, 0)
        self.baseline_window_label = QLabel("—")
        grid.addWidget(self.baseline_window_label, row, 1)

        layout.addLayout(grid)

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

    def refresh_ui_enabled_state(self):
        snapshot = self.controller.get_controller_status_snapshot()
        device_open = snapshot.device_open
        scope_configured = snapshot.scope_configured

        main_window = self._find_main_window()
        scope_busy = main_window.is_scope_busy() if main_window is not None else False

        if self.capture_once_btn is not None:
            self.capture_once_btn.setEnabled(
                (not self._capture_in_progress)
                and (not scope_busy)
                and device_open
                and scope_configured
            )

        if self.cancel_wait_btn is not None:
            self.cancel_wait_btn.setEnabled(
                self._capture_in_progress and device_open and scope_configured
            )

    def _clear_result_labels(self):
        self.peak_label.setText("—")
        self.baseline_label.setText("—")
        self.amplitude_label.setText("—")
        self.peak_index_label.setText("—")
        self.trigger_index_label.setText("—")
        self.baseline_window_label.setText("—")

    def set_unknown(self):
        set_status_badge(self.capture_status_label, "Unknown", "gray")
        self._clear_result_labels()

    def set_ready(self):
        set_status_badge(self.capture_status_label, "Ready", "blue")
        self._clear_result_labels()

    def set_waiting_trigger(self):
        set_status_badge(self.capture_status_label, "Waiting trigger", "yellow")

    def set_cancelled(self):
        set_status_badge(self.capture_status_label, "Cancelled", "gray")

    def refresh_from_result(self, result):
        set_status_badge(self.capture_status_label, "Captured", "green")
        self.peak_label.setText(f"{result.peak:.6f} V")
        self.baseline_label.setText(f"{result.baseline:.6f} V")
        self.amplitude_label.setText(f"{result.amplitude:.6f} V")
        self.peak_index_label.setText(str(result.peak_index))
        self.trigger_index_label.setText(str(result.trigger_index_estimate))
        self.baseline_window_label.setText(
            f"[{result.baseline_start}:{result.baseline_end}]"
        )

    def refresh_after_connection_change(self):
        self.refresh_ui_enabled_state()

        snapshot = self.controller.get_controller_status_snapshot()

        if not snapshot.device_open:
            self.set_unknown()
            return

        if not snapshot.scope_configured:
            set_status_badge(self.capture_status_label, "Scope not configured", "red")
            self._clear_result_labels()
            return

        self.refresh_passive()

    def refresh_passive(self):
        self.refresh_ui_enabled_state()

        snapshot = self.controller.get_controller_status_snapshot()

        if not snapshot.device_open:
            self.set_unknown()
            return

        if not snapshot.scope_configured:
            set_status_badge(self.capture_status_label, "Scope not configured", "red")
            self._clear_result_labels()
            return

        if self._capture_in_progress:
            self.set_waiting_trigger()
            return

        if self._last_capture_cancelled:
            self.set_cancelled()
            return

        result = self.controller.mca.last_scope_result
        if result is None:
            self.set_ready()
            return

        self.refresh_from_result(result)

    def _capture_once(self):
        if self._capture_in_progress:
            return

        self._capture_in_progress = True
        self._last_capture_cancelled = False

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(True)

        self.refresh_ui_enabled_state()
        self.set_waiting_trigger()
        self._append_log("Capture started. Waiting for trigger...")

        self._capture_thread = QThread()
        self._capture_worker = CaptureWorker(self.controller)
        self._capture_worker.moveToThread(self._capture_thread)

        self._capture_thread.started.connect(self._capture_worker.run)
        self._capture_worker.finished.connect(self._on_capture_finished)
        self._capture_worker.cancelled.connect(self._on_capture_cancelled)
        self._capture_worker.error.connect(self._on_capture_error)

        self._capture_worker.finished.connect(self._capture_thread.quit)
        self._capture_worker.cancelled.connect(self._capture_thread.quit)
        self._capture_worker.error.connect(self._capture_thread.quit)

        self._capture_thread.finished.connect(self._cleanup_capture_thread)

        self._capture_thread.start()

    def _cancel_waiting(self):
        if not self._capture_in_progress:
            return

        try:
            self.controller.cancel_capture_waiting()
            self._append_log("Capture cancellation requested.")
        except Exception as e:
            self._append_log(f"Cancel capture error: {e}")

    def _on_capture_finished(self, result):
        self._capture_in_progress = False
        self._last_capture_cancelled = False

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(False)

        self.refresh_from_result(result)
        self.refresh_ui_enabled_state()

        self._append_log(
            "Capture completed: "
            f"peak={result.peak:.6f} V, "
            f"baseline={result.baseline:.6f} V, "
            f"amplitude={result.amplitude:.6f} V, "
            f"peak_index={result.peak_index}, "
            f"trigger_index={result.trigger_index_estimate}."
        )

    def _on_capture_cancelled(self):
        self._capture_in_progress = False
        self._last_capture_cancelled = True

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(False)

        self.refresh_ui_enabled_state()
        self.set_cancelled()
        self._append_log("Capture cancelled.")

    def _on_capture_error(self, message: str):
        self._capture_in_progress = False
        self._last_capture_cancelled = False

        main_window = self._find_main_window()
        if main_window is not None:
            main_window.set_scope_busy(False)

        self.refresh_ui_enabled_state()
        self.refresh_passive()
        self._append_log(f"Capture error: {message}")

    def _cleanup_capture_thread(self):
        if self._capture_worker is not None:
            self._capture_worker.deleteLater()
            self._capture_worker = None

        if self._capture_thread is not None:
            self._capture_thread.deleteLater()
            self._capture_thread = None
