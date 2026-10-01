"""Offscreen Qt tests do not take over the desktop or global hotkeys."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import sys
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


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
