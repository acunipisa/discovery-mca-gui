from PyQt6.QtCore import Qt, QTimer, QThread
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.controller import DiscoveryMCAController
from frontends.gui.auto_pulse_worker import AutoPulseWorker
from frontends.gui.groups.connection_group import ConnectionGroup
from frontends.gui.groups.supplies_group import SuppliesGroup
from frontends.gui.groups.hv_group import HVGroup
from frontends.gui.groups.capture_group import CaptureGroup
from frontends.gui.groups.mca_group import MCAGroup
from frontends.gui.groups.trigger_scope_group import TriggerScopeGroup
from frontends.gui.plot_panel import PlotPanel
from frontends.gui.widgets.collapsible_group_box import CollapsibleGroupBox
from frontends.gui.groups.test_pulse_group import TestPulseGroup


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Discovery 3 MCA")
        self.resize(1400, 900)

        self.controller = DiscoveryMCAController()
        self.log_view = None

        self.connection_group = None
        self.supplies_group = None
        self.hv_group = None
        self.trigger_scope_group = None
        self.capture_group = None
        self.mca_group = None
        self.test_pulse_group = None

        self.root_splitter = None
        self.left_panel = None
        self.right_panel = None
        self.plot_panel = None

        self._pulse_thread = None
        self._pulse_worker = None

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._on_poll_timer_timeout)
        self.poll_interval_s = 1.0

        self.scope_busy = False
        self.left_ratio_max = 0.25
        self._clamping_splitter = False

        self._build_ui()
        self.refresh_all_groups()
        self.refresh_plot_panel()

    def is_scope_busy(self) -> bool:
        return bool(self.scope_busy)

    def set_scope_busy(self, busy: bool):
        self.scope_busy = bool(busy)
        self.refresh_all_groups()

    def closeEvent(self, event):
        try:
            self.stop_polling(log=False)
        except Exception:
            pass

        try:
            self.controller.close()
        except Exception:
            pass

        super().closeEvent(event)

    def _build_ui(self):
        self.root_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.root_splitter.setChildrenCollapsible(False)

        self.left_panel = self._build_left_panel()
        self.right_panel = self._build_right_panel()

        self.root_splitter.addWidget(self.left_panel)
        self.root_splitter.addWidget(self.right_panel)

        self.root_splitter.setStretchFactor(0, 0)
        self.root_splitter.setStretchFactor(1, 1)

        initial_left = self._recommended_initial_left_width()
        total = max(1, self.width())
        initial_right = max(1, total - initial_left)

        self.root_splitter.setSizes([initial_left, initial_right])
        self.root_splitter.splitterMoved.connect(self._on_root_splitter_moved)

        self.setCentralWidget(self.root_splitter)
        self._apply_root_splitter_limits()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.root_splitter is None:
            return

        self._apply_root_splitter_limits()

    def _recommended_initial_left_width(self) -> int:
        total = max(1, self.width())
        content_min = self._left_content_min_width()
        suggested = int(total * 0.28)
        return max(content_min, suggested)

    def _left_content_min_width(self) -> int:
        if self.left_panel is None:
            return 260

        inner = self.left_panel.widget()
        if inner is None:
            return 260

        content_hint = inner.sizeHint().width()
        frame_extra = 24
        return max(260, content_hint + frame_extra)

    def _right_content_min_width(self) -> int:
        if self.right_panel is None:
            return 420

        return max(420, self.right_panel.minimumSizeHint().width() + 24)

    def _left_splitter_limits_px(self) -> tuple[int, int]:
        total = self.root_splitter.width()
        if total <= 0:
            return 0, 0

        handle_w = self.root_splitter.handleWidth()
        usable = max(1, total - handle_w)

        left_min = self._left_content_min_width()
        right_min = self._right_content_min_width()

        left_max_from_right = max(left_min, usable - right_min)
        left_max_from_ratio = int(usable * self.left_ratio_max)
        left_max = max(left_min, min(left_max_from_right, left_max_from_ratio))

        if left_max < left_min:
            left_max = left_min

        return left_min, left_max

    def _apply_root_splitter_limits(self):
        if self.root_splitter is None:
            return

        sizes = self.root_splitter.sizes()
        if len(sizes) < 2:
            return

        left_min, left_max = self._left_splitter_limits_px()
        total = sum(sizes)
        if total <= 0:
            return

        current_left = sizes[0]
        clamped_left = max(left_min, min(current_left, left_max))

        if clamped_left == current_left:
            return

        self._clamping_splitter = True
        try:
            self.root_splitter.setSizes([clamped_left, max(1, total - clamped_left)])
        finally:
            self._clamping_splitter = False

    def _on_root_splitter_moved(self, pos: int, index: int):
        if self._clamping_splitter:
            return
        self._apply_root_splitter_limits()

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.connection_group = ConnectionGroup(
            controller=self.controller,
            log_callback=self._append_log,
        )
        layout.addWidget(self.connection_group)

        self.supplies_group = SuppliesGroup(
            controller=self.controller,
            log_callback=self._append_log,
            expanded=False,
        )
        layout.addWidget(self.supplies_group)

        self.hv_group = HVGroup(
            controller=self.controller,
            log_callback=self._append_log,
            expanded=False,
        )
        layout.addWidget(self.hv_group)

        self.trigger_scope_group = TriggerScopeGroup(
            controller=self.controller,
            log_callback=self._append_log,
            expanded=False,
        )
        layout.addWidget(self.trigger_scope_group)

        self.capture_group = CaptureGroup(
            controller=self.controller,
            log_callback=self._append_log,
            expanded=False,
        )
        layout.addWidget(self.capture_group)

        self.mca_group = MCAGroup(
            controller=self.controller,
            log_callback=self._append_log,
            expanded=False,
        )
        layout.addWidget(self.mca_group)

        self.test_pulse_group = TestPulseGroup(
            controller=self.controller,
            log_callback=self._append_log,
            expanded=False,
        )
        layout.addWidget(self.test_pulse_group)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _build_right_panel(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.plot_panel = PlotPanel(controller=self.controller)
        self.plot_panel.plot_view_combo.currentIndexChanged.connect(
            self._on_plot_view_changed
        )

        log_section = self._build_log_section()

        splitter.addWidget(self.plot_panel)
        splitter.addWidget(log_section)
        splitter.setSizes([700, 180])

        return splitter

    def _build_log_section(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        box = QGroupBox("Log / Debug")
        layout = QVBoxLayout(box)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlainText("GUI started.\nPyQt6 layout placeholder ready.")

        layout.addWidget(self.log_view)
        outer.addWidget(box)

        return widget

    def _make_placeholder_collapsible(self, title: str) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel(f"{title} placeholder"))

        return CollapsibleGroupBox(title, content, expanded=False)

    def _append_log(self, text: str):
        if self.log_view is not None:
            self.log_view.appendPlainText(text)

    def _on_plot_view_changed(self):
        self.refresh_plot_panel()

        if self.plot_panel is None:
            return

        selected_view = self.plot_panel.current_view()
        if selected_view != "Last Pulse":
            return

        if (
            self.controller.mca.last_buffer is None
            or self.controller.mca.last_scope_result is None
        ):
            self._try_fetch_last_pulse_async()

    def refresh_plot_panel(self):
        if self.plot_panel is None:
            return
        self.plot_panel.refresh_plot_panel()

    def is_polling_active(self) -> bool:
        return self.poll_timer.isActive()

    def get_poll_interval_s(self) -> float:
        return float(self.poll_interval_s)

    def set_poll_interval_s(self, interval_s: float):
        interval_s = max(1.0, float(interval_s))
        self.poll_interval_s = interval_s

        if self.poll_timer.isActive():
            self.poll_timer.setInterval(int(round(interval_s * 1000)))

        if self.connection_group is not None:
            self.connection_group.refresh_polling_controls()

    def start_polling(self):
        snapshot = self.controller.get_controller_status_snapshot()
        if not snapshot.device_open:
            raise RuntimeError("Cannot start polling: device not connected.")

        interval_ms = int(round(max(1.0, self.poll_interval_s) * 1000))
        self.poll_timer.start(interval_ms)

        if self.connection_group is not None:
            self.connection_group.refresh_polling_controls()

        self._append_log(f"Polling started ({self.poll_interval_s:.3f} s).")

    def stop_polling(self, log: bool = True):
        was_active = self.poll_timer.isActive()
        self.poll_timer.stop()

        if self.connection_group is not None:
            self.connection_group.refresh_polling_controls()

        if log and was_active:
            self._append_log("Polling stopped.")

    def _on_poll_timer_timeout(self):
        try:
            snapshot = self.controller.get_controller_status_snapshot()
            if not snapshot.device_open:
                self.stop_polling(log=True)
                return

            self.refresh_all_groups()
            self.refresh_plot_panel()
        except Exception as e:
            self._append_log(f"Polling refresh error: {e}")

    def refresh_all_groups(self):
        if self.connection_group is not None:
            self.connection_group.refresh_status()
            self.connection_group.refresh_polling_controls()

        if self.supplies_group is not None:
            self.supplies_group.refresh_after_connection_change()
            self.supplies_group.refresh_passive()

        if self.hv_group is not None:
            self.hv_group.refresh_after_connection_change()
            self.hv_group.refresh_passive()

        if self.trigger_scope_group is not None:
            self.trigger_scope_group.refresh_after_connection_change()
            self.trigger_scope_group.refresh_passive()

        if self.capture_group is not None:
            self.capture_group.refresh_after_connection_change()
            self.capture_group.refresh_passive()

        if self.mca_group is not None:
            self.mca_group.refresh_after_connection_change()
            self.mca_group.refresh_passive()

        if self.test_pulse_group is not None:
            self.test_pulse_group.refresh_after_connection_change()
            self.test_pulse_group.refresh_passive()

    def _on_auto_capture_done(self, result):
        self.set_scope_busy(False)
        self._append_log(
            "Auto pulse captured: "
            f"peak={result.peak:.6f} V, "
            f"baseline={result.baseline:.6f} V, "
            f"amplitude={result.amplitude:.6f} V, "
            f"peak_index={result.peak_index}, "
            f"trigger_index={result.trigger_index_estimate}."
        )
        self.refresh_all_groups()
        self.refresh_plot_panel()

    def _on_auto_capture_error(self, message: str):
        self.set_scope_busy(False)
        self._append_log(f"Auto pulse capture failed: {message}")
        self.refresh_all_groups()
        self.refresh_plot_panel()

    def _try_fetch_last_pulse_async(self):
        if self.is_scope_busy():
            self._append_log("Skip auto pulse capture: scope busy.")
            return

        snapshot = self.controller.get_controller_status_snapshot()
        if not snapshot.device_open:
            self._append_log("Skip auto pulse capture: device not connected.")
            return

        if not snapshot.scope_configured:
            self._append_log("Skip auto pulse capture: scope not configured.")
            return

        self.set_scope_busy(True)
        self._append_log("Auto pulse capture started...")

        self._pulse_thread = QThread()
        self._pulse_worker = AutoPulseWorker(self.controller)
        self._pulse_worker.moveToThread(self._pulse_thread)

        self._pulse_thread.started.connect(self._pulse_worker.run)

        self._pulse_worker.finished.connect(self._on_auto_capture_done)
        self._pulse_worker.error.connect(self._on_auto_capture_error)

        self._pulse_worker.finished.connect(self._pulse_thread.quit)
        self._pulse_worker.error.connect(self._pulse_thread.quit)

        self._pulse_thread.finished.connect(self._cleanup_auto_pulse_thread)

        self._pulse_thread.start()

    def _cleanup_auto_pulse_thread(self):
        if self._pulse_worker is not None:
            self._pulse_worker.deleteLater()
            self._pulse_worker = None

        if self._pulse_thread is not None:
            self._pulse_thread.deleteLater()
            self._pulse_thread = None
