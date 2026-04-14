from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure


class PlotToolbar(NavigationToolbar2QT):
    toolitems = [
        item
        for item in NavigationToolbar2QT.toolitems
        if item[0] in ("Home", "Pan", "Zoom", "Save")
    ]


class PlotPanel(QWidget):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller

        self.plot_view_combo = None
        self.plot_info_label = None

        self.figure = None
        self.canvas = None
        self.ax = None

        self.lin_radio = None
        self.log_radio = None
        self.auto_range_check = None
        self.toolbar = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls = QGroupBox("Plot Controls")
        controls_layout = QHBoxLayout(controls)

        self.plot_view_combo = QComboBox()
        self.plot_view_combo.addItems(["MCA Spectrum", "Last Pulse"])

        self.lin_radio = QRadioButton("Lin")
        self.log_radio = QRadioButton("Log")
        self.lin_radio.setChecked(True)

        self.auto_range_check = QCheckBox("Auto range")
        self.auto_range_check.setChecked(True)

        self.plot_view_combo.currentIndexChanged.connect(self.refresh_plot_panel)
        self.lin_radio.toggled.connect(self.refresh_plot_panel)
        self.log_radio.toggled.connect(self.refresh_plot_panel)
        self.auto_range_check.toggled.connect(self.refresh_plot_panel)

        controls_layout.addWidget(QLabel("View:"))
        controls_layout.addWidget(self.plot_view_combo)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(QLabel("Y scale:"))
        controls_layout.addWidget(self.lin_radio)
        controls_layout.addWidget(self.log_radio)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(self.auto_range_check)
        controls_layout.addStretch()

        plot_box = QGroupBox("Plot")
        plot_box_layout = QVBoxLayout(plot_box)
        plot_box_layout.setContentsMargins(8, 8, 8, 8)
        plot_box_layout.setSpacing(8)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        # self.figure.subplots_adjust(left=0.05, right=0.95, bottom=0.08, top=0.95)
        self.toolbar = PlotToolbar(self.canvas, self)

        self.ax.set_title("No data")
        self.ax.set_xlabel("Sample index")
        self.ax.set_ylabel("Voltage [V]")
        self._style_plot_axes()

        self.canvas.mpl_connect("scroll_event", self._on_scroll_zoom)

        plot_box_layout.addWidget(self.toolbar)
        plot_box_layout.addWidget(self.canvas)
        self.canvas.setStyleSheet("background-color: #1e1e1e;")

        info_box = QGroupBox("Plot Info")
        info_layout = QHBoxLayout(info_box)

        self.plot_info_label = QLabel("No data.")
        info_layout.addWidget(self.plot_info_label)
        info_layout.addStretch()

        layout.addWidget(controls)
        layout.addWidget(plot_box, 1)
        layout.addWidget(info_box)

    def current_view(self) -> str:
        if self.plot_view_combo is None:
            return ""
        return self.plot_view_combo.currentText()

    def _style_plot_axes(self):
        if self.figure is None or self.ax is None:
            return

        fig_bg = "#1e1e1e"
        ax_bg = "#252526"
        text_fg = "#d4d4d4"
        grid_c = "#3c3c3c"
        spine_c = "#6e6e6e"

        self.figure.patch.set_facecolor(fig_bg)
        self.ax.set_facecolor(ax_bg)

        self.ax.title.set_color(text_fg)
        self.ax.xaxis.label.set_color(text_fg)
        self.ax.yaxis.label.set_color(text_fg)

        self.ax.tick_params(axis="both", which="both", colors=text_fg)
        self.ax.tick_params(axis="both", labelsize=8)

        for spine in self.ax.spines.values():
            spine.set_color(spine_c)

        self.ax.grid(True, color=grid_c, linestyle=":", linewidth=0.8)

    def _set_y_scale_for_last_pulse(self):
        # Il last pulse resta sempre lineare: log qui non è robusto né semanticamente utile.
        self.ax.set_yscale("linear")

    def _set_y_scale_for_mca(self, spectrum):
        if self.log_radio is None or not self.log_radio.isChecked():
            self.ax.set_yscale("linear")
            return "linear"

        positive_values = [float(v) for v in spectrum if v > 0]
        if len(positive_values) == 0:
            self.ax.set_yscale("linear")
            return "linear"

        try:
            self.ax.set_yscale("log")
            return "log"
        except Exception:
            self.ax.set_yscale("linear")
            return "linear"

    def _apply_y_autorange_linear(self, values):
        if values is None:
            return

        if len(values) == 0:
            return

        y_min = float(min(values))
        y_max = float(max(values))

        if y_min == y_max:
            span = abs(y_min) * 0.05
            if span <= 0:
                span = 1.0
            self.ax.set_ylim(y_min - span, y_max + span)
            return

        pad = (y_max - y_min) * 0.05
        self.ax.set_ylim(y_min - pad, y_max + pad)

    def _apply_y_autorange_log(self, values):
        if values is None:
            return

        if len(values) == 0:
            return

        positive_values = [float(v) for v in values if v > 0]
        if len(positive_values) == 0:
            return

        y_max = max(positive_values)

        # For MCA counts, a log plot should start from 1, not from the minimum
        # positive bin content. Zero cannot be shown on a pure log axis.
        y_min = 1.0

        if y_max <= y_min:
            y_max = y_min * 1.2
        else:
            y_max = y_max * 1.1

        self.ax.set_ylim(y_min, y_max)

    def _apply_x_range_from_length(self, n_points: int):
        if n_points <= 0:
            return

        if n_points == 1:
            self.ax.set_xlim(-0.5, 0.5)
            return

        self.ax.set_xlim(0, n_points - 1)

    def refresh_plot_panel(self):
        if self.ax is None or self.canvas is None:
            return

        selected_view = self.current_view()

        self.ax.clear()
        self._style_plot_axes()
        self._reset_toolbar_history()

        text_fg = "#d4d4d4"
        signal_c = "#4fc1ff"
        baseline_c = "#c586c0"
        trigger_c = "#dcdcaa"
        peak_c = "#f44747"

        if selected_view == "MCA Spectrum":
            spectrum = self.controller.mca.spectrum

            self.ax.set_title("MCA Spectrum", color=text_fg, fontsize=10)
            self.ax.set_xlabel("Channel", color=text_fg, fontsize=9)
            self.ax.set_ylabel("Counts", color=text_fg, fontsize=9)

            if spectrum is None or len(spectrum) == 0:
                self.plot_info_label.setText("No MCA spectrum available.")
                self._style_plot_axes()
                self.canvas.draw_idle()
                if self.toolbar is not None:
                    self.toolbar.update()
                return

            self.ax.plot(spectrum, color=signal_c, linewidth=1.0)
            scale_mode = self._set_y_scale_for_mca(spectrum)

            self._apply_x_range_from_length(len(spectrum))

            if self.auto_range_check is not None and self.auto_range_check.isChecked():
                if scale_mode == "log":
                    self._apply_y_autorange_log(spectrum)
                else:
                    self._apply_y_autorange_linear(spectrum)

            # Re-apply styling after scale/locator changes, especially for log axes.
            self._style_plot_axes()

            summary = self.controller.mca_summary()
            scale_text = "Log" if scale_mode == "log" else "Lin"
            self.plot_info_label.setText(
                f"Scale={scale_text} | "
                f"Events={summary['event_count']} | "
                f"Accepted={summary['accepted_count']} | "
                f"Rejected={summary['rejected_count']} | "
                f"Counts={summary['total_counts_in_spectrum']} | "
                f"Elapsed={summary['elapsed_time_s']:.3f} s | "
                f"Rate={summary['accepted_rate_cps']:.3f} cps | "
                f"InstantaneousDeadTime={summary['dead_time_instant_percent']:.1f}% | "
                f"AverageDeadTime={summary['dead_time_average_percent']:.1f}%"
            )

            self.canvas.draw_idle()
            if self.toolbar is not None:
                self.toolbar.update()
            return

        buffer = self.controller.mca.last_buffer
        result = self.controller.mca.last_scope_result

        self.ax.set_title("Last Pulse", color=text_fg, fontsize=10)
        self.ax.set_xlabel("Sample index", color=text_fg, fontsize=9)
        self.ax.set_ylabel("Voltage [V]", color=text_fg, fontsize=9)

        if buffer is None or result is None:
            self.plot_info_label.setText("No captured pulse.")
            self._style_plot_axes()
            self.canvas.draw_idle()
            if self.toolbar is not None:
                self.toolbar.update()
            return

        self.ax.plot(buffer, color=signal_c, linewidth=1.2)

        self.ax.axhline(
            result.baseline,
            color=baseline_c,
            linestyle="--",
            linewidth=1.0,
        )
        self.ax.axvline(
            result.trigger_index_estimate,
            color=trigger_c,
            linestyle=":",
            linewidth=1.2,
        )
        self.ax.axvline(
            result.peak_index,
            color=peak_c,
            linestyle="-",
            linewidth=1.2,
        )

        self._set_y_scale_for_last_pulse()
        self._apply_x_range_from_length(len(buffer))

        if self.auto_range_check is not None and self.auto_range_check.isChecked():
            self._apply_y_autorange_linear(buffer)

        self._style_plot_axes()

        self.plot_info_label.setText(
            f"Peak={result.peak:.6f} V | "
            f"Baseline={result.baseline:.6f} V | "
            f"Amplitude={result.amplitude:.6f} V | "
            f"PeakIdx={result.peak_index} | "
            f"TriggerIdx={result.trigger_index_estimate} | "
            f"BaselineWindow=[{result.baseline_start}:{result.baseline_end}]"
        )

        self.canvas.draw_idle()
        if self.toolbar is not None:
            self.toolbar.update()

    def _on_scroll_zoom(self, event):
        if self.ax is None or self.canvas is None:
            return

        if event.xdata is None or event.ydata is None:
            return

        scale = 0.9 if event.button == "up" else 1.1

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        xdata = event.xdata
        ydata = event.ydata

        new_xlim = [
            xdata - (xdata - xlim[0]) * scale,
            xdata + (xlim[1] - xdata) * scale,
        ]

        yscale = self.ax.get_yscale()
        if yscale == "log":
            # In log scale y must remain strictly positive.
            if ydata <= 0:
                ydata = max(ylim[0], 1e-12)

            new_ymin = ydata - (ydata - ylim[0]) * scale
            new_ymax = ydata + (ylim[1] - ydata) * scale

            eps = 1e-12
            new_ymin = max(new_ymin, eps)
            new_ymax = max(new_ymax, new_ymin * (1.0 + 1e-6))

            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ymin, new_ymax)
        else:
            new_ylim = [
                ydata - (ydata - ylim[0]) * scale,
                ydata + (ylim[1] - ydata) * scale,
            ]
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)

        self.canvas.draw_idle()
        if self.toolbar is not None:
            self.toolbar.update()

    def _reset_toolbar_history(self):
        if self.toolbar is None:
            return

        try:
            self.toolbar._nav_stack.clear()
        except Exception:
            pass
