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

    def display_policy(self):
        import AppKit
        from ...appearance import DisplayPolicy
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        high = bool(workspace.accessibilityDisplayShouldIncreaseContrast())
        return DisplayPolicy(
            transparency=not workspace.accessibilityDisplayShouldReduceTransparency() and not high,
            motion=not workspace.accessibilityDisplayShouldReduceMotion(), high_contrast=high)

    def apply_appearance(self, board):
        import AppKit
        if getattr(board, '_appearance_observer', None) is None:
            from Foundation import NSOperationQueue
            def policy_changed(_notification):
                if not board._closing:
                    board.refresh_appearance()
            centre = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
            board._appearance_observer = centre.addObserverForName_object_queue_usingBlock_(
                AppKit.NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification, None,
                NSOperationQueue.mainQueue(), policy_changed)
        if board.appearance_theme != 'Glass' or not board.display_policy.transparency:
            record = getattr(board, '_visual_effect', None)
            if record is not None:
                record[1].removeFromSuperview()
                board._visual_effect = None
            return False
        try:
            window = native_window(board)
            content = window.contentView()
            record = getattr(board, '_visual_effect', None)
            if record is not None and record[0] != content:
                self.release_appearance(board)
                record = None
            if record is None:
                parent = content.superview()
                if parent is None:
                    return False
                effect = AppKit.NSVisualEffectView.alloc().initWithFrame_(content.frame())
                effect.setMaterial_(AppKit.NSVisualEffectMaterialUnderWindowBackground)
                effect.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
                effect.setState_(AppKit.NSVisualEffectStateActive)
                effect.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameAqua))
                effect.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
                effect.setWantsLayer_(True)
                effect.layer().setCornerRadius_(board.corner_radius())
                effect.layer().setMasksToBounds_(True)
                parent.addSubview_positioned_relativeTo_(effect, AppKit.NSWindowBelow, content)
                board._visual_effect = (content, effect, parent)
            return True
        except (AttributeError, RuntimeError, ValueError):
            self.release_appearance(board)
            return False

    def release_appearance(self, board):
        record = getattr(board, '_visual_effect', None)
        if record is not None:
            record[1].removeFromSuperview()
            board._visual_effect = None
        observer = getattr(board, '_appearance_observer', None)
        if observer is not None:
            import AppKit
            AppKit.NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(observer)
            board._appearance_observer = None

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
        layer.setCornerRadius_(board.corner_radius())
        layer.setMasksToBounds_(True)

    def sync_decoration(self, board):
        if board.isVisible() and not board._closing:
            self.configure_board(board)
            window = native_window(board)
            record = getattr(board, '_visual_effect', None)
            if record is not None and (record[0] != window.contentView()
                                        or record[2] != window.contentView().superview()):
                board.refresh_appearance()
            window.invalidateShadow()

    def sync_surface(self, surface):
        if not surface.isVisible():
            return
        window = native_window(surface)
        content = window.contentView()
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(surface.corner_radius())
        content.layer().setMasksToBounds_(True)
        window.setHasShadow_(True)
        record = getattr(surface, '_visual_effect', None)
        if record is not None and (record[0] != content or record[2] != content.superview()):
            surface.refresh_appearance()
        window.invalidateShadow()

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

    def show_without_activating(self, widget):
        super().show_without_activating(widget)
        self.configure_board(widget)
        native_window(widget).orderFrontRegardless()

    def board_order(self, boards):
        import AppKit
        lookup = {int(native_window(board).windowNumber()): board for board in boards}
        ordered = [lookup[int(window.windowNumber())] for window in
                   AppKit.NSApplication.sharedApplication().orderedWindows()
                   if int(window.windowNumber()) in lookup]
        return list(reversed(ordered))
