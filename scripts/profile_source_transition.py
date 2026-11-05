"""Time unmodified source callbacks in a disposable VM, never release acceptance.

The separate native-input driver still owns the input sequence and assertions.
Only method names and timing are recorded; no text, captures or user input.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Requires a disposable GitHub-hosted runner.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from PySide6.QtCore import qVersion
    from mini_whiteboard.app import main as application_main
    from mini_whiteboard import windows as native

    with args.output.open('w', encoding='utf-8', buffering=1) as output:
        def record(event, **values):
            output.write(json.dumps({'event': event, 'unix_ns': time.time_ns(),
                                     'monotonic_ns': time.perf_counter_ns(), **values})+'\n')

        record('environment', python=sys.version, qt=qVersion(), source=os.environ.get('GITHUB_SHA'),
               purpose='Source timing comparison only; this does not execute or accept the published EXE.')
        tracked = {'WhiteboardApplication.notify', 'ScreenshotController.start',
                   'PreviewOverlay.__init__', 'PreviewOverlay.showEvent',
                   'PreviewOverlay.paintEvent', 'PlacementController.release', 'PlacementController.start_at',
                   'HoldTracker.activate', 'HoldTracker.release', 'PlacementController.cancel',
                   'ScreenshotController.release', 'ScreenshotController.cancel',
                   'ScreenshotController.capture_pending', 'ScreenshotController.complete',
                   'ScreenshotController.deliver', 'NativeHotkeys.enable_escape',
                   'WindowsDesktop.display_policy', 'WindowsDesktop.displays',
                   'WindowsDesktop.set_window_rect', 'QtDesktop.configure_overlay',
                   'PreviewOverlay.sync_material', 'BackdropHost.__init__', 'BackdropHost.close',
                   'RoundedBackdrop.__init__', 'RoundedBackdrop.close', 'WindowsCapture.prepare',
                   'WindowsCapture.capture_region'}
        active = {}

        def profile(frame, event, _arg):
            method = frame.f_code.co_qualname
            if event in ('c_call','c_return','c_exception') and method in tracked:
                name = getattr(_arg,'__qualname__',getattr(_arg,'__name__','C call'))
                key = (id(frame),name)
                if event == 'c_call':
                    active[key]=time.perf_counter_ns()
                    record('c_call',method=method,callee=name)
                elif (entered := active.pop(key,None)) is not None:
                    record(event,method=method,callee=name,duration_ms=(time.perf_counter_ns()-entered)/1e6)
                return
            if event not in ('call', 'return'):
                return
            key = id(frame)
            if event == 'return':
                entered = active.pop(key, None)
                if entered:
                    record('return', method=method, duration_ms=(time.perf_counter_ns()-entered)/1e6)
                return
            if method not in tracked:
                if method != 'NativeHotkeys.nativeEventFilter':
                    return
                if bytes(frame.f_locals['event_type']) not in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
                    return
                message = native.W.MSG.from_address(int(frame.f_locals['message']))
                if message.message != native.WM_HOTKEY:
                    return
            active[key] = time.perf_counter_ns()
            detail={}
            instance=frame.f_locals.get('self')
            if method == 'HoldTracker.activate':
                detail={'identifier':frame.f_locals.get('identifier'),'previous_active':instance.active,'blocked':list(instance.blocked)}
            elif method == 'NativeHotkeys.nativeEventFilter':
                detail={'identifier':int(message.wParam),'message_tick':int(message.time)}
            elif method.startswith(('PlacementController.','ScreenshotController.')):
                detail={'owner':instance.session.owner,'anchor':str(getattr(instance,'anchor',None))}
            record('call', method=method, **detail)

        def garbage_collection(phase, info):
            record('gc-'+phase, **info)
        gc.callbacks.append(garbage_collection)
        sys.setprofile(profile)
        try:
            return application_main()
        finally:
            sys.setprofile(None)
            gc.callbacks.remove(garbage_collection)


if __name__ == '__main__':
    raise SystemExit(main())
