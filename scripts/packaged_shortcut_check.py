"""Opt-in real-key acceptance for both shortcuts in an unmodified Windows EXE.

Owns the app and an external text/menu target. Never substitutes a shortcut or
posts activation messages. Foreground events detect transient shell activation.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'windows'
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mini_whiteboard import windows as n
from mini_whiteboard.geometry import Rect
from mini_whiteboard.settings import SHADOW
from mini_whiteboard.hotkey_config import defaults, compatibility, Chord, HotkeyConfig, ACTIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path,
                        default=Path('dist/windows-v134-review01/Mini Whiteboard/Mini Whiteboard.exe'))
    parser.add_argument('--output', type=Path, default=Path('verification/v134-review01/packaged-shortcuts'))
    parser.add_argument('--profile', choices=('compatibility', 'custom', 'default'), default='compatibility')
    parser.add_argument('--capture-only', action='store_true', help='Exercise the available default Q separately when W conflicts.')
    parser.add_argument('--available-defaults', action='store_true', help='Probe and exercise every available default; report conflicts explicitly.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    configuration = {'default': defaults(hide='shift'), 'compatibility': compatibility(defaults(hide='shift')),
                     'custom': HotkeyConfig(Chord({'ctrl', 'alt'}, 'F8'), Chord({'ctrl', 'meta'}, 'F9'),
                                            defaults(hide='shift').hide)}[args.profile]
    modifier_keys = {'ctrl': (0xA2, 0xA3), 'alt': (0xA4, 0xA5), 'shift': (0xA0, 0xA1), 'meta': (0x5B, 0x5C)}
    n.enable_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    guard = n.SingleInstance()
    available = guard.acquired
    guard.close()
    if not available:
        raise RuntimeError('Exit Mini Whiteboard before this desktop check.')
    executable = args.executable.resolve(strict=True)
    u = n.user32
    foreground = n.bind(u, 'GetForegroundWindow', W.HWND)
    pid_for = n.bind(u, 'GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
    title = n.bind(u, 'GetWindowTextW', C.c_int, W.HWND, W.LPWSTR, C.c_int)
    get_rect = n.bind(u, 'GetWindowRect', W.BOOL, W.HWND, C.POINTER(W.RECT))
    visible = n.bind(u, 'IsWindowVisible', W.BOOL, W.HWND)
    post = n.bind(u, 'PostMessageW', W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    set_cursor = n.bind(u, 'SetCursorPos', W.BOOL, C.c_int, C.c_int)
    key_event = n.bind(u, 'keybd_event', None, W.BYTE, W.BYTE, W.DWORD, C.c_size_t)
    mouse = n.bind(u, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
    at = n.bind(u, 'WindowFromPoint', W.HWND, W.POINT)
    ancestor = n.bind(u, 'GetAncestor', W.HWND, W.HWND, W.UINT)
    enum_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    enum = n.bind(u, 'EnumWindows', W.BOOL, enum_type, W.LPARAM)
    hook_type = C.WINFUNCTYPE(None, W.HANDLE, W.DWORD, W.HWND, W.LONG, W.LONG, W.DWORD, W.DWORD)
    set_hook = n.bind(u, 'SetWinEventHook', W.HANDLE, W.DWORD, W.DWORD, W.HMODULE,
                      hook_type, W.DWORD, W.DWORD, W.DWORD)
    unhook = n.bind(u, 'UnhookWinEvent', W.BOOL, W.HANDLE)
    previous, pointer = foreground(), n.cursor_position()
    process = target = hook = None
    pressed, rows, foreground_events = set(), [], []
    observing = False
    temporary = tempfile.TemporaryDirectory(prefix='miniwhiteboard-packaged-keys-')
    state_path = Path(temporary.name)/'target.json'
    from .native_preferences import compatibility_preferences
    preferences = compatibility_preferences(configuration)
    preferences.__enter__()
    available_actions = set(ACTIONS)
    default_probe = None
    if args.available_defaults:
        if args.profile != 'default':
            raise ValueError('--available-defaults requires --profile default')
        probe = n.NativeHotkeys(app)
        probe.configure(configuration)
        try:
            probe.start()
        except OSError:
            pass
        available_actions = set(probe.registered)
        default_probe = {str(i): {'shortcut': chord.label(), 'registered': i in probe.registered,
                                 'error': probe.errors.get(i)} for i, chord in configuration.items()}
        probe.close()

    def owner(hwnd):
        pid = W.DWORD()
        pid_for(hwnd, C.byref(pid))
        return pid.value

    def name(hwnd):
        text = C.create_unicode_buffer(256)
        title(hwnd, text, len(text))
        return text.value

    def bounds(hwnd):
        rect = W.RECT()
        if not get_rect(hwnd, C.byref(rect)):
            raise RuntimeError('Owned window disappeared')
        return Rect(rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top)

    def windows():
        found = []
        @enum_type
        def visit(hwnd, _):
            if owner(hwnd) == process.pid and visible(hwnd):
                found.append(int(hwnd))
            return True
        enum(visit, 0)
        return found

    def boards():
        return [h for h in windows() if name(h).startswith('Whiteboard ')]

    def previews():
        return [h for h in windows() if any(bounds(h) == m.rect for m in n.monitors())]

    def check(label, condition, detail=None):
        row = {'check': label, 'status': 'PASS' if condition else 'FAIL', 'detail': detail}
        rows.append(row)
        print(json.dumps(row), flush=True)
        if not condition:
            raise AssertionError(label)

    def state():
        for _ in range(120):
            try:
                return json.loads(state_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                QTest.qWait(50)
        raise RuntimeError('External target state unavailable')

    def key(vk, up=False):
        if not up and owner(foreground()) not in (process.pid, target_pid):
            raise RuntimeError('Keyboard focus left the owned test processes')
        key_event(vk, u.MapVirtualKeyW(vk, 0), (2 if up else 0) | (1 if vk in (0x5B, 0x5C, 0xA5) else 0), 0)
        pressed.discard(vk) if up else pressed.add(vk)

    def drain():
        for vk in tuple(pressed):
            key(vk, True)
        QTest.qWait(100)

    def focus():
        u.SetForegroundWindow(target_hwnd)
        QTest.qWait(80)
        if foreground() != target_hwnd:
            u.SetWindowPos(target_hwnd, W.HWND(-1), 0, 0, 0, 0, 0x0053)
            QTest.qWait(80)
            r = bounds(target_hwnd)
            point = (round(r.x+r.width/2), round(r.y+12))
            set_cursor(*point)
            QTest.qWait(30)
            if ancestor(at(W.POINT(*point)), 2) != target_hwnd:
                raise RuntimeError('Owned focus target is covered')
            mouse(2, 0, 0, 0, 0)
            mouse(4, 0, 0, 0, 0)
            QTest.qWait(80)
            u.SetWindowPos(target_hwnd, W.HWND(-2), 0, 0, 0, 0, 0x0013)
        check('External text application has focus', foreground() == target_hwnd)

    @hook_type
    def foreground_changed(_hook, _event, hwnd, *_args):
        if observing:
            foreground_events.append({'hwnd': int(hwnd or 0), 'pid': owner(hwnd), 'title': name(hwnd)})

    def start(chord, point):
        nonlocal observing
        focus()
        foreground_events.clear()
        observing = True
        set_cursor(*point)
        for vk in chord:
            key(vk)

    def settled(label):
        nonlocal observing
        drain()
        observing = False
        unexpected = [e for e in foreground_events if e['pid'] not in (process.pid, target_pid)]
        check(label+' leaves no shell/other-app activation or held key', not unexpected
              and not previews() and not any(u.GetAsyncKeyState(vk) & 0x8000
                  for vk in (0x5B, 0x5C, 0xA4, 0xA5, 0xA0, 0xA1, 0xA2, 0xA3,
                             configuration.create.windows_key, configuration.capture.windows_key, 27)), unexpected)
        external = state()
        check(label+' leaves external text and Alt menu untouched', external['text'] == original
              and not external['menu_active'] and not external['menu_shows'])

    def close_boards():
        for hwnd in boards():
            post(hwnd, 0x10, 0, 0)
        QTest.qWait(80)
        check('Closing the owned board retains the tray process', not boards() and process.poll() is None)

    try:
        process = subprocess.Popen([str(executable)], creationflags=subprocess.CREATE_NO_WINDOW)
        QTest.qWait(1800)
        check('Final executable starts quietly', process.poll() is None and not windows())
        target = subprocess.Popen([sys.executable, '-m', 'scripts.creation_shortcut_check',
                                   '--focus-target', str(state_path)], creationflags=subprocess.CREATE_NO_WINDOW)
        identity = state()
        target_hwnd, target_pid = identity['hwnd'], identity['pid']
        original = identity['text']
        hook = set_hook(3, 3, None, foreground_changed, 0, 0, 0)
        check('Foreground observer is active', bool(hook))
        points = (((180, 220), (540, 440)), ((540, 440), (180, 220)),
                  ((180, 440), (540, 220)), ((540, 220), (180, 440)))
        for identifier, binding in configuration.items()[:2]:
            if identifier not in available_actions:
                check('Default unavailable: positive gesture NOT RUN', True, default_probe[str(identifier)])
                continue
            if args.capture_only and identifier == ACTIONS[0]:
                continue
            trigger, trigger_key = binding.key, binding.windows_key
            variants = tuple(itertools.product(*(modifier_keys[m] for m in ('meta', 'ctrl', 'alt', 'shift') if m in binding.modifiers)))
            for variant, modifiers in enumerate(variants):
                chord = (*modifiers, trigger_key)
                for index, first in enumerate(chord):
                    begin, end = points[index]
                    start(chord, begin)
                    QTest.qWait(120)
                    check(trigger+' actual native hold starts only a passive preview',
                          bool(previews()) and not boards() and foreground() == target_hwnd,
                          {'modifiers': modifiers, 'first_release': first, 'begin': begin, 'end': end})
                    set_cursor(*end)
                    for _ in range(6):
                        key(trigger_key)
                        QTest.qWait(12)
                    check(trigger+' held repeats cannot create a board', not boards() and bool(previews()))
                    if variant == 0 and index == 0:
                        n.capture_rect(Rect(150, 190, 430, 290)).save(str(args.output/(trigger+'-actual-preview.png')))
                    order = (first,)+tuple(vk for vk in reversed(chord) if vk != first)
                    for vk in order:
                        key(vk, True)
                        QTest.qWait(150)
                        check(trigger+' each release leaves exactly one result', len(boards()) == 1)
                    hwnd = boards()[0]
                    scale = u.GetDpiForWindow(hwnd)/96
                    shadow = round(SHADOW*scale)
                    r = bounds(hwnd)
                    paper = Rect(r.x+shadow, r.y+shadow, r.width-2*shadow, r.height-2*shadow)
                    check(trigger+' board matches the normalized physical rectangle', paper == Rect(180, 220, 360, 220), vars(paper))
                    check(trigger+' completion focuses its result', foreground() == hwnd)
                    if variant == 0 and index == 0:
                        n.capture_rect(paper).save(str(args.output/(trigger+'-actual-result.png')))
                    settled(trigger+' completed gesture')
                    close_boards()
                start(chord, (180, 220))
                QTest.qWait(100)
                set_cursor(540, 440)
                key(27)
                QTest.qWait(50)
                key(27, True)
                for _ in range(8):
                    key(trigger_key)
                    QTest.qWait(15)
                check(trigger+' Escape cancels and suppresses held restart', not boards() and not previews()
                      and foreground() == target_hwnd)
                settled(trigger+' cancelled gesture')
            chord = (*variants[0], trigger_key)
            for attempt in range(3):
                start(chord, (180, 220))
                # Give the native activation one event turn, then release fast.
                QTest.qWait(20)
                set_cursor(540, 440)
                for vk in reversed(chord):
                    key(vk, True)
                QTest.qWait(200)
                check(trigger+' rapid consecutive gesture creates exactly one result', len(boards()) == 1, attempt)
                settled(trigger+' rapid gesture')
                close_boards()
            start(chord, (180, 220))
            QTest.qWait(40)
            drain()
            check(trigger+' zero-area release cancels', not boards() and not previews())
            settled(trigger+' zero-area gesture')
        check('Selected configuration passed in the final executable', True, args.profile)
    finally:
        observing = False
        drain()
        if hook:
            unhook(hook)
        for child in (process, target):
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        set_cursor(*pointer)
        if previous:
            u.SetForegroundWindow(previous)
        temporary.cleanup()
        preferences.__exit__(None, None, None)
        (args.output/'checks.json').write_text(json.dumps({'executable': str(executable),
            'profile': args.profile, 'capture_only': args.capture_only, 'configuration': json.loads(configuration.to_json()),
            'default_registration_probe': default_probe,
            'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(), 'checks': rows,
            'limits': ['Physical negative-coordinate and mixed-DPI monitors were not available.']}, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
