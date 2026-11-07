"""Query one owned frozen Qt window from a separate UIA apartment, without Qt."""
import argparse
import json
import os
from pathlib import Path


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Disposable hosted client only')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handle',type=int,required=True)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--action',choices=('click','state'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    from pywinauto import Desktop
    from scripts.client_wizard_check import native_windows
    report=dict(handle=args.handle,pid=args.pid,name=args.name,action=args.action,
                scope='Separate UIA client process without a Qt GUI/COM apartment')
    try:
        owned=next((w for w in native_windows() if w['handle']==args.handle and w['pid']==args.pid),None)
        if owned is None:raise RuntimeError('Requested visible window does not belong to the test process')
        report['native']=owned
        window=Desktop(backend='uia').window(handle=args.handle)
        root=window.wrapper_object()
        report['root']=dict(name=root.window_text(),handle=root.handle,process_id=root.process_id())
        report['controls']=[]
        for control in root.descendants():
            rect=control.rectangle()
            report['controls'].append(dict(name=control.window_text(),control_type=control.element_info.control_type,
                                           rectangle=[rect.left,rect.top,rect.right,rect.bottom]))
        # Qt exposes checkable QToolButtons as CheckBox controls through UIA.
        # Match the observed accessible name and require exactly one control.
        matches=[c for c in root.descendants() if c.window_text()==args.name
                 and c.element_info.control_type in ('CheckBox','Button')]
        if len(matches)!=1:raise RuntimeError('Named accessible control is not unique: '+args.name)
        button=matches[0]
        report['selected_control_type']=button.element_info.control_type
        if args.action=='click':button.click_input()
        else:report['checked']=button.get_toggle_state()==1
        report['result']='PASS'
        return 0
    except Exception as error:
        report.update(result='FAILED',error=repr(error))
        return 1
    finally:
        args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
