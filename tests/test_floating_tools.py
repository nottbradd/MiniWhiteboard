import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, QSettings, Qt
from PySide6.QtTest import QTest
from tests.qt_case import APP, QtCase, wait_until
from mini_whiteboard.board import BoardWindow
from mini_whiteboard.document import Text, Stroke
from mini_whiteboard.floating_tools import FloatingTools, place_tools
from mini_whiteboard.snapping import SnapPreferences
from mini_whiteboard.tool_buttons import TARGET


class FloatingToolsTests(QtCase):
    def setUp(self):
        super().setUp()
        self.preferences = SnapPreferences()
        self.manager = FloatingTools(APP,self.preferences)
        self.board = self.make_board()

    def make_board(self):
        board = BoardWindow('Tools fixture',self.preferences)
        self.widgets.append(board)
        board.setGeometry(100,180,650,420)
        board.show()
        board.activateWindow()
        board.canvas.setFocus()
        self.manager.add_board(board)
        APP.processEvents()
        return board

    def tearDown(self):
        self.manager.close()
        super().tearDown()

    def enable(self):
        self.preferences.set_floating_tools(True)
        self.board.activateWindow()
        self.board.canvas.setFocus()
        self.manager.activate(self.board)
        self.assertTrue(wait_until(lambda:self.manager.palette is not None and self.manager.palette.isVisible(),200))
        # The offscreen plugin activates even WindowDoesNotAcceptFocus windows;
        # native nonactivation is checked by the isolated Windows GUI script.
        self.board.activateWindow()
        self.board.canvas.setFocus()
        APP.processEvents()
        return self.manager.palette

    def test_default_off_and_saved_preference(self):
        self.assertIsNone(self.manager.palette)
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory)/'settings.ini'),QSettings.Format.IniFormat)
            prefs = SnapPreferences(settings=settings)
            self.assertFalse(prefs.floating_tools)
            prefs.set_floating_tools(True)
            self.assertTrue(SnapPreferences(settings=settings).floating_tools)
            prefs.set_floating_tools(False)
            self.assertFalse(SnapPreferences(settings=settings).floating_tools)

    def test_compact_targets_accessible_names_and_keyboard_sync(self):
        palette = self.enable()
        self.assertEqual(palette.height(),46)
        for name,b in palette.buttons.items():
            self.assertEqual(b.size(),QSize(TARGET,TARGET))
            self.assertEqual(b.accessibleName(),name)
            self.assertTrue(b.toolTip())
        QTest.keyClick(self.board.canvas,Qt.Key.Key_E)
        self.assertTrue(palette.buttons['Eraser'].isChecked())
        QTest.mouseClick(palette.buttons['Shape'],Qt.MouseButton.LeftButton)
        self.assertEqual(self.board.canvas.tool,'Shape')
        QTest.keyClick(self.board.canvas,Qt.Key.Key_3)
        self.assertEqual(self.board.canvas.shape_key,3)
        width = palette.width()
        self.board.resize(900,600)
        APP.processEvents()
        self.assertEqual(palette.width(),width)

    def test_active_board_switch_retains_configuration_and_one_palette(self):
        first = self.enable()
        self.manager.choose('Eraser')
        self.board.canvas.set_number(4)
        second = self.make_board()
        self.assertTrue(wait_until(lambda:self.manager.board is second,200))
        from shiboken6 import isValid
        self.assertTrue(not isValid(first) or not first.isVisible())
        self.assertEqual(second.canvas.tool,'Draw')
        self.board.activateWindow()
        self.board.canvas.setFocus()
        self.assertTrue(wait_until(lambda:self.manager.board is self.board and self.manager.palette is not None,200))
        self.assertEqual(self.board.canvas.eraser_diameter,64)
        self.assertTrue(self.manager.palette.buttons['Eraser'].isChecked())

    def test_tap_long_press_release_and_movement_cancel(self):
        palette = self.enable()
        button = palette.buttons['Draw']
        QTest.mousePress(button,Qt.MouseButton.LeftButton)
        button.timer.start(10)  # Exercise the real queued timer without a slow test.
        self.assertTrue(wait_until(lambda:self.manager.options is not None,200))
        popup = self.manager.options
        QTest.mouseRelease(button,Qt.MouseButton.LeftButton)
        APP.processEvents()
        self.assertIs(self.manager.options,popup)
        self.assertEqual(self.board.canvas.document.index,0)
        self.manager.close_options()
        QTest.mousePress(button,Qt.MouseButton.LeftButton)
        QTest.mouseMove(button,QPoint(button.width()+20,button.height()+20))
        self.assertFalse(button.timer.isActive())
        QTest.mouseRelease(button,Qt.MouseButton.LeftButton,pos=QPoint(20,20))
        self.assertIsNone(self.manager.options)
        QTest.mouseClick(button,Qt.MouseButton.RightButton)
        self.assertIsNotNone(self.manager.options)

    def test_drag_offset_follows_board_and_clamps(self):
        palette = self.enable()
        board_start = self.board.pos()
        tool_start = palette.pos()
        grip = palette.grip
        QTest.mousePress(grip,Qt.MouseButton.LeftButton,pos=QPoint(10,20))
        start = QPointF(grip.mapToGlobal(QPoint(10,20)))
        self.manager.drag(start+QPointF(35,70))
        QTest.mouseRelease(grip,Qt.MouseButton.LeftButton,pos=QPoint(10,20))
        APP.processEvents()
        self.assertEqual(self.board.pos(),board_start)
        self.assertEqual(palette.pos(),tool_start+QPoint(35,70))
        self.assertEqual(self.board.canvas.document.index,0)
        self.board.move(board_start+QPoint(12,16))
        APP.processEvents()
        self.assertEqual(palette.pos(),tool_start+QPoint(47,86))

    def test_placement_all_routes_negative_origins_and_scaling_units(self):
        for scale in (1,1.25,1.5,1.75,2):
            # Qt exposes logical work areas; never multiply their global origin.
            work = QRect(-1600,-900,round(1600/scale),round(900/scale))
            size = QSize(375,46)
            board = QRect(work.left()+50,work.top()+110,500,200)
            r,kind = place_tools(board,size,work)
            self.assertEqual(kind,'above')
            self.assertTrue(work.contains(r))
            board.moveTop(work.top())
            r,kind = place_tools(board,size,work)
            self.assertEqual(kind,'below')
            self.assertTrue(work.contains(r))
            r,kind = place_tools(work,size,work)
            self.assertEqual(kind,'inside')
            self.assertTrue(work.contains(r))
            r,kind = place_tools(board,size,work,QPoint(-10000,10000))
            self.assertEqual(kind,'manual')
            self.assertTrue(work.contains(r))

    def test_narrow_screen_wrap_keeps_all_targets(self):
        palette = self.enable()
        palette.fit(QRect(0,0,240,480))
        self.assertLessEqual(palette.width(),224)
        for button in palette.buttons.values():
            self.assertEqual(button.size(),QSize(42,42))
            self.assertTrue(palette.rect().contains(button.geometry()))

    def test_text_completion_does_not_consume_next_drawing_gesture(self):
        palette = self.enable()
        canvas = self.board.canvas
        for text in ('','A V E 12345'):
            canvas.begin_editing(Text((60,60)))
            QTest.keyClicks(canvas.editor,text)
            self.manager.choose('Draw')
            self.assertIsNone(canvas.editor)
            before = len(canvas.document.objects)
            QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=QPoint(80,160))
            QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=QPoint(150,180))
            self.assertEqual(len(canvas.document.objects),before+1)
            self.assertIsInstance(canvas.document.objects[-1],Stroke)
        self.assertEqual([o.text for o in canvas.document.objects if isinstance(o,Text)],['A V E 12345'])

    def test_hide_close_capture_and_repeat_enable_cleanup(self):
        palette = self.enable()
        self.manager.open_options('Eraser')
        self.manager.set_capture_suspended(True)
        self.assertFalse(palette.isVisible())
        self.assertIsNone(self.manager.options)
        self.manager.set_capture_suspended(False)
        self.board.activateWindow()
        self.board.canvas.setFocus()
        APP.processEvents()
        self.manager.refresh()
        self.assertTrue(palette.isVisible())
        self.board.minimize_to_tray()
        self.assertFalse(palette.isVisible())
        self.board.restore()
        APP.processEvents()
        for _ in range(5):
            self.preferences.set_floating_tools(False)
            self.assertIsNone(self.manager.palette)
            self.enable()
        self.board.close()
        self.assertIsNone(self.manager.board)
        self.assertIsNone(self.manager.palette)

    def test_other_app_focus_hides_and_undo_uses_document(self):
        palette = self.enable()
        canvas = self.board.canvas
        canvas.document.add(Stroke(((60,60),(120,100))))
        canvas.sync_selection()
        self.manager.choose('Undo')
        self.assertEqual(canvas.document.index,0)
        self.assertTrue(palette.buttons['Redo'].isEnabled())
        self.manager.choose('Redo')
        self.assertEqual(canvas.document.index,1)
        with patch.object(APP,'activeWindow',return_value=None):
            self.manager.refresh()
        self.assertFalse(palette.isVisible())

    def test_synthetic_tablet_tap_hold_and_mouse_deduplication(self):
        from PySide6.QtGui import QPointingDevice,QInputDevice,QTabletEvent,QMouseEvent
        palette = self.enable()
        button = palette.buttons['Eraser']
        calls=[]
        button.clicked.connect(lambda:calls.append('tap'))
        device = QPointingDevice('test pen',77,QInputDevice.DeviceType.Stylus,
            QPointingDevice.PointerType.Pen,QInputDevice.Capability.Position,1,2)
        pos = QPointF(20,20)
        global_pos = QPointF(button.mapToGlobal(pos.toPoint()))
        def tablet(kind,button_value=Qt.MouseButton.LeftButton):
            ev=QTabletEvent(kind,device,pos,global_pos,.5,0,0,0,0,0,
                           Qt.KeyboardModifier.NoModifier,button_value,
                           Qt.MouseButton.NoButton if kind==QEvent.Type.TabletRelease else button_value)
            APP.sendEvent(button,ev)
            self.assertTrue(ev.isAccepted())
        tablet(QEvent.Type.TabletPress)
        tablet(QEvent.Type.TabletRelease)
        self.assertEqual(calls,['tap'])
        for kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease):
            ev=QMouseEvent(kind,pos,pos,global_pos,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,
                          Qt.KeyboardModifier.NoModifier,Qt.MouseEventSource.MouseEventSynthesizedByQt)
            APP.sendEvent(button,ev)
        self.assertEqual(calls,['tap'])
        tablet(QEvent.Type.TabletPress)
        button.timer.start(10)
        self.assertTrue(wait_until(lambda:self.manager.options is not None,200))
        tablet(QEvent.Type.TabletRelease)
        self.assertEqual(calls,['tap'])
        self.assertIsNotNone(self.manager.options)
        self.manager.close_options()
        tablet(QEvent.Type.TabletPress,Qt.MouseButton.RightButton)
        self.assertIsNotNone(self.manager.options)
        tablet(QEvent.Type.TabletRelease,Qt.MouseButton.RightButton)
        self.assertEqual(calls,['tap'])

    def test_synthetic_touch_tap_and_cancel(self):
        from PySide6.QtGui import QPointingDevice,QInputDevice,QTouchEvent,QEventPoint
        palette=self.enable()
        button=palette.buttons['Shape']
        calls=[]
        button.clicked.connect(lambda:calls.append('tap'))
        device=QPointingDevice('test touch',78,QInputDevice.DeviceType.TouchScreen,
            QPointingDevice.PointerType.Finger,QInputDevice.Capability.Position,1,0)
        local=QPointF(20,20)
        global_pos=QPointF(button.mapToGlobal(local.toPoint()))
        def touch(kind,state):
            event=QTouchEvent(kind,device,Qt.KeyboardModifier.NoModifier,
                             [QEventPoint(0,state,local,global_pos)])
            button.event(event)
            self.assertTrue(event.isAccepted())
        touch(QEvent.Type.TouchBegin,QEventPoint.State.Pressed)
        touch(QEvent.Type.TouchEnd,QEventPoint.State.Released)
        self.assertEqual(calls,['tap'])
        touch(QEvent.Type.TouchBegin,QEventPoint.State.Pressed)
        touch(QEvent.Type.TouchCancel,QEventPoint.State.Released)
        self.assertIsNone(button.pointer)
        self.assertFalse(button.timer.isActive())
        self.assertEqual(calls,['tap'])
