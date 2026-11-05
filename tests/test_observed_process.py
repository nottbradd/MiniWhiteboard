import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.observed_process import run


class ObservedProcessTests(unittest.TestCase):
    def test_preserves_output_arguments_and_failure_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'operation'
            result = run([sys.executable, '-c',
                          'import sys; print(sys.argv[1],flush=True); print("error",file=sys.stderr); sys.exit(7)',
                          'a path with spaces'], output, 'failing-command', 5)
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['exit_code'], 7)
            self.assertIn('a path with spaces', (output/'stdout.txt').read_text())
            self.assertIn('error', (output/'stderr.txt').read_text())
            self.assertEqual(json.loads((output/'result.json').read_text())['status'], 'FAILED')

    def test_timeout_retains_partial_output_and_returns_promptly(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'operation'
            result = run([sys.executable, '-c',
                          'import time; print("before stall",flush=True); time.sleep(60)'],
                         output, 'stalled-command', 1)
            self.assertEqual(result['status'], 'TIMED OUT')
            self.assertLess(result['elapsed_seconds'], 8)
            self.assertIn('before stall', (output/'stdout.txt').read_text())
            events = [json.loads(line)['event'] for line in (output.parent/'progress.jsonl').read_text().splitlines()]
            self.assertIn('timeout', events)
            self.assertEqual(events[-1], 'end')

    @unittest.skipUnless(os.name == 'nt', 'Windows process-tree cleanup')
    def test_timeout_stops_owned_descendant(self):
        import ctypes
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'operation'
            code = ('import subprocess,sys,time; '
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],'
                    'creationflags=subprocess.CREATE_NO_WINDOW); '
                    'print(p.pid,flush=True); time.sleep(60)')
            result = run([sys.executable, '-c', code], output, 'owned-tree', 2)
            self.assertEqual(result['status'], 'TIMED OUT')
            pid = int((output/'stdout.txt').read_text().strip())
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel.WaitForSingleObject.restype = ctypes.c_uint32
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x00100000, False, pid)
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0)
                finally:
                    kernel.CloseHandle(handle)


if __name__ == '__main__':
    unittest.main()
