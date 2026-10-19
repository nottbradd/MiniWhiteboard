"""Portable safeguards for Mac CI packaging and its owned-process monitor."""
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from scripts.macos_package_check import bundle_manifest, external_dependencies, validate_bundle
from scripts.macos_package_release import inspect_zip
from scripts.macos_startup_check import observe_process


class MacPackagingTests(unittest.TestCase):
    def test_linkage_rejects_external_paths_but_accepts_apple_and_relative_names(self):
        listing = """binary:
    /System/Library/Frameworks/AppKit.framework/AppKit (compatibility version 1.0.0)
    /usr/lib/libSystem.B.dylib (compatibility version 1.0.0)
    @rpath/QtCore.framework/QtCore (compatibility version 1.0.0)
    @loader_path/libffi.dylib (compatibility version 1.0.0)
    /Users/runner/hostedtoolcache/libmissing.dylib (compatibility version 1.0.0)
    /opt/homebrew/lib/libmissing.dylib (compatibility version 1.0.0)
"""
        self.assertEqual(external_dependencies(listing), [
            "/Users/runner/hostedtoolcache/libmissing.dylib", "/opt/homebrew/lib/libmissing.dylib"])

    def test_manifest_detects_contents_and_empty_directory_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"Contents").mkdir()
            first = bundle_manifest(root)
            self.assertEqual(first[0]["path"], "Contents")
            self.assertTrue(first[0]["directory"])
            (root/"Contents/runtime").write_bytes(b"original")
            second = bundle_manifest(root)
            (root/"Contents/runtime").write_bytes(b"modified")
            self.assertNotEqual(second, bundle_manifest(root))

    def test_zip_root_and_crc_with_resource_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)/"release.zip"
            with zipfile.ZipFile(archive, "w") as source:
                source.writestr("Mini Whiteboard.app/Contents/Info.plist", b"plist")
                source.writestr("__MACOSX/Mini Whiteboard.app/._Contents", b"metadata")
            self.assertEqual(inspect_zip(archive), dict(entries=2, app_at_root=True, crc="PASSED"))

    def test_zip_rejects_extra_roots_and_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)/"release.zip"
            for entry in ("outside.txt", "../Mini Whiteboard.app/Contents/Info.plist",
                          "Mini Whiteboard.app/../outside.txt", "/absolute/file", "bad\\file"):
                with self.subTest(entry=entry):
                    with zipfile.ZipFile(archive, "w") as source:
                        source.writestr("Mini Whiteboard.app/Contents/Info.plist", b"plist")
                        source.writestr(entry, b"unexpected")
                    with self.assertRaises(RuntimeError):
                        inspect_zip(archive)

    def test_zip_requires_app_at_root_and_detects_corrupt_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)/"release.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as source:
                source.writestr("Mini Whiteboard.app/Contents/Info.plist", b"unique-payload-123")
            raw = archive.read_bytes()
            archive.write_bytes(raw.replace(b"unique-payload-123", b"unique-payload-456", 1))
            with self.assertRaisesRegex(RuntimeError, "CRC"):
                inspect_zip(archive)
            with zipfile.ZipFile(archive, "w") as source:
                source.writestr("Mini Whiteboard.app/empty", b"")
            with self.assertRaisesRegex(RuntimeError, "root"):
                inspect_zip(archive)

    def bundle_fixture(self, root):
        bundle = root/"Mini Whiteboard.app"
        (bundle/"Contents/MacOS").mkdir(parents=True)
        info = {"CFBundleIdentifier": "com.brad.miniwhiteboard", "CFBundleShortVersionString": "1.2",
                "CFBundleVersion": "1.2", "LSMinimumSystemVersion": "14.0", "LSUIElement": True,
                "CFBundleExecutable": "Mini Whiteboard", "NSScreenCaptureUsageDescription": "Capture a region"}
        (bundle/"Contents/Info.plist").write_bytes(plistlib.dumps(info))
        executable = bundle/"Contents/MacOS/Mini Whiteboard"
        executable.write_bytes(b"\xcf\xfa\xed\xfe")
        executable.chmod(0o755)
        return bundle, info

    def native_output(self, command, **kwargs):
        if command[0].endswith("file"):
            return "Mach-O 64-bit executable x86_64"
        if command[0].endswith("lipo"):
            return "x86_64"
        return "binary:\n    /usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n"

    def test_validation_rejects_wrong_metadata_and_missing_architecture(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.macos_package_check.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="valid", stderr="")), patch(
                "scripts.macos_package_check.subprocess.check_output", side_effect=self.native_output):
            bundle, info = self.bundle_fixture(Path(directory))
            result = validate_bundle(bundle, "universal2")
            self.assertEqual(result["status"], "FAILED")
            self.assertIn("Architectures", result["error"])
            info["CFBundleVersion"] = "1.0"
            (bundle/"Contents/Info.plist").write_bytes(plistlib.dumps(info))
            result = validate_bundle(bundle, "x86_64")
            self.assertEqual(result["status"], "FAILED")
            self.assertIn("metadata", result["error"])

    def test_validation_rejects_windows_runtime_files(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.macos_package_check.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="valid", stderr="")), patch(
                "scripts.macos_package_check.subprocess.check_output", side_effect=self.native_output):
            bundle, _ = self.bundle_fixture(Path(directory))
            (bundle/"Contents/MacOS/a.dll").write_bytes(b"MZruntime")
            result = validate_bundle(bundle, "x86_64")
            self.assertEqual(result["status"], "FAILED")
            self.assertIn("Windows", result["error"])


class StartupMonitorTests(unittest.TestCase):
    def launch(self, code, *arguments):
        process = subprocess.Popen([sys.executable, "-c", code, *arguments],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        return process

    def test_immediate_normal_exit_does_not_pass_startup(self):
        process = self.launch("print('version only')")
        with self.assertRaisesRegex(RuntimeError, "exited during startup"):
            observe_process(process, 5, lambda pid: self.fail("Must not terminate an exited process"))

    def test_immediate_failure_does_not_pass_startup(self):
        process = self.launch("raise ImportError('missing runtime')")
        with self.assertRaisesRegex(RuntimeError, "ImportError"):
            observe_process(process, 5, lambda pid: False)

    def test_liveness_requires_successful_normal_termination(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = Path(directory)/"stop"
            process = self.launch("import pathlib,sys,time\np=pathlib.Path(sys.argv[1])\n"
                                  "while not p.exists(): time.sleep(.01)\n", str(stop))
            def terminate(pid):
                self.assertEqual(pid, process.pid)
                stop.write_text("quit")
                return True
            result = observe_process(process, .1, terminate)
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["exit_code"], 0)
            self.assertIsNotNone(process.poll())

    def test_rejected_termination_does_not_pass(self):
        process = self.launch("import time; time.sleep(30)")
        with self.assertRaisesRegex(RuntimeError, "did not accept termination"):
            observe_process(process, .1, lambda pid: False)


if __name__ == "__main__":
    unittest.main()
