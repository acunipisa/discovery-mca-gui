from ctypes import *


class PowerSupplyManager:
    def __init__(self, dwf_lib, hdwf):
        self.dwf = dwf_lib
        self.hdwf = hdwf

    def _check(self, ok, func_name: str):
        if ok:
            return
        err = create_string_buffer(512)
        self.dwf.FDwfGetLastErrorMsg(err)
        raise RuntimeError(f"{func_name} failed: {err.value.decode()}")

    def _check_open(self):
        if self.hdwf is None:
            raise RuntimeError("Invalid device handle")

    def _configure_analog_io(self):
        self._check_open()
        self._check(
            self.dwf.FDwfAnalogIOConfigure(self.hdwf),
            "FDwfAnalogIOConfigure",
        )

    def _refresh_analog_io_status(self):
        self._check_open()
        self._check(
            self.dwf.FDwfAnalogIOStatus(self.hdwf),
            "FDwfAnalogIOStatus",
        )

    def set_master_enable(self, enabled: bool):
        self._check_open()
        self._check(
            self.dwf.FDwfAnalogIOEnableSet(self.hdwf, c_int(1 if enabled else 0)),
            "FDwfAnalogIOEnableSet",
        )
        self._configure_analog_io()

    def set_positive_supply(self, voltage: float, enabled: bool = True):
        self._check_open()

        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(0), c_int(1), c_double(voltage)
            ),
            "FDwfAnalogIOChannelNodeSet(+ voltage)",
        )
        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(0), c_int(0), c_double(1.0 if enabled else 0.0)
            ),
            "FDwfAnalogIOChannelNodeSet(+ enable)",
        )
        self._configure_analog_io()

    def set_negative_supply(self, voltage: float, enabled: bool = True):
        self._check_open()

        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(1), c_int(1), c_double(voltage)
            ),
            "FDwfAnalogIOChannelNodeSet(- voltage)",
        )
        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(1), c_int(0), c_double(1.0 if enabled else 0.0)
            ),
            "FDwfAnalogIOChannelNodeSet(- enable)",
        )
        self._configure_analog_io()

    def disable_positive_supply(self):
        self._check_open()
        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(0), c_int(0), c_double(0.0)
            ),
            "FDwfAnalogIOChannelNodeSet(+ disable)",
        )
        self._configure_analog_io()

    def disable_negative_supply(self):
        self._check_open()
        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(1), c_int(0), c_double(0.0)
            ),
            "FDwfAnalogIOChannelNodeSet(- disable)",
        )
        self._configure_analog_io()

    def disable_all_supplies(self):
        self._check_open()
        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(0), c_int(0), c_double(0.0)
            ),
            "FDwfAnalogIOChannelNodeSet(+ disable)",
        )
        self._check(
            self.dwf.FDwfAnalogIOChannelNodeSet(
                self.hdwf, c_int(1), c_int(0), c_double(0.0)
            ),
            "FDwfAnalogIOChannelNodeSet(- disable)",
        )
        self._check(
            self.dwf.FDwfAnalogIOEnableSet(self.hdwf, c_int(0)),
            "FDwfAnalogIOEnableSet(0)",
        )
        self._configure_analog_io()

    def read_supply_status(self):
        self._check_open()
        self._refresh_analog_io_status()

        master_on = c_int()
        pos_en = c_double()
        pos_v = c_double()
        pos_i = c_double()
        neg_en = c_double()
        neg_v = c_double()
        neg_i = c_double()

        self.dwf.FDwfAnalogIOEnableStatus(self.hdwf, byref(master_on))
        self.dwf.FDwfAnalogIOChannelNodeStatus(
            self.hdwf, c_int(0), c_int(0), byref(pos_en)
        )
        self.dwf.FDwfAnalogIOChannelNodeStatus(
            self.hdwf, c_int(0), c_int(1), byref(pos_v)
        )
        self.dwf.FDwfAnalogIOChannelNodeStatus(
            self.hdwf, c_int(0), c_int(2), byref(pos_i)
        )
        self.dwf.FDwfAnalogIOChannelNodeStatus(
            self.hdwf, c_int(1), c_int(0), byref(neg_en)
        )
        self.dwf.FDwfAnalogIOChannelNodeStatus(
            self.hdwf, c_int(1), c_int(1), byref(neg_v)
        )
        self.dwf.FDwfAnalogIOChannelNodeStatus(
            self.hdwf, c_int(1), c_int(2), byref(neg_i)
        )

        return {
            "master_enable": bool(master_on.value),
            "positive": {
                "enabled": bool(pos_en.value),
                "voltage": pos_v.value,
                "current": pos_i.value,
            },
            "negative": {
                "enabled": bool(neg_en.value),
                "voltage": neg_v.value,
                "current": neg_i.value,
            },
        }
