from ctypes import *


def _dwf_const_to_int(x):
    if hasattr(x, "value"):
        x = x.value

    if isinstance(x, (bytes, bytearray)):
        if len(x) != 1:
            raise ValueError(f"Expected 1-byte DWF constant, got {x!r}")
        return x[0]

    return int(x)


class DeviceManager:
    def __init__(self):
        self.dwf = cdll.dwf
        self.hdwf = c_int()
        self.is_open = False

    def open(self):
        if self.is_open:
            return

        err = create_string_buffer(512)

        if not self.dwf.FDwfDeviceOpen(c_int(-1), byref(self.hdwf)):
            self.dwf.FDwfGetLastErrorMsg(err)
            raise RuntimeError(f"FDwfDeviceOpen failed: {err.value.decode()}")

        self.dwf.FDwfDeviceAutoConfigureSet(self.hdwf, c_int(0))
        self.is_open = True

    def close(self):
        if self.is_open:
            self.dwf.FDwfDeviceClose(self.hdwf)
            self.is_open = False

    def check_open(self):
        if not self.is_open:
            raise RuntimeError("Device not open")
