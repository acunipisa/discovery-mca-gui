from dataclasses import dataclass
from enum import Enum


@dataclass
class MCAConfig:
    n_channels: int = 1024
    voltage_min: float = 0.0
    voltage_max: float = 5.0
    baseline_width: int = 64
    baseline_center_offset: int = 128
    trigger_index_estimate: int = 256


@dataclass
class ScopeConfig:
    sample_rate_hz: float
    buffer_size: int
    input_range_v: float
    offset_v: float
    trigger_level_v: float
    trigger_rising: bool
    pulse_polarity_positive: bool
    channel: int
    pretrigger_samples: int
    holdoff_s: float


@dataclass
class ScopeSetupSummary:
    sample_rate_hz: float
    buffer_size: int
    expected_trigger_index: int
    trigger_level_v: float
    trigger_rising: bool
    pulse_polarity_positive: bool
    input_range_v: float
    offset_v: float
    channel: int
    holdoff_s: float


class AppState(str, Enum):
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    SCOPE_CONFIGURED = "scope_configured"
    MCA_RUNNING = "mca_running"


@dataclass
class MCAStatusSnapshot:
    running: bool
    event_count: int
    accepted_count: int
    rejected_count: int
    overflow_count: int
    underflow_count: int
    elapsed_time_s: float
    accepted_rate_cps: float
    total_counts_in_spectrum: int
    has_last_result: bool
    has_last_buffer: bool


@dataclass
class ScopeCaptureResult:
    samples: list[float]
    peak: float
    baseline: float
    amplitude: float
    peak_index: int
    trigger_index_estimate: int
    baseline_start: int
    baseline_end: int
    sample_rate_hz: float


@dataclass
class ControllerStatusSnapshot:
    state: AppState
    device_open: bool
    scope_configured: bool
    has_power_manager: bool
    has_scope_manager: bool
    has_hv_manager: bool
    has_test_pulse_manager: bool
