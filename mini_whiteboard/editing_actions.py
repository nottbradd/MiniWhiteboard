"""Canvas editing commands shared by keyboard and small native context menus."""
from dataclasses import replace
from pathlib import Path
import time
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QRegion
from PySide6.QtWidgets import QApplication, QMenu

from .document import ImageObject, Text, new_id, transformed
from .settings import INK, CLIPBOARD_MIME, PASTE_OFFSET, IMAGE_FIT_FRACTION
from .transforms import Affine, translation
from . import clipboard, images, rendering


class EditingActions:
    def init_actions(self):
        self.board_id = uuid4().hex
        self.active_color = INK
        self.recent_colors = []
        self.palette = None
        self.context_menu = None
        self._paste_token = None
        self._paste_count = 0
        self._last_nudge = None
        self.setAcceptDrops(True)

    def commit_edit(self, objects, label, selection=None, frame=None, merge=False):
        self.sync_scene()
        before = self.scene.records.copy()
        if not self.document.commit(objects, label, merge=merge):
            return False
        self.sync_scene()
        dirty = QRegion()
        for identifier in before.keys() | self.scene.records.keys():
            old, new = before.get(identifier), self.scene.records.get(identifier)
            if old is not None and new is not None and old.obj is new.obj:
                continue
            if old is not None:
                dirty |= self.dirty_region(old.bounds)
            if new is not None:
                dirty |= self.dirty_region(new.bounds)
        # Reordering also changes overlapping pixels without replacing objects.
        if label in ("Bring to front", "Send to back"):
            for obj in self.selected_objects:
                dirty |= self.dirty_region(self.scene.record(obj.id).bounds)
        if selection is not None:
            self.set_selection(selection)
        else:
            self.sync_selection(rebuild=frame is None)
        if frame is not None:
            self.frame = frame
            self.sync_tool_overlay()
        self.invalidate(dirty)
        return True

    def editable_selection(self):
        return tuple(o for o in self.selected_objects if not o.locked)

    def select_all(self):
        self.cancel_interaction()
        self.tool = "Select"
        self.set_selection(o.id for o in self.document.objects if not o.locked and not rendering.bounds(o).isEmpty())
        self.update_cursor()

    def copy_selection(self):
        self.cancel_interaction()
        objects = self.editable_selection()
        if not objects:
            return False
        try:
            QApplication.clipboard().setMimeData(clipboard.mime_data(objects, self.board_id))
            self.show_feedback("Copied selection")
            return True
        except ValueError as error:
            self.show_feedback(str(error))
            return False

    def delete_selection(self, label="Delete selection"):
        self.cancel_interaction()
        ids = {o.id for o in self.editable_selection()}
        self.commit_edit(tuple(o for o in self.document.objects if o.id not in ids), label, set())

    def cut_selection(self):
        if self.copy_selection():
            self.delete_selection("Cut selection")

    def insert_copies(self, objects, dx, dy, label):
        copies = tuple(replace(transformed(o, translation(dx, dy)), id=new_id(), locked=False) for o in objects)
        self.tool = "Select"
        self.commit_edit((*self.document.objects, *copies), label, {o.id for o in copies})
        self.update_cursor()
        return copies

    def duplicate_selection(self):
        self.cancel_interaction()
        objects = self.editable_selection()
        if objects:
            self.insert_copies(objects, PASTE_OFFSET, PASTE_OFFSET, "Duplicate selection")

    def paste(self):
        self.cancel_interaction()
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return
        try:
            if mime.hasFormat(CLIPBOARD_MIME):
                objects, source, token = clipboard.decode(mime.data(CLIPBOARD_MIME))
                if token != self._paste_token:
                    self._paste_count = 0 if source == self.board_id else -1
                    self._paste_token = token
                self._paste_count += 1
                delta = PASTE_OFFSET*self._paste_count
                self.insert_copies(objects, delta, delta, "Paste objects")
                return
            image = QApplication.clipboard().image()
            if image.isNull():
                for format_name in ("image/png", "image/jpeg", "image/webp"):
                    if mime.hasFormat(format_name):
                        image = images.read_bytes(mime.data(format_name))
                        if not image.isNull():
                            break
            if not image.isNull():
                self.insert_image(images.from_image(image))
            elif mime.hasUrls():
                self.insert_files([url.toLocalFile() for url in mime.urls() if url.isLocalFile()])
            else:
                self.show_feedback("Copy an image or a Mini Whiteboard selection first")
        except (ValueError, OSError) as error:
            self.show_feedback(str(error))

    def image_at(self, obj, position=None, fit=IMAGE_FIT_FRACTION):
        width, height = obj.pixel_size
        scale = min(1, self.width()*fit/width, self.height()*fit/height)
        if position is None:
            p = self.mapFromGlobal(QCursor.pos())
            position = (p.x(), p.y()) if self.valid_position((p.x(), p.y())) else (self.width()/2, self.height()/2)
        w, h = width*scale, height*scale
        x = max(0, min(self.width()-w, position[0]-w/2))
        y = max(0, min(self.height()-h, position[1]-h/2))
        return replace(obj, transform=translation(x, y) @ Affine(a=scale, d=scale))

    def insert_image(self, obj, position=None):
        obj = self.image_at(obj, position)
        self.tool = "Select"
        self.commit_edit((*self.document.objects, obj), "Paste image", {obj.id})
        self.update_cursor()
        return obj

    def insert_files(self, filenames, position=None):
        objects = tuple(self.image_at(images.from_file(name), position) for name in filenames)
        if objects:
            self.tool = "Select"
            self.commit_edit((*self.document.objects, *objects), "Drop images", {o.id for o in objects})
            self.update_cursor()

    def nudge(self, dx, dy):
        self.cancel_interaction()
        ids = frozenset(o.id for o in self.editable_selection())
        if not ids:
            return
        now = time.monotonic()
        merge = self._last_nudge is not None and self._last_nudge[1:] == (ids, self.document.index) and now-self._last_nudge[0] < .4
        matrix = translation(dx, dy)
        frame = self.frame.transformed(matrix) if self.frame is not None else None
        self.commit_edit(tuple(transformed(o, matrix) if o.id in ids else o for o in self.document.objects),
                         "Nudge selection", frame=frame, merge=merge)
        self._last_nudge = now, ids, self.document.index

    def open_palette(self):
        self.cancel_interaction()
        if self.palette is not None:
            self.palette.close()
        from .palette import ColorPalette
        self.palette = ColorPalette(self, self.selected_ids)
        p = QCursor.pos()
        if not self.valid_position((self.mapFromGlobal(p).x(), self.mapFromGlobal(p).y())):
            p = self.mapToGlobal(self.rect().center())
        screen = self.window().screen().availableGeometry()
        self.palette.move(max(screen.left(), min(p.x()+8, screen.right()-self.palette.width())),
                          max(screen.top(), min(p.y()+8, screen.bottom()-self.palette.height())))
        self.palette.show()
        self.palette.setFocus(Qt.FocusReason.PopupFocusReason)
        self.sync_tool_overlay()

    def apply_color(self, color, identifiers=None):
        chosen = QColor(color)
        if not chosen.isValid():
            return
        color = chosen.name()
        self.active_color = color
        self.recent_colors = [color, *(c for c in self.recent_colors if c != color)][:7]
        ids = self.selected_ids if identifiers is None else identifiers
        self.commit_edit(tuple(replace(o, color=color) if o.id in ids and not o.locked and not isinstance(o, ImageObject)
                               else o for o in self.document.objects), "Change colour")
        self.show_feedback("Colour · " + color)

    def reorder(self, front):
        self.cancel_interaction()
        ids = {o.id for o in self.editable_selection()}
        selected = tuple(o for o in self.document.objects if o.id in ids)
        rest = tuple(o for o in self.document.objects if o.id not in ids)
        self.commit_edit((*rest, *selected) if front else (*selected, *rest), "Bring to front" if front else "Send to back")

    def set_locked(self, identifiers, locked):
        self.cancel_interaction()
        ids = set(identifiers)
        self.commit_edit(tuple(replace(o, locked=locked) if o.id in ids else o for o in self.document.objects),
                         "Lock objects" if locked else "Unlock objects", set() if locked else ids)

    def make_context_menu(self, position):
        self.cancel_interaction()
        hit = self.hit_test(position, include_locked=True)
        if hit and not hit.locked and hit.id not in self.selected_ids:
            self.set_selection({hit.id})
        from .surfaces import SurfaceMenu
        menu = SurfaceMenu(self.window().platform, self.preferences, self)
        menu.add_heading('Selection' if self.selected_ids else 'Whiteboard')
        has_selection = bool(self.editable_selection())
        commands = (("Cut", self.cut_selection), ("Copy", self.copy_selection), ("Paste", self.paste),
                    ("Duplicate", self.duplicate_selection), ("Delete", self.delete_selection))
        for label, callback in commands:
            action = menu.addAction(label, lambda checked=False, fn=callback: fn())
            action.setEnabled(label == "Paste" or has_selection)
        menu.addSeparator()
        menu.addAction("Bring to front", lambda: self.reorder(True)).setEnabled(has_selection)
        menu.addAction("Send to back", lambda: self.reorder(False)).setEnabled(has_selection)
        menu.addAction("Lock selection", lambda: self.set_locked(self.selected_ids, True)).setEnabled(has_selection)
        if hit and hit.locked:
            menu.addAction("Unlock this object", lambda: self.set_locked({hit.id}, False))
        locked = tuple(o for o in self.document.objects if o.locked)
        if locked:
            submenu = menu.addMenu("Locked objects")
            for index, obj in enumerate(locked, 1):
                name = "Image" if isinstance(obj, ImageObject) else type(obj).__name__
                submenu.addAction(f"Unlock {name} {index}", lambda checked=False, identifier=obj.id: self.set_locked({identifier}, False))
        return menu

    def contextMenuEvent(self, event):
        if self.editor is not None:
            return super().contextMenuEvent(event)
        if self.context_menu is not None:
            self.context_menu.close()
            self.context_menu.deleteLater()
        self.context_menu = self.make_context_menu((event.pos().x(), event.pos().y()))
        self.context_menu.aboutToHide.connect(lambda: QTimer.singleShot(0, self.sync_tool_overlay))
        self.context_menu.popup(event.globalPos())
        self.sync_tool_overlay()

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if self.editor is None and urls and all(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in
                                               ('.png','.jpg','.jpeg','.webp') for u in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self.editor is not None:
            return
        try:
            self.insert_files([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()],
                              (event.position().x(), event.position().y()))
            event.acceptProposedAction()
        except (ValueError, OSError) as error:
            self.show_feedback(str(error))

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)
