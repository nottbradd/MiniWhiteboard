"""Canvas gestures, transient selection, and focus-scoped keyboard routing."""
from dataclasses import replace
import math
import time

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QCursor, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QWidget

from .document import Document, Shape, Stroke, Text, ImageObject, transformed
from .geometry import constrained_end, Rect
from . import rendering
from .settings import (FONT_SIZES, PEN_SIZES, SHAPES, TOOL_KEYS, ERASER_SIZES,
                       DRAG_THRESHOLD, DEFAULT_ERASER_KEY,
                       DIRTY_PADDING, DIRTY_RECT_LIMIT, RADIUS, BORDER_WIDTH, CONTAINMENT_TOLERANCE)
from .text_editor import TextEditor, EditorOverlay
from .transforms import Erasure, PaintClip, translation, resize_transform, rotate_transform
from .scene import Scene
from .editing_actions import EditingActions
from .snapping import SnapPreferences, SnapTargets


class Canvas(EditingActions, QWidget):
    def __init__(self, parent=None, preferences=None):
        super().__init__(parent)
        self.document = Document()
        self.scene = Scene()
        self.background_cache = None
        self.suspended = False
        self.ocr_service = self.ocr_panel = None
        self.tool_overlay = None
        self.clip_spec = None
        self.preferences = preferences if preferences is not None else SnapPreferences()
        self.preferences.changed.connect(self.clear_guides)
        self.guide_lines = ()
        self.snap_targets = None
        self.gesture_bounds = QRectF()
        self.tool = "Draw"
        self.pen_key = self.font_key = self.shape_key = 1
        self.eraser_key = DEFAULT_ERASER_KEY
        self.eraser_mode = "circular"
        self.selected_ids = set()
        self.frame = None
        self.editor = self.editor_overlay = self.editing_object = None
        self.dismissed_click = None
        self.gesture = None
        self.gesture_before = None
        self.gesture_sources = ()
        self.gesture_has_text = False
        self.gesture_frame = None
        self.selection_before = set()
        self.preview = self.original = None
        self.start = self.last_sample = None
        self.points = []
        self.resize_handle = None
        self.dragged = False
        self.marquee_add = False
        self.click_hit = None
        self.cursor_position = None
        from .feedback import FeedbackLabel, ShortcutReference
        self.feedback = FeedbackLabel(self)
        self.help_panel = ShortcutReference(self.window())
        self.init_actions()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.update_cursor()

    @property
    def selected_id(self):
        """Single-selection convenience for existing board integrations."""
        return next(iter(self.selected_ids)) if len(self.selected_ids) == 1 else None

    @selected_id.setter
    def selected_id(self, identifier):
        self.set_selection({identifier} if identifier else set())

    @property
    def selected(self):
        return self.document.get(self.selected_id)

    @property
    def selected_objects(self):
        return tuple(obj for obj in self.document.objects if obj.id in self.selected_ids)

    @property
    def eraser_diameter(self):
        return ERASER_SIZES[self.eraser_key]

    @property
    def current_objects(self):
        after = self.gesture_after
        return after if after is not None else self.document.objects

    @property
    def gesture_after(self):
        # Materialize once at commit (or when a test explicitly requests it),
        # never during pointer updates or painting.
        return self.scene.after() if self.scene.previews else None

    def sync_scene(self):
        if self.ocr_panel is not None and self.document.get(self.ocr_panel.image.id) is not self.ocr_panel.image:
            self.ocr_panel.close()
        self.scene.sync(self.document.objects)

    def set_screenshot_background(self, obj):
        from .background import ScreenshotBackground
        self.background_cache = ScreenshotBackground(obj) if obj is not None else None
        if self.background_cache is not None:
            self.sync_scene()
            record = self.scene.record(obj.id)
            if record is not None:
                self.background_cache.prepare(self.rect(), self.devicePixelRatioF(), self.clip_spec, record)
        self.update()

    def control_rects(self):
        board = self.window()
        return tuple(QRectF(button.geometry()).translated(-self.x(), -self.y()).adjusted(-1, -1, 1, 1)
                     for button in (getattr(board, "minus", None), getattr(board, "remove", None)) if button is not None)

    def refresh_document_clip(self):
        board = self.window()
        if not hasattr(board, "paper_rect"):
            return
        paper = board.paper_rect()
        paper.translate(-self.x(), -self.y())
        def frozen(rect):
            return Rect(rect.x(), rect.y(), rect.width(), rect.height())
        clip = PaintClip(frozen(QRectF(self.rect())), frozen(paper), RADIUS,
                         tuple(frozen(rect) for rect in self.control_rects()))
        if clip != self.clip_spec:
            self.clip_spec = clip
            self.setMask(QRegion(rendering.clip_path(clip).toFillPolygon().toPolygon()))
            self.update()
        self.sync_tool_overlay()

    def valid_position(self, position):
        p = rendering.point(position)
        return QRectF(self.rect()).contains(p) and (self.clip_spec is None or rendering.clip_path(self.clip_spec).contains(p))

    def invalidate(self, rect):
        if isinstance(rect, QRegion):
            if not rect.isEmpty():
                if rect.rectCount() > DIRTY_RECT_LIMIT:
                    rect = QRegion(rect.boundingRect())
                self.update(rect.intersected(QRegion(self.rect())))
        elif rect is not None and not rect.isEmpty():
            self.update(rect.adjusted(-DIRTY_PADDING, -DIRTY_PADDING, DIRTY_PADDING, DIRTY_PADDING).toAlignedRect().intersected(self.rect()))

    def dirty_region(self, rect):
        return QRegion(rect.adjusted(-DIRTY_PADDING, -DIRTY_PADDING, DIRTY_PADDING, DIRTY_PADDING).toAlignedRect()) if not rect.isEmpty() else QRegion()

    def marquee_rect(self):
        if self.gesture == "marquee" and self.dragged:
            return QRectF(rendering.point(self.start), rendering.point(self.last_sample)).normalized()
        return QRectF()

    def sync_tool_overlay(self):
        if not hasattr(self, "editor"):
            return
        frame = self.frame if self.tool in ("Select", "Shape", "Text") else None
        cursor = self.cursor_position if self.tool == "Eraser" else None
        marquee = self.marquee_rect()
        guides = self.guide_lines
        popup = ((self.palette is not None and self.palette.isVisible()) or
                 (self.context_menu is not None and self.context_menu.isVisible()))
        if self.editor is not None or not self.isVisible() or self.help_panel.isVisible() or popup:
            frame = cursor = None
            marquee = QRectF()
            guides = ()
        endpoints = ()
        if frame and self.tool == "Shape" and self.selected_id:
            record = self.scene.record(self.selected_id)
            obj = record.obj if record else self.selected
            if isinstance(obj, Shape) and obj.kind in ("Line", "Arrow"):
                endpoints = (obj.transform.map(obj.a), obj.transform.map(obj.b))
        if self.tool_overlay is None and (frame is not None or cursor is not None or not marquee.isEmpty() or guides):
            from .overlays import ToolOverlay
            self.tool_overlay = ToolOverlay(self)
        if self.tool_overlay is not None:
            self.tool_overlay.sync(frame, cursor, self.eraser_diameter, self.eraser_mode == "stroke", endpoints, marquee, guides)

    def clear_guides(self):
        self.guide_lines = ()
        self.sync_tool_overlay()

    def hit_test(self, position, include_locked=False):
        self.sync_scene()
        p = rendering.point(position)
        candidates = self.scene.query(QRectF(p.x()-.01, p.y()-.01, .02, .02), hits=True,
                                      reverse=True, editable=not include_locked)
        return next((record.obj for record in candidates if (include_locked or not record.obj.locked)
                     and rendering.hit_path(record.obj).contains(p)), None)

    def set_selection(self, identifiers):
        self.sync_scene()
        self.selected_ids = {i for i in identifiers if (r := self.scene.record(i)) is None or not r.obj.locked}
        self.frame = rendering.selection_frame(self.selected_objects)
        self.sync_tool_overlay()

    def sync_selection(self, rebuild=True):
        self.sync_scene()
        self.selected_ids.intersection_update(identifier for identifier in self.selected_ids
                                              if (record := self.scene.record(identifier)) is not None and not record.obj.locked and not record.bounds.isEmpty())
        if rebuild:
            self.frame = rendering.selection_frame(self.selected_objects)
        self.sync_tool_overlay()

    def show_feedback(self, text):
        self.feedback.show_message(text)

    def toggle_help(self):
        self.help_panel.setVisible(not self.help_panel.isVisible())
        self.help_panel.raise_()
        self.sync_tool_overlay()

    def show_eraser_feedback(self):
        suffix = "Whole stroke" if self.eraser_mode == "stroke" else f"{self.eraser_diameter} px"
        self.show_feedback(f"Eraser · {suffix}")

    def update_cursor(self, position=None):
        if self.tool == "Eraser" and self.editor is None:
            self.setCursor(Qt.CursorShape.BlankCursor)
            return
        if position is not None and self.frame and self.tool in ("Select", "Shape", "Text"):
            if self.tool == "Shape" and rendering.endpoint_at(self.selected, position) is not None:
                self.setCursor(Qt.CursorShape.CrossCursor)
                return
            handle = rendering.handle_at(self.frame, position, self.devicePixelRatioF())
            if handle is not None:
                if handle == 8:
                    cursor = Qt.CursorShape.CrossCursor
                else:
                    p = self.frame.handle(handle)
                    angle = math.degrees(math.atan2(p[1]-self.frame.center[1], p[0]-self.frame.center[0]))
                    cursor = (Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeFDiagCursor,
                              Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor)[round(angle/45) % 4]
                self.setCursor(cursor)
                return
            if self.tool == "Select" and self.frame.contains(position):
                self.setCursor(Qt.CursorShape.ClosedHandCursor if self.gesture == "move" else Qt.CursorShape.OpenHandCursor)
                return
        self.setCursor({"Draw": Qt.CursorShape.CrossCursor, "Text": Qt.CursorShape.IBeamCursor,
                        "Shape": Qt.CursorShape.CrossCursor, "Select": Qt.CursorShape.ArrowCursor}.get(self.tool, Qt.CursorShape.ArrowCursor))

    def set_tool(self, tool):
        self.cancel_interaction()
        self.tool = tool
        if tool == "Eraser":
            p = self.mapFromGlobal(QCursor.pos())
            self.cursor_position = (p.x(), p.y()) if self.valid_position((p.x(), p.y())) else None
        else:
            self.cursor_position = None
        self.update_cursor()
        if tool == "Eraser":
            self.show_eraser_feedback()
        else:
            suffix = {"Draw": str(self.pen_key), "Text": str(self.font_key),
                      "Shape": SHAPES[self.shape_key]}.get(tool)
            self.show_feedback(tool + (" · " + suffix if suffix else ""))
        self.sync_tool_overlay()

    def set_number(self, number):
        self.cancel_interaction()
        if self.tool == "Draw" and number in PEN_SIZES:
            self.pen_key = number
            self.show_feedback(f"Draw · {number}")
        elif self.tool == "Text" and number in FONT_SIZES:
            self.font_key = number
            objects = tuple(replace(obj, size=FONT_SIZES[number]/obj.transform.scale)
                            if obj.id in self.selected_ids and isinstance(obj, Text) else obj
                            for obj in self.document.objects)
            self.document.commit(objects, "Font size")
            self.sync_selection()
            self.show_feedback(f"Text · {FONT_SIZES[number]} pt")
            self.update()
        elif self.tool == "Shape" and number in SHAPES:
            self.shape_key = number
            self.show_feedback(f"Shape · {SHAPES[number]}")
        elif self.tool == "Eraser" and number in (*ERASER_SIZES, 5):
            if number == 5:
                self.eraser_mode = "circular" if self.eraser_mode == "stroke" else "stroke"
                if self.eraser_mode == "circular":
                    self.eraser_key = DEFAULT_ERASER_KEY
            else:
                self.eraser_mode = "circular"
                self.eraser_key = number
            self.show_eraser_feedback()
        self.sync_tool_overlay()

    def keyPressEvent(self, event):
        # No ordinary tool QAction/QShortcut exists on any ancestor. The editor
        # owns all typing, including shortcuts accepted via ShortcutOverride.
        if self.editor is not None or not self.hasFocus() or not self.window().isActiveWindow():
            event.ignore()
            return
        key, mods = event.key(), event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if key == Qt.Key.Key_F1:
            self.toggle_help()
        elif key == Qt.Key.Key_Escape:
            if getattr(self.window(), "_gesture", None):
                self.window().cancel_window_gesture()
            elif self.gesture:
                self.cancel_interaction()
            elif self.help_panel.isVisible():
                self.help_panel.hide()
                self.sync_tool_overlay()
            else:
                self.set_selection(set())
        elif ctrl and key in (Qt.Key.Key_Z, Qt.Key.Key_Y):
            self.cancel_interaction()
            if key == Qt.Key.Key_Y or shift:
                self.document.redo()
            else:
                self.document.undo()
            self.sync_selection()
            self.update()
        elif ctrl and not mods & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier) and key in (
                Qt.Key.Key_C, Qt.Key.Key_X, Qt.Key.Key_V, Qt.Key.Key_D, Qt.Key.Key_A):
            {Qt.Key.Key_C:self.copy_selection, Qt.Key.Key_X:self.cut_selection,
             Qt.Key.Key_V:self.paste, Qt.Key.Key_D:self.duplicate_selection, Qt.Key.Key_A:self.select_all}[key]()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down) and not mods & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            step = 10 if shift else 1
            dx,dy = {Qt.Key.Key_Left:(-step,0),Qt.Key.Key_Right:(step,0),Qt.Key.Key_Up:(0,-step),Qt.Key.Key_Down:(0,step)}[key]
            self.nudge(dx,dy)
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not ctrl:
            self.delete_selection()
        elif not mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier |
                         Qt.KeyboardModifier.MetaModifier):
            letter = chr(key) if 0 <= key < 128 else ""
            if letter == "C":
                self.open_palette()
            elif letter in TOOL_KEYS:
                self.set_tool(TOOL_KEYS[letter])
            elif Qt.Key.Key_1 <= key <= Qt.Key.Key_7:
                self.set_number(key-Qt.Key.Key_0)
            else:
                event.ignore()
                return
        else:
            event.ignore()
            return
        event.accept()

    def begin_editing(self, obj):
        if obj.locked:
            return
        self.finish_editing()
        self.cancel_interaction()
        self.set_selection({obj.id})
        self.editing_object = obj
        self.cursor_position = None
        self.editor = TextEditor(obj, None)
        editor = self.editor
        self.editor.committed.connect(lambda: self.finish_editing(editor))
        self.editor.focus_finished.connect(lambda: self.finish_editing(editor, refocus=False, deselect=True))
        self.editor.help_requested.connect(self.toggle_help)
        self.editor_overlay = EditorOverlay(obj, self.editor, self)
        self.editor_overlay.show()
        self.editor_overlay.activate_editor()
        QApplication.instance().installEventFilter(self)
        self.sync_tool_overlay()
        self.update()

    def finish_editing(self, session=None, *, refocus=True, deselect=False):
        if self.editor is None or (session is not None and session is not self.editor):
            return
        editor, overlay = self.editor, self.editor_overlay
        editor.closing = True
        obj = replace(self.editing_object, text=editor.toPlainText())
        self.editor = self.editor_overlay = self.editing_object = None
        QApplication.instance().removeEventFilter(self)
        editor.commit_timer.stop()
        overlay.hide()
        overlay.deleteLater()  # The proxy owns the editor and its children.
        meaningful = bool(obj.text.strip())
        if self.document.get(obj.id) is not None:
            if meaningful:
                self.document.replace(obj, "Edit text")
            else:
                self.document.delete({obj.id}, "Delete text")
        elif meaningful:
            self.document.add(obj, "Create text")
        if deselect:
            self.set_selection(set())
        else:
            self.sync_selection()
        if refocus and self.window().isActiveWindow():
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.update_cursor()
        self.update()

    def editor_outside_press(self, session, event):
        """Own one outside canvas press; its move/release has no gesture to finish."""
        if session is not self.editor:
            return
        self.dismissed_click = (time.monotonic(), event.globalPosition())
        self.finish_editing(session, deselect=True)
        event.accept()

    def edit_text_at(self, position):
        if not self.valid_position(position):
            return
        from .settings import TEXT_MARGIN, TEXT_MIN_WIDTH, TEXT_MAX_WIDTH
        hit = self.hit_test(position)
        width = min(TEXT_MAX_WIDTH, max(TEXT_MIN_WIDTH, round(self.width()-position[0]-TEXT_MARGIN)))
        self.begin_editing(hit if isinstance(hit, Text) else Text(position,
                           size=FONT_SIZES[self.font_key], color=self.active_color, layout_width=width))

    def eventFilter(self, watched, event):
        if (self.editor is not None and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
                and not self.editor.popup_active() and isinstance(watched, QWidget)):
            view = watched if isinstance(watched, EditorOverlay) else watched.parentWidget()
            if isinstance(view, EditorOverlay) and view.canvas is self and view is not self.editor_overlay:
                return False  # A retired view cannot finish its replacement session.
            if not self.editor_overlay.owns_mouse_event(watched, event):
                if watched in (self, self.editor_overlay, self.editor_overlay.viewport()):
                    self.editor_outside_press(self.editor, event)
                    return True
                # Controls, other boards and other applications keep their own input.
                self.finish_editing(self.editor, refocus=False, deselect=True)
        return False

    def paintEvent(self, event):
        self.sync_scene()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        clip = rendering.clip_path(self.clip_spec) if self.clip_spec is not None else None

        def paint(obj, bounds, data=None):
            # Only artwork touching a document boundary needs the additional
            # rounded/control-hole clip. Interior objects use the event region.
            clipped = clip is not None and not clip.contains(bounds.adjusted(-1, -1, 1, 1))
            if clipped:
                painter.save()
                painter.setClipPath(clip)
            rendering.paint_object(painter, obj, data)
            if clipped:
                painter.restore()

        for record in self.scene.query(QRectF(event.rect()).adjusted(-2, -2, 2, 2)):
            if not event.region().intersects(record.bounds.adjusted(-2, -2, 2, 2).toAlignedRect()):
                continue
            obj = record.obj
            if not self.editing_object or obj.id != self.editing_object.id:
                cache = self.background_cache
                if cache is not None and cache.matches(obj):
                    cache.prepare(self.rect(), self.devicePixelRatioF(), self.clip_spec, record)
                    cache.paint(painter, event.region())
                else:
                    paint(obj, record.bounds, record.paint)
        if self.preview is not None:
            paint(self.preview, rendering.bounds(self.preview))

    @staticmethod
    def position(event):
        return event.position().x(), event.position().y()

    def start_gesture(self, kind):
        self.sync_scene()
        self.scene.clear_preview()
        self.gesture = kind
        self.gesture_before = self.document.objects
        self.selection_before = set(self.selected_ids)
        self.gesture_sources = self.selected_objects
        self.gesture_has_text = any(isinstance(obj, (Text, ImageObject)) for obj in self.gesture_sources)
        self.gesture_bounds = QRectF()
        for obj in self.gesture_sources:
            self.gesture_bounds = self.gesture_bounds.united(self.scene.record(obj.id).bounds)
        self.snap_targets = (SnapTargets(self.scene.records.values(), self.selected_ids, QRectF(self.rect()))
                             if kind in ("move", "resize") else None)
        self.gesture_frame = self.frame
        self.dragged = False

    def mousePressEvent(self, event):
        board = self.window()
        if hasattr(board, "route_canvas_edge") and board.route_canvas_edge(event):
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.finish_editing()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.start = self.last_sample = self.position(event)
        self.cursor_position = self.start
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self.frame and self.tool in ("Select", "Shape", "Text"):
            endpoint = rendering.endpoint_at(self.selected, self.start) if self.tool == "Shape" else None
            handle = rendering.handle_at(self.frame, self.start, self.devicePixelRatioF())
            if endpoint is not None:
                self.start_gesture("endpoint")
                self.resize_handle, self.original = endpoint, self.selected
                return
            if handle is not None:
                self.start_gesture("rotate" if handle == 8 else "resize")
                self.resize_handle = handle
                return
        if not self.valid_position(self.start):
            return
        hit = self.hit_test(self.start)
        if self.tool == "Select":
            if shift and hit:
                self.set_selection(self.selected_ids ^ {hit.id})
            elif (self.frame and self.frame.contains(self.start)) or (hit and hit.id in self.selected_ids):
                self.start_gesture("move")
                self.click_hit = hit.id if hit else None
            elif hit:
                self.set_selection({hit.id})
                self.start_gesture("move")
                self.click_hit = hit.id
            else:
                self.start_gesture("marquee")
                self.marquee_add = shift
        elif self.tool == "Text":
            self.edit_text_at(self.start)
        elif isinstance(hit, Text) and self.tool != "Eraser":
            self.set_selection({hit.id})
            self.start_gesture("text_click")
        elif self.tool == "Draw":
            self.start_gesture("draw")
            self.set_selection(set())
            self.points = [self.start]
            self.preview = Stroke(tuple(self.points), PEN_SIZES[self.pen_key], clip=self.clip_spec, color=self.active_color)
        elif self.tool == "Shape":
            self.start_gesture("shape")
            self.set_selection(set())
            self.preview = Shape(SHAPES[self.shape_key], self.start, self.start, clip=self.clip_spec, color=self.active_color)
        elif self.tool == "Eraser":
            self.start_gesture("erase")
            self.erase_segment(self.start, self.start)
        if self.preview is not None:
            self.invalidate(rendering.bounds(self.preview))
        self.sync_tool_overlay()

    def erase_segment(self, a, b):
        sweep = rendering.swept_brush(a, b, self.eraser_diameter)
        if self.clip_spec is not None:
            sweep = sweep.intersected(rendering.clip_path(self.clip_spec))
        dirty = QRegion()
        for record in self.scene.query(sweep.boundingRect(), editable=True, strokes_only=self.eraser_mode == "stroke"):
            obj = record.obj
            if obj.locked or (self.eraser_mode == "stroke" and not isinstance(obj, Stroke)) or not sweep.intersects(rendering.visible_ink(obj)):
                continue
            updated = None
            if self.eraser_mode == "circular":
                mask = Erasure(a, b, self.eraser_diameter/2, obj.transform.inverse(), self.clip_spec)
                updated = replace(obj, erasures=(*obj.erasures, mask))
                if rendering.remaining_local(updated).isEmpty():
                    updated = None
            self.scene.preview(obj.id, updated)
            dirty |= self.dirty_region(record.bounds if self.eraser_mode == "stroke"
                                       else record.bounds.intersected(sweep.boundingRect()))
        self.invalidate(dirty)

    def update_gesture(self, position, shift=False, alt=False):
        self.cursor_position = position if self.valid_position(position) else None
        dirty = QRegion()
        if self.preview is not None and self.gesture != "draw":
            dirty |= self.dirty_region(rendering.bounds(self.preview))
        self.dragged = self.dragged or math.dist(self.start, position) >= DRAG_THRESHOLD
        if self.gesture == "text_click" and self.dragged:
            self.set_selection(set())
            if self.tool == "Draw":
                self.gesture = "draw"
                self.points = [self.start]
                self.preview = Stroke(tuple(self.points), PEN_SIZES[self.pen_key], clip=self.clip_spec, color=self.active_color)
            else:
                self.gesture = "shape"
                self.preview = Shape(SHAPES[self.shape_key], self.start, position, clip=self.clip_spec, color=self.active_color)
        if self.gesture == "draw":
            if math.dist(self.points[-1], position) >= .5:
                # Midpoint interpolation only changes the previous tail and the
                # newly appended segment. The convex hull of these control points
                # bounds both curves, including their round stroke caps/joins.
                tail = (*self.points[-3:], position)
                xs, ys = zip(*tail)
                radius = self.preview.width/2
                dirty |= self.dirty_region(QRectF(min(xs)-radius,min(ys)-radius,
                                                  max(xs)-min(xs)+2*radius,max(ys)-min(ys)+2*radius))
                self.points.append(position)
                self.preview = replace(self.preview, points=tuple(self.points))
        elif self.gesture == "shape":
            self.preview = replace(self.preview, b=constrained_end(self.start, position, self.preview.kind, shift))
        elif self.gesture in ("move", "resize", "rotate") and self.dragged:
            if self.gesture == "move":
                matrix, self.guide_lines = self.snap_targets.move(self.gesture_bounds,
                    position[0]-self.start[0], position[1]-self.start[1], self.preferences, alt)
            elif self.gesture == "resize":
                matrix = resize_transform(self.gesture_frame, self.resize_handle, self.start, position, shift or self.gesture_has_text)
                matrix, self.guide_lines = self.snap_targets.resize(self.gesture_frame, self.resize_handle,
                    matrix, shift or self.gesture_has_text, self.preferences, alt)
            else:
                matrix = rotate_transform(self.gesture_frame, self.start, position, shift)
            group_bounds = QRectF()
            coalesce = len(self.gesture_sources) > DIRTY_RECT_LIMIT
            for obj in self.gesture_sources:
                changed = self.scene.preview(obj.id, transformed(obj, matrix), transform_only=True)
                if coalesce:
                    group_bounds = group_bounds.united(changed)
                else:
                    dirty |= self.dirty_region(changed)
            if coalesce:
                dirty |= self.dirty_region(group_bounds)
            self.frame = self.gesture_frame.transformed(matrix)
        elif self.gesture == "endpoint" and self.dragged:
            obj = self.original
            local = obj.transform.inverse().map(position)
            anchor = obj.b if self.resize_handle == 0 else obj.a
            end = constrained_end(anchor, local, obj.kind, shift)
            updated = replace(obj, **({"a": end} if self.resize_handle == 0 else {"b": end}))
            dirty |= self.dirty_region(self.scene.preview(obj.id, updated))
            self.frame = rendering.selection_frame([updated])
        elif self.gesture == "erase" and position != self.last_sample:
            self.erase_segment(self.last_sample, position)
        self.last_sample = position
        if self.preview is not None and self.gesture != "draw":
            dirty |= self.dirty_region(rendering.bounds(self.preview))
        self.invalidate(dirty)
        self.sync_tool_overlay()

    def mouseMoveEvent(self, event):
        board = self.window()
        if hasattr(board, "route_canvas_edge") and board.route_canvas_edge(event):
            return
        position = self.position(event)
        self.cursor_position = position if self.valid_position(position) else None
        if self.gesture:
            self.update_gesture(position, bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
                                bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
        else:
            self.update_cursor(position)
            if self.tool == "Eraser":
                self.sync_tool_overlay()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.gesture:
            return
        self.update_gesture(self.position(event), bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
                            bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
        kind = self.gesture
        if kind == "draw":
            self.document.add(self.preview, "Draw stroke")
        elif kind == "shape" and math.dist(self.preview.a, self.preview.b) > 2:
            self.document.add(self.preview, "Create shape")
            self.set_selection({self.preview.id})
        elif kind == "marquee":
            if self.dragged:
                r = QRectF(rendering.point(self.start), rendering.point(self.last_sample)).normalized()
                e = CONTAINMENT_TOLERANCE
                r = r.adjusted(-e, -e, e, e)
                ids = {record.obj.id for record in self.scene.query(r, editable=True) if r.contains(record.bounds)}
                self.set_selection(ids | self.selection_before if self.marquee_add else ids)
            else:
                self.set_selection(set())
        elif kind == "move" and not self.dragged:
            if self.click_hit is None:
                self.set_selection(set())
            elif self.click_hit not in self.selected_ids:
                self.set_selection({self.click_hit})
        elif self.scene.previews:
            label = {"move": "Move selection", "resize": "Resize selection", "rotate": "Rotate selection",
                     "endpoint": "Edit endpoint", "erase": "Erase strokes" if self.eraser_mode == "stroke" else "Erase artwork"}[kind]
            self.document.commit(self.gesture_after, label)
        self.cancel_interaction(restore=False)
        self.sync_selection(rebuild=kind not in ("move", "resize", "rotate", "endpoint"))
        self.update_cursor(self.position(event))

    def mouseDoubleClickEvent(self, event):
        if self.dismissed_click is not None:
            stamp, point = self.dismissed_click
            delta = event.globalPosition()-point
            if (time.monotonic()-stamp <= QApplication.doubleClickInterval()/1000
                    and delta.manhattanLength() <= QApplication.startDragDistance()):
                event.accept()
                return
        self.dismissed_click = None
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tool == "Eraser":
                self.mousePressEvent(event)
                return
            hit = self.hit_test(self.position(event))
            if isinstance(hit, Text):
                self.begin_editing(hit)
                return
        super().mouseDoubleClickEvent(event)

    def cancel_interaction(self, restore=True):
        self.guide_lines = ()
        dirty = QRegion()
        if self.preview is not None:
            dirty |= self.dirty_region(rendering.bounds(self.preview))
        if restore and self.gesture:
            self.selected_ids = set(self.selection_before)
            self.frame = self.gesture_frame
            dirty |= self.dirty_region(self.scene.clear_preview())
        else:
            self.sync_scene()
            self.scene.clear_preview()
        self.gesture = None
        self.gesture_before = None
        self.gesture_sources = ()
        self.preview = self.original = None
        self.points = []
        self.resize_handle = None
        self.dragged = False
        self.invalidate(dirty)
        self.sync_tool_overlay()

    def event(self, event):
        if event.type() in (QEvent.Type.WindowDeactivate, QEvent.Type.Hide):
            self.cancel_interaction()
            self.cursor_position = None
            if self.tool_overlay is not None:
                self.tool_overlay.hide()
        elif event.type() in (QEvent.Type.WindowActivate, QEvent.Type.Show):
            self.sync_tool_overlay()
        return super().event(event)

    def enterEvent(self, event):
        p = self.mapFromGlobal(QCursor.pos())
        self.cursor_position = (p.x(), p.y()) if self.tool == "Eraser" and self.valid_position((p.x(), p.y())) else None
        self.sync_tool_overlay()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.cursor_position = None
        self.sync_tool_overlay()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        self.feedback.reposition()
        if self.editor_overlay is not None:
            self.editor_overlay.setGeometry(self.rect())
        self.refresh_document_clip()
        super().resizeEvent(event)

    def stop_transient_ui(self):
        if self.ocr_panel is not None:
            self.ocr_panel.close()
        if self.palette is not None:
            self.palette.close()
        if self.context_menu is not None:
            self.context_menu.close()
        self.feedback.stop()
        self.help_panel.hide()
        self.cursor_position = None
        if self.tool_overlay is not None:
            self.tool_overlay.hide()
