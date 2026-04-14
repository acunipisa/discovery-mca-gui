import os
import ctypes
from ctypes import wintypes
import psutil

from frontends.gui_app import main

# Win32 constants
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x2
ProcessPowerThrottling = 4


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("ControlMask", wintypes.ULONG),
        ("StateMask", wintypes.ULONG),
    ]


def disable_process_power_throttling():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # Proper signatures for 64-bit safety
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []

    kernel32.SetProcessInformation.restype = wintypes.BOOL
    kernel32.SetProcessInformation.argtypes = [
        wintypes.HANDLE,  # hProcess
        wintypes.DWORD,  # ProcessInformationClass
        wintypes.LPVOID,  # ProcessInformation
        wintypes.DWORD,  # ProcessInformationSize
    ]

    state = PROCESS_POWER_THROTTLING_STATE()
    state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
    state.ControlMask = (
        PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION
    )
    # 0 means: do not enable those throttling flags
    state.StateMask = 0

    hproc = kernel32.GetCurrentProcess()

    ok = kernel32.SetProcessInformation(
        hproc,
        ProcessPowerThrottling,
        ctypes.byref(state),
        ctypes.sizeof(state),
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


def boost_process_priority():
    p = psutil.Process(os.getpid())
    p.nice(psutil.HIGH_PRIORITY_CLASS)


if __name__ == "__main__":
    boost_process_priority()

    try:
        disable_process_power_throttling()
    except OSError as e:
        print(f"Warning: could not disable process power throttling: {e}")

    main()
