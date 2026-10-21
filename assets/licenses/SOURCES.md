# Dependency sources for Mini Whiteboard

Qt and Qt for Python binaries are unmodified upstream 6.11.2 builds. The release
uses dynamically loaded libraries. The exact source archives are listed below,
along with locally computed SHA-256 values. Source archives are also provided
as GitHub Release assets. Each archive includes upstream build files and license
texts. The corresponding notice collections are packaged with both apps.

## Rebuilding and replacing Qt/PySide

Mini Whiteboard's MIT source and both PyInstaller specifications are available
in the repository and the release's automatically generated source archives.
Follow Qt/Qt for Python's upstream build instructions inside these source
archives to build compatible shared libraries and Python bindings. Install your
build into a development environment and rebuild Mini Whiteboard with build.ps1
or build_macos.sh. On Windows, bundled DLLs and bindings are separate files in
_internal/PySide6 and _internal/shiboken6. On Mac, frameworks and bindings are
separate files in the app bundle; changing signed files requires re-signing the
modified bundle (ad-hoc signing is supported by the build). No project license
term prevents modifying or reverse engineering the application to debug changes
to LGPL libraries. Preserve the original package while testing replacements.

## Sources

- **qtbase 6.11.2:** https://download.qt.io/archive/qt/6.11/6.11.2/submodules/qtbase-everywhere-src-6.11.2.tar.xz
  SHA-256: `5b2e00eccaf5a4d8c14134ffa0ea8dfd0a35ae1ffc7f8d87fa4305a1ed23cf22`
- **qtsvg 6.11.2:** https://download.qt.io/archive/qt/6.11/6.11.2/submodules/qtsvg-everywhere-src-6.11.2.tar.xz
  SHA-256: `d594337feca84c26fb67fe87b85e6a5c12fda404b611d905f9d138210c311876`
- **qtimageformats 6.11.2:** https://download.qt.io/archive/qt/6.11/6.11.2/submodules/qtimageformats-everywhere-src-6.11.2.tar.xz
  SHA-256: `cecd8900f34b6550076309bc94f62f828008b633a4239e0a08c86788f41001f8`
- **pyside-setup 6.11.2:** https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz
  SHA-256: `cba47efbaad1bedd529725cbc14e21f156c7a19366f07b3edfbb076ffd7afdf8`

Python source: https://www.python.org/downloads/source/ (use the runtime version
recorded in the packaged licenses/MANIFEST.json).
PyObjC source: https://github.com/ronaldoussoren/pyobjc/tree/v12.2.2
PyInstaller source: https://github.com/pyinstaller/pyinstaller/tree/v6.22.3

The PyObjC wheels' original license notices are collected on the Mac builder.
Python's actual runtime license is collected on each builder. The PyInstaller
notice includes the bootloader exception. Apple system frameworks and Windows
system libraries remain components of their respective operating systems.

## OCR sources and rebuilding

Windows uses the unmodified standalone tesserocr 2.11.0 CPython 3.12 x64 wheel
from [the upstream Windows build release](https://github.com/simonflueckiger/tesserocr-windows_build/releases/tag/tesserocr-v2.11.0-tesseract-5.5.3).
Its SHA-256 is `74604b65547b6e988dcdab0d6d7366964ec588a9fd28a526b2ca9b9f8b8d3dea`.
The build recipe is pinned at `cb737e34870e2568da274ac89e1b11db2c52aad8`;
its tesserocr submodule is `d27f2e394c79739c75b062fc150b08f420300ab6`.
It builds Tesseract 5.5.3 (`db0ec62`) and Leptonica 1.87.0 (`13275a2`),
using the named Software Network image/compression dependencies.

[OCR-SOURCES.json](OCR-SOURCES.json) records exact archive bytes/hashes for all
these libraries and **cysignals 1.12.6** (the upstream wheel release identifies
that version for Python 3.12+). The V1.3 release's `MiniWhiteboard-OCR-Sources.zip`
contains those archives, the Windows build recipe and patches, and this guide.
Follow its `appveyor.yml` dependency/wheel build steps with Python 3.12 x64 and
Visual Studio 2022. Build cysignals from its included sdist without modifying its
source, as the recipe does. These sources include the build files and licenses.

English `eng.traineddata` is the original tessdata_fast 4.1.0 file, under Apache 2.0.
SHA-256: `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
Its download URL is recorded in the repository's `assets/ocr/MANIFEST.json`.

Windows OCR DLLs/extensions remain external, dynamically loaded files under
`_internal/tesserocr`, including `_internal/tesserocr/cysignals/signals*.pyd`.
Replace them with ABI-compatible builds or install rebuilt wheels and rebuild the
app. No project term prevents modification or reverse engineering to debug LGPL
library changes. Keep required notices with redistributed modifications. The Mac
package uses the operating system's Vision framework and the pinned PyObjC bridge;
it does not bundle Windows OCR binaries or English model data.
