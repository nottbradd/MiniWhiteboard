"""Small explicit packaged-input experiments in a disposable protected VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

from scripts.observed_process import run


def cases_for(mode):
    if mode == 'motion':
        return [dict(action=action,profile=profile,hold_ms=20,release_index=-1,
                     prelude=prelude,post_release_motion=True)
                for profile in ('default','custom') for action in ('W','Q') for prelude in (0,'full')]
    if mode == 'source-pending':
        return [dict(case, source=True) for case in cases_for('pending')]
    if mode == 'pending':
        cases=[]
        for profile,count in (('default',4),('custom',3)):
            for action in ('W','Q'):
                # Fixed short schedules, never held until a preview appears.
                for index in range(count):
                    cases.append(dict(action=action,profile=profile,hold_ms=5,
                                      release_index=index,side=index%2))
                cases.append(dict(action=action,profile=profile,hold_ms=5,
                                  release_index=-1,escape=True,side=1))
                cases.append(dict(action=action,profile=profile,hold_ms=20,
                                  release_index=-1,repeats=True,side=1))
        cases.append(dict(action='W',hold_ms=20,release_index=-1,post_release_motion=True))
        return cases
    if mode=='notify':
        return [dict(action='Q',hold_ms=600,release_index=-1,prelude=n,zero_after_prelude=True,sample=s)
                for n in (0,1,4) for s in range(2)]+[
                dict(action='Q',hold_ms=600,release_index=-1,prelude='full',omit_terminal_zero=True,sample=s) for s in range(2)]
    if mode=='stale':
        return [dict(action='Q',hold_ms=20,release_index=-1,prelude=n,post_release_motion=True,source=source)
                for n in (0,'full') for source in (False,True)]
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


def case_group(mode, start=0, count=None):
    cases = list(enumerate(cases_for(mode)))
    if start < 0 or start >= len(cases) or (count is not None and (count < 1 or start+count > len(cases))):
        raise ValueError('Case group must stay within the original matrix')
    return cases[start:] if count is None else cases[start:start+count]


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':
        raise SystemExit('Requires a disposable GitHub-hosted runner.')
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate-identity',type=Path)
    parser.add_argument('--case-start',type=int,default=0)
    parser.add_argument('--case-count',type=int)
    parser.add_argument('--mode',choices=('probe-smoke','reduce','source','notify','stale','pending','source-pending','motion','early-default-fresh','early-default-full','early-custom-fresh','early-custom-full'),required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    expected='a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716'
    if args.candidate_identity:
        from scripts.candidate_identity import read
        expected=read(args.candidate_identity)['exe_sha256']
    actual=hashlib.sha256(args.executable.read_bytes()).hexdigest()
    if actual!=expected: raise RuntimeError('Executable differs from the fixed investigation identity')
    results=[]
    path=args.output/'matrix.json'
    selected=case_group(args.mode,args.case_start,args.case_count)
    state=dict(mode=args.mode,executable_sha256=actual,source_only=all(c.get('source') for _,c in selected),
               unpublished_candidate=bool(args.candidate_identity),expected_indices=[i for i,_ in selected],
               total_matrix_cases=len(cases_for(args.mode)),cases=results)
    def checkpoint(phase, **detail):
        state.update(phase=phase,utc=datetime.now(timezone.utc).isoformat(),**detail)
        temporary=path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as stream:
            stream.write(json.dumps(state,indent=2)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        with (args.output/'progress.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(dict(phase=phase,utc=state['utc'],**detail))+'\n')
            stream.flush()
            os.fsync(stream.fileno())
    checkpoint('before-execution')
    for index,case in selected:
        case_path=args.output/f'case-{index:02}.json'
        case_path.write_text(json.dumps(case),encoding='utf-8')
        destination=args.output/f'case-{index:02}'
        profile=case.get('profile','default')
        command=[sys.executable,'-m','scripts.packaged_shortcut_check','--executable',str(args.executable),
                 '--output',str(destination),'--profile',profile,'--trace-transition','--timing-case',str(case_path)]
        if profile=='default': command.append('--available-defaults')
        if case.get('source'): command.append('--source-diagnostic')
        checkpoint('before-case',current_index=index,current_case=case,command=command)
        operation=run(command,args.output/'operations'/f'case-{index:02}',f'early-{index:02}',120)
        result_path=destination/'early-release.json'
        result=json.loads(result_path.read_text()) if result_path.is_file() else {'result':'INCOMPLETE: no case result'}
        results.append({'index':index,'case':case,'operation':operation,'result':result.get('result'),
                        'primary':result.get('primary'),'next':result.get('next'),'error':result.get('error')})
        checkpoint('after-case',current_index=index,operation_status=operation['status'])
        if operation['status'] in ('TIMED OUT','ERROR'):
            break  # No blind retries or further input after a lost process boundary.
    passed=len(results)==len(selected) and all(r['result']=='PASS' for r in results)
    checkpoint('finished',result='PASS' if passed else 'INCOMPLETE OR FAILED')
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
