"""Offscreen Qt tests do not take over the desktop or global hotkeys."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import sys
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEvent
from PySide6.QtTest import QTest

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


def wait_until(predicate, timeout_ms):
    """Pump short event-loop turns within a fixed wall-clock assertion budget.

    A single long qWait can return with an overdue Python timer callback still
    queued on the macOS offscreen dispatcher. Short turns service those callbacks
    without increasing the deadline or ignoring a failed completion condition.
    """
    clock = QElapsedTimer()
    clock.start()
    while not predicate():
        remaining = timeout_ms-clock.elapsed()
        if remaining <= 0:
            return False
        QTest.qWait(min(5,remaining))
    return clock.elapsed() <= timeout_ms


class QtCase(unittest.TestCase):
    def setUp(self):
        self.native_patch = patch("mini_whiteboard.windows.IS_WINDOWS", False)
        self.native_patch.start()
        # Legacy regression fixtures deliberately emulate the Windows desktop;
        # new platform tests inject independent point-coordinate services.
        from mini_whiteboard.platform.windows import create_platform
        self.platform_patch = patch("mini_whiteboard.platform._platform", create_platform())
        self.platform_patch.start()
        self.widgets = []
        self.exceptions = []
        self.old_hook = sys.excepthook
        sys.excepthook = lambda kind, value, tb: self.exceptions.append(value)

    def tearDown(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        APP.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.native_patch.stop()
        self.platform_patch.stop()
        sys.excepthook = self.old_hook
        self.assertEqual(self.exceptions, [], "Unhandled Qt callback exception")
