"""Opt-in Windows native key/release matrix, using only disposable owned windows.

Exercises the actual RegisterHotKey and foreground routes. A pre-existing
shortcut owner is reported as NOT RUN, never bypassed or silently substituted.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtCore import QSettings, QTimer, Qt, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit
from mini_whiteboard import windows as n
from mini_whiteboard.app import WhiteboardApplication
from mini_whiteboard.platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY
from mini_whiteboard.snapping import SnapPreferences


def focus_target(path):
    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle('Mini Whiteboard disposable shortcut target')
    edit = QTextEdit('Owned test content. Global creation must leave this text and its menus alone.')
    window.setCentralWidget(edit)
    menu = window.menuBar().addMenu('File')
    menu.addAction('Test command')
    shown = []
    menu.aboutToShow.connect(lambda: shown.append(True))
    window.setGeometry(90, 90, 780, 520)
    window.show()
    edit.setFocus()
    def report():
        path.write_text(json.dumps({'hwnd': int(window.winId()), 'pid': os.getpid(),
            'text': edit.toPlainText(), 'menu_shows': len(shown),
            'menu_active': window.menuBar().hasFocus() or menu.isVisible()}), encoding='utf-8')
    timer = QTimer(window)
    timer.timeout.connect(report)
    timer.start(40)
    report()
    return app.exec()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--focus-target', type=Path)
    parser.add_argument('--output', type=Path, default=Path('verification/v133-review02/creation-shortcuts.json'))
    parser.add_argument('--require-both', action='store_true')
    args = parser.parse_args()
    if args.focus_target:
        return focus_target(args.focus_target)
    n.enable_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    guard = n.SingleInstance()
    if not guard.acquired:
        raise RuntimeError('Exit Mini Whiteboard before this opt-in desktop test.')
    u = n.user32
    foreground = n.bind(u, 'GetForegroundWindow', W.HWND)
    set_cursor = n.bind(u, 'SetCursorPos', W.BOOL, C.c_int, C.c_int)
    key_event = n.bind(u, 'keybd_event', None, W.BYTE, W.BYTE, W.DWORD, C.c_size_t)
    previous, pointer = foreground(), n.cursor_position()
    pressed, rows, warnings, errors, limits = set(), [], [], [], []
    previous_hook = sys.excepthook
    sys.excepthook = lambda kind, error, tb: errors.append(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix='miniwhiteboard-creation-check-')
    root = Path(temporary.name)
    state_path = root/'target.json'
    prefs = SnapPreferences(settings=QSettings(str(root/'settings.ini'), QSettings.Format.IniFormat))
    prefs.set_windows_hide('shift')
    # Reserve just Q with an owned registration, then release it and retry.
    # Existing third-party owners are never unregistered or overridden.
    reserved = bool(u.RegisterHotKey(None, 0x5571, 13 | n.MOD_NOREPEAT, ord('Q')))
    controller = WhiteboardApplication(app, prefs)
    controller.notify = warnings.append
    target = subprocess.Popen([sys.executable, '-m', __name__ if __name__ != '__main__' else 'scripts.creation_shortcut_check',
                               '--focus-target', str(state_path)], creationflags=subprocess.CREATE_NO_WINDOW)
    target_hwnd = None

    def state():
        for _ in range(10):
            try:
                return json.loads(state_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                QTest.qWait(20)
        raise RuntimeError('Disposable target state is unavailable')

    def check(label, condition, detail=None):
        row = {'check': label, 'status': 'PASS' if condition else 'FAIL', 'detail': detail}
        rows.append(row)
        print(json.dumps(row), flush=True)
        if not condition:
            raise AssertionError(label)

    def key(vk, up=False):
        key_event(vk, u.MapVirtualKeyW(vk, 0), (2 if up else 0) | (1 if vk in (0x5B, 0x5C, 0xA5) else 0), 0)
        pressed.discard(vk) if up else pressed.add(vk)

    def drain():
        for vk in tuple(pressed):
            key(vk, True)
        QTest.qWait(100)

    def focus():
        u.SetForegroundWindow(target_hwnd)
        QTest.qWait(100)
        check('Disposable external application owns keyboard focus', foreground() == target_hwnd)

    def idle(label):
        check(label, not controller.placement.state.active and not controller.capture.active
              and not controller.placement.overlays and not controller.capture.overlays
              and not controller.hotkeys.hold.timer.isActive() and not controller.hotkeys.hold.blocked
              and not any(u.GetAsyncKeyState(vk) & 0x8000 for vk in (0x5B, 0x5C, 0xA4, 0xA5, 0xA0, 0xA1, 87, 81)))

    try:
        if reserved:
            app.processEvents()
            check('Owned Q registration conflict preserves other working bindings',
                  CAPTURE_HOTKEY not in controller.hotkeys.registered, warnings)
            working = set(controller.hotkeys.registered)
            controller.retry_hotkey()
            check('Retry while Q is occupied preserves registered bindings', controller.hotkeys.registered == working)
            u.UnregisterHotKey(None, 0x5571)
            reserved = False
            controller.retry_hotkey()
            check('Retry registers the released Q binding without changing working shortcuts',
                  controller.hotkeys.registered == working | {CAPTURE_HOTKEY})
        for _ in range(100):
            if state_path.exists():
                break
            QTest.qWait(30)
        target_hwnd = state()['hwnd']
        original = state()['text']
        QTest.qWait(100)
        for trigger, identifier in (('W', CREATE_HOTKEY), ('Q', CAPTURE_HOTKEY)):
            if identifier not in controller.hotkeys.registered:
                limits.append(f'Win+Alt+Shift+{trigger} positive native gestures: NOT RUN (registration conflict on this desktop)')
                controller.rebuild_menu()
                check(f'{trigger} conflict remains visible with retry and working bindings',
                      any('unavailable' in a.text() and 'Win+Alt+Shift+'+trigger in a.text() for a in controller.menu.actions())
                      and any(a.text() == 'Retry global shortcut' for a in controller.menu.actions()), warnings)
                continue
            for win, alt, shift in itertools.product((0x5B, 0x5C), (0xA4, 0xA5), (0xA0, 0xA1)):
                chord = (win, alt, shift, ord(trigger))
                for first in chord:
                    order = (first,) + tuple(vk for vk in reversed(chord) if vk != first)
                    focus()
                    count = len(controller.boards)
                    set_cursor(180, 220)
                    for vk in (win, alt, shift, ord(trigger)):
                        key(vk)
                    QTest.qWait(100)
                    active = controller.placement.state.active if trigger == 'W' else controller.capture.active
                    check(f'{trigger} hold has one passive preview before release', active and len(controller.boards) == count
                          and foreground() == target_hwnd, {'win': win, 'alt': alt, 'shift': shift, 'release_order': order})
                    set_cursor(540, 440)
                    QTest.qWait(60)
                    for _ in range(5):
                        key(ord(trigger))
                    for index, vk in enumerate(order):
                        key(vk, True)
                        QTest.qWait(100)
                        check(f'{trigger} release {index+1} creates exactly one board', len(controller.boards) == count+1)
                    board = controller.boards[-1]
                    check(f'{trigger} release keeps foreground on its board, with no external menu',
                          foreground() == int(board.winId()) and not state()['menu_active'] and state()['menu_shows'] == 0)
                    idle(f'{trigger} completed chord drains every key and preview')
                    board.close()
                    QTest.qWait(30)
                focus()
                count = len(controller.boards)
                set_cursor(180, 220)
                for vk in (win, alt, shift, ord(trigger)):
                    key(vk)
                QTest.qWait(100)
                set_cursor(540, 440)
                QTest.qWait(70)
                overlays = controller.placement.overlays if trigger == 'W' else controller.capture.overlays
                if win == 0x5B and alt == 0xA4:
                    for index, overlay in enumerate(overlays):
                        overlay.grab().save(str(args.output.parent/f'{trigger}-native-preview-{index}.png'))
                key(27)
                QTest.qWait(50)
                key(27, True)
                for _ in range(12):
                    key(ord(trigger))
                    QTest.qWait(10)
                check(f'{trigger} Escape cancels without restart or foreground/menu activation',
                      len(controller.boards) == count and not controller.placement.state.active and not controller.capture.active
                      and foreground() == target_hwnd and not state()['menu_active'])
                drain()
                idle(f'{trigger} cancellation drains modifiers without a result')
        if CAPTURE_HOTKEY in controller.hotkeys.registered:
            # Keep real native activation and release; inject only the capture
            # service failure, which cannot be safely forced in a shipped EXE.
            service = controller.capture.service
            original_capture = service.capture_region
            failures = []
            controller.capture.message.connect(failures.append)
            def fail_capture(_rect, _success, failure, _excluded):
                failure(OSError('Owned verification capture failure'))
            try:
                service.capture_region = fail_capture
                focus()
                count = len(controller.boards)
                set_cursor(180, 220)
                for vk in (0x5B, 0xA4, 0xA0, ord('Q')):
                    key(vk)
                QTest.qWait(80)
                set_cursor(540, 440)
                key(ord('Q'), True)
                QTest.qWait(150)
                drain()
                check('Native Q capture failure reports its error without a board',
                      len(controller.boards) == count and any('Owned verification' in s for s in failures))
                idle('Native Q failure drains its gesture and previews')
            finally:
                service.capture_region = original_capture
            focus()
            set_cursor(180, 220)
            for vk in (0x5B, 0xA4, 0xA0, ord('Q')):
                key(vk)
            QTest.qWait(80)
            set_cursor(540, 440)
            key(ord('Q'), True)
            QTest.qWait(180)
            drain()
            check('Next native Q gesture recovers after capture failure', len(controller.boards) == count+1)
            controller.boards[-1].close()
            QTest.qWait(50)
        focus()
        QTest.qWait(100)
        check('All native gestures leave external text and menu unchanged',
              state()['text'] == original and not state()['menu_active'] and not state()['menu_shows'])
        check('No Qt callback exceptions', not errors, errors)
        if args.require_both:
            check('Both requested creation shortcuts completed the native matrix', not limits, limits)
    finally:
        drain()
        if reserved:
            u.UnregisterHotKey(None, 0x5571)
        controller.cleanup()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if target_hwnd:
            n.bind(u, 'PostMessageW', W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)(target_hwnd, 0x10, 0, 0)
        try:
            target.wait(timeout=4)
        except subprocess.TimeoutExpired:
            target.terminate()
            target.wait(timeout=4)
        guard.close()
        set_cursor(*pointer)
        if previous:
            u.SetForegroundWindow(previous)
        temporary.cleanup()
        sys.excepthook = previous_hook
        args.output.write_text(json.dumps({'checks': rows, 'not_run': limits, 'warnings': warnings,
                                          'exceptions': errors}, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
