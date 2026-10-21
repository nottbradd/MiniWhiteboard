"""One application-wide worker and one waiting request, with queued GUI results."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
import time
from uuid import uuid4

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .ocr_worker import MAX_REQUEST, MAX_TEXT, TIMEOUT, validate_image


@dataclass
class Request:
    image: object
    identifier: str = field(default_factory=lambda: uuid4().hex)
    cancelled: Event = field(default_factory=Event)


@dataclass(frozen=True)
class Result:
    identifier: str
    text: str = ''
    error: str = ''


def run_worker(job, timeout=TIMEOUT):
    from .clipboard import encode
    if job.cancelled.is_set():
        return Result(job.identifier)
    process = None
    temporary = tempfile.TemporaryDirectory(prefix='miniwhiteboard-ocr-')
    try:
        directory = Path(temporary.name)
        request, response = directory / 'request.json', directory / 'result.json'
        payload = json.dumps({'image': encode((job.image,), 'ocr').decode('utf-8'), 'language': 'en'})
        if len(payload.encode('utf-8')) > MAX_REQUEST:
            raise ValueError('The OCR request is too large.')
        request.write_text(payload, encoding='utf-8')
        if job.cancelled.is_set():
            return Result(job.identifier)
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.append(str(Path(__file__).resolve().parents[1] / 'main.py'))
        command += ['--ocr-worker', str(request), str(response)]
        environment = os.environ.copy()
        environment.update(OMP_THREAD_LIMIT='1', OMP_NUM_THREADS='1')
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if job.cancelled.wait(.05):
                return Result(job.identifier)
            if time.monotonic() >= deadline:
                return Result(job.identifier, error='OCR timed out. Try a smaller image.')
        if process.returncode or not response.is_file() or response.stat().st_size > MAX_TEXT * 6 + 2048:
            raise RuntimeError('Worker failed.')
        data = json.loads(response.read_text(encoding='utf-8'))
        text, error = data['text'], data['error']
        if not isinstance(text, str) or not isinstance(error, str) or len(text) > MAX_TEXT:
            raise RuntimeError('Invalid worker response.')
        return Result(job.identifier, text, error[:250])
    except ValueError as error:
        return Result(job.identifier, error=str(error)[:250])
    except (OSError, RuntimeError, KeyError):
        return Result(job.identifier, error='The offline OCR engine could not run. Check the app resources.')
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        temporary.cleanup()


class OcrService(QObject):
    completed = Signal(object)
    delivered = Signal(object)

    def __init__(self, parent=None, runner=run_worker):
        super().__init__(parent)
        self.runner = runner
        self.requests = {}
        self.pool = None
        self.closed = False
        self.completed.connect(self.accept_result, Qt.ConnectionType.QueuedConnection)

    def submit(self, image):
        validate_image(image)
        if self.closed:
            raise ValueError('OCR is shutting down.')
        if len(self.requests) >= 2:
            raise ValueError('OCR is busy. Wait for the current requests or cancel one.')
        job = Request(image)
        self.requests[job.identifier] = job
        if self.pool is None:
            self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='MiniWhiteboardOCR')
        self.pool.submit(self.execute, job)
        return job.identifier

    def execute(self, job):
        try:
            result = self.runner(job)
        except Exception:
            result = Result(job.identifier, error='OCR could not recognize this image.')
        self.completed.emit(result)

    @Slot(object)
    def accept_result(self, result):
        job = self.requests.pop(result.identifier, None)
        if job is not None and not job.cancelled.is_set() and not self.closed:
            self.delivered.emit(result)

    def cancel(self, identifier):
        job = self.requests.get(identifier)
        if job is not None:
            job.cancelled.set()

    def close(self):
        self.closed = True
        for job in self.requests.values():
            job.cancelled.set()
        if self.pool is not None:
            self.pool.shutdown(wait=True, cancel_futures=True)
            self.pool = None
        self.requests.clear()
