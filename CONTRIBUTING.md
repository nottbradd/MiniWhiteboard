# Contributing to Mini Whiteboard

Focused fixes, documentation improvements and reproducible bug reports are welcome.
Use the [README](README.md) for product behaviour and downloads. Linux is unsupported.

## Development setup

Clone the repository and run commands from its root.

### Windows

Use 64-bit Python 3.12 on Windows 10/11:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m mini_whiteboard
```

### macOS

Use the standard python.org universal2 Python 3.13 on macOS 14+.
The build also needs Xcode Command Line Tools.

```bash
python3.13 -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements-dev.txt -r requirements-macos.txt
.venv-macos/bin/python -m mini_whiteboard
```

The small `main.py` launcher also works. Source and frozen Mac applications may
have different Screen Recording permission identities.

## Architecture essentials

| Area | Responsibility |
|---|---|
| `app.py`, `board.py` | Tray/menu lifetime, board registry, frameless windows and controls |
| `platform/` | Narrow Runtime, Desktop, Hotkeys and Capture services; Windows and Mac adapters |
| `gestures.py`, `placement.py`, `screenshot.py` | One creation owner, passive previews, release completion, cancellation and asynchronous capture |
| `document.py`, `transforms.py` | Immutable objects, stable IDs/order, affine transforms, local masks and before/after history |
| `canvas.py`, `text_editor.py` | Tool gestures, selection, focus routing and transformed plain-text editing |
| `rendering.py`, `scene.py`, `background.py` | Shaped text/painted geometry, cached bounds, sparse previews, dirty painting and screenshot display cache |
| `editing_actions.py`, `clipboard.py`, `snapping.py` | Shared commands, validated editable MIME and alignment |
| `tests/`, `scripts/` | Portable regressions, opt-in native checks and package validation |

Shared tools and document logic belong outside native adapters. Portable tests
inject fake services; native scripts use owned windows and processes.

Keep these invariants covered:

- Creation is hold → move → release, with no result on press. Releasing any
  required key ends the gesture. Repeats, competing shortcuts and stale callbacks
  cannot create a second result. Tracking stops after held keys drain.
- Native desktop units cross explicit boundaries: physical pixels on Windows,
  points on Mac. Do not scale global origins as local coordinates.
- Ordinary tool keys require an active board, canvas focus and no editor.
  The real QTextEdit owns ShortcutOverride, typing, clipboard and editor undo.
  Finish callbacks belong to one session. Embedded popup menus retain the editor.
- A new blank/whitespace draft changes no document history or redo branch.
  Clearing existing text is one deletion. Canvas dismissal consumes that press;
  meaningful Text-mode continuation is routed once using viewport/global coordinates.
- One gesture commits one document action. Escape restores the captured state.
  Selection and previews stay outside history. Object identity, original image
  bytes, masks, text width and stacking survive transforms/undo.
- Bounds include surviving artwork outside the viewport. Text uses shaped glyph
  outlines for ink; its convenient box hit area has bounded tolerance work.
  Masks are subtracted after hit tolerance.
- Annotation work reuses the original locked screenshot's display cache at
  viewport × DPR. It must not decode/resample source pixels per pointer event.
- Last-board close leaves the utility running. Documents remain session-only;
  only guide/grid/shortcut preferences persist.

## Tests and builds

Windows:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_tests
.\.venv\Scripts\python.exe -m scripts.check_documentation
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
.\.venv\Scripts\python.exe -m scripts.package_check
.\.venv\Scripts\python.exe -m scripts.package_release
```

Output: `dist/windows-v121/Mini Whiteboard/` and
`build/releases-v1.2.1/WinMiniWhiteboardV1.2.1.zip`. Keep the entire runtime folder.

Mac:

```bash
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m scripts.run_tests
.venv-macos/bin/python -m scripts.check_documentation
bash build_macos.sh
.venv-macos/bin/python -m scripts.macos_startup_check
.venv-macos/bin/python -m scripts.macos_package_release
```

Output: `dist/macos-v121/Mini Whiteboard.app` and
`build/releases-v1.2.1/MacMiniWhiteboardV1.2.1.zip`. Rename the ZIP with
`-Preview` for public preview downloads without changing its bytes.

The Mac build targets 14.0 and attempts Universal2. An arm64 retry is allowed
only after a genuine dependency architecture mismatch on Apple Silicon. Validation
checks every Mach-O slice, linkage, signatures, symlinks, metadata and notice hash.
Packaging uses ditto, extracts on Mac and fully revalidates. Transfer that finished
ZIP unchanged through other operating systems.

[Windows CI](.github/workflows/windows-tests.yml) runs source tests.
[Mac CI](.github/workflows/macos-build.yml) runs tests, build, limited startup and
archive validation on the standard macos-15 runner. Relevant main pushes or a
manual Actions dispatch start the Mac job. Its reports are Actions artifacts;
automated startup does not establish interactive Mac acceptance.

`APP_VERSION` is the application version. Generate Windows resources with
`scripts.make_version`; patch versions have four numeric Windows components
(for example 1.2.1.0). Keep Mac plist versions, defaults, download names and checks
consistent. Use a fresh versioned staging directory to preserve earlier packages.

Both build scripts stage dependency notices before packaging; package checkers
verify their manifest. See [dependency sources and rebuilding](assets/licenses/SOURCES.md).
Mac signing defaults to ad-hoc; `MINIWHITEBOARD_SIGNING_IDENTITY` accepts an existing
Developer ID identity. Notarization/stapling require separate verification.

## Contributions and reports

Add a regression that reproduces a behaviour change through the relevant input
route. Documentation-only edits do not need new tests. Use
[the testing guide](docs/TESTING.md) for native acceptance and troubleshooting.
Report actual results, OS/display setup and remaining **NOT RUN** items.

Keep credentials, private screenshots and personal paths out of commits.
Environments, build outputs, archives and verification logs are ignored; store
detailed local evidence there or in Actions artifacts. Release notes summarize
actual checks. For suspected security issues, use private vulnerability reporting
if available, or request a private channel without posting exploit details publicly.

Contributions to the project's own code/assets use [MIT](LICENSE).
Preserve attribution and dependency terms in [third-party notices](docs/THIRD_PARTY_NOTICES.md).
