"""Create and round-trip a metadata-preserving tester ZIP on macOS."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from pathlib import PurePosixPath
from .macos_package_check import bundle_manifest, validate_bundle
from .build_support import verify_release_files


def inspect_zip(archive, bundle_name="Mini Whiteboard.app"):
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or not path.parts:
                raise RuntimeError("Unsafe archive entry: " + name)
            if path.parts[0] not in (bundle_name, "__MACOSX"):
                raise RuntimeError("Unexpected archive root: " + name)
        if bundle_name+"/Contents/Info.plist" not in names:
            raise RuntimeError("ZIP does not contain the app at its root.")
        broken = source.testzip()
        if broken:
            raise RuntimeError("ZIP CRC failed: " + broken)
        return dict(entries=len(names), app_at_root=True, crc="PASSED")


def main():
    if sys.platform != "darwin":
        raise SystemExit("Mac ZIPs must be made on macOS with ditto, never repacked on Windows.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=Path("dist/macos-v133-review01/Mini Whiteboard.app"))
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    license_report = verify_release_files(bundle)
    report = json.loads(Path("verification/macos-package-check.json").read_text())
    if report["status"] != "PASSED" or Path(report["bundle"]) != bundle or report["files"] != bundle_manifest(bundle):
        raise SystemExit("Run scripts.macos_package_check on this exact bundle first.")
    archive = Path("build/candidates/v1.3.3/review-01/MacMiniWhiteboardV1.3.3-Preview.zip").resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)], check=True)
    inspection = inspect_zip(archive, bundle.name)
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), directory], check=True)
        extracted = Path(directory)/bundle.name
        if bundle_manifest(extracted) != report["files"]:
            raise RuntimeError("ZIP round-trip changed files, permissions or symlinks.")
        extracted_report = validate_bundle(extracted, report["architecture"])
        Path("verification/macos-extracted-package-check.json").write_text(
            json.dumps(extracted_report, indent=2), encoding="utf-8")
        if extracted_report["status"] != "PASSED":
            raise RuntimeError("Extracted app validation failed: " + extracted_report.get("error", "unknown"))
    result = dict(status="PASSED", **license_report, archive=str(archive), bytes=archive.stat().st_size,
                  sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  metadata_roundtrip=True, architecture=report["architecture"], zip_inspection=inspection,
                  extracted_bundle="PASSED",
                  native_acceptance="See docs/TESTING.md and native reports; packaging alone does not verify GUI behaviour.")
    Path("verification/macos-release.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
