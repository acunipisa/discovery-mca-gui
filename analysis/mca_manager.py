from dataclasses import dataclass
import time
from queue import Queue, Full, Empty
from threading import Thread

import numpy as np

from app.models import MCAConfig
from hardware.scope_manager import ScopeWaitCancelled
import ctypes
from ctypes import wintypes


def _set_current_thread_high_priority():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    THREAD_PRIORITY_HIGHEST = 2

    kernel32.GetCurrentThread.restype = wintypes.HANDLE
    kernel32.GetCurrentThread.argtypes = []

    kernel32.SetThreadPriority.restype = wintypes.BOOL
    kernel32.SetThreadPriority.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
    ]

    hthread = kernel32.GetCurrentThread()

    ok = kernel32.SetThreadPriority(hthread, THREAD_PRIORITY_HIGHEST)
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


@dataclass
class MCAEventResult:
    accepted: bool
    peak: float
    baseline: float
    amplitude: float
    bin_index: int | None
    peak_index: int
    baseline_start: int
    baseline_end: int


class MCAManager:
    def __init__(self, config: MCAConfig | None = None):
        self.config = config or MCAConfig()

        self.spectrum = None
        self.running = False

        self.event_count = 0
        self.accepted_count = 0
        self.rejected_count = 0
        self.overflow_count = 0
        self.underflow_count = 0

        self.last_result: MCAEventResult | None = None
        self.start_time: float | None = None

        self.acquisition_time_s = 0.0
        self.run_start_time = None

        self.last_buffer = None
        self.last_scope_result = None

        self.last_status_interval_s = 0.0
        self.last_status_event_delta = 0
        self.last_status_accepted_delta = 0
        self.last_status_rejected_delta = 0
        self.last_status_overflow_delta = 0
        self.last_status_underflow_delta = 0

        self.total_dead_time_s = 0.0
        self.last_dead_time_s = 0.0
        self.last_status_dead_time_delta_s = 0.0
        self.last_status_dead_time_percent = 0.0

        self._processing_queue = Queue(maxsize=256)
        self._processing_thread: Thread | None = None
        self._dropped_buffers = 0

        self.arm_count = 0
        self.triggered_read_count = 0
        self.processed_count = 0

        self._status_callback = None
        self._status_period_s = 1.0
        self._last_status_clock = 0.0
        self._prev_event_count = 0
        self._prev_accepted_count = 0
        self._prev_rejected_count = 0
        self._prev_overflow_count = 0
        self._prev_underflow_count = 0
        self._prev_total_dead_time_s = 0.0

    def clear(self):
        self.spectrum = None
        self.running = False

        self.event_count = 0
        self.accepted_count = 0
        self.rejected_count = 0
        self.overflow_count = 0
        self.underflow_count = 0

        self.last_result = None
        self.start_time = None

        self.acquisition_time_s = 0.0
        self.run_start_time = None

        self.last_buffer = None
        self.last_scope_result = None

        self.last_status_interval_s = 0.0
        self.last_status_event_delta = 0
        self.last_status_accepted_delta = 0
        self.last_status_rejected_delta = 0
        self.last_status_overflow_delta = 0
        self.last_status_underflow_delta = 0

        self.total_dead_time_s = 0.0
        self.last_dead_time_s = 0.0
        self.last_status_dead_time_delta_s = 0.0
        self.last_status_dead_time_percent = 0.0

        self._processing_queue = Queue(maxsize=256)
        self._processing_thread = None
        self._dropped_buffers = 0

        self.arm_count = 0
        self.triggered_read_count = 0
        self.processed_count = 0

        self._status_callback = None
        self._status_period_s = 1.0
        self._last_status_clock = 0.0
        self._prev_event_count = 0
        self._prev_accepted_count = 0
        self._prev_rejected_count = 0
        self._prev_overflow_count = 0
        self._prev_underflow_count = 0
        self._prev_total_dead_time_s = 0.0

    def amplitude_to_bin(self, amplitude: float) -> int | None:
        vmin = self.config.voltage_min
        vmax = self.config.voltage_max
        n_channels = self.config.n_channels

        if amplitude < vmin:
            self.underflow_count += 1
            return None

        if amplitude >= vmax:
            self.overflow_count += 1
            return n_channels - 1

        span = vmax - vmin
        return int((amplitude - vmin) / span * n_channels)

    def process_event(self, scope_result) -> MCAEventResult:
        amplitude = scope_result.amplitude
        peak = scope_result.peak
        baseline = scope_result.baseline

        bin_index = self.amplitude_to_bin(amplitude)

        accepted = bin_index is not None
        if accepted:
            if self.spectrum is None:
                self.spectrum = np.zeros(self.config.n_channels, dtype=np.uint32)
            self.spectrum[bin_index] += 1
            self.accepted_count += 1
        else:
            self.rejected_count += 1

        result = MCAEventResult(
            accepted=accepted,
            peak=peak,
            baseline=baseline,
            amplitude=amplitude,
            bin_index=bin_index,
            peak_index=scope_result.peak_index,
            baseline_start=scope_result.baseline_start,
            baseline_end=scope_result.baseline_end,
        )

        self.last_result = result
        return result

    def _process_samples(self, scope, samples) -> MCAEventResult:
        cfg = scope.config
        if cfg is None:
            raise RuntimeError("Scope not configured.")

        self.last_buffer = samples.copy()

        scope_result = scope.process_buffer(
            samples=samples,
            sample_rate_hz=cfg.sample_rate_hz,
            trigger_index_estimate=self.config.trigger_index_estimate,
            baseline_width=self.config.baseline_width,
            baseline_center_offset=self.config.baseline_center_offset,
            pulse_polarity_positive=cfg.pulse_polarity_positive,
        )

        self.last_scope_result = scope_result
        self.event_count += 1
        self.processed_count += 1
        return self.process_event(scope_result)

    def _estimate_trigger_time_from_capture(
        self,
        scope,
        samples,
        trigger_done_time: float,
    ) -> float:
        cfg = scope.config
        if cfg is None:
            return trigger_done_time

        trigger_index = scope.estimate_trigger_crossing(
            samples,
            trigger_level_v=cfg.trigger_level_v,
            trigger_rising=cfg.trigger_rising,
        )

        if trigger_index is None:
            trigger_index = self.config.trigger_index_estimate

        trigger_index = max(0, min(int(trigger_index), len(samples) - 1))

        fs = float(cfg.sample_rate_hz)
        if fs <= 0:
            return trigger_done_time

        samples_after_trigger = len(samples) - trigger_index
        dt_after_trigger_s = samples_after_trigger / fs

        return trigger_done_time - dt_after_trigger_s

    def _store_status_deltas(
        self,
        interval_s: float,
        prev_event_count: int,
        prev_accepted_count: int,
        prev_rejected_count: int,
        prev_overflow_count: int,
        prev_underflow_count: int,
        prev_total_dead_time_s: float,
    ):
        self.last_status_interval_s = interval_s
        self.last_status_event_delta = self.event_count - prev_event_count
        self.last_status_accepted_delta = self.accepted_count - prev_accepted_count
        self.last_status_rejected_delta = self.rejected_count - prev_rejected_count
        self.last_status_overflow_delta = self.overflow_count - prev_overflow_count
        self.last_status_underflow_delta = self.underflow_count - prev_underflow_count
        self.last_status_dead_time_delta_s = (
            self.total_dead_time_s - prev_total_dead_time_s
        )
        self.last_status_dead_time_percent = (
            100.0 * self.last_status_dead_time_delta_s / interval_s
            if interval_s > 0
            else 0.0
        )

    def _maybe_emit_status(self):
        now_clock = time.monotonic()
        interval_s = now_clock - self._last_status_clock

        if interval_s < self._status_period_s:
            return

        self._store_status_deltas(
            interval_s=interval_s,
            prev_event_count=self._prev_event_count,
            prev_accepted_count=self._prev_accepted_count,
            prev_rejected_count=self._prev_rejected_count,
            prev_overflow_count=self._prev_overflow_count,
            prev_underflow_count=self._prev_underflow_count,
            prev_total_dead_time_s=self._prev_total_dead_time_s,
        )

        self._last_status_clock = now_clock
        self._prev_event_count = self.event_count
        self._prev_accepted_count = self.accepted_count
        self._prev_rejected_count = self.rejected_count
        self._prev_overflow_count = self.overflow_count
        self._prev_underflow_count = self.underflow_count
        self._prev_total_dead_time_s = self.total_dead_time_s

        if self._status_callback is not None:
            self._status_callback(self, self.last_result)

    def _emit_final_status_if_needed(self):
        if self.event_count == self._prev_event_count:
            return

        final_interval_s = time.monotonic() - self._last_status_clock
        if final_interval_s <= 0:
            return

        self._store_status_deltas(
            interval_s=final_interval_s,
            prev_event_count=self._prev_event_count,
            prev_accepted_count=self._prev_accepted_count,
            prev_rejected_count=self._prev_rejected_count,
            prev_overflow_count=self._prev_overflow_count,
            prev_underflow_count=self._prev_underflow_count,
            prev_total_dead_time_s=self._prev_total_dead_time_s,
        )

        if self._status_callback is not None:
            self._status_callback(self, self.last_result)

    def _processing_loop(self, scope):
        while True:
            try:
                item = self._processing_queue.get(timeout=0.05)
            except Empty:
                continue

            if item is None:
                self._processing_queue.task_done()
                break

            samples, trigger_done_time, t_read_done = item

            try:
                trigger_time_est = self._estimate_trigger_time_from_capture(
                    scope,
                    samples,
                    trigger_done_time,
                )

                dead_time_s = t_read_done - trigger_time_est
                if dead_time_s < 0:
                    dead_time_s = 0.0

                self.last_dead_time_s = dead_time_s
                self.total_dead_time_s += dead_time_s

                self._process_samples(scope, samples)
                self._maybe_emit_status()
            finally:
                self._processing_queue.task_done()

    def _start_processing_thread(self, scope):
        self._processing_thread = Thread(
            target=self._processing_loop,
            args=(scope,),
            daemon=True,
        )
        self._processing_thread.start()

    def _stop_processing_thread(self):
        if self._processing_thread is not None:
            self._processing_thread.join(timeout=2.0)
            self._processing_thread = None

    def run_forever(
        self,
        scope,
        status_period_s: float = 1.0,
        duration_s: float | None = None,
        status_callback=None,
    ):
        self.running = True
        self.run_start_time = time.time()

        status_period_s = float(status_period_s)
        if status_period_s <= 0:
            raise ValueError("status_period_s must be > 0.")

        cfg = scope.config
        if cfg is None:
            raise RuntimeError("Scope not configured.")

        try:
            _set_current_thread_high_priority()
        except OSError as e:
            print(f"Warning: could not raise MCA thread priority: {e}")

        self._status_callback = status_callback
        self._status_period_s = status_period_s
        self._last_status_clock = time.monotonic()
        self._prev_event_count = self.event_count
        self._prev_accepted_count = self.accepted_count
        self._prev_rejected_count = self.rejected_count
        self._prev_overflow_count = self.overflow_count
        self._prev_underflow_count = self.underflow_count
        self._prev_total_dead_time_s = self.total_dead_time_s

        self._start_processing_thread(scope)

        try:
            scope.start_mca_repeated()
            self.arm_count += 1

            while self.running:
                if duration_s is not None:
                    elapsed_this_run = time.time() - self.run_start_time
                    if elapsed_this_run >= duration_s:
                        self.stop()
                        break

                try:
                    samples, trigger_done_time = scope.wait_for_trigger_and_read(
                        channel=cfg.channel,
                        buffer_size=cfg.buffer_size,
                    )
                except ScopeWaitCancelled:
                    if not self.running:
                        break
                    raise

                self.triggered_read_count += 1
                t_read_done = time.perf_counter()

                try:
                    self._processing_queue.put_nowait(
                        (samples, trigger_done_time, t_read_done)
                    )
                except Full:
                    self._dropped_buffers += 1

        except KeyboardInterrupt:
            self.stop()
            raise
        finally:
            self.running = False
            self.run_start_time = None

            try:
                scope.stop()
            finally:
                self._processing_queue.put(None)
                self._processing_queue.join()
                self._emit_final_status_if_needed()
                self._stop_processing_thread()

    def stop(self):
        if self.running and self.run_start_time is not None:
            self.acquisition_time_s += time.time() - self.run_start_time

        self.running = False
        self.run_start_time = None

    def elapsed_time_s(self) -> float:
        elapsed = self.acquisition_time_s

        if self.running and self.run_start_time is not None:
            elapsed += time.time() - self.run_start_time

        return elapsed

    def instantaneous_accepted_rate_cps(self) -> float:
        if self.last_status_interval_s <= 0:
            return 0.0
        return self.last_status_accepted_delta / self.last_status_interval_s

    def average_accepted_rate_cps(self) -> float:
        elapsed = self.elapsed_time_s()
        return self.accepted_count / elapsed if elapsed > 0 else 0.0

    def print_status_line(self, result: MCAEventResult | None = None):
        if result is None:
            result = self.last_result

        inst_cps = self.instantaneous_accepted_rate_cps()
        avg_cps = self.average_accepted_rate_cps()
        inst_dead_pct = self.instantaneous_dead_time_percent()
        avg_dead_pct = self.average_dead_time_percent()

        if result is None:
            print(
                f"events={self.event_count} "
                f"accepted={self.accepted_count} "
                f"rejected={self.rejected_count} "
                f"overflow={self.overflow_count} "
                f"underflow={self.underflow_count} "
                f"inst_cps={inst_cps:.2f} "
                f"avg_cps={avg_cps:.2f} "
                f"dead_inst={inst_dead_pct:.1f}% "
                f"dead_avg={avg_dead_pct:.1f}% "
                f"arms={self.arm_count} "
                f"reads={self.triggered_read_count} "
                f"processed={self.processed_count} "
                f"dropped={self._dropped_buffers}"
            )
            return

        print(
            f"events={self.event_count} "
            f"accepted={self.accepted_count} "
            f"rejected={self.rejected_count} "
            f"overflow={self.overflow_count} "
            f"underflow={self.underflow_count} "
            f"inst_cps={inst_cps:.2f} "
            f"avg_cps={avg_cps:.2f} "
            f"dead_inst={inst_dead_pct:.1f}% "
            f"dead_avg={avg_dead_pct:.1f}% "
            f"arms={self.arm_count} "
            f"reads={self.triggered_read_count} "
            f"processed={self.processed_count} "
            f"dropped={self._dropped_buffers} "
            f"last_amp={result.amplitude:.6f} V "
            f"last_bin={result.bin_index}"
        )

    def spectrum_summary(self) -> dict:
        elapsed = self.elapsed_time_s()
        rate = self.average_accepted_rate_cps()
        total_counts = int(self.spectrum.sum()) if self.spectrum is not None else 0

        return {
            "n_channels": self.config.n_channels,
            "voltage_min": self.config.voltage_min,
            "voltage_max": self.config.voltage_max,
            "event_count": self.event_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "overflow_count": self.overflow_count,
            "underflow_count": self.underflow_count,
            "elapsed_time_s": elapsed,
            "accepted_rate_cps": rate,
            "dead_time_instant_percent": self.instantaneous_dead_time_percent(),
            "dead_time_average_percent": self.average_dead_time_percent(),
            "total_counts_in_spectrum": total_counts,
            "arm_count": self.arm_count,
            "triggered_read_count": self.triggered_read_count,
            "processed_count": self.processed_count,
            "dropped_buffers": self._dropped_buffers,
        }

    def instantaneous_dead_time_percent(self) -> float:
        return self.last_status_dead_time_percent

    def average_dead_time_percent(self) -> float:
        elapsed = self.elapsed_time_s()
        if elapsed <= 0:
            return 0.0
        return 100.0 * self.total_dead_time_s / elapsed
