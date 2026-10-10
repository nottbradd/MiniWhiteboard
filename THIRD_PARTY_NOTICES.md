# Third-party software and distribution

The [MIT license](LICENSE) covers Mini Whiteboard's own source and assets. It
does not replace the licenses of Python, Qt, PySide6 or other dependencies.
The source repository does not vendor these dependencies; they are installed
from the requirement files when developing or building the app.

## Dependencies used by Version 1.1

| Software | Use | Upstream license information |
|---|---|---|
| Python | Runtime | [Python license and bundled notices](https://docs.python.org/3/license.html) |
| PySide6 / Shiboken6 6.11.2 | Python bindings for Qt | [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html); LGPLv3/GPLv3 or commercial terms apply as described upstream |
| Qt 6.11.2 | Widgets, rendering and platform integration | Component-specific terms; [Qt open-source obligations](https://www.qt.io/development/open-source-lgpl-obligations) |
| PyObjC 12.2.2 frameworks / core | macOS native bridges | [PyObjC license](https://github.com/ronaldoussoren/pyobjc/blob/main/pyobjc-framework-Cocoa/LICENSE.txt); MIT, with separate notices for included software such as libffi |
| PyInstaller 6.22.3 | Packaging tool and bootloader | [PyInstaller license and distribution exception](https://pyinstaller.org/en/stable/license.html) |

Requirements pin the direct packages. A packaged build also contains transitive
dependencies and platform components. Its exact contents must be checked when
preparing a binary release.

## Packaged releases

A binary distribution needs the applicable notices and license texts for the
software it actually contains. Any source-availability and replacement/relinking
requirements under the chosen Qt/PySide license must also be satisfied. An MIT
license for this repository alone does not fulfill those requirements.

No stable GitHub Release has been published. The existing macOS Actions ZIP is
a tester artifact with verified build/startup/archive results. Preparing complete
third-party notices and reviewing distribution requirements remain separate
binary-release work. Automated build checks verify the package's technical
contents; they do not establish license compliance.
