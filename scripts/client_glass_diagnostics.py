"""Read-only native observations; source instrumentation never changes frozen bytes."""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import time


def window_state(pid):
    """Preserve duplicate backdrop HWNDs and their actual desktop stacking order."""
    u=C.WinDLL('user32',use_last_error=True)
    callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    signatures={
        'GetWindowThreadProcessId':(W.DWORD,[W.HWND,C.POINTER(W.DWORD)]),
        'GetWindowTextW':(C.c_int,[W.HWND,W.LPWSTR,C.c_int]),
        'GetClassNameW':(C.c_int,[W.HWND,W.LPWSTR,C.c_int]),
        'GetWindowRect':(W.BOOL,[W.HWND,C.POINTER(W.RECT)]),
        'GetWindowLongPtrW':(C.c_ssize_t,[W.HWND,C.c_int]),
        'GetWindow':(W.HWND,[W.HWND,W.UINT]),
        'IsWindowVisible':(W.BOOL,[W.HWND]),
        'GetForegroundWindow':(W.HWND,[]),
        'EnumWindows':(W.BOOL,[callback,W.LPARAM]),
    }
    for name,(result,args) in signatures.items():
        function=getattr(u,name);function.restype=result;function.argtypes=args
    dwm=C.WinDLL('dwmapi').DwmGetWindowAttribute
    dwm.restype=C.c_long;dwm.argtypes=[W.HWND,W.DWORD,C.c_void_p,W.DWORD]
    rows=[];order=0
    @callback
    def visit(hwnd,_):
        nonlocal order
        order+=1;process=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(process))
        if process.value!=pid:return True
        title=C.create_unicode_buffer(256);u.GetWindowTextW(hwnd,title,len(title))
        kind=C.create_unicode_buffer(256);u.GetClassNameW(hwnd,kind,len(kind))
        rect=W.RECT();u.GetWindowRect(hwnd,C.byref(rect))
        cloaked=W.DWORD();status=dwm(hwnd,14,C.byref(cloaked),C.sizeof(cloaked))
        rows.append(dict(hwnd=int(hwnd),pid=pid,title=title.value,class_name=kind.value,
            visible=bool(u.IsWindowVisible(hwnd)),z_order=order,owner=u.GetWindow(hwnd,4),
            previous=u.GetWindow(hwnd,3),next=u.GetWindow(hwnd,2),
            style=hex(u.GetWindowLongPtrW(hwnd,-16)&0xffffffff),
            extended_style=hex(u.GetWindowLongPtrW(hwnd,-20)&0xffffffff),
            rectangle=[rect.left,rect.top,rect.right,rect.bottom],
            cloaked=dict(hresult=hex(status&0xffffffff),value=cloaked.value)))
        return True
    u.EnumWindows(visit,0)
    return dict(utc=datetime.now(timezone.utc).isoformat(),foreground=u.GetForegroundWindow(),windows=rows)


def wait_visible_window(pid,pump,seconds=8,background_kind=None):
    """Observe a real painted background instead of assuming a cold-start delay."""
    send=C.WinDLL('user32').SendMessageTimeoutW
    send.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,C.POINTER(C.c_size_t)]
    send.restype=C.c_size_t
    started=time.monotonic();state=None
    while time.monotonic()-started<seconds:
        pump();state=window_state(pid)
        for window in state['windows']:
            result=C.c_size_t()
            if window['visible'] and send(window['hwnd'],0,0,0,2,100,C.byref(result)):
                if background_kind is not None:
                    from PySide6.QtGui import QGuiApplication
                    from mini_whiteboard import windows as native
                    from mini_whiteboard.geometry import Rect
                    scale=QGuiApplication.instance().primaryScreen().devicePixelRatio()
                    left,top,_,_=window['rectangle']
                    # Left of the fixture's text: opaque fill, independent of
                    # font rendering, gradients and the native window shadow.
                    pixel=native.capture_rect(Rect(round(left+10*scale),round(top+100*scale),1,1)).pixelColor(0,0)
                    expected=(245,247,251) if background_kind=='light' else (220,196,219)
                    if pixel.getRgb()[:3]!=expected:continue
                return dict(ready_ms=(time.monotonic()-started)*1000,state=state)
        time.sleep(.025)
    raise TimeoutError('Owned background did not become visible and responsive: '+repr(state))


def d3d11_devices():
    """Independent capability probe, not a claim about WUC's private device."""
    create=C.WinDLL('d3d11').D3D11CreateDevice
    create.restype=C.c_long
    create.argtypes=[C.c_void_p,C.c_int,W.HMODULE,W.UINT,C.POINTER(W.UINT),W.UINT,W.UINT,
                     C.POINTER(C.c_void_p),C.POINTER(W.UINT),C.POINTER(C.c_void_p)]
    rows=[]
    for name,kind in (('default hardware adapter',1),('WARP software',5)):
        device=C.c_void_p();context=C.c_void_p();level=W.UINT()
        status=create(None,kind,None,0,None,0,7,C.byref(device),C.byref(level),C.byref(context))
        rows.append(dict(request=name,hresult=hex(status&0xffffffff),feature_level=hex(level.value),
                         device_created=bool(device.value)))
        for pointer in (context,device):
            if pointer.value:
                table=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
                C.WINFUNCTYPE(W.ULONG,C.c_void_p)(table[2])(pointer)
    return dict(scope='Separate D3D11 capability probes; WUC compositor owns its internal device',results=rows)


def instrument_source(report,save):
    """Record real source-only API results, including errors swallowed by fallback."""
    from mini_whiteboard.platform.windows import appearance,composition,native
    events=report.setdefault('source_api_events',[])
    def event(name,**data):
        events.append(dict(monotonic=time.monotonic(),operation=name,**data))
    original_bind=native.bind
    def bind(library,name,*signature):
        function=original_bind(library,name,*signature)
        if name not in ('CreateWindowExW','SetLayeredWindowAttributes','DwmSetWindowAttribute','DestroyWindow'):
            return function
        def observed(*args):
            result=function(*args)
            event(name,result=result,last_error=C.get_last_error())
            return result
        return observed
    native.bind=bind
    original_call=composition.Interface.call
    def call(self,slot,types=(),values=(),result=composition.HRESULT):
        try:
            status=original_call(self,slot,types,values,result)
            event('composition.Interface.call',interface=getattr(self,'diagnostic_name','unknown'),slot=slot,result=status)
            return status
        except Exception as error:
            event('composition.Interface.call',interface=getattr(self,'diagnostic_name','unknown'),slot=slot,error=repr(error))
            save();raise
    composition.Interface.call=call
    original_query=composition.Interface.query
    def query(self,identifier):
        value=original_query(self,identifier);value.diagnostic_name=identifier;return value
    composition.Interface.query=query
    original_host=appearance.BackdropHost
    class ObservedHost(original_host):
        def __init__(self,board):
            event('host.create.start',owner=int(board.winId()),title=board.windowTitle())
            try:
                super().__init__(board)
                event('host.create.complete',owner=self.owner,handle=self.handle)
            except Exception as error:
                event('host.create.failed',error=repr(error));raise
            finally:save()
        def sync(self,board):
            try:
                super().sync(board)
                event('host.sync',owner=self.owner,handle=self.handle,dimensions=self.effect.dimensions)
            except Exception as error:
                event('host.sync.failed',error=repr(error));save();raise
        def close(self):
            event('host.close',owner=self.owner,handle=self.handle)
            super().close();save()
    appearance.BackdropHost=ObservedHost
