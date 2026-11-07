"""Exercise the exact reported release only inside a disposable hosted Windows VM.

The caller owns continuous Defender observation. No build, executable rewriting,
exclusions, security bypass, or release publication is performed here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Requires a disposable GitHub-hosted runner.')
    import winreg
    from PySide6.QtCore import QSettings
    from mini_whiteboard.hotkey_config import Chord, HotkeyConfig, defaults
    from mini_whiteboard.platform.windows.login import WindowsLogin, RUN_KEY, APPROVAL_KEY, VALUE_NAME
    from scripts.payload_manifest import verify_manifest, read_manifest
    from scripts.build_support import verify_release_files, verify_frozen_modules
    from scripts.observed_process import run as observed_run

    parser = argparse.ArgumentParser()
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--package', choices=('all', 'installer', 'portable'), default='all')
    parser.add_argument('--client-gui', action='store_true')
    parser.add_argument('--candidate-identity', type=Path)
    args = parser.parse_args()
    if args.client_gui:
        from scripts.client_environment_check import dismiss_wsl_prompt
        dismiss_wsl_prompt()
    visuals_only = args.client_gui and os.environ.get('MINIWHITEBOARD_CLIENT_VISUALS_ONLY') == '1'
    editing_only = args.client_gui and os.environ.get('MINIWHITEBOARD_CLIENT_EDITING_ONLY') == '1'
    gestures_only = args.client_gui and os.environ.get('MINIWHITEBOARD_CLIENT_GESTURES_ONLY') == '1'
    comparison_only = args.client_gui and os.environ.get('MINIWHITEBOARD_CLIENT_COMPARISON_ONLY') == '1'
    upgrade_only = args.client_gui and os.environ.get('MINIWHITEBOARD_CLIENT_UPGRADE_ONLY') == '1'
    focused = visuals_only or editing_only or gestures_only
    candidate = None
    if args.candidate_identity:
        from scripts.candidate_identity import read
        candidate = read(args.candidate_identity)
    args.output.mkdir(exist_ok=True, parents=True)
    report = {'purpose': 'Original published-package investigation, not final release acceptance',
              'checks': [], 'native_suites': [], 'not_run': [
                  'Genuine browser download and Explorer extraction',
                  'School-managed policy and original threat identification',
                  'Interactive SmartScreen/Smart App Control',
                  'Automatic Windows sign-in',
                  'Clean machine with development tools uninstalled']}
    output = args.output / 'runtime.json'
    if candidate:
        report['purpose'] = ('Unpublished candidate client checks; browser provenance in parent report; ARM64/Test Mode limitations'
                             if args.client_gui else 'Unpublished candidate on a hosted Server VM; not Windows client acceptance')
        report['candidate_identity'] = candidate
    if args.client_gui:
        report['not_run'][0]='Published release URL acceptance; this candidate uses the genuine browser/Explorer artifact-container route recorded by the parent'
        report['client_scope']=('Focused frozen Glass/toolbar checks only' if visuals_only else
                                'Existing early-release and pointer-motion matrices only' if gestures_only else
                                'Focused editing/tray/control checks only' if editing_only else 'Full client package acceptance')

    def save():
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def check(label, condition, detail=None, *, fatal=True):
        row = {'check': label, 'status': 'PASS' if condition else 'FAIL', 'detail': detail}
        report['checks'].append(row)
        print(json.dumps(row), flush=True)
        save()
        if not condition and fatal:
            raise AssertionError(label)

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def bounded(label, command, timeout):
        report['current_operation'] = label
        save()
        result = observed_run(command, args.output/'runtime-operations'/label, label, timeout)
        report.setdefault('operations', []).append(result)
        save()
        if result['status'] in ('TIMED OUT', 'ERROR'):
            raise RuntimeError(f"{label}: {result['status']}; retained partial output")
        return result['exit_code']

    def reg(key, name):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except FileNotFoundError:
            return None

    install_key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{94CAAC15-1695-4601-9CA3-67F10E2A8A32}_is1'
    check('Disposable account has no Mini Whiteboard install or startup entry',
          reg(install_key, 'InstallLocation') is None and reg(RUN_KEY, VALUE_NAME) is None
          and reg(APPROVAL_KEY, VALUE_NAME) is None)
    portable = args.downloads / 'portable' / 'Mini Whiteboard'
    installer = args.downloads / 'MiniWhiteboard-1.3.4-HotkeyPatch-Setup.exe'
    exe_hash = 'a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716'
    installer_hash = '29770151f8df811e1f8890a93aaa201f2e666e05bb1310dcf086bbd7b73a460b'
    if candidate:
        installer = args.downloads/candidate['assets'][0]['name']
        installer_hash, exe_hash = candidate['assets'][0]['sha256'], candidate['exe_sha256']
    check('Installer matches the recorded investigation identity', digest(installer) == installer_hash)
    expected = read_manifest((portable / 'MiniWhiteboard.payload').read_text(encoding='utf-8'))

    def payload(directory, label, exact=False):
        check(label + ': executable matches the recorded investigation identity', digest(directory / 'Mini Whiteboard.exe') == exe_hash)
        check(label + f': all {len(expected)} intended runtime files match the portable archive',
              all((directory / name).is_file() and digest(directory / name) == value for name, value in expected.items()))
        check(label + ': payload manifest is identical',
              (directory / 'MiniWhiteboard.payload').read_bytes() == (portable / 'MiniWhiteboard.payload').read_bytes())
        if exact:
            check(label + ': no unexpected runtime files', True, verify_manifest(directory))
        check(label + ': dependency notices and module inventory', True,
              {**verify_release_files(directory), **verify_frozen_modules(directory / 'Mini Whiteboard.exe')})

    def native(directory, label):
        completed = []
        if upgrade_only:
            report['native_suites_not_run']='Focused installer replacement checks; native input suites remain separate'
            save();return True
        if gestures_only:
            if not args.candidate_identity:
                raise RuntimeError('Client gesture matrices require an exact candidate identity')
            for mode,deadline in (('pending',300),('motion',240)):
                dest=args.output/(label+'-'+mode)
                code=bounded(label+'-'+mode,[sys.executable,'-m','scripts.early_release_matrix',
                    '--executable',str(directory/'Mini Whiteboard.exe'),'--candidate-identity',str(args.candidate_identity),
                    '--output',str(dest),'--mode',mode],deadline)
                completed.append(code==0)
                check(label+': unchanged '+mode+' functional matrix completed',code==0,fatal=False)
            return all(completed)
        if args.client_gui and not editing_only:
            for background in ('light','busy'):
                dest=args.output/(label+'-glass-'+background)
                code=bounded(label+'-glass-'+background,[sys.executable,'-m','scripts.packaged_drawing_check',
                    '--executable',str(directory/'Mini Whiteboard.exe'),'--expected-sha',exe_hash,
                    '--output',str(dest),'--toolbar','--visual-only','--theme','Glass','--background',background],90)
                completed.append(code==0)
                check(label+': Glass/toolbar '+background+' visual capture completed',code==0,fatal=False)
            if visuals_only:
                return all(completed)
        for module, suffix, extra in (
            ('scripts.packaged_shortcut_check', 'defaults', ['--profile', 'default', '--available-defaults', '--trace-transition']),
            ('scripts.packaged_shortcut_check', 'custom', ['--profile', 'custom']),
            ('scripts.package_check', 'editing', ['--expected-version', candidate['version'] if candidate else '1.3.4']
             + (['--extended'] if args.client_gui else [])),
        ):
            if editing_only and suffix != 'editing':
                continue
            destination = args.output / (label + '-' + suffix)
            command = [sys.executable, '-m', module, '--executable', str(directory / 'Mini Whiteboard.exe'),
                       '--output', str(destination), *extra]
            if args.client_gui and module=='scripts.packaged_shortcut_check':
                command+=['--functional-deadline-ms','2000']
            exit_code = bounded(label + '-' + suffix, command, 180)
            rows_path = destination / 'checks.json'
            document = json.loads(rows_path.read_text()) if rows_path.is_file() else []
            rows = document.get('checks', []) if isinstance(document, dict) else document
            report['native_suites'].append({'package': label, 'module': module, 'profile': suffix,
                                           'exit_code': exit_code, 'reported_checks': len(rows)})
            passed = exit_code == 0 and bool(rows) and all(row['status'] == 'PASS' for row in rows)
            completed.append(passed)
            # Each suite owns and cleans up its process and preferences. Retain
            # failures while collecting the independent suites and file hashes.
            check(label + ': ' + suffix + ' native checks completed', passed, len(rows), fatal=False)
            if suffix == 'defaults' and (not passed or label == 'portable'):
                for diagnostic_name, diagnostic_option, purpose in (
                    ('capture-isolated', '--capture-only', 'Q without prior W workload'),
                    ('capture-after-cancel', '--cancel-prelude', 'Q after only one zero-area W cancellation'),
                ):
                    isolated = args.output / (label + '-' + diagnostic_name)
                    isolated_exit = bounded(label + '-' + diagnostic_name,
                        [sys.executable, '-m', 'scripts.packaged_shortcut_check', '--executable',
                         str(directory / 'Mini Whiteboard.exe'), '--output', str(isolated),
                         '--profile', 'default', '--available-defaults', '--trace-transition', diagnostic_option], 180)
                    report.setdefault('frozen_diagnostics', []).append({
                        'package': label, 'exit_code': isolated_exit,
                        'purpose': 'Fresh unchanged executable: '+purpose+'; does not replace the failed full acceptance sequence'})
                    save()
            if suffix == 'defaults' and not passed:
                diagnostic = args.output / (label + '-source-comparison')
                diagnostic_exit = bounded(label + '-source-comparison',
                    [sys.executable, '-m', 'scripts.packaged_shortcut_check', '--executable',
                     str(directory / 'Mini Whiteboard.exe'), '--output', str(diagnostic),
                     '--profile', 'default', '--available-defaults', '--trace-transition', '--source-diagnostic'], 180)
                report.setdefault('source_diagnostics', []).append({
                    'package': label, 'exit_code': diagnostic_exit,
                    'purpose': 'Callback timings in source; excluded from exact-package acceptance'})
                save()
        return all(completed)

    target = Path(os.environ['LOCALAPPDATA']) / 'Programs' / 'Mini Whiteboard'

    def setup(label, package=installer, extra=()):
        if args.client_gui:
            expected_setup=(installer_hash if package==installer else
                            '29770151f8df811e1f8890a93aaa201f2e666e05bb1310dcf086bbd7b73a460b')
            return bounded(label,[sys.executable,'-m','scripts.client_wizard_check','--executable',str(package),
                                  '--expected-sha',expected_setup,'--output',str(args.output/('wizard-'+label)),*extra],80)
        return bounded(label, [str(package), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART',
                                 '/LOG=' + str(args.output / (label + '.log')), '/DIR=' + str(target)],
                       60)

    def uninstall(label):
        if args.client_gui:
            return bounded(label,[sys.executable,'-m','scripts.client_wizard_check','--executable',str(target/'unins000.exe'),
                                  '--uninstall','--output',str(args.output/('wizard-'+label))],80)
        return bounded(label, [str(target / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                                 '/NORESTART', '/LOG=' + str(args.output / (label + '.log'))],
                       45)

    def quiet_launch(directory, label):
        report['current_operation'] = label + ': quiet launch'
        save()
        if args.client_gui and directory==target and not focused:
            configured=QSettings('MiniWhiteboard','MiniWhiteboard')
            configured.setValue('shortcuts/custom_windows',defaults(hide='shift').to_json());configured.sync()
        # The child has only Windows on PATH, and no Python environment hints.
        environment = dict(os.environ, PATH=os.environ['WINDIR'] + ';' + os.environ['WINDIR'] + '\\System32')
        for name in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_PREFIX', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH'):
            environment.pop(name, None)
        if args.client_gui:
            from win32com.shell import shell,shellcon
            import win32api,win32event,win32process
            from PIL import ImageGrab
            ImageGrab.grab(all_screens=True).save(args.output/(label+'-before-shell-launch.png'))
            try:
                from scripts.client_wizard_check import shell_open
                launched=shell_open(lambda:shell.ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
                    lpFile=str(directory/'Mini Whiteboard.exe'),lpDirectory=str(directory),nShow=1),args.output/(label+'-shell-observation'),directory/'Mini Whiteboard.exe',exe_hash)
                handle=launched.get('hProcess')
                if not handle: raise RuntimeError('Shell did not provide an owned application process; inspect security UI')
                class ShellChild:
                    def __init__(self):
                        import ctypes as C
                        from ctypes import wintypes as W
                        get_pid=C.windll.kernel32.GetProcessId
                        get_pid.argtypes=[W.HANDLE];get_pid.restype=W.DWORD
                        self.pid=get_pid(int(handle))
                    def poll(self):
                        result=win32process.GetExitCodeProcess(handle)
                        return None if result==259 else result
                    def terminate(self): win32api.TerminateProcess(handle,1)
                    def wait(self,timeout):
                        if win32event.WaitForSingleObject(handle,int(timeout*1000))==258:
                            raise TimeoutError('Owned shell-launched process did not exit')
                        handle.Close()
                child=ShellChild()
            except Exception:
                ImageGrab.grab(all_screens=True).save(args.output/(label+'-shell-launch-blocked.png'))
                raise
        else:
            child = subprocess.Popen([str(directory / 'Mini Whiteboard.exe')], env=environment,
                                     cwd=str(directory), creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            time.sleep(3)
            if args.client_gui:
                ImageGrab.grab(all_screens=True).save(args.output/(label+'-shell-launched.png'))
            check(label + (': normal Shell launch stays running' if args.client_gui else ': packaged runtime stays running without Python on PATH'), child.poll() is None)
            if directory == target and not focused:
                owned_board=None
                if args.client_gui:
                    import ctypes as C
                    from ctypes import wintypes as W
                    from scripts.client_wizard_check import native_windows
                    from PIL import ImageGrab
                    u=C.windll.user32
                    u.SetCursorPos.argtypes=[C.c_int,C.c_int]
                    u.keybd_event.argtypes=[W.BYTE,W.BYTE,W.DWORD,C.c_size_t]
                    u.SetCursorPos(180,220)
                    chord=(0xA2,0x5B,0xA0,0x57)
                    try:
                        for vk in chord:u.keybd_event(vk,0,1 if vk==0x5B else 0,0)
                        time.sleep(.4);u.SetCursorPos(540,440);time.sleep(.1)
                    finally:
                        for vk in reversed(chord):u.keybd_event(vk,0,2|(1 if vk==0x5B else 0),0)
                    deadline=time.monotonic()+2
                    while time.monotonic()<deadline:
                        owned_board=next((w for w in native_windows() if w['pid']==child.pid and w['title']=='Whiteboard 1'),None)
                        if owned_board:break
                        time.sleep(.02)
                    check('Running refusal begins with a real owned board',owned_board is not None,owned_board)
                    ImageGrab.grab(all_screens=True).save(args.output/'running-refusal-before.png')
                refused_setup=setup('running-refusal');refused_uninstall=uninstall('uninstall-refusal')
                check('Setup refuses a running installed application', refused_setup==10 if args.client_gui else refused_setup!=0)
                check('Uninstall refuses a running application', refused_uninstall==10 if args.client_gui else refused_uninstall!=0)
                check('Refusal leaves the running process alive', child.poll() is None)
                if owned_board is not None:
                    after=next((w for w in native_windows() if w['handle']==owned_board['handle']),None)
                    check('Setup and uninstall refusal preserve the same visible board',
                          after is not None and after['pid']==child.pid and after['rectangle']==owned_board['rectangle'],after)
                    ImageGrab.grab(all_screens=True).save(args.output/'running-refusal-after.png')
        finally:
            # Only this test-owned process is stopped; no user desktop is involved.
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)

    installed = False
    settings = QSettings('MiniWhiteboard', 'MiniWhiteboard')
    settings_snapshot = {key: settings.value(key) for key in settings.allKeys()}
    try:
        if args.package != 'installer':
            payload(portable, 'Portable before launch', exact=True)
            if comparison_only:
                report['purpose']='Controlled same-VM frozen V1.3.4 HotkeyPatch versus V1.3.6 Glass/White comparison, not full acceptance'
                baseline=args.downloads/'comparison-baseline/Mini Whiteboard'
                expected_baseline='a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716'
                check('Published HotkeyPatch baseline identity matches',digest(baseline/'Mini Whiteboard.exe')==expected_baseline)
                check('Published HotkeyPatch baseline inventory matches',True,verify_manifest(baseline))
                completed=[]
                for background in ('light','busy'):
                    for version,directory,sha,toolbar,theme in (
                        ('v134',baseline,expected_baseline,False,'Glass'),
                        ('v136-off',portable,exe_hash,False,'Glass'),
                        ('v136-on',portable,exe_hash,True,'Glass'),
                        ('v136-white',portable,exe_hash,True,'White')):
                        label='comparison-'+background+'-'+version
                        command=[sys.executable,'-m','scripts.packaged_drawing_check',
                            '--executable',str(directory/'Mini Whiteboard.exe'),'--expected-sha',sha,
                            '--output',str(args.output/label),'--visual-only','--comparison',
                            '--theme',theme,'--background',background]
                        if toolbar:command.append('--toolbar')
                        code=bounded(label,command,60);completed.append(code==0)
                        check(label+' capture completed',code==0,fatal=False)
                payload(portable,'Portable after comparison',exact=True)
                check('Baseline executable unchanged after comparison',digest(baseline/'Mini Whiteboard.exe')==expected_baseline)
                check('All controlled comparison captures completed',all(completed))
                report['result']='COMPARISON CAPTURED; inspect pixels and diagnostics before attributing a cause'
                return
            quiet_launch(portable, 'Portable')
            native_passed = native(portable, 'portable')
            payload(portable, 'Portable after execution', exact=True)
            check('Portable did not install itself or opt into startup',
                  reg(install_key, 'InstallLocation') is None and reg(RUN_KEY, VALUE_NAME) is None)
            check('All requested portable native suites passed', native_passed)
            if args.package == 'portable':
                report['result'] = 'PASS for the listed portable-package checks only'
                return
        check('Exact recorded installer completes a fresh '+('wizard' if args.client_gui else 'silent')+' installation', setup('fresh-install') == 0)
        installed = True
        payload(target, 'Installed before launch')
        quiet_launch(target, 'Installed')
        payload(target, 'Installed after execution')
        if focused:
            native_passed=native(target,'installed')
            payload(target,'Installed after focused visual checks')
            check('Focused-check installation uninstalls normally',uninstall('focused-uninstall')==0)
            installed=False
            check('All requested installed focused checks passed',native_passed)
            report['result']='PASS for the selected installed subset only; full acceptance remains separate'
            return
        check('Fresh installation uninstalls normally', uninstall('fresh-uninstall') == 0)
        installed = False

        predecessor = args.downloads / 'MiniWhiteboard-1.3.4-HotkeyPatch-Setup.exe'
        check('Predecessor hash matches the published V1.3.4 HotkeyPatch installer', digest(predecessor) ==
              '29770151f8df811e1f8890a93aaa201f2e666e05bb1310dcf086bbd7b73a460b')
        check('Published V1.3.4 HotkeyPatch installs before upgrade', setup('predecessor-install', predecessor) == 0)
        installed = True
        old_manifest=(target/'MiniWhiteboard.payload').read_bytes()
        old_payload=read_manifest(old_manifest.decode('utf-8'))
        check('Installed predecessor is the actual published HotkeyPatch executable',
              digest(target/'Mini Whiteboard.exe')=='a539339e2ee83c54be86e3e67115c5d1f0bcbca12605bb875ba241f5b79e2716')
        old_location=reg(install_key,'InstallLocation')
        obsolete=sorted(set(old_payload)-set(expected))
        report['upgrade_inventories']=dict(old_count=len(old_payload),new_count=len(expected),obsolete_paths=obsolete,
                                           identity=install_key,old_location=old_location)
        unrelated=target/'tester-personal-notes.txt'
        check('Unrelated fixture does not replace an existing file',not unrelated.exists())
        unrelated.write_text('Preserve this unrelated tester file.',encoding='utf-8')

        configuration = HotkeyConfig(Chord({'ctrl', 'alt'}, 'F8'), Chord({'ctrl', 'meta'}, 'F9'), defaults().hide)
        settings.setValue('shortcuts/custom_windows', configuration.to_json())
        settings.setValue('appearance/theme', 'Glass')
        settings.setValue('tools/floating', True)
        settings.sync()
        login = WindowsLogin(target / 'Mini Whiteboard.exe', frozen=True)
        login.set_enabled(True)
        check('Opt-in startup registers the actual installed path', reg(RUN_KEY, VALUE_NAME) == login.command)
        # Preserve an explicit OS-disabled approval record through repeat setup.
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, APPROVAL_KEY, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, VALUE_NAME, 0, winreg.REG_BINARY, b'\x03' + b'\x00' * 11)
        approval = reg(APPROVAL_KEY, VALUE_NAME)
        if args.client_gui:
            def old_preserved(label):
                check(label+': every previous runtime byte and inventory survives',
                    all((target/name).is_file() and digest(target/name)==sha for name,sha in old_payload.items())
                    and (target/'MiniWhiteboard.payload').read_bytes()==old_manifest)
                check(label+': previous app registration survives',
                    reg(install_key,'DisplayVersion')=='1.3.4' and reg(install_key,'InstallLocation')==old_location)
                check(label+': unrelated file and startup approval survive',
                    unrelated.read_text(encoding='utf-8')=='Preserve this unrelated tester file.'
                    and reg(APPROVAL_KEY,VALUE_NAME)==approval)
            check('Cancelling the normal replacement wizard completes before copying',
                  setup('cancel-upgrade',extra=('--cancel-before-install',))==20)
            old_preserved('Cancelled upgrade')
            import ctypes as C
            from ctypes import wintypes as W
            k=C.WinDLL('kernel32',use_last_error=True)
            open_file=k.CreateFileW
            open_file.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
            open_file.restype=W.HANDLE
            k.CloseHandle.argtypes=[W.HANDLE]
            lock=open_file(str(target/'_internal/PySide6/Qt6Widgets.dll'),0x80000000,1,None,3,0,None)
            check('Owned file lock established for pre-copy failure test',bool(lock) and lock!=C.c_void_p(-1).value)
            try:
                check('Normal wizard refuses a locked replacement file',
                      setup('locked-upgrade',extra=('--expect-replacement-failure',))==20)
            finally:k.CloseHandle(lock)
            old_preserved('Pre-copy failure')
            if upgrade_only:
                import threading
                late=target/'_internal/PySide6/plugins/imageformats/qwebp.dll'
                before_time=(target/'Mini Whiteboard.exe').stat().st_mtime_ns
                stop_lock=threading.Event();late_lock=[]
                def interrupt_copy():
                    deadline=time.monotonic()+55
                    while not stop_lock.is_set() and time.monotonic()<deadline:
                        try:changed=(target/'Mini Whiteboard.exe').stat().st_mtime_ns!=before_time
                        except FileNotFoundError:changed=False
                        if changed:
                            handle=open_file(str(late),0x80000000,1,None,3,0,None)
                            if handle and handle!=C.c_void_p(-1).value:late_lock.append(handle)
                            return
                        time.sleep(.003)
                watcher=threading.Thread(target=interrupt_copy,daemon=True);watcher.start()
                try:
                    code=setup('mid-copy-rollback',extra=('--expect-replacement-failure',))
                finally:
                    stop_lock.set();watcher.join(2)
                    for handle in late_lock:k.CloseHandle(handle)
                check('Mid-copy fault was injected after executable replacement began',bool(late_lock))
                check('Normal wizard reports and aborts the mid-copy failure',code==20)
                old_preserved('Mid-copy rollback')
                restored=subprocess.Popen([str(target/'Mini Whiteboard.exe')],creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    time.sleep(3)
                    check('Restored published HotkeyPatch runtime starts after rollback',restored.poll() is None,
                          'Controlled direct process startup; normal Shell acceptance is a separate check')
                finally:
                    if restored.poll() is None:restored.terminate();restored.wait(5)
        check('Upgrade from published V1.3.4 HotkeyPatch to the investigated package completes', setup('upgrade-install') == 0)
        settings.sync()
        check('Upgrade preserves custom hotkeys, appearance, floating tools and disabled startup choice',
              settings.value('shortcuts/custom_windows') == configuration.to_json()
              and settings.value('appearance/theme') == 'Glass'
              and settings.value('tools/floating',type=bool)
              and reg(RUN_KEY, VALUE_NAME) == login.command and reg(APPROVAL_KEY, VALUE_NAME) == approval)
        check('External startup disable remains effective',not login.state().enabled)
        check('Upgrade reuses the stable installation identity and directory',
              reg(install_key,'InstallLocation')==old_location and reg(install_key,'DisplayVersion')==(candidate['version'] if candidate else '1.3.4'))
        if obsolete:
            check('Upgrade removes all unchanged obsolete inventoried files',all(not (target/name).exists() for name in obsolete),obsolete)
        else:
            report['obsolete_removal']=f'NOT APPLICABLE to these two actual inventories: both contain the same {len(expected)} paths. No removal was exercised.'
        check('Upgrade preserves the unrelated file',unrelated.read_text(encoding='utf-8')=='Preserve this unrelated tester file.')
        entries=[]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall') as root:
            index=0
            while True:
                try:name=winreg.EnumKey(root,index)
                except OSError:break
                index+=1
                key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall'+'\\'+name
                if reg(key,'DisplayName')=='Mini Whiteboard':entries.append(key)
        check('Exactly one Mini Whiteboard installed-app entry remains',entries==[install_key],entries)
        if args.client_gui:
            from PySide6.QtCore import QStandardPaths
            from win32com.client import Dispatch
            shell=Dispatch('WScript.Shell')
            link=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.ApplicationsLocation))/'Mini Whiteboard/Mini Whiteboard.lnk'
            check('Start menu shortcut targets the updated installed executable',
                  link.is_file() and Path(shell.CreateShortcut(str(link)).TargetPath).resolve()==(target/'Mini Whiteboard.exe').resolve())
            desktop_link=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))/'Mini Whiteboard.lnk'
            check('Desktop shortcut remains absent when not selected',not desktop_link.exists())
        payload(target, 'Installed after upgrade')
        check('Same-version repeat install completes', setup('repeat-install') == 0)
        payload(target, 'Installed after repeat setup')
        settings.sync()
        check('Same-version reinstall preserves path, hotkeys, floating tools and external startup disable',
              reg(install_key,'InstallLocation')==old_location
              and settings.value('shortcuts/custom_windows')==configuration.to_json()
              and settings.value('appearance/theme')=='Glass' and settings.value('tools/floating',type=bool)
              and reg(RUN_KEY,VALUE_NAME)==login.command and reg(APPROVAL_KEY,VALUE_NAME)==approval)
        native_passed = native(target, 'installed')
        payload(target, 'Installed after native suites')
        check('Normal '+('wizard' if args.client_gui else 'silent')+' uninstall completes', uninstall('normal-uninstall') == 0)
        installed = False
        check('Uninstall removes owned app files, entry and startup registrations',
              not (target / 'Mini Whiteboard.exe').exists() and reg(install_key, 'InstallLocation') is None
              and reg(RUN_KEY, VALUE_NAME) is None and reg(APPROVAL_KEY, VALUE_NAME) is None)
        check('Uninstall preserves user preferences', settings.value('shortcuts/custom_windows') == configuration.to_json())
        check('Uninstall preserves the unrelated file',unrelated.read_text(encoding='utf-8')=='Preserve this unrelated tester file.')
        check('All requested installed native suites passed', native_passed)
        report['result'] = 'PASS for the listed package checks only'
    except Exception as error:
        report['result'] = 'FAILED'; report['error'] = str(error)
        raise
    finally:
        if installed:
            try:
                report['cleanup_uninstall_exit'] = uninstall('cleanup-uninstall')
            except Exception as error:
                report['cleanup_error'] = str(error)
        settings.clear()
        for key, value in settings_snapshot.items():
            settings.setValue(key, value)
        settings.sync()
        report['startup_restored'] = reg(RUN_KEY, VALUE_NAME) is None and reg(APPROVAL_KEY, VALUE_NAME) is None
        save()


if __name__ == '__main__':
    main()
