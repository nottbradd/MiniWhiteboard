"""Documented DWM Acrylic on a nonlayered passive host behind Qt's artwork."""
import ctypes as C
from ctypes import wintypes as W
import sys

from ...appearance import DisplayPolicy
from ...settings import RADIUS, SHADOW
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
        self.owner = int(board.winId())
        global _window_class
        if '_window_class' not in globals():
            _register_class()
        create = native.bind(native.user32, 'CreateWindowExW', W.HWND, W.DWORD,
            W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
            W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p)
        # Black client pixels have zero alpha for the extended DWM frame.
        self.handle = create(0x080000A8, _window_class, 'Mini Whiteboard glass backdrop',
                             0x80C40000, 0, 0, 1, 1, None, None, None, None)
        if not self.handle:
            raise OSError('Cannot create backdrop host.')
        try:
            dwm = C.WinDLL('dwmapi')
            attribute = native.bind(dwm, 'DwmSetWindowAttribute', C.c_long,
                                   W.HWND, W.DWORD, C.c_void_p, W.DWORD)
            margins = (C.c_int * 4)(-1, -1, -1, -1)
            extend = native.bind(dwm, 'DwmExtendFrameIntoClientArea', C.c_long, W.HWND, C.c_void_p)
            for identifier, value in ((2, 2), (20, 0), (33, 2), (34, 0xFFFFFFFE), (38, 3)):
                number = C.c_int(value)
                if attribute(self.handle, identifier, C.byref(number), C.sizeof(number)) < 0:
                    raise OSError('DWM backdrop unavailable.')
            if extend(self.handle, C.byref(margins)) < 0:
                raise OSError('DWM frame unavailable.')
            native.bind(native.user32, 'SendMessageW', C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)(self.handle, 0x0086, 1, 0)
        except Exception:
            self.close()
            raise
        self.region_key = None

    def sync(self, board):
        rect = board.physical_paper_rect()
        scale = board.devicePixelRatioF()
        # DWM controls its own discrete corner radius and ignores arbitrary
        # HRGN clipping for the system backdrop. Keep its frosted core strictly
        # inside our larger rounded optical edge instead of leaking square
        # backdrop pixels through transparent corners. The outer edge stays clear.
        from math import ceil, sqrt
        inset = ceil(max(0, board.corner_radius()-8)*(1-1/sqrt(2))) + 1
        rect = rect.expanded(-round(inset*scale))
        dimensions = round(rect.width), round(rect.height), round(8 * scale)
        if not native.user32.SetWindowPos(self.handle, self.owner, round(rect.x), round(rect.y),
                                          dimensions[0], dimensions[1], 0x0050):
            raise OSError('Cannot place backdrop.')
        if dimensions != self.region_key:
            gdi = C.WinDLL('gdi32')
            create_region = native.bind(gdi, 'CreateRoundRectRgn', W.HRGN,
                C.c_int, C.c_int, C.c_int, C.c_int, C.c_int, C.c_int)
            region = create_region(0, 0, dimensions[0]+1, dimensions[1]+1,
                                   dimensions[2]*2, dimensions[2]*2)
            if not region:
                raise OSError('Cannot clip backdrop.')
            if not native.bind(native.user32, 'SetWindowRgn', C.c_int, W.HWND, W.HRGN, W.BOOL)(self.handle, region, True):
                native.bind(gdi, 'DeleteObject', W.BOOL, W.HGDIOBJ)(region)
                raise OSError('Cannot clip backdrop.')
            self.region_key = dimensions

    def close(self):
        if self.handle:
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
