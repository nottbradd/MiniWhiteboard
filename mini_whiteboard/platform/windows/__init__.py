"""Adapter around the established Win32 implementation and its coordinate rules."""
import ctypes as C
from ctypes import wintypes as W

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath

from . import native
from ...settings import RADIUS, SHADOW
from ...shortcuts import ShortcutPolicy
from ..base import Platform, QtDesktop, QtRuntime


class WindowsDesktop(QtDesktop):
    def display_policy(self):
        from .appearance import display_policy
        return display_policy()

    def apply_appearance(self, board):
        from .appearance import BackdropHost, capable
        if board.appearance_theme != 'Glass' or not capable(board.display_policy):
            self.release_appearance(board)
            return False
        try:
            host = getattr(board, '_backdrop', None)
            if host is not None and host.owner != int(board.winId()):
                self.release_appearance(board)
                host = None
            if host is None:
                board._backdrop = host = BackdropHost(board)
            if board.isVisible():
                host.sync(board)
            return True
        except (OSError, AttributeError):
            self.release_appearance(board)
            return False

    def release_appearance(self, board):
        host = getattr(board, '_backdrop', None)
        if host is not None:
            host.close()
            board._backdrop = None

    @property
    def paints_shadow(self):
        return not native.IS_WINDOWS

    @property
    def separate_shadow(self):
        return native.IS_WINDOWS

    def cursor_position(self):
        return native.cursor_position()

    def displays(self):
        return native.monitors()

    def dominant_display(self, rect):
        return native.dominant_monitor(rect)

    def placement_scale(self, rect):
        return self.dominant_display(rect).scale

    def window_scale(self, widget):
        return widget.devicePixelRatioF()

    def window_rect(self, widget):
        return native.window_rect(widget)

    def set_window_rect(self, widget, rect):
        native.set_window_rect(widget, rect)

    def focus_window(self, widget):
        native.focus_window(widget)

    def show_without_activating(self, widget):
        super().show_without_activating(widget)
        if native.IS_WINDOWS:
            show = native.bind(native.user32, 'ShowWindow', W.BOOL, W.HWND, C.c_int)
            show(int(widget.winId()), 4)  # SW_SHOWNOACTIVATE
            native.user32.SetWindowPos(int(widget.winId()), W.HWND(-1), 0, 0, 0, 0, 0x0013)

    def board_order(self, boards):
        if not native.IS_WINDOWS:
            return list(boards)
        lookup = {int(board.winId()): board for board in boards}
        result = []
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        @callback_type
        def visit(handle, _):
            if int(handle) in lookup:
                result.append(lookup[int(handle)])
            return True
        native.bind(native.user32, 'EnumWindows', W.BOOL, callback_type, W.LPARAM)(visit, 0)
        return list(reversed(result))

    def paper_rect(self, board):
        dpr = board.devicePixelRatioF()
        pad = round(SHADOW*dpr)/dpr
        width, height = board.width(), board.height()
        if native.IS_WINDOWS and board.windowHandle() is not None:
            bounds = native.window_rect(board)
            width, height = bounds.width/dpr, bounds.height/dpr
        return QRectF(pad, pad, width-2*pad, height-2*pad)

    def sync_decoration(self, board):
        if not native.IS_WINDOWS or not board.isVisible() or board._closing:
            return
        if board._shadow is None:
            from ...shadow import PaperShadow
            board._shadow = PaperShadow(board)
        bounds = self.window_rect(board)
        scale = board.devicePixelRatioF()
        key = (bounds.width, bounds.height, scale, board.corner_radius())
        if key != board._region_key:
            board._region_key = key
            native.clip_window_to_paper(board, round(SHADOW*scale), round(board.corner_radius()*scale))
        board._shadow.sync()
        if getattr(board, '_backdrop', None) is not None:
            try:
                board._backdrop.sync(board)
            except OSError:
                self.release_appearance(board)
                board.native_glass = False
                board.update()

    def native_event(self, board, event_type, message):
        if native.IS_WINDOWS and bytes(event_type) == b"windows_generic_MSG":
            msg = W.MSG.from_address(int(message))
            if msg.message in (0x001A, 0x031A, 0x031E):
                board.refresh_appearance()
            if msg.message == 0x0047 and getattr(board, '_backdrop', None) is not None:
                try:
                    board._backdrop.sync(board)
                except OSError:
                    self.release_appearance(board)
                    board.native_glass = False
                    board.update()
            if msg.message == 0x0084:
                x = C.c_short(msg.lParam & 0xffff).value
                y = C.c_short((msg.lParam >> 16) & 0xffff).value
                bounds = self.window_rect(board)
                scale = self.window_scale(board)
                point = QPointF((x-bounds.x)/scale, (y-bounds.y)/scale)
                path = QPainterPath()
                path.addRoundedRect(board.paper_rect(), board.corner_radius(), board.corner_radius())
                if not path.contains(point):
                    return True, -1
        return None


class WindowsCapture:
    def prepare(self):
        pass

    def capture_region(self, rect, success, failure, excluded=()):
        try:
            image = native.capture_rect(rect)
        except (OSError, ValueError) as error:
            failure(error)
        else:
            success(image)

    def cancel(self):
        pass


class WindowsRuntime(QtRuntime):
    @property
    def persist_preferences(self):
        return native.IS_WINDOWS

    def prepare(self):
        native.enable_dpi_awareness()

    def single_instance(self):
        return native.SingleInstance()


def create_platform():
    return Platform("windows", WindowsRuntime(), WindowsDesktop(), WindowsCapture(),
                    lambda app, preset: native.NativeHotkeys(app), ShortcutPolicy())
