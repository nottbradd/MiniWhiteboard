"""Select native services lazily so the other OS never imports its dependencies."""
import sys

_platform = None


def get_platform():
    global _platform
    if _platform is None:
        if sys.platform == "win32":
            from .windows import create_platform
        elif sys.platform == "darwin":
            from .macos import create_platform
        else:
            raise OSError("Mini Whiteboard supports Windows 10/11 and macOS 14 or later.")
        _platform = create_platform()
    return _platform
