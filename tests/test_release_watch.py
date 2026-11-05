"""Release observations must survive a blocked GUI and later pointer movement."""
import threading
import time
import unittest
from mini_whiteboard.platform.windows.release_watch import ReleaseWatch


class ReleaseWatchTests(unittest.TestCase):
    def setUp(self):
        self.state = ({1}, {1}, False)
        self.point = (540, 440)
        self.read = threading.Event()
        self.watch = ReleaseWatch(lambda: self.state, self.cursor)
        self.addCleanup(self.watch.stop)

    def cursor(self):
        point = self.point
        self.read.set()
        return point

    def wait_result(self):
        until = time.monotonic()+1
        while self.watch.result is None and time.monotonic()<until:
            time.sleep(.001)
        self.assertIsNotNone(self.watch.result)
        return self.watch.result

    def test_retains_first_release_without_gui_dispatch(self):
        self.watch.begin(1)
        self.state = ({1}, set(), False)  # A modifier released, trigger still held.
        self.assertTrue(self.read.wait(1))
        self.point = (700, 500)
        self.assertEqual(self.wait_result().point, (540, 440))
        self.watch.observe((set(), set(), False))
        self.assertEqual(self.watch.result.point, (540, 440))

    def test_escape_cannot_become_a_late_release(self):
        self.watch.begin(1)
        self.state = ({1}, {1}, True)
        self.assertTrue(self.wait_result().cancelled)
        self.watch.observe((set(), set(), False))
        self.assertIsNone(self.watch.result.point)
        self.assertFalse(self.read.is_set())

    def test_cancelled_observer_stops_and_next_gesture_is_independent(self):
        self.watch.begin(1)
        self.watch.stop()
        self.state = (set(), set(), False)
        self.assertIsNone(self.watch.observe(self.state))
        self.watch.begin(2)
        self.assertEqual(self.wait_result().point, self.point)
        self.watch.stop()
        self.assertFalse(any(t.name=='MiniWhiteboard release' for t in threading.enumerate()))

    def test_sampling_failure_is_reported_without_a_position(self):
        def fail():
            raise OSError('sample unavailable')
        self.watch.sample = fail
        self.watch.begin(1)
        end = self.wait_result()
        self.assertEqual(end.error, 'sample unavailable')
        self.assertIsNone(end.point)
