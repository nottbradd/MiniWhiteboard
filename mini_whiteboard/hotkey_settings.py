"""Small settings window with explicit recording and an OS-independent selector."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QApplication)

from .hotkey_config import (ACTIONS, ACTION_NAMES, KEYS, Chord, HotkeyConfig,
                            compatibility, defaults, recorded_chord)
from .branding import app_icon


class HotkeySettings(QDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.mac = controller.platform.shortcuts.mac
        self.original = controller.hotkeys.configuration
        self.available = set(controller.hotkeys.registered)
        self.errors = dict(controller.hotkeys.errors)
        self.recording = None
        self.closed = False
        self.rows = {}
        self.setObjectName('hotkeySettings')
        self.setWindowTitle('Mini Whiteboard · Hotkeys')
        self.setWindowIcon(app_icon())
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(590)
        palette = QPalette(self.palette())
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            palette.setColor(role, QColor('#172033'))
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Button):
            palette.setColor(role, QColor('#f7f8fa'))
        palette.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.Highlight, QColor('#2563b8'))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
        self.setPalette(palette)
        self.setStyleSheet('QWidget { color: #172033; } QDialog { background: #f7f8fa; }'
                           'QGroupBox { font-weight: 600; margin-top: 10px; padding-top: 10px; border: 1px solid #d5dae3; border-radius: 6px; }'
                           'QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }'
                           'QPushButton, QComboBox { background: #ffffff; color: #172033; padding: 5px 8px; border: 1px solid #bac4d2; border-radius: 4px; }'
                           'QPushButton:hover { background: #e8f0fc; }'
                           'QPushButton:focus, QComboBox:focus { border-color: #2563b8; }'
                           'QComboBox QAbstractItemView { background: #ffffff; color: #172033; selection-background-color: #2563b8; selection-color: white; }'
                           'QLabel#hotkeyMessage { color: #a03522; }')
        layout = QVBoxLayout(self)
        title = QLabel('Global hotkeys')
        title.setStyleSheet('font-size: 19px; font-weight: 600; margin-bottom: 4px;')
        layout.addWidget(title)
        note = QLabel('Global actions are paused while this window is open.\n'
                      'Record a chord, or select its modifiers and key if another app intercepts it.')
        note.setWordWrap(True)
        layout.addWidget(note)
        names = (('ctrl', 'Control' if self.mac else 'Ctrl'), ('alt', 'Option' if self.mac else 'Alt'),
                 ('shift', 'Shift'), ('meta', 'Command' if self.mac else 'Win'))
        for identifier in ACTIONS:
            box = QGroupBox(ACTION_NAMES[identifier])
            grid = QGridLayout(box)
            checks = {}
            for column, (modifier, label) in enumerate(names):
                check = QCheckBox(label)
                check.setAccessibleName(ACTION_NAMES[identifier] + ' ' + label)
                checks[modifier] = check
                grid.addWidget(check, 0, column)
                check.toggled.connect(self.refresh_labels)
            keys = QComboBox()
            keys.addItems(KEYS)
            keys.setAccessibleName(ACTION_NAMES[identifier] + ' key')
            keys.currentTextChanged.connect(self.refresh_labels)
            grid.addWidget(keys, 0, 4)
            record = QPushButton('Record')
            record.setObjectName('record_' + str(identifier))
            record.setAccessibleName('Record ' + ACTION_NAMES[identifier])
            record.clicked.connect(lambda _checked=False, i=identifier: self.begin_recording(i))
            grid.addWidget(record, 0, 5)
            status = QLabel()
            status.setWordWrap(True)
            grid.addWidget(status, 1, 0, 1, 6)
            self.rows[identifier] = checks, keys, record, status
            layout.addWidget(box)
        presets = QHBoxLayout()
        if self.mac:
            preset = QPushButton('Alternate: Command+Option+Shift')
            preset.clicked.connect(lambda: self.load(defaults(True, 'alternate')))
        else:
            preset = QPushButton('Compatibility preset: Win+Alt+Shift+W/Q')
            preset.clicked.connect(lambda: self.load(compatibility(self.configuration())))
        presets.addWidget(preset)
        presets.addStretch()
        layout.addLayout(presets)
        self.message = QLabel('')
        self.message.setObjectName('hotkeyMessage')
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply |
                                   QDialogButtonBox.StandardButton.Cancel |
                                   QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText('Reset Defaults')
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(lambda: self.load(defaults(self.mac)))
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.load(self.original)
        self.controller.hotkeys.pause()
        QApplication.instance().installEventFilter(self)
        self.finished.connect(self.finish)

    def configuration(self):
        return HotkeyConfig(*(Chord(frozenset(m for m, c in self.rows[i][0].items() if c.isChecked()),
                                     self.rows[i][1].currentText()) for i in ACTIONS))

    def load(self, configuration):
        self.stop_recording()
        for identifier, chord in configuration.items():
            checks, keys, _record, _status = self.rows[identifier]
            for name, check in checks.items():
                check.setChecked(name in chord.modifiers)
            keys.setCurrentText(chord.key)
        if hasattr(self, 'message'):
            self.message.clear()
        self.refresh_labels()

    def refresh_labels(self, *_args):
        if len(self.rows) != 3:
            return
        config = self.configuration()
        for identifier, chord in config.items():
            if chord != self.original[identifier]:
                status = 'Not applied'
            elif identifier in self.available:
                status = 'Registered before pausing'
            else:
                status = 'Unavailable — ' + self.errors.get(identifier, 'not registered')
            self.rows[identifier][3].setText(chord.label(self.mac) + ' · ' + status)

    def begin_recording(self, identifier):
        self.stop_recording()
        # A failed Apply may have reclaimed the old bindings for rollback.
        self.controller.hotkeys.pause()
        self.recording = identifier
        self.rows[identifier][2].setText('Listening…')
        self.rows[identifier][2].setFocus()
        self.message.setText('Press a modifier + key. Esc stops recording. You can also select the controls above.')

    def stop_recording(self):
        if self.recording is not None:
            self.rows[self.recording][2].setText('Record')
            self.recording = None

    def eventFilter(self, watched, event):
        if self.recording is None:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            self.stop_recording()
            return False
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            event.accept()
            if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                if event.key() == Qt.Key.Key_Escape:
                    self.stop_recording()
                    self.message.setText('Recording stopped. Changes have not been applied.')
                else:
                    try:
                        chord = recorded_chord(event, self.mac)
                    except ValueError as error:
                        self.message.setText(str(error))
                    else:
                        identifier = self.recording
                        self.stop_recording()
                        checks, keys, *_ = self.rows[identifier]
                        for name, check in checks.items():
                            check.setChecked(name in chord.modifiers)
                        keys.setCurrentText(chord.key)
                        self.message.setText('Recorded. Release the keys, then choose Apply.')
            return True
        return False

    def apply(self):
        self.stop_recording()
        try:
            self.controller.apply_hotkey_configuration(self.configuration())
        except (ValueError, OSError) as error:
            self.message.setText(str(error))
            self.adjustSize()
            return
        self.accept()

    def finish(self, _result):
        if self.closed:
            return
        self.closed = True
        self.stop_recording()
        QApplication.instance().removeEventFilter(self)
        try:
            self.controller.hotkeys.resume()
        except OSError as error:
            self.controller.hotkey_error(str(error))
        self.controller.update_shortcut_labels()
        self.controller.rebuild_menu()
