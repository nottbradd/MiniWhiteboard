"""The main app's supported SMAppService login item; no helper or launch plist."""
from pathlib import Path
import sys
from ...login import LoginState, packaged_path_issue


class MacLogin:
    def __init__(self, *, service=None, executable=None, bundle=None, frozen=None, temporary_roots=None, applications_roots=None):
        self.service = service
        self.executable = Path(executable or sys.executable).resolve()
        self.bundle = Path(bundle).resolve() if bundle else None
        self.frozen, self.temporary_roots = frozen, temporary_roots
        self.applications_roots = applications_roots

    def _service(self):
        issue = packaged_path_issue(self.executable, self.frozen, self.temporary_roots)
        if issue:
            raise OSError(issue)
        if self.bundle is None:
            from Foundation import NSBundle
            self.bundle = Path(str(NSBundle.mainBundle().bundlePath())).resolve()
        roots = self.applications_roots or (Path('/Applications'), Path.home()/'Applications')
        if self.bundle.suffix != '.app' or not any(self.bundle.is_relative_to(Path(root).resolve()) for root in roots):
            raise OSError('Move Mini Whiteboard to Applications first.')
        if not self.executable.is_relative_to(self.bundle/'Contents/MacOS'):
            raise OSError('Open the installed Mini Whiteboard application bundle first.')
        if self.service is None:
            from ServiceManagement import SMAppService
            self.service = SMAppService.mainAppService()
        return self.service

    def state(self):
        try:
            status = int(self._service().status())
            if status == 1:
                return LoginState(registered=True, enabled=True)
            if status == 2:
                return LoginState(registered=True, approval_required=True,
                                  detail='Review Mini Whiteboard in System Settings → Login Items.')
            if status == 0:
                return LoginState()
            return LoginState(available=False, detail='macOS could not find this login application. Move it to Applications and reopen it.')
        except Exception as error:
            return LoginState(available=False, detail=str(error))

    def set_enabled(self, enabled):
        service = self._service()
        current = self.state()
        if not current.available:
            raise OSError(current.detail)
        if bool(enabled) == current.enabled and not current.approval_required:
            return current
        try:
            ok, error = (service.registerAndReturnError_(None) if enabled
                         else service.unregisterAndReturnError_(None))
        except Exception as error:
            raise OSError(f'macOS could not change Open at login: {error}') from error
        result = self.state()
        if not ok and not (enabled and result.approval_required):
            detail = str(error.localizedDescription()) if error is not None else 'Registration was not accepted.'
            raise OSError(f'macOS could not change Open at login: {detail}')
        return result

    def open_settings(self):
        from ServiceManagement import SMAppService
        SMAppService.openSystemSettingsLoginItems()
