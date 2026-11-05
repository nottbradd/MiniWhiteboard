"""Retain a gesture's first release while the GUI thread prepares its preview.

Only the configured creation keys/modifiers and Escape are sampled. The worker
has no Qt objects, hooks or keyboard text, and stops at release or cancellation.
It is idle between gestures. The GUI still owns every window and native binding.
"""
from dataclasses import dataclass
import threading
import time


@dataclass(frozen=True)
class EndPoint:
    point: tuple | None
    cancelled: bool = False
    error: str | None = None


class ReleaseWatch:
    def __init__(self, sample, cursor):
        self.sample, self.cursor = sample, cursor
        self.identifier = None
        self.result = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def begin(self, identifier):
        self.stop()
        self.identifier, self.result = identifier, None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='MiniWhiteboard release', daemon=True)
        self._thread.start()

    def observe(self, state):
        """Both samplers share one immutable first result; later motion loses."""
        with self._lock:
            if self.result is None and self.identifier is not None and not self._stop.is_set():
                if state[2]:
                    self.result = EndPoint(None, cancelled=True)
                elif self.identifier not in state[1]:
                    self.result = EndPoint(tuple(self.cursor()))
            return self.result

    def _run(self):
        try:
            while not self._stop.is_set():
                if self.observe(self.sample()) is not None:
                    return
                # Python's Windows sleep uses a high-resolution waitable timer.
                # This is a sampling interval, not a hard real-time guarantee.
                time.sleep(.001)
        except Exception as error:
            with self._lock:
                if self.result is None and not self._stop.is_set():
                    self.result = EndPoint(None, error=str(error))

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(.1)
            if self._thread.is_alive():
                raise OSError('Creation release observer did not stop.')
            self._thread = None

