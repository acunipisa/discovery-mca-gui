from app.defaults import (
    BASELINE_CENTER_OFFSET,
    BASELINE_WIDTH,
    BUFFER_SIZE,
    HV_CHANNEL,
    INPUT_RANGE_V,
    OFFSET_V,
    SAMPLE_RATE_HZ,
    TEST_PULSE_CHANNEL,
    TRIGGER_CHANNEL,
    TRIGGER_INDEX_ESTIMATE,
    HOLDOFF_S,
    build_default_mca_config,
)
from hardware.device_manager import DeviceManager
from hardware.hv_manager import HVManager
from analysis.mca_manager import MCAManager
from app.models import (
    AppState,
    ControllerStatusSnapshot,
    MCAConfig,
    MCAStatusSnapshot,
    ScopeSetupSummary,
    ScopeConfig,
)
from hardware.power_supply_manager import PowerSupplyManager
from hardware.scope_manager import ScopeCaptureResult, ScopeManager
from hardware.test_pulse_manager import TestPulseManager
from analysis.mca_io import save_spectrum_csv, save_spectrum_html
from analysis.mca_plotting import plot_last_buffer, plot_spectrum


class DiscoveryMCAController:
    def __init__(self, mca_config: MCAConfig | None = None):
        self.device = DeviceManager()
        self.power: PowerSupplyManager | None = None
        self.scope: ScopeManager | None = None
        self.hv: HVManager | None = None
        self.test_pulse: TestPulseManager | None = None

        self.scope_configured = False
        self.state = AppState.DISCONNECTED

        self.mca = MCAManager(mca_config or build_default_mca_config())
        self.mca_configured = False

    def open(self):
        if self.device.is_open:
            return

        self.device.open()
        self.power = PowerSupplyManager(self.device.dwf, self.device.hdwf)
        self.scope = ScopeManager(self.device.dwf, self.device.hdwf)
        self.hv = HVManager(self.device.dwf, self.device.hdwf)
        self.test_pulse = TestPulseManager(
            self.device.dwf,
            self.device.hdwf,
            channel=TEST_PULSE_CHANNEL,
        )
        self.state = AppState.IDLE

    def close(self):
        if self.device.is_open:
            try:
                if self.power is not None:
                    self.power.disable_all_supplies()
            except Exception:
                pass
            self.device.close()

        self.power = None
        self.scope = None
        self.hv = None
        self.test_pulse = None
        self.scope_configured = False
        self.state = AppState.DISCONNECTED

    def _require_open(self):
        if not self.device.is_open:
            raise RuntimeError("Device not open")

    def _require_scope(self) -> ScopeManager:
        self._require_open()
        if self.scope is None:
            raise RuntimeError("Scope manager not initialized")
        return self.scope

    def _require_power(self) -> PowerSupplyManager:
        self._require_open()
        if self.power is None:
            raise RuntimeError("Power manager not initialized")
        return self.power

    def _require_hv(self) -> HVManager:
        self._require_open()
        if self.hv is None:
            raise RuntimeError("HV manager not initialized")
        return self.hv

    def _require_test_pulse(self) -> TestPulseManager:
        self._require_open()
        if self.test_pulse is None:
            raise RuntimeError("Test pulse manager not initialized")
        return self.test_pulse

    # =========================
    # POWER
    # =========================

    def read_supply_status(self) -> dict:
        return self._require_power().read_supply_status()

    def enable_positive_supply(self, voltage: float = 5.0):
        power = self._require_power()
        power.set_positive_supply(voltage, enabled=True)
        power.set_master_enable(True)

    def disable_positive_supply(self):
        self._require_power().disable_positive_supply()

    def enable_negative_supply(self, voltage_magnitude: float = 5.0):
        power = self._require_power()
        power.set_negative_supply(voltage_magnitude, enabled=True)
        power.set_master_enable(True)

    def disable_negative_supply(self):
        self._require_power().disable_negative_supply()

    def disable_all_supplies(self):
        self._require_power().disable_all_supplies()

    # =========================
    # SCOPE
    # =========================

    def configure_scope(
        self,
        trigger_level_v: float = 0.2,
        trigger_rising: bool = True,
        pulse_polarity_positive: bool = True,
        channel: int = TRIGGER_CHANNEL,
        sample_rate_hz: float = SAMPLE_RATE_HZ,
        buffer_size: int = BUFFER_SIZE,
        input_range_v: float = INPUT_RANGE_V,
        offset_v: float = OFFSET_V,
        pretrigger_samples: int = TRIGGER_INDEX_ESTIMATE,
        holdoff_s: float = HOLDOFF_S,
    ) -> ScopeSetupSummary:
        scope = self._require_scope()

        scope.configure_single_trigger(
            channel=channel,
            sample_rate_hz=sample_rate_hz,
            buffer_size=buffer_size,
            input_range_v=input_range_v,
            offset_v=offset_v,
            trigger_level_v=trigger_level_v,
            trigger_rising=trigger_rising,
            pulse_polarity_positive=pulse_polarity_positive,
            pretrigger_samples=pretrigger_samples,
            holdoff_s=holdoff_s,
        )

        self.scope_configured = True
        self.state = AppState.SCOPE_CONFIGURED

        cfg = scope.config
        if cfg is None:
            raise RuntimeError("Scope configuration failed.")

        return ScopeSetupSummary(
            sample_rate_hz=cfg.sample_rate_hz,
            buffer_size=cfg.buffer_size,
            expected_trigger_index=cfg.pretrigger_samples,
            trigger_level_v=cfg.trigger_level_v,
            trigger_rising=cfg.trigger_rising,
            pulse_polarity_positive=cfg.pulse_polarity_positive,
            input_range_v=cfg.input_range_v,
            offset_v=cfg.offset_v,
            channel=cfg.channel,
            holdoff_s=cfg.holdoff_s,
        )

    def get_scope_config(self) -> ScopeConfig | None:
        if not self.scope_configured or self.scope is None:
            return None
        return self.scope.config

    def ensure_scope_configured(self):
        if not self.scope_configured:
            raise RuntimeError("Scope not configured yet. Configure it first.")

    def arm_scope(self):
        self.ensure_scope_configured()
        self._require_scope().arm()

    def stop_scope(self):
        self.ensure_scope_configured()
        self._require_scope().stop()

    def cancel_capture_waiting(self):
        self.ensure_scope_configured()
        self._require_scope().request_cancel_wait()

    def capture_once(self) -> ScopeCaptureResult:
        self.ensure_scope_configured()
        scope = self._require_scope()
        cfg = scope.config
        if cfg is None:
            raise RuntimeError("Scope not configured.")

        scope.clear_cancel_wait()
        scope.arm()

        samples, _ = scope.wait_for_trigger_and_read(
            channel=cfg.channel,
            buffer_size=cfg.buffer_size,
        )

        scope_result = scope.process_buffer(
            samples=samples,
            sample_rate_hz=cfg.sample_rate_hz,
            trigger_index_estimate=cfg.pretrigger_samples,
            baseline_width=BASELINE_WIDTH,
            baseline_center_offset=BASELINE_CENTER_OFFSET,
            pulse_polarity_positive=cfg.pulse_polarity_positive,
        )

        self.mca.last_buffer = samples.copy()
        self.mca.last_scope_result = scope_result

        return scope_result

    # =========================
    # HV
    # =========================

    def set_hv_voltage(self, voltage_v: float, channel: int = HV_CHANNEL) -> float:
        hv = self._require_hv()
        hv.set_voltage(voltage_v, channel=channel)
        return hv.get_voltage(channel=channel)

    def stop_hv(self, channel: int = HV_CHANNEL, force_zero: bool = True):
        self._require_hv().stop(channel=channel, force_zero=force_zero)

    def get_hv_voltage(self, channel: int = HV_CHANNEL) -> float:
        return self._require_hv().get_voltage(channel=channel)

    # =========================
    # MCA
    # =========================

    def configure_mca(
        self,
        n_channels: int,
        voltage_min: float,
        voltage_max: float,
    ) -> MCAConfig:
        if self.mca.running:
            raise RuntimeError("Cannot change MCA configuration while MCA is running.")

        n_channels = int(n_channels)
        voltage_min = float(voltage_min)
        voltage_max = float(voltage_max)

        if n_channels <= 0:
            raise ValueError("n_channels must be > 0.")
        if voltage_max <= voltage_min:
            raise ValueError("voltage_max must be greater than voltage_min.")
        if voltage_min < 0:
            raise ValueError("voltage_min must be >= 0.")

        self.mca.config.n_channels = n_channels
        self.mca.config.voltage_min = voltage_min
        self.mca.config.voltage_max = voltage_max

        self.mca.clear()
        self.mca_configured = True

        return self.get_mca_config()

    def get_mca_config(self) -> MCAConfig | None:
        if not self.mca_configured:
            return None

        cfg = self.mca.config
        return MCAConfig(
            n_channels=cfg.n_channels,
            voltage_min=cfg.voltage_min,
            voltage_max=cfg.voltage_max,
            baseline_width=cfg.baseline_width,
            baseline_center_offset=cfg.baseline_center_offset,
            trigger_index_estimate=cfg.trigger_index_estimate,
        )

    def ensure_mca_configured(self):
        if not self.mca_configured:
            raise RuntimeError("MCA not configured yet. Apply MCA configuration first.")

    def start_mca(
        self,
        status_period_s: float = 1.0,
        duration_s: float | None = None,
        status_callback=None,
    ):
        self.ensure_scope_configured()
        self.ensure_mca_configured()
        scope = self._require_scope()

        try:
            self.state = AppState.MCA_RUNNING
            self.mca.run_forever(
                scope,
                status_period_s=status_period_s,
                duration_s=duration_s,
                status_callback=status_callback,
            )
        finally:
            self.state = (
                AppState.SCOPE_CONFIGURED if self.scope_configured else AppState.IDLE
            )

    def stop_mca(self):
        self.mca.stop()

        if self.scope_configured and self.scope is not None:
            try:
                self.scope.request_cancel_wait()
            except Exception:
                pass

    def clear_mca(self):
        self.mca.clear()

    def mca_summary(self) -> dict:
        return self.mca.spectrum_summary()

    def save_mca_csv(self, filepath: str):
        save_spectrum_csv(self.mca.spectrum, filepath)

    def save_mca_html(self, filepath: str):
        save_spectrum_html(self.mca.spectrum, filepath)

    def plot_mca(self):
        plot_spectrum(self.mca.spectrum)

    def plot_last_buffer(self):
        plot_last_buffer(self.mca.last_buffer, self.mca.last_scope_result)

    # =========================
    # TEST PULSE
    # =========================

    def start_test_pulse_ramp(
        self,
        frequency_hz: float = 100.0,
        amplitude_v: float = 1.0,
        offset_v: float = -1.0,
        symmetry_percent: float = 100.0,
        phase_deg: float = 0.0,
    ):
        self._require_test_pulse().start_ramp_up(
            frequency_hz=frequency_hz,
            amplitude_v=amplitude_v,
            offset_v=offset_v,
            symmetry_percent=symmetry_percent,
            phase_deg=phase_deg,
        )

    def stop_test_pulse(self, force_zero: bool = False):
        self._require_test_pulse().stop(force_zero=force_zero)

    # =========================
    # STATUS
    # =========================

    def get_state(self) -> AppState:
        return self.state

    def get_mca_status_snapshot(self) -> MCAStatusSnapshot:
        summary = self.mca.spectrum_summary()
        return MCAStatusSnapshot(
            running=self.mca.running,
            event_count=self.mca.event_count,
            accepted_count=self.mca.accepted_count,
            rejected_count=self.mca.rejected_count,
            overflow_count=self.mca.overflow_count,
            underflow_count=self.mca.underflow_count,
            elapsed_time_s=summary["elapsed_time_s"],
            accepted_rate_cps=summary["accepted_rate_cps"],
            total_counts_in_spectrum=summary["total_counts_in_spectrum"],
            has_last_result=self.mca.last_result is not None,
            has_last_buffer=self.mca.last_buffer is not None,
        )

    def get_controller_status_snapshot(self) -> ControllerStatusSnapshot:
        return ControllerStatusSnapshot(
            state=self.state,
            device_open=self.device.is_open,
            scope_configured=self.scope_configured,
            has_power_manager=self.power is not None,
            has_scope_manager=self.scope is not None,
            has_hv_manager=self.hv is not None,
            has_test_pulse_manager=self.test_pulse is not None,
        )

    def start_test_pulse(
        self,
        mode: str,
        frequency_hz: float,
        amplitude_v: float,
        offset_v: float,
        symmetry_percent: float,
        phase_deg: float = 0.0,
    ):
        tp = self._require_test_pulse()

        mode = str(mode).strip().lower()

        if mode == "ramp_up":
            tp.start_ramp_up(
                frequency_hz=frequency_hz,
                amplitude_v=amplitude_v,
                offset_v=offset_v,
                symmetry_percent=symmetry_percent,
                phase_deg=phase_deg,
            )
            return

        if mode == "pulse":
            tp.start_pulse(
                frequency_hz=frequency_hz,
                amplitude_v=amplitude_v,
                offset_v=offset_v,
                duty_cycle_percent=symmetry_percent,
                phase_deg=phase_deg,
            )
            return

        raise ValueError(f"Unsupported test pulse mode: {mode}")
