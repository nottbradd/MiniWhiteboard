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

    def available_finish(self, requested, policy, screen=None):
        import AppKit
        from ...appearance import FROSTED, LIQUID, OPAQUE
        if requested == 'White':
            return requested
        if policy.high_contrast or not policy.transparency:
            return OPAQUE
        if requested == LIQUID and getattr(AppKit, 'NSGlassEffectView', None) is not None:
            return LIQUID
        return FROSTED

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
        from ...appearance import FROSTED, LIQUID
        if getattr(board, '_appearance_observer', None) is None:
            from Foundation import NSOperationQueue
            def policy_changed(_notification):
                if not board._closing:
                    board.refresh_appearance()
            centre = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
            board._appearance_observer = centre.addObserverForName_object_queue_usingBlock_(
                AppKit.NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification, None,
                NSOperationQueue.mainQueue(), policy_changed)
        finish = self.available_finish(board.appearance_theme, board.display_policy)
        if getattr(board, 'screenshot_surface', False) or finish not in (LIQUID, FROSTED):
            self.remove_material(board)
            return False
        record = getattr(board, '_visual_effect', None)
        try:
            content = native_window(board).contentView()
            parent = content.superview()
            if record is not None and (record[0] != content or record[2] != parent):
                self.remove_material(board)
                record = None
            if parent is None:
                return False
            if record is not None:
                self.sync_material(board)
                return board._native_finish
        except (AttributeError, RuntimeError, ValueError):
            self.remove_material(board)
            return False
        # Failure to install one native view can still leave the other material
        # available. Keep the accessibility observer through either failure.
        for candidate in ((LIQUID, FROSTED) if finish == LIQUID else (FROSTED,)):
            effect = None
            try:
                if candidate == LIQUID:
                    effect = AppKit.NSGlassEffectView.alloc().initWithFrame_(content.frame())
                    effect.setStyle_(AppKit.NSGlassEffectViewStyleClear)
                    effect.setCornerRadius_(board.corner_radius())
                else:
                    effect = AppKit.NSVisualEffectView.alloc().initWithFrame_(content.frame())
                    effect.setMaterial_(AppKit.NSVisualEffectMaterialPopover)
                    effect.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
                    effect.setState_(AppKit.NSVisualEffectStateActive)
                    effect.setAlphaValue_(0.77)
                effect.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameAqua))
                effect.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
                effect.setWantsLayer_(True)
                effect.layer().setCornerRadius_(board.corner_radius())
                effect.layer().setMasksToBounds_(True)
                parent.addSubview_positioned_relativeTo_(effect, AppKit.NSWindowBelow, content)
                board._visual_effect = (content, effect, parent)
                board._native_finish = candidate
                self.sync_material(board)
                return candidate
            except (AttributeError, RuntimeError, ValueError):
                if effect is not None:
                    effect.removeFromSuperview()
                board._visual_effect = None
        return False

    def sync_material(self, surface):
        record = getattr(surface, '_visual_effect', None)
        if record is None:
            return
        content, effect, _parent = record
        paper = surface.paper_rect()
        frame, bounds = content.frame(), content.bounds()
        effect.setFrame_(((frame.origin.x+paper.left(),
                           frame.origin.y+bounds.size.height-paper.bottom()),
                          (paper.width(), paper.height())))
        if getattr(surface, '_native_finish', None) == 'Liquid Glass':
            effect.setCornerRadius_(surface.corner_radius())
        effect.layer().setCornerRadius_(surface.corner_radius())
        effect.layer().setMasksToBounds_(True)

    def remove_material(self, board):
        record = getattr(board, '_visual_effect', None)
        if record is not None:
            record[1].removeFromSuperview()
            board._visual_effect = None

    def release_appearance(self, board):
        self.remove_material(board)
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
            self.sync_material(board)
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
        self.sync_material(surface)
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
