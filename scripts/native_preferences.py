"""Opt-in desktop checks restore the user's preferences even after a failure."""
from contextlib import contextmanager
from PySide6.QtCore import QSettings
from mini_whiteboard.hotkey_config import compatibility, defaults


@contextmanager
def compatibility_preferences(configuration=None):
    from mini_whiteboard.windows import SingleInstance
    guard = SingleInstance()
    available = guard.acquired
    guard.close()
    if not available:
        raise RuntimeError('Exit Mini Whiteboard before this desktop check.')
    settings = QSettings('MiniWhiteboard', 'MiniWhiteboard')
    keys = ('shortcuts/custom_windows', 'appearance/theme')
    before = {key: (settings.contains(key), settings.value(key)) for key in keys}
    try:
        settings.setValue(keys[0], (configuration or compatibility(defaults(hide='shift'))).to_json())
        settings.setValue(keys[1], 'White')
        settings.sync()
        yield
    finally:
        for key, (existed, value) in before.items():
            settings.setValue(key, value) if existed else settings.remove(key)
        settings.sync()
