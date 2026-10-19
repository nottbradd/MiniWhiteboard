"""Render a controlled demo using the app's real placement controller and board.

No user screen contents or native global shortcuts are captured. The fake desktop
drives the real renderer deterministically; real-key acceptance is tested separately.
Run with --frames-only if Pillow is unavailable, then encode those PNGs separately.
"""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication

from tests.fake_platform import fake_platform
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.document import Shape, Stroke, Text
from mini_whiteboard.geometry import Rect
from mini_whiteboard.platform.base import Display
from mini_whiteboard.shortcuts import ShortcutPolicy
from mini_whiteboard.snapping import SnapPreferences


def encode(directory, output):
    from PIL import Image
    metadata=json.loads((directory/'frames.json').read_text())
    frames=[Image.open(directory/item['file']).convert('RGB') for item in metadata]
    palette=frames[-1].quantize(colors=128)
    indexed=[frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(output,save_all=True,append_images=indexed[1:],
                    duration=[item['duration'] for item in metadata],loop=0,
                    optimize=True,disposal=2)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--frames-only',action='store_true')
    args=parser.parse_args()
    directory=Path('verification/demo-frames')
    media=Path('docs/media')
    directory.mkdir(parents=True,exist_ok=True)
    media.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    if os.name == 'nt':
        fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for filename in ('segoeui.ttf','segoeuib.ttf'):
            if QFontDatabase.addApplicationFont(str(fonts/filename)) < 0:
                raise RuntimeError('Could not load the Windows demo font: '+filename)
    app.setFont(QFont('Segoe UI',11))
    platform=fake_platform()
    platform.shortcuts=ShortcutPolicy(mac=False)
    platform.desktop.screens=[Display('Demo',Rect(0,0,960,580),1,1)]
    controller=WhiteboardApplication(app,SnapPreferences(),platform=platform)
    controller.tray.hide()
    records=[]
    anchor=(135,148)
    end=(825,468)

    def frame(caption, pointer, duration=80, keys=False):
        app.processEvents()
        image=QImage(960,580,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor('#17232f'))
        p=QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#203342'))
        for x in range(24,960,32):
            for y in range(128,500,32):
                p.drawPoint(x,y)
        p.setFont(QFont('Segoe UI',29,QFont.Weight.Bold))
        p.setPen(QColor('#f5f8fb'))
        p.drawText(QPointF(52,61),'Mini Whiteboard')
        p.setFont(QFont('Segoe UI',12))
        p.setPen(QColor('#a5b9c9'))
        p.drawText(QPointF(53,93),'A little space for your next idea.')
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#52d4c4'))
        p.drawRoundedRect(QRectF(806,38,100,30),15,15)
        p.setFont(QFont('Segoe UI',10,QFont.Weight.Bold))
        p.setPen(QColor('#162e32'))
        p.drawText(QRectF(806,38,100,30),Qt.AlignmentFlag.AlignCenter,'VERSION 1.2')
        for overlay in controller.placement.overlays:
            p.drawPixmap(0,0,overlay.grab())
        for board in controller.boards:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0,0,0,30))
            p.drawRoundedRect(QRectF(board.x()-5,board.y()+4,board.width()+10,board.height()+9),15,15)
            p.drawPixmap(board.pos(),board.grab())
        x,y=pointer
        cursor=QPainterPath(QPointF(x,y))
        for dx,dy in ((0,20),(5,15),(11,25),(15,23),(9,13),(17,13)):
            cursor.lineTo(x+dx,y+dy)
        cursor.closeSubpath()
        p.setPen(QPen(QColor('#17232f'),1.5))
        p.setBrush(QColor('#f5fbff'))
        p.drawPath(cursor)
        p.setFont(QFont('Segoe UI',13,QFont.Weight.Bold))
        p.setPen(QColor('#eff7fb'))
        p.drawText(QPointF(53,529),caption)
        if keys:
            p.setBrush(QColor('#e1faf4'))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(645,502,261,43),9,9)
            p.setFont(QFont('Segoe UI',13,QFont.Weight.Bold))
            p.setPen(QColor('#1a584e'))
            p.drawText(QRectF(645,502,261,43),Qt.AlignmentFlag.AlignCenter,'Ctrl  +  Alt  +  W')
        p.end()
        name=f'{len(records):03d}.png'
        image.save(str(directory/name))
        records.append({'file':name,'duration':duration})
        return image

    try:
        platform.desktop.cursor=anchor
        frame('1  Point at the first corner.',anchor,900)
        controller.hotkeys.events.create.emit()
        assert controller.placement.state.active and not controller.boards
        frame('2  Hold the shortcut to start.',anchor,850,True)
        for i in range(1,25):
            t=i/24
            eased=t*t*(3-2*t)
            point=(round(anchor[0]+(end[0]-anchor[0])*eased),round(anchor[1]+(end[1]-anchor[1])*eased))
            platform.desktop.cursor=point
            controller.placement.track()
            frame('3  Keep holding and move.',point,keys=True)
        frame('4  Release to place your board.',end,850,True)
        controller.hotkeys.events.create_released.emit()
        assert len(controller.boards)==1 and not controller.placement.state.active
        frame('Your board is ready.',end,800)
        canvas=controller.boards[0].canvas
        objects=(Text((36,30),'Make room for an idea.',28,layout_width=610),
                 Text((38,88),'Sketch. Type. Annotate.',18,color='#6b7c8c'),
                 Shape('Rounded rectangle',(36,157),(206,234),3,color='#2878d0'),
                 Text((59,176),'Start here',18,color='#2878d0'),
                 Shape('Arrow',(230,196),(357,196),4,color='#e04444'),
                 Text((384,175),'Keep it simple.',18),
                 Stroke(((50,272),(107,259),(168,277),(245,258),(310,271),(361,260)),4,color='#26945c'))
        canvas.document.commit(objects,'Demo artwork')
        canvas.scene.sync(canvas.document.objects)
        canvas.update()
        screenshot=frame('Draw, type and annotate — no permanent toolbar.',(456,421),2200)
        screenshot.save(str(media/'whiteboard.png'))
        (directory/'frames.json').write_text(json.dumps(records),encoding='utf-8')
        if not args.frames_only:
            encode(directory,media/'placement.gif')
        print(json.dumps({'frames':len(records),'milliseconds':sum(r['duration'] for r in records),
                          'controller_hold_release':'PASSED','user_screen_content':'not captured'}))
    finally:
        controller.cleanup()
        app.processEvents()


if __name__=='__main__':
    main()
