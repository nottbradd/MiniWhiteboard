"""Inspect and briefly launch only the built executable owned by this test."""
import ctypes as C
import argparse
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import time
import sys

import pefile
from PySide6.QtGui import QGuiApplication
from mini_whiteboard import windows
from mini_whiteboard import APP_VERSION
from mini_whiteboard.geometry import Rect
from mini_whiteboard.settings import BORDER, SHADOW
from .build_support import verify_release_files, verify_ocr_runtime


def main():
    windows.enable_dpi_awareness()
    app = QGuiApplication.instance() or QGuiApplication([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=Path("dist/windows-v13/Mini Whiteboard/Mini Whiteboard.exe"))
    args = parser.parse_args()
    executable = args.executable.resolve()
    results = []

    def check(label, condition, detail=None):
        entry = {"check": label, "status": "PASS" if condition else "FAIL", "detail": detail}
        results.append(entry)
        print(json.dumps(entry), flush=True)
        if not condition:
            raise AssertionError(label)

    notices = verify_release_files(executable.parent)
    verify_ocr_runtime(executable.parent)
    check('License notices are complete and unused Qt products are absent', True, notices)
    pe = pefile.PE(str(executable))
    check("Executable is Windows GUI subsystem (no console)", pe.OPTIONAL_HEADER.Subsystem == 2)
    version_strings = {}
    for group in pe.FileInfo:
        for entry in group:
            for table in getattr(entry, 'StringTable', ()):
                version_strings.update(table.entries)
    parts = tuple(int(part) for part in APP_VERSION.split('.'))
    numeric = (parts + (0, 0, 0, 0))[:4]
    fixed = pe.VS_FIXEDFILEINFO[0]
    check(f'Executable string and numeric metadata are Version {APP_VERSION}',
          version_strings.get(b'ProductVersion') == APP_VERSION.encode()
          and version_strings.get(b'FileVersion') == APP_VERSION.encode()
          and fixed.FileVersionMS == fixed.ProductVersionMS == (numeric[0] << 16 | numeric[1])
          and fixed.FileVersionLS == fixed.ProductVersionLS == (numeric[2] << 16 | numeric[3]),
          {key.decode(): value.decode() for key,value in version_strings.items()})
    check('Bundled JPEG and WEBP decoders are included',
          all((executable.parent/'_internal/PySide6/plugins/imageformats'/name).is_file()
              for name in ('qjpeg.dll','qwebp.dll')))
    manifests = []
    for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if resource.id == 24:
            for name in resource.directory.entries:
                for language in name.directory.entries:
                    data = language.data.struct
                    manifests.append(pe.get_data(data.OffsetToData, data.Size).decode("utf-8", errors="replace"))
    check("Embedded manifest is PerMonitorV2 and asInvoker",
          any("PerMonitorV2" in text and 'level="asInvoker"' in text and 'assemblyIdentity version="1.3.0.0"' in text for text in manifests))
    initial = windows.SingleInstance()
    if not initial.acquired:
        initial.close()
        raise SystemExit("Exit Mini Whiteboard before testing the packaged executable.")
    initial.close()
    process = subprocess.Popen([str(executable)], creationflags=subprocess.CREATE_NO_WINDOW)
    saved_cursor = windows.cursor_position()
    helper = None
    pressed = set()
    previous = windows.bind(windows.user32, "GetForegroundWindow", W.HWND)()
    try:
        acquired = True
        for _ in range(50):
            guard = windows.SingleInstance()
            acquired = guard.acquired
            guard.close()
            if not acquired or process.poll() is not None:
                break
            time.sleep(.1)
        check("Packaged application starts and holds mutex", process.poll() is None and not acquired)
        duplicate = subprocess.run([str(executable)], timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        check("Second packaged instance exits quietly", duplicate.returncode == 0 and process.poll() is None)
        time.sleep(1)
        visible = []
        owned_windows = []
        user32 = windows.user32
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        enum = windows.bind(user32, "EnumWindows", W.BOOL, callback_type, W.LPARAM)
        get_pid = windows.bind(user32, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
        is_visible = windows.bind(user32, "IsWindowVisible", W.BOOL, W.HWND)

        @callback_type
        def visit(handle, param):
            pid = W.DWORD()
            get_pid(handle, C.byref(pid))
            if pid.value == process.pid:
                owned_windows.append(int(handle))
                if is_visible(handle):
                    visible.append(int(handle))
            return True

        enum(visit, 0)
        check("Packaged startup has no visible board/dashboard/console", visible == [], visible)
        # A hidden tray/message window identifies the real GUI thread without
        # guessing the first thread in the process. Post messages only there.
        if not owned_windows:
            raise AssertionError("Packaged Qt tray did not create a message window")
        thread = get_pid(owned_windows[0], None)
        post_thread = windows.bind(user32, "PostThreadMessageW", W.BOOL, W.DWORD, W.UINT, W.WPARAM, W.LPARAM)
        set_cursor = windows.bind(user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)
        title = windows.bind(user32, "GetWindowTextW", C.c_int, W.HWND, W.LPWSTR, C.c_int)
        get_rect = windows.bind(user32, 'GetWindowRect', W.BOOL, W.HWND, C.POINTER(W.RECT))

        def board_windows():
            visible.clear()
            owned_windows.clear()
            enum(visit, 0)
            found = []
            for handle in visible:
                text = C.create_unicode_buffer(256)
                title(handle, text, 256)
                if text.value.startswith("Whiteboard "):
                    found.append(handle)
            return found

        def preview_windows():
            board_windows()
            previews = []
            monitors = windows.monitors()
            for handle in visible:
                rect = W.RECT()
                if get_rect(handle, C.byref(rect)):
                    bounds = Rect(rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top)
                    if any(bounds == m.rect for m in monitors):
                        previews.append(handle)
            return previews

        helper = subprocess.Popen([sys.executable, '-m', 'scripts.focus_target'], stdout=subprocess.PIPE,
                                  text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        identity = json.loads(helper.stdout.readline())
        foreground = windows.bind(user32, 'GetForegroundWindow', W.HWND)
        def focus_helper():
            user32.SetForegroundWindow(identity['hwnd'])
            time.sleep(.2)
            if foreground() != identity['hwnd']:
                user32.SetWindowPos(identity['hwnd'], W.HWND(-1), 0, 0, 0, 0, 0x0053)
                time.sleep(.4)
                set_cursor(100, 130)
                get_at = windows.bind(user32, 'WindowFromPoint', W.HWND, W.POINT)
                owner = W.DWORD()
                get_pid(get_at(W.POINT(*windows.cursor_position())), C.byref(owner))
                check('Packaged external activation target is owned', owner.value == identity['pid'])
                mouse = windows.bind(user32, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
                mouse(2, 0, 0, 0, 0)
                mouse(4, 0, 0, 0, 0)
                time.sleep(.2)
                user32.SetWindowPos(identity['hwnd'], W.HWND(-2), 0, 0, 0, 0, 0x0013)
            check('Packaged test has external helper focus', foreground() == identity['hwnd'])

        focus_helper()
        key_event = windows.bind(user32, 'keybd_event', None, W.BYTE, W.BYTE, W.DWORD, C.c_size_t)

        def key(vk, up=False):
            key_event(vk, 0, 2 if up else 0, 0)
            pressed.discard(vk) if up else pressed.add(vk)

        def begin(trigger, point):
            set_cursor(*point)
            for vk in (0x11, 0x12, ord(trigger)):
                key(vk)
            time.sleep(.2)

        def release_all():
            for vk in tuple(pressed):
                key(vk, True)
            time.sleep(.15)

        def wait_boards(count):
            for _ in range(40):
                boards = board_windows()
                if len(boards) == count or process.poll() is not None:
                    return boards
                time.sleep(.1)
            return boards

        begin('W', (130,150))
        check('Packaged hold starts preview without a board', not board_windows() and bool(preview_windows()))
        check('Packaged passive preview preserves external focus', foreground() == identity['hwnd'])
        set_cursor(630,490)
        for _ in range(30):
            key(ord('W'))
            time.sleep(.04)
        check('Packaged long repeated hold cannot create a board', not board_windows() and bool(preview_windows()))
        key(0x11, True)
        boards = wait_boards(1)
        check('Packaged modifier-first release creates one board', len(boards) == 1)
        key(0x12, True)
        for _ in range(8):
            key(ord('W'))
            time.sleep(.025)
        check('Packaged remaining held trigger does not create another preview', len(board_windows()) == 1
              and not preview_windows())
        release_all()
        actual_rect = W.RECT()
        get_rect = windows.bind(user32,'GetWindowRect',W.BOOL,W.HWND,C.POINTER(W.RECT))
        if not get_rect(boards[0],C.byref(actual_rect)):
            raise RuntimeError('Cannot inspect the owned board bounds')
        dpi = windows.bind(user32,'GetDpiForWindow',W.UINT,W.HWND)(boards[0]) / 96
        shadow = round(SHADOW*dpi)
        paper = Rect(actual_rect.left+shadow,actual_rect.top+shadow,
                     actual_rect.right-actual_rect.left-2*shadow,
                     actual_rect.bottom-actual_rect.top-2*shadow)
        check('Packaged paper matches hold rectangle', paper == Rect(130,150,500,340), vars(paper))
        surface = windows.capture_rect(paper)
        width,height = surface.width(),surface.height()
        pixels = [surface.pixelColor(x,y).name() for x,y in
                  ((width//2,0),(0,height//2),(width-1,height//2),(width//2,height-1))]
        check('Packaged blank board has top line and no side or bottom outlines',
              pixels[0]==BORDER and all(p=='#ffffff' for p in pixels[1:]), pixels)
        # Native input targets only this owned frozen board. Pixel assertions
        # observe its visible editor/artwork without adding a test API to the app.
        mouse = windows.bind(user32, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
        get_at = windows.bind(user32, 'WindowFromPoint', W.HWND, W.POINT)
        ancestor = windows.bind(user32, 'GetAncestor', W.HWND, W.HWND, W.UINT)
        owned_board = boards[0]

        def click_paper(x, y):
            p = (round(paper.x+x*dpi), round(paper.y+y*dpi))
            set_cursor(*p)
            time.sleep(.04)
            if ancestor(get_at(W.POINT(*p)), 2) != owned_board:
                raise RuntimeError('Frozen textbox click is outside the owned board')
            mouse(2, 0, 0, 0, 0)
            try:
                time.sleep(.04)
            finally:
                mouse(4, 0, 0, 0, 0)
            time.sleep(.12)

        def text_key(vk, ctrl=False):
            if foreground() != owned_board:
                raise RuntimeError('Frozen textbox key target is not the owned board')
            if ctrl:
                key(0x11)
            try:
                key(vk)
                key(vk, True)
            finally:
                if ctrl:
                    key(0x11, True)
            time.sleep(.08)

        def dark_content():
            area = Rect(round(paper.x+14*dpi), round(paper.y+40*dpi),
                        round(paper.width-28*dpi), round(paper.height-105*dpi))
            image = windows.capture_rect(area)
            return sum(image.pixelColor(x, y).lightness() < 150
                       for y in range(image.height()) for x in range(image.width()))

        text_key(ord('T'))
        click_paper(50, 80)
        check('Frozen native Text click visibly opens an editor', dark_content() > 5)
        click_paper(60, 190)
        check('Frozen native blank dismissal removes the editor without replacement', dark_content() == 0)
        text_key(ord('Q'))
        text_key(0x1B)
        check('Frozen dismissal leaves no editor to receive stray typing', dark_content() == 0)
        click_paper(80, 220)
        for _ in range(4):
            text_key(ord('Q'))
        text_key(0x1B)
        check('Frozen next intentional click types and commits text', dark_content() > 8)
        text_key(ord('Z'), ctrl=True)
        check('Frozen text creation is one document undo', dark_content() == 0)
        text_key(ord('Y'), ctrl=True)
        check('Frozen text creation redo restores visible content', dark_content() > 8)
        text_key(0x1B)  # Clear selection handles before reopening.
        click_paper(90, 230)
        text_key(ord('A'), ctrl=True)
        text_key(0x08)
        text_key(0x0D, ctrl=True)
        check('Frozen clearing existing text removes invisible objects/editor', dark_content() == 0)
        text_key(ord('Z'), ctrl=True)
        check('Frozen cleared-text undo restores the original artwork', dark_content() > 8)
        text_key(ord('Y'), ctrl=True)
        check('Frozen cleared-text redo removes it again', dark_content() == 0)
        text_key(ord('C'))
        click_paper(370, 100)
        text_key(ord('Q'))
        text_key(0x1B)
        check('Frozen palette dismissal does not replay into textbox creation', dark_content() == 0)
        point = (round(paper.x+paper.width*.2),round(paper.y+paper.height*.3))
        end = (round(paper.x+paper.width*.7),round(paper.y+paper.height*.7))
        begin('S', point)
        check('Packaged screenshot hold starts only a preview', len(board_windows()) == 1 and bool(preview_windows()))
        set_cursor(*end)
        time.sleep(.15)
        key(ord('S'), True)
        boards = wait_boards(2)
        release_all()
        check('Packaged screenshot release creates image board without mouse input', len(boards) == 2 and process.poll() is None)
        post = windows.bind(user32, 'PostMessageW', W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        for handle in boards:
            post(handle, 0x0010, 0, 0)
        time.sleep(.2)
        check('Packaged close preserves tray process', not board_windows() and process.poll() is None)
        focus_helper()
        # No text is typed here; a registered global shortcut is sent only while
        # the owned helper has focus. Abort if Windows denied foreground access.
        check('External helper restored before packaged cancellation', foreground() == identity['hwnd'])
        begin('S', (250,330))
        key(0x1b)
        time.sleep(.1)
        key(0x1b, True)
        for _ in range(10):
            key(ord('S'))
            time.sleep(.03)
        check('Packaged Escape while held removes preview and suppresses restart', not board_windows() and not preview_windows())
        release_all()
        begin('W', (250,330))
        release_all()
        check('Packaged too-small release cancels completely', not board_windows() and not preview_windows())
        begin('W', (130,150))
        set_cursor(630,490)
        release_all()
        check('Packaged fresh hold recovers after cancellation', len(wait_boards(1)) == 1)
    finally:
        # This test created the process without boards; terminate only that
        # exact subprocess. Normal application exit is via its tray action.
        for vk in tuple(pressed):
            key_event(vk, 0, 2, 0)
        process.terminate()
        process.wait(timeout=10)
        if helper is not None:
            helper.terminate()
            helper.wait(timeout=10)
        if previous:
            windows.user32.SetForegroundWindow(previous)
        windows.bind(windows.user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)(*saved_cursor)
        Path(".test-artifacts").mkdir(exist_ok=True)
        Path(".test-artifacts/package-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
