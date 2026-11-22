"""Review-only experiment with DWMSBT_TRANSIENTWINDOW on a separate test HWND."""
import ctypes as C
from ctypes import wintypes as W

from mini_whiteboard.platform.windows import appearance, native


class AcrylicHost:
    def __init__(self, board):
        self.owner = int(board.winId())
        if not hasattr(appearance, '_window_class'):
            appearance._register_class()
        create = native.bind(native.user32, 'CreateWindowExW', W.HWND, W.DWORD,
            W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
            W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p)
        self.handle = create(0x080000A8, appearance._window_class, 'Acrylic probe',
                             0x80000000, 0, 0, 1, 1, None, None, None, None)
        if not self.handle:
            raise OSError('Cannot create acrylic host')
        dwm = C.WinDLL('dwmapi')
        attribute = native.bind(dwm, 'DwmSetWindowAttribute', C.c_long,
                                W.HWND,W.DWORD,C.c_void_p,W.DWORD)
        acrylic = C.c_int(3)
        status = attribute(self.handle, 38, C.byref(acrylic), 4)
        margins = (C.c_int*4)(-1, -1, -1, -1)
        extend = native.bind(dwm, 'DwmExtendFrameIntoClientArea', C.c_long, W.HWND,C.c_void_p)
        print('DWMSBT_TRANSIENTWINDOW',status,'extend glass',extend(self.handle,C.byref(margins)),flush=True)

    def sync(self, board):
        bounds = board.physical_paper_rect()
        w,h = round(bounds.width),round(bounds.height)
        diameter = round(board.corner_radius()*2*board.devicePixelRatioF())
        key = w,h,diameter
        if key != getattr(self,'key',None):
            gdi = C.WinDLL('gdi32')
            rounded = native.bind(gdi,'CreateRoundRectRgn',W.HANDLE,*([C.c_int]*6))(
                1,1,w,h,diameter,diameter)
            native.bind(native.user32,'SetWindowRgn',C.c_int,W.HWND,W.HANDLE,W.BOOL)(self.handle,rounded,1)
            self.key = key
        native.user32.SetWindowPos(self.handle, self.owner, round(bounds.x), round(bounds.y), w,h,0x0050)

    def close(self):
        if self.handle:
            native.bind(native.user32, 'DestroyWindow', W.BOOL, W.HWND)(self.handle)
            self.handle = None
