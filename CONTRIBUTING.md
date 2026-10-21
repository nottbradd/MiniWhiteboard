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
| `appearance.py`, native appearance adapters | Shared style values, accessibility policy and passive compositor effects |
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
  every outside canvas dismissal deselects and consumes the complete click, including a retargeted double-click. A separate click can start editing.
- One gesture commits one document action. Escape restores the captured state.
  Selection and previews stay outside history. Object identity, original image
  bytes, masks, text width and stacking survive transforms/undo.
- Bounds include surviving artwork outside the viewport. Text uses shaped glyph
  outlines for ink; its convenient box hit area has bounded tolerance work.
  Masks are subtracted after hit tolerance.
- Annotation work reuses the original locked screenshot's display cache at
  viewport × DPR. It must not decode/resample source pixels per pointer event.
- Last-board close leaves the utility running. Documents remain session-only;
  only guide/grid/shortcut/appearance preferences persist.

## Tests and builds

Windows:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_tests
.\.venv\Scripts\python.exe -m scripts.check_documentation
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
.\.venv\Scripts\python.exe -m scripts.package_check
.\.venv\Scripts\python.exe -m scripts.package_release
```

Output: `dist/windows-v132-review01/Mini Whiteboard/` and
`build/candidates/v1.3.2/review-01/WinMiniWhiteboardV1.3.2.zip`. Keep the entire runtime folder.

Build the recommended installer with the pinned, free Inno Setup compiler:

```powershell
.\.venv\Scripts\python.exe -m scripts.bootstrap_inno
.\.venv\Scripts\python.exe -m scripts.build_installer --compiler verification/tools/innosetup-6.7.3/compiler/ISCC.exe
```

The bootstrap verifies the official release SHA-256 and extracts in upstream's
portable mode inside ignored `verification/tools/`. It creates no compiler
shortcuts or uninstall entry. The installer source is `installer/MiniWhiteboard.iss`.
Keep its AppId and mutex names stable across versions. Installation is per user;
automatic application closing is disabled. The application mutex also blocks
uninstallation while boards may be open. Setup never opts users into login startup.

Mac:

```bash
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m scripts.run_tests
.venv-macos/bin/python -m scripts.check_documentation
bash build_macos.sh
.venv-macos/bin/python -m scripts.macos_startup_check
.venv-macos/bin/python -m scripts.macos_package_release
```

Output: `dist/macos-v132-review01/Mini Whiteboard.app` and
`build/candidates/v1.3.2/review-01/MacMiniWhiteboardV1.3.2-Preview.zip`. The Mac download remains a preview. Transfer the ZIP without changing its bytes.

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
(for example 1.3.1.0). Keep Mac plist versions, defaults, download names and checks
consistent. Use a fresh versioned staging directory to preserve earlier packages.

Builds must use an environment without the removed OCR dependencies.
Windows keeps Python 3.12 x64; Mac keeps universal2 Python 3.13. Only Qt/PySide
is a shared runtime requirement. Mac retains Cocoa, Quartz, ScreenCaptureKit
and CoreMedia bridges for the existing native services. Package guards inspect
both runtime filenames and the frozen module archive for removed OCR payload.
Mac also includes the matching PyObjC ServiceManagement bridge for login startup.

`login.py` defines the observed registration state. Windows uses the current
user's documented [Run key](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)
with the real quoted executable and `--login`. StartupApproved is read
conservatively as a compatibility signal; its format is not a public API.
Disabled/unknown approval records require the user to check Startup apps. The
app never writes an enable flag or recreates registration at launch. Mac uses
[SMAppService.mainAppService](https://developer.apple.com/documentation/servicemanagement/smappservice/mainapp?language=objc),
requires the real bundle in Applications and reflects enabled/pending/error states.
No helper, launch plist or paid signing service is required. Actual acceptance
under the current ad hoc signature remains a separate Mac check.

The vector masters are `assets/mini_whiteboard.svg` and `assets/tray_symbol.svg`.
`scripts.make_icon` regenerates the committed PNGs, multi-resolution ICO and
installer wizard artwork in `assets/installer/`;
`scripts.make_macos_icon` produces the ICNS on Mac. Runtime icons use cached PNGs.
The Mac status icon is a template mask; Windows selects contrasting status
symbols from system appearance and refreshes on OS broadcasts without polling.

`appearance.py` owns material values and explicit interface font roles. The
document/editor family helper remains regular and preserves text metrics.
`surfaces.py` retains QMenu navigation and owns temporary material lifetimes.
On supported Windows 11 systems, a small ABI bridge uses a
[host backdrop brush](https://learn.microsoft.com/en-us/uwp/api/windows.ui.composition.compositor.createhostbackdropbrush)
and a rounded compositor clip on a passive HWND. Its bounds/corner centres match
the Qt surface; one physical pixel of antialias coverage sits under the painted
rim. This avoids the inset rectangle and stale sampling observed with the DWM
system Acrylic host. No additional runtime library is required. Qt paints one
rim and static shading; adapters release native visuals/hosts on hide or handle
replacement. There is no desktop readback, input polling or idle animation.
The 140 ms edge light catch runs on Glass show/restore, theme changes and temporary
surfaces. Repeated triggers retain the original deadline; hide/close cancels it.
Production follows system motion policy. Native tests can inject a local policy
without changing accessibility settings or adding a product override.
Cocoa's OS-owned menus retain native presentation; app-owned palette/help windows
use the shared surface. Standard OS colour and permission dialogs stay native.

Surface edges use per-pixel alpha. Avoid binary QWidget masks and rounded
SetWindowRgn clipping on boards/popups: they cut off antialiased pixels. Windows
layered-window alpha provides native hit testing; the passive material host uses
LAYERED and TRANSPARENT together to bypass input across processes. Verify actual
mouse delivery to a separate process, as HTTRANSPARENT only searches one thread.
`alpha_clip.py` clips boundary artwork, the screenshot display cache and temporary
editor pixels. Interior drawing retains its direct paint path. Window actions use
font-independent vector geometry in `window_controls.py`.

Both creation modes share `PreviewOverlay`: a low-tint rounded selection with
native frost where available, a translucent fallback, and an unfilled two-tone
outline when transparency is disabled. Per-monitor origins and compositor clips
stay in their native units. An unchanged pointer causes no material or paint
update. Preview hosts are released before capture; Windows waits for composition
once, and Mac capture retains window-ID exclusions. Never capture the desktop to
simulate a preview's blur.

Windows Hide All preferences change only H. Retrying skips bindings already
registered, and changing the option retains the physical-H latch until release.
Mac global presets and ordinary Command+H remain separate.

Hide All is separate from ordinary focused restore. Keep native nonactivation,
restore-batch membership, stopped activation timers and transient cleanup covered.
Glass is a background compositor effect; never animate whole-window opacity or
capture the desktop to fake blur. Native adapters own effect/view cleanup.

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
