"""Verify native Z-order after focusing an ordinary disposable window."""
import ctypes as C
from ctypes import wintypes as W

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from mini_whiteboard import windows


def run_topmost_checks(board, check):
    user32 = windows.user32
    get_style = windows.bind(user32, "GetWindowLongW", C.c_long, W.HWND, C.c_int)
    foreground = windows.bind(user32, "GetForegroundWindow", W.HWND)
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    enum = windows.bind(user32, "EnumWindows", W.BOOL, callback_type, W.LPARAM)
    board_id = int(board.winId())
    check("Board has native WS_EX_TOPMOST", bool(get_style(board_id, -20) & 8))
    ordinary = QWidget()
    ordinary.setWindowTitle("Mini Whiteboard disposable ordinary-window test")
    ordinary.setGeometry(board.geometry().adjusted(0, 0, 220, 180))
    old_cursor = windows.cursor_position()
    try:
        ordinary.show()
        ordinary_id = int(ordinary.winId())
        check("Comparison window is an ordinary non-topmost window", not bool(get_style(ordinary_id, -20) & 8))
        ordinary.activateWindow()
        user32.SetForegroundWindow(ordinary_id)
        QTest.qWait(150)
        if foreground() != ordinary_id:
            # Windows may reject programmatic activation. Click an exposed point
            # of this owned window, only after checking the exact native root.
            user32.SetWindowPos(ordinary_id, W.HWND(-1), 0, 0, 0, 0, 0x0053)
            QTest.qWait(200)
            rect = windows.window_rect(ordinary)
            point = W.POINT(round(rect.right-30), round(rect.bottom-30))
            at = windows.bind(user32, "WindowFromPoint", W.HWND, W.POINT)
            root = windows.bind(user32, "GetAncestor", W.HWND, W.HWND, W.UINT)
            check("Topmost test activation point belongs to owned ordinary window", root(at(point), 2) == ordinary_id,
                  {"found": root(at(point), 2), "expected": ordinary_id, "point": [point.x, point.y]})
            windows.bind(user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)(point.x, point.y)
            mouse = windows.bind(user32, "mouse_event", None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
            mouse(2, 0, 0, 0, 0)
            mouse(4, 0, 0, 0, 0)
            QTest.qWait(150)
            user32.SetWindowPos(ordinary_id, W.HWND(-2), 0, 0, 0, 0, 0x0013)
        check("Comparison window returns to ordinary Z-order", not bool(get_style(ordinary_id, -20) & 8))
        ordered = []

        @callback_type
        def visit(handle, param):
            ordered.append(int(handle))
            return True

        for _ in range(3):
            ordinary.raise_()
            ordinary.activateWindow()
            user32.SetForegroundWindow(ordinary_id)
            QTest.qWait(150)
            ordered.clear()
            enum(visit, 0)
            if board_id not in ordered or ordinary_id not in ordered or ordered.index(board_id) >= ordered.index(ordinary_id):
                check("Board remains above focused ordinary window", False)
        check("Board remains above focused ordinary window", ordered.index(board_id) < ordered.index(ordinary_id))
        check("Board loses focus without losing topmost state", foreground() == ordinary_id and not board.isActiveWindow())
        QTest.qWait(350)
        check("Topmost board does not repeatedly steal focus", foreground() == ordinary_id)
    finally:
        ordinary.close()
        ordinary.deleteLater()
        board.restore()
        windows.bind(user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)(*old_cursor)
        QTest.qWait(100)
