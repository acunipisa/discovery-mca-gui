from ctypes import *

from hardware.dwfconstants import AnalogOutNodeCarrier, funcDC


def _ct_val(x):
    return x.value if hasattr(x, "value") else x


class HVManager:
    def __init__(self, dwf_lib, hdwf):
        self.dwf = dwf_lib
        self.hdwf = hdwf
        self.channel = 0
        self.is_configured = False
        self.last_voltage_v = 0.0

    def _check(self, ok, func_name: str):
        if ok:
            return
        err = create_string_buffer(512)
        self.dwf.FDwfGetLastErrorMsg(err)
        raise RuntimeError(f"{func_name} failed: {err.value.decode()}")

    def set_voltage(self, voltage_v: float, channel: int = 0):
        voltage_v = float(voltage_v)
        channel = int(channel)

        if voltage_v < 0.0 or voltage_v > 1.2:
            raise ValueError("Voltage must be in the range 0.0 .. 1.2 V")

        self.channel = channel

        self._check(
            self.dwf.FDwfAnalogOutNodeEnableSet(
                self.hdwf,
                c_int(channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_bool(True),
            ),
            "FDwfAnalogOutNodeEnableSet",
        )
        self._check(
            self.dwf.FDwfAnalogOutNodeFunctionSet(
                self.hdwf,
                c_int(channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_ubyte(_ct_val(funcDC)),
            ),
            "FDwfAnalogOutNodeFunctionSet",
        )
        self._check(
            self.dwf.FDwfAnalogOutNodeAmplitudeSet(
                self.hdwf,
                c_int(channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(0.0),
            ),
            "FDwfAnalogOutNodeAmplitudeSet",
        )
        self._check(
            self.dwf.FDwfAnalogOutNodeOffsetSet(
                self.hdwf,
                c_int(channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                c_double(voltage_v),
            ),
            "FDwfAnalogOutNodeOffsetSet",
        )
        self._check(
            self.dwf.FDwfAnalogOutConfigure(self.hdwf, c_int(channel), c_bool(True)),
            "FDwfAnalogOutConfigure",
        )

        self.is_configured = True
        self.last_voltage_v = voltage_v

    def stop(self, channel: int | None = None, force_zero: bool = True):
        if channel is None:
            channel = self.channel

        channel = int(channel)

        if force_zero:
            self._check(
                self.dwf.FDwfAnalogOutNodeOffsetSet(
                    self.hdwf,
                    c_int(channel),
                    c_int(_ct_val(AnalogOutNodeCarrier)),
                    c_double(0.0),
                ),
                "FDwfAnalogOutNodeOffsetSet(0)",
            )
            self._check(
                self.dwf.FDwfAnalogOutNodeAmplitudeSet(
                    self.hdwf,
                    c_int(channel),
                    c_int(_ct_val(AnalogOutNodeCarrier)),
                    c_double(0.0),
                ),
                "FDwfAnalogOutNodeAmplitudeSet(0)",
            )

        self._check(
            self.dwf.FDwfAnalogOutConfigure(self.hdwf, c_int(channel), c_bool(False)),
            "FDwfAnalogOutConfigure(stop)",
        )

        if force_zero:
            self.last_voltage_v = 0.0

    def get_voltage(self, channel: int | None = None) -> float:
        if channel is None:
            channel = self.channel

        channel = int(channel)
        value = c_double()

        self._check(
            self.dwf.FDwfAnalogOutNodeOffsetGet(
                self.hdwf,
                c_int(channel),
                c_int(_ct_val(AnalogOutNodeCarrier)),
                byref(value),
            ),
            "FDwfAnalogOutNodeOffsetGet",
        )
        return value.value
