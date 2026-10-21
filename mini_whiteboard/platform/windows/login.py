"""Per-user Run registration. Startup approval is observed, never enabled by us."""
import ntpath
from pathlib import Path
import re
import subprocess
import sys
from ...login import LoginState, packaged_path_issue

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APPROVAL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'
VALUE_NAME = 'MiniWhiteboard'


class UserRegistry:
    def get(self, key, name):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except FileNotFoundError:
            return None

    def put(self, key, name, value):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)

    def remove(self, key, name):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            pass


def owned_command(command):
    if not isinstance(command, str):
        return False
    match = re.fullmatch(r'"([^"\r\n]+)" --login', command)
    return bool(match and ntpath.basename(match[1]).casefold() == 'mini whiteboard.exe')


class WindowsLogin:
    def __init__(self, executable=None, *, frozen=None, registry=None, temporary_roots=None, value_name=VALUE_NAME):
        self.executable = Path(executable or sys.executable).resolve()
        self.frozen, self.temporary_roots = frozen, temporary_roots
        self.registry = registry or UserRegistry()
        self.value_name = value_name

    @property
    def command(self):
        return subprocess.list2cmdline([str(self.executable), '--login'])

    def state(self):
        issue = packaged_path_issue(self.executable, self.frozen, self.temporary_roots)
        if issue:
            return LoginState(available=False, detail=issue)
        if self.executable.name.casefold() != 'mini whiteboard.exe':
            return LoginState(available=False, detail='Use the original Mini Whiteboard executable name.')
        if len(self.command.encode('utf-16-le')) // 2 > 260:
            return LoginState(available=False, detail='Move Mini Whiteboard to a shorter, permanent application path first.')
        try:
            command = self.registry.get(RUN_KEY, self.value_name)
            if command is None:
                return LoginState()
            if not owned_command(command):
                return LoginState(available=False, detail='Another program owns this startup entry. It was left unchanged.')
            approval = self.registry.get(APPROVAL_KEY, self.value_name)
            # Windows does not expose StartupTask for an unpackaged desktop app.
            # Conservatively observe known approval records, without writing an
            # undocumented enable flag. Unknown formats require an OS check.
            approved = approval is None or (isinstance(approval, bytes) and len(approval) >= 4
                                           and int.from_bytes(approval[:4], 'little') in (2, 6))
            detail = ''
            if not approved:
                detail = 'Check Mini Whiteboard in Windows Startup apps.'
            elif ntpath.normcase(command) != ntpath.normcase(self.command):
                detail = 'A different Mini Whiteboard copy is registered.'
            return LoginState(registered=True, enabled=approved, approval_required=not approved, detail=detail)
        except OSError as error:
            return LoginState(available=False, detail=f'Windows startup settings could not be read: {error}')

    def set_enabled(self, enabled):
        state = self.state()
        if not state.available:
            raise OSError(state.detail)
        try:
            if enabled:
                command = self.registry.get(RUN_KEY, self.value_name)
                if command is not None and not owned_command(command):
                    raise OSError('The startup entry changed ownership. It was left unchanged.')
                if command != self.command:
                    self.registry.put(RUN_KEY, self.value_name, self.command)
            else:
                command = self.registry.get(RUN_KEY, self.value_name)
                if command is not None and not owned_command(command):
                    raise OSError('The startup entry changed ownership. It was left unchanged.')
                if command is None:
                    return self.state()
                self.registry.remove(RUN_KEY, self.value_name)
                self.registry.remove(APPROVAL_KEY, self.value_name)
        except OSError as error:
            raise OSError(f'Could not change Open at login: {error}') from error
        return self.state()

    def open_settings(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if not QDesktopServices.openUrl(QUrl('ms-settings:startupapps')):
            raise OSError('Open Windows Settings → Apps → Startup to review Mini Whiteboard.')
