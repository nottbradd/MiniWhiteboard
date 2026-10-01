"""Carbon RegisterEventHotKey: event driven, with explicit press/release state.

Bare Escape is temporary and shares this registration path. Its reliability
without Accessibility must pass scripts.macos_escape_probe on actual hardware.
"""
import ctypes as C
import sys

from PySide6.QtCore import Signal
from ..base import HotkeyEvents, CREATE_HOTKEY, CAPTURE_HOTKEY, ESCAPE_HOTKEY
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
            self.deliver(identifier.id, kind == 5)
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

    def close(self):
        if self.handler:
            self.remove(self.handler)
            self.handler = None


class MacHotkeyEvents(HotkeyEvents):
    warning = Signal(str)


class MacHotkeys:
    def __init__(self, app, preset="default", backend_factory=Carbon):
        self.events = MacHotkeyEvents()
        self.preset = preset
        self.handles = {}
        self.down = set()
        self.backend_factory = backend_factory
        self.backend = None
        self.escape_available = None

    @property
    def registered(self):
        return set(self.handles)

    def _ensure_backend(self):
        if self.backend is None:
            self.backend = self.backend_factory(self.deliver)

    def deliver(self, identifier, pressed):
        if not pressed:
            self.down.discard(identifier)
            return
        if identifier not in self.handles or identifier in self.down:
            return
        self.down.add(identifier)
        {CREATE_HOTKEY: self.events.create, CAPTURE_HOTKEY: self.events.capture,
         ESCAPE_HOTKEY: self.events.cancel}[identifier].emit()

    def start(self):
        self._ensure_backend()
        modifiers = (1 << 8 | 1 << 9 | 1 << 11) if self.preset == "alternate" else (1 << 12 | 1 << 11)
        failures = []
        for identifier, key, label in ((CREATE_HOTKEY, 13, "W"), (CAPTURE_HOTKEY, 1, "S")):
            if identifier in self.handles:
                continue
            try:
                self.handles[identifier] = self.backend.add(identifier, key, modifiers)
            except OSError as error:
                failures.append(f"{ShortcutPolicy(True, self.preset).global_label(label)}: {error}")
        if failures:
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
        for identifier in tuple(self.handles):
            self._unregister(identifier)
        if self.backend is not None:
            self.backend.close()
            self.backend = None
