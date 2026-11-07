"""One optional, event-driven tool surface for the active board interaction group."""
import weakref
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QColorDialog, QFrame, QGridLayout,
                              QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget)
from .appearance import interface_font
from .settings import PEN_SIZES, FONT_SIZES, SHAPES, ERASER_SIZES, PALETTE_COLORS
from .surfaces import Surface
from .tool_buttons import ToolButton, TARGET

TOOLS = ('Draw','Eraser','Select','Shape','Text')
ACTIONS = (*TOOLS,'Colour','Undo','Redo')
GAP = 8  # Includes separation from board shadows and work-area edges.


def clamp_rect(rect, work):
    return QRect(max(work.left(),min(rect.x(),work.right()-rect.width()+1)),
                 max(work.top(),min(rect.y(),work.bottom()-rect.height()+1)),
                 min(rect.width(),work.width()),min(rect.height(),work.height()))


def place_tools(board, size, work, offset=None):
    """All arguments are Qt global logical units, preserving monitor origins."""
    safe = work.adjusted(GAP,GAP,-GAP,-GAP)
    if offset is not None:
        return clamp_rect(QRect(board.topLeft()+offset,size),safe), 'manual'
    x = round(board.center().x()-size.width()/2)
    above = QRect(QPoint(x,board.top()-GAP-size.height()),size)
    below = QRect(QPoint(x,board.bottom()+1+GAP),size)
    for candidate, mode in ((above,'above'),(below,'below')):
        # Horizontal clamping is allowed near screen edges; vertical fit decides.
        if candidate.top() >= safe.top() and candidate.bottom() <= safe.bottom():
            return clamp_rect(candidate,safe), mode
    inside = QRect(QPoint(x,board.bottom()-size.height()-GAP),size)
    return clamp_rect(inside,safe), 'inside'


class ToolSurface(Surface,QFrame):
    def __init__(self, manager, board):
        super().__init__(board,Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.manager = manager
        self.interactive_surface = True
        self.init_surface(board.platform,board.canvas.preferences)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAccessibleName('Floating tools')
        self.setWindowTitle('Mini Whiteboard floating tools')

    def paintEvent(self,event):
        self.paint_surface()

    def dismiss_for_theme(self):
        self.refresh_appearance()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key.Key_Escape:
            self.manager.close_options(refocus=True)
            event.accept()
        else:
            super().keyPressEvent(event)


class ToolPalette(ToolSurface):
    def __init__(self, manager, board):
        super().__init__(manager,board)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
        self.buttons = {}
        self.grip = ToolButton('Grip',self,grip=True)
        self.grip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.grip.drag_started.connect(manager.start_drag)
        self.grip.dragged.connect(manager.drag)
        self.grip.drag_finished.connect(manager.finish_drag)
        self.divider = QFrame(self)
        self.divider.setStyleSheet('background:rgba(75,85,110,50);')
        for name in ACTIONS:
            b = ToolButton(name,self,hold=name in TOOLS)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda checked=False, n=name: manager.choose(n))
            b.held.connect(lambda n=name: manager.open_options(n))
            self.buttons[name] = b
        self.columns = 8

    def fit(self, work):
        # Target sizes remain 42 logical px; only wrap when the screen requires it.
        self.columns = max(1,min(8,(work.width()-2*GAP-32)//TARGET))
        rows = (len(ACTIONS)+self.columns-1)//self.columns
        width = 32+self.columns*TARGET+(7 if self.columns==8 else 0)
        self.setFixedSize(width,4+rows*TARGET)
        self.grip.move(4,2)
        for index,button in enumerate(self.buttons.values()):
            row,col = divmod(index,self.columns)
            extra = 7 if self.columns==8 and col>=5 else 0
            button.move(28+col*TARGET+extra,2+row*TARGET)
        self.divider.setVisible(self.columns==8)
        self.divider.setGeometry(28+5*TARGET+3,11,1,24)

    def sync(self,canvas):
        for name,button in self.buttons.items():
            button.setChecked(name==canvas.tool)
        self.buttons['Undo'].setEnabled(canvas.document.index>0 or canvas.editor is not None)
        self.buttons['Redo'].setEnabled(canvas.document.index<len(canvas.document.history))
        self.buttons['Colour'].setToolTip('Colour · '+canvas.active_color)

    def cancel_pointers(self):
        self.grip.cancel_pointer()
        for button in self.buttons.values():
            button.cancel_pointer()


class ColourSwatch(QToolButton):
    """Keep the colour independent of the button's checked/hover/focus frame."""
    def __init__(self, color):
        super().__init__()
        self.color = QColor(color)

    def paintEvent(self,event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.color)
        painter.setPen(QPen(QColor('#7e8794'),1))
        painter.drawEllipse(QRectF(self.width()/2-6,self.height()/2-6,12,12))


class Options(ToolSurface):
    def __init__(self,manager,board,tool,work):
        super().__init__(manager,board)
        self.setAccessibleName(tool+' options')
        self.setWindowTitle('Mini Whiteboard '+tool+' options')
        self.tool = tool
        self.identifiers = set(board.canvas.selected_ids)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8,8,8,8)
        outer.setSpacing(4)
        title = QLabel(tool)
        title.setFont(interface_font('compact_heading'))
        title.setStyleSheet('color:#202124;background:transparent;')
        outer.addWidget(title)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; }')
        content = QWidget()
        self.grid = QGridLayout(content)
        self.grid.setContentsMargins(0,0,0,0)
        self.grid.setSpacing(2)
        self.row = 0
        self.columns = max(1,min(7,(work.width()-2*GAP-26)//TARGET))
        canvas = board.canvas
        if tool == 'Draw':
            self.heading('Stroke size')
            self.choices([(str(size)+' px',lambda n=n:canvas.set_number(n),canvas.pen_key==n)
                          for n,size in PEN_SIZES.items()])
        elif tool == 'Eraser':
            self.heading('Size')
            self.choices([(str(size)+' px',lambda n=n:canvas.set_number(n),
                           canvas.eraser_mode=='circular' and canvas.eraser_key==n) for n,size in ERASER_SIZES.items()])
            self.action('Whole stroke',lambda:canvas.set_number(5),canvas.eraser_mode=='stroke')
        elif tool == 'Shape':
            self.heading('Shape')
            # Real supported shapes; no invented fill/line-style controls.
            for n,name in SHAPES.items():
                self.action(name,lambda n=n:canvas.set_number(n),canvas.shape_key==n)
        elif tool == 'Text':
            self.heading('Font size')
            self.choices([(str(size)+' pt',lambda n=n:canvas.set_number(n),canvas.font_key==n)
                          for n,size in FONT_SIZES.items()])
        elif tool == 'Select':
            for label,fn in (('Select all',canvas.select_all),('Duplicate',canvas.duplicate_selection),
                             ('Bring to front',lambda:canvas.reorder(True)),('Send to back',lambda:canvas.reorder(False)),
                             ('Delete',canvas.delete_selection)):
                self.action(label,fn,enabled=label=='Select all' or bool(canvas.editable_selection()))
        if tool in ('Draw','Shape','Text','Colour'):
            self.heading('Colour')
            items = [(name,lambda c=color:canvas.apply_color(c,self.identifiers),
                      QColor(canvas.active_color)==QColor(color),color) for name,color in PALETTE_COLORS]
            self.choices(items)
            self.action('Custom colour…',self.custom_colour)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        content.adjustSize()
        width = min(work.width()-2*GAP,max(180,content.sizeHint().width()+18))
        height = min(work.height()-2*GAP,content.sizeHint().height()+48)
        self.setFixedSize(width,height)

    def heading(self,text):
        label = QLabel(text)
        label.setFont(interface_font('support'))
        label.setStyleSheet('color:#454954;background:transparent;')
        self.grid.addWidget(label,self.row,0,1,self.columns)
        self.row += 1

    def button(self,text,fn,checked=False,enabled=True,color=None):
        b = ColourSwatch(color) if color else QToolButton()
        b.setText('' if color else text)
        b.setAccessibleName(text)
        b.setToolTip(text)
        b.setMinimumHeight(TARGET)
        b.setFont(interface_font('support'))
        b.setCheckable(True)
        b.setChecked(checked)
        b.setEnabled(enabled)
        b.setStyleSheet('QToolButton { color:#202124; background:transparent; border:1px solid transparent; border-radius:10px; padding:2px; }'
                        'QToolButton:checked { background:#b8eef3; border-color:#77d7e6; }'
                        'QToolButton:hover, QToolButton:focus { background:rgba(120,160,200,35); border-color:#8aa2b8; }'
                        'QToolButton:disabled { color:#9b9da1; }')
        b.clicked.connect(lambda: self.manager.option_action(fn))
        return b

    def choices(self,items):
        for index,item in enumerate(items):
            text,fn,checked,*color = item
            b = self.button(text,fn,checked,color=color[0] if color else None)
            b.setFixedWidth(TARGET)
            self.grid.addWidget(b,self.row+index//self.columns,index%self.columns)
        self.row += (len(items)+self.columns-1)//self.columns

    def action(self,text,fn,checked=False,enabled=True):
        self.grid.addWidget(self.button(text,fn,checked,enabled),self.row,0,1,self.columns)
        self.row += 1

    def custom_colour(self):
        manager, canvas = self.manager,self.manager.board.canvas
        identifiers = self.identifiers
        manager.close_options()
        dialog = QColorDialog(QColor(canvas.active_color),manager.palette)
        dialog.setWindowTitle('Colour')
        # Nonblocking lifetime belongs to the toolbar group, including OS popups.
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        manager.colour_dialog = dialog
        dialog.colorSelected.connect(lambda color:canvas.apply_color(color.name(),identifiers))
        dialog.finished.connect(lambda _:manager.colour_finished())
        dialog.open()


class FloatingTools(QObject):
    def __init__(self,app,preferences):
        super().__init__(app)
        self.app,self.preferences = app,preferences
        self.boards = weakref.WeakSet()
        self.offsets = weakref.WeakKeyDictionary()
        self.board = self.palette = self.options = self.colour_dialog = None
        self.drag_origin = None
        self.capture_suspended = False
        self.hiding = False
        self.closed = False
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh)
        preferences.floating_tools_changed.connect(self.preference_changed)
        app.installEventFilter(self)
        app.focusChanged.connect(self.schedule)
        app.applicationStateChanged.connect(self.schedule)

    def add_board(self,board):
        self.boards.add(board)
        board.canvas.tools_changed.connect(self.sync)
        board.deleted.connect(self.remove_board)
        self.schedule()

    def remove_board(self,board):
        self.boards.discard(board)
        self.offsets.pop(board,None)
        if self.board is board:
            self.retire()
            self.board = None

    def group_board(self,widget):
        while widget is not None:
            if widget in self.boards:
                return widget
            if widget in (self.palette,self.options,self.colour_dialog):
                return self.board
            widget = widget.parentWidget() if isinstance(widget,QWidget) else None
        return None

    def schedule(self,*_):
        if not self.closed:
            self.refresh_timer.start(0)

    def preference_changed(self):
        if not self.preferences.floating_tools:
            self.retire()
        self.schedule()

    def activate(self,board):
        if board not in self.boards or board._closing:
            return
        if self.board is not board:
            self.retire()
            self.board = board
        self.schedule()

    def work_area(self):
        return self.board.screen().availableGeometry()

    def board_rect(self):
        r = self.board.paper_rect().toAlignedRect()
        r.moveTopLeft(self.board.mapToGlobal(r.topLeft()))
        return r

    def refresh(self):
        if self.closed:
            return
        active = self.app.activePopupWidget() or self.app.activeModalWidget() or self.app.activeWindow()
        target = self.group_board(active)
        if target is not None and target is not self.board:
            self.activate(target)
        b = self.board
        visible = (self.preferences.floating_tools and not self.capture_suspended and b is not None
                   and b.isVisible() and not b._closing and not b.canvas.suspended and target is b)
        if not visible:
            self.hide()
            return
        if self.palette is None:
            self.palette = ToolPalette(self,b)
        self.position()
        self.palette.sync(b.canvas)
        if not self.palette.isVisible():
            self.palette.show()

    def position(self):
        if self.palette is None or self.board is None:
            return
        work = self.work_area()
        self.palette.fit(work)
        rect,self.placement = place_tools(self.board_rect(),self.palette.size(),work,self.offsets.get(self.board))
        self.palette.move(rect.topLeft())
        if self.options is not None:
            r,_ = place_tools(rect,self.options.size(),work)
            self.options.move(r.topLeft())

    def sync(self):
        if self.palette is not None and self.board is not None:
            self.palette.sync(self.board.canvas)

    def choose(self,name):
        if self.board is None:
            return
        self.close_options()
        c = self.board.canvas
        c.finish_editing()
        if name in TOOLS:
            c.set_tool(name)
        elif name in ('Undo','Redo'):
            c.undo_redo(name=='Redo')
        elif name == 'Colour':
            self.open_options(name)
            return
        self.refocus()
        self.sync()

    def open_options(self,name):
        if self.board is None or self.palette is None:
            return
        self.close_options()
        canvas = self.board.canvas
        canvas.finish_editing()
        if name in TOOLS:
            canvas.set_tool(name)
        self.options = Options(self,self.board,name,self.work_area())
        self.position()
        self.options.show()
        self.sync()

    def option_action(self,fn):
        fn()
        self.sync()
        # Keep the small surface open for several settings; refresh its checks.
        if self.options is not None:
            tool = self.options.tool
            self.open_options(tool)

    def refocus(self):
        if self.board is not None and self.board.isVisible() and not self.board._closing:
            self.board.activateWindow()
            self.board.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def colour_finished(self):
        self.colour_dialog = None
        if not self.hiding and not self.closed:
            self.refocus()
        self.sync()

    def close_options(self,refocus=False):
        if self.options is not None:
            popup,self.options = self.options,None
            popup.close()
            popup.deleteLater()
        if refocus:
            self.refocus()

    def start_drag(self,pos):
        self.close_options()
        if self.palette is not None:
            self.drag_origin = (QPointF(pos),self.palette.pos())

    def drag(self,pos):
        if self.drag_origin is None or self.palette is None:
            return
        start,origin = self.drag_origin
        target = origin+(pos-start).toPoint()
        rect = clamp_rect(QRect(target,self.palette.size()),self.work_area().adjusted(GAP,GAP,-GAP,-GAP))
        self.offsets[self.board] = rect.topLeft()-self.board_rect().topLeft()
        self.palette.move(rect.topLeft())
        self.placement = 'manual'

    def finish_drag(self):
        self.drag_origin = None
        self.refocus()

    def hide(self):
        self.hiding = True
        self.close_options()
        if self.colour_dialog is not None:
            dialog,self.colour_dialog = self.colour_dialog,None
            dialog.reject()
        if self.palette is not None:
            self.palette.cancel_pointers()
            self.palette.hide()
        self.drag_origin = None
        self.hiding = False

    def retire(self):
        active = self.app.activeWindow()
        target = self.group_board(active)
        self.hide()
        if self.palette is not None:
            palette,self.palette = self.palette,None
            palette.close()
            palette.deleteLater()
        # Closing a Tool can activate its old parent. Preserve an already-active
        # other board during a switch, never activate on an external focus change.
        if target is not None and target is not self.board and active is target:
            if self.group_board(self.app.activeWindow()) is self.board:
                target.activateWindow()
                target.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_capture_suspended(self,value):
        self.capture_suspended = value
        if value:
            self.hide()
        else:
            self.schedule()

    def eventFilter(self,watched,event):
        if self.closed:
            return False
        kind = event.type()
        if watched in self.boards:
            if kind == QEvent.Type.WindowActivate:
                self.schedule()
            elif kind in (QEvent.Type.Hide,QEvent.Type.Close):
                if watched is self.board:
                    self.hide()
            elif kind in (QEvent.Type.Move,QEvent.Type.Resize,QEvent.Type.Show,
                          QEvent.Type.WindowDeactivate,QEvent.Type.DevicePixelRatioChange):
                self.schedule()
        if kind == QEvent.Type.MouseButtonPress and self.options is not None and isinstance(watched,QWidget):
            if watched.window() not in (self.options,self.palette) and watched is not self.colour_dialog:
                self.close_options()
        if kind in (QEvent.Type.ApplicationDeactivate,QEvent.Type.ApplicationActivate):
            self.schedule()
        return False

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.refresh_timer.stop()
        self.app.removeEventFilter(self)
        self.app.focusChanged.disconnect(self.schedule)
        self.app.applicationStateChanged.disconnect(self.schedule)
        self.preferences.floating_tools_changed.disconnect(self.preference_changed)
        self.retire()
        self.boards.clear()
        self.board = None
