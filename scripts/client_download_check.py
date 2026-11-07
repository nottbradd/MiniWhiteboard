"""Drive ordinary Edge download and Explorer extraction in a disposable client VM.

No WebDriver security switches, HTTP download fallback, archive library,
download-marker changes, warning dismissal or application launch is used here.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Requires a disposable GitHub-hosted runner.')
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('prepare', 'download', 'extract'))
    parser.add_argument('--path', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--url')
    parser.add_argument('--expected-entry', default='Mini Whiteboard/Mini Whiteboard.exe')
    args = parser.parse_args()
    from PIL import ImageGrab
    from pywinauto import Desktop, mouse

    args.output.mkdir(parents=True, exist_ok=True)
    desktop = Desktop(backend='uia')
    report = {'operation': args.operation, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'security_warning_dismissed': False, 'origin_marker_changed': False, 'steps': []}

    def save():
        (args.output/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

    def evidence(label):
        # Commit the stage and pixels before any accessibility provider call.
        # UIA enumeration itself can hang on the hosted first-run desktop.
        report['steps'].append({'label': label, 'utc': datetime.now(timezone.utc).isoformat()})
        save()
        ImageGrab.grab(all_screens=True).save(args.output/(label+'.png'))
        rows = []
        from ctypes import wintypes
        user = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        @callback_type
        def visit(hwnd, _):
            if user.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(256)
                user.GetWindowTextW(hwnd, title, len(title))
                pid, rect = wintypes.DWORD(), wintypes.RECT()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                user.GetWindowRect(hwnd, ctypes.byref(rect))
                rows.append({'title': title.value, 'pid': pid.value, 'handle': int(hwnd),
                             'rectangle': [rect.left, rect.top, rect.right, rect.bottom]})
            return True
        user.EnumWindows(visit, 0)
        (args.output/(label+'.json')).write_text(json.dumps(rows, indent=2), encoding='utf-8')
        foreground = ctypes.windll.user32.GetForegroundWindow
        foreground.restype = ctypes.c_void_p
        report['steps'][-1]['foreground_handle'] = foreground()
        save()

    def wait_for(predicate, seconds, description):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.25)
        raise TimeoutError(description)

    def activate_browser(window):
        # UIA SetFocus can focus an element without bringing Edge in front of
        # the shell. Use its native top-level window, then confirm ownership.
        foreground = ctypes.windll.user32.GetForegroundWindow
        foreground.restype = ctypes.c_void_p
        # Avoid pywinauto's AttachThreadInput/WaitForInputIdle focus path: a
        # stalled GUI thread can block it beyond the operation deadline.
        from ctypes import wintypes
        user = ctypes.windll.user32
        user.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
        user.SetForegroundWindow.argtypes = [wintypes.HWND]
        user.ShowWindowAsync(window.handle, 9)
        user.SetForegroundWindow(window.handle)
        evidence('browser-focus-attempt')
        if foreground() != window.handle:
            # Normal title-bar click, only when the point really belongs to
            # this browser. Never click through an intervening dialog/warning.
            from ctypes import wintypes
            hit = ctypes.windll.user32.WindowFromPoint
            hit.argtypes = [wintypes.POINT]
            hit.restype = ctypes.c_void_p
            ancestor = ctypes.windll.user32.GetAncestor
            ancestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            ancestor.restype = ctypes.c_void_p
            rect = window.rectangle()
            point = (rect.left+(rect.right-rect.left)//2, rect.top+18)
            if ancestor(hit(wintypes.POINT(*point)), 2) != window.handle:
                raise RuntimeError('Browser title bar is occluded; no click sent')
            mouse.click(coords=point)
        wait_for(lambda: foreground() == window.handle, 3,
                 'Browser does not own foreground; no keys were sent')

    browser = None
    try:
        save()
        if args.operation == 'prepare':
            evidence('client-initial-desktop')
            # The hosted Windows 11 image can show a non-binding first-run
            # privacy page. Decline optional telemetry in this disposable VM;
            # never dismiss a sign-in, license, permission or security warning.
            for window in desktop.windows(title='Microsoft account'):
                labels = [c.window_text() for c in window.descendants()]
                if 'Choose privacy settings for your device' not in labels:
                    continue
                for control in window.descendants(control_type='Button'):
                    if control.window_text().startswith(('Get location-based experiences',
                            'Send optional inking and typing diagnostic data',
                            'Let Windows use info about your device')):
                        before = control.window_text()
                        control.invoke()
                        wait_for(lambda: control.window_text() != before, 5, 'Privacy choice did not change')
                evidence('client-optional-privacy-declined')
                spec = desktop.window(handle=window.handle)
                accept = spec.child_window(auto_id='OobeSettingsAcceptButton', control_type='Button')
                # CloudExperienceHost removes its UIA provider when this page
                # closes. Observe the native handle instead of querying a stale
                # provider, which can raise EVENT_E_ALL_SUBSCRIBERS_FAILED.
                visible = ctypes.windll.user32.IsWindowVisible
                visible.argtypes = [ctypes.c_void_p]
                visible.restype = ctypes.c_bool
                spec.set_focus()
                foreground = ctypes.windll.user32.GetForegroundWindow
                foreground.restype = ctypes.c_void_p
                if foreground() != window.handle:
                    raise RuntimeError('Privacy page does not own foreground; no native input sent')
                evidence('client-privacy-before-confirmation')
                accept.click_input()
                time.sleep(2)
                evidence('client-privacy-after-click')
                if visible(window.handle):
                    # A normal keyboard activation provides a separate input
                    # observation. Never close the process or bypass the page.
                    accept.set_focus()
                    if foreground() != window.handle or not accept.has_keyboard_focus():
                        raise RuntimeError('Privacy confirmation lacks keyboard focus; no key sent')
                    accept.type_keys('{SPACE}')
                    evidence('client-privacy-after-space')
                wait_for(lambda: not visible(window.handle), 20,
                         'Privacy page did not close')
            evidence('client-desktop-ready')
            report['result'] = 'PASS for client desktop preparation only'
            return
        if args.operation == 'download':
            fixture_url = bool(args.url and re.fullmatch(
                r'https://raw\.githubusercontent\.com/nottbradd/MiniWhiteboard/[0-9a-f]{40}/tests/fixtures/client-preflight\.zip', args.url))
            if not args.url or not (fixture_url or args.url.startswith('https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.4/')):
                raise ValueError('Only the recorded public release URL is allowed')
            args.destination.mkdir(exist_ok=True, parents=True)
            if args.path.exists():
                raise FileExistsError('Browser download requires a fresh destination')
            profile = args.output/'edge-profile'
            (profile/'Default').mkdir(parents=True)
            # Only the download destination is configured. Browser protection
            # and download-origin handling retain their normal settings.
            (profile/'Default/Preferences').write_text(json.dumps({'download': {
                'default_directory': str(args.destination.resolve())}}), encoding='utf-8')
            edge = next((p for p in (Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')),
                                    Path(os.environ['ProgramFiles']))
                         if (p/'Microsoft/Edge/Application/msedge.exe').is_file()), None)
            if edge is None:
                raise FileNotFoundError('Microsoft Edge is not installed')
            command = [str(edge/'Microsoft/Edge/Application/msedge.exe'),
                       '--user-data-dir='+str(profile.resolve()), '--no-first-run',
                       '--no-default-browser-check', '--force-renderer-accessibility',
                       'https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3.4']
            browser = subprocess.Popen(command)
            report['browser_command'] = command
            window = desktop.window(process=browser.pid, class_name='Chrome_WidgetWin_1')
            window.wait('visible', timeout=30)
            activate_browser(window)
            time.sleep(2)
            evidence('release-page')
            foreground = ctypes.windll.user32.GetForegroundWindow
            foreground.restype = ctypes.c_void_p
            if foreground() != window.handle:
                raise RuntimeError('Browser does not own foreground; no keys were sent')
            # The browser handles a URL entered through its real address bar.
            window.type_keys('^l')
            window.type_keys(args.url, with_spaces=True, pause=.001)
            window.type_keys('{ENTER}')
            try:
                wait_for(lambda: args.path.is_file() and not list(args.destination.glob('*.crdownload')),
                         90, 'Browser download incomplete or blocked; no warning was bypassed')
            finally:
                activate_browser(window)
                if foreground() == window.handle:
                    window.type_keys('^j')
                time.sleep(1)
                evidence('downloads')
            report['bytes'] = args.path.stat().st_size
            report['method'] = 'Visible Microsoft Edge; real address-bar navigation'
            # Close only the isolated browser profile opened by this test.
            window.close()
        else:
            if args.destination.exists():
                raise FileExistsError('Explorer extraction requires a fresh destination')
            subprocess.Popen([str(Path(os.environ['WINDIR'])/'explorer.exe'), str(args.path.resolve())])
            archive_window = wait_for(lambda: next((w for w in desktop.windows(class_name='CabinetWClass')
                if w.is_visible() and args.path.stem.lower() in w.window_text().lower()),None),
                20,'Archive Explorer window unavailable')
            # The earlier run invoked an offscreen overflow command and never
            # opened a wizard. Maximize the owned Explorer and use its visible
            # command instead; do not replace normal extraction with an API.
            from ctypes import wintypes
            ctypes.windll.user32.ShowWindowAsync.argtypes=[wintypes.HWND,ctypes.c_int]
            activate_browser(archive_window)
            # Activation restores the window. Maximize afterwards and verify
            # the result, rather than assuming the earlier request survived.
            ctypes.windll.user32.ShowWindowAsync(archive_window.handle,3)
            ctypes.windll.user32.IsZoomed.argtypes=[wintypes.HWND]
            wait_for(lambda: ctypes.windll.user32.IsZoomed(archive_window.handle),
                     3,'Explorer did not maximize')
            time.sleep(1)
            evidence('explorer-maximized')
            report['explorer_buttons']=[dict(name=c.window_text(),visible=c.is_visible())
                for c in archive_window.descendants(control_type='Button')]
            save()

            def extract_button():
                for window in desktop.windows(class_name='CabinetWClass'):
                    if not window.is_visible():
                        continue
                    for control in window.descendants(control_type='Button'):
                        if control.window_text().lower().strip().startswith('extract all'):
                            return control
                return None

            button = wait_for(extract_button, 30, 'Explorer Extract all command unavailable')
            rectangle=button.rectangle()
            report['extract_action']={'name':button.window_text(),'visible':button.is_visible(),
                                      'enabled':button.is_enabled(),
                                      'rectangle':[rectangle.left,rectangle.top,rectangle.right,rectangle.bottom]}
            evidence('explorer-archive')
            outer=archive_window.rectangle()
            if not (button.is_visible() and outer.left <= rectangle.left < rectangle.right <= outer.right
                    and outer.top <= rectangle.top < rectangle.bottom <= outer.bottom):
                # One bounded normal overflow-menu attempt, with evidence before
                # input. An invisible command is not a successful invocation.
                more=next((c for c in archive_window.descendants(control_type='Button')
                           if c.is_visible() and c.window_text().lower() in ('see more','more')),None)
                if more is None:
                    raise RuntimeError('Extract all is outside the visible Explorer; no reachable overflow command')
                more.click_input()
                evidence('explorer-overflow')
                button=wait_for(lambda: next((c for w in desktop.windows() if w.is_visible()
                    for c in w.descendants(control_type='MenuItem')
                    if c.is_visible() and c.window_text().lower().startswith('extract all')),None),
                    5,'Visible Extract all overflow item unavailable')
            button.click_input()
            evidence('explorer-extract-invoked')
            wizard = desktop.window(title_re='Extract.*')
            wizard.wait('visible', timeout=15)
            edit = wizard.child_window(control_type='Edit', found_index=0)
            edit.set_edit_text(str(args.destination.resolve()))
            evidence('explorer-extract-dialog')
            wizard.child_window(title='Extract', control_type='Button').click_input()
            expected = Path(args.expected_entry)
            if expected.is_absolute() or '..' in expected.parts:
                raise ValueError('Expected extracted entry must stay inside the destination')
            wait_for(lambda: (args.destination/expected).is_file()
                     and not wizard.exists(timeout=.1), 90, 'Explorer extraction incomplete or blocked')
            evidence('explorer-extracted')
            report['method'] = 'Explorer compressed-folder Extract all dialog'
        report['result'] = 'PASS for this operation only'
    except Exception as error:
        report['result'] = 'BLOCKED'
        report['error'] = str(error)
        try:
            evidence('failure')
        except Exception as collection_error:
            report['evidence_error'] = str(collection_error)
        raise
    finally:
        report['ended_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
