"""Read-only asynchronous wait-chain observations for an owned GUI thread."""
import ctypes as C
from ctypes import wintypes as W


class LockInfo(C.Structure):
    _fields_ = [('name', W.WCHAR * 128), ('timeout', C.c_longlong), ('alertable', W.BOOL)]


class ThreadInfo(C.Structure):
    _fields_ = [('pid', W.DWORD), ('tid', W.DWORD), ('wait_ms', W.DWORD), ('switches', W.DWORD)]


class NodeData(C.Union):
    _fields_ = [('lock', LockInfo), ('thread', ThreadInfo)]


class Node(C.Structure):
    _fields_ = [('kind', C.c_int), ('status', C.c_int), ('data', NodeData)]


class WaitChainObserver:
    def __init__(self, record):
        self.record = record
        self.api = C.WinDLL('advapi32', use_last_error=True)
        callback_type = C.WINFUNCTYPE(None, W.HANDLE, C.c_size_t, W.DWORD,
                                     C.POINTER(W.DWORD), C.POINTER(Node), C.POINTER(W.BOOL))

        def callback(_handle, tid, error, count, nodes, cycle):
            result = []
            if not error and count and nodes:
                for node in nodes[:min(count.contents.value, 16)]:
                    row = {'kind': node.kind, 'status': node.status}
                    if node.kind == 8:  # WctThreadType
                        row.update(pid=node.data.thread.pid, tid=node.data.thread.tid,
                                   wait_ms=node.data.thread.wait_ms,
                                   context_switches=node.data.thread.switches)
                    result.append(row)
            record('wait-chain', gui_thread=tid, error=error, nodes=result,
                   cycle=bool(cycle.contents.value) if cycle else None)

        self.callback = callback_type(callback)
        self.api.OpenThreadWaitChainSession.argtypes = [W.DWORD, callback_type]
        self.api.OpenThreadWaitChainSession.restype = W.HANDLE
        self.api.GetThreadWaitChain.argtypes = [W.HANDLE, C.c_size_t, W.DWORD, W.DWORD,
                                               C.POINTER(W.DWORD), C.POINTER(Node), C.POINTER(W.BOOL)]
        self.api.GetThreadWaitChain.restype = W.BOOL
        self.api.CloseThreadWaitChainSession.argtypes = [W.HANDLE]
        self.api.CloseThreadWaitChainSession.restype = None
        self.handle = self.api.OpenThreadWaitChainSession(1, self.callback)  # async
        self.pending = []
        if not self.handle:
            record('wait-chain-unavailable', error=C.get_last_error())

    def observe(self, tid):
        if not self.handle:
            return
        count, nodes, cycle = W.DWORD(16), (Node * 16)(), W.BOOL()
        # Asynchronous output storage must live until callback/session closure.
        self.pending.append((count, nodes, cycle))
        ok = self.api.GetThreadWaitChain(self.handle, tid, 0, tid,
                                        C.byref(count), nodes, C.byref(cycle))
        error = 0 if ok else C.get_last_error()
        self.record('wait-chain-request', gui_thread=tid, error=error)

    def close(self):
        if self.handle:
            self.api.CloseThreadWaitChainSession(self.handle)
            self.handle = None
