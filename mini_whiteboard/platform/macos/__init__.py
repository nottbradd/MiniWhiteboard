"""Native dependencies are loaded only when the macOS adapter is selected."""
from ..base import Platform
from ...shortcuts import ShortcutPolicy


def create_platform():
    from .login import MacLogin
    from .desktop import MacDesktop
    from .runtime import MacRuntime
    from .hotkeys import MacHotkeys
    from .capture import MacCaptureService
    desktop = MacDesktop()
    return Platform("macos", MacRuntime(), desktop, MacCaptureService(desktop),
                    lambda app, preset: MacHotkeys(app, preset), ShortcutPolicy(mac=True), MacLogin())
