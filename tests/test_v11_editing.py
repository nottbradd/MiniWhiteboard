from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt, QMimeData
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tests.test_canvas import CanvasCase
from tests.qt_case import APP
from mini_whiteboard import clipboard, images, rendering
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import ImageObject, Shape, Stroke, Text
from mini_whiteboard.settings import CLIPBOARD_MIME, PASTE_OFFSET, PALETTE_COLORS
from mini_whiteboard.transforms import Affine, Erasure, rotation, translation


def sample_image(width=100, height=60):
    image = QImage(width,height,QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    return image


class ReleaseEditingTests(CanvasCase):
    def fixture(self):
        a = Stroke(((50,100),(220,100)), 5, color='#e04444',
                   erasures=(Erasure((100,80),(100,120),8),))
        b = Text((80,140),'editable',20,color='#2878d0',transform=translation(20,10) @ rotation(15))
        c = images.from_image(sample_image(), (280,160))
        self.canvas.document.commit((a,b,c),'Fixture')
        self.canvas.select_all()
        return a,b,c

    def test_copy_mime_has_editable_data_and_image_without_history(self):
        objects = self.fixture()
        self.key(Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
        mime = QApplication.clipboard().mimeData()
        self.assertTrue(mime.hasFormat(CLIPBOARD_MIME))
        self.assertTrue(mime.hasImage())
        decoded, source, token = clipboard.decode(mime.data(CLIPBOARD_MIME))
        self.assertEqual(decoded,objects)
        self.assertEqual(source,self.canvas.board_id)
        self.assertTrue(token)
        self.assertEqual(self.canvas.document.index,1)
        self.assertFalse(QApplication.clipboard().image().isNull())

    def test_same_board_repeated_paste_new_ids_order_masks_and_offsets(self):
        objects = self.fixture()
        self.canvas.copy_selection()
        for count in (1,2):
            self.key(Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier)
            copies = self.canvas.document.objects[-3:]
            for original, copied in zip(objects,copies):
                self.assertNotEqual(original.id,copied.id)
                self.assertEqual(copied.transform,translation(count*PASTE_OFFSET,count*PASTE_OFFSET) @ original.transform)
                self.assertEqual(copied.erasures,original.erasures)
                if isinstance(original,ImageObject):
                    self.assertEqual(copied.png,original.png)
                else:
                    self.assertEqual(copied.color,original.color)
        self.assertEqual(len(set(o.id for o in self.canvas.document.objects)),9)
        self.assertEqual(self.canvas.document.index,3)
        self.key(Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.canvas.document.objects),6)
        self.key(Qt.Key.Key_Y,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.canvas.document.objects),9)

    def test_cross_board_paste_uses_windows_clipboard(self):
        objects = self.fixture()
        self.canvas.copy_selection()
        other = BoardWindow('Other')
        self.widgets.append(other)
        other.canvas.paste()
        self.assertEqual(len(other.canvas.document.objects),3)
        for old,new in zip(objects,other.canvas.document.objects):
            self.assertEqual(new.transform,old.transform)
            self.assertNotEqual(new.id,old.id)
        self.assertEqual(self.canvas.document.objects,objects)

    def test_cut_duplicate_delete_and_exact_undo(self):
        objects = self.fixture()
        self.canvas.cut_selection()
        self.assertFalse(self.canvas.document.objects)
        self.assertTrue(QApplication.clipboard().mimeData().hasImage())
        self.canvas.document.undo()
        self.canvas.set_selection(o.id for o in objects)
        self.canvas.duplicate_selection()
        self.assertEqual(len(self.canvas.document.objects),6)
        self.assertIs(self.canvas.document.objects[-1].png, objects[-1].png)
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects,objects)

    def test_nudges_group_history_and_preserve_relative_positions(self):
        objects = self.fixture()
        frame = self.canvas.frame
        self.key(Qt.Key.Key_Right)
        self.key(Qt.Key.Key_Right)
        self.key(Qt.Key.Key_Down,Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.canvas.document.index,2)
        for old,new in zip(objects,self.canvas.document.objects):
            self.assertEqual(new.transform,translation(2,10) @ old.transform)
        self.assertEqual(self.canvas.frame.center,(frame.center[0]+2,frame.center[1]+10))
        self.key(Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.canvas.document.objects,objects)

    def test_paste_large_image_fits_and_small_image_is_not_upscaled(self):
        for width,height in ((4000,2400),(50,30)):
            QApplication.clipboard().setImage(sample_image(width,height))
            self.canvas.paste()
            obj = self.canvas.document.objects[-1]
            self.assertIsInstance(obj,ImageObject)
            rect = rendering.bounds(obj)
            self.assertLessEqual(rect.width(),self.canvas.width()*.9+1)
            self.assertLessEqual(rect.height(),self.canvas.height()*.9+1)
            self.assertAlmostEqual(rect.width()/rect.height(),width/height)
            if width == 50:
                self.assertEqual(obj.transform.scale,1)

    def test_image_transform_is_proportional_and_keeps_png(self):
        obj = self.canvas.insert_image(images.from_image(sample_image(120,80)), (160,150))
        frame = self.canvas.frame
        tip = frame.handle(3)
        self.drag((round(tip[0]),round(tip[1])),(round(tip[0]+40),round(tip[1])))
        new = self.canvas.document.objects[0]
        self.assertIs(new.png,obj.png)
        self.assertAlmostEqual(new.transform.a,new.transform.d)
        self.assertGreater(new.transform.scale,obj.transform.scale)
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects,(obj,))

    def test_image_decoding_reused_during_transform(self):
        obj = self.canvas.insert_image(images.from_image(sample_image(600,400)), (250,200))
        data = self.canvas.scene.record(obj.id).paint
        self.canvas.start = self.canvas.last_sample = self.canvas.frame.center
        self.canvas.start_gesture('move')
        with patch.object(images,'decoded',side_effect=AssertionError('repeated decoding')):
            for i in range(5):
                self.canvas.update_gesture((self.canvas.start[0]+20+i,self.canvas.start[1]+10))
                self.assertIs(self.canvas.scene.record(obj.id).paint,data)
        self.canvas.cancel_interaction()

    def test_image_mask_pixels_rotate_copy_and_undo_remain_exact(self):
        obj = images.from_image(sample_image(120,80), (0,0),
                                transform=translation(180,100) @ rotation(90),
                                erasures=(Erasure((60,0),(60,80),8),))
        target = QImage(300,300,QImage.Format.Format_ARGB32_Premultiplied)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        rendering.paint_object(painter,obj)
        painter.end()
        self.assertEqual(target.pixelColor(140,160).alpha(),0)
        self.assertEqual(target.pixelColor(140,130).blue(),255)
        self.assertEqual(target.pixelColor(140,130).alpha(),255)
        self.canvas.document.add(obj)
        self.canvas.set_selection({obj.id})
        self.canvas.copy_selection()
        self.canvas.paste()
        copied = self.canvas.document.objects[-1]
        self.assertEqual(copied.erasures,obj.erasures)
        self.assertEqual(copied.png,obj.png)
        after = self.canvas.document.objects
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects,(obj,))
        self.canvas.document.redo()
        self.assertEqual(self.canvas.document.objects,after)

    def test_future_text_colour_and_per_board_memory(self):
        self.canvas.apply_color('#e04444')
        self.canvas.set_tool('Text')
        QTest.mouseClick(self.canvas,Qt.MouseButton.LeftButton,pos=QPoint(80,80))
        QTest.keyClicks(self.canvas.editor,'Red text')
        self.canvas.finish_editing()
        self.assertEqual(self.canvas.document.objects[-1].color,'#e04444')
        other = BoardWindow('Independent colours')
        self.widgets.append(other)
        self.assertNotEqual(other.canvas.active_color,self.canvas.active_color)

    def test_colours_apply_to_selection_and_future_objects_but_not_images(self):
        objects = self.fixture()
        self.canvas.apply_color('#9052c8')
        self.assertEqual(self.canvas.document.index,2)
        self.assertEqual(self.canvas.document.objects[-1],objects[-1])
        self.assertTrue(all(o.color=='#9052c8' for o in self.canvas.document.objects[:2]))
        self.canvas.set_selection(set())
        self.canvas.set_tool('Draw')
        self.drag((20,20),(40,40))
        self.assertEqual(self.canvas.document.objects[-1].color,'#9052c8')
        self.canvas.set_tool('Shape')
        self.drag((300,300),(380,350))
        self.assertEqual(self.canvas.document.objects[-1].color,'#9052c8')

    def test_color_popup_number_and_escape(self):
        self.canvas.open_palette()
        palette = self.canvas.palette
        self.assertLess(palette.width(),350)
        QTest.keyClick(palette,Qt.Key.Key_2)
        APP.processEvents()
        self.assertEqual(self.canvas.active_color,PALETTE_COLORS[1][1])
        self.assertIsNone(self.canvas.palette)
        self.canvas.open_palette()
        QTest.keyClick(self.canvas.palette,Qt.Key.Key_Escape)
        self.assertEqual(self.canvas.active_color,PALETTE_COLORS[1][1])

    def test_text_owns_all_new_shortcuts_and_arrows(self):
        self.fixture()
        obj = Text((40,40),'')
        self.canvas.begin_editing(obj)
        editor = self.canvas.editor
        QTest.keyClicks(editor,'C c 1234554321')
        QTest.keyClick(editor,Qt.Key.Key_Left)
        QTest.keyClick(editor,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(editor,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(QApplication.clipboard().text(),'C c 1234554321')
        self.assertEqual(self.canvas.document.index,1)
        self.assertIsNone(self.canvas.palette)
        QTest.keyClick(editor,Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(editor.toPlainText(),'C c 1234554321')

    def test_lock_prevents_selection_transform_and_erasure_and_context_unlocks(self):
        obj = Stroke(((60,100),(240,100)),10)
        self.canvas.document.add(obj)
        self.canvas.set_selection({obj.id})
        self.canvas.set_locked({obj.id},True)
        locked = self.canvas.document.objects[0]
        self.assertFalse(self.canvas.selected_ids)
        self.assertIsNone(self.canvas.hit_test((100,100)))
        self.canvas.select_all()
        self.assertFalse(self.canvas.selected_ids)
        self.canvas.set_tool('Eraser')
        self.drag((100,80),(100,120))
        self.assertEqual(self.canvas.document.objects,(locked,))
        self.canvas.set_number(5)
        self.drag((80,80),(80,120))
        self.assertEqual(self.canvas.document.objects,(locked,))
        menu = self.canvas.make_context_menu((100,100))
        self.widgets.append(menu)
        unlock = next(a for a in menu.actions() if a.text()=='Unlock this object')
        unlock.trigger()
        self.assertFalse(self.canvas.document.objects[0].locked)
        self.assertEqual(self.canvas.selected_ids,{obj.id})
        self.canvas.document.undo()
        self.assertTrue(self.canvas.document.objects[0].locked)

    def test_layer_order_preserves_group_order_and_undo(self):
        objects = self.fixture()
        self.canvas.set_selection({objects[0].id,objects[1].id})
        self.canvas.reorder(True)
        self.assertEqual(self.canvas.document.objects,(objects[2],objects[0],objects[1]))
        self.canvas.reorder(False)
        self.assertEqual(self.canvas.document.objects,objects)
        self.canvas.document.undo()
        self.assertEqual(self.canvas.document.objects,(objects[2],objects[0],objects[1]))

    def test_invalid_editable_clipboard_is_rejected_without_document_change(self):
        objects = self.fixture()
        data = json.loads(clipboard.encode(objects,self.canvas.board_id))
        data['objects'][0]['transform']['a'] = float('nan')
        with self.assertRaises(ValueError):
            clipboard.decode(json.dumps(data).encode())
        mime = QMimeData()
        mime.setData(CLIPBOARD_MIME,b'{invalid')
        QApplication.clipboard().setMimeData(mime)
        self.canvas.paste()
        self.assertEqual(self.canvas.document.objects,objects)

    def test_png_jpeg_webp_file_import(self):
        folder = Path('.test-artifacts')
        folder.mkdir(exist_ok=True)
        from PySide6.QtGui import QImageWriter
        supported = {bytes(f).decode() for f in QImageWriter.supportedImageFormats()}
        for ext in ('png','jpg','jpeg','webp'):
            if ext not in supported:
                continue
            path = folder/f'v11-import.{ext}'
            self.assertTrue(sample_image().save(str(path)))
            self.canvas.insert_files([str(path)],(150,150))
            self.assertEqual(self.canvas.document.objects[-1].pixel_size,(100,60))
