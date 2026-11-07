"""Compact vector controls with a single pointer-owned tap/hold interaction."""
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QConicalGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QToolButton

TARGET = 42
ICON = 20


def paint_icon(p, name, color='#202124'):
    p.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    if name == 'Draw':
        for i, point in enumerate(((2,18),(4,11),(14,1),(19,6),(9,16),(2,18))):
            (path.moveTo if i == 0 else path.lineTo)(*point)
        p.drawPath(path)
        p.drawLine(QPointF(12,3),QPointF(17,8))
    elif name == 'Eraser':
        for i, point in enumerate(((2,12),(12,2),(19,9),(10,18),(7,18),(2,12))):
            (path.moveTo if i == 0 else path.lineTo)(*point)
        p.drawPath(path)
        p.drawLine(QPointF(7,7),QPointF(14,14))
    elif name == 'Select':
        for i, point in enumerate(((3,1),(3,17),(8,13),(12,20),(15,18),(11,11),(18,11),(3,1))):
            (path.moveTo if i == 0 else path.lineTo)(*point)
        p.drawPath(path)
    elif name == 'Shape':
        p.drawRoundedRect(QRectF(1,2,12,12),1,1)
        p.setBrush(QColor('#f6f8fa'))
        p.drawEllipse(QRectF(9,9,10,10))
    elif name == 'Text':
        p.drawLine(2,3,18,3)
        p.drawLine(10,3,10,18)
        p.drawLine(6,18,14,18)
    elif name == 'Colour':
        gradient = QConicalGradient(QPointF(10,10), 0)
        for step, value in enumerate(('#f44336','#ffda38','#46c961','#21b5ea','#7a5ded','#f44336')):
            gradient.setColorAt(step/5,QColor(value))
        p.setBrush(gradient)
        p.setPen(QPen(QColor('#ffffff'),1))
        p.drawEllipse(QRectF(0,0,20,20))
    elif name in ('Undo','Redo'):
        if name == 'Redo':
            p.translate(20,0)
            p.scale(-1,1)
        path.moveTo(7,4)
        path.lineTo(2,8)
        path.lineTo(7,12)
        path.moveTo(3,8)
        path.lineTo(12,8)
        path.cubicTo(20,8,20,18,11,18)
        p.drawPath(path)
    elif name == 'Grip':
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        for x in (6,13):
            for y in (4,10,16):
                p.drawEllipse(QPointF(x,y),1.25,1.25)


class ToolButton(QToolButton):
    held = Signal()
    drag_started = Signal(object)
    dragged = Signal(object)
    drag_finished = Signal()

    def __init__(self, name, parent=None, *, hold=False, grip=False):
        super().__init__(parent)
        self.name, self.hold, self.grip = name, hold, grip
        self.pointer = None
        self.origin = None
        self.consumed = False
        self.native_sequence = False
        self.suppress_synthetic = QTimer(self)
        self.suppress_synthetic.setSingleShot(True)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.long_press)
        self.setFixedSize(24 if grip else TARGET, TARGET)
        self.setAccessibleName('Move floating tools' if grip else name)
        self.setToolTip('Drag to move floating tools' if grip else name + (' · hold or right-click for options' if hold else ''))
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCheckable(not grip)

    def cancel_pointer(self):
        self.timer.stop()
        self.pointer = None
        self.origin = None
        self.setDown(False)

    def press(self, pos, source):
        if self.pointer is not None or not self.isEnabled():
            return
        self.pointer, self.origin, self.consumed = source, QPointF(pos), False
        self.setDown(True)
        if self.grip:
            self.drag_started.emit(pos)
        elif self.hold:
            interval = QApplication.styleHints().mousePressAndHoldInterval()
            self.timer.start(interval if interval > 0 else 500)

    def move_pointer(self, pos):
        if self.origin is None:
            return
        if self.grip:
            self.dragged.emit(pos)
        elif ((pos-self.origin).manhattanLength() > QApplication.startDragDistance()
              or not self.rect().contains(self.mapFromGlobal(pos.toPoint()))):
            self.timer.stop()
            self.consumed = True
            self.setDown(False)

    def release(self, pos):
        if self.pointer is None:
            return
        fire = not self.consumed and self.rect().contains(self.mapFromGlobal(pos.toPoint()))
        self.cancel_pointer()
        if self.grip:
            self.drag_finished.emit()
        elif fire:
            self.clicked.emit()

    def long_press(self):
        if self.pointer is not None:
            self.consumed = True
            self.setDown(False)
            self.held.emit()

    def mousePressEvent(self, event):
        if event.source() != Qt.MouseEventSource.MouseEventNotSynthesized and self.suppress_synthetic.isActive():
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self.hold:
            self.cancel_pointer()
            self.held.emit()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.press(event.globalPosition(),'mouse')
        event.accept()

    def mouseMoveEvent(self, event):
        if self.pointer == 'mouse':
            self.move_pointer(event.globalPosition())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.pointer == 'mouse' and event.button() == Qt.MouseButton.LeftButton:
            self.release(event.globalPosition())
        event.accept()

    def tabletEvent(self, event):
        self.suppress_synthetic.start(500)
        if event.type() == QEvent.Type.TabletPress:
            self.press(event.globalPosition(),'tablet')
        elif event.type() == QEvent.Type.TabletMove and self.pointer == 'tablet':
            self.move_pointer(event.globalPosition())
        elif event.type() == QEvent.Type.TabletRelease and self.pointer == 'tablet':
            self.release(event.globalPosition())
        event.accept()  # Qt must not synthesize another mouse activation.

    def event(self, event):
        kind = event.type()
        if kind in (QEvent.Type.TouchBegin,QEvent.Type.TouchUpdate,QEvent.Type.TouchEnd,QEvent.Type.TouchCancel):
            self.suppress_synthetic.start(500)
            points = event.points()
            if kind == QEvent.Type.TouchCancel or len(points) != 1:
                self.cancel_pointer()
            elif kind == QEvent.Type.TouchBegin:
                self.press(points[0].globalPosition(),'touch')
            elif kind == QEvent.Type.TouchUpdate and self.pointer == 'touch':
                self.move_pointer(points[0].globalPosition())
            elif kind == QEvent.Type.TouchEnd and self.pointer == 'touch':
                self.release(points[0].globalPosition())
            event.accept()
            return True
        if kind in (QEvent.Type.Hide,QEvent.Type.EnabledChange) and hasattr(self,'timer'):
            self.cancel_pointer()
        return super().event(event)

    def leaveEvent(self,event):
        if self.pointer and not self.grip:
            self.timer.stop()
            self.consumed = True
        super().leaveEvent(event)

    def contextMenuEvent(self,event):
        event.accept()  # Right button and native hold already share the options route.

    def paintEvent(self,event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked() or self.isDown() or self.underMouse() or self.hasFocus():
            p.setPen(QPen(QColor('#77d7e6'),1) if self.isChecked() else Qt.PenStyle.NoPen)
            p.setBrush(QColor('#b8eef3') if self.isChecked() else QColor(120,160,200,25))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),13,13)
        if not self.isEnabled():
            p.setOpacity(.32)
        p.translate((self.width()-ICON)/2,(self.height()-ICON)/2)
        paint_icon(p,self.name)
