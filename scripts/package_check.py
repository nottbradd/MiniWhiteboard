"""Inspect and briefly launch only the built executable owned by this test."""
import ctypes as C
import argparse
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import time
import sys

os.environ['QT_QPA_PLATFORM'] = 'windows'
import pefile
from PySide6.QtGui import QGuiApplication, QImage
from mini_whiteboard import windows
from mini_whiteboard import APP_VERSION
from mini_whiteboard.geometry import Rect
from mini_whiteboard.settings import BORDER, SHADOW
from .build_support import verify_release_files, verify_frozen_modules


def main():
    windows.enable_dpi_awareness()
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('verification/v136-review02/package'))
    parser.add_argument("--executable", type=Path, default=Path("dist/windows-v136-review02/Mini Whiteboard/Mini Whiteboard.exe"))
    parser.add_argument('--extended', action='store_true', help='Additional client-VM GUI routes; requires pywinauto.')
    parser.add_argument('--expected-version', default=APP_VERSION,
                        help='Recorded package version when checking an older published baseline.')
    args = parser.parse_args()
    if args.extended and (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        parser.error('Extended GUI checks require a disposable hosted runner.')
    if args.extended:
        sys.coinit_flags=2
        from pywinauto import Desktop  # Same STA as Qt, before its GUI/clipboard exists.
    app = QGuiApplication.instance() or QGuiApplication([])
    args.output.mkdir(parents=True,exist_ok=True)
    executable = args.executable.resolve()
    results = []

    def check(label, condition, detail=None):
        entry = {"check": label, "status": "PASS" if condition else "FAIL", "detail": detail}
        results.append(entry)
        print(json.dumps(entry), flush=True)
        (args.output/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        if not condition:
            raise AssertionError(label)

    notices = verify_release_files(executable.parent)
    check('License notices are complete and unused Qt products are absent', True, notices)
    check('Frozen executable contains no removed OCR modules', True, verify_frozen_modules(executable))
    pe = pefile.PE(str(executable))
    check("Executable is Windows GUI subsystem (no console)", pe.OPTIONAL_HEADER.Subsystem == 2)
    version_strings = {}
    for group in pe.FileInfo:
        for entry in group:
            for table in getattr(entry, 'StringTable', ()):
                version_strings.update(table.entries)
    parts = tuple(int(part) for part in args.expected_version.split('.'))
    numeric = (parts + (0, 0, 0, 0))[:4]
    fixed = pe.VS_FIXEDFILEINFO[0]
    check(f'Executable string and numeric metadata are Version {args.expected_version}',
          version_strings.get(b'ProductVersion') == args.expected_version.encode()
          and version_strings.get(b'FileVersion') == args.expected_version.encode()
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
          any("PerMonitorV2" in text and 'level="asInvoker"' in text and
              f'assemblyIdentity version="{".".join(map(str,numeric))}"' in text for text in manifests))
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
                # An unrelated foreground app can constrain the cursor. Place
                # only our disposable helper under the existing pointer rather
                # than changing global cursor confinement or clicking elsewhere.
                helper_rect=W.RECT();get_rect(identity['hwnd'],C.byref(helper_rect))
                pointer=windows.cursor_position()
                user32.SetWindowPos(identity['hwnd'], W.HWND(-1),
                    pointer[0]-(helper_rect.right-helper_rect.left)//2,
                    pointer[1]-(helper_rect.bottom-helper_rect.top)//2,0,0,0x0051)
                time.sleep(.2)
                get_at = windows.bind(user32, 'WindowFromPoint', W.HWND, W.POINT)
                owner = W.DWORD()
                pointer=windows.cursor_position()
                target=get_at(W.POINT(*pointer))
                get_pid(target, C.byref(owner))
                check('Packaged external activation target is owned', owner.value == identity['pid'],
                      {'pointer':pointer,'target':target,'actual_pid':owner.value,'wanted_pid':identity['pid'],
                       'helper':identity['hwnd']})
                mouse = windows.bind(user32, 'mouse_event', None, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.c_size_t)
                mouse(2, 0, 0, 0, 0)
                mouse(4, 0, 0, 0, 0)
                time.sleep(.2)
                user32.SetWindowPos(identity['hwnd'], W.HWND(-2),helper_rect.left,helper_rect.top,0,0,0x0011)
            check('Packaged test has external helper focus', foreground() == identity['hwnd'])

        focus_helper()
        key_event = windows.bind(user32, 'keybd_event', None, W.BYTE, W.BYTE, W.DWORD, C.c_size_t)

        def key(vk, up=False):
            key_event(vk, user32.MapVirtualKeyW(vk, 0), (2 if up else 0) | (1 if vk in (0x5B,0x5C,0xA5) else 0), 0)
            pressed.discard(vk) if up else pressed.add(vk)

        def begin(trigger, point):
            set_cursor(*point)
            for vk in (0x5B, 0xA4, 0xA0, ord(trigger)):
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
        key(0x5B, True)
        boards = wait_boards(1)
        check('Packaged modifier-first release creates one board', len(boards) == 1)
        key(0xA4, True)
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
            # This process owns a Qt clipboard in the extended check. Service
            # its delayed-render requests while the frozen editor pastes; a
            # sleeping clipboard owner can block the other app's message loop.
            deadline=time.monotonic()+.08
            while time.monotonic()<deadline:
                app.processEvents()
                time.sleep(.005)

        def dark_content():
            # A proxy editor's antialiased blue-gray frame is lighter than ink.
            # Count it too: a blank editor must stay observable when its caret
            # blinks off, and dismissal must remove both its frame and its ink.
            area = Rect(round(paper.x+14*dpi), round(paper.y+40*dpi),
                        round(paper.width-28*dpi), round(paper.height-105*dpi))
            image = windows.capture_rect(area)
            rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
            pixels = rgba.constBits()
            return sum(1 for r,g,b in zip(pixels[0::4],pixels[1::4],pixels[2::4])
                       if max(r,g,b)+min(r,g,b) < 299 or (b-r > 5 and r < 245))

        text_key(ord('T'))
        click_paper(50, 80)
        # Observe native composition within a fixed budget instead of treating
        # one GDI snapshot as a synchronous client-paint acknowledgement. The
        # same missed first snapshot reproduces on the preserved public build.
        editor_observation_started=time.perf_counter()
        first_editor_pixels = dark_content()
        while first_editor_pixels<=5 and time.perf_counter()-editor_observation_started<.25:
            time.sleep(.01)
            first_editor_pixels=dark_content()
        editor_observation_ms=(time.perf_counter()-editor_observation_started)*1000
        windows.capture_rect(paper).save(str(args.output/'first-editor-observation.png'))
        if first_editor_pixels <= 5:
            windows.capture_rect(paper).save(str(args.output/'first-editor-observation.png'))
            time.sleep(.5)
            windows.capture_rect(paper).save(str(args.output/'settled-editor-observation.png'))
            print(json.dumps({'first_editor_pixels':first_editor_pixels,'settled_editor_pixels':dark_content(),
                              'modifiers':{name:bool(user32.GetAsyncKeyState(vk)&0x8000) for name,vk in
                                           (('Control',0x11),('Alt',0x12),('Shift',0x10),('W',ord('W')))},
                              'foreground':foreground(),'board':owned_board}),flush=True)
        check('Frozen native Text click visibly opens an editor',
              first_editor_pixels>5 and editor_observation_ms<=250,
              {'pixels':first_editor_pixels,'observation_ms':editor_observation_ms,'poll_budget_ms':250})
        blink_samples = []
        for _ in range(4):
            time.sleep(.18)
            blink_samples.append(dark_content())
        check('Frozen editor remains observable across caret blinking',min(blink_samples) > 5,blink_samples)
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
        begin('Q', point)
        check('Packaged screenshot hold starts only a preview', len(board_windows()) == 1 and bool(preview_windows()))
        set_cursor(*end)
        time.sleep(.15)
        key(ord('Q'), True)
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
        begin('Q', (250,330))
        key(0x1b)
        time.sleep(.1)
        key(0x1b, True)
        for _ in range(10):
            key(ord('Q'))
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
        if args.extended:
            from pywinauto import Desktop
            owned_board = board_windows()[0]
            desktop = Desktop(backend='uia')
            text_key(ord('T'))
            click_paper(50, 65)
            for character in 'AVE12345':
                text_key(ord(character))
            text_key(ord('A'), ctrl=True)
            text_key(ord('C'), ctrl=True)
            app.processEvents()
            check('Client editor receives tool letters and digits exclusively', app.clipboard().text() == 'ave12345')
            expected_text=('Mini Whiteboard keeps this sentence inside the textbox. '
                           'A V E 12345 remain text while editing this second sentence.')
            app.clipboard().setText(expected_text)
            app.processEvents()
            windows.capture_rect(paper).save(str(args.output/'client-before-paste.png'))
            text_key(ord('V'), ctrl=True)
            windows.capture_rect(paper).save(str(args.output/'client-after-paste.png'))
            text_key(ord('A'),ctrl=True)
            text_key(ord('C'),ctrl=True)
            app.processEvents()
            check('Client editor receives and copies back the complete replacement text',app.clipboard().text()==expected_text,
                  {'expected_characters':len(expected_text),'actual_characters':len(app.clipboard().text())})
            text_key(0x0D, ctrl=True)
            windows.capture_rect(paper).save(str(args.output/'client-after-text-finish.png'))
            text_key(0x1B)

            def ink_bounds():
                area = Rect(round(paper.x+16*dpi), round(paper.y+38*dpi),
                            round(paper.width-32*dpi), round(paper.height-90*dpi))
                shot = windows.capture_rect(area).convertToFormat(QImage.Format.Format_RGBA8888)
                data = shot.constBits()
                ink = [i//4 for i in range(0, len(data), 4) if max(data[i:i+3]) < 100]
                if not ink:
                    return None
                xs = [v % shot.width() for v in ink]; ys = [v // shot.width() for v in ink]
                return (area.x+min(xs), area.y+min(ys), area.x+max(xs), area.y+max(ys))

            before = ink_bounds()
            windows.capture_rect(paper).save(str(args.output/'client-wrapped-text.png'))
            check('Client committed text visibly wraps across multiple lines',
                  before is not None and before[3]-before[1] > 40*dpi, before)
            text_key(ord('A'))
            text_key(ord('A'), ctrl=True)
            centre = (round((before[0]+before[2])/2), round((before[1]+before[3])/2))
            delta = (round(30*dpi), round(20*dpi))
            set_cursor(*centre)
            check('Client selection drag targets its owned board',
                  ancestor(get_at(W.POINT(*centre)), 2) == owned_board)
            mouse(2, 0, 0, 0, 0)
            try:
                for step in range(1, 7):
                    set_cursor(centre[0]+round(delta[0]*step/6), centre[1]+round(delta[1]*step/6))
                    time.sleep(.025)
            finally:
                mouse(4, 0, 0, 0, 0)
            time.sleep(.15)
            text_key(0x1B)
            moved = ink_bounds()
            expected = tuple(value+delta[i % 2] for i,value in enumerate(before))
            check('Client selection movement translates the visible text',
                  moved is not None and all(abs(a-b) <= 1 for a,b in zip(moved, expected)),
                  {'before': before, 'after': moved, 'expected': expected})
            text_key(ord('Z'), ctrl=True)
            text_key(0x1B)
            check('Client movement undo restores the original visible geometry', ink_bounds() == before)
            text_key(ord('Y'), ctrl=True)
            text_key(0x1B)
            check('Client movement redo restores the translated visible geometry', ink_bounds() == moved)
            focus_helper()

            def hide_restore():
                for vk in (0xA2, 0xA4, 0xA0, ord('H')):
                    key(vk)
                time.sleep(.15)
                release_all()

            hide_restore()
            check('Client Hide All removes the board while retaining the process', not board_windows() and process.poll() is None)
            hide_restore()
            check('Client Restore All returns the board without taking external focus',
                  len(wait_boards(1)) == 1 and foreground() == identity['hwnd'])
            board_ui = desktop.window(handle=owned_board)
            board_ui.child_window(title='Minimise whiteboard', control_type='Button').click_input()
            time.sleep(.2)
            check('Client minimise control hides the board without deleting it', not board_windows() and process.poll() is None)

            def tray_menu():
                tray = desktop.window(class_name='Shell_TrayWnd')
                icons = [b for b in tray.descendants(control_type='Button') if b.window_text().startswith('Mini Whiteboard')]
                if not icons:
                    overflow = [b for b in tray.descendants(control_type='Button')
                                if b.window_text() in ('Show hidden icons', 'Hidden icon menu')]
                    if not overflow:
                        raise RuntimeError('Tray overflow control not exposed; saved GUI evidence is required')
                    overflow[0].click_input()
                    time.sleep(.2)
                    icons = [b for w in desktop.windows() if w.is_visible()
                             for b in w.descendants(control_type='Button') if b.window_text().startswith('Mini Whiteboard')]
                if len(icons) != 1:
                    raise RuntimeError('Cannot uniquely locate the test application tray icon')
                icons[0].click_input(button='right')
                time.sleep(.15)

            def menu_item(prefix):
                items = [c for w in desktop.windows(process=process.pid) if w.is_visible()
                         for c in w.descendants(control_type='MenuItem')
                         if c.window_text().startswith(prefix) and c.is_visible()]
                if len(items) != 1:
                    raise RuntimeError('Menu item not uniquely visible: '+prefix)
                return items[0]

            tray_menu()
            menu_item('Whiteboards').move_mouse_input()
            time.sleep(.3)
            menu_item('Whiteboard ').click_input()
            check('Client Whiteboards tray menu restores the minimised board', len(wait_boards(1)) == 1)
            tray_menu()
            menu_item('Settings').move_mouse_input()
            time.sleep(.3)
            menu_item('Hotkeys').click_input()
            dialog = desktop.window(title='Mini Whiteboard · Hotkeys', process=process.pid)
            dialog.wait('visible', timeout=5)
            check('Client real tray settings route opens all three hotkey rows',
                  len(dialog.descendants(control_type='ComboBox')) == 3)
            windows.capture_rect(Rect(0, 0, 1024, 768)).save(str(args.output/'client-hotkey-settings.png'))
            combo = dialog.child_window(title='Create whiteboard key', control_type='ComboBox')
            combo.select('F8')
            dialog.child_window(title='Apply', control_type='Button').click_input()
            dialog.wait_not('visible', timeout=5)
            from PySide6.QtCore import QSettings
            stored = QSettings('MiniWhiteboard', 'MiniWhiteboard')
            stored.sync()
            check('Client hotkey Apply saves the GUI-selected trigger',
                  json.loads(stored.value('shortcuts/custom_windows'))['bindings'][0]['key'] == 'F8')
            board_ui.child_window(title='Delete whiteboard', control_type='Button').click_input()
            time.sleep(.2)
            check('Client close control removes the board and retains the tray', not board_windows() and process.poll() is None)
            tray_menu()
            menu_item('Exit Mini Whiteboard').click_input()
            process.wait(timeout=5)
            check('Client tray Exit closes the application normally', process.returncode == 0)
    finally:
        # This test created the process without boards; terminate only that
        # exact subprocess. Normal application exit is via its tray action.
        for vk in tuple(pressed):
            key_event(vk, user32.MapVirtualKeyW(vk, 0), 2 | (1 if vk in (0x5B,0x5C,0xA5) else 0), 0)
        if args.extended:
            try:
                windows.capture_rect(Rect(0, 0, 1024, 768)).save(str(args.output/'client-final-desktop.png'))
                from pywinauto import Desktop
                ui = [{'title':w.window_text(), 'pid':w.process_id(), 'controls':[
                    {'name':c.window_text(), 'type':c.element_info.control_type}
                    for c in w.descendants()[:350]]} for w in Desktop(backend='uia').windows() if w.is_visible()]
                (args.output/'client-final-ui.json').write_text(json.dumps(ui, indent=2), encoding='utf-8')
            except Exception as error:
                print(json.dumps({'gui_evidence_error': str(error)}), flush=True)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        if helper is not None:
            helper.terminate()
            helper.wait(timeout=10)
        if previous:
            windows.user32.SetForegroundWindow(previous)
        windows.bind(windows.user32, "SetCursorPos", W.BOOL, C.c_int, C.c_int)(*saved_cursor)
        (args.output/'checks.json').write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    from .native_preferences import compatibility_preferences
    with compatibility_preferences():
        raise SystemExit(main())
