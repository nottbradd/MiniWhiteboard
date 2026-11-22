"""Opt-in optical review with an independent moving window and a stationary board."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys

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
    photograph(background,path,settle_ms=0)


def capture_scene(bg, folder, name):
    bg.palette_name = 'reel'
    for phase in (None, 0, 12):
        bg.phase = phase
        bg.update()
        take_frame(bg, folder/f"reel-{name}-{'bare' if phase is None else phase}.png")
    result = {'diagonal': [measure(folder, name, 'reel', p) for p in (0,12)],
              'channels': [channel_separation(folder, name, p, 'reel') for p in (0,12)]}
    if any(phase['exterior']['columns'] != 30 for phase in result['diagonal']):
        raise RuntimeError('The uncovered part of the moving line was missing.')
    phases = range(-12, 13, 2)
    bg.grazing = True
    for phase in [None,*phases]:
        bg.phase = phase
        bg.update()
        take_frame(bg,folder/f"corner-{name}-{'bare' if phase is None else phase}.png")
    bg.grazing = False
    return result


def compare_with_uncovered(report):
    uncovered = report['samples']['uncovered']['diagonal']
    for name, sample in report['samples'].items():
        for reference, observed in zip(uncovered, sample['diagonal']):
            outside = dict(reference['rim_samples'])
            matched = [abs(offset - outside[x]) for x, offset in observed['rim_samples'] if x in outside]
            observed['rim_peak_vs_uncovered'] = round(max(matched), 2) if matched else None
    if report['native']['liquid'] == LIQUID:
        # Static highlights are absent from the difference image. Require a
        # change at the native rim in both poses and a channel split in motion.
        liquid = report['samples']['liquid']
        for pose in liquid['diagonal']:
            if (pose['rim_peak_vs_uncovered'] or 0) < 1.5:
                raise RuntimeError('Liquid rim did not move the line at both positions.')
        if max(row['rim_max'] or 0 for row in liquid['channels']) < .45:
            raise RuntimeError('Moving neutral line did not separate into colours at the rim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
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
            report['samples'][name] = capture_scene(bg, folder, name)
        compare_with_uncovered(report)
    finally:
        (folder/'reel.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        board.close()
        bg.close()
        app.processEvents()


if __name__=='__main__':
    main()
