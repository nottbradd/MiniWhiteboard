# Third-party software and distribution

The [MIT license](https://github.com/nottbradd/MiniWhiteboard/blob/main/LICENSE)
covers Mini Whiteboard's own source and assets. Python, Qt, PySide6 and the other
dependencies retain their original licenses.

## Dependencies used by Version 1.3.4

| Software | Use | Upstream license information |
|---|---|---|
| Python | Runtime | [Python license and bundled notices](https://docs.python.org/3/license.html) |
| PySide6 / Shiboken6 6.11.2 | Python bindings for Qt | [Qt for Python licenses](https://doc.qt.io/qtforpython-6.11/licenses.html); the release uses the open-source LGPL terms |
| Qt 6.11.2 | Widgets, rendering, image formats and platform integration | [Qt component notices](https://doc.qt.io/qt-6.11/licenses-used-in-qt.html); LGPLv3 with the applicable component notices |
| PyObjC 12.2.2 core / frameworks | macOS native bridges | MIT, with notices for included software; original wheel license files are included in the Mac package |
| PyInstaller 6.22.3 | Packaging tool and bootloader | [License and bootloader distribution exception](https://pyinstaller.org/en/stable/license.html) |
| Inno Setup 6.7.3 | Windows installer compiler and installer/uninstaller runtime | [Inno Setup license](../assets/licenses/innosetup-6.7.3.txt); upstream copyright and notices are retained |
| OpenSSL runtime libraries | Included with Python | Apache 2.0; the original upstream license is included |
| libffi, Windows ABI-8 DLL | Python ctypes | MIT; the upstream notice is included; the DLL has no version resource |

The Mac PyObjC framework set includes Cocoa, Quartz, ScreenCaptureKit, CoreMedia
and ServiceManagement. The icon vector masters and generated branding are
Mini Whiteboard's own MIT-licensed assets.

## What the downloads contain

Each app includes a `licenses` directory. On Windows it is under `_internal`;
on Mac it is under `Contents/Resources`. Its `MANIFEST.json` records
the builder's Python version, package versions and SHA-256 of every notice file.
Packaging verifies these hashes before making an archive.

The directory includes the project's MIT license, the actual Python runtime
license, original installed-package notices, and versioned collections of
upstream license and third-party notice texts from Qt/PySide 6.11.2. The
collections preserve upstream alternative commercial terms and notices for
components present in those source archives; that does not change the LGPL
terms used for the shipped Qt/PySide binaries.

The application uses Qt Widgets. Its packaging excludes the unused Qt Virtual
Keyboard, QML, Quick and PDF products and rejects a package containing them.
Native text input continues through the Windows or Cocoa platform plugin.
The exact bundled libraries are also inspected during release verification.

## Sources and replacing libraries

The [dependency source guide](https://github.com/nottbradd/MiniWhiteboard/blob/main/assets/licenses/SOURCES.md)
lists exact upstream source archives, their locally computed hashes, and how to
rebuild or replace the dynamically loaded Qt/PySide libraries. The same guide
is included at `licenses/upstream/SOURCES.md`. Corresponding source archives
are attached to the [V1.3 GitHub Release](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3).

The project's MIT source and PyInstaller build specifications are available in
the repository and GitHub's source archives. No project license term prevents
modifying or reverse engineering the app to debug changes to LGPL libraries.
Modified Mac bundles need to be re-signed; the build supports ad-hoc signing.

Apple frameworks and Windows system libraries remain operating-system
components. Generated notice checks establish that the intended texts are
present and unchanged; they are technical package checks.

V1.3.1 removes the OCR engine, data and exclusive bridges/notices. The historical
V1.3 release retains its original notices and corresponding sources. The five
remaining exact source archives are unchanged and remain accessible there.
