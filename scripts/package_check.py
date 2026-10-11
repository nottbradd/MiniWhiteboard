"""Inspect and briefly launch only the built executable owned by this test."""
import ctypes as C
import argparse
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import time

import pefile
from mini_whiteboard import windows
from mini_whiteboard import APP_VERSION
from mini_whiteboard.geometry import Rect
from mini_whiteboard.settings import BORDER, SHADOW
from .build_support import verify_release_files


def main():
    windows.enable_dpi_awareness()
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=Path("dist/windows-v11/Mini Whiteboard/Mini Whiteboard.exe"))
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
    check('License notices are complete and unused Qt products are absent', True, notices)
    pe = pefile.PE(str(executable))
    check("Executable is Windows GUI subsystem (no console)", pe.OPTIONAL_HEADER.Subsystem == 2)
    version_strings = {}
    for group in pe.FileInfo:
        for entry in group:
            for table in getattr(entry, 'StringTable', ()):
                version_strings.update(table.entries)
    check('Executable product and file metadata are Version 1.1',
          version_strings.get(b'ProductVersion') == APP_VERSION.encode()
          and version_strings.get(b'FileVersion') == APP_VERSION.encode(),
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
          any("PerMonitorV2" in text and 'level="asInvoker"' in text and 'assemblyIdentity version="1.1.0.0"' in text for text in manifests))
    initial = windows.SingleInstance()
    if not initial.acquired:
        initial.close()
        raise SystemExit("Exit Mini Whiteboard before testing the packaged executable.")
    initial.close()
    process = subprocess.Popen([str(executable)], creationflags=subprocess.CREATE_NO_WINDOW)
    saved_cursor = windows.cursor_position()
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

        set_cursor(130, 150)
        post_thread(thread, windows.WM_HOTKEY, windows.CREATE_HOTKEY, 0)
        # A cold launch can still be loading Qt when the message is posted.
        # Keep the pointer at the first corner until the actual preview exists.
        # Empty board enumeration alone would also pass before the event ran.
        preview_ready = False
        for _ in range(50):
            boards = board_windows()
            preview_ready = not boards and bool(visible)
            if preview_ready or process.poll() is not None:
                break
            time.sleep(.1)
        check("Packaged first event creates preview only", preview_ready, visible)
        set_cursor(630, 490)
        post_thread(thread, windows.WM_HOTKEY, windows.CREATE_HOTKEY, 0)
        for _ in range(30):
            time.sleep(.1)
            boards = board_windows()
            if boards or process.poll() is not None:
                break
        check("Packaged second event creates a board with bundled canvas/shadow", len(boards) == 1, boards)
        post = windows.bind(user32, "PostMessageW", W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        time.sleep(.25)
        actual_rect = W.RECT()
        get_rect = windows.bind(user32,'GetWindowRect',W.BOOL,W.HWND,C.POINTER(W.RECT))
        if not get_rect(boards[0],C.byref(actual_rect)):
            raise RuntimeError('Cannot inspect the owned board bounds')
        dpi = windows.bind(user32,'GetDpiForWindow',W.UINT,W.HWND)(boards[0]) / 96
        shadow = round(SHADOW*dpi)
        paper = Rect(actual_rect.left+shadow,actual_rect.top+shadow,
                     actual_rect.right-actual_rect.left-2*shadow,
                     actual_rect.bottom-actual_rect.top-2*shadow)
        surface = windows.capture_rect(paper)
        width,height = surface.width(),surface.height()
        pixels = [surface.pixelColor(x,y).name() for x,y in
                  ((width//2,0),(0,height//2),(width-1,height//2),(width//2,height-1))]
        check('Packaged blank board has top line and no side or bottom outlines',
              pixels[0]==BORDER and all(p=='#ffffff' for p in pixels[1:]),
              {'pixels':pixels,'window_rect':[actual_rect.left,actual_rect.top,actual_rect.right,actual_rect.bottom]})
        post_thread(thread, windows.WM_HOTKEY, windows.CAPTURE_HOTKEY, 0)
        time.sleep(.3)
        board_windows()  # Refresh all visible windows owned by the packaged process.
        overlays = []
        for handle in visible:
            rect = W.RECT()
            if get_rect(handle,C.byref(rect)) and rect.right-rect.left > 1000:
                overlays.append(handle)
        check('Packaged capture overlay exists above the owned blank board', bool(overlays))
        point = (round(paper.x+paper.width*.2),round(paper.y+paper.height*.3))
        end = (round(paper.x+paper.width*.7),round(paper.y+paper.height*.7))
        set_cursor(*point)
        get_at = windows.bind(user32,'WindowFromPoint',W.HWND,W.POINT)
        check('Packaged screenshot drag starts on its owned overlay',
              windows.cursor_position()==point and get_at(W.POINT(*point)) in overlays,
              {'target':point,'cursor':windows.cursor_position(),
               'window':get_at(W.POINT(*point)),'overlays':overlays})
        mouse = windows.bind(user32,'mouse_event',None,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.c_size_t)
        mouse(0x0002,0,0,0,0)
        try:
            time.sleep(.1)
            set_cursor(*end)
            if windows.cursor_position()!=end:
                raise RuntimeError('Pointer moved during the owned capture test')
        finally:
            mouse(0x0004,0,0,0,0)
        time.sleep(.4)
        boards = board_windows()
        check('Packaged capture creates an image board using bundled background-cache module',len(boards)==2 and process.poll() is None)
        for handle in boards:
            post(handle, 0x0010, 0, 0)
        time.sleep(.2)
        check("Packaged board close leaves tray process running", not board_windows() and process.poll() is None)
        post_thread(thread, windows.WM_HOTKEY, windows.CAPTURE_HOTKEY, 0)
        time.sleep(.3)
        check('Packaged screenshot shortcut creates selection overlay only', not board_windows() and bool(visible))
        post_thread(thread, windows.WM_HOTKEY, windows.ESCAPE_HOTKEY, 0)
        time.sleep(.2)
        check('Packaged screenshot Escape removes overlay and keeps tray alive', not board_windows() and not visible and process.poll() is None)
    finally:
        # This test created the process without boards; terminate only that
        # exact subprocess. Normal application exit is via its tray action.
        process.terminate()
        process.wait(timeout=10)
        windows.bind(windows.user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)(*saved_cursor)
        Path(".test-artifacts").mkdir(exist_ok=True)
        Path(".test-artifacts/package-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
