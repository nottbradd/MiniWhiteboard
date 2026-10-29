"""Small, typed Win32 boundary. No hooks, worker GUI threads, or idle polling."""

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QPoint, Qt
from PySide6.QtGui import QGuiApplication

from ...geometry import Rect
from ..base import HotkeyEvents
from ..hold import HoldTracker
from ..toggle import ToggleLatch
from ..base import HIDE_HOTKEY
from ...hotkey_config import ConfigurableHotkeys, defaults

IS_WINDOWS = sys.platform == "win32"
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
CREATE_HOTKEY = 0x4D01
ESCAPE_HOTKEY = 0x4D02
CAPTURE_HOTKEY = 0x4D03
ESCAPE_VARIANTS = (ESCAPE_HOTKEY,) + tuple(range(0x4E01, 0x4E10))
CREATION_MODIFIERS = 0x0008 | 0x0004  # MOD_WIN | MOD_SHIFT (default only).
CREATION_KEYS = {CREATE_HOTKEY: ord('W'), CAPTURE_HOTKEY: ord('Q')}


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


def clear_window_region(widget):
    """Retain the layered window's per-pixel alpha edge and native alpha hit test.

    SetWindowRgn rounds the curve to binary pixels and cuts off antialiasing.
    Windows passes zero-alpha layered pixels to other processes. Native material
    and shadow hosts must also have LAYERED | TRANSPARENT input styles.
    """
    if not IS_WINDOWS:
        return
    apply = bind(user32, "SetWindowRgn", C.c_int, W.HWND, W.HANDLE, W.BOOL)
    if not apply(int(widget.winId()), None, True):
        raise C.WinError(C.get_last_error())


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


class NativeHotkeys(QAbstractNativeEventFilter, ConfigurableHotkeys):
    def __init__(self, app, hide_shortcut='default'):
        super().__init__()
        self.app = app
        self.events = HotkeyEvents()
        self.registered = set()
        self.hide_shortcut = hide_shortcut
        self.initialize_configuration(defaults(hide=hide_shortcut))
        self.hold = HoldTracker(app, self.events, self.sample,
                                {Qt.Key.Key_W: CREATE_HOTKEY, Qt.Key.Key_Q: CAPTURE_HOTKEY})
        self.hide_latch = ToggleLatch(app, self.events.hide_toggle,
                                      lambda: bool(user32.GetAsyncKeyState(self.configuration.hide.windows_key) & 0x8000))
        self._refresh_tracking()
        self.hide_latch.released.connect(lambda: self.record_release(HIDE_HOTKEY))
        self.last_activation = {}
        self.last_release = {}
        self.events.create_released.connect(lambda: self.record_release(CREATE_HOTKEY))
        self.events.capture_released.connect(lambda: self.record_release(CAPTURE_HOTKEY))
        app.installNativeEventFilter(self)

    def record_release(self, identifier):
        self.last_release[identifier] = kernel32.GetTickCount()

    def sample(self):
        down = {identifier for identifier, chord in self.configuration.items()[:2]
                if user32.GetAsyncKeyState(chord.windows_key) & 0x8000}
        keys = {'meta': (0x5B, 0x5C), 'alt': (0xA4, 0xA5), 'shift': (0xA0, 0xA1), 'ctrl': (0xA2, 0xA3)}
        held = {name for name, codes in keys.items() if any(user32.GetAsyncKeyState(key) & 0x8000 for key in codes)}
        complete = {identifier for identifier in down if self.configuration[identifier].modifiers <= held}
        return down, complete, bool(user32.GetAsyncKeyState(0x1B) & 0x8000)

    def register(self, identifier, modifiers, key):
        if not IS_WINDOWS:
            raise OSError("Global hotkeys require Windows")
        if identifier in self.registered:
            return
        if not user32.RegisterHotKey(None, identifier, modifiers | MOD_NOREPEAT, key):
            raise C.WinError(C.get_last_error())
        self.registered.add(identifier)

    def _register_chord(self, identifier, chord):
        self.register(identifier, chord.windows_modifiers, chord.windows_key)

    def _unregister(self, identifier):
        if identifier in self.registered:
            user32.UnregisterHotKey(None, identifier)
            self.registered.remove(identifier)

    def set_hide_shortcut(self, choice):
        if choice not in ('default', 'shift'):
            raise ValueError('Unknown Hide All shortcut.')
        self._unregister(HIDE_HOTKEY)
        self.hide_shortcut = choice
        self.configuration = self.configuration.with_hide(defaults(hide=choice).hide)
        self._refresh_tracking()
        self.record_release(HIDE_HOTKEY)

    def enable_escape(self):
        # Cover every subset of either configured chord during release cleanup.
        masks = [self.configuration[i].windows_modifiers for i in (CREATE_HOTKEY, CAPTURE_HOTKEY)]
        failures = {}
        for modifiers in range(16):
            if any(modifiers & mask == modifiers for mask in masks):
                try:
                    self.register(ESCAPE_VARIANTS[modifiers], modifiers, 0x1B)
                except OSError as error:
                    # Ctrl+Esc and Ctrl+Shift+Esc are reserved by Windows. A
                    # missing draining subset must not abort a valid gesture.
                    failures[modifiers] = str(error)
        active = self.hold.active
        required = self.configuration[active].windows_modifiers if active in (CREATE_HOTKEY, CAPTURE_HOTKEY) else None
        if 0 in failures or required in failures:
            self.events.warning.emit('Escape with this shortcut is reserved or unavailable. '
                                     'Use Cancel placement / screenshot in the tray menu. '
                                     'Choose another creation chord in Settings → Hotkeys for keyboard cancellation.')

    def disable_escape(self):
        for identifier in ESCAPE_VARIANTS:
            if identifier in self.registered:
                user32.UnregisterHotKey(None, identifier)
                self.registered.remove(identifier)

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS and bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = W.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self.registered:
                if self.paused:
                    return True, 0
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
                        chord = self.configuration[msg.wParam]
                        if (msg.lParam & 15 != chord.windows_modifiers
                                or msg.lParam >> 16 & 0xFFFF != chord.windows_key):
                            return True, 0
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
