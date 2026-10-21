"""Inspect a real Mac bundle's metadata, code signatures and complete binary stack."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys
from mini_whiteboard import APP_VERSION

MACHO_MAGIC = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
               b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}


def bundle_manifest(bundle):
    entries = []
    for path in sorted(bundle.rglob("*")):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            entries.append({"path": relative, "link": os.readlink(path)})
        elif path.is_file():
            entries.append({"path": relative, "bytes": path.stat().st_size,
                            "mode": path.stat().st_mode & 0o777,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        elif path.is_dir():
            entries.append({"path": relative, "directory": True,
                            "mode": path.stat().st_mode & 0o777})
    return entries


def external_dependencies(dependencies):
    """Only Apple system libraries may use absolute install names."""
    paths = []
    for line in dependencies.splitlines():
        match = re.match(r"\s+(/.*?)\s+\(", line)
        if match and not match[1].startswith(("/System/Library/", "/usr/lib/")):
            paths.append(match[1])
    return paths


def validate_bundle(bundle, architecture):
    bundle = Path(bundle).resolve()
    results = []
    def check(label, condition, detail=None):
        results.append(dict(check=label, status="PASSED" if condition else "FAILED", detail=detail))
        if not condition:
            raise RuntimeError(label)
    try:
        check("App bundle exists", bundle.is_dir() and bundle.name == "Mini Whiteboard.app")
        plist = bundle/"Contents/Info.plist"
        validation = subprocess.run(["/usr/bin/plutil", "-lint", str(plist)],
                                    capture_output=True, text=True, timeout=20)
        check("Info.plist passes plutil", validation.returncode == 0,
              dict(stdout=validation.stdout, stderr=validation.stderr))
        with (bundle/"Contents/Info.plist").open("rb") as source:
            info = plistlib.load(source)
        check("Bundle metadata and accessory mode", all(info.get(k) == v for k, v in {
            "CFBundleIdentifier": "com.brad.miniwhiteboard", "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION, "LSMinimumSystemVersion": "14.0", "LSUIElement": True}.items()))
        check("Screen capture purpose without microphone purpose", bool(info.get("NSScreenCaptureUsageDescription"))
              and "NSMicrophoneUsageDescription" not in info)
        executable = bundle/"Contents/MacOS"/info["CFBundleExecutable"]
        check("Executable permissions", executable.is_file() and executable.resolve().is_relative_to(bundle)
              and os.access(executable, os.X_OK))
        binary_description = subprocess.check_output(["/usr/bin/file", "-b", str(executable)], text=True)
        check("Executable is Mach-O", "Mach-O" in binary_description, binary_description.strip())
        required = {"arm64", "x86_64"} if architecture == "universal2" else {architecture}
        binaries = []
        for path in sorted(bundle.rglob("*")):
            if path.is_symlink():
                check("Bundle symlink resolves internally: "+str(path.relative_to(bundle)),
                      path.exists() and path.resolve().is_relative_to(bundle))
                continue
            if not path.is_file():
                continue
            check("No Windows executable or DLL: "+str(path.relative_to(bundle)),
                  path.suffix.lower() not in (".exe", ".dll"))
            with path.open("rb") as source:
                magic = source.read(4)
            check("No Windows PE binary: "+str(path.relative_to(bundle)), not magic.startswith(b"MZ"))
            if magic not in MACHO_MAGIC:
                continue
            slices = subprocess.check_output(["/usr/bin/lipo", "-archs", str(path)], text=True).split()
            check("Architectures: "+str(path.relative_to(bundle)), required.issubset(slices), slices)
            dependencies = subprocess.check_output(["/usr/bin/otool", "-L", str(path)], text=True)
            check("No build-machine library dependency: "+str(path.relative_to(bundle)),
                  not external_dependencies(dependencies), dependencies)
            binaries.append(str(path.relative_to(bundle)))
        check("Native binaries present", bool(binaries))
        check("Python runtime is bundled", any("Python.framework/" in name or
              Path(name).name.startswith("libpython3") for name in binaries))
        for framework in ("QtCore", "QtGui", "QtWidgets"):
            check(framework+" framework is bundled", any(framework+".framework/" in name for name in binaries))
        check("Qt Cocoa platform plugin is bundled", any(Path(name).name == "libqcocoa.dylib" for name in binaries))
        check("PyObjC native bridge is bundled", any(Path(name).name.startswith("_objc.") for name in binaries))
        from PyInstaller.archive.readers import CArchiveReader
        archive = CArchiveReader(str(executable))
        pyz = archive.open_embedded_archive("PYZ.pyz")
        from .build_support import verify_frozen_modules
        check('Removed OCR modules are absent', verify_frozen_modules(executable)['frozen_ocr_modules_absent'])
        for name in ("objc", "AppKit", "Foundation", "Quartz", "CoreMedia", "ScreenCaptureKit",
                     "mini_whiteboard.platform.macos.runtime", "mini_whiteboard.platform.macos.desktop",
                     "mini_whiteboard.platform.macos.hotkeys", "mini_whiteboard.platform.macos.capture"):
            check("Frozen module is bundled: "+name, name in pyz.toc)
        unwanted = [name for name in pyz.toc if name == "mini_whiteboard.windows"
                    or name.startswith("mini_whiteboard.platform.windows")]
        check("Windows platform is excluded from frozen modules", not unwanted, unwanted)
        signature = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2", str(bundle)],
                                   text=True, capture_output=True)
        check("Code signatures verify", signature.returncode == 0, signature.stderr)
        version = subprocess.run([str(executable), "--version"], timeout=20, capture_output=True, text=True)
        check("Frozen executable starts for version query", version.returncode == 0,
              dict(stdout=version.stdout, stderr=version.stderr))
        manifest = bundle_manifest(bundle)
        result = dict(status="PASSED", architecture=architecture, bundle=str(bundle),
                      host_architecture=platform.machine(),
                      checks=results, files=manifest, native_gui="NOT RUN by this structural check")
    except Exception as error:
        result = dict(status="FAILED", bundle=str(bundle), checks=results, error=str(error))
    return result


def main():
    if sys.platform != "darwin":
        raise SystemExit("NOT RUN: bundle verification requires macOS.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=Path("dist/macos-v131-candidate/Mini Whiteboard.app"))
    parser.add_argument("--architecture", choices=("universal2", "arm64", "x86_64"), default="universal2")
    parser.add_argument("--report", type=Path, default=Path("verification/macos-package-check.json"))
    args = parser.parse_args()
    result = validate_bundle(args.bundle, args.architecture)
    output = args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("files", "checks")}, indent=2))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
