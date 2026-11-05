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
        ImageGrab.grab(all_screens=True).save(args.output/(label+'.png'))
        rows = []
        for window in desktop.windows():
            if not window.is_visible():
                continue
            info = {'title': window.window_text(), 'pid': window.process_id(),
                    'handle': window.handle, 'enabled': window.is_enabled(), 'controls': []}
            try:
                for control in window.descendants()[:350]:
                    rectangle = control.rectangle()
                    info['controls'].append({'name': control.window_text(),
                        'type': control.element_info.control_type,
                        'automation_id': control.element_info.automation_id,
                        'enabled': control.is_enabled(), 'visible': control.is_visible(),
                        'rectangle': [rectangle.left, rectangle.top, rectangle.right, rectangle.bottom]})
            except Exception as error:
                info['inspection_error'] = str(error)
            rows.append(info)
        (args.output/(label+'.json')).write_text(json.dumps(rows, indent=2), encoding='utf-8')
        foreground = ctypes.windll.user32.GetForegroundWindow
        foreground.restype = ctypes.c_void_p
        report['steps'].append({'label': label, 'utc': datetime.now(timezone.utc).isoformat(),
                                'foreground_handle': foreground()})
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
        try:
            Desktop(backend='win32').window(handle=window.handle).set_focus()
        except Exception as error:
            report.setdefault('browser_focus_errors', []).append(str(error))
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
            if not args.url or not args.url.startswith('https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.4/'):
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

            def extract_button():
                for window in desktop.windows(class_name='CabinetWClass'):
                    if not window.is_visible():
                        continue
                    for control in window.descendants(control_type='Button'):
                        if control.window_text().lower().strip().startswith('extract all'):
                            return control
                return None

            button = wait_for(extract_button, 30, 'Explorer Extract all command unavailable')
            evidence('explorer-archive')
            button.click_input()
            wizard = desktop.window(title_re='Extract Compressed.*')
            wizard.wait('visible', timeout=15)
            edit = wizard.child_window(control_type='Edit', found_index=0)
            edit.set_edit_text(str(args.destination.resolve()))
            evidence('explorer-extract-dialog')
            wizard.child_window(title='Extract', control_type='Button').click_input()
            wait_for(lambda: (args.destination/'Mini Whiteboard/Mini Whiteboard.exe').is_file()
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
