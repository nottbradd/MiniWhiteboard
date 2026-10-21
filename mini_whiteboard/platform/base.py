"""Desktop units stop here; document geometry always uses Qt logical units."""
from dataclasses import dataclass, field
from typing import Callable, Protocol

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QImage

from ..geometry import Rect, large_enough
from ..settings import MIN_HEIGHT, MIN_WIDTH, SHADOW
from ..login import UnavailableLogin

CREATE_HOTKEY = 0x4D01
ESCAPE_HOTKEY = 0x4D02
CAPTURE_HOTKEY = 0x4D03
HIDE_HOTKEY = 0x4D07


class HotkeyEvents(QObject):
    create = Signal()
    create_released = Signal()
    cancel = Signal()
    capture = Signal()
    capture_released = Signal()
    hide_toggle = Signal()
    warning = Signal(str)


@dataclass(frozen=True)
class Display:
    name: str
    rect: Rect
    scale: float
    identifier: int | str = ""


class CapturePermissionError(OSError):
    """A recoverable denial, separate from a failed or empty capture."""


class CaptureService(Protocol):
    def prepare(self) -> None: ...
    def capture_region(self, rect: Rect, success: Callable[[QImage], None],
                       failure: Callable[[Exception], None], excluded=()) -> None: ...
    def cancel(self) -> None: ...


class QtDesktop:
    def display_policy(self):
        from ..appearance import DisplayPolicy
        return DisplayPolicy(transparency=False)

    def apply_appearance(self, board):
        return False

    def release_appearance(self, board):
        pass

    """Logical-coordinate implementation for injected tests and common helpers."""
    shadow_margin = SHADOW
    paints_shadow = True
    separate_shadow = False

    def board_flags(self):
        return Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint

    def cursor_position(self):
        point = QCursor.pos()
        return point.x(), point.y()

    def displays(self):
        return [Display(screen.name(), Rect(screen.geometry().x(), screen.geometry().y(),
                                            screen.geometry().width(), screen.geometry().height()),
                        screen.devicePixelRatio()) for screen in QGuiApplication.screens()]

    def dominant_display(self, rect):
        displays = self.displays()
        if not displays:
            raise OSError("No displays are available.")
        return max(displays, key=lambda display: display.rect.intersection_area(rect))

    def placement_scale(self, rect):
        return 1.0

    def window_scale(self, widget):
        return 1.0

    def window_rect(self, widget):
        rect = widget.geometry()
        return Rect(rect.x(), rect.y(), rect.width(), rect.height())

    def set_window_rect(self, widget, rect):
        widget.setGeometry(round(rect.x), round(rect.y), round(rect.width), round(rect.height))

    def configure_board(self, board):
        pass

    def configure_overlay(self, overlay, *, interactive=False, owner=None):
        pass

    def capture_window_identifier(self, widget):
        return None

    def paper_rect(self, board):
        dpr = board.devicePixelRatioF()
        pad = round(self.shadow_margin*dpr)/dpr
        return QRectF(pad, pad, board.width()-2*pad, board.height()-2*pad)

    def paper_bounds(self, board):
        return self.window_rect(board).expanded(-round(self.shadow_margin*self.window_scale(board)))

    def canvas_region(self, canvas, rect):
        board = canvas.window()
        native = self.window_rect(board)
        scale = self.window_scale(board)
        return Rect(native.x+(canvas.x()+rect.x())*scale,
                    native.y+(canvas.y()+rect.y())*scale,
                    rect.width()*scale, rect.height()*scale)

    def overlay_local_bounds(self, overlay, rect):
        scale = self.window_scale(overlay)
        origin = overlay.monitor.rect
        return QRectF((rect.x-origin.x)/scale, (rect.y-origin.y)/scale,
                      rect.width/scale, rect.height/scale)

    def focus_window(self, widget):
        widget.show()
        widget.raise_()
        widget.activateWindow()

    def show_without_activating(self, widget):
        previous = widget.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        widget.show()
        widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, previous)

    def board_order(self, boards):
        return list(boards)

    def place_board(self, board, rect):
        scale = self.placement_scale(rect)
        margin = self.shadow_margin
        board.resize(round(rect.width/scale+2*margin), round(rect.height/scale+2*margin))
        board.winId()
        self.configure_board(board)
        self.set_window_rect(board, rect.expanded(round(margin*scale)))
        board.show()
        for _ in range(2):
            self.set_window_rect(board, rect.expanded(round(margin*self.window_scale(board))))
        if not large_enough(rect, self.window_scale(board)):
            raise ValueError("The selected rectangle is below 160 × 100 logical pixels at this window's scale.")

    def sync_decoration(self, board):
        pass

    def native_event(self, board, event_type, message):
        return None


class EmptyInstance:
    acquired = True

    def close(self):
        pass


class QtRuntime:
    persist_preferences = False

    def prepare(self):
        pass

    def single_instance(self):
        return EmptyInstance()

    def configure_application(self, app):
        pass

    def tray_icon(self):
        from ..branding import tray_icon
        return tray_icon()

    def configure_tray(self, app, tray):
        pass

    def activate_existing(self, guard):
        pass

    def close(self):
        pass


@dataclass
class Platform:
    name: str
    runtime: object
    desktop: QtDesktop
    capture: CaptureService
    hotkey_factory: Callable
    shortcuts: object
    login: object = field(default_factory=UnavailableLogin)

    def create_hotkeys(self, app, preset="default"):
        return self.hotkey_factory(app, preset)
