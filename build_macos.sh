#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo 'Mini Whiteboard.app must be built and verified on macOS.' >&2
    exit 1
fi
python_bin="${MINIWHITEBOARD_PYTHON:-.venv-macos/bin/python}"
if [[ ! -x "$python_bin" ]]; then
    echo 'Create .venv-macos and install requirements-dev.txt and requirements-macos.txt first.' >&2
    exit 1
fi
export MACOSX_DEPLOYMENT_TARGET=14.0
export MINIWHITEBOARD_ARCH="${MINIWHITEBOARD_ARCH:-universal2}"
mkdir -p verification build
"$python_bin" -m scripts.check_documentation
"$python_bin" -m scripts.package_notices
"$python_bin" -m scripts.make_macos_icon
QT_QPA_PLATFORM=offscreen "$python_bin" -m scripts.run_tests > verification/macos-shared-tests.txt 2>&1
build_target() {
    "$python_bin" -m PyInstaller --noconfirm --distpath dist/macos-v133-review01 --workpath "build/macos-v133-review01-$MINIWHITEBOARD_ARCH" \
        'Mini Whiteboard.macos.spec' > "verification/macos-build-$MINIWHITEBOARD_ARCH.txt" 2>&1
}
if ! build_target; then
    # Only a demonstrated architecture mismatch permits automatic arm64 retry.
    if [[ "$MINIWHITEBOARD_ARCH" == universal2 && "$(uname -m)" == arm64 ]] && \
        "$python_bin" -c 'import pathlib,sys; s=pathlib.Path("verification/macos-build-universal2.txt").read_text(); sys.exit(0 if "IncompatibleBinaryArchError" in s else 1)'; then
        echo 'Universal2 dependency mismatch; see verification/macos-build-universal2.txt. Trying arm64.'
        export MINIWHITEBOARD_ARCH=arm64
        build_target
    else
        echo "Build failed. Read verification/macos-build-$MINIWHITEBOARD_ARCH.txt." >&2
        exit 1
    fi
fi
"$python_bin" -m scripts.macos_package_check --architecture "$MINIWHITEBOARD_ARCH"
echo 'Built dist/macos-v133-review01/Mini Whiteboard.app. Interactive acceptance: see docs/TESTING.md.'
echo 'Create a verified tester ZIP: .venv-macos/bin/python -m scripts.macos_package_release'
echo 'Automated build/packaging does not complete the interactive Mac acceptance checklist.'
