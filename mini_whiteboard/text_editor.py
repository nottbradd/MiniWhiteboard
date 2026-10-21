"""A real editor owns all typing; only finish/help commands are intercepted."""
import math

from PySide6.QtCore import QEvent, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor, QTextOption, QPainterPath, QPainter
from PySide6.QtWidgets import (QApplication, QFrame, QTextEdit, QGraphicsView, QGraphicsScene,
                              QGraphicsProxyWidget, QWidget)

from .settings import INK, SELECTION
from .transforms import translation
from . import rendering


class TextEditor(QTextEdit):
    committed = Signal()
    focus_finished = Signal()
    help_requested = Signal()

    def __init__(self, obj, parent):
        super().__init__(parent)
        self.closing = False
        self.commit_timer = QTimer(self)
        self.commit_timer.setSingleShot(True)
        self.commit_timer.timeout.connect(self.commit_if_unfocused)
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"QTextEdit {{ background: transparent; color: {obj.color}; "
                           f"border: 1px dashed {SELECTION}; padding: 0; }}")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.layout_width = obj.layout_width
        self.setLineWrapMode(QTextEdit.LineWrapMode.FixedPixelWidth)
        self.setLineWrapColumnOrWidth(obj.layout_width)
        self.setTabChangesFocus(False)
        self.document().setDocumentMargin(2)
        from .shortcuts import ui_font_family
        font = QFont(ui_font_family())
        font.setPointSizeF(obj.size)
        self.setFont(font)
        option = self.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(option)
        self.setPlainText(obj.text)
        self.move(0, 0)
        self.textChanged.connect(self.fit_contents)
        self.fit_contents()
        self.moveCursor(QTextCursor.MoveOperation.End)

    def fit_contents(self):
        self.document().setTextWidth(self.layout_width)
        size = self.document().size()
        self.resize(self.layout_width+2, max(30, math.ceil(size.height())+2))

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            # Accepting this delivers the real key to this editor, rather than
            # allowing an ancestor's QAction/QShortcut to steal it.
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape or (
                event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and
                event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.committed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F1:
            self.help_requested.emit()
            return
        # Letters, numbers, Enter, arrows, clipboard, delete and undo/redo all
        # retain QTextEdit behavior. Never forward these to the canvas router.
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # A native context menu temporarily takes focus; returning from it must
        # not commit/destroy the editor underneath copy/paste actions.
        if not self.closing and event.reason() != Qt.FocusReason.PopupFocusReason:
            self.commit_timer.start(0)

    def commit_if_unfocused(self):
        if (not self.closing and self.isVisible() and not self.hasFocus()
                and not self.popup_active()):
            self.focus_finished.emit()

    def popup_active(self):
        # A proxy embeds QTextEdit's menus in its scene. Such menus are visible
        # child widgets, but are absent from QApplication.activePopupWidget().
        return (QApplication.activePopupWidget() is not None or
                any(child.isVisible() and child.windowType() == Qt.WindowType.Popup
                    for child in self.findChildren(QWidget)))


class MaskedEditorProxy(QGraphicsProxyWidget):
    """Mask only the embedded text widget; its popup children keep normal UI."""

    def __init__(self, obj):
        super().__init__()
        self.obj = obj

    def paint(self, painter, option, widget=None):
        painter.save()
        if self.obj.erasures:
            clip = QPainterPath()
            clip.addRect(self.boundingRect())
            # QTextEdit has a one-pixel frame around its two-pixel document margin.
            offset = translation(1-self.obj.position[0], 1-self.obj.position[1])
            mask = rendering.qt_transform(offset).map(rendering.mask_path(self.obj.erasures))
            painter.setClipPath(clip.subtracted(mask), Qt.ClipOperation.IntersectClip)
        super().paint(painter, option, widget)
        painter.restore()


class EditorOverlay(QGraphicsView):
    """Temporary scene for one real QTextEdit, without changing the object canvas."""

    def __init__(self, obj, editor, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.editor = editor
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QGraphicsView { background: transparent; border: none; }")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setAutoFillBackground(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setScene(QGraphicsScene(self))
        self.proxy = MaskedEditorProxy(obj)
        self.scene().addItem(self.proxy)
        self.proxy.setWidget(editor)
        transform = obj.transform @ translation(obj.position[0]-1, obj.position[1]-1)
        self.proxy.setTransform(rendering.qt_transform(transform))
        self.setGeometry(canvas.rect())
        self.setSceneRect(QRectF(canvas.rect()))
        from .alpha_clip import EditorClip
        self.clip_effect = EditorClip(canvas, self)
        self.setGraphicsEffect(self.clip_effect)
        editor.textChanged.connect(self.keep_caret_visible)
        editor.cursorPositionChanged.connect(self.keep_caret_visible)

    def keep_caret_visible(self):
        # Only this temporary view pans. Committed artwork and board geometry
        # remain unchanged, and no canvas scrollbar is introduced.
        extent = self.proxy.mapRectToScene(self.proxy.boundingRect())
        self.setSceneRect(QRectF(self.canvas.rect()).united(extent.adjusted(-12, -12, 12, 12)))
        caret = self.proxy.mapRectToScene(QRectF(self.editor.cursorRect()))
        self.ensureVisible(caret, 12, 12)

    def activate_editor(self):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.scene().setFocus(Qt.FocusReason.MouseFocusReason)
        self.proxy.setFocus(Qt.FocusReason.MouseFocusReason)
        self.editor.setFocus(Qt.FocusReason.MouseFocusReason)
        self.keep_caret_visible()

    def owns_mouse_event(self, watched, event):
        if watched is self.editor or self.editor.isAncestorOf(watched):
            return True
        if watched in (self, self.viewport()):
            p = event.position().toPoint()
            if watched is self:
                p = self.viewport().mapFrom(self, p)
            scene_pos = self.mapToScene(p)
            return self.proxy.contains(self.proxy.mapFromScene(scene_pos))
        return False

    def mousePressEvent(self, event):
        if self.editor.closing:
            event.accept()
            return
        if self.editor.popup_active():
            super().mousePressEvent(event)
            self.restore_after_popup()
            return
        if not self.proxy.contains(self.proxy.mapFromScene(self.mapToScene(event.position().toPoint()))):
            self.canvas.editor_outside_press(self.editor, event)
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.editor.closing:
            event.accept()
        elif self.editor.popup_active():
            super().mouseDoubleClickEvent(event)
            self.restore_after_popup()
        elif not self.proxy.contains(self.proxy.mapFromScene(self.mapToScene(event.position().toPoint()))):
            self.canvas.editor_outside_press(self.editor, event)
        else:
            super().mouseDoubleClickEvent(event)

    def restore_after_popup(self):
        if (self.canvas.editor is self.editor and not self.editor.closing
                and not self.editor.popup_active()):
            self.activate_editor()

    def resizeEvent(self, event):
        self.setSceneRect(QRectF(self.viewport().rect()))
        super().resizeEvent(event)
