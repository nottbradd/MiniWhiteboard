"""Opt-in Windows textbox regression using native input in an owned board only."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from mini_whiteboard import windows
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Document
from mini_whiteboard.geometry import Rect


def main():
    windows.enable_dpi_awareness()
    app = QApplication([])
    guard = windows.SingleInstance()
    if not guard.acquired:
        raise SystemExit("Exit Mini Whiteboard before running this desktop test.")
    previous = windows.bind(windows.user32, "GetForegroundWindow", W.HWND)()
    saved_cursor = windows.cursor_position()
    set_cursor = windows.bind(windows.user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)
    key_event = windows.bind(windows.user32, "keybd_event", None, W.BYTE, W.BYTE, W.DWORD, C.c_size_t)
    mouse_event = windows.bind(windows.user32, "mouse_event", None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
    at_point = windows.bind(windows.user32, "WindowFromPoint", W.HWND, W.POINT)
    ancestor = windows.bind(windows.user32, "GetAncestor", W.HWND, W.HWND, W.UINT)
    foreground = windows.bind(windows.user32, "GetForegroundWindow", W.HWND)
    board = BoardWindow("Mini Whiteboard owned textbox test")
    results, errors = [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda kind, value, tb: errors.append(repr(value))

    def check(label, condition, detail=None):
        results.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
        print(json.dumps(results[-1]), flush=True)
        if not condition:
            raise AssertionError(label)

    def click(x, y, right=False):
        point = board.canvas.mapToGlobal(QPoint(x, y))
        set_cursor(point.x(), point.y())
        QTest.qWait(25)
        handle = at_point(W.POINT(point.x(), point.y()))
        if ancestor(handle, 2) != int(board.winId()):
            raise AssertionError("Native click target is not the owned test board")
        mouse_event(8 if right else 2, 0, 0, 0, 0)
        try:
            QTest.qWait(30)
        finally:
            mouse_event(16 if right else 4, 0, 0, 0, 0)
        QTest.qWait(70)

    def press(vk, ctrl=False):
        if foreground() != int(board.winId()):
            raise AssertionError("Native key target is not the owned test board")
        if ctrl:
            key_event(0x11, 0, 0, 0)
        try:
            key_event(vk, 0, 0, 0)
            key_event(vk, 0, 2, 0)
        finally:
            if ctrl:
                key_event(0x11, 0, 2, 0)
        QTest.qWait(50)

    try:
        monitor = windows.monitors()[0]
        board.place(Rect(monitor.rect.x+100, monitor.rect.y+130, 650, 450))
        QTest.qWait(180)
        click(25, 25)  # Verify ownership before any keyboard input.
        board.canvas.document = Document()
        board.canvas.cancel_interaction()
        board.canvas.set_selection(set())
        press(ord("T"))
        click(50, 65)
        check("Native T and canvas click creates one focused editor",
              board.canvas.tool == "Text" and board.canvas.editor is not None
              and board.canvas.editor.hasFocus())
        click(60, 270)
        check("Native outside press/release leaves no replacement editor",
              board.canvas.editor is None and board.canvas.editor_overlay is None)
        check("Native empty dismissal leaves model, history and selection empty",
              not board.canvas.document.objects and not board.canvas.document.history
              and not board.canvas.selected_ids and board.canvas.gesture is None)
        click(80, 290)
        check("Native next separate click immediately creates a focused editor",
              board.canvas.editor is not None and board.canvas.editor.hasFocus()
              and board.canvas.editing_object.position == (80, 290))
        for vk in (0x20, 0x09, 0x0D, 0x20):
            press(vk)
        click(60, 60)
        check("Native typed whitespace dismisses without model/history",
              board.canvas.editor is None and not board.canvas.document.history)
        for _ in range(5):
            click(50, 65)
            click(60, 270)
        check("Native rapid repeated cycles leave no editor, selection or objects",
              board.canvas.editor is None and not board.canvas.selected_ids
              and not board.canvas.document.objects)
        click(50, 65)
        press(ord('Q'))
        editor = board.canvas.editor
        check("Native typing remains owned by QTextEdit", editor.toPlainText().lower() == 'q')

        def inspect_menu():
            menus = [m for m in editor.findChildren(QMenu) if m.isVisible()]
            check("Native right-click embedded editor menu survives deferred focus",
                  bool(menus) and board.canvas.editor is editor and editor.popup_active())
            click(590, 340)
            check("Native menu dismissal keeps editor and creates no canvas gesture",
                  board.canvas.editor is editor and board.canvas.gesture is None
                  and not editor.popup_active())

        QTimer.singleShot(150, inspect_menu)
        click(75, 80, right=True)
        QTest.qWait(200)
        check("Native context-menu callbacks completed without errors", not errors, errors)
        press(0x1B)
        original = board.canvas.document.objects
        check("Native Escape commits meaningful text once",
              len(original) == 1 and original[0].text.lower() == 'q'
              and board.canvas.document.index == 1 and board.canvas.editor is None,
              {"objects": [str(o) for o in original], "index": board.canvas.document.index,
               "editor": str(board.canvas.editor), "focus": str(QApplication.focusWidget())})
        # Reopen with a native Text-tool click rather than a fixture-only callback.
        board.canvas.set_selection(set())
        click(55, 75)
        check("Native text click reopens committed content", board.canvas.editor is not None)
        press(ord('A'), ctrl=True)
        press(0x08)
        press(0x0D, ctrl=True)
        check("Native clearing existing text commits one deletion",
              not board.canvas.document.objects and board.canvas.document.index == 2
              and board.canvas.editor is None)
        press(ord('Z'), ctrl=True)
        check("Native document undo restores original text exactly", board.canvas.document.objects == original)
        press(ord('Y'), ctrl=True)
        check("Native document redo restores deletion", not board.canvas.document.objects)
        press(ord('C'))
        check("Native C opens the temporary palette", board.canvas.palette is not None
              and board.canvas.palette.isVisible())
        click(590, 340)
        check("Native palette dismissal does not create text or a canvas action",
              board.canvas.editor is None and board.canvas.gesture is None
              and not board.canvas.document.objects)
        check("Native textbox audit has no callback exceptions or mouse grab",
              not errors and board.mouseGrabber() is None and board.canvas.gesture is None)
    finally:
        board.close()
        app.processEvents()
        set_cursor(*saved_cursor)
        if previous:
            windows.user32.SetForegroundWindow(previous)
        guard.close()
        sys.excepthook = old_hook
        output = Path(".test-artifacts/text-input-check.json")
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(results, indent=2)+"\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
