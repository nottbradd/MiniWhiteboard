"""Accessory application lifetime and one local lock, without a helper service."""
import os
from pathlib import Path
import platform

from PySide6.QtCore import QLockFile
from ..base import QtRuntime

BUNDLE_ID = "com.brad.miniwhiteboard"


class MacInstance:
    def __init__(self, directory=None):
        directory = Path(directory or Path.home()/"Library"/"Application Support"/BUNDLE_ID)
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(directory/"instance.lock"))
        # A long-running tray app must not be declared stale because of its age.
        # QLockFile still checks whether the owning process has exited.
        self.lock.setStaleLockTime(0)
        self.acquired = self.lock.tryLock(0)
        self.owner_pid = None
        if not self.acquired:
            pid, _host, _app = self.lock.getLockInfo()
            if not pid or pid < 0:
                raise OSError("Mini Whiteboard could not acquire its local instance lock.")
            self.owner_pid = pid

    def close(self):
        if self.acquired:
            self.lock.unlock()
            self.acquired = False


class MacRuntime(QtRuntime):
    persist_preferences = True

    def prepare(self):
        if int(platform.mac_ver()[0].split(".")[0] or 0) < 14:
            raise OSError("Mini Whiteboard requires macOS 14 or later.")

    def single_instance(self):
        return MacInstance()

    def configure_application(self, app):
        import AppKit
        app.setOrganizationName("MiniWhiteboard")
        # Keep Qt's NSApplication delegate and event loop. Only change policy.
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    def activate_existing(self, guard):
        import AppKit
        if guard.owner_pid and guard.owner_pid != os.getpid():
            running = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(guard.owner_pid)
            if running is not None:
                running.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
