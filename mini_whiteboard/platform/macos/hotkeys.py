"""Carbon RegisterEventHotKey: event driven, with explicit press/release state.

Bare Escape is temporary and shares this registration path. Its reliability
without Accessibility must pass scripts.macos_escape_probe on actual hardware.
"""
import ctypes as C
import sys

from ..base import HotkeyEvents, CREATE_HOTKEY, CAPTURE_HOTKEY, ESCAPE_HOTKEY, HIDE_HOTKEY
from ..hold import HoldTracker
from ..toggle import ToggleLatch
from ...shortcuts import ShortcutPolicy
from ...hotkey_config import ConfigurableHotkeys, defaults

# Carbon virtual key codes (ANSI letter positions, as used by the original presets).
CARBON_KEYS = dict(zip('ASDFHGZXCVBQWERYT12346597' + '80OUIP',
                      (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17,
                       18, 19, 20, 21, 22, 23, 25, 26, 28, 29, 31, 32, 34, 35)))
CARBON_KEYS.update({'L': 37, 'J': 38, 'K': 40, 'N': 45, 'M': 46,
                    **dict(zip((f'F{i}' for i in range(1, 13)), (122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111)))})


def fourcc(text):
    return int.from_bytes(text.encode("ascii"), "big")


class EventType(C.Structure):
    _fields_ = [("eventClass", C.c_uint32), ("eventKind", C.c_uint32)]


class HotkeyID(C.Structure):
    _fields_ = [("signature", C.c_uint32), ("id", C.c_uint32)]


class Carbon:
    signature = fourcc("MWbd")
    callback_type = C.CFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p, C.c_void_p)

    def __init__(self, deliver):
        if sys.platform != "darwin":
            raise OSError("Carbon hotkeys require macOS.")
        self.library = C.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        def bind(name, result, *args):
            function = getattr(self.library, name)
            function.restype, function.argtypes = result, args
            return function
        self.target = bind("GetEventDispatcherTarget", C.c_void_p)()
        self.register = bind("RegisterEventHotKey", C.c_int32, C.c_uint32, C.c_uint32,
                             HotkeyID, C.c_void_p, C.c_uint32, C.POINTER(C.c_void_p))
        self.unregister = bind("UnregisterEventHotKey", C.c_int32, C.c_void_p)
        self.remove = bind("RemoveEventHandler", C.c_int32, C.c_void_p)
        self.kind = bind("GetEventKind", C.c_uint32, C.c_void_p)
        self.event_time = bind("GetEventTime", C.c_double, C.c_void_p)
        self.clock = bind("GetCurrentEventTime", C.c_double)
        self.modifiers = bind("GetCurrentKeyModifiers", C.c_uint32)
        self.keys = bind("GetKeys", None, C.POINTER(C.c_uint32))
        self.parameter = bind("GetEventParameter", C.c_int32, C.c_void_p, C.c_uint32,
                              C.c_uint32, C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p)
        install = bind("InstallEventHandler", C.c_int32, C.c_void_p, self.callback_type,
                       C.c_uint32, C.POINTER(EventType), C.c_void_p, C.POINTER(C.c_void_p))
        self.deliver = deliver
        self.callback = self.callback_type(self._event)
        event_types = (EventType*2)(EventType(fourcc("keyb"), 5), EventType(fourcc("keyb"), 6))
        self.handler = C.c_void_p()
        status = install(self.target, self.callback, 2, event_types, None, C.byref(self.handler))
        if status:
            raise OSError(f"Installing the global shortcut handler failed (OSStatus {status}).")

    def _event(self, _call, event, _data):
        identifier = HotkeyID()
        status = self.parameter(event, fourcc("----"), fourcc("hkid"), None,
                                C.sizeof(identifier), None, C.byref(identifier))
        if status or identifier.signature != self.signature:
            return -9874  # eventNotHandledErr
        kind = self.kind(event)
        if kind not in (5, 6):
            return -9874
        try:
            self.deliver(identifier.id, kind == 5, self.event_time(event))
        except Exception:
            sys.excepthook(*sys.exc_info())
        return 0

    def add(self, identifier, key, modifiers):
        handle = C.c_void_p()
        status = self.register(key, modifiers, HotkeyID(self.signature, identifier),
                               self.target, 0, C.byref(handle))
        if status:
            raise OSError(f"OSStatus {status}")
        return handle

    def discard(self, handle):
        self.unregister(handle)

    def sample(self, bindings):
        # Carbon hardware state works in the background without an event tap,
        # Accessibility prompt, or Input Monitoring subscription.
        keys = (C.c_uint32*4)()
        self.keys(keys)
        down = {identifier for identifier, (code, _required) in bindings.items()
                if keys[code//32] & (1 << (code % 32))}
        held = self.modifiers()
        complete = {identifier for identifier in down if held & bindings[identifier][1] == bindings[identifier][1]}
        return down, complete, bool(keys[53//32] & (1 << (53 % 32)))

    def key_down(self, code):
        keys = (C.c_uint32*4)()
        self.keys(keys)
        return bool(keys[code//32] & (1 << (code % 32)))

    def close(self):
        if self.handler:
            self.remove(self.handler)
            self.handler = None


class MacHotkeys(ConfigurableHotkeys):
    mac = True
    def __init__(self, app, preset="default", backend_factory=Carbon):
        self.events = HotkeyEvents()
        self.preset = preset
        self.initialize_configuration(defaults(True, preset))
        self.handles = {}
        self.down = set()
        self.backend_factory = backend_factory
        self.backend = None
        self.escape_available = None
        self.hold = HoldTracker(app, self.events, self.sample)
        self.hide_latch = ToggleLatch(app, self.events.hide_toggle,
                                      lambda: self.backend.key_down(CARBON_KEYS[self.configuration.hide.key]))
        self._refresh_tracking()
        self.hide_latch.released.connect(lambda: self.record_release(HIDE_HOTKEY))
        self.last_activation = {}
        self.press_time = {}
        self.last_release = {}
        self.events.create_released.connect(lambda: self.record_release(CREATE_HOTKEY))
        self.events.capture_released.connect(lambda: self.record_release(CAPTURE_HOTKEY))

    def record_release(self, identifier):
        if self.backend is not None:
            self.last_release[identifier] = max(self.last_release.get(identifier, 0), self.backend.clock())

    @property
    def modifiers(self):
        return (1 << 8 | 1 << 9 | 1 << 11) if self.preset == "alternate" else (1 << 12 | 1 << 11)

    def sample(self):
        self._ensure_backend()
        return self.backend.sample({i: (CARBON_KEYS[chord.key], chord.carbon_modifiers)
                                    for i, chord in self.configuration.items()[:2]})

    @property
    def registered(self):
        return set(self.handles)

    def _ensure_backend(self):
        if self.backend is None:
            self.backend = self.backend_factory(self.deliver)

    def deliver(self, identifier, pressed, stamp=None):
        if self.paused:
            return
        if not pressed:
            if stamp is not None and stamp < self.press_time.get(identifier, 0):
                return
            self.down.discard(identifier)
            if stamp is not None:
                self.last_release[identifier] = max(stamp, self.last_release.get(identifier, 0))
            if identifier == HIDE_HOTKEY:
                self.hide_latch.poll()
            else:
                self.hold.release(identifier)
            return
        if identifier not in self.handles:
            return
        if stamp is not None:
            if stamp <= max(self.last_activation.get(identifier, -1), self.last_release.get(identifier, -1)):
                return
            self.last_activation[identifier] = self.press_time[identifier] = stamp
        if identifier == HIDE_HOTKEY:
            self.hide_latch.activate()
            return
        if identifier != ESCAPE_HOTKEY:
            self.hold.activate(identifier)
            return
        if identifier in self.down:
            return
        self.down.add(identifier)
        self.events.cancel.emit()

    def _register_chord(self, identifier, chord):
        self._ensure_backend()
        self.handles[identifier] = self.backend.add(identifier, CARBON_KEYS[chord.key], chord.carbon_modifiers)

    def enable_escape(self):
        self._ensure_backend()
        if ESCAPE_HOTKEY in self.handles:
            return True
        try:
            self.handles[ESCAPE_HOTKEY] = self.backend.add(ESCAPE_HOTKEY, 53, 0)
            self.escape_available = True
            return True
        except OSError as error:
            self.escape_available = False
            self.events.warning.emit("Global Escape could not be registered. Cancel this selection from "
                                     f"Mini Whiteboard's menu-bar menu. {error}")
            return False

    def disable_escape(self):
        self._unregister(ESCAPE_HOTKEY)

    def _unregister(self, identifier):
        handle = self.handles.pop(identifier, None)
        if handle is not None:
            self.backend.discard(handle)
        self.down.discard(identifier)

    def set_preset(self, preset):
        if preset not in ("default", "alternate"):
            raise ValueError("Unknown global shortcut preset.")
        for identifier in tuple(self.handles):
            self._unregister(identifier)
        self.preset = preset
        self.configuration = defaults(True, preset)
        self._refresh_tracking()

    def close(self):
        self.events.cancel.emit()
        self.hold.close()
        self.hide_latch.close()
        for identifier in tuple(self.handles):
            self._unregister(identifier)
        if self.backend is not None:
            self.backend.close()
            self.backend = None
