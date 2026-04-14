from ctypes import *

from hardware.dwfconstants import (
    AnalogOutNodeCarrier,
    funcTriangle,
    funcPulse,
)


def _ct_val(x):
    return x.value if hasattr(x, "value") else x


class TestPulseManager:
    MODE_TRIANGLE = "triangle"
    MODE_PULSE = "pulse"

    def __init__(self, dwf_lib, hdwf, channel: int = 1):
        self.dwf = dwf_lib
        self.hdwf = hdwf
        self.channel = int(channel)
        self.is_running = False

        self.mode = None
        self.frequency_hz = None
        self.amplitude_v = None
        self.offset_v = None
        self.symmetry_percent = None
        self.phase_deg = None

    def _check(self, ok, func_name: str):
        if ok:
            return
        err = create_string_buffer(512)
        self.dwf.FDwfGetLastErrorMsg(err)
        raise RuntimeError(f"{func_name} failed: {err.value.decode()}")

    def _set_node_enabled(self, enabled: bool):
        self._check(
            self.dwf.FDwfAnalogOutNodeEnableSet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_bool(enabled),
            ),
            "FDwfAnalogOutNodeEnableSet",
        )

    def _set_function(self, mode: str):
        if mode == self.MODE_TRIANGLE:
            func = funcTriangle
        elif mode == self.MODE_PULSE:
            func = funcPulse
        else:
            raise ValueError(f"Unsupported waveform mode: {mode}")

        self._check(
            self.dwf.FDwfAnalogOutNodeFunctionSet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_ubyte(_ct_val(func)),
            ),
            "FDwfAnalogOutNodeFunctionSet",
        )

    @staticmethod
    def _validate_frequency(frequency_hz: float) -> float:
        frequency_hz = float(frequency_hz)
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0.")
        return frequency_hz

    @staticmethod
    def _validate_amplitude(amplitude_v: float) -> float:
        amplitude_v = float(amplitude_v)
        if amplitude_v < 0:
            raise ValueError("amplitude_v must be >= 0.")
        return amplitude_v

    @staticmethod
    def _validate_offset(offset_v: float) -> float:
        return float(offset_v)

    @staticmethod
    def _validate_symmetry(symmetry_percent: float) -> float:
        symmetry_percent = float(symmetry_percent)
        if not (0.0 <= symmetry_percent <= 100.0):
            raise ValueError("symmetry_percent must be between 0 and 100.")
        return symmetry_percent

    @staticmethod
    def _validate_phase(phase_deg: float) -> float:
        return float(phase_deg)

    def configure_waveform(
        self,
        mode: str,
        frequency_hz: float,
        amplitude_v: float,
        offset_v: float,
        symmetry_percent: float,
        phase_deg: float = 0.0,
    ):
        mode = str(mode).strip().lower()

        if mode not in (self.MODE_TRIANGLE, self.MODE_PULSE):
            raise ValueError(f"Unsupported waveform mode: {mode}")

        frequency_hz = self._validate_frequency(frequency_hz)
        amplitude_v = self._validate_amplitude(amplitude_v)
        offset_v = self._validate_offset(offset_v)
        symmetry_percent = self._validate_symmetry(symmetry_percent)
        phase_deg = self._validate_phase(phase_deg)

        self._set_node_enabled(True)
        self._set_function(mode)

        self._check(
            self.dwf.FDwfAnalogOutNodeFrequencySet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(frequency_hz),
            ),
            "FDwfAnalogOutNodeFrequencySet",
        )

        self._check(
            self.dwf.FDwfAnalogOutNodeAmplitudeSet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(amplitude_v),
            ),
            "FDwfAnalogOutNodeAmplitudeSet",
        )

        self._check(
            self.dwf.FDwfAnalogOutNodeOffsetSet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(offset_v),
            ),
            "FDwfAnalogOutNodeOffsetSet",
        )

        self._check(
            self.dwf.FDwfAnalogOutNodeSymmetrySet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(symmetry_percent),
            ),
            "FDwfAnalogOutNodeSymmetrySet",
        )

        self._check(
            self.dwf.FDwfAnalogOutNodePhaseSet(
                self.hdwf,
                c_int(self.channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(phase_deg),
            ),
            "FDwfAnalogOutNodePhaseSet",
        )

        self.mode = mode
        self.frequency_hz = frequency_hz
        self.amplitude_v = amplitude_v
        self.offset_v = offset_v
        self.symmetry_percent = symmetry_percent
        self.phase_deg = phase_deg

    def configure_triangle(
        self,
        frequency_hz: float = 100.0,
        amplitude_v: float = 1.0,
        offset_v: float = 0.0,
        symmetry_percent: float = 0.0,
        phase_deg: float = 0.0,
    ):
        self.configure_waveform(
            mode=self.MODE_TRIANGLE,
            frequency_hz=frequency_hz,
            amplitude_v=amplitude_v,
            offset_v=offset_v,
            symmetry_percent=symmetry_percent,
            phase_deg=phase_deg,
        )

    def configure_pulse(
        self,
        frequency_hz: float = 1000.0,
        amplitude_v: float = 1.0,
        offset_v: float = 0.0,
        duty_cycle_percent: float = 1.0,
        phase_deg: float = 0.0,
    ):
        self.configure_waveform(
            mode=self.MODE_PULSE,
            frequency_hz=frequency_hz,
            amplitude_v=amplitude_v,
            offset_v=offset_v,
            symmetry_percent=duty_cycle_percent,
            phase_deg=phase_deg,
        )

    def start(self):
        self._check(
            self.dwf.FDwfAnalogOutConfigure(
                self.hdwf,
                c_int(self.channel),
                c_bool(True),
            ),
            "FDwfAnalogOutConfigure(start)",
        )
        self.is_running = True

    def stop(self, force_zero: bool = False):
        if force_zero:
            self._check(
                self.dwf.FDwfAnalogOutNodeAmplitudeSet(
                    self.hdwf,
                    c_int(self.channel),
                    c_int(_ct_val(AnalogOutNodeCarrier)),
                    c_double(0.0),
                ),
                "FDwfAnalogOutNodeAmplitudeSet(0)",
            )
            self._check(
                self.dwf.FDwfAnalogOutNodeOffsetSet(
                    self.hdwf,
                    c_int(self.channel),
                    c_int(_ct_val(AnalogOutNodeCarrier)),
                    c_double(0.0),
                ),
                "FDwfAnalogOutNodeOffsetSet(0)",
            )

        self._check(
            self.dwf.FDwfAnalogOutConfigure(
                self.hdwf,
                c_int(self.channel),
                c_bool(False),
            ),
            "FDwfAnalogOutConfigure(stop)",
        )
        self.is_running = False

    def start_triangle(
        self,
        frequency_hz: float = 100.0,
        amplitude_v: float = 1.0,
        offset_v: float = 0.0,
        symmetry_percent: float = 0.0,
        phase_deg: float = 0.0,
    ):
        self.configure_triangle(
            frequency_hz=frequency_hz,
            amplitude_v=amplitude_v,
            offset_v=offset_v,
            symmetry_percent=symmetry_percent,
            phase_deg=phase_deg,
        )
        self.start()

    def start_pulse(
        self,
        frequency_hz: float = 1000.0,
        amplitude_v: float = 1.0,
        offset_v: float = 0.0,
        duty_cycle_percent: float = 1.0,
        phase_deg: float = 0.0,
    ):
        self.configure_pulse(
            frequency_hz=frequency_hz,
            amplitude_v=amplitude_v,
            offset_v=offset_v,
            duty_cycle_percent=duty_cycle_percent,
            phase_deg=phase_deg,
        )
        self.start()

    def get_config_summary(self) -> dict:
        return {
            "channel": self.channel,
            "is_running": self.is_running,
            "mode": self.mode,
            "frequency_hz": self.frequency_hz,
            "amplitude_v": self.amplitude_v,
            "offset_v": self.offset_v,
            "symmetry_percent": self.symmetry_percent,
            "phase_deg": self.phase_deg,
        }
