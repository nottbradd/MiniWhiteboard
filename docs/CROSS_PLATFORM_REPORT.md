# Mini Whiteboard V1.2 cross-platform update

V1.2 shares hold/move/release ownership and wrapped text layout across platforms.
Windows retains RegisterHotKey/MOD_NOREPEAT plus a temporary native release latch;
macOS retains Carbon registration and release events, with temporary hardware
state checks for modifier-first release and remaining trigger cleanup. Neither
adapter introduces idle tracking or a new permission request.

Mac CI now uses the standard free macos-15 runner. Deployment, bundle and runtime
minimum remain macOS 14.0. Universal2 validation and the genuine-architecture-only
fallback remain unchanged. Actual OS/CPU/Python/build revision and CI results are
in [TEST_RESULTS.md](TEST_RESULTS.md). Interactive Mac acceptance, macOS 14 and
Intel execution remain NOT RUN until observed on real hardware.

## Historical V1.1 report

# Mini Whiteboard 1.1 — cross-platform implementation report

## Release publication update — 2026-10-11

V1.1 ships as a stable Windows release with a Mac preview, as
approved by the owner. Reference documents now live in `docs/`; the launcher
is `main.py`. Both packages include staged dependency notices and source access,
and exclude unused Qt Virtual Keyboard, QML, Quick and PDF products. The
placement GIF and screenshot use the real app renderer on a controlled desktop.
The final Windows package passed 110 native checks, 31 real input checks and
17 packaged checks. The [October 11 Mac run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/38108550854)
passed 162 tests, Universal2/769 bundle checks, limited startup and archive
verification. Interactive Mac acceptance and Intel execution remain NOT RUN.
See [RELEASE_NOTES.md](RELEASE_NOTES.md) and [TEST_RESULTS.md](TEST_RESULTS.md) for
the current publication evidence. The sections below retain earlier results.

Implementation recorded 2026-10-01 on Windows 11, one 1920×1080 display at
100%. Hosted Mac results reviewed 2026-10-10.

**Windows is built, verified and packaged. The hosted Mac workflow has also
succeeded:** [October 1 run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/36831877399),
commit `7cd78288558ed1120fa39d7fabf331d438034c2f`. Its macOS 14.8.9 arm64 runner,
with Python 3.13.15, passed 156 tests, built/validated Universal2, passed a limited
packaged Cocoa startup check and verified the ditto ZIP after extraction.
Interactive Mac acceptance and Intel execution remain **NOT RUN**.

The repository is [nottbradd/MiniWhiteboard](https://github.com/nottbradd/MiniWhiteboard).
The source-publication update adds the selected MIT license, contribution/report
instructions and Windows CI. Existing application code and Windows packages are
preserved. Generated verification paths below name ignored local outputs; real
Mac CI reports are available in the linked run's verification artifact.

## 1. Changed files

| Area | Files and purpose |
|---|---|
| Platform foundation | `mini_whiteboard/platform/{__init__,base,capture_geometry}.py`: lazy selection, services and explicit display capture planning |
| Windows boundary | `platform/windows/{__init__,native}.py`: adapters and original Win32 implementation; `windows.py` is a compatibility alias for older diagnostics |
| Mac implementation | `platform/macos/{__init__,runtime,desktop,hotkeys,capture}.py` |
| Shared integration | `app.py`, `board.py`, `placement.py`, `screenshot.py`, `overlays.py`, `shadow.py`; native operations route through services |
| Shortcuts/settings/fonts | New `shortcuts.py`, `system_menu.py`; updates in `snapping.py`, `feedback.py`, `rendering.py`, `text_editor.py`; `geometry.py` documents native units |
| Windows packaging | `build.ps1`, `Mini Whiteboard.spec`, `scripts/package_check.py`, `scripts/package_release.py`; separate candidate directory/archive |
| Mac packaging | `build_macos.sh`, `Mini Whiteboard.macos.spec`, `requirements-macos.txt`, `scripts/make_macos_icon.py`, `scripts/macos_package_check.py`, `scripts/macos_package_release.py` |
| Verification | `tests/fake_platform.py`, `tests/test_platform.py`, `tests/test_macos_capture.py`, `tests/qt_case.py`; `scripts/macos_escape_probe.py`, `scripts/macos_native_smoke.py`; shared screenshot benchmark now supports Cocoa |
| Documentation | README, SPEC, PLAN, TEST_RESULTS, PERFORMANCE, Windows MANUAL_TESTING; new MACOS_CHECKLIST and this report; `.gitignore` excludes the Mac venv |

`verification/cross-platform-audit.json` contains the exact source list and release
preservation results. The immutable document, canvas/tool logic, object clipboard,
selection/transforms/eraser systems, image storage, scene cache and background
raster implementation remain shared.

## 2–4. Architecture and native isolation

`Platform` supplies Runtime, Desktop, Hotkeys and Capture. Shared controllers ask
for placement, focus, displays, cursor position and capture. Windows preserves its
physical coordinates, DPI rules and GDI code. Mac desktop geometry is in points.
Fake services let tests exercise timing/cancellation/coordinates without a desktop.

The Windows release contains no Mac adapter or PyObjC modules; its frozen module
archive was inspected. Mac dependencies are in a separate requirements file.
Source/build/distribution/release were preserved and hashed before refactoring.

## 5. Windows regression gate

The baseline's 126 tests passed. After introducing adapters, 126 tests, 110 native
checks and real W/S keyboard/mouse checks passed **before substantial Mac code**.
Final results are below. The original dist, build files and Desktop tester ZIP
still match their preserved hashes.

## 6–7. Mac hotkeys and Escape

Carbon `RegisterEventHotKey` delivers pressed/released events through the Qt-owned
native event loop. Held-state tracking suppresses repeats; release only clears
that state. Default Control+Option+W/S and alternate Command+Option+Shift+W/S are
persisted, with partial-registration conflict reporting, retry and cleanup.

**Bare Escape feasibility: NOT RUN on a Mac.** The temporary registration path
and `macos_escape_probe.py` are implemented. The probe records external focus and
pre-existing Accessibility state; only an observed external event without that
permission counts as a permission-free pass. Registration rejection is reported,
and the active interaction can be cancelled through the menu bar. No keyboard
polling, event tap or Accessibility request was added. Native acceptance remains
blocked on that probe result; unaffected Mac source work has been completed.

## 8–9. Mac lifecycle and windows

Qt retains ownership of NSApplication and its event loop. Accessory activation
policy plus LSUIElement avoids a Dock-centric launch. QSystemTrayIcon supplies
the single status item and shared compact menu. QLockFile prevents duplicate
owners. Closing all boards keeps the status utility alive.

Capture's QObject dispatcher and timer are created lazily after QApplication and
owned by it. The startup-order audit added two regression tests; selecting the
Mac platform before application construction now creates no capture QObject.

The adapter obtains Qt's NSView/NSWindow, uses floating level, disables hiding on
deactivation, applies a rounded transparent surface/native shadow, and activates
only on creation or explicit restore. It exposes no Pin control. Ordinary Space
membership is retained; explicit restore can move a board to the active Space.
Native focus, shadow/input corners, Spaces/Mission Control/Stage Manager and
full-screen behaviour remain unverified; no universal full-screen claim is made.

## 10. Clipboard and text ownership

QClipboard and the validated custom object MIME payload remain shared. No native
pasteboard fallback was added without an observed format gap. Mac interoperability
with Preview, browsers, screenshots and Finder still needs native verification.

Qt maps ControlModifier to macOS Command under its default mapping, allowing the
existing editing commands and QTextEdit behaviour to remain shared. Platform help
shows Command/Option labels. Tool letters/numbers have no application-wide shortcut;
the router requires canvas focus and exits while the real editor is active.
ShortcutOverride, clipboard and editor undo ownership remain intact.
[Qt modifier documentation](https://doc.qt.io/qt-6/qt.html#KeyboardModifier-enum).

## 11–13. Capture, permissions and displays

The Mac service uses `SCShareableContent`, per-display `SCContentFilter` and
`SCScreenshotManager` still-image capture for macOS 14+. Callbacks return through
a queued Qt signal; stale generations are ignored and a 15-second timeout fails
cleanly. Temporary Escape stays active while capture is pending. Hidden selection
windows are explicitly excluded by native IDs.

Screen Recording preflight/request occurs before selection. Denial explains the
purpose and offers System Settings; failed/empty captures cannot create a board.
Audio capture is disabled. No microphone or Accessibility permission is requested.

Capture planning intersects the selected point rectangle with each display,
converts only local crop dimensions to that display's pixels, and composes at the
highest participating scale. Desktop gaps stay white. Negative origins and mixed
scales are tested with fakes. Physical Mac Retina/non-Retina, orientation, display
removal and colour results still require hardware checks.

## 14. Performance

Shared caching/dirty regions/source identity and locked-image exclusion remain.
The Windows native workload ran 28 cases, 60 samples each. All 21 screenshot cases
used one cache build and had zero measured image decode, geometry rebuild or source
painting calls. With a 4K source, median input-event times ranged from 1.491 ms
(whole-stroke erase) to 5.472 ms (rotate 10 objects). These are event timings, not
FPS or a claim of a new speedup. See PERFORMANCE.md. Native Mac performance: NOT RUN.

## 15–16. Universal2 and signing

Universal2 is the default target in the Mac build. PyInstaller must accept the
complete dependency stack; the checker inspects every Mach-O file, executable
mode, internal symlink and code signature. A real `IncompatibleBinaryArchError`
allows arm64 fallback on Apple Silicon, retaining the failed log. **The hosted
run built and verified Universal2 without fallback. Intel execution remains
NOT RUN.** This follows [PyInstaller's architecture requirements](https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support).

The initial spec permits PyInstaller's ad-hoc signing. Developer ID is an optional
environment setting for a future signed/notarised/stapled release. No Apple
Developer membership is required for the initial tester plan. README/checklist
document [Apple's Open Anyway process](https://support.apple.com/en-au/102445).
No Mac signature, notarisation or Gatekeeper result was produced on Windows.

## 17–19. Actual results and unrun checks

| Verification | Result |
|---|---|
| Latest automated shared/platform/packaging suite | **PASSED: 156 tests** |
| Test suite at Windows build | **PASSED: 143 tests**; the subsequent Mac-only startup fix is excluded from that build |
| Final native Windows suite | **PASSED: 111 checks**, no callback exceptions |
| Final real Windows keys/mouse | **PASSED: 33 checks** |
| Final packaged executable | **PASSED: 16 checks** |
| Final Windows build | **PASSED**, exit 0, GUI subsystem, Version 1.1 |
| Compilation / pip consistency / version | **PASSED** |
| Windows archive integrity | **PASSED: all 165 file hashes and CRCs** |
| Old Windows build/release preservation | **PASSED** |
| Mac build / Universal2 / ad-hoc signature / ditto ZIP | **CI VERIFIED**, October 1 run |
| Limited packaged Cocoa startup | **CI VERIFIED**, eight seconds, normal exit 0 |
| Interactive Mac acceptance / Intel execution | **NOT RUN** |

All native tests used owned Windows processes/windows. Native Mac hotkeys/Escape,
menu/Dock/lifetime, focus/topmost/corner input, physical Command shortcuts,
clipboard apps, TCC permission flows, real ScreenCaptureKit crops, Retina/mixed
displays, Spaces/Mission Control/Stage Manager, single instance, idle CPU and clean
bundle deployment are NOT RUN. Windows mixed-DPI/negative monitor arrangements,
monitor removal, clean-machine deployment and extended third-party app/manual
testing also remain NOT RUN. See both manual checklists.

## 20–23. Artifacts

- **Windows executable:** `dist/windows-v11/Mini Whiteboard/Mini Whiteboard.exe`
  (1,864,080 bytes). SHA-256:
  `3d53acc4b8f22e0f21ce0b6acecd307b06aecf76206eae38e9b3d6abfbddc94a`.
- **Windows ZIP on Desktop:**
  `Desktop/WinMiniWhiteboardV1.1.zip`
  (45,589,638 bytes). SHA-256:
  `97f9d4c48cadab4f89ac2d29a5ce62dfe1542979d80ef8cc055b2e4669851450`.
  A workspace copy is in `build/WinMiniWhiteboardV1.1.zip`. The actual Desktop copy
  was reopened and every entry verified against the final distribution.
- **Previous tester archive:** `MiniWhiteboardV1.1.zip` on Desktop remains unchanged;
  its SHA-256 is `09bac13fef9ce702855e208784c1dbc07fa97f039121d0e0258218e2797d1b51`.
- **Mac .app:** built and verified in CI, `dist/macos-v11/Mini Whiteboard.app`.
- **Mac ZIP:** built and verified in CI, `MacMiniWhiteboardV1.1.zip`, 74,214,960
  bytes, SHA-256 `56402e4443d09abac57c1a010017bf78d3de3217d9ef80a8898abb3a85cd63f1`.
  Available as the inner file in the run's **MacMiniWhiteboardV1.1** artifact;
  transfer unchanged. Desktop delivery has not been verified here.
- **Public binary release:** none published. Interactive acceptance and complete
  third-party distribution notices remain separate release work; see
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Windows launch: extract the Desktop ZIP, open `Mini Whiteboard`, run
`Mini Whiteboard.exe`, and keep `_internal` alongside it. Look in the system tray.

## 24. Build and automate verification without owning a Mac

New Git/GitHub files: `.gitignore` excludes environments/caches/builds/distributions,
generated verification files and release ZIPs; `.gitattributes` preserves LF shell
and YAML files; `.github/workflows/macos-v1.1.yml` defines **macOS V1.1**. Source,
tests, requirements, both specs, build scripts, documentation and required assets
are versioned. Existing local/Desktop build outputs are preserved and excluded.

The manual workflow and relevant pushes to main run on a real `macos-14` runner
with Python 3.13 and pip caching. Checkout, setup-python and upload-artifact are
pinned to verified revisions of their current v7 tags. Documentation-only pushes
do not run the full Mac build. No Windows build runs in the job.

The stages report OS/CPU/Python/Qt/PySide6/PyInstaller/PyObjC versions, install the
existing requirements, run the new headless `scripts.macos_smoke` import/platform
check, run the full suite, and use the existing shell script and Mac spec. Bundle
validation now checks plist validity, metadata, executable mode, Python/Qt/bridge/
frozen modules, Cocoa plugin, all architectures, external linkage, symlinks,
Windows PE/EXE/DLL exclusion and code signatures. A brief owned Cocoa launch
detects immediate failures and requests normal termination. If the runner lacks
a WindowServer login session, its startup report explicitly says NOT RUN.

The existing Mac release script uses ditto, checks ZIP root and CRCs, extracts
into a clean temporary directory, compares contents/structure/modes/symlinks and
revalidates the extracted app completely. Only then is the inner release ZIP
uploaded as **MacMiniWhiteboardV1.1**. Tests/build/reports are separately uploaded
as **macos-v1.1-verification**, including after failures. The run summary preserves
all interactive NOT RUN statuses.

No application adapter, requirements, architecture target or PyInstaller spec
was changed for CI. Universal2 remains the default, with the existing conditional
arm64 fallback after a demonstrated architecture mismatch. The actual hosted
result confirms imports and full-stack Universal2 build
acceptance. Interactive native API behaviour remains unverified.

Local results: **156 tests passed**, actionlint 1.7.12 passed, shell syntax and
Python compilation passed, and pip check found no broken dependencies. The 11 new
portable tests cover archive root/CRC/traversal, manifest changes, linkage,
metadata/architecture/Windows-file rejection, and startup liveness/termination.
They do not constitute native Mac verification. Logs remain under ignored local
`verification/`; future runner reports are downloadable artifacts.

Follow [GITHUB_SETUP.md](GITHUB_SETUP.md) to rerun the existing workflow or
download the successful run's artifact. Extract GitHub's outer archive and
transfer the inner `MacMiniWhiteboardV1.1.zip` unchanged. The run URL, revision,
runner/package versions, results and hash are recorded in TEST_RESULTS.
The automated Mac stage has succeeded; interactive acceptance remains open.

GitHub schedules `macos-14` brownouts in October and retirement on November 2,
2026. The initial workflow keeps the requested label; an unavailable runner is
an external failure, not an application test result. See
[GitHub's runner notice](https://github.com/actions/runner-images/issues/13518).

## 25. Remaining interactive work on a Mac

1. Copy the source, install the standard universal2 Python 3.13 and Xcode Command
   Line Tools. Create `.venv-macos` and install both dev/Mac requirements.
2. Run the shared tests, the bare-Escape probe with Accessibility off and another
   app focused, then native smoke/capture/performance checks.
3. Run `bash build_macos.sh`; inspect the architecture/signature report. Launch
   the real app from Finder and complete MACOS_CHECKLIST.md against the bundle.
4. Resolve any native failures. Record hardware, OS, architecture and limitations;
   do not infer native acceptance from mocked tests or a Universal2 file inspection.
5. Run `scripts.macos_package_release` on that Mac, compare its round-trip report,
   then copy its ZIP unchanged to Windows Desktop and compare SHA-256 values.

Copyable commands, expected results and future signing commands are in
[README.md](../README.md#test-and-build) and [MACOS_CHECKLIST.md](MACOS_CHECKLIST.md).
This remaining stage needs macOS; all independent Windows work is delivered.
