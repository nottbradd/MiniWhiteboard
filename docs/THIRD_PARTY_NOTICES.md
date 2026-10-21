# Third-party software and distribution

The [MIT license](https://github.com/nottbradd/MiniWhiteboard/blob/main/LICENSE)
covers Mini Whiteboard's own source and assets. Python, Qt, PySide6 and the other
dependencies retain their original licenses.

## Dependencies used by Version 1.3

| Software | Use | Upstream license information |
|---|---|---|
| Python | Runtime | [Python license and bundled notices](https://docs.python.org/3/license.html) |
| PySide6 / Shiboken6 6.11.2 | Python bindings for Qt | [Qt for Python licenses](https://doc.qt.io/qtforpython-6.11/licenses.html); the release uses the open-source LGPL terms |
| Qt 6.11.2 | Widgets, rendering, image formats and platform integration | [Qt component notices](https://doc.qt.io/qt-6.11/licenses-used-in-qt.html); LGPLv3 with the applicable component notices |
| PyObjC 12.2.2 core / frameworks | macOS native bridges | MIT, with notices for included software; original wheel license files are included in the Mac package |
| PyInstaller 6.22.3 | Packaging tool and bootloader | [License and bootloader distribution exception](https://pyinstaller.org/en/stable/license.html) |
| tesserocr 2.11.0 (Windows) | Python OCR adapter | MIT; pinned standalone x64 wheel |
| Tesseract 5.5.3 / tessdata_fast English 4.1.0 (Windows) | Offline OCR engine/data | Apache 2.0 |
| Leptonica 1.87.0 and image/compression libraries (Windows) | Tesseract runtime | BSD/MIT/zlib/IJG/0BSD notices, preserved individually |
| cysignals 1.12.6 (Windows) | Tesserocr signal support | LGPLv3; LGPL and incorporated GPLv3 texts, corresponding source and rebuild recipe supplied |
| Vision (Mac) | Offline OCR | System framework, through PyObjC Vision 12.2.2 |
| OpenSSL runtime libraries | Included with Python | Apache 2.0; the original upstream license is included |
| libffi, Windows ABI-8 DLL | Python ctypes | MIT; the upstream notice is included; the DLL has no version resource |

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

## Windows OCR runtime

The wheel bundles Tesseract, Leptonica, GIFLIB 6.1.3, IJG JPEG 10, libpng 1.6.58,
libtiff 4.7.1, zlib 1.3.2, libwebp 1.6.0, OpenJPEG 2.5.4, zstd 1.5.7 and
liblzma/XZ 5.8.3. It also bundles the dynamically loaded cysignals extension.
Original notices are retained as `ocr-*.txt`; exact source archive URLs/hashes are
in `OCR-SOURCES.json`. Windows binary/model hashes are in `assets/ocr/MANIFEST.json`.
The OCR source ZIP contains those exact sources and the upstream Windows build
recipe/patches. No separate system Tesseract installation is required.
