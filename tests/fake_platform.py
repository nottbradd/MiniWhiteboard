"""Controllable platform services with no native global registration or capture."""
from mini_whiteboard.platform.base import (Platform, QtDesktop, QtRuntime, Display,
                                         HotkeyEvents, CREATE_HOTKEY, CAPTURE_HOTKEY)
from mini_whiteboard.geometry import Rect
from mini_whiteboard.shortcuts import ShortcutPolicy


class FakeDesktop(QtDesktop):
    shadow_margin = 0
    paints_shadow = False

    def __init__(self):
        self.cursor = (40, 40)
        self.screens = [Display("Retina", Rect(0, 0, 1200, 800), 2, 10),
                        Display("Left", Rect(-1200, -100, 1200, 800), 1, 20)]

    def cursor_position(self):
        return self.cursor

    def displays(self):
        return self.screens


class FakeHotkeys:
    def __init__(self, app=None, preset="default"):
        self.events = HotkeyEvents()
        self.registered = set()
        self.escape = False
        self.preset = preset

    def start(self):
        self.registered.update((CREATE_HOTKEY, CAPTURE_HOTKEY))

    def enable_escape(self):
        self.escape = True

    def disable_escape(self):
        self.escape = False

    def set_preset(self, preset):
        self.preset = preset
        self.registered.clear()

    def close(self):
        self.registered.clear()


class FakeCapture:
    def __init__(self):
        self.requests = []
        self.denial = None

    def prepare(self):
        if self.denial:
            raise self.denial

    def capture_region(self, rect, success, failure, excluded=()):
        self.requests.append((rect, success, failure, excluded))

    def cancel(self):
        pass


def fake_platform():
    return Platform("fake", QtRuntime(), FakeDesktop(), FakeCapture(), FakeHotkeys, ShortcutPolicy(mac=True))
