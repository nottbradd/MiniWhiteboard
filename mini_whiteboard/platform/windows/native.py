"""Small, typed Win32 boundary. No hooks, worker GUI threads, or idle polling."""

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QPoint
from PySide6.QtGui import QGuiApplication

from ...geometry import Rect
from ..base import HotkeyEvents
from ..hold import HoldTracker
from ..toggle import ToggleLatch
from ..base import HIDE_HOTKEY

IS_WINDOWS = sys.platform == "win32"
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
CREATE_HOTKEY = 0x4D01
ESCAPE_HOTKEY = 0x4D02
CAPTURE_HOTKEY = 0x4D03
ESCAPE_VARIANTS = (ESCAPE_HOTKEY, 0x4D04, 0x4D06)


if IS_WINDOWS:
    user32 = C.WinDLL("user32", use_last_error=True)
    kernel32 = C.WinDLL("kernel32", use_last_error=True)

    def bind(dll, name, result, *args):
        function = getattr(dll, name)
        function.restype, function.argtypes = result, args
        return function

    bind(user32, "RegisterHotKey", W.BOOL, W.HWND, C.c_int, W.UINT, W.UINT)
    bind(user32, "UnregisterHotKey", W.BOOL, W.HWND, C.c_int)
    bind(user32, "GetCursorPos", W.BOOL, C.POINTER(W.POINT))
    bind(user32, "GetAsyncKeyState", C.c_short, C.c_int)
    bind(user32, "GetWindowRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
    bind(user32, "GetDpiForWindow", W.UINT, W.HWND)
    bind(user32, "SetWindowPos", W.BOOL, W.HWND, W.HWND,
         C.c_int, C.c_int, C.c_int, C.c_int, W.UINT)
    bind(user32, "SetForegroundWindow", W.BOOL, W.HWND)
    bind(user32, "SetProcessDpiAwarenessContext", W.BOOL, C.c_void_p)
    bind(kernel32, "CreateMutexW", W.HANDLE, C.c_void_p, W.BOOL, W.LPCWSTR)
    bind(kernel32, "CloseHandle", W.BOOL, W.HANDLE)
    bind(kernel32, "GetTickCount", W.DWORD)


def enable_dpi_awareness():
    if IS_WINDOWS:
        # ERROR_ACCESS_DENIED means the manifest/host has already set awareness.
        if not user32.SetProcessDpiAwarenessContext(C.c_void_p(-4)):
            error = C.get_last_error()
            if error != 5:
                raise C.WinError(error)


class SingleInstance:
    def __init__(self, name="Local\\MiniWhiteboard-9fb88530"):
        self.handle = None
        self.acquired = True
        if IS_WINDOWS:
            self.handle = kernel32.CreateMutexW(None, False, name)
            if not self.handle:
                raise C.WinError(C.get_last_error())
            self.acquired = C.get_last_error() != 183

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def cursor_position():
    if IS_WINDOWS:
        point = W.POINT()
        if not user32.GetCursorPos(C.byref(point)):
            raise C.WinError(C.get_last_error())
        return point.x, point.y
    from PySide6.QtGui import QCursor
    p = QCursor.pos()
    return p.x(), p.y()


def window_rect(widget):
    if IS_WINDOWS:
        rect = W.RECT()
        if not user32.GetWindowRect(int(widget.winId()), C.byref(rect)):
            raise C.WinError(C.get_last_error())
        return Rect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    g = widget.geometry()
    return Rect(g.x(), g.y(), g.width(), g.height())


def set_window_rect(widget, rect: Rect, *, topmost=True):
    if IS_WINDOWS:
        # NOACTIVATE | NOOWNERZORDER; focusing is a separate explicit action.
        if not user32.SetWindowPos(int(widget.winId()), W.HWND(-1 if topmost else 0),
                                  round(rect.x), round(rect.y), round(rect.width),
                                  round(rect.height), 0x0010 | 0x0200):
            raise C.WinError(C.get_last_error())
    else:
        widget.setGeometry(round(rect.x), round(rect.y), round(rect.width), round(rect.height))


def focus_window(widget):
    widget.show()
    widget.raise_()
    widget.activateWindow()
    if IS_WINDOWS:
        user32.SetForegroundWindow(int(widget.winId()))


def clip_window_to_paper(widget, inset, radius):
    """Exclude decorative margins from the HWND's input region.

    HTTRANSPARENT alone only forwards within a thread. A native window region
    excludes the margin for every application; a separate passive window paints
    the shadow without intercepting desktop input.
    """
    if not IS_WINDOWS:
        return
    bounds = window_rect(widget)
    gdi32 = C.WinDLL("gdi32", use_last_error=True)
    create = bind(gdi32, "CreateRoundRectRgn", W.HANDLE, C.c_int, C.c_int, C.c_int,
                  C.c_int, C.c_int, C.c_int)
    delete = bind(gdi32, "DeleteObject", W.BOOL, W.HANDLE)
    apply = bind(user32, "SetWindowRgn", C.c_int, W.HWND, W.HANDLE, W.BOOL)
    region = create(inset, inset, round(bounds.width)-inset+1,
                    round(bounds.height)-inset+1, radius*2, radius*2)
    if not region:
        raise C.WinError(C.get_last_error())
    if not apply(int(widget.winId()), region, True):
        delete(region)
        raise C.WinError(C.get_last_error())
    # Windows owns the region after a successful SetWindowRgn.


@dataclass(frozen=True)
class Monitor:
    name: str
    rect: Rect
    scale: float


def monitors():
    screens = QGuiApplication.screens()
    if not IS_WINDOWS:
        return [Monitor(s.name(), Rect(s.geometry().x(), s.geometry().y(),
                                      s.geometry().width(), s.geometry().height()),
                        s.devicePixelRatio()) for s in screens]

    class MonitorInfo(C.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT),
                    ("dwFlags", W.DWORD), ("szDevice", W.WCHAR * 32)]

    callback_type = C.WINFUNCTYPE(W.BOOL, W.HANDLE, W.HDC, C.POINTER(W.RECT), W.LPARAM)
    get_info = bind(user32, "GetMonitorInfoW", W.BOOL, W.HANDLE, C.POINTER(MonitorInfo))
    enum = bind(user32, "EnumDisplayMonitors", W.BOOL, W.HDC, C.c_void_p,
                callback_type, W.LPARAM)
    result = []

    @callback_type
    def callback(handle, _dc, _rect, _data):
        info = MonitorInfo()
        info.cbSize = C.sizeof(info)
        if get_info(handle, C.byref(info)):
            screen = next((s for s in screens if s.name() == info.szDevice), None)
            if screen is None:
                # QScreen names normally match MONITORINFOEX device names.
                screen = QGuiApplication.screenAt(QPoint(info.rcMonitor.left, info.rcMonitor.top)) or screens[0]
            r = info.rcMonitor
            result.append(Monitor(info.szDevice, Rect(r.left, r.top, r.right-r.left,
                                                     r.bottom-r.top), screen.devicePixelRatio()))
        return True

    if not enum(None, None, callback, 0) or not result:
        raise OSError("Windows did not return any monitors")
    return result


def dominant_monitor(rect, available=None):
    available = monitors() if available is None else available
    return max(available, key=lambda m: m.rect.intersection_area(rect))


class NativeHotkeys(QAbstractNativeEventFilter):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.events = HotkeyEvents()
        self.registered = set()
        self.hold = HoldTracker(app, self.events, self.sample)
        self.hide_latch = ToggleLatch(app, self.events.hide_toggle,
                                      lambda: bool(user32.GetAsyncKeyState(ord('H')) & 0x8000))
        self.hide_latch.released.connect(lambda: self.record_release(HIDE_HOTKEY))
        self.last_activation = {}
        self.last_release = {}
        self.events.create_released.connect(lambda: self.record_release(CREATE_HOTKEY))
        self.events.capture_released.connect(lambda: self.record_release(CAPTURE_HOTKEY))
        app.installNativeEventFilter(self)

    def record_release(self, identifier):
        self.last_release[identifier] = kernel32.GetTickCount()

    def sample(self):
        down = {identifier for identifier, key in ((CREATE_HOTKEY, "W"), (CAPTURE_HOTKEY, "S"))
                if user32.GetAsyncKeyState(ord(key)) & 0x8000}
        modifiers = all(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x11, 0x12))
        return down, down if modifiers else set(), bool(user32.GetAsyncKeyState(0x1B) & 0x8000)

    def register(self, identifier, modifiers, key):
        if not IS_WINDOWS:
            raise OSError("Global hotkeys require Windows")
        if identifier in self.registered:
            return
        if not user32.RegisterHotKey(None, identifier, modifiers | MOD_NOREPEAT, key):
            raise C.WinError(C.get_last_error())
        self.registered.add(identifier)

    def start(self):
        failures = []
        for identifier, key in ((CREATE_HOTKEY, "W"), (CAPTURE_HOTKEY, "S"), (HIDE_HOTKEY, "H")):
            try:
                self.register(identifier, 0x0001 | 0x0002, ord(key))
            except OSError as error:
                failures.append(f"Ctrl+Alt+{key}: {error}")
        if failures:
            self.events.cancel.emit()
            raise OSError("\n".join(failures))

    def enable_escape(self):
        # Consume Escape in every release order, including while Ctrl/Alt are
        # still held. Bare Escape registration alone cannot consume Alt+Escape.
        # Ctrl+Escape is reserved by Windows. The hold sampler covers that
        # transitional state; only the available combinations are registered.
        for identifier, modifiers in zip(ESCAPE_VARIANTS, (0, 1, 3)):
            self.register(identifier, modifiers, 0x1B)

    def disable_escape(self):
        for identifier in ESCAPE_VARIANTS:
            if identifier in self.registered:
                user32.UnregisterHotKey(None, identifier)
                self.registered.remove(identifier)

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS and bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = W.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self.registered:
                if msg.wParam in ESCAPE_VARIANTS:
                    self.events.cancel.emit()
                else:
                    released = self.last_release.get(msg.wParam)
                    # A delayed repeat already queued before completion cannot
                    # become a fresh hold after the release latch has drained.
                    if released is not None and not 0 < (msg.time-released) % (1 << 32) < (1 << 31):
                        return True, 0
                    # Qt may expose the same native message through two paths.
                    stamp = (msg.time, msg.lParam)
                    if self.last_activation.get(msg.wParam) != stamp:
                        self.last_activation[msg.wParam] = stamp
                        if msg.wParam == HIDE_HOTKEY:
                            self.hide_latch.activate()
                        else:
                            self.hold.activate(msg.wParam)
                return True, 0
        return False, 0

    def close(self):
        self.events.cancel.emit()
        self.hold.close()
        self.hide_latch.close()
        for identifier in tuple(self.registered):
            user32.UnregisterHotKey(None, identifier)
        self.registered.clear()
        self.app.removeNativeEventFilter(self)


def capture_rect(rect):
    """Capture physical virtual-desktop pixels, including negative coordinates."""
    from PySide6.QtGui import QImage
    from ...images import check_size
    if not IS_WINDOWS:
        raise OSError("Desktop capture requires Windows.")
    width, height = round(rect.width), round(rect.height)
    check_size(width, height)
    # Wait for removal of the selection overlays to reach desktop composition.
    dwm = C.WinDLL("dwmapi")
    bind(dwm, "DwmFlush", C.c_long)()
    gdi = C.WinDLL("gdi32", use_last_error=True)
    get_dc = bind(user32, "GetDC", W.HDC, W.HWND)
    release_dc = bind(user32, "ReleaseDC", C.c_int, W.HWND, W.HDC)
    create_dc = bind(gdi, "CreateCompatibleDC", W.HDC, W.HDC)
    create_bitmap = bind(gdi, "CreateCompatibleBitmap", W.HANDLE, W.HDC, C.c_int, C.c_int)
    select = bind(gdi, "SelectObject", W.HANDLE, W.HDC, W.HANDLE)
    delete_dc = bind(gdi, "DeleteDC", W.BOOL, W.HDC)
    delete_object = bind(gdi, "DeleteObject", W.BOOL, W.HANDLE)
    blit = bind(gdi, "BitBlt", W.BOOL, W.HDC, C.c_int, C.c_int, C.c_int, C.c_int,
                W.HDC, C.c_int, C.c_int, W.DWORD)

    class Header(C.Structure):
        _fields_ = [("size",W.DWORD),("width",W.LONG),("height",W.LONG),("planes",W.WORD),
                    ("bits",W.WORD),("compression",W.DWORD),("image_size",W.DWORD),
                    ("xppm",W.LONG),("yppm",W.LONG),("used",W.DWORD),("important",W.DWORD)]
    get_bits = bind(gdi, "GetDIBits", C.c_int, W.HDC, W.HANDLE, W.UINT, W.UINT,
                    C.c_void_p, C.POINTER(Header), W.UINT)
    source = get_dc(None)
    target = bitmap = old = None
    try:
        if not source:
            raise C.WinError(C.get_last_error())
        target = create_dc(source)
        bitmap = create_bitmap(source, width, height)
        if not target or not bitmap:
            raise C.WinError(C.get_last_error())
        old = select(target, bitmap)
        if not blit(target,0,0,width,height,source,round(rect.x),round(rect.y),0x00CC0020 | 0x40000000):
            raise C.WinError(C.get_last_error())
        select(target, old)
        old = None
        header = Header(C.sizeof(Header), width, -height, 1, 32, 0, width*height*4, 0,0,0,0)
        buffer = C.create_string_buffer(width*height*4)
        if get_bits(source,bitmap,0,height,buffer,C.byref(header),0) != height:
            raise C.WinError(C.get_last_error())
        return QImage(buffer.raw, width,height,width*4,QImage.Format.Format_RGB32).copy()
    finally:
        if old and target:
            select(target,old)
        if bitmap:
            delete_object(bitmap)
        if target:
            delete_dc(target)
        if source:
            release_dc(None,source)
