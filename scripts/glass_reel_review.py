"""Opt-in optical review with an independent moving window and a stationary board."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mini_whiteboard.appearance import FROSTED, LIQUID
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.geometry import Rect
from mini_whiteboard.platform import get_platform
from mini_whiteboard.snapping import SnapPreferences
from .glass_optics import (BOARD_H, BOARD_W, HEIGHT, LEFT, TOP, WIDTH, RemoteBackground,
                           channel_separation, measure, photograph)


def take_frame(background, path):
    if sys.platform != 'win32':
        photograph(background, path)
        return
    import ctypes
    from ctypes import wintypes as W
    from mini_whiteboard.platform.windows import native
    QTest.qWait(220)
    x, y = background.origin.toTuple()
    scale = background.ratio
    point_window = native.bind(native.user32, 'WindowFromPoint', W.HWND, W.POINT)
    window_pid = native.bind(native.user32, 'GetWindowThreadProcessId', W.DWORD,
                             W.HWND, ctypes.POINTER(W.DWORD))
    for dx, dy in ((5,5), (WIDTH-5,5), (5,HEIGHT-5), (WIDTH-5,HEIGHT-5), (WIDTH//2,HEIGHT//2)):
        pid = W.DWORD()
        window_pid(point_window(W.POINT(round((x+dx)*scale),round((y+dy)*scale))), ctypes.byref(pid))
        if pid.value not in (os.getpid(), background.pid):
            raise RuntimeError('Another window covers the moving-line fixture.')
    # This test camera reads only the physical rectangle occupied by our fixture.
    region = Rect(*(round(v*scale) for v in (x,y,WIDTH,HEIGHT)))
    if not native.capture_rect(region).save(str(path)):
        raise OSError(f'Could not save {path.name}')


def capture_scene(bg, folder, name, *, motion=False):
    bg.palette_name = 'reel'
    for phase in (None, 0, 12):
        bg.phase = phase
        bg.update()
        take_frame(bg, folder/f"reel-{name}-{'bare' if phase is None else phase}.png")
    result = {'diagonal': [measure(folder, name, 'reel', p) for p in (0,12)],
              'channels': [channel_separation(folder, name, p, 'reel') for p in (0,12)]}
    if any(phase['exterior']['columns'] != 30 for phase in result['diagonal']):
        raise RuntimeError('The uncovered part of the moving line was missing.')
    phases = list(range(-12,13,2)) if motion else [-4,0,4]
    bg.grazing = True
    for phase in [None,*phases]:
        bg.phase = phase
        bg.update()
        take_frame(bg,folder/f"corner-{name}-{'bare' if phase is None else phase}.png")
    bg.grazing = False
    return result


def mac_trials(board, bg, folder, report):
    import AppKit
    if board.native_glass != LIQUID or board._glass_rim is None:
        raise RuntimeError('The native AppKit liquid material is required for the rim comparison.')
    rim = board._glass_rim
    # Parameters affect only the additional native glass view under Qt artwork.
    # Each scene includes its own stationary no-line frame for colour measurements.
    for name,inset,width,alpha,tint in (
        ('narrow',2.4,5.5,.53,(.04,.42,.79,.70)),
        ('inset',4.0,6.0,.70,(.02,.46,.85,.86)),
        ('wide',2.8,8.0,.78,(.03,.42,.88,.92)),
        ('warm',3.5,6.5,.70,(.95,.36,.04,.85)),
    ):
        rim.inset,rim.band,rim.key = inset,width,None
        rim.view.setAlphaValue_(alpha)
        rim.view.setTintColor_(AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*tint))
        board.desktop.sync_material(board)
        QTest.qWait(180)
        report['samples'][name] = capture_scene(bg,folder,name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--mac-trials',action='store_true')
    args = parser.parse_args()
    folder = args.output
    folder.mkdir(parents=True,exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    preferences = SnapPreferences()
    bg = RemoteBackground()
    board = BoardWindow('Mini Whiteboard',preferences,get_platform())
    scale = bg.ratio if sys.platform == 'win32' else 1
    x,y = bg.origin.toTuple()
    bounds = Rect(*(round(v*scale) for v in (x+LEFT,y+TOP,BOARD_W,BOARD_H)))
    report = dict(system=platform.platform(),scale=bg.ratio,board_pid=os.getpid(),background_pid=bg.pid,
                  paper=[LEFT,TOP,BOARD_W,BOARD_H],native={},samples={})
    try:
        for name,theme in (('uncovered',None),('white','White'),('frosted',FROSTED),('liquid',LIQUID)):
            if theme is not None:
                preferences.set_theme(theme)
                if not board.isVisible():
                    board.place(bounds)
                QTest.qWait(300)
                report['native'][name] = board.native_glass or ('White' if theme=='White' else 'Opaque')
            report['samples'][name] = capture_scene(bg,folder,name,motion=not args.mac_trials)
        if args.mac_trials:
            mac_trials(board,bg,folder,report)
    finally:
        (folder/'reel.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        board.close()
        bg.close()
        app.processEvents()


if __name__=='__main__':
    main()
