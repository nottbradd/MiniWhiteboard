"""Tray lifetime is independent of the number of whiteboards."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .platform import get_platform
from .shortcuts import ShortcutPolicy
from .system_menu import rebuild_menu
from .board import BoardWindow
from .placement import PlacementController
from .screenshot import ScreenshotController
from .snapping import SnapPreferences
from .settings import APP_NAME, MIN_WIDTH, MIN_HEIGHT
from . import APP_VERSION
from .branding import app_icon


class WhiteboardApplication:
    def __init__(self, app, preferences=None, platform=None):
        self.app = app
        self.platform = platform or get_platform()
        self.boards = []
        self.minimized_order = []
        self.hidden_batch = []
        self.next_number = 1
        self.exiting = False
        self.preferences = preferences if preferences is not None else SnapPreferences(persist=self.platform.runtime.persist_preferences)
        self.platform.shortcuts = ShortcutPolicy(self.platform.shortcuts.mac, self.preferences.shortcut_preset,
                                                 self.preferences.windows_hide)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        app.setWindowIcon(app_icon())
        from .surfaces import SurfaceMenu
        self.menu = SurfaceMenu(self.platform, self.preferences)
        self.tray = QSystemTrayIcon(self.platform.runtime.tray_icon(), app)
        self.platform.runtime.configure_tray(app, self.tray)
        self.update_shortcut_labels()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        self.menu.aboutToShow.connect(self.rebuild_menu)
        self.hotkeys = self.platform.create_hotkeys(app, self.preferences.shortcut_preset)
        if not self.platform.shortcuts.mac and hasattr(self.hotkeys, 'set_hide_shortcut'):
            self.hotkeys.set_hide_shortcut(self.preferences.windows_hide)
        self.hotkeys.events.hide_toggle.connect(self.toggle_visibility)
        if hasattr(self.hotkeys.events, "warning"):
            self.hotkeys.events.warning.connect(self.notify)
        self.placement = PlacementController(self.hotkeys, platform=self.platform)
        self.placement.confirmed.connect(self.create_board)
        self.placement.message.connect(self.notify)
        self.capture = ScreenshotController(self.hotkeys, self.placement)
        self.capture.captured.connect(self.create_screenshot_board)
        self.capture.message.connect(self.notify)
        self.capture.permission_required.connect(self.capture_permission_error)
        self.rebuild_menu()
        self.tray.show()
        try:
            self.hotkeys.start()
        except OSError as error:
            QTimer.singleShot(0, lambda detail=str(error): self.hotkey_error(detail))
        app.aboutToQuit.connect(self.cleanup)
        app.screenRemoved.connect(self.displays_changed)
        app.screenAdded.connect(self.watch_screen)
        for screen in app.screens():
            self.watch_screen(screen)

    def displays_changed(self, *_args):
        if self.exiting:
            return
        self.placement.cancel()
        self.capture.cancel()

    def watch_screen(self, screen):
        self.displays_changed()
        screen.geometryChanged.connect(self.displays_changed)
        screen.logicalDotsPerInchChanged.connect(self.displays_changed)

    def hotkey_error(self, detail):
        alternative = (' Choose Hide All shortcut → Ctrl+Alt+Shift+H in the tray menu if H conflicts.'
                       if not self.platform.shortcuts.mac and self.preferences.windows_hide == 'default' else '')
        self.notify('A global shortcut is unavailable. Working shortcuts remain registered. '
                    'Close or reassign the application that owns the unavailable shortcut, then '
                    f'use Retry global shortcut from the {self.platform.shortcuts.status_location} menu.'
                    f'{alternative}\n{detail}')

    def update_shortcut_labels(self):
        policy = self.platform.shortcuts
        self.tray.setToolTip(f"Mini Whiteboard {APP_VERSION} · {policy.global_label('W')} / {policy.global_label('S')} / {policy.global_label('H')}")

    def change_shortcut_preset(self, preset):
        self.placement.cancel()
        self.capture.cancel()
        self.hotkeys.set_preset(preset)
        self.preferences.set_shortcut_preset(preset)
        self.platform.shortcuts = ShortcutPolicy(mac=True, preset=preset)
        self.update_shortcut_labels()
        self.retry_hotkey()

    def change_hide_shortcut(self, choice):
        self.hotkeys.set_hide_shortcut(choice)
        self.preferences.set_windows_hide(choice)
        self.platform.shortcuts = ShortcutPolicy(hide_shortcut=choice)
        self.update_shortcut_labels()
        self.retry_hotkey()

    def capture_permission_error(self, detail):
        box = QMessageBox(QMessageBox.Icon.Information, "Screen Recording permission", detail)
        settings = box.addButton("Open System Settings", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is settings:
            self.platform.capture.open_permission_settings()

    def retry_hotkey(self):
        try:
            self.hotkeys.start()
            policy = self.platform.shortcuts
            self.notify(f"{policy.global_label('W')}, {policy.global_label('S')} and {policy.global_label('H')} are ready.")
        except OSError as error:
            self.hotkey_error(str(error))

    def notify(self, text):
        self.tray.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, 3000)

    def create_board(self, rect, *, screenshot=False):
        board = BoardWindow(f"Whiteboard {self.next_number}", self.preferences, self.platform, screenshot=screenshot)
        try:
            board.place(rect)
        except (OSError, ValueError) as error:
            board.close()
            board.deleteLater()
            self.notify(str(error))
            return
        self.next_number += 1
        board.deleted.connect(self.delete_board)
        board.minimized.connect(self.remember_minimized)
        board.restored.connect(self.forget_hidden_board)
        self.boards.append(board)
        return board

    def create_screenshot_board(self, rect, image):
        from .geometry import Rect
        from .images import from_image
        from .transforms import Affine, translation
        from dataclasses import replace
        try:
            obj = from_image(image, locked=True)
        except (ValueError, OSError) as error:
            self.notify(f"Screenshot capture failed: {error}")
            return
        scale = self.platform.desktop.placement_scale(rect)
        # Keep the captured region's origin and ratio. Tiny captures enlarge
        # uniformly to the minimum board size, without adding letterbox gutters.
        enlarge = max(1, MIN_WIDTH*scale/rect.width, MIN_HEIGHT*scale/rect.height)
        body = Rect(rect.x, rect.y, rect.width*enlarge, rect.height*enlarge)
        board = self.create_board(body, screenshot=True)
        if board is None:
            return
        canvas = board.canvas
        factor = min(canvas.width()/image.width(), canvas.height()/image.height())
        x = (canvas.width()-image.width()*factor)/2
        y = (canvas.height()-image.height()*factor)/2
        obj = replace(obj, transform=translation(x,y) @ Affine(a=factor,d=factor))
        canvas.commit_edit((obj,), "Capture screenshot", set())
        canvas.set_screenshot_background(obj)
        canvas.tool = "Draw"
        canvas.update_cursor()
        canvas.show_feedback("Locked · right-click to unlock")
        return board

    def delete_board(self, board):
        self.forget_hidden_board(board)
        if board in self.boards:
            self.boards.remove(board)
        if board in self.minimized_order:
            self.minimized_order.remove(board)
        board.deleteLater()

    def remember_minimized(self, board):
        if board in self.minimized_order:
            self.minimized_order.remove(board)
        self.minimized_order.append(board)

    def restore_board(self, board):
        if board in self.minimized_order:
            self.minimized_order.remove(board)
        board.restore()

    def forget_hidden_board(self, board):
        if board in self.hidden_batch:
            self.hidden_batch.remove(board)

    def toggle_visibility(self):
        self.menu.close()
        self.placement.cancel()
        self.capture.cancel()
        if self.hidden_batch:
            restore, self.hidden_batch = self.hidden_batch, []
            for board in restore:
                if board in self.boards and not board._closing and not board.isVisible():
                    board.restore(activate=False)
            return
        visible = [board for board in self.boards if board.isVisible() and not board._closing]
        self.hidden_batch = self.platform.desktop.board_order(visible)
        for board in self.hidden_batch:
            board.prepare_hide()
            board.hide()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick and self.minimized_order:
            self.restore_board(self.minimized_order[-1])

    def rebuild_menu(self):
        rebuild_menu(self)

    def show_about(self):
        box = QMessageBox(QMessageBox.Icon.NoIcon, 'About Mini Whiteboard',
                          f'Mini Whiteboard\nVersion {APP_VERSION}\n\nA small space for ideas.')
        box.setWindowIcon(app_icon())
        box.setIconPixmap(app_icon().pixmap(64, 64))
        box.exec()

    def change_login(self, enabled):
        try:
            state = self.platform.login.set_enabled(enabled)
            if state.approval_required:
                box = QMessageBox(QMessageBox.Icon.Information, 'Open at login', state.detail)
                settings = box.addButton('Open startup settings', QMessageBox.ButtonRole.ActionRole)
                box.addButton(QMessageBox.StandardButton.Ok)
                box.exec()
                if box.clickedButton() is settings:
                    self.platform.login.open_settings()
        except OSError as error:
            QMessageBox.warning(None, 'Open at login', str(error))
        self.rebuild_menu()

    def open_login_settings(self):
        try:
            self.platform.login.open_settings()
        except OSError as error:
            QMessageBox.warning(None, 'Open at login', str(error))

    def show_shortcuts(self):
        QMessageBox.information(None, "Keyboard shortcuts", self.platform.shortcuts.help_html())

    def cleanup(self):
        if self.exiting:
            return
        self.exiting = True
        self.hidden_batch.clear()
        self.placement.cancel()
        self.capture.cancel()
        self.hotkeys.close()
        for board in tuple(self.boards):
            board.close()
        self.tray.hide()
        self.menu.close()


def main():
    if "--version" in sys.argv:
        if sys.stdout is not None:
            print(f"{APP_NAME} {APP_VERSION}")
        return 0
    platform = get_platform()
    platform.runtime.prepare()
    guard = platform.runtime.single_instance()
    if not guard.acquired:
        # SMAppService launches the main bundle without custom arguments.
        # All duplicate launches stay quiet, including automatic/manual overlap.
        guard.close()
        return 0
    try:
        app = QApplication(sys.argv)
        platform.runtime.configure_application(app)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, APP_NAME, f"The system {platform.shortcuts.status_location} is unavailable.")
            return 1
        controller = WhiteboardApplication(app, platform=platform)
        result = app.exec()
        controller.cleanup()
        return result
    finally:
        platform.runtime.close()
        guard.close()
