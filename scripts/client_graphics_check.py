"""Read graphics policy and observe frozen-source Glass; not binary acceptance."""
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Disposable hosted client only')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    report=dict(scope='Read-only Windows graphics state and frozen-source rendering diagnosis; not final-executable acceptance',
                utc=datetime.now(timezone.utc).isoformat(),observations=[])
    def save():
        (args.output/'graphics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    from scripts.client_glass_diagnostics import d3d11_devices,instrument_source,window_state,wait_visible_window
    report['d3d11']=d3d11_devices()
    instrument_source(report,save)
    query="@{video=Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,VideoProcessor,Status,AdapterCompatibility; session=$env:SESSIONNAME; os=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture} | ConvertTo-Json -Depth 5"
    result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',query],capture_output=True,text=True,timeout=15)
    report['system']=json.loads(result.stdout) if result.returncode==0 else dict(error=result.stderr)
    os.environ['QT_QPA_PLATFORM']='windows'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from mini_whiteboard import windows as n
    from mini_whiteboard.board import BoardWindow
    from mini_whiteboard.snapping import SnapPreferences
    from mini_whiteboard.platform.windows.appearance import display_policy
    from scripts.native_preferences import compatibility_preferences
    from scripts.client_environment_check import dismiss_wsl_prompt
    dismiss_wsl_prompt()
    n.enable_dpi_awareness();app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    report['display_policy']=vars(display_policy())
    report['remote_session_metric']=bool(C.windll.user32.GetSystemMetrics(0x1000))
    enabled=W.BOOL()
    status=C.windll.dwmapi.DwmIsCompositionEnabled(C.byref(enabled))
    report['dwm_composition']=dict(hresult=status,enabled=bool(enabled.value))
    class Power(C.Structure):
        _fields_=[('ac',W.BYTE),('battery_flag',W.BYTE),('battery_percent',W.BYTE),
                  ('system_status',W.BYTE),('battery_seconds',W.DWORD),('full_seconds',W.DWORD)]
    power=Power()
    if C.windll.kernel32.GetSystemPowerStatus(C.byref(power)):
        report['power']={name:getattr(power,name) for name,_ in Power._fields_}
    errors=[];sys.excepthook=lambda kind,value,tb:errors.append(repr(value))
    report['callback_errors']=errors
    save()
    with compatibility_preferences():
        prefs=SnapPreferences();prefs.set_theme('Glass')
        for background in ('light','busy'):
            child=None;board=None;manager=None
            try:
                child=subprocess.Popen([sys.executable,'-m','scripts.floating_tools_check','--native',
                    '--background-child','--background-kind',background,'--output',str(args.output/background)],
                    creationflags=subprocess.CREATE_NO_WINDOW)
                ready=wait_visible_window(child.pid,app.processEvents,background_kind=background)
                screen=n.monitors()[0].rect
                before=n.capture_rect(screen);before.save(str(args.output/(background+'-before.png')))
                board=BoardWindow('Source-only Glass diagnosis',prefs)
                board.setGeometry(180,160,600,400)
                board.show();board.activateWindow();board.canvas.setFocus()
                QTest.qWait(900)
                image=n.capture_rect(screen);image.save(str(args.output/(background+'-source-glass.png')))
                host=getattr(board,'_backdrop',None)
                points=((280,300),(420,300),(650,450))
                report['observations'].append(dict(background=background,background_readiness=ready,native_glass=board.native_glass,
                    host=host.handle if host else None,composition_dimensions=host.effect.dimensions if host and host.effect else None,
                    foreground=int(C.windll.user32.GetForegroundWindow()),board=int(board.winId()),
                    points=points,before=[before.pixelColor(x,y).getRgb() for x,y in points],
                    after=[image.pixelColor(x,y).getRgb() for x,y in points]))
                report['observations'][-1]['native_windows']=window_state(os.getpid())
                save()
                board.close();QTest.qWait(80)
                # Exercise the existing source fallback explicitly. This is
                # fault injection, not evidence that this VM selected fallback
                # automatically (its native host reports success but is grey).
                from unittest.mock import patch
                from mini_whiteboard.document import Text
                from mini_whiteboard.floating_tools import FloatingTools
                with patch('mini_whiteboard.platform.windows.appearance.capable',return_value=False):
                    prefs.set_floating_tools(True)
                    manager=FloatingTools(app,prefs)
                    board=BoardWindow('Source-only forced fallback diagnosis',prefs)
                    manager.add_board(board)
                    board.setGeometry(180,160,600,400)
                    board.canvas.document.commit((Text((40,250),'Readable fallback · A V E 12345',size=16),),'Diagnostic text')
                    board.show();board.activateWindow();board.canvas.setFocus();QTest.qWait(400)
                    manager.open_options('Draw');QTest.qWait(250)
                    surfaces=[board,manager.palette,manager.options]
                    if any(w is None or not w.isVisible() or w.native_glass for w in surfaces):
                        raise AssertionError('Forced fallback board, toolbar and popover did not become visible')
                    n.capture_rect(screen).save(str(args.output/(background+'-source-forced-fallback.png')))
                    report.setdefault('forced_fallback',[]).append(dict(background=background,
                        scope='Source-only capable=False injection; no OS setting or frozen payload changed',
                        surfaces=[dict(title=w.windowTitle(),native_glass=w.native_glass,
                                       host=bool(getattr(w,'_backdrop',None))) for w in surfaces],
                        native_windows=window_state(os.getpid())))
                    save()
            finally:
                if manager is not None:manager.close();prefs.set_floating_tools(False)
                if board is not None: board.close();QTest.qWait(80)
                if child is not None and child.poll() is None: child.terminate();child.wait(5)
    report['ended_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':
    main()
