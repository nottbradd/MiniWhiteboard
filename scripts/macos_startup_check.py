"""Briefly launch one owned bundle process, then request normal Cocoa termination."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys


def observe_process(process, seconds, terminate):
    """A version query or early normal exit does not pass the utility launch check."""
    try:
        stdout, stderr = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        if not terminate(process.pid):
            raise RuntimeError("Cocoa did not accept termination of the owned app.")
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Owned app did not exit after normal Cocoa termination.") from error
        if process.returncode != 0:
            raise RuntimeError(f"App exit code after Cocoa termination: {process.returncode}; {stderr}")
        if any(marker in stderr for marker in ("Traceback (most recent call last)",
                                              "ModuleNotFoundError", "ImportError", "Library not loaded")):
            raise RuntimeError("Packaged startup reported an import/library failure: " + stderr)
        return dict(status="PASSED", seconds=seconds, exit_code=process.returncode,
                    termination="Cocoa terminate", stdout=stdout, stderr=stderr)
    raise RuntimeError(f"App exited during startup (code {process.returncode}); {stdout}; {stderr}")


def main():
    if sys.platform != "darwin":
        raise SystemExit("NOT RUN: packaged Mac startup requires macOS.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=Path("dist/macos-v131-review03/Mini Whiteboard.app"))
    parser.add_argument("--seconds", type=float, default=8)
    args = parser.parse_args()
    process = None
    result = dict(native_gui="NOT RUN; this check only detects immediate startup failure")
    try:
        import Quartz
        if not Quartz.CGSessionCopyCurrentDictionary():
            result.update(status="NOT RUN", reason="Runner has no WindowServer login session.")
        else:
            import AppKit
            def terminate(pid):
                running = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
                return running is not None and bool(running.terminate())
            bundle = args.bundle.resolve()
            with (bundle/"Contents/Info.plist").open("rb") as source:
                info = plistlib.load(source)
            executable = bundle/"Contents/MacOS"/info["CFBundleExecutable"]
            environment = dict(os.environ, QT_QPA_PLATFORM="cocoa")
            process = subprocess.Popen([str(executable)], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, env=environment)
            result.update(observe_process(process, args.seconds, terminate))
    except Exception as error:
        result.update(status="FAILED", error=str(error))
    finally:
        # Reap only the process this check created, even after a failed launch.
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
            result["forced_cleanup"] = True
    output = Path("verification/macos-startup-check.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
