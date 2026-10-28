"""Opt-in native pointer regression with observable selected/moved object IDs."""
import argparse
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import sys
os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import Qt, QSettings, QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import windows as n, rendering, images, clipboard
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Document, Text, Shape, transformed
from mini_whiteboard.geometry import Rect
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.transforms import translation, rotation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    n.enable_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    u = n.user32
    fg = n.bind(u, 'GetForegroundWindow', W.HWND)
    at = n.bind(u, 'WindowFromPoint', W.HWND, W.POINT)
    ancestor = n.bind(u, 'GetAncestor', W.HWND, W.HWND, W.UINT)
    move = n.bind(u, 'SetCursorPos', W.BOOL, C.c_int, C.c_int)
    mouse = n.bind(u, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
    previous, cursor = fg(), n.cursor_position()
    prefs = SnapPreferences(settings=QSettings(str(args.output/'test.ini'), QSettings.Format.IniFormat))
    prefs.smart_guides = prefs.grid_snap = False
    board = BoardWindow('Mini Whiteboard native selection reproduction', prefs, screenshot=True)
    scale = board.devicePixelRatioF()
    board.place(Rect(100, 100, 620*scale, 380*scale))
    canvas = board.canvas
    rows, errors = [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda kind, error, tb: errors.append(str(error))
    image = QImage(620, 380, QImage.Format.Format_RGB32)
    image.fill(QColor('#f1f4f8'))
    background = images.from_image(image, locked=True)

    def check(label, value, detail=None):
        row = {'check': label, 'status': 'PASS' if value else 'FAIL', 'detail': detail}
        rows.append(row)
        print(json.dumps(row), flush=True)
        if not value:
            raise AssertionError(label)

    def ink_point(obj):
        ink = rendering.visible_ink(obj)
        r = ink.boundingRect()
        points = ((x, y) for y in range(round(r.top())+2, round(r.bottom())-1)
                  for x in range(round(r.left())+2, round(r.right())-1))
        return min((p for p in points if ink.contains(rendering.point(p))),
                   key=lambda p: abs(p[0]-r.center().x())+abs(p[1]-r.center().y()))

    def point(local):
        rect = board.desktop.canvas_region(canvas, QRectF(*local, 1, 1))
        return round(rect.x), round(rect.y)

    def click(local, end=None):
        QTest.qWait(app.doubleClickInterval()+30)
        target = point(local)
        move(*target)
        QTest.qWait(40)
        check('Native pointer reaches the intended board', ancestor(at(W.POINT(*target)), 2) == int(board.winId()))
        mouse(2, 0, 0, 0, 0)
        QTest.qWait(40)
        if end is not None:
            for step in range(1, 9):
                pos = (local[0]+(end[0]-local[0])*step/8, local[1]+(end[1]-local[1])*step/8)
                move(*point(pos))
                QTest.qWait(15)
        mouse(4, 0, 0, 0, 0)
        QTest.qWait(60)

    try:
        for index, (theme, scenario) in enumerate((theme, scenario) for theme in ('White', 'Glass')
                                                 for scenario in ('left-first', 'right-first', 'multiline-rotated', 'selection-frame')):
            prefs.set_theme(theme)
            left = Text((35, 115), 'Left note', layout_width=550)
            right = Text((265, 115), 'Right target', layout_width=250)
            if scenario == 'multiline-rotated':
                matrix = translation(20, 0) @ rotation(8)
                left = transformed(replace(left, text='Left note\nAnother line'), matrix)
                right = transformed(replace(right, text='Right target\nSecond line'), matrix)
            if scenario == 'selection-frame':
                left = Shape('Rectangle', (25, 70), (570, 320), 2)
            objects = (background, left, right) if scenario != 'right-first' else (background, right, left)
            canvas.document = Document()
            canvas.document.commit(objects, 'Fixture')
            canvas.set_screenshot_background(background)
            canvas.set_tool('Select')
            canvas.set_selection({left.id} if scenario == 'selection-frame' else set())
            canvas.update()
            QTest.qWait(90)
            target = ink_point(right)
            n.capture_rect(board.physical_paper_rect()).save(str(args.output/f'{index:02d}-before.png'))
            click(target)
            check(f'{theme} {scenario}: visible target is selected', canvas.selected_ids == {right.id},
                  {'click_canvas': target, 'click_desktop': point(target), 'selected': list(canvas.selected_ids), 'expected': right.id})
            canvas.set_selection({left.id} if scenario == 'selection-frame' else set())
            end = (target[0]+30, target[1]+55)
            before_pixel, after_pixel = point(target), point(end)
            delta = tuple((b-a)/scale for a, b in zip(before_pixel, after_pixel))
            click(target, end)
            expected = translation(*delta) @ right.transform
            actual = canvas.document.get(right.id).transform
            check(f'{theme} {scenario}: native drag moves only the target',
                  canvas.selected_ids == {right.id} and canvas.document.get(left.id) == left
                  and all(math.isclose(getattr(actual, key), getattr(expected, key), abs_tol=1e-6)
                          for key in ('a', 'b', 'c', 'd', 'tx', 'ty'))
                  and canvas.document.get(background.id) == background,
                  {'expected_from_physical_pointer': vars(expected), 'actual': vars(actual)})
            n.capture_rect(board.physical_paper_rect()).save(str(args.output/f'{index:02d}-after.png'))
            canvas.document.undo()
            check(f'{theme} {scenario}: one undo restores all exact objects', canvas.document.objects == objects)
            board.desktop.set_window_rect(board, Rect(150, 160, 620*scale+16*scale, 380*scale+16*scale))
            QTest.qWait(60)
        check('Native selection callbacks remain error free', not errors, errors)
    finally:
        mouse(4, 0, 0, 0, 0)
        board.close()
        app.processEvents()
        move(*cursor)
        if previous:
            u.SetForegroundWindow(previous)
        sys.excepthook = old_hook
        (args.output/'checks.json').write_text(json.dumps({'dpr': scale, 'checks': rows, 'exceptions': errors}, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
