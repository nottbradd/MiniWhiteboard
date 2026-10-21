"""Observed OS registration, never a preference that reenables itself at launch."""
from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile
import os


@dataclass(frozen=True)
class LoginState:
    available: bool = True
    registered: bool = False
    enabled: bool = False
    approval_required: bool = False
    detail: str = ''


class UnavailableLogin:
    def state(self):
        return LoginState(available=False, detail='Available in the packaged application.')

    def set_enabled(self, enabled):
        raise OSError(self.state().detail)

    def open_settings(self):
        pass


def packaged_path_issue(path, frozen=None, temporary_roots=None):
    if not (getattr(sys, 'frozen', False) if frozen is None else frozen):
        return 'Available in the packaged application.'
    path = Path(path).resolve()
    roots = temporary_roots
    if roots is None:
        roots = [tempfile.gettempdir()]
        roots += [value for key in ('TEMP','TMP') if (value:=os.environ.get(key))]
        if sys.platform == 'win32' and os.environ.get('WINDIR'):
            roots.append(Path(os.environ['WINDIR'])/'Temp')
    if any(path.is_relative_to(Path(root).resolve()) for root in roots):
        return 'Move Mini Whiteboard out of the temporary folder first.'
    for parent in path.parents:
        if (parent / '.git').exists() and path.relative_to(parent).parts[0] in ('build', 'dist', 'verification'):
            return 'Use an installed or portable application copy first.'
    if not path.is_file():
        return 'The application could not find its installed executable.'
    return ''
