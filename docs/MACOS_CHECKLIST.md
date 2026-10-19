# macOS 14+ acceptance checklist — Mini Whiteboard 1.2

[V1.2 CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39256527611)
passed 191 tests, 769 Universal2 bundle checks, eight-second Cocoa startup and
375-entry ditto ZIP extraction/revalidation. Actual environment: macOS 15.7.9,
arm64, Universal2 Python 3.13.15, source 08b3893. Minimum app support remains 14.0.
The unchanged inner ZIP is published as MacMiniWhiteboardV1.2-Preview.zip.
These automated checks do not complete the interactive checklist below.

**Interactive acceptance: NOT RUN.** Record PASSED, FAILED or NOT RUN for
each interactive item on a real Mac. Keep OS, architecture, display setup,
source revision/hash, signature and logs with results.

Historical V1.1 evidence: [the October 11 release run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/38108550854)
passed 162 tests, Universal2 build/769 bundle checks, an eight-second packaged
Cocoa startup check, and ditto ZIP extraction/revalidation. The package has 15
verified notice files. Runner: macOS 14.8.9, arm64, Python 3.13.15.
Those checks are **CI VERIFIED**. Limited startup does not establish global
input, menu use, TCC, focus or physical display behaviour. The download remains
a **Mac preview**. Intel execution and all interactive acceptance below remain
**NOT RUN**. See [TEST_RESULTS.md](TEST_RESULTS.md) and
[GITHUB_SETUP.md](GITHUB_SETUP.md).

## 1. Setup and Escape feasibility gate

Install the standard python.org universal2 Python 3.13 (not its free-threaded
variant) and Xcode Command Line Tools. Copy this source project without Windows
environments/distributions. Run these commands from the project directory:

```bash
xcode-select --install
python3.13 -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements-dev.txt -r requirements-macos.txt
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m unittest discover -v
.venv-macos/bin/python -m scripts.macos_escape_probe
```

- [ ] Exit any running Mini Whiteboard. Leave Accessibility permission for this
  Python/Terminal host off. Focus TextEdit or Finder and press bare Escape within
  45 seconds. `verification/macos-escape-probe.json` must record an external PID,
  an observed event, and Accessibility not already granted for a permission-free
  **PASSED** result. Repeat with another foreground app and supported OS versions.
- [ ] If registration fails or delivery is unreliable, record actual OS/error and
  do not claim global Escape works. Check menu-bar **Cancel placement / screenshot**
  as the least invasive available alternative. No Accessibility prompt, event tap,
  permanent keyboard polling or persistent foreground focus may be introduced silently.
  V1.2 temporarily samples Carbon hardware state during holds/release cleanup;
  check that it stops when idle and requests no new permissions.
- [ ] After the probe exits, Escape reaches the foreground app normally again.

The source supports the temporary registration path provisionally; this native
gate is still open. Continue unrelated capture, model and packaging checks if
the gate fails, keeping the limitation explicit.

## 2. Source native smoke and real input

```bash
.venv-macos/bin/python -m scripts.macos_native_smoke
.venv-macos/bin/python -m scripts.macos_native_smoke --capture
.venv-macos/bin/python -m scripts.screenshot_performance --native --frames 30 --repeats 2 --output verification/macos-performance.json
.venv-macos/bin/python 'main.py'
```

The native smoke uses owned windows and Qt-delivered key events; it does not
prove physical global shortcut delivery. `--capture` can request Screen Recording
permission. Source launch and the frozen bundle may have different TCC identities;
repeat permission checks using the installed bundle.

- [ ] One menu-bar icon, no board/dashboard/splash/Dock icon at startup.
- [ ] Physical Control+Option+W: hold anchors, move updates passive dotted
  preview, release W or any required modifier creates exactly one board. No
  initial board, second press, clicks or minimum hold time. Test four directions,
  negative coordinates, minimum size cancellation, repeats and fresh recovery.
- [ ] Test the persisted Command+Option+Shift+W/S preset, including conflict/retry.
  Check the default with VoiceOver settings; do not overwrite system bindings.
- [ ] Cancel placement and screenshot selection with external focus. Confirm
  overlays/timers disappear and subsequent W starts at a fresh first corner.
- [ ] Physical Control+Option+S uses the same hold, move, release gesture and creates
  one locked screenshot background with Draw active. Competing W/S holds are ignored.
- [ ] Test trigger-first and each modifier-first release in both presets; remaining
  held S must not activate Shape. Escape while held cancels without a restart.
- [ ] Quit during each workflow; restart and verify registrations are available.

## 3. Windows, focus, Spaces and lifecycle

- [ ] Frameless rounded paper, thin top border only, no side/bottom outline or
  screenshot rim, soft shadow, narrow drag strip, two usable controls and no Pin.
- [ ] All eight invisible resize directions and top-strip dragging. Tool handles
  take precedence. Tool visuals can extend beyond paper but cannot cover controls.
- [ ] Boards remain above an ordinary foreground app for at least 30 seconds
  without taking keyboard focus. Typing stays in that other app.
- [ ] Create/restore focuses the requested board. Minimise retains content and
  undo; the Whiteboards submenu restores that same board.
- [ ] Multiple independent boards; closing the last leaves the menu item alive.
- [ ] Launch twice, including from Finder: exactly one owner/menu/hotkey manager.
  Quit, then relaunch. Check recovery after terminating an owned test instance.
- [ ] Spaces: boards stay in their Space normally; explicit restore works from
  another Space. Do not force CanJoinAllSpaces.
- [ ] Mission Control, Stage Manager and full-screen apps: record actual behaviour
  and limitations. Universal full-screen overlay coverage is not an acceptance claim.
- [ ] Idle CPU after closing boards stays low; no placement/capture timer remains.

## 4. Tools, text and clipboard

- [ ] Draw and five sizes; seven shapes/creation constraints/endpoint editing.
- [ ] A/V topmost/Shift/marquee selection; shared move, anchored scale and rotation;
  proportional text/image resizing; snapping bypass with Option; Delete/Backspace.
- [ ] Partial erasing of strokes/shapes/text/images; whole-stroke toggle on key 5;
  per-board sizes/mode memory; one undo per gesture; Escape rollback.
- [ ] Colour palette/custom/recent colours, ordering, locking and unlocking.
- [ ] Physical Command+C/X/V/D/A/Z and Command+Shift+Z; arrow/Shift-arrow nudging.
- [ ] Edit rotated/masked multiline text. Type **A V E 12345 C D S T**, use Delete,
  Backspace, Command+A/C/X/V/Z/Shift+Z, context menu, Return, Escape and
  Command+Return. Only the editor owns these actions; document undo remains
  separate until commit. Test focus after an outside-click commit.
- [ ] Smart Guides/Grid Snap preferences and global shortcut preset survive exit.
  Board contents remain session-only.
- [ ] Mini Whiteboard → Mini Whiteboard retains editable transforms/masks/colours.
- [ ] Mini Whiteboard → Preview/another image app carries the rendered image.
- [ ] Browser image, native clipboard screenshot, Preview image → Mini Whiteboard.
- [ ] Finder copied PNG/JPG/WEBP files where Qt exposes URLs; drag/drop too.
  Record any unsupported format before adding a native pasteboard fallback.

## 5. Screen Recording, Retina and performance

- [ ] Fresh permission state: useful explanation and native request; denial leaves
  no overlay or empty board. Open System Settings reaches the permission panel.
- [ ] Grant, restart if required, capture again. Revoke while running and repeat.
  No microphone or Accessibility prompt for screenshots.
- [ ] Capture asymmetric known content; inspect top/bottom orientation, correct
  crop edges/colours, absence of cursor/selection overlay and image dimensions.
- [ ] Retina and non-Retina displays; different scales, left/top negative origins,
  spans across displays and desktop gaps; no DPR applied to global origins.
- [ ] Move/resize boards between displays; cache has viewport×DPR pixels once.
  Source PNG identity survives annotations, undo/redo, unlock/transform/relock.
- [ ] Disconnect a selected display during placement/capture: clean cancellation.
- [ ] Capture errors/timeouts/late callbacks produce no unexpected board.
- [ ] Compare blank/1080p/1440p/4K workloads in `macos-performance.json`; verify
  one cache build and no image decode/geometry/source rendering during gestures.
  Inspect real pointer responsiveness; timing results are not display FPS.

## 6. Build, install and packaged acceptance

```bash
bash build_macos.sh
open 'dist/macos-v12/Mini Whiteboard.app'
```

- [x] **CI VERIFIED for the October 1 artifact:** build first attempts Universal2. Read `verification/macos-build-universal2.txt`.
  Only an actual architecture mismatch permits arm64 fallback; record the exact
  binary/blocker. `macos-package-check.json` checks every Mach-O slice, signature,
  internal symlink and absence of build-machine Python/Homebrew paths.
- [x] **CI VERIFIED for the October 1 artifact:** inspect `Contents/Info.plist`: bundle ID `com.brad.miniwhiteboard`, both versions
  1.1, minimum 14.0, LSUIElement, correct icon and screen-capture purpose string.
- [ ] Launch by Finder on a clean supported Mac without Python installed; no
  Terminal. Repeat sections 1–5 against the packaged app, especially global keys,
  TCC permission identity, editor focus and clipboard interoperability.
- [ ] Test native arm64; test Intel separately if shipping a Universal2 claim.
  A universal binary inspection alone does not constitute Intel execution testing.
- [ ] Download/quarantine test with an ad-hoc build and Apple's supported
  [Open Anyway flow](https://support.apple.com/en-au/102445). Never disable Gatekeeper globally.

Initial signing is ad-hoc and needs no Apple Developer membership. For a future
Developer ID release, rebuild with the identity, verify hardened runtime signing,
then notarise and staple before re-verifying/repackaging:

```bash
MINIWHITEBOARD_SIGNING_IDENTITY='Developer ID Application: NAME (TEAMID)' bash build_macos.sh
.venv-macos/bin/python -m scripts.macos_package_release
xcrun notarytool submit build/releases-v1.2/MacMiniWhiteboardV1.2.zip --keychain-profile YOUR_PROFILE --wait
xcrun stapler staple 'dist/macos-v12/Mini Whiteboard.app'
.venv-macos/bin/python -m scripts.macos_package_check --architecture universal2
.venv-macos/bin/python -m scripts.macos_package_release
```

Use `--architecture arm64` if that was the actual build target. These signing
commands are future steps and have not been run in this Windows session.

## 7. Mac archive and Windows transfer

Automated tester packaging may run in CI before interactive acceptance. Keep
unperformed native checks marked NOT RUN; record them separately when performed.
For local Mac packaging after bundle validation:

```bash
.venv-macos/bin/python -m scripts.macos_package_release
shasum -a 256 build/releases-v1.2/MacMiniWhiteboardV1.2.zip
```

- [x] **CI VERIFIED for the October 1 artifact:** archive contains `Mini Whiteboard.app` at the root. `ditto` round-trip verifies
  hashes, executable modes, symlinks and code signature. Store the release JSON.
- [ ] Transfer that ZIP unchanged to the Windows Desktop; do not extract/repack.
  Compare `Get-FileHash -Algorithm SHA256` with the Mac hash. Preserve the existing
  Windows tester archive. Final Desktop files: `WinMiniWhiteboardV1.2.zip` and
  `MacMiniWhiteboardV1.2-Preview.zip as separate platform packages.

## V1.2 wrapping and runner acceptance

- [ ] Repeat wrapped editing/reopen, long URLs, newlines, caret visibility, font
  presets, transforms, masks, clipboard, history and board resize checks from
  [the Windows checklist](MANUAL_TESTING.md#v12-wrapped-text-acceptance).
- [ ] Confirm deployment target/Info.plist/runtime minimum stay 14.0 when built
  on the macos-15 runner. Record real OS/CPU; test macOS 14 and Intel on actual
  hardware before claiming interactive behaviour was verified there.
