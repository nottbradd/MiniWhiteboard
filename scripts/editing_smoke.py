"""Owned-window editing checks invoked by native_smoke (no global input)."""
from dataclasses import replace
import math

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mini_whiteboard.document import Document, Shape, Stroke, Text, transformed
from mini_whiteboard import rendering
from mini_whiteboard.transforms import Affine, Erasure, rotation, translation
from .polish_smoke import capture_board


def run_editing_checks(board, check, artifacts):
    board.resize(780, 540)
    canvas = board.canvas
    canvas.document = Document()
    canvas.set_selection(set())
    canvas.setFocus()
    QTest.qWait(100)

    def key(code, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(canvas, code, modifier)
        QApplication.processEvents()

    def drag(start, end, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, modifier, QPoint(*start))
        QTest.mouseMove(canvas, QPoint(*end))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, modifier, QPoint(*end))
        QApplication.processEvents()

    a = Stroke(((60, 100), (320, 100)), 6)
    b = Shape("Rounded rectangle", (70, 150), (190, 240), 4)
    c = Text((230, 160), "Editable text", 20)
    canvas.document.commit((a, b, c), "Fixture")
    key(Qt.Key.Key_A)
    drag((30, 70), (480, 290))
    check("Native A marquee selects mixed objects", canvas.selected_ids == {a.id, b.id, c.id})
    frame = canvas.frame
    start = frame.handle(4)
    drag((round(start[0]), round(start[1])), (round(start[0]+60), round(start[1]+35)))
    resized = canvas.document.objects
    check("Native text group resize remains proportional",
          all(abs(o.transform.a-o.transform.d) < 1e-8 for o in resized) and resized[0].transform.scale > 1)
    frame = canvas.frame
    start = frame.rotation_handle()
    radius = math.dist(start, frame.center)
    drag((round(start[0]), round(start[1])), (round(frame.center[0]+radius), round(frame.center[1])),
         Qt.KeyboardModifier.ShiftModifier)
    rotated = canvas.document.objects
    check("Native shared rotation snaps to 90 degrees", abs(canvas.frame.angle-90) < 1e-7)
    capture_board(board).save(str(artifacts/"selection-transform.png"))
    key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    check("Native group rotation undo is exact", canvas.document.objects == resized)
    key(Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    check("Native group rotation redo is exact", canvas.document.objects == rotated)
    key(Qt.Key.Key_Backspace)
    check("Native multi-delete retains the board", not canvas.document.objects and board.isVisible())
    key(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    check("Native multi-delete undo restores all objects", canvas.document.objects == rotated)

    canvas.document = Document()
    canvas.set_selection(set())
    canvas.document.add(a)
    key(Qt.Key.Key_E)
    drag((180, 70), (180, 130))
    cut = canvas.document.objects[0]
    check("Native circular eraser leaves both outside fragments",
          cut.id == a.id and rendering.visible_ink(cut).contains(QPointF(80, 100))
          and rendering.visible_ink(cut).contains(QPointF(300, 100))
          and not rendering.visible_ink(cut).contains(QPointF(180, 100)))
    key(Qt.Key.Key_5)
    drag((60, 90), (60, 110))
    check("Native whole-stroke mode removes every fragment", not canvas.document.objects)
    key(Qt.Key.Key_3)
    check("Native size key returns to circular mode", canvas.eraser_mode == "circular" and canvas.eraser_diameter == 32)

    text = Text((10, 10), "Masked text", 28,
                transform=translation(130, 120) @ rotation(20) @ Affine(a=1.3, d=1.3),
                erasures=(Erasure((42, 0), (42, 100), 7),))
    canvas.document = Document()
    canvas.document.add(text)
    canvas.begin_editing(text)
    QTest.qWait(100)
    check("Native transformed QTextEdit owns focus", canvas.editor is not None and canvas.editor.hasFocus())
    board.grab().save(str(artifacts/"masked-text-editing.png"))
    target = QApplication.focusWidget()
    QTest.keyClick(target, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(target, "A V E 12345")
    check("Native proxy focus target types tool keys normally", canvas.editor.toPlainText() == "A V E 12345")
    check("Native typing leaves document undo untouched", canvas.document.index == 1)
    QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(target, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(target, Qt.Key.Key_Escape)
    QApplication.processEvents()
    updated = canvas.document.objects[0]
    check("Native text commit retains rotation and mask", updated.text == "A V E 12345"
          and updated.transform == text.transform and updated.erasures == text.erasures)
    check("Native editor commit returns canvas focus", canvas.hasFocus())
    key(Qt.Key.Key_T)
    key(Qt.Key.Key_2)
    check("Native transformed font preset gives 20 pt", abs(canvas.document.objects[0].size*text.transform.scale-20) < 1e-7)
    board.grab().save(str(artifacts/"masked-text-committed.png"))
