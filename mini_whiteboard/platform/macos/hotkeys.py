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

    def sample(self, required):
        # Carbon hardware state works in the background without an event tap,
        # Accessibility prompt, or Input Monitoring subscription.
        keys = (C.c_uint32*4)()
        self.keys(keys)
        down = {identifier for identifier, code in ((CREATE_HOTKEY, 13), (CAPTURE_HOTKEY, 1))
                if keys[code//32] & (1 << (code % 32))}
        complete = self.modifiers() & required == required
        return down, down if complete else set(), bool(keys[53//32] & (1 << (53 % 32)))

    def hide_key_down(self):
        keys = (C.c_uint32*4)()
        self.keys(keys)
        return bool(keys[0] & (1 << 4))

    def close(self):
        if self.handler:
            self.remove(self.handler)
            self.handler = None


class MacHotkeys:
    def __init__(self, app, preset="default", backend_factory=Carbon):
        self.events = HotkeyEvents()
        self.preset = preset
        self.handles = {}
        self.down = set()
        self.backend_factory = backend_factory
        self.backend = None
        self.escape_available = None
        self.hold = HoldTracker(app, self.events, self.sample)
        self.hide_latch = ToggleLatch(app, self.events.hide_toggle,
                                      lambda: self.backend.hide_key_down())
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
        return self.backend.sample(self.modifiers)

    @property
    def registered(self):
        return set(self.handles)

    def _ensure_backend(self):
        if self.backend is None:
            self.backend = self.backend_factory(self.deliver)

    def deliver(self, identifier, pressed, stamp=None):
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

    def start(self):
        self._ensure_backend()
        modifiers = self.modifiers
        failures = []
        for identifier, key, label in ((CREATE_HOTKEY, 13, "W"), (CAPTURE_HOTKEY, 1, "S"), (HIDE_HOTKEY, 4, "H")):
            if identifier in self.handles:
                continue
            try:
                self.handles[identifier] = self.backend.add(identifier, key, modifiers)
            except OSError as error:
                failures.append(f"{ShortcutPolicy(True, self.preset).global_label(label)}: {error}")
        if failures:
            self.events.cancel.emit()
            raise OSError("; ".join(failures))

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

    def close(self):
        self.events.cancel.emit()
        self.hold.close()
        self.hide_latch.close()
        for identifier in tuple(self.handles):
            self._unregister(identifier)
        if self.backend is not None:
            self.backend.close()
            self.backend = None
