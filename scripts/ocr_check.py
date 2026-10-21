"""Real source/frozen OCR, restricted lookup paths, exact fixtures and bounded cleanup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from mini_whiteboard.clipboard import encode
from mini_whiteboard.images import from_image, read_bytes
from mini_whiteboard import APP_VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--output', type=Path, default=Path('verification/ocr-check.json'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [str(args.executable.resolve())] if args.executable else [sys.executable, str(root/'main.py')]
    expected = 'MINI WHITEBOARD\nMeeting 42: Ready!\nhttps://example.com/plan'
    results = []
    environment = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'TESSDATA_PREFIX'):
        environment.pop(key, None)
    if sys.platform == 'win32':
        environment['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
    else:
        environment['PATH'] = '/usr/bin:/bin'
    environment.update(TESSDATA_PREFIX='/nonexistent/system-tesseract', OMP_THREAD_LIMIT='1',
                       OMP_NUM_THREADS='1', MINIWHITEBOARD_OCR_DENY_NETWORK='1')
    try:
        with tempfile.TemporaryDirectory(prefix='Mini Whiteboard 文件 ') as temporary:
            directory = Path(temporary)
            for name in ('clean', 'dark', 'transparent'):
                image = from_image(read_bytes((root/'tests/fixtures/ocr'/f'{name}.png').read_bytes()))
                request, response = directory/'request.json', directory/'result.json'
                request.write_text(json.dumps({'image': encode((image,), 'diagnostic').decode()}), encoding='utf-8')
                started = time.perf_counter()
                process = subprocess.run(command+['--ocr-worker', str(request), str(response)],
                    env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=25,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                data = json.loads(response.read_text(encoding='utf-8'))
                passed = process.returncode == 0 and not data['error'] and data['text'] == expected and data['version'] == APP_VERSION
                results.append({'fixture': name, 'exact_match': passed, 'seconds': time.perf_counter()-started})
                if not passed:
                    raise RuntimeError(f'{name} OCR did not match the ground truth: {data!r}')
    finally:
        report = {'version': APP_VERSION, 'platform': platform.platform(), 'architecture': platform.machine(),
                  'frozen': bool(args.executable), 'restricted_path': True,
                  'network_audit_guard': True, 'unicode_space_paths': True,
                  'status': 'PASSED' if len(results) == 3 and all(r['exact_match'] for r in results) else 'FAILED',
                  'results': results}
        if args.executable:
            report['executable_sha256'] = hashlib.sha256(args.executable.read_bytes()).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
