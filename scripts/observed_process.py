"""Run a diagnostic operation with durable progress and a bounded lifetime."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def run(command, directory, label, timeout):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = {'label': label, 'timeout_seconds': timeout, 'status': 'STARTING',
              'started_utc': datetime.now(timezone.utc).isoformat()}
    journal = directory.parent / 'progress.jsonl'

    def record(event, **values):
        row = {'utc': datetime.now(timezone.utc).isoformat(), 'label': label,
               'event': event, 'elapsed_seconds': round(time.monotonic()-started, 3), **values}
        with journal.open('a', encoding='utf-8') as output:
            output.write(json.dumps(row) + '\n')
            output.flush()
        print(json.dumps(row), flush=True)

    def save():
        temporary = directory / 'result.tmp'
        temporary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        temporary.replace(directory / 'result.json')

    record('start', timeout_seconds=timeout)
    save()
    child = None
    readers = []
    output_errors = []
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                 start_new_session=os.name != 'nt')
        result.update(pid=child.pid, status='RUNNING')
        save()
        record('spawned', pid=child.pid)

        def copy(stream, filename):
            # Unbuffered writes preserve partial output if the operation hangs.
            try:
                with (directory / filename).open('wb', buffering=0) as output:
                    while chunk := stream.read1(8192):
                        output.write(chunk)
            except OSError as error:
                output_errors.append({'file': filename, 'error': str(error)})

        for stream, filename in ((child.stdout, 'stdout.txt'), (child.stderr, 'stderr.txt')):
            reader = threading.Thread(target=copy, args=(stream, filename), daemon=True)
            reader.start()
            readers.append(reader)
        deadline = started + timeout
        while child.poll() is None:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                result['status'] = 'TIMED OUT'
                save()
                record('timeout', pid=child.pid)
                # Stop only this owned process tree, never a service or another
                # user's application. A timeout cannot count as a passing scan.
                if os.name == 'nt':
                    stopped = subprocess.run([str(Path(os.environ['WINDIR'])/'System32'/'taskkill.exe'),
                                              '/PID', str(child.pid), '/T', '/F'],
                                             capture_output=True, timeout=10,
                                             creationflags=subprocess.CREATE_NO_WINDOW)
                    result['tree_stop_exit_code'] = stopped.returncode
                else:
                    import signal
                    os.killpg(child.pid, signal.SIGKILL)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
                break
            try:
                child.wait(timeout=min(10, remaining))
            except subprocess.TimeoutExpired:
                record('heartbeat', pid=child.pid)
        result['exit_code'] = child.returncode
        for reader in readers:
            reader.join(timeout=5)
        result['output_complete'] = all(not reader.is_alive() for reader in readers) and not output_errors
        result['output_errors'] = output_errors
        if result['status'] != 'TIMED OUT':
            result['status'] = 'PASS' if child.returncode == 0 and result['output_complete'] else 'FAILED'
    except Exception as error:
        result.update(status='ERROR', error=str(error))
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
    finally:
        if child is not None:
            for reader in readers:
                reader.join(timeout=2)
            if all(not reader.is_alive() for reader in readers):
                for stream in (child.stdout, child.stderr):
                    stream.close()
        result['ended_utc'] = datetime.now(timezone.utc).isoformat()
        result['elapsed_seconds'] = round(time.monotonic()-started, 3)
        save()
        record('end', status=result['status'], exit_code=result.get('exit_code'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--timeout', type=float, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.timeout <= 0:
        parser.error('A command and positive timeout are required')
    result = run(command, args.directory, args.label, args.timeout)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
