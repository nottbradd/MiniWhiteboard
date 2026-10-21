"""Rounded native compositor material on a passive host behind Qt's artwork."""
import ctypes as C
from ctypes import wintypes as W
import sys

from ...appearance import DisplayPolicy
from . import native


def display_policy():
    if not native.IS_WINDOWS:
        return DisplayPolicy(transparency=False)
    class HighContrast(C.Structure):
        _fields_ = [('size', W.UINT), ('flags', W.DWORD), ('scheme', W.LPWSTR)]
    system_parameters = native.bind(native.user32, 'SystemParametersInfoW', W.BOOL,
                                    W.UINT, W.UINT, C.c_void_p, W.UINT)
    high = HighContrast(C.sizeof(HighContrast), 0, None)
    system_parameters(0x0042, high.size, C.byref(high), 0)
    motion = W.BOOL(True)
    system_parameters(0x1042, 0, C.byref(motion), 0)
    transparency = True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            transparency = bool(winreg.QueryValueEx(key, 'EnableTransparency')[0])
    except OSError:
        pass
    return DisplayPolicy(transparency=transparency and not high.flags & 1,
                         motion=bool(motion.value), high_contrast=bool(high.flags & 1))


def capable(policy):
    return (native.IS_WINDOWS and sys.getwindowsversion().build >= 22621
            and policy.transparency and not policy.high_contrast)


class BackdropHost:
    """No Qt layered-window backdrop assumptions, input, activation, or timers."""
    def __init__(self, board):
        self.handle = None
        self.effect = None
        self.owner = int(board.winId())
        global _window_class
        if '_window_class' not in globals():
            _register_class()
        create = native.bind(native.user32, 'CreateWindowExW', W.HWND, W.DWORD,
            W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
            W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p)
        # NOREDIRECTIONBITMAP: this window has only a compositor visual, no GDI
        # backing rectangle. It is topmost, transparent to input and nonactivating.
        self.handle = create(0x082000A8, _window_class, 'Mini Whiteboard glass backdrop',
                             0x80000000, 0, 0, 1, 1, None, None, None, None)
        if not self.handle:
            raise OSError('Cannot create backdrop host.')
        try:
            dwm = C.WinDLL('dwmapi')
            attribute = native.bind(dwm, 'DwmSetWindowAttribute', C.c_long,
                                   W.HWND, W.DWORD, C.c_void_p, W.DWORD)
            enabled = W.BOOL(True)
            # DWMWA_USE_HOSTBACKDROPBRUSH, supported on Windows 11. Unlike the
            # system Acrylic backdrop this brush has an explicit rounded clip.
            if attribute(self.handle, 17, C.byref(enabled), C.sizeof(enabled)) < 0:
                raise OSError('DWM host backdrop unavailable.')
            from .composition import RoundedBackdrop
            self.effect = RoundedBackdrop(self.handle)
        except Exception:
            self.close()
            raise

    def sync(self, board):
        rect = board.physical_paper_rect()
        scale = board.devicePixelRatioF()
        dimensions = round(rect.width), round(rect.height)
        if not native.user32.SetWindowPos(self.handle, self.owner, round(rect.x), round(rect.y),
                                          dimensions[0], dimensions[1], 0x0050):
            raise OSError('Cannot place backdrop.')
        self.effect.resize(*dimensions, board.corner_radius()*scale)

    def close(self):
        if self.handle:
            try:
                if self.effect is not None:
                    self.effect.close()
                    self.effect = None
            finally:
                native.bind(native.user32, 'DestroyWindow', W.BOOL, W.HWND)(self.handle)
                self.handle = None


def _register_class():
    global _window_class, _window_proc
    callback = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    default = native.bind(native.user32, 'DefWindowProcW', C.c_ssize_t,
                          W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    @callback
    def procedure(handle, message, wparam, lparam):
        if message == 0x0083:  # A frameless client area, while retaining DWM eligibility.
            return 0
        if message == 0x0084:
            return -1  # HTTRANSPARENT
        if message == 0x0021:
            return 3  # MA_NOACTIVATE
        return default(handle, message, wparam, lparam)
    class WindowClass(C.Structure):
        _fields_ = [('style', W.UINT), ('procedure', callback), ('class_extra', C.c_int),
                    ('window_extra', C.c_int), ('instance', W.HINSTANCE), ('icon', W.HICON),
                    ('cursor', W.HANDLE), ('brush', W.HBRUSH), ('menu', W.LPCWSTR), ('name', W.LPCWSTR)]
    gdi = C.WinDLL('gdi32')
    brush = native.bind(gdi, 'GetStockObject', W.HGDIOBJ, C.c_int)(4)  # BLACK_BRUSH
    name = 'MiniWhiteboardDwmBackdropV131'
    record = WindowClass(0, procedure, 0, 0, None, None, None, brush, None, name)
    if not native.bind(native.user32, 'RegisterClassW', W.ATOM, C.POINTER(WindowClass))(C.byref(record)):
        raise OSError('Cannot register backdrop class.')
    _window_proc = procedure
    _window_class = name
