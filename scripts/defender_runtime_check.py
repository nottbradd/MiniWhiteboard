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
        if args.client_gui:
            for background in ('light','busy'):
                dest=args.output/(label+'-glass-'+background)
                code=bounded(label+'-glass-'+background,[sys.executable,'-m','scripts.packaged_drawing_check',
                    '--executable',str(directory/'Mini Whiteboard.exe'),'--expected-sha',exe_hash,
                    '--output',str(dest),'--toolbar','--visual-only','--theme','Glass','--background',background],90)
                completed.append(code==0)
                check(label+': Glass/toolbar '+background+' visual capture completed',code==0,fatal=False)
        for module, suffix, extra in (
            ('scripts.packaged_shortcut_check', 'defaults', ['--profile', 'default', '--available-defaults', '--trace-transition']),
            ('scripts.packaged_shortcut_check', 'custom', ['--profile', 'custom']),
            ('scripts.package_check', 'editing', ['--expected-version', candidate['version'] if candidate else '1.3.4']
             + (['--extended'] if args.client_gui else [])),
        ):
            destination = args.output / (label + '-' + suffix)
            command = [sys.executable, '-m', module, '--executable', str(directory / 'Mini Whiteboard.exe'),
                       '--output', str(destination), *extra]
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

    def setup(label, package=installer):
        if args.client_gui:
            return bounded(label,[sys.executable,'-m','scripts.client_wizard_check','--executable',str(package),
                                  '--output',str(args.output/('wizard-'+label))],80)
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
                launched=shell.ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,lpFile=str(directory/'Mini Whiteboard.exe'),
                                            lpDirectory=str(directory),nShow=1)
                handle=launched.get('hProcess')
                if not handle: raise RuntimeError('Shell did not provide an owned application process; inspect security UI')
                class ShellChild:
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
            if directory == target:
                refused_setup=setup('running-refusal');refused_uninstall=uninstall('uninstall-refusal')
                check('Setup refuses a running installed application', refused_setup==10 if args.client_gui else refused_setup!=0)
                check('Uninstall refuses a running application', refused_uninstall==10 if args.client_gui else refused_uninstall!=0)
                check('Refusal leaves the running process alive', child.poll() is None)
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
        check('Fresh installation uninstalls normally', uninstall('fresh-uninstall') == 0)
        installed = False

        predecessor = args.downloads / 'MiniWhiteboard-1.3.4-Setup.exe'
        check('Predecessor hash matches the preserved original V1.3.4 installer', digest(predecessor) ==
              '0139ba25a5b9cd119c52d42e30ca3052ebb49877d2eee14d45432eacc4506222')
        check('Original V1.3.4 installs before upgrade', setup('predecessor-install', predecessor) == 0)
        installed = True

        configuration = HotkeyConfig(Chord({'ctrl', 'alt'}, 'F8'), Chord({'ctrl', 'meta'}, 'F9'), defaults().hide)
        settings.setValue('shortcuts/custom_windows', configuration.to_json())
        settings.setValue('appearance/theme', 'Glass')
        settings.sync()
        login = WindowsLogin(target / 'Mini Whiteboard.exe', frozen=True)
        login.set_enabled(True)
        check('Opt-in startup registers the actual installed path', reg(RUN_KEY, VALUE_NAME) == login.command)
        # Preserve an explicit OS-disabled approval record through repeat setup.
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, APPROVAL_KEY, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, VALUE_NAME, 0, winreg.REG_BINARY, b'\x03' + b'\x00' * 11)
        approval = reg(APPROVAL_KEY, VALUE_NAME)
        check('Upgrade from original V1.3.4 to the investigated package completes', setup('upgrade-install') == 0)
        settings.sync()
        check('Upgrade preserves custom hotkeys, appearance and disabled startup choice',
              settings.value('shortcuts/custom_windows') == configuration.to_json()
              and settings.value('appearance/theme') == 'Glass'
              and reg(RUN_KEY, VALUE_NAME) == login.command and reg(APPROVAL_KEY, VALUE_NAME) == approval)
        payload(target, 'Installed after upgrade')
        check('Same-version repeat install completes', setup('repeat-install') == 0)
        payload(target, 'Installed after repeat setup')
        native_passed = native(target, 'installed')
        payload(target, 'Installed after native suites')
        check('Normal '+('wizard' if args.client_gui else 'silent')+' uninstall completes', uninstall('normal-uninstall') == 0)
        installed = False
        check('Uninstall removes owned app files, entry and startup registrations',
              not (target / 'Mini Whiteboard.exe').exists() and reg(install_key, 'InstallLocation') is None
              and reg(RUN_KEY, VALUE_NAME) is None and reg(APPROVAL_KEY, VALUE_NAME) is None)
        check('Uninstall preserves user preferences', settings.value('shortcuts/custom_windows') == configuration.to_json())
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
