"""Read Windows Security's Protection history UI on the owned disposable client."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Disposable hosted client only')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    from PIL import ImageGrab
    from pywinauto import Desktop
    from scripts.client_wizard_check import native_windows
    report=dict(started_utc=datetime.now(timezone.utc).isoformat(),result='INCOMPLETE',steps=[],
                scope='Read-only Windows Security navigation; no threat action, protection change or history clearing')
    def save(phase,controls=None):
        report['steps'].append(dict(phase=phase,utc=datetime.now(timezone.utc).isoformat(),
                                   windows=native_windows(),controls=controls))
        (args.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        ImageGrab.grab(all_screens=True).save(args.output/(str(len(report['steps']))+'-'+phase+'.png'))
    try:
        save('before-open')
        query="Get-StartApps | Where-Object Name -eq 'Windows Security' | Select-Object Name,AppID | ConvertTo-Json -Compress"
        found=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',query],capture_output=True,text=True,timeout=10)
        app=json.loads(found.stdout)
        if not isinstance(app,dict) or not app.get('AppID'):raise RuntimeError('Windows Security start entry is not unique')
        report['app']=app
        os.startfile('shell:AppsFolder\\'+app['AppID'])
        desktop=Desktop(backend='uia');deadline=time.monotonic()+40;visited=set();previous=None
        while time.monotonic()<deadline:
            windows=[w for w in desktop.windows() if w.is_visible() and w.window_text()=='Windows Security']
            if len(windows)!=1:time.sleep(.2);continue
            controls=[c for c in windows[0].descendants() if c.is_visible()]
            rows=[dict(name=c.window_text(),type=c.element_info.control_type) for c in controls]
            fingerprint=json.dumps(rows)
            if fingerprint!=previous:save('security-page',rows);previous=fingerprint
            names=[c.window_text().strip() for c in controls]
            if 'No recent actions' in names:
                report.update(result='PASS: Protection history reports No recent actions',no_recent_actions=True)
                save('history-empty',rows);return 0
            # The previous Virus & threat protection page contains a hyperlink
            # and child Text named Protection history. Clicking it does not
            # synchronously complete navigation. Do not accept that old page
            # as the history page while its current-threat controls remain.
            history_heading=any(c.element_info.control_type=='Text' and
                c.window_text().strip()=='Protection history' and
                c.parent().element_info.control_type!='Hyperlink' for c in controls)
            if ('Protection history' in visited and history_heading and
                    'Quick scan' not in names and 'Virus & threat protection status' not in names):
                report.update(result='Protection history opened; inspect retained entries',no_recent_actions=False)
                save('history-entries',rows);return 0
            for name in ('Protection history','Virus & threat protection'):
                if name in visited:continue
                choices=[c for c in controls if c.window_text().strip()==name and
                         c.element_info.control_type in ('Button','Hyperlink','ListItem','TreeItem') and c.is_enabled()]
                if len(choices)==1:
                    choices[0].click_input();visited.add(name);break
            time.sleep(.25)
        raise TimeoutError('Protection history UI was not observed within its deadline')
    except Exception as error:
        report.update(result='INCOMPLETE',error=repr(error));save('failure');return 1
    finally:
        report['ended_utc']=datetime.now(timezone.utc).isoformat()
        (args.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
