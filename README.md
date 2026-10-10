# Mini Whiteboard

[![Windows tests](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/windows-tests.yml/badge.svg)](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/windows-tests.yml)
[![macOS build](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/macos-v1.1.yml/badge.svg)](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/macos-v1.1.yml)

A small desktop whiteboard you place with two keyboard presses. Draw, type, paste
images and annotate screenshots without a permanent toolbar. Version **1.1** uses
PySide6, with a Windows tray icon and a macOS menu-bar item. Launch opens no board.

## Features

- Exactly two presses to place a board: **Ctrl+Alt+W** on Windows or
  **Control+Option+W** on macOS.
- Freehand drawing, seven shapes, multiline text and a temporary colour palette.
- Multiple selection, shared movement/scaling/rotation, Smart Guides and optional
  Grid Snap.
- Circular partial erasure and a whole-stroke eraser.
- Editable copy/cut/paste/duplicate, image paste and local image drops.
- A global screenshot shortcut that creates a board with a locked background,
  ready to annotate.
- Undo/redo, object locking and ordering, and independent boards.

Documents last for the current session. Only preferences are saved. The app has
no accounts, network service or telemetry.

## Platform status

| Platform | Support and evidence |
|---|---|
| Windows 10/11, 64-bit | Native input, capture, lifecycle and packaged-app checks passed on Windows 11. Physical mixed-DPI and clean-machine deployment remain untested. |
| macOS 14+, preview | [The October 1 CI run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/36831877399) passed 156 tests, built and validated a Universal2 app, passed a limited packaged startup check and verified the ZIP round-trip. Interactive acceptance remains **NOT RUN**. |
| Linux | Unsupported. |

The observed Mac runner used macOS 14.8.9 on arm64 with Python 3.13.15. Universal2
binary validation does not prove execution on Intel. See
[TEST_RESULTS.md](TEST_RESULTS.md) for actual results and both platform checklists
for the remaining GUI/hardware checks.

## Get the app

**No stable GitHub Release has been published yet.** You can run from source or,
for Mac testing, download the artifact from the successful Actions run above.
[GITHUB_SETUP.md](GITHUB_SETUP.md) explains how to obtain the inner
`MacMiniWhiteboardV1.1.zip`. Actions artifacts expire; they are separate from
GitHub Releases.

For an existing Windows tester ZIP, extract it, open **Mini Whiteboard**, and run
**Mini Whiteboard.exe**. Keep its `_internal` folder alongside the executable.
The packaged build includes Python and Qt.

For a Mac tester ZIP, extract it on macOS, move **Mini Whiteboard.app** to
Applications, and open it. This initial build is ad-hoc signed. For a trusted
build blocked by Gatekeeper, follow
[Apple's Open Anyway instructions](https://support.apple.com/en-au/102445).
Interactive Mac hotkeys, focus, permissions, capture and physical display
behaviour still need [native acceptance](MACOS_CHECKLIST.md).

Binary-release preparation also includes the dependency notices and requirements
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Run from source

Clone the repository, then use the commands for your platform:

```text
git clone https://github.com/nottbradd/MiniWhiteboard.git
cd MiniWhiteboard
```

### Windows

Use 64-bit Python 3.12 on Windows 10/11. From PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m mini_whiteboard
```

### macOS

Use the standard python.org universal2 Python 3.13 on macOS 14+:

```bash
python3.13 -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements-macos.txt
.venv-macos/bin/python -m mini_whiteboard
```

Look for the tray/menu-bar icon. Closing the last board leaves the utility
running; choose **Exit Mini Whiteboard** or **Quit Mini Whiteboard** to exit.

## Place a board

1. Point at the first corner and press the global W shortcut, then release it.
2. Move the pointer to the opposite corner. A dotted outline previews the board.
3. Press the same shortcut again. The rectangle becomes a focused board.

Placement supports every drag direction. Mouse clicks and key release do not
confirm it. A rectangle smaller than 160 × 100 logical pixels leaves placement
active so you can enlarge it. Escape cancels. A held key cannot create repeated
boards.

## Tools and shortcuts

Tool keys work only in the focused canvas. New boards start in Draw mode and
remember their tool settings. Press **F1** for help.

| Key | Action |
|---|---|
| D, then 1–5 | Draw at 2, 4, 6, 9 or 14 px |
| T, then 1–3 | Text at 14, 20 or 28 pt |
| S, then 1–7 | Rectangle, rounded rectangle, ellipse, line, arrow, triangle, diamond |
| A or V | Select and transform; Shift-click toggles selection, Shift-marquee adds |
| E, then 1–4 | Circular partial eraser at 8, 16, 32 or 64 logical px |
| E, then 5 | Toggle whole-stroke erasing; a second 5 returns to the 16 px circular brush |
| C | Temporary colour palette; 1–7 choose presets |
| Arrow keys / Shift+arrows | Move the selection by 1 / 10 logical px |
| Delete / Backspace | Delete the selected editable objects |

Corner handles scale proportionally. Edge handles scale one axis unless Shift
is held or the selection contains text or images. The rotation handle rotates
around the group centre; Shift snaps to 15-degree increments. Escape cancels an
active gesture. Selection bounds include surviving artwork outside the viewport.

Circular erasing cuts every editable object under the swept brush. Whole-stroke
mode removes an entire original freehand stroke when any surviving fragment is
hit. Locked objects are protected. Erased regions stay attached through transforms
and text edits. New drawing over an erased region remains visible.

| Action | Windows | macOS |
|---|---|---|
| Place a board | Ctrl+Alt+W twice | Control+Option+W twice |
| Screenshot region | Ctrl+Alt+S, drag and release | Control+Option+S, drag and release |
| Copy / cut / paste / duplicate | Ctrl+C / X / V / D | Command+C / X / V / D |
| Select all | Ctrl+A | Command+A |
| Undo / redo | Ctrl+Z / Ctrl+Shift+Z | Command+Z / Command+Shift+Z |
| Bypass snapping | Alt | Option |
| Finish text editing | Ctrl+Enter or Escape | Command+Return or Escape |

While a textbox is active, its editor owns typing, clipboard commands and undo.
Letters, numbers, arrows, Delete and Backspace never switch canvas tools during
editing. Clicking outside commits text. Board undo resumes after editing ends.

The canvas context menu offers locking, unlocking and front/back ordering. The
tray/menu-bar **Snap & Guides** menu controls Smart Guides and Grid Snap. On Mac,
**Global shortcuts** offers Command+Option+Shift+W/S when the default conflicts.
Screen capture may require Screen Recording permission; the app explains the
request. A rejected or failed capture creates no blank board.

## Test and build

Development requirements include the packaging tools. Windows, from PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -v
Remove-Item Env:QT_QPA_PLATFORM
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The Windows build targets `dist/windows-v11/Mini Whiteboard/`. Keep the complete
output folder together when testing it.

Mac builds require Xcode Command Line Tools:

```bash
.venv-macos/bin/python -m pip install -r requirements-dev.txt -r requirements-macos.txt
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m unittest discover -v
bash build_macos.sh
.venv-macos/bin/python -m scripts.macos_package_release
```

The Mac build attempts Universal2. It allows an arm64 retry only after a genuine
architecture mismatch on an Apple Silicon host. Packaging uses `ditto` and
verifies the archive after extraction. Keep the finished Mac ZIP unchanged when
transferring it through Windows.

[Windows CI](.github/workflows/windows-tests.yml) runs automated tests on code/config
pushes and pull requests to main. [Mac CI](.github/workflows/macos-v1.1.yml) runs the full
build/validation pipeline for relevant main pushes or manual dispatches.
Generated logs under `verification/` are ignored; CI reports are downloadable
Actions artifacts.

## Development and limitations

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributions,
[SPEC.md](SPEC.md) for behaviour, [PLAN.md](PLAN.md) for design history,
[PERFORMANCE.md](PERFORMANCE.md) for measurements, and
[CROSS_PLATFORM_REPORT.md](CROSS_PLATFORM_REPORT.md) for platform details.
Manual checks are in [MANUAL_TESTING.md](MANUAL_TESTING.md) and
[MACOS_CHECKLIST.md](MACOS_CHECKLIST.md).

Image import is limited to 64 million pixels and editable clipboard data to
96 MB. Protected desktop content may be unavailable to native capture. Physical
multi-monitor/DPI arrangements, long sessions and third-party clipboard apps need
further manual testing. Mac floating windows use normal Space membership; display
over every full-screen app is not guaranteed.

## License

Mini Whiteboard's own source and assets use the [MIT license](LICENSE).
Dependencies retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
