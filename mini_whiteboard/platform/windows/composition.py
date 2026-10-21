"""Small ABI bridge to Windows.UI.Composition; no desktop readback or extra runtime.

The interface IDs/slots are the public Windows SDK contracts. A host backdrop
brush samples behind its HWND. RectangleClip applies the same physical radius
as the Qt surface, unlike DWM's discrete system-backdrop corner preferences.
"""
import ctypes as C
from ctypes import wintypes as W
import uuid

POINTER = C.c_void_p
HRESULT = C.c_long


class Guid(C.Structure):
    _fields_ = [('bytes', C.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__((C.c_ubyte * 16).from_buffer_copy(uuid.UUID(value).bytes_le))


class Vector2(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float)]


def check(result):
    if result < 0:
        raise OSError(f'Windows composition failed (0x{result & 0xffffffff:08x}).')


class Interface:
    """One owned COM reference. Call signatures are explicit at each boundary."""
    def __init__(self, pointer):
        self.pointer = pointer

    def call(self, slot, types=(), values=(), result=HRESULT):
        table = C.cast(self.pointer, C.POINTER(C.POINTER(POINTER))).contents
        function = C.WINFUNCTYPE(result, POINTER, *types)(table[slot])
        status = function(self.pointer, *values)
        if result == HRESULT:
            check(status)
        return status

    def query(self, identifier):
        pointer = POINTER()
        self.call(0, (C.POINTER(Guid), C.POINTER(POINTER)),
                  (C.byref(Guid(identifier)), C.byref(pointer)))
        return Interface(pointer)

    def create(self, slot, types=(), values=()):
        pointer = POINTER()
        self.call(slot, (*types, C.POINTER(POINTER)), (*values, C.byref(pointer)))
        return Interface(pointer)

    def release(self):
        if self.pointer:
            self.call(2, result=W.ULONG)
            self.pointer = None


class Dispatcher:
    """One lazy queue on Qt's GUI thread, using its existing Windows message loop."""
    def __init__(self):
        from PySide6.QtCore import QCoreApplication
        self.core = C.WinDLL('combase')
        self.closed = False
        initialize = self.core.RoInitialize
        initialize.argtypes, initialize.restype = [W.UINT], HRESULT
        check(initialize(0))  # Qt/OLE uses this same single-threaded apartment.
        self.controller = None
        try:
            class Options(C.Structure):
                _fields_ = [('size', W.DWORD), ('thread', C.c_int), ('apartment', C.c_int)]
            create = C.WinDLL('CoreMessaging').CreateDispatcherQueueController
            create.argtypes, create.restype = [Options, C.POINTER(POINTER)], HRESULT
            pointer = POINTER()
            check(create(Options(C.sizeof(Options), 2, 0), C.byref(pointer)))
            self.controller = Interface(pointer)
            QCoreApplication.instance().aboutToQuit.connect(self.close)
        except Exception:
            self.close()
            raise

    def compositor(self):
        name = 'Windows.UI.Composition.Compositor'
        string, pointer = POINTER(), POINTER()
        create = self.core.WindowsCreateString
        create.argtypes, create.restype = [W.LPCWSTR, W.UINT, C.POINTER(POINTER)], HRESULT
        check(create(name, len(name), C.byref(string)))
        try:
            activate = self.core.RoActivateInstance
            activate.argtypes, activate.restype = [POINTER, C.POINTER(POINTER)], HRESULT
            check(activate(string, C.byref(pointer)))
        finally:
            delete = self.core.WindowsDeleteString
            delete.argtypes, delete.restype = [POINTER], HRESULT
            delete(string)
        return Interface(pointer)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.controller is not None:
            # ShutdownQueueAsync is part of IDispatcherQueueController. No
            # recurring timer or private event loop is needed during app life.
            operation = self.controller.create(7)
            operation.release()
            self.controller.release()
            self.controller = None
        uninitialize = self.core.RoUninitialize
        uninitialize.argtypes, uninitialize.restype = [], None
        uninitialize()


_dispatcher = None


class RoundedBackdrop:
    def __init__(self, handle):
        global _dispatcher
        if _dispatcher is None:
            _dispatcher = Dispatcher()
        self.references = []
        self.compositor = None
        self.target = None
        self.dimensions = None
        try:
            own = self.own
            self.compositor = own(_dispatcher.compositor())
            compositor = own(self.compositor.query('b403ca50-7f8c-4e83-985f-cc45060036d8'))
            interop = own(self.compositor.query('29e691fa-4567-4dca-b319-d0f207eb6807'))
            desktop_target = own(interop.create(3, (W.HWND, W.BOOL), (handle, False)))
            self.target = own(desktop_target.query('a1bea8ba-d726-4663-8129-6b5e7927ffa6'))
            sprite = own(compositor.create(22))
            self.visual = own(sprite.query('117e202d-a859-4c89-873b-c2aa566788e3'))
            compositor3 = own(self.compositor.query('c9dd8ef0-6eb1-4e3c-a658-675d9c64d4ab'))
            backdrop = own(compositor3.create(6))
            brush = own(backdrop.query('ab0d7608-30c0-40e9-b568-b60a6bd1fb46'))
            sprite.call(7, (POINTER,), (brush.pointer,))
            compositor7 = own(self.compositor.query('d3483fad-9a12-53ba-bfc8-88b7ff7977c6'))
            self.clip = own(compositor7.create(8))
            clip = own(self.clip.query('1ccd2a52-cfc7-4ace-9983-146bb8eb6a3c'))
            self.visual.call(15, (POINTER,), (clip.pointer,))
            self.target.call(7, (POINTER,), (self.visual.pointer,))
        except Exception:
            self.close()
            raise

    def own(self, reference):
        self.references.append(reference)
        return reference

    def resize(self, width, height, radius):
        dimensions = width, height, radius
        if dimensions == self.dimensions:
            return
        self.visual.call(36, (Vector2,), (Vector2(width, height),))
        # Keep the compositor's antialiased coverage inside the painted rim.
        # This is one physical pixel, covered by that rim at every DPI, not a
        # separately inset rectangular panel. Corner centres remain identical.
        for slot,value in ((7,height-1),(13,1),(15,width-1),(17,1)):
            self.clip.call(slot, (C.c_float,), (value,))
        for slot in (9, 11, 19, 21):
            self.clip.call(slot, (Vector2,), (Vector2(max(0,radius-1),max(0,radius-1)),))
        self.dimensions = dimensions

    def close(self):
        try:
            if self.target is not None:
                self.target.call(7, (POINTER,), (None,))
            if self.compositor is not None:
                closable = self.compositor.query('30d5a829-7fa4-4026-83bb-d75bae4ea99e')
                try:
                    closable.call(6)  # IClosable.Close: detach native composition resources.
                finally:
                    closable.release()
        finally:
            for reference in reversed(self.references):
                reference.release()
            self.references.clear()
            self.target = self.compositor = None
