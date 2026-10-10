# Verification report — Mini Whiteboard Version 1.1

## Public repository preparation — 2026-10-10

| Check | Actual result | Scope/evidence |
|---|---|---|
| Full local automated suite | **PASSED — 156 tests in 5.428 s** | Windows/offscreen; `verification/public-repository-tests.txt` |
| New hosted Windows workflow | **PASSED — 156 tests in 5.518 s** | [October 10 run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/38040194417), commit `acbfae87756b8acf034f7a4359c425c4fc488633`; Windows Server 2025, Python 3.12.10 |
| Both Actions workflows | **PASSED — actionlint 1.7.12** | Existing Mac pipeline and new Windows tests pipeline |
| Documentation links | PASSED | All relative file targets in the updated guides/reports exist |
| Dependency consistency | PASSED | pip check: no broken requirements |
| Existing tracked history | No findings in the scanned categories | One initial commit; generated-artifact filenames and common credential signatures checked |
| Current documentation privacy | PASSED | Machine-specific absolute paths removed from current files; historical paths remain in the initial commit |
| Workspace Windows package preservation | PASSED | Existing workspace ZIP and EXE match the recorded SHA-256 values below; no rebuild |
| New native GUI/hardware checks | **NOT RUN** | This update changes documentation and repository configuration |

The sandbox initially blocked temporary-file access in 14 tests. The complete
suite then passed outside the sandbox. The history scan is not proof that every
possible secret is absent. The original Desktop archives were not found at their
previously recorded locations; this turn verified the retained workspace release.
The first hosted Windows run passed dependency installation, pip check and the
complete offscreen suite. It does not establish native GUI acceptance on that runner.

## GitHub macOS execution — observed 2026-10-10

The [October 1 Actions run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/36831877399)
**succeeded** for commit `7cd78288558ed1120fa39d7fabf331d438034c2f`.
Its job logs and downloaded verification artifact were inspected on October 10.
The macOS build, Universal2 validation, limited Cocoa startup and ZIP are
**CI VERIFIED**. Interactive native acceptance remains **NOT RUN**.

| Check | Actual result | Evidence/scope |
|---|---|---|
| Runner environment | macOS 14.8.9, arm64; Python 3.13.15 universal2 | Installed-environment/import report and job logs |
| Dependencies and imports | PASSED | PySide6/Qt 6.11.2, PyInstaller 6.22.3, PyObjC 12.2.2; dependency installation and platform selection |
| Full runner suite | **PASSED — 156 tests in 6.712 s** | Complete unittest step |
| PyInstaller app build | **PASSED — Universal2** | Build step and package report |
| Bundle validation | **PASSED — 861 checks** | Metadata, runtime, Mach-O/linkage, symlinks, Windows binary exclusion and signatures |
| Limited packaged startup | **PASSED** | Eight seconds; normal Cocoa termination, exit 0; does not establish interactive acceptance |
| ditto archive and clean extraction | **PASSED** | Root/CRC, complete manifest comparison and extracted-bundle validation |
| Native global input, menus, focus, TCC, capture, Spaces, physical displays | **NOT RUN** | [MACOS_CHECKLIST.md](MACOS_CHECKLIST.md) |
| Intel execution | **NOT RUN** | Universal2 inspection is not execution on Intel |

Inner archive: `MacMiniWhiteboardV1.1.zip`, **74,214,960 bytes**, SHA-256
`56402e4443d09abac57c1a010017bf78d3de3217d9ef80a8898abb3a85cd63f1`.
Artifacts: **MacMiniWhiteboardV1.1** and **macos-v1.1-verification**, expiring
October 31, 2026. The app is an ad-hoc signed tester build; no stable GitHub
Release has been published. See [GITHUB_SETUP.md](GITHUB_SETUP.md) for downloads.

Generated `verification/` and `.test-artifacts/` paths in this report name local
outputs, which are excluded from Git. Hosted evidence is available in the run's
logs and verification artifact. This source-publication update does not rebuild
or publish either platform's binary. Binary distribution notices remain a
separate task; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Historical local CI preparation — 2026-10-01

Before the first hosted run, 156 local tests, actionlint 1.7.12, Mac shell syntax,
Python compilation, dependency consistency and Windows release preservation
passed. Eleven portable tests covered ZIP CRC/root/traversal, manifest changes,
external dependency rejection, metadata/architecture/Windows-file validation and
startup monitoring. These local tests were separate from the real Mac results above.

## Historical cross-platform Windows release verification — 2026-10-01

**At this Windows release stage, the Mac build and native checks had not run.**
The observed Mac CI results above supersede that build status. This section
records the Windows release paths/counts; older refinement evidence follows.

Environment: Windows 11 10.0.26200, Python 3.12.14 x64, PySide6 6.11.2,
PyInstaller 6.22.3. Available hardware: one 1920×1080 display at 100%.

| Check | Actual result | Evidence |
|---|---|---|
| Original release protection | PASSED | `verification/baselines/windows-v11-20261001/manifest.json`; source ZIP, dist/build copies and previous Desktop ZIP |
| Pre-change automated baseline | PASSED — 126 tests | `.test-artifacts/cross-platform-baseline-tests.txt` |
| Platform-refactor gate | PASSED — 126 tests, 110 native checks, real W/S input workflow | `.test-artifacts/platform-refactor-tests.txt`, `verification/platform-refactor-native.json`; completed before substantial Mac code |
| Shared/adaptor suite at startup-order audit | PASSED — 145 tests | `verification/cross-platform-startup-tests.txt`; superseded by the 156-test result above |
| Windows build test gate | PASSED — 143 tests | `verification/cross-platform-tests.txt`; the later Mac-only fix is excluded from the Windows executable |
| Final Windows native regression | PASSED — 111 checks | `verification/windows-cross-platform-native.json`; includes conditional owned activation check, no callback exceptions |
| Final actual Windows keyboard/mouse workflow | PASSED — 33 checks | `verification/windows-cross-platform-hotkeys.json`; distinct W presses, release/repeats, focus, Escape and S capture |
| Final frozen executable | PASSED — 16 checks | `verification/windows-cross-platform-package.json`; GUI subsystem, launch, duplicate instance, placement, pixels, capture and lifetime |
| Windows build | PASSED, exit 0 | `dist/windows-v11/Mini Whiteboard/Mini Whiteboard.exe`; Version 1.1 |
| Windows dependency isolation | PASSED | `verification/cross-platform-audit.json`; no Mac adapter/PyObjC modules in executable's frozen module archive |
| Source compilation, dependency consistency, version | PASSED | compileall; pip check; source `--version` returns Mini Whiteboard 1.1 |
| Screenshot workload | PASSED instrumentation; 28 measured cases | `verification/windows-cross-platform-performance.json`; 21 screenshot cases reuse one raster with no per-gesture decode/geometry/source-image painting |
| Desktop Windows ZIP | PASSED — 165 files | `verification/windows-v11-release-verified.json`; CRC and each SHA-256 match the final distribution |
| Old distribution/build/Desktop tester archive retained | PASSED | `verification/cross-platform-audit.json`; original hashes unchanged |
| Mac shortcut/async capture logic with fake services | PASSED within 145 tests | 13 platform/hotkey/geometry/lock tests, 6 capture/startup-order tests |
| Native bare-Escape feasibility on Mac | NOT RUN | `scripts/macos_escape_probe.py` provided; native result remains open |
| Native Mac lifecycle/windows/focus/Command/clipboard/capture/Retina/Spaces | NOT RUN | `MACOS_CHECKLIST.md`; Windows mocks are not native evidence |
| Mac .app/Universal2/signing/ditto ZIP | NOT RUN | Build/spec/check/release scripts supplied; no Mac artifact is claimed |

Final Windows Desktop archive: `Desktop/WinMiniWhiteboardV1.1.zip`
(45,589,638 bytes). SHA-256:
`97f9d4c48cadab4f89ac2d29a5ce62dfe1542979d80ef8cc055b2e4669851450`.

The existing `MiniWhiteboardV1.1.zip` remains intact with SHA-256
`09bac13fef9ce702855e208784c1dbc07fa97f039121d0e0258218e2797d1b51`.

### Corrections and verification limits

The new lock test caught PySide's three-value `QLockFile.getLockInfo()` return;
the code was corrected and the suite rerun successfully. Async capture retains
temporary Escape registration until completion/cancellation and ignores stale
callbacks. No unresolved automated failure remains.

A follow-up source audit found that Mac platform selection constructed a QObject
and capture timer before QApplication. Capture objects now initialize on first
use and belong to the application. A subprocess test verifies platform selection
with no application and a second test checks reuse/ownership. All 145 tests pass.
This follows [Qt's application/object lifetime requirements](https://doc.qt.io/qt-6/threads-qobject.html).
Only excluded Mac modules and tests changed; the verified Windows release hash
is unchanged. Native Mac startup and shutdown still require actual Mac testing.

An early build invoked through nested PowerShell redirection returned a wrapper
error for normal stderr test output although PyInstaller completed. The final
build was rerun without that wrapper and exited 0; its exact executable passed
the packaged checks and is the one in the verified Desktop ZIP.

Native tests here use owned Windows windows/processes. Real mixed-DPI and negative
monitor layouts, monitor removal, clean-machine deployment, extended use and
hand-operated third-party clipboard apps remain NOT RUN. All Mac native/hardware
checks, including the Escape feasibility gate, remain NOT RUN. Mac signing is
configured for ad-hoc initially; no signature or Universal2 success is claimed.

See [CROSS_PLATFORM_REPORT.md](CROSS_PLATFORM_REPORT.md) for the requested delivery
report and [MACOS_CHECKLIST.md](MACOS_CHECKLIST.md) for exact Mac commands and gates.

## Historical screenshot refinement report — 2026-09-30

Date: 2026-09-30. Windows 11 10.0.26200, Python 3.12.14 (64 bit),
PySide6 6.11.2, PyInstaller 6.22.3. Hardware: **one 1920×1080 display at 100%**.

## Release result

**Implemented, tested, rebuilt, launched and packaged.** The existing Desktop
`MiniWhiteboard.zip` has been replaced with the screenshot-performance/top-border
refinement. Version remains **1.1**. The actual Desktop archive was reopened;
every file matches the new distribution, including the new executable. The
source project remains intact.

| Check | Actual result | Scope |
|---|---|---|
| Pre-refinement baseline | PASS — 112 tests | All existing placement, lifecycle, tools and Version 1.1 regressions |
| Final automated suite and build suite | **PASS — 126 tests** | 112 regressions plus 14 cache, dirty-pixel, locked-query and border/resize tests |
| Windows native suite | **PASS — 110 checks**, no callback exceptions | Hotkeys, focus, topmost, text, tools, clipboard IPC, real capture, cache reuse and all eight native resize directions |
| Real Windows key/mouse workflow | **PASS — 33 checks**, no callback exceptions | Actual W/S key combinations, exact two-press placement, release/repeat handling, screenshot drag, Escape and known pixels |
| Screenshot comparison | COMPLETE — 28 cases per run | Blank/1080p/1440p/4K × seven gestures; before/after native and offscreen runs |
| Paired raster comparison | COMPLETE — three regions | 220 samples per path, direct source painting versus display cache |
| PyInstaller build | PASS | 126 tests, icon, Version 1.1 resources, manifest, runtime dependencies and GUI executable |
| Packaged executable | **PASS — 16 checks** | Launch, duplicate launch, no startup board, W placement, actual border pixels, completed screenshot capture, S/Escape and tray lifetime |
| Compilation / dependencies / version | PASS | compileall, pip check, source version command returns Mini Whiteboard 1.1 |
| Desktop ZIP contents and integrity | **PASS — 165 files** | Every CRC and SHA-256 matches distribution; EXE metadata is 1.1; no source/tests/logs/development environment |
| Owned-widget visual inspection | PASS | Screenshot reaches side/bottom edges without a white rim; top line, rounded clipping, small controls and soft shadow retained |

The native and packaged checks are scripted Windows GUI tests using disposable
owned windows, with real mouse input where stated. They are not a claim of a full
hand-operated acceptance pass. Tests restore the pointer and close only their
owned windows/processes. Clipboard interoperability uses owned Windows processes.

## Diagnosis and implementation

### Confirmed extra work

The previous source image passed through its transformed, smoothly scaled paint
path and canvas clipping on every relevant dirty paint, despite being locked and
unchanged. Freehand drawing invalidated the old/new bounds of the whole growing
stroke. Scene queries scanned locked-object bounds before tool filtering, and
locked screenshots entered Smart Guide targets.

**The reported severe stutter was not reproduced on this hardware.** These are
verified sources of unnecessary work. Removing them is supported by paint/cache
instrumentation and paired raster timings, not a claim that they explain every
possible slowdown on other machines.

### Operations already efficient before this change

The screenshot was decoded once and its paint geometry cached. Document history
already shared immutable ImageObjects and PNG bytes; it did not duplicate or
serialize image pixels for each annotation. Most gestures already used dirty
regions. There was no clipboard polling during annotation. These properties are
preserved and tested explicitly.

### New cache and dirty regions

`ScreenshotBackground` keeps a display-resolution premultiplied QImage for the
original locked capture. Its physical size is logical viewport × DPR once; source
PNG pixels remain unchanged. Cache creation renders the source transform and
rounded/control clipping once. Subsequent paints perform a one-to-one blit under
Qt's dirty event clip, preserving object stacking and transparent control holes.

Viewport/DPI/clip changes rebuild it. Annotation content and history do not.
Unlocking or changing the image uses the existing editable image renderer with
cached decoding/geometry. Selection, movement, proportional resize, rotation,
copying and guide participation remain available after context-menu unlock.
Undo to the original locked state can reuse the cache.

Drawing now updates only the changing curve tail plus pen/antialias padding. A
pixel test reconstructs incremental updates and compares them with full rendering
across sharp turns. Erasers retain swept/affected bounds; transforms retain
old/new selection regions. Marquee, guides, handles and eraser cursors stay on the
separate passive overlay. Large selections can still legitimately dirty most of
a board.

Locked objects are removed from the editable candidate order before click,
marquee and eraser bounds/detail testing. Whole-stroke erasing filters non-strokes
early. Locked images are omitted from Smart Guide candidates. Context unlocking
still has access to the full object order.

## Border and resizing

- Paper is filled as a rounded white surface with **no outline pen**.
- The only border is a **1 logical px** line in neutral grey **#dadce0** across the
  straight top span. Its colour/width remain in central settings.
- There are no grey side/bottom lines or curved outline segments down the lower
  corners. Removing the former 2 px canvas inset also eliminates a white rim
  around screenshots. Actual content remains clipped to the rounded paper and
  control holes.
- Existing 12 px corner radius, 8 px shadow extent, subtle shadow rendering,
  11 px top strip, minimise/close controls and always-on-top behaviour remain.
- **EDGE_GRIP = 7 logical px** provides invisible resize targets on all four
  edges and four corners, with matching cursors. Their dimensions are independent
  of the visible line. The remaining narrow top region drags the board.
- Idle canvas events explicitly route those zones to window resizing. Object
  transform handles and active canvas gestures retain priority; controls retain
  their existing input targets. Passive interaction overlays can extend beyond
  the document clip.

Native real-mouse checks grew the window from all eight directions without
changing document contents. Pixel checks verified the top line and clean
left/right/bottom pixels on blank and screenshot boards. A visual inspection
caught a remaining white inset during development; it was removed and the final
pixel/native suite rerun.

## Performance evidence and limits

Every fixture contains **20 strokes + 20 shapes + 10 text objects**, with 10
annotations selected for group transforms. Sources: 1920×1080, 2560×1440 and
3840×2160. The board is 1280×820; the final display cache is 1264×793 at DPR 1.
Native runs use 60 pointer samples per case; offscreen runs use 120.

| Operation | Native 4K before, ms | Native 4K after, ms | Native blank after, ms |
|---|---:|---:|---:|
| Drawing | 1.699 | 1.385 | 1.289 |
| Circular erase | 1.613 | 1.814 | 1.796 |
| Whole-stroke erase | 1.174 | 1.424 | 1.249 |
| Marquee | 1.530 | 1.861 | 1.524 |
| Move 10 | 3.410 | 3.740 | 3.524 |
| Resize 10 | 3.253 | 3.528 | 3.466 |
| Rotate 10 | 3.921 | 4.090 | 4.583 |

These are median gesture/event-processing times, not FPS. Native screenshot
interaction is close to blank in this fixture. **Most total-event medians did not
improve in the before/after run**, and the offscreen 4K draw/resize results show
larger increases. Short sequential measurements are load-sensitive. No universal
speedup or complete resolution of the reported stutter is claimed.

The consistent reductions are:

- **Zero source-image paints** during annotation gestures after initial caching,
  versus up to 62 in the native before case. Zero repeated decodes both before
  and after; one cache build per setup and none during annotation work.
- Native drawing mean document repaint area **3.410% → 0.576%**, about **83% less**
  including release. Pixel equality verifies the narrower update does not leave
  stale drawing artifacts.
- Paired raster timings: 32×32 region **0.0414 → 0.0067 ms**; 160×80
  **0.0633 → 0.0105 ms**; 600×300 **0.2744 → 0.0650 ms**. This is 4.2–6.2× for
  the background raster step alone, excluding all other interaction costs.

The view cache adds about **3.82 MiB** at the tested viewport/DPR while retaining
original source quality. Synthetic DPR 1/1.25/1.5/2 tests verify cache sizes and
pixel equivalence. Full before/after tables, p95, commits, counters, profiles,
methods and reproduction commands are in [PERFORMANCE.md](PERFORMANCE.md).

## Existing features retained and tested

The complete existing suite covers drawing, shapes, proportional text transforms,
masked text editing, both erasers and key-5 toggle, A/V selection, move/resize/
rotation, colours, copy/paste/image import, Smart Guides, Grid Snap, locking,
context commands, undo/redo, minimise/restore, always-on-top and tray lifecycle.
Native checks exercise transformed QTextEdit focus and typed tool keys. Canvas
shortcuts still require an active board, canvas focus and no editor; the editor's
ShortcutOverride keeps ordinary letters/numbers, clipboard commands and Ctrl+Z
inside text editing.

The real-key suite separately verifies exact first-corner/second-corner W
placement, reverse direction, invalid-small retry, MOD_NOREPEAT/key release and
capture/placement switching. Production hotkey and placement logic was unchanged.
The packaged app also completed a screenshot capture, exercising the bundled new
background module.

## Executable and replaced archive

- EXE: `dist/Mini Whiteboard/Mini Whiteboard.exe`
- EXE bytes: **1,849,849**.
- EXE SHA-256: `3cc32a2034dc4bd14e981febb08b79dd38957ff9b2d233143b18b0ff902139d1`.
- ZIP: `Desktop/MiniWhiteboard.zip`.
- ZIP bytes: **45,577,426**, about 45.6 MB (43.5 MiB).
- ZIP SHA-256: `09bac13fef9ce702855e208784c1dbc07fa97f039121d0e0258218e2797d1b51`.
- All **165 runtime files** are under `Mini Whiteboard/`, including `_internal`.
  ProductVersion/FileVersion are **1.1**; numeric version/manifest remain 1.1.0.0.
- The replaced pre-refinement Version 1.1 EXE had SHA-256
  `64ca8a6cfefeca239fcd7376e2dc816d2a003ba1daa1f6838a86226cab10168a`.
  The new archived executable differs and matches the rebuilt distribution.
  The previous ZIP was 45,574,180 bytes; it is no longer the Desktop archive.

Recipients should **extract the ZIP**, open **Mini Whiteboard**, and run
**Mini Whiteboard.exe**, keeping `_internal` beside it. Python is included.
The app starts in the tray; Ctrl+Alt+W places a blank board and Ctrl+Alt+S starts
screenshot selection.

```powershell
& '.\dist\Mini Whiteboard\Mini Whiteboard.exe'
# Source:
.\.venv\Scripts\python.exe '.\Main App.py'
```

The portable distribution remains unsigned. Documents are session-only; only
Snap & Guides preferences persist. No runtime dependency or installation step
was added by this refinement.

## Changed files in this refinement

| Area | Files |
|---|---|
| Screenshot cache | New `mini_whiteboard/background.py`; updated `app.py`, `canvas.py` |
| Early query filtering / guides | `mini_whiteboard/scene.py`, `snapping.py` |
| Border, clipping and resize routing | `mini_whiteboard/settings.py`, `board.py`, `canvas.py` |
| Automated regressions | New `tests/test_screenshot_refinement.py`; updated `tests/test_polish.py` |
| Profiling and Windows verification | New `scripts/screenshot_performance.py`, `raster_cache_check.py`, `refinement_smoke.py`; updated `v11_smoke.py`, `polish_smoke.py`, `hotkey_workflow_check.py`, `package_check.py` |
| Documentation | `README.md`, `SPEC.md`, `PLAN.md`, `MANUAL_TESTING.md`, `PERFORMANCE.md`, `TEST_RESULTS.md` |
| Delivery / evidence | Rebuilt `dist/Mini Whiteboard`, build logs, benchmark/native artifacts, release manifests and replaced Desktop ZIP |

F1 shortcut text is unchanged because this refinement adds no user command.

## Evidence

- [126-test log](verification/final-tests-refinement.txt), [production build log](verification/build-refinement.txt).
- [110 native checks](verification/native-smoke.json), [33 real-input checks](verification/hotkey-workflow.json), [16 packaged checks](verification/package-check.json).
- [Actual Desktop ZIP manifest and per-file hashes](verification/release-manifest.json).
- [Screenshot border visual](verification/refinement-screenshot-border.png), [blank board](verification/board-monitor-1.png), [F1](verification/help-monitor-1.png).
- [Native before](verification/screenshot-native-before.json), [native after](verification/screenshot-native-after.json), [paired raster](verification/screenshot-raster-comparison.json).

Earlier packaged-test attempts stopped on test-pointer timing and pixel sampling
at assumed bounds. The final harness uses the actual owned window bounds and
immediate guarded pointer input; all 16 checks passed. A paint-test mock also
retained a live QPainter beyond widget deletion; replacing it with a plain
instrumentation function removed that test-lifetime fault. Final automated,
native and build runs completed without that fault. PowerShell's build log may
label normal unittest/PyInstaller stderr as NativeCommandError; the build exited
zero and its new executable passed independent launch and archive checks.

## NOT RUN — manual and hardware checks

See [MANUAL_TESTING.md](MANUAL_TESTING.md), especially K for this refinement.

- Physical 1440p/4K displays, secondary displays, negative desktop coordinates,
  mixed-DPI transitions at 125/150/175/200%, cross-display capture and monitor
  removal. Large source images and synthetic raster DPR were tested instead.
- Prolonged hand-operated responsiveness/memory with many 4K screenshot boards,
  large histories and very long strokes; at least 60 seconds of idle observation.
- Full hand-operated editing/capture acceptance in the frozen executable and
  deployment on a clean Windows machine without Python.
- Hand-operated image copy/paste in Paint, Word, OneNote, Discord, browsers and
  Snipping Tool. Windows clipboard IPC between owned processes passed.
- Extended custom-colour/native context-menu/tray/file-drag ergonomics, guide and
  rotated-group feel, every object handle at all display scales, and IME/RTL/emoji
  editing. Automated command/focus/geometry coverage does not replace these.
- Extended visual judgement on bright/dark desktops and real fractional-DPI
  rounding/shadow appearance. The final 100% screenshots were visually inspected.

No claim is made that pending checks passed. Source image import remains limited
to 64 million pixels and editable clipboard data to 96 MB. Protected/secure
content may not be available to native screenshot capture.
