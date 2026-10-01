"""Native polish checks and captures of owned widgets only."""
import ctypes as C
from ctypes import wintypes as W

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mini_whiteboard import windows
from mini_whiteboard.document import Document, Shape, Stroke, Text
from mini_whiteboard.geometry import Rect
from mini_whiteboard.placement import PreviewOverlay
from mini_whiteboard.settings import CANVAS_INSET, TOP_STRIP


def capture_board(board, padding=40):
    """Compose board, shadow, and passive tool window without reading the desktop."""
    dpr = board.devicePixelRatioF()
    image = QImage(round((board.width()+padding*2)*dpr), round((board.height()+padding*2)*dpr),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(QColor("#c9ced5"))
    painter = QPainter(image)
    if board._shadow is not None and board._shadow.isVisible():
        painter.drawPixmap(padding, padding, board._shadow.grab())
    painter.drawPixmap(padding, padding, board.grab())
    overlay = board.canvas.tool_overlay
    if overlay is not None and overlay.isVisible():
        origin = overlay.visual_rect.topLeft()+QPointF(board.canvas.pos())+QPointF(padding, padding)
        painter.drawPixmap(origin, overlay.grab())
    painter.end()
    return image


def run_polish_checks(board, check, artifacts):
    board.resize(640, 440)
    canvas = board.canvas
    canvas.finish_editing()
    canvas.document = Document()
    canvas.set_selection(set())
    windows.focus_window(board)
    canvas.setFocus()
    QTest.qWait(80)
    paper = board.paper_rect()
    check("Native edge-to-edge content and compact top strip", canvas.x()-paper.left() == CANVAS_INSET == 0
          and canvas.y()-paper.top() == TOP_STRIP == 11)
    check("No unnecessary pin control", len([w for w in board.children() if w.inherits("QToolButton")]) == 2)
    canvas.document.commit((Stroke(((30, 90), (350, 90)), 5),
                            Shape("Rounded rectangle", (50, 140), (220, 270), 3),
                            Text((265, 155), "Compact paper", 20)), "Fixture")
    canvas.set_tool("Eraser")
    canvas.set_number(4)
    canvas.cursor_position = (150, 150)
    canvas.sync_tool_overlay()
    QTest.qWait(50)
    overlay = canvas.tool_overlay
    get_style = windows.bind(windows.user32, "GetWindowLongPtrW", C.c_ssize_t, W.HWND, C.c_int)
    style = get_style(int(overlay.winId()), -20)
    check("Native tool overlay transparent and non-activating", bool(style & 0x20) and bool(style & 0x08000000), hex(style))
    check("Native tool overlay preserves foreground and canvas focus",
          windows.user32.GetForegroundWindow() == int(board.winId()) and canvas.hasFocus())
    for key, mode, size in ((5, "stroke", 64), (5, "circular", 16), (5, "stroke", 16),
                            (1, "circular", 8), (5, "stroke", 8), (4, "circular", 64)):
        QTest.keyClick(canvas, Qt.Key.Key_0+key)
        QApplication.processEvents()
        check(f"Native E → {key}: {mode} {size} px", (canvas.eraser_mode, canvas.eraser_diameter) == (mode, size)
              and overlay.whole_stroke == (mode == "stroke"))
    w, h = canvas.width(), canvas.height()
    positions = (("top", (w/2, 1)), ("bottom", (w/2, h-2)), ("left", (1, h/2)), ("right", (w-2, h/2)),
                 ("top-left", (3, 3)), ("top-right", (w-3, 15)),
                 ("bottom-left", (7, h-7)), ("bottom-right", (w-7, h-7)))
    for name, position in positions:
        canvas.cursor_position = position
        canvas.sync_tool_overlay()
        QTest.qWait(30)
        image = overlay.grab().toImage()
        dpr = image.devicePixelRatio()
        rect = overlay.visual_rect
        complete = True
        for dx, dy in ((32, 0), (-32, 0), (0, 32), (0, -32)):
            p = QPointF(position[0]+dx, position[1]+dy)
            if any(r.adjusted(-2, -2, 2, 2).contains(p) for r in canvas.control_rects()):
                continue
            x, y = round((p.x()-rect.x())*dpr), round((p.y()-rect.y())*dpr)
            complete &= any(image.pixelColor(xx, yy).alpha() > 100
                            for xx in range(x-1, x+2) for yy in range(y-1, y+2))
        check(f"Native complete cursor at {name}", complete)
        capture_board(board).save(str(artifacts/f"cursor-{name}.png"))
    canvas.cursor_position = (100, 100)
    canvas.sync_tool_overlay()
    canvas.set_number(5)
    capture_board(board).save(str(artifacts/"cursor-stroke-mode.png"))
    canvas.set_number(5)
    canvas.begin_editing(Text((80, 70)))
    QTest.qWait(50)
    check("Native text editing hides tool overlay", not overlay.isVisible())
    tool_state = canvas.tool, canvas.eraser_mode, canvas.eraser_key
    QTest.keyClicks(QApplication.focusWidget(), "1234554321")
    check("Native exact 1234554321 leaves eraser state unchanged", canvas.editor.toPlainText() == "1234554321"
          and (canvas.tool, canvas.eraser_mode, canvas.eraser_key) == tool_state)
    canvas.finish_editing()
    canvas.cursor_position = (100, 100)
    canvas.sync_tool_overlay()
    board.minimize_to_tray()
    check("Native minimise hides tool surface", not overlay.isVisible())
    board.restore()
    QTest.qWait(50)
    canvas.set_tool("Draw")

    monitor = windows.monitors()[0]
    preview = PreviewOverlay(monitor)
    try:
        preview.set_outline(Rect(monitor.rect.x+80, monitor.rect.y+80, 520, 260))
        preview.show()
        QTest.qWait(30)
        pixmap = preview.grab()
        for name, background in (("bright", "#ffffff"), ("dark", "#26303d")):
            image = QImage(700, 420, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor(background))
            painter = QPainter(image)
            painter.drawPixmap(QRectF(0, 0, 700, 420), pixmap, QRectF(0, 0, 700, 420))
            painter.end()
            image.save(str(artifacts/f"preview-{name}.png"))
        check("Native dotted preview keeps focus on board", windows.user32.GetForegroundWindow() == int(board.winId()))
    finally:
        preview.close()
        preview.deleteLater()
