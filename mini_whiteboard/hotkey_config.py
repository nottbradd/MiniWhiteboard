"""Validated global bindings; native adapters own registration, never tool keys."""
from dataclasses import dataclass, replace
import json

from PySide6.QtCore import Qt
from .platform.base import CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY

ACTIONS = (CREATE_HOTKEY, CAPTURE_HOTKEY, HIDE_HOTKEY)
ACTION_NAMES = dict(zip(ACTIONS, ('Create whiteboard', 'Screenshot / quick capture', 'Hide All / Restore All')))
KEYS = tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') + tuple(f'F{i}' for i in range(1, 13))
MODIFIERS = frozenset(('ctrl', 'alt', 'shift', 'meta'))


@dataclass(frozen=True)
class Chord:
    modifiers: frozenset
    key: str

    def __post_init__(self):
        object.__setattr__(self, 'modifiers', frozenset(self.modifiers))

    def validate(self):
        if self.key not in KEYS:
            raise ValueError('Choose one letter, number, or F1–F12 key.')
        if not self.modifiers <= MODIFIERS:
            raise ValueError('Unsupported modifier.')
        if not self.modifiers & {'ctrl', 'alt', 'meta'}:
            raise ValueError('Include Ctrl, Alt or Win (Control, Option or Command on Mac).')

    def label(self, mac=False):
        names = {'ctrl': 'Control' if mac else 'Ctrl', 'alt': 'Option' if mac else 'Alt',
                 'shift': 'Shift', 'meta': 'Command' if mac else 'Win'}
        order = ('ctrl', 'meta', 'alt', 'shift') if mac else ('ctrl', 'alt', 'shift', 'meta')
        return '+'.join([names[m] for m in order if m in self.modifiers] + [self.key])

    @property
    def qt_key(self):
        return int(getattr(Qt.Key, 'Key_' + self.key))

    @property
    def windows_key(self):
        return 0x70 + int(self.key[1:]) - 1 if self.key.startswith('F') and len(self.key) > 1 else ord(self.key)

    @property
    def windows_modifiers(self):
        return sum({'alt': 1, 'ctrl': 2, 'shift': 4, 'meta': 8}[m] for m in self.modifiers)

    @property
    def carbon_modifiers(self):
        return sum({'ctrl': 1 << 12, 'alt': 1 << 11, 'shift': 1 << 9, 'meta': 1 << 8}[m] for m in self.modifiers)


@dataclass(frozen=True)
class HotkeyConfig:
    create: Chord
    capture: Chord
    hide: Chord

    def items(self):
        return tuple(zip(ACTIONS, (self.create, self.capture, self.hide)))

    def __getitem__(self, identifier):
        return dict(self.items())[identifier]

    def validate(self):
        assigned = {}
        for identifier, chord in self.items():
            try:
                chord.validate()
            except ValueError as error:
                raise ValueError(f'{ACTION_NAMES[identifier]}: {error}') from error
            if chord in assigned:
                raise ValueError(f'{ACTION_NAMES[identifier]} duplicates {ACTION_NAMES[assigned[chord]]}. Choose different shortcuts.')
            assigned[chord] = identifier
        return self

    def with_hide(self, chord):
        return replace(self, hide=chord)

    def to_json(self):
        return json.dumps({'version': 1, 'bindings': [
            {'modifiers': sorted(chord.modifiers), 'key': chord.key} for _, chord in self.items()]})

    @classmethod
    def from_json(cls, text):
        try:
            data = json.loads(text)
            if data['version'] != 1 or len(data['bindings']) != 3:
                raise ValueError('Unknown hotkey configuration.')
            return cls(*(Chord(frozenset(c['modifiers']), c['key']) for c in data['bindings'])).validate()
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid saved hotkeys.') from error


def defaults(mac=False, preset='default', hide='default'):
    creation = frozenset(('meta', 'alt', 'shift') if preset == 'alternate' else ('ctrl', 'alt')) if mac else frozenset(('shift', 'meta'))
    hiding = creation if mac else frozenset(('ctrl', 'alt', 'shift') if hide == 'shift' else ('ctrl', 'alt'))
    return HotkeyConfig(Chord(creation, 'W'), Chord(creation, 'S' if mac else 'Q'), Chord(hiding, 'H'))


def compatibility(config):
    modifiers = frozenset(('meta', 'alt', 'shift'))
    return HotkeyConfig(Chord(modifiers, 'W'), Chord(modifiers, 'Q'), config.hide)


def recorded_chord(event, mac=False):
    key = next((name for name in KEYS if int(getattr(Qt.Key, 'Key_' + name)) == event.key()), None)
    if key is None:
        raise ValueError('Press a letter, number, or F1–F12 with modifiers, or select it below.')
    flags = event.modifiers()
    mapping = ((Qt.KeyboardModifier.ControlModifier, 'meta' if mac else 'ctrl'),
               (Qt.KeyboardModifier.MetaModifier, 'ctrl' if mac else 'meta'),
               (Qt.KeyboardModifier.AltModifier, 'alt'), (Qt.KeyboardModifier.ShiftModifier, 'shift'))
    chord = Chord(frozenset(name for flag, name in mapping if flags & flag), key)
    chord.validate()
    return chord


class ConfigurableHotkeys:
    """A failed apply rolls back registrations; persistence is the caller's job.

    Native registration cannot be atomic across three OS calls. Unchanged owned
    bindings stay registered where possible; swapped keys are released together.
    Rollback failures are reported and reflected in ``registered``, never hidden.
    """
    mac = False

    def initialize_configuration(self, configuration):
        self.configuration = configuration.validate()
        self.paused = False
        self._resume_ids = set()
        self.errors = {}

    def _refresh_tracking(self):
        self.hold.trigger_keys = {}
        for identifier, chord in self.configuration.items()[:2]:
            self.hold.trigger_keys.setdefault(chord.qt_key, set()).add(identifier)
        self.hide_latch.trigger_key = self.configuration.hide.qt_key

    def _quiesce(self):
        self.events.cancel.emit()
        self.disable_escape()
        self.hold.active = None
        self.hold.blocked.clear()
        self.hold.timer.stop()
        self.hide_latch.held = False
        self.hide_latch.timer.stop()
        for identifier in ACTIONS:
            self.record_release(identifier)

    def configure(self, configuration):
        """Startup only: load preferences before making any registrations."""
        if self.registered:
            raise RuntimeError('Use apply_configuration for active shortcuts.')
        self.configuration = configuration.validate()
        self._refresh_tracking()

    def start(self):
        failures = {}
        for identifier, chord in self.configuration.items():
            if identifier in self.registered:
                continue
            try:
                self._register_chord(identifier, chord)
            except OSError as error:
                failures[identifier] = str(error)
        self.errors = failures
        if failures:
            raise OSError('\n'.join(f'{ACTION_NAMES[i]} — {self.configuration[i].label(self.mac)}: {e}' for i, e in failures.items()))

    def pause(self):
        if not self.paused:
            self._resume_ids = set(self.registered) & set(ACTIONS)
        self.paused = True
        self._quiesce()
        for identifier in ACTIONS:
            self._unregister(identifier)

    def resume(self):
        self._quiesce()
        try:
            self.start()
        finally:
            # Reject queued settings-time activations and drain any keys still
            # held on close before allowing a fresh gesture.
            self._drain_held_keys()
            for identifier in ACTIONS:
                self.record_release(identifier)
            self.paused = False

    def _drain_held_keys(self):
        down = self.sample()[0]
        self.hold.blocked.update(down)
        if down:
            self.hold.timer.start()
        if self.hide_latch.is_down():
            self.hide_latch.held = True
            self.hide_latch.timer.start()

    def apply_configuration(self, configuration):
        configuration.validate()
        old, was_paused = self.configuration, self.paused
        working = self._resume_ids if was_paused else set(self.registered) & set(ACTIONS)
        self.paused = True
        self._quiesce()
        changed = {i for i in ACTIONS if old[i] != configuration[i]}
        for identifier in changed:
            self._unregister(identifier)
        self.configuration = configuration
        self._refresh_tracking()
        try:
            self.start()
        except OSError as error:
            failed = str(error)
            for identifier in ACTIONS:
                if identifier in changed or identifier not in working:
                    self._unregister(identifier)
            self.configuration = old
            self._refresh_tracking()
            rollback = []
            for identifier in working:
                if identifier not in self.registered:
                    try:
                        self._register_chord(identifier, old[identifier])
                    except OSError as restore_error:
                        rollback.append(f'{ACTION_NAMES[identifier]}: {restore_error}')
            self.errors = {i: 'Unavailable' for i in ACTIONS if i not in self.registered}
            explanation = ('Previous working shortcuts restored.' if not rollback else
                           'Could not restore: ' + '; '.join(rollback) + '. Use Settings → Hotkeys to retry.')
            raise OSError(f'{failed}\nChanges were not saved. {explanation}') from error
        finally:
            self.paused = was_paused
            if not was_paused:
                self._drain_held_keys()
        self._resume_ids = set(ACTIONS)
