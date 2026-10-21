"""Qt maps ControlModifier to Command on macOS; native hotkeys use their own flags."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ShortcutPolicy:
    mac: bool = False
    preset: str = "default"
    hide_shortcut: str = "default"

    def global_label(self, key):
        prefix = ("Command+Option+Shift" if self.preset == "alternate" else "Control+Option") if self.mac else "Ctrl+Alt"
        if not self.mac and key == 'H' and self.hide_shortcut == 'shift':
            prefix += '+Shift'
        return f"{prefix}+{key}"

    @property
    def status_location(self):
        return "menu bar" if self.mac else "tray"

    @property
    def quit_label(self):
        return "Quit Mini Whiteboard" if self.mac else "Exit Mini Whiteboard"

    def help_html(self):
        from .settings import SHORTCUT_REFERENCE
        return self.format_help(SHORTCUT_REFERENCE).replace('<br>', '<br>\n')

    def help_sections(self):
        from .settings import HELP_SECTIONS
        return tuple((title, self.format_help(body)) for title, body in HELP_SECTIONS)

    def format_help(self, text):
        if not self.mac:
            text = text.replace('Ctrl+Alt+H', self.global_label('H'))
        if self.mac:
            for key in ('W', 'S', 'H'):
                text = text.replace('Ctrl+Alt+' + key, self.global_label(key))
            text = text.replace("Ctrl+Y / Ctrl+Shift+Z", "Command+Shift+Z")
            text = text.replace("Ctrl+Enter", "Command+Return").replace("Ctrl+", "Command+")
            text = text.replace("Alt", "Option").replace("tray", "menu bar").replace("F1", "F1 / Fn+F1")
        return text


def ui_font_family():
    from .platform import get_platform
    if not get_platform().shortcuts.mac:
        return "Segoe UI"
    from PySide6.QtGui import QFontDatabase
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
