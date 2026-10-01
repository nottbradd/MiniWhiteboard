"""Cocoa floating windows; desktop geometry stays in top-left-origin points."""
import ctypes

from PySide6.QtCore import Qt
from ..base import Display, QtDesktop
from ...geometry import Rect
from ...settings import RADIUS


def native_window(widget):
    import objc
    # Qt owns this NSView and NSWindow. Never release or replace them.
    view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
    return view.window()


class MacDesktop(QtDesktop):
    shadow_margin = 0
    paints_shadow = False

    def board_flags(self):
        # A Window can receive keyboard focus; floating level is set explicitly.
        return Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint

    def displays(self):
        import AppKit
        import Quartz
        displays = []
        seen = set()
        for screen in AppKit.NSScreen.screens():
            identifier = int(screen.deviceDescription()["NSScreenNumber"])
            if identifier in seen:
                continue
            seen.add(identifier)
            bounds = Quartz.CGDisplayBounds(identifier)
            displays.append(Display(str(screen.localizedName()),
                                    Rect(bounds.origin.x, bounds.origin.y, bounds.size.width, bounds.size.height),
                                    float(screen.backingScaleFactor()), identifier))
        return displays

    def configure_board(self, board):
        import AppKit
        window = native_window(board)
        window.setLevel_(AppKit.NSFloatingWindowLevel)
        window.setHidesOnDeactivate_(False)
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.setHasShadow_(True)
        # No CanJoinAllSpaces or FullScreenAuxiliary: retain normal Space membership.
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorManaged)
        view = window.contentView()
        view.setWantsLayer_(True)
        layer = view.layer()
        layer.setCornerRadius_(RADIUS)
        layer.setMasksToBounds_(True)

    def sync_decoration(self, board):
        if board.isVisible() and not board._closing:
            self.configure_board(board)
            native_window(board).invalidateShadow()

    def configure_overlay(self, overlay, *, interactive=False, owner=None):
        import AppKit
        window = native_window(overlay)
        window.setLevel_(AppKit.NSFloatingWindowLevel + 1)
        window.setHidesOnDeactivate_(False)
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.setHasShadow_(False)
        window.setIgnoresMouseEvents_(not interactive)
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorTransient |
                                      AppKit.NSWindowCollectionBehaviorIgnoresCycle)
        if owner is not None:
            parent = native_window(owner)
            if window.parentWindow() != parent:
                parent.addChildWindow_ordered_(window, AppKit.NSWindowAbove)

    def focus_window(self, widget):
        import AppKit
        widget.show()
        self.configure_board(widget)
        window = native_window(widget)
        # Activation happens only on creation/explicit restore, never in a timer
        # maintaining Z order. Move an explicitly restored board to this Space.
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorManaged |
                                      AppKit.NSWindowCollectionBehaviorMoveToActiveSpace)
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        window.makeKeyAndOrderFront_(None)
        widget.activateWindow()
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorManaged)

    def capture_window_identifier(self, widget):
        return int(native_window(widget).windowNumber())
