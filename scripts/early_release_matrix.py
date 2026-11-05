"""Small explicit packaged-input experiments in a disposable protected VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from scripts.observed_process import run


def cases_for(mode):
    if mode == 'probe-smoke':
        return [dict(action='W',hold_ms=20,release_index=-1),
                dict(action='Q',hold_ms=20,release_index=-1),
                dict(action='Q',hold_ms=600,release_index=-1)]
    if mode == 'reduce':
        return [dict(action='Q',hold_ms=600,release_index=-1,prelude=n,sample=sample)
                for n in (0,1,4,16,'full') for sample in range(2)]
    if mode == 'source':
        return [dict(action='Q',hold_ms=600,release_index=-1,prelude=n,source=True)
                for n in (0,'full')]
    profile='custom' if 'custom' in mode else 'default'
    prelude='full' if mode.endswith('full') else 0
    count=3 if profile=='custom' else 4
    cases=[]
    for action in ('W','Q'):
        for index in range(count):
            cases.append(dict(action=action,hold_ms=(5,20,60,120)[index],release_index=index,
                              side=index%2,profile=profile,prelude=prelude))
        for extra in ({'zero':True,'hold_ms':20},{'escape':True,'hold_ms':60},{'repeats':True,'hold_ms':240}):
            cases.append(dict(action=action,release_index=-1,side=1,profile=profile,prelude=prelude,**extra))
    cases.append(dict(action='Q',hold_ms=60,release_index=-1,profile=profile,prelude=prelude,cancel_after_release_ms=5))
    return cases


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Requires a disposable GitHub-hosted runner.')
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('probe-smoke','reduce','source','early-default-fresh','early-default-full','early-custom-fresh','early-custom-full'),required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    expected='a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716'
    actual=hashlib.sha256(args.executable.read_bytes()).hexdigest()
    if actual!=expected: raise RuntimeError('Only the fixed published executable is accepted by this investigation')
    results=[]
    path=args.output/'matrix.json'
    for index,case in enumerate(cases_for(args.mode)):
        case_path=args.output/f'case-{index:02}.json'
        case_path.write_text(json.dumps(case),encoding='utf-8')
        destination=args.output/f'case-{index:02}'
        profile=case.get('profile','default')
        command=[sys.executable,'-m','scripts.packaged_shortcut_check','--executable',str(args.executable),
                 '--output',str(destination),'--profile',profile,'--trace-transition','--timing-case',str(case_path)]
        if profile=='default': command.append('--available-defaults')
        if case.get('source'): command.append('--source-diagnostic')
        operation=run(command,args.output/'operations'/f'case-{index:02}',f'early-{index:02}',120)
        result_path=destination/'early-release.json'
        result=json.loads(result_path.read_text()) if result_path.is_file() else {'result':'INCOMPLETE: no case result'}
        results.append({'case':case,'operation':operation,'result':result.get('result'),
                        'primary':result.get('primary'),'next':result.get('next'),'error':result.get('error')})
        path.write_text(json.dumps({'mode':args.mode,'executable_sha256':actual,'source_only':args.mode=='source',
                                    'cases':results},indent=2)+'\n',encoding='utf-8')
        if operation['status'] in ('TIMED OUT','ERROR'):
            break  # No blind retries or further input after a lost process boundary.
    return 0 if len(results)==len(cases_for(args.mode)) and all(r['result']=='PASS' for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
