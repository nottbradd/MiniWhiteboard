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
        key = (bounds.width, bounds.height, scale)
        if key != board._region_key:
            board._region_key = key
            native.clip_window_to_paper(board, round(SHADOW*scale), round(RADIUS*scale))
        board._shadow.sync()

    def native_event(self, board, event_type, message):
        if native.IS_WINDOWS and bytes(event_type) == b"windows_generic_MSG":
            msg = W.MSG.from_address(int(message))
            if msg.message == 0x0084:
                x = C.c_short(msg.lParam & 0xffff).value
                y = C.c_short((msg.lParam >> 16) & 0xffff).value
                bounds = self.window_rect(board)
                scale = self.window_scale(board)
                point = QPointF((x-bounds.x)/scale, (y-bounds.y)/scale)
                path = QPainterPath()
                path.addRoundedRect(board.paper_rect(), RADIUS, RADIUS)
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
