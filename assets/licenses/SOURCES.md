# Dependency sources for Mini Whiteboard V1.1

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
