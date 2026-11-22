"""Native UI photographs, keyboard/mouse checks and contrast samples on a test desktop."""
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from mini_whiteboard.appearance import DisplayPolicy, THEMES
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Stroke, Text
from mini_whiteboard.floating_tools import FloatingTools
from mini_whiteboard.geometry import Rect
from mini_whiteboard.platform import get_platform
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.surfaces import SurfaceMenu
from mini_whiteboard.system_menu import populate_appearance
from .glass_optics import Background, photograph


def global_rect(widget):
    return QRect(widget.mapToGlobal(QPoint()), widget.size())


def activate_owned_board(board):
    board.activate_explicitly()
    if sys.platform != 'win32':
        return
    from ctypes import wintypes as W
    from mini_whiteboard.platform.windows import native
    QTest.qWait(70)
    u = native.user32
    foreground = native.bind(u, 'GetForegroundWindow', W.HWND)
    if foreground() == int(board.winId()):
        return
    # An interactive Windows desktop can reject SetForegroundWindow on initial
    # launch. Activate only the test board, with one click on its empty top strip.
    paper = board.physical_paper_rect()
    target = round(paper.x+paper.width/2),round(paper.y+4*board.devicePixelRatioF())
    lookup = native.bind(u,'WindowFromPoint',W.HWND,W.POINT)
    root = native.bind(u,'GetAncestor',W.HWND,W.HWND,W.UINT)
    if root(lookup(W.POINT(*target)),2) != int(board.winId()):
        raise RuntimeError('Another window covers the board activation target.')
    cursor = native.cursor_position()
    move = native.bind(u,'SetCursorPos',W.BOOL,W.INT,W.INT)
    mouse = native.bind(u,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,W.WPARAM)
    move(*target)
    mouse(2,0,0,0,0)
    mouse(4,0,0,0,0)
    QTest.qWait(75)
    if native.cursor_position()==target:
        move(*cursor)

def luminance(rgb):
    value = np.asarray(rgb, dtype=float)/255
    linear = np.where(value <= .04045, value/12.92, ((value+.055)/1.055)**2.4)
    return linear @ np.array([.2126, .7152, .0722])


def sample(image, crop, target, *, icon=False):
    # Measure solid ink and its immediate local backing in the same control.
    # The light median is stable across normal spacing, antialiasing and glyphs.
    roi = global_rect(target).translated(-crop.x(), -crop.y())
    if icon:
        roi = roi.adjusted(9,9,-9,-9)
    factor = image.width/crop.width()
    box = tuple(round(x*factor) for x in (roi.left(), roi.top(), roi.right()+1, roi.bottom()+1))
    values = np.sort(luminance(np.asarray(image.convert('RGB').crop(box))).ravel())
    ink = float(np.mean(values[:max(3,round(len(values)*.006))]))
    backing = float(np.median(values))
    return round((backing+.05)/(ink+.05),2)


def ring_contrast(image, crop, button):
    origin = global_rect(button).topLeft()-crop.topLeft()
    scale = image.width/crop.width()
    pixels = luminance(np.asarray(image.convert('RGB')))
    y = round((origin.y()+button.height()/2)*scale)
    x = origin.x()
    edge = pixels[y-2:y+3,round((x+1)*scale):round((x+5)*scale)]
    inside = pixels[y-2:y+3,round((x+7)*scale):round((x+10)*scale)]
    return round((float(np.median(inside))+.05)/(float(np.median(edge.min(axis=1)))+.05),2)


def run(folder):
    folder.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    platform, prefs = get_platform(), SnapPreferences()
    work = app.primaryScreen().availableGeometry()
    bg = Background(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    bg.setGeometry(work)
    bg.palette_name = 'busy'
    bg.phase = 12
    bg.show()
    bg.raise_()
    board = BoardWindow('Mini Whiteboard', prefs, platform)
    factor = app.primaryScreen().devicePixelRatio() if sys.platform == 'win32' else 1
    width, height = min(570,work.width()-40), min(247,work.height()-140)
    x = work.center().x()-width//2
    y = min(work.bottom()-height-18, work.top()+round(work.height()*.56))
    board.place(Rect(*[round(v*factor) for v in (x,y,width,height)]))
    board.canvas.document.add(Text((26, 35), 'Sketch for Monday', size=20))
    board.canvas.document.add(Stroke(((35,108),(66,91),(93,97),(117,78),(161,85)), width=3,
                                     color='#205db6'))
    manager = FloatingTools(app, prefs)
    manager.add_board(board)
    prefs.set_floating_tools(True)
    manager.activate(board)
    report = {'checks':{}, 'surfaces':{}, 'contrast':{}}
    checks = report['checks']
    original_policy = platform.desktop.display_policy
    try:
        for mode in (*THEMES, 'Opaque'):
            if mode == 'Opaque':
                platform.desktop.display_policy = lambda: DisplayPolicy(transparency=False, motion=False)
                board.refresh_appearance()
            else:
                prefs.set_theme(mode)
            activate_owned_board(board)
            QTest.qWait(300)
            manager.refresh()
            palette = manager.palette
            if palette is None or not palette.isVisible():
                raise RuntimeError('The active board did not show its floating tools')
            palette.refresh_appearance()
            QTest.keyClick(board.canvas,Qt.Key.Key_F6)
            QTest.qWait(80)
            QTest.keyClick(palette.buttons['Draw'],Qt.Key.Key_Down)
            QTest.qWait(240)
            options = manager.options
            if options is None or not options.isVisible() or not palette.isVisible():
                raise RuntimeError('Toolbar or popover disappeared during keyboard opening.')
            area = global_rect(board).united(global_rect(palette)).united(global_rect(options))
            area = area.adjusted(-12,-12,12,12).intersected(work)
            name = mode.lower().split()[0]
            report['surfaces'][mode] = dict(board=board.native_glass,
               toolbar=palette.native_glass, popover=options.native_glass,
               toolbar_height=palette.height(), target=palette.buttons['Draw'].width())
            if sys.platform == 'win32':
                from ctypes import wintypes as W
                from mini_whiteboard.platform.windows import native
                point=palette.buttons['Draw'].mapToGlobal(palette.buttons['Draw'].rect().center())
                ratio=palette.devicePixelRatioF()
                lookup=native.bind(native.user32,'WindowFromPoint',W.HWND,W.POINT)
                root=native.bind(native.user32,'GetAncestor',W.HWND,W.HWND,W.UINT)
                def at_tool():
                    return root(lookup(W.POINT(round(point.x()*ratio),round(point.y()*ratio))),2)
                before=at_tool()
                if before == int(bg.winId()):
                    # The test backdrop can enter the topmost band after the
                    # first owned tool opens. Order only the fixture window.
                    host=getattr(board,'_backdrop',None)
                    native.user32.SetWindowPos(int(bg.winId()),host.handle if host else int(board.winId()),
                                               0,0,0,0,0x0213)
                    QTest.qWait(80)
                report.setdefault('native_tool_visibility',{})[mode]=dict(
                    covered_by_fixture=before==int(bg.winId()),visible=palette.isVisible(),
                    target_is_toolbar=at_tool()==int(palette.winId()))
            for scene in ('light', 'dark', 'busy'):
                bg.palette_name = scene
                bg.update()
                path = folder/f'controls-{name}-{scene}.png'
                photograph(bg, path, area)
                with Image.open(path) as im:
                    labels = [x for x in options.findChildren(QLabel) if x.isVisible() and x.text()]
                    report['contrast'][f'{mode}/{scene}'] = dict(
                        text={x.text():sample(im, area, x) for x in labels},
                        tool_icon=sample(im, area, palette.buttons['Draw'], icon=True),
                        selected_ring=ring_contrast(im, area, palette.buttons['Draw']))
            manager.close_options(refocus=True)
        platform.desktop.display_policy = original_policy
        prefs.set_theme('Liquid Glass')
        board.refresh_appearance()
        board.activate_explicitly()
        QTest.qWait(200)
        palette = manager.palette
        QTest.mouseClick(palette.buttons['Eraser'],Qt.MouseButton.LeftButton)
        checks['mouse_select'] = board.canvas.tool == 'Eraser'
        board.activate_explicitly()
        QTest.qWait(100)
        QTest.keyClick(board.canvas, Qt.Key.Key_F6)
        QTest.qWait(150)
        checks['F6_focus'] = palette.buttons['Eraser'].hasFocus()
        if checks['F6_focus']:
            focus_area = global_rect(palette).adjusted(-6,-6,6,6).intersected(work)
            photograph(bg, folder/'keyboard-focus.png', focus_area)
            with Image.open(folder/'keyboard-focus.png') as im:
                report['focus_contrast'] = ring_contrast(im, focus_area, palette.buttons['Eraser'])
        QTest.keyClick(palette.buttons['Eraser'], Qt.Key.Key_Down)
        QTest.qWait(150)
        checks['keyboard_options'] = manager.options is not None and manager.options.isVisible()
        if manager.options is not None:
            QTest.keyClick(manager.options, Qt.Key.Key_Escape)
            QTest.qWait(150)
        checks['escape_returns_canvas'] = manager.options is None and board.canvas.hasFocus()
        menu = SurfaceMenu(platform, prefs)
        populate_appearance(menu, prefs, platform.desktop, [board])
        report['menu'] = [a.text() for a in menu.actions()]
        if not platform.shortcuts.mac:
            menu.popup(board.mapToGlobal(QPoint(70,52)))
            QTest.qWait(120)
            photograph(bg, folder/'appearance-menu.png',
                       global_rect(menu).adjusted(-8,-8,8,8).intersected(work))
            QTest.keyClick(menu, Qt.Key.Key_Escape)
            checks['escape_menu'] = not menu.isVisible()
        menu.close()
        start = board.geometry()
        board.move(start.x()+12, start.y()+8)
        board.resize(start.width()-17, start.height()-11)
        QTest.qWait(200)
        checks['move_resize'] = board.geometry().topLeft() != start.topLeft() and board.size() != start.size()
        board.minimize_to_tray()
        checks['minimise'] = not board.isVisible()
        board.restore()
        QTest.qWait(200)
        checks['restore'] = board.isVisible() and board.appearance_theme == 'Liquid Glass'
        if sys.platform == 'darwin':
            # WindowServer's point lookup can be made without AX privileges.
            # Check a known body and exterior point before interpreting a corner.
            import AppKit
            from mini_whiteboard.platform.macos.desktop import native_window
            primary_height = AppKit.NSScreen.screens()[0].frame().size.height
            paper = board.paper_rect().toAlignedRect()
            bnum = native_window(board).windowNumber()
            bgnum = native_window(bg).windowNumber()
            found = {}
            for label,point in (('body',paper.center()), ('corner',paper.topLeft()+QPoint(1,1)),
                                ('exterior', paper.bottomLeft()+QPoint(0,12))):
                pos = board.mapToGlobal(point)
                number = AppKit.NSWindow.windowNumberAtPoint_belowWindowWithWindowNumber_(
                    (pos.x(),primary_height-pos.y()),0)
                found[label] = 'board' if number == bnum else 'background' if number == bgnum else 'another window'
            report['WindowServer point lookup'] = found
    finally:
        platform.desktop.display_policy = original_policy
        (folder/'controls.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        manager.close()
        board.close()
        bg.close()
    print(json.dumps(checks), flush=True)
    if not all(checks.values()):
        raise RuntimeError('One or more native UI checks failed')
    for scene, observed in report['contrast'].items():
        if (not observed['text'] or min(observed['text'].values()) < 4.5 or
                min(observed['tool_icon'], observed['selected_ring']) < 3):
            raise RuntimeError(f'Insufficient measured contrast in {scene}: {observed}')
    for mode, visibility in report.get('native_tool_visibility', {}).items():
        if not visibility['target_is_toolbar']:
            raise RuntimeError(f'Toolbar was occluded in the {mode} photographs.')
    if report.get('focus_contrast',0) < 3:
        raise RuntimeError('Keyboard focus missed its contrast target')


if __name__ == '__main__':
    run(Path(sys.argv[1]))
