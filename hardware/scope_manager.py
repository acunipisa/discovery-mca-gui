from ctypes import *
import time
from threading import Event

from app.models import ScopeConfig, ScopeCaptureResult
from hardware.dwfconstants import (
    trigsrcDetectorAnalogIn,
    trigtypeEdge,
    trigcondRisingPositive,
    trigcondFallingNegative,
    DwfStateDone,
)


def _ct_val(x):
    return x.value if hasattr(x, "value") else x


class ScopeWaitCancelled(Exception):
    pass


class ScopeManager:
    def __init__(self, dwf_lib, hdwf):
        self.dwf = dwf_lib
        self.hdwf = hdwf

        self.config: ScopeConfig | None = None
        self.is_configured = False

        self._cancel_wait_event = Event()

        # Internal run state
        self._acquisition_running = False
        self._mode = "idle"  # "idle" | "manual" | "mca"

    def _check(self, ok, func_name: str):
        if ok:
            return
        err = create_string_buffer(512)
        self.dwf.FDwfGetLastErrorMsg(err)
        raise RuntimeError(f"{func_name} failed: {err.value.decode()}")

    def request_cancel_wait(self):
        self._cancel_wait_event.set()

    def clear_cancel_wait(self):
        self._cancel_wait_event.clear()

    def reset_state(self):
        self.clear_cancel_wait()
        try:
            self.dwf.FDwfAnalogInConfigure(self.hdwf, c_bool(False), c_bool(False))
        finally:
            self._acquisition_running = False
            self._mode = "idle"

    def configure_single_trigger(
        self,
        channel: int = 0,
        sample_rate_hz: float = 6.25e6,
        buffer_size: int = 512,
        input_range_v: float = 5.0,
        offset_v: float = 0.0,
        trigger_level_v: float = 0.1,
        trigger_rising: bool = True,
        pulse_polarity_positive: bool = True,
        pretrigger_samples: int | None = None,
        holdoff_s: float = 0.0,
    ):
        channel = int(channel)
        sample_rate_hz = float(sample_rate_hz)
        buffer_size = int(buffer_size)
        input_range_v = float(input_range_v)
        offset_v = float(offset_v)
        trigger_level_v = float(trigger_level_v)
        trigger_rising = bool(trigger_rising)
        pulse_polarity_positive = bool(pulse_polarity_positive)
        holdoff_s = float(holdoff_s)

        if holdoff_s < 0:
            raise ValueError(f"holdoff_s must be >= 0, got {holdoff_s}")

        expected_pretrigger = buffer_size // 2

        if (
            pretrigger_samples is not None
            and int(pretrigger_samples) != expected_pretrigger
        ):
            raise ValueError(
                "This ScopeManager is configured for symmetric trigger window only: "
                f"with buffer_size={buffer_size}, pretrigger_samples must be "
                f"{expected_pretrigger}, got {pretrigger_samples}."
            )

        self.reset_state()

        self._check(
            self.dwf.FDwfAnalogInConfigure(self.hdwf, c_bool(False), c_bool(False)),
            "FDwfAnalogInConfigure(stop-before-config)",
        )

        self._check(
            self.dwf.FDwfAnalogInFrequencySet(self.hdwf, c_double(sample_rate_hz)),
            "FDwfAnalogInFrequencySet",
        )
        self._check(
            self.dwf.FDwfAnalogInBufferSizeSet(self.hdwf, c_int(buffer_size)),
            "FDwfAnalogInBufferSizeSet",
        )

        self._check(
            self.dwf.FDwfAnalogInChannelEnableSet(
                self.hdwf, c_int(channel), c_bool(True)
            ),
            "FDwfAnalogInChannelEnableSet",
        )

        self._check(
            self.dwf.FDwfAnalogInChannelAttenuationSet(
                self.hdwf, c_int(channel), c_double(1.0)
            ),
            "FDwfAnalogInChannelAttenuationSet",
        )

        self._check(
            self.dwf.FDwfAnalogInChannelRangeSet(
                self.hdwf, c_int(channel), c_double(input_range_v)
            ),
            "FDwfAnalogInChannelRangeSet",
        )
        self._check(
            self.dwf.FDwfAnalogInChannelOffsetSet(
                self.hdwf, c_int(channel), c_double(offset_v)
            ),
            "FDwfAnalogInChannelOffsetSet",
        )

        self._check(
            self.dwf.FDwfAnalogInTriggerAutoTimeoutSet(self.hdwf, c_double(0.0)),
            "FDwfAnalogInTriggerAutoTimeoutSet",
        )

        self._check(
            self.dwf.FDwfAnalogInTriggerHoldOffSet(self.hdwf, c_double(holdoff_s)),
            "FDwfAnalogInTriggerHoldOffSet",
        )

        self._check(
            self.dwf.FDwfAnalogInTriggerSourceSet(
                self.hdwf, c_ubyte(_ct_val(trigsrcDetectorAnalogIn))
            ),
            "FDwfAnalogInTriggerSourceSet",
        )
        self._check(
            self.dwf.FDwfAnalogInTriggerTypeSet(
                self.hdwf, c_int(_ct_val(trigtypeEdge))
            ),
            "FDwfAnalogInTriggerTypeSet",
        )
        self._check(
            self.dwf.FDwfAnalogInTriggerChannelSet(self.hdwf, c_int(channel)),
            "FDwfAnalogInTriggerChannelSet",
        )
        self._check(
            self.dwf.FDwfAnalogInTriggerLevelSet(self.hdwf, c_double(trigger_level_v)),
            "FDwfAnalogInTriggerLevelSet",
        )

        trigger_condition = (
            trigcondRisingPositive if trigger_rising else trigcondFallingNegative
        )
        self._check(
            self.dwf.FDwfAnalogInTriggerConditionSet(
                self.hdwf,
                c_int(_ct_val(trigger_condition)),
            ),
            "FDwfAnalogInTriggerConditionSet",
        )

        self._check(
            self.dwf.FDwfAnalogInTriggerPositionSet(self.hdwf, c_double(0.0)),
            "FDwfAnalogInTriggerPositionSet",
        )

        self._check(
            self.dwf.FDwfAnalogInConfigure(self.hdwf, c_bool(True), c_bool(False)),
            "FDwfAnalogInConfigure(apply)",
        )

        time.sleep(0.05)

        self.config = ScopeConfig(
            sample_rate_hz=sample_rate_hz,
            buffer_size=buffer_size,
            input_range_v=input_range_v,
            offset_v=offset_v,
            trigger_level_v=trigger_level_v,
            trigger_rising=trigger_rising,
            pulse_polarity_positive=pulse_polarity_positive,
            channel=channel,
            pretrigger_samples=expected_pretrigger,
            holdoff_s=holdoff_s,
        )

        self.is_configured = True

    def start_manual_wait(self):
        if not self.is_configured:
            raise RuntimeError("Scope not configured")

        self.reset_state()
        self.clear_cancel_wait()

        self._check(
            self.dwf.FDwfAnalogInConfigure(self.hdwf, c_bool(False), c_bool(True)),
            "FDwfAnalogInConfigure(start-manual)",
        )
        self._acquisition_running = True
        self._mode = "manual"

    def start_mca_repeated(self):
        if not self.is_configured:
            raise RuntimeError("Scope not configured")

        self.reset_state()
        self.clear_cancel_wait()

        self._check(
            self.dwf.FDwfAnalogInConfigure(self.hdwf, c_bool(False), c_bool(True)),
            "FDwfAnalogInConfigure(start-mca)",
        )
        self._acquisition_running = True
        self._mode = "mca"

    def arm(self):
        self.start_manual_wait()

    def stop(self):
        self.clear_cancel_wait()
        try:
            self._check(
                self.dwf.FDwfAnalogInConfigure(self.hdwf, c_bool(False), c_bool(False)),
                "FDwfAnalogInConfigure(stop)",
            )
        finally:
            self._acquisition_running = False
            self._mode = "idle"

    def wait_for_trigger_and_read(
        self, channel: int = 0, buffer_size: int = 512
    ) -> tuple[list[float], float]:
        channel = int(channel)
        buffer_size = int(buffer_size)

        if not self._acquisition_running:
            raise RuntimeError("Scope acquisition not started.")

        sts = c_byte()

        try:
            while True:
                if self._cancel_wait_event.is_set():
                    raise ScopeWaitCancelled("Capture waiting cancelled by user.")

                self._check(
                    self.dwf.FDwfAnalogInStatus(self.hdwf, c_int(1), byref(sts)),
                    "FDwfAnalogInStatus",
                )

                if sts.value == _ct_val(DwfStateDone):
                    t_trigger_done = time.perf_counter()
                    break

            data = (c_double * buffer_size)()
            self._check(
                self.dwf.FDwfAnalogInStatusData(
                    self.hdwf, c_int(channel), data, c_int(buffer_size)
                ),
                "FDwfAnalogInStatusData",
            )

            return list(data), t_trigger_done
        finally:
            self.clear_cancel_wait()

    @staticmethod
    def estimate_trigger_crossing(
        samples: list[float],
        trigger_level_v: float,
        trigger_rising: bool = True,
    ) -> int | None:
        if len(samples) < 2:
            return None

        for i in range(1, len(samples)):
            prev_v = samples[i - 1]
            curr_v = samples[i]

            if trigger_rising:
                if prev_v < trigger_level_v and curr_v >= trigger_level_v:
                    return i
            else:
                if prev_v > trigger_level_v and curr_v <= trigger_level_v:
                    return i

        return None

    def process_buffer(
        self,
        samples: list[float],
        sample_rate_hz: float,
        trigger_index_estimate: int | None = None,
        baseline_width: int = 64,
        baseline_center_offset: int = 128,
        pulse_polarity_positive: bool | None = None,
    ) -> ScopeCaptureResult:
        n = len(samples)
        if n == 0:
            raise ValueError("Empty samples")

        if self.config is None:
            raise RuntimeError("Scope not configured")

        if pulse_polarity_positive is None:
            pulse_polarity_positive = self.config.pulse_polarity_positive

        if trigger_index_estimate is None:
            trigger_index_estimate = self.config.pretrigger_samples

        trigger_index = self.estimate_trigger_crossing(
            samples,
            trigger_level_v=self.config.trigger_level_v,
            trigger_rising=self.config.trigger_rising,
        )

        if trigger_index is None:
            trigger_index = trigger_index_estimate

        center = trigger_index - baseline_center_offset
        start = max(0, center - baseline_width // 2)
        end = min(n, start + baseline_width)
        if end <= start:
            raise ValueError("Invalid baseline window")

        baseline_slice = samples[start:end]
        baseline = sum(baseline_slice) / len(baseline_slice)

        if pulse_polarity_positive:
            peak = max(samples)
            amplitude = peak - baseline
        else:
            peak = min(samples)
            amplitude = baseline - peak

        peak_index = samples.index(peak)

        return ScopeCaptureResult(
            samples=samples,
            peak=peak,
            baseline=baseline,
            amplitude=abs(amplitude),
            peak_index=peak_index,
            trigger_index_estimate=trigger_index,
            baseline_start=start,
            baseline_end=end,
            sample_rate_hz=sample_rate_hz,
        )
