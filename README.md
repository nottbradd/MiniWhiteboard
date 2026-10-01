# Mini Whiteboard — Version 1.1

A small desktop whiteboard controlled from the keyboard. Windows uses a tray
icon; the macOS 14+ implementation uses a menu-bar item. Launch opens no board.

**Current status (2026-10-01):** Windows is tested. The GitHub-hosted macOS build
workflow is prepared; its first actual run is **PENDING repository creation and
push**. No Mac `.app` or ZIP is claimed yet. Interactive native Mac checks are
**NOT RUN**. See [GITHUB_SETUP.md](GITHUB_SETUP.md) for the Windows-to-Mac build
steps and [CROSS_PLATFORM_REPORT.md](CROSS_PLATFORM_REPORT.md) for actual results.

Version 1.1 adds editable copy/cut/paste/duplicate, screenshot and image paste,
arrow-key movement, a temporary colour palette, object locking and ordering,
Smart Guides, optional Grid Snap, and **Ctrl+Alt+S** screenshot-to-whiteboard.
The exact two-press **Ctrl+Alt+W** placement workflow and existing tools remain.

## Share or run the release

Windows: extract **WinMiniWhiteboardV1.1.zip**, open the **Mini Whiteboard** folder, and run
**Mini Whiteboard.exe**. Keep its `_internal` folder beside the executable.
The release includes Python and Qt; recipients do not need to install Python.
The new archive is `WinMiniWhiteboardV1.1.zip` on the Windows Desktop. The previous
tester archive is preserved.
It is built for 64-bit Windows 10/11 and launches into the tray, including the
hidden-icons area. No administrator rights or installation are required.

## Windows: install and run from source

Use 64-bit Python 3.12 on Windows 10 or Windows 11. The implementation is tested
with Python 3.12.14 and PySide6 6.11.2. No administrator rights are required.

From PowerShell in this project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe '.\Main App.py'
```

If Python is installed without the `py` launcher, use its full `python.exe` path
for the first command. You can also launch with:

```powershell
.\.venv\Scripts\python.exe -m mini_whiteboard
```

Development launch uses the terminal for diagnostics. The packaged application
has no console. There are no accounts, network services, startup entries, or
Windows services.

## macOS: installation and operation

The intended tester archive is **MacMiniWhiteboardV1.1.zip**, containing
**Mini Whiteboard.app**. It must first be built and verified on actual macOS;
the GitHub-hosted runner can perform that build. Once
available, extract it there, move the app to Applications, and open it. Use its
menu-bar item; there is no startup board, dashboard or Dock workflow. Closing
the last board keeps the utility alive. **Quit Mini Whiteboard** exits.

For a trusted ad-hoc tester build blocked by Gatekeeper, attempt to open it, then
use **System Settings → Privacy & Security → Open Anyway**, and confirm **Open**.
Follow [Apple's supported instructions](https://support.apple.com/en-au/102445).
Developer ID signing/notarisation are not required for this initial tester build.

| Action | Windows | macOS |
|---|---|---|
| Place a board, two distinct presses | Ctrl+Alt+W | Control+Option+W |
| Capture a region | Ctrl+Alt+S | Control+Option+S |
| Copy / cut / paste / duplicate | Ctrl+C / X / V / D | Command+C / X / V / D |
| Select all | Ctrl+A | Command+A |
| Undo / redo | Ctrl+Z / Ctrl+Shift+Z | Command+Z / Command+Shift+Z |
| Bypass snapping | Alt | Option |
| Finish editing text | Ctrl+Enter or Escape | Command+Return or Escape |
| Help | F1 | F1 or Fn+F1 |

All tools and numbered sizes below are shared. The Mac **Global shortcuts** menu
offers **Command+Option+Shift+W/S** for conflicts, including VoiceOver use. The
preset, Smart Guides and Grid Snap are remembered. Use **Retry global shortcut**
after resolving a registration conflict.

Mac boards use a floating level above ordinary windows and activate on creation
or explicit restore. There is no Pin control. Space membership remains normal;
overlaying every full-screen app is not guaranteed.

Bare Escape is registered temporarily during placement/capture. A real Mac must
verify that it works while another app is focused without Accessibility access.
The app reports rejected registrations and offers **Cancel placement / screenshot**
in the menu bar. It does not poll the keyboard or request Accessibility access.

**Screenshots:** Control+Option+S → click-drag → release creates a locked background,
ready to draw. ScreenCaptureKit requests Screen Recording permission when needed.
The app explains why and offers **Open System Settings**. Enable Mini Whiteboard
under Privacy & Security → Screen Recording (or Screen & System Audio Recording),
then restart if asked. Denial or failure creates no blank board. No microphone
access is requested. Positions stay in desktop points; each display's pixels are
composed explicitly and the display cache applies DPR once.

**Clipboard:** use Command+V, including after Control+Shift+Command+4 copies a
screenshot. Qt's clipboard and editable object format are retained. Native
Preview/browser/Finder interoperability still needs the Mac checklist.

### Build through GitHub from Windows

[GITHUB_SETUP.md](GITHUB_SETUP.md) covers creating the empty private repository,
pushing the prepared source, **Actions → macOS V1.1 → Run workflow**, and downloading
the **MacMiniWhiteboardV1.1** artifact. The workflow installs Mac dependencies,
runs imports and the full automated suite, builds with the existing shell/spec,
checks the bundle, briefly launches it if a login session is available, and creates
and round-trips a `ditto` ZIP on the requested `macos-14` runner. Verification logs
are retained as a separate artifact. No Windows release build runs in this job.

After the job succeeds, extract GitHub's outer artifact archive on Windows to get
the inner **MacMiniWhiteboardV1.1.zip**, then send that inner file unchanged to Mac
testers. A successful build remains a tester/beta release until the interactive
checks in [MACOS_CHECKLIST.md](MACOS_CHECKLIST.md) are completed.

### Build on macOS 14+

Use the standard universal2 Python 3.13 from python.org and Xcode Command Line
Tools. Copy the source project to the Mac, leaving the Windows `.venv`, `build`
and `dist` folders behind. From the Mac project directory:

```bash
python3.13 -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements-dev.txt -r requirements-macos.txt
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m unittest discover -v
.venv-macos/bin/python -m scripts.macos_escape_probe
.venv-macos/bin/python -m scripts.macos_native_smoke
.venv-macos/bin/python -m scripts.macos_native_smoke --capture
bash build_macos.sh
open 'dist/macos-v11/Mini Whiteboard.app'
```

During the Escape probe, focus another app and press bare Escape within 45 seconds
with Accessibility permission off. Record its result before placement acceptance.
Complete [MACOS_CHECKLIST.md](MACOS_CHECKLIST.md), including the packaged app.

The build attempts Universal2 and checks every frozen Mach-O file. A demonstrated
`IncompatibleBinaryArchError` permits an arm64 retry on Apple Silicon, retaining
the failed log. Other build errors stop. Universal2 and Intel are not yet verified.
After native acceptance:

```bash
.venv-macos/bin/python -m scripts.macos_package_release
shasum -a 256 build/MacMiniWhiteboardV1.1.zip
```

The Mac release script uses `ditto`, then verifies the extracted hashes, executable
modes, symlinks and signature. Transfer the finished ZIP unchanged to the Windows
Desktop and compare its SHA-256 using `Get-FileHash -Algorithm SHA256`.

The spec uses `com.brad.miniwhiteboard`, Version 1.1, minimum macOS 14.0, `LSUIElement`,
an `.icns`, and a screen-capture purpose string. The default signature is ad-hoc.
A later Developer ID build can set `MINIWHITEBOARD_SIGNING_IDENTITY`, then be
notarised and stapled before recreating the ZIP. See the Mac checklist for commands.

## Place a board: press → move → press again

The detailed examples below use Windows key names. On Mac, use the mapping above
and the menu-bar item in place of the tray.

1. Put the cursor at the first corner while using any normal desktop application.
2. Press **Ctrl+Alt+W**, then release the keys. This records the first corner.
3. Move the mouse, with no mouse button or shortcut held. Small translucent white
   dots follow the cursor, with a faint shadow for bright backgrounds. The desktop
   remains visible through the outline.
4. Press **Ctrl+Alt+W** again. The selected rectangle becomes a focused board.

The first corner can be any of the four corners. **Escape** cancels placement.
Holding the shortcut does not count as two presses. Selections smaller than
**160 × 100 logical pixels** show a tray message and stay in placement mode with
the same first corner. Move farther and press again.

Each new pair of presses creates a new independent board. The paper body matches
the selected rectangle; its shadow extends beyond that rectangle. Windows keeps
physical desktop coordinates, including negative monitor coordinates, and uses
the monitor with greatest overlap for initial sizing. Mac keeps desktop points
throughout placement. Real mixed-scale hardware checks are listed in TEST_RESULTS.md.

If Ctrl+Alt+W is already registered elsewhere, the app explains the conflict.
Release that binding in the other application, then use **Retry global shortcut**
in the tray menu. Escape is registered globally only during placement or capture.

## Tools and shortcuts

Tool shortcuts affect only the focused board and are disabled while editing text.
New boards start in Draw mode. Each board remembers its tool settings.

| Key | Tool | Number mappings |
|---|---|---|
| **D** | Draw | 1 = 2 px, 2 = 4 px, 3 = 6 px, 4 = 9 px, 5 = 14 px |
| **T** | Text | 1 = 14 pt, 2 = 20 pt, 3 = 28 pt |
| **S** | Shapes | 1 Rectangle, 2 Rounded rectangle, 3 Ellipse, 4 Line, 5 Arrow, 6 Triangle, 7 Diamond |
| **A / V** | Select and transform | Both keys activate the same tool |
| **E** | Eraser | 1 = 8 px, 2 = 16 px, 3 = 32 px, 4 = 64 px; 5 toggles whole stroke |

Draw with the left mouse button. A click creates a dot. Pen thickness changes
apply to future strokes. Create all seven shapes by dragging in S mode; Shift
creates squares/circles, starts other closed shapes at 1:1, and snaps line/arrow
angles to 45 degrees. In S mode, single lines/arrows retain endpoint editing.

### Select and transform

- Press **A** or **V**. Click to select the topmost matching object. Thin strokes
  have a small hit tolerance. Shift+click toggles membership.
- Drag empty canvas outside the transform box to draw a marquee, in any direction.
  Only objects fully contained in it are selected, including their stroke width,
  rotation, and scaling. Shift+marquee adds. Offscreen portions still count.
- Drag a selected object or the shared box interior to move the group. Click empty
  canvas without dragging to clear selection.
- Circular corner handles scale proportionally. Edge handles scale one axis;
  Shift preserves the current ratio. Any selection containing text always scales
  proportionally. Objects and spacing scale together around the opposite anchor.
- Drag the handle above the box to rotate the whole group around its centre.
  Shift snaps to 15-degree increments. Crossing a resize anchor never mirrors.
- Escape cancels a drag and restores its starting state. Otherwise it clears the
  selection after any open help panel is dismissed.

### Erase

Circular mode removes only ink inside the swept brush, leaving outside portions
intact. It works on freehand strokes, shape outlines, arrowheads, and rendered
text. Cuts stay attached through movement, scaling, rotation, and text editing.
Underlying objects remain editable. Every overlapping object beneath the brush
is affected; new content drawn over an old cut remains visible.

New boards default to a **16 logical-pixel circular brush**. Each board remembers
its mode and diameter. Keys **1–4** choose a diameter and return to circular mode.
Key **5** toggles whole-stroke mode. When enabled, touching any surviving fragment
removes that original freehand stroke; shapes and text are unaffected. Entering
this mode retains the current diameter for targeting. **Press 5 again to return
to circular mode at the default size 2 (16 px)**. Pressing 1–4 immediately selects
that circular diameter instead.

The brush shows a solid thin circle for circular erasing and a subtly dashed circle
for whole-stroke targeting. Its full outline can extend beyond the paper edge.
Actual drawing and erasing remain restricted to valid canvas pixels; controls
stay above tool visuals.

| Shortcut | Action outside text editing |
|---|---|
| C | Open the temporary colour palette; 1–7 choose presets |
| Ctrl+C / Ctrl+X | Copy / cut selected editable objects and an image to Windows clipboard |
| Ctrl+V | Paste editable objects, a clipboard image, or copied local image files |
| Ctrl+D | Duplicate selection by 16 px right/down |
| Ctrl+A | Select all unlocked objects |
| Arrow / Shift+Arrow | Nudge the selection 1 / 10 logical pixels |
| Alt while moving/resizing | Temporarily disable Smart Guides and Grid Snap |
| Ctrl+Alt+S | Click-drag a desktop region to create a screenshot board |
| Ctrl+Z | Undo |
| Ctrl+Y or Ctrl+Shift+Z | Redo |
| Delete or Backspace | Delete all selected objects in one action |
| Escape | Cancel the current interaction, hide help, or clear selection |
| F1 | Show/hide the compact shortcut reference |

A drag or continuous eraser gesture is one undo action. Undo/redo covers object
creation, multi-deletion, both eraser modes, group movement/resizing/rotation, committed text edits, and
font-size changes. Canceling an unfinished gesture leaves the document unchanged.
Tool and size changes produce a brief fading label; there is no toolbar.

## Copy, images, colour and selection

**Copy/cut/paste:** use Ctrl+C/X/V; Ctrl+D duplicates without replacing the
clipboard. Mini Whiteboard copies a validated JSON MIME payload with the original
objects, transforms, erasure masks, colours and stacking order. Every pasted copy
gets a new identity. Same-board pastes move by 16 px right/down, then 32 px, 48 px,
and so on; the first paste into another board preserves coordinates. Repeated
cross-board pastes also advance by 16 px. `PASTE_OFFSET` controls this distance.
Windows clipboard also receives a transparent rendered image for other apps.
That image is limited to 4096 px on its longest side; editable object data retains
full source detail. Guides, handles and controls are excluded.

**Images:** copy a screenshot with Snipping Tool/Win+Shift+S or copy an image from
another app, focus the canvas, then Ctrl+V. PNG/JPG/JPEG/WEBP files can also be
dropped onto a board. Large images fit within 90% of the visible canvas; small
images keep their size. Placement is centred around the cursor when it is inside
the canvas, otherwise around the board centre. The original pixels are retained
as immutable PNG data and decoded once for painting. Move, rotate, resize,
duplicate, erase, order and undo images like other objects. Every resize handle
preserves image aspect ratio, including mixed selections containing images.

**Colour:** press C, then 1 Black, 2 Red, 3 Blue, 4 Green, 5 Yellow, 6 Purple or
7 White. The compact popover also has Custom colour and recent swatches. Choosing
a colour changes selected strokes/shapes/text in one undo action and sets the
board's default colour for future objects. Images keep their colours. With no
selection, only the default changes. Each board remembers its own colour.
Choose a swatch, click outside, or press Escape to dismiss the palette.

**Selection:** Ctrl+A excludes locked objects. Arrows move 1 logical pixel and
Shift+Arrows move 10. Consecutive nudges less than 0.4 seconds apart are grouped
for undo. Right-click for Cut, Copy, Paste, Duplicate, Delete, Bring to front,
Send to back and Lock selection. Locked objects render normally and are excluded
from ordinary clicks, marquees, transforms and erasing. Right-click a locked
object for **Unlock this object**, or use **Locked objects** in the same menu.
Colour changes, ordering, locking, pasting and transforms all support undo/redo.

## Smart Guides and Grid Snap

Right-click the tray icon → **Snap & Guides**:

- **Smart Guides** starts enabled. Moving/resizing near another object's edges
  or centre, or the canvas edges/centre, aligns within 6 logical pixels and shows
  a thin temporary guide. Calculations use cached nearby bounds.
- **Grid Snap** starts disabled. Enable it to align to an invisible 10 px grid.
- When both are enabled, a nearby smart alignment takes priority.
- Hold **Alt** during movement/resizing to bypass both. Guides disappear when
  alignment stops or the gesture finishes/cancels.

These preferences apply to every board and are remembered through QSettings
(Windows: `HKEY_CURRENT_USER\Software\MiniWhiteboard\MiniWhiteboard`; macOS: the
user preferences domain). Changing them does not
create an undo entry. `SNAP_THRESHOLD` and `GRID_SIZE` centralize the defaults.

## Screenshot → whiteboard

1. Press **Ctrl+Alt+S** from another desktop application, or choose
   **Screenshot to Whiteboard** in the tray.
2. Click and drag a rectangle over the visible desktop. The same glassy dotted
   border marks the region; Escape cancels.
3. Release the mouse. The overlays disappear before Windows captures the pixels.
4. A board appears at the selected location with the screenshot fitted into its
   usable area, locked, and Draw ready. Add annotations immediately. Unlock the
   image through its context menu when you want to move or edit it.

This workflow uses native physical desktop coordinates and per-monitor overlays.
Ctrl+Alt+W continues to use **two hotkey presses**; mouse release only confirms a
screenshot capture. Switching between the workflows cancels the other preview.

## Text editing

Press **T** and click to create a textbox. Double-click existing text to edit it.
The editor supports multiline text, selection, cursor movement, copy/paste,
deletion, and its own undo/redo.

- **Letters and numbers type normally**, including `A V E 12345`, `1234554321`, and the other tool keys.
- Enter adds a newline.
- Ctrl+Enter or Escape finishes editing and retains the text.
- Clicking outside the textbox commits the edit.
- A new textbox left completely empty is removed.
- Ctrl+Z during typing affects only the editor. After committing, canvas undo
  restores the previous committed text in one step.
- To change font size, finish editing, keep/select the text object, press **T**,
  then **1**, **2**, or **3**. This sets the displayed size to 14/20/28 pt for all
  selected text objects, even after scaling. Rotation and erasure masks remain.
- Editing happens in place with the object's rotation, proportional scale, and
  erasures visible. Clipboard operations retain the underlying plain text.

## Move, resize, minimize, and delete

Paper has a subtle **1 px top border only** and an 11 px top drag strip.
There is no side/bottom outline or inset, including around screenshots. Invisible
**7 px resize zones** retain all four edge and four corner resize operations.
Rounded corners and the exterior soft shadow are retained. Boards remain above
ordinary application windows after losing focus, without repeatedly taking focus
back. This was verified natively; no extra pin control was needed.

- Drag the empty top strip to move the whole board. Drag edges/corners to resize.
- Resizing the window clips/reveals the document; it does not scale or discard
  objects. There are no scrollbars or infinite-canvas controls.
- **−** hides that board to the tray, retaining geometry, contents, and history.
- Select a board in the tray menu to restore it. Double-click the tray icon to
  restore the most recently minimized board.
- **×** deletes only that board and its contents. This deletion is permanent for
  that board; canvas Undo does not restore a deleted window.
- Closing the last board leaves the tray app running. Choose **Exit Mini Whiteboard**
  from the tray menu to quit.

Contents are held in memory for this session. They are not saved across application
exits. Launching the application a second time exits the new process quietly,
leaving the existing instance intact.

## Test

The standard suite runs with Qt's offscreen platform and does not take control of
your desktop. It includes document/geometry tests and real Qt editor/input tests.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

Opt-in native checks briefly open disposable Windows test windows. Close any
running Mini Whiteboard first. Leave the mouse and keyboard alone during the
keyboard workflow check; it restores cursor/focus afterward and stops if it cannot
verify that its own test window has focus.

```powershell
.\.venv\Scripts\python.exe -m scripts.native_smoke
.\.venv\Scripts\python.exe -m scripts.hotkey_workflow_check
```

Results and images go to `.test-artifacts/`. See [TEST_RESULTS.md](TEST_RESULTS.md)
for actual verification status and [MANUAL_TESTING.md](MANUAL_TESTING.md) for
precise Windows and hardware testing steps.

The optional performance workload compares circular/stroke erasing, marquee,
single/group movement, resizing and rotation with 10, 100 and 500 mixed objects:

```powershell
.\.venv\Scripts\python.exe -m scripts.performance_check --frames 16 --output .test-artifacts/performance.json --profile .test-artifacts/profile.txt
```

This measures GUI-thread processing and offscreen raster painting, including
actual dirty areas. It is not a measurement of native display FPS. Baseline and
updated measurements are retained in `verification/`.
See [PERFORMANCE.md](PERFORMANCE.md) for the full timing comparison and its limits.

## Windows: build the no-console executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The script generates the icon and Windows version resources, runs the test suite,
and builds with PyInstaller. `APP_VERSION = "1.1"` in `mini_whiteboard/__init__.py`
drives application/About metadata, executable resources and the assembly manifest.
Source diagnostics: `.\.venv\Scripts\python.exe -m mini_whiteboard --version`.
Launch the result:

```powershell
& '.\dist\windows-v11\Mini Whiteboard\Mini Whiteboard.exe'
```

Distribute the **entire `dist\windows-v11\Mini Whiteboard` folder**, including `_internal`.
It contains Python/Qt, so the recipient does not need a Python installation.
The executable uses an `asInvoker`, Per-Monitor V2 manifest. It is unsigned;
code signing and an installer are outside this version's scope.

## Source layout

`SPEC.md` contains the current requirements, including the polish/performance
update; `PLAN.md` records the implementation plan and decisions.

- `app.py`: tray, board registry, application lifetime.
- `platform/base.py`: Runtime/Desktop/Hotkeys/Capture service boundary.
- `platform/windows/`: original Win32 implementation, mutex, hotkeys and capture.
  `windows.py` retains a compatibility alias for existing diagnostic scripts.
- `platform/macos/`: accessory lifetime, local lock, Cocoa windows, Carbon hotkeys and ScreenCaptureKit.
- `platform/capture_geometry.py`: point-to-pixel planning for mixed-display capture.
- `shortcuts.py` / `system_menu.py`: platform labels, fonts and shared status menu.
- `placement.py` / `geometry.py`: placement state and transparent previews.
- `screenshot.py`: separate click-drag capture workflow and cleanup.
- `clipboard.py` / `images.py`: editable clipboard payloads, image rendering and cached sources.
- `editing_actions.py` / `palette.py`: keyboard/context commands and temporary colours.
- `snapping.py`: shared preferences and cached alignment targets.
- `background.py`: display-resolution cache for the original locked screenshot.
- `board.py` / `shadow.py`: paper, input-transparent shadow, controls, movement and resizing.
- `document.py` / `transforms.py`: immutable objects, affine transforms, local masks,
  shared-frame geometry, and per-board transactional undo history.
- `canvas.py`: tool interactions and focus-aware key routing.
- `scene.py`: cached bounds, broad-phase queries, and sparse gesture previews.
- `overlays.py`: one passive surface per board for cursor, marquee and handles.
- `rendering.py`: surviving ink geometry, painted bounds, masks, selection controls,
  hit testing, and continuous swept brushes.
- `text_editor.py`: transformed Qt editor overlay, mask clipping, and shortcut protection.
- `feedback.py` / `settings.py`: fading feedback, F1 help, centralized defaults.

Painting culls objects against the dirty region. Gestures capture their original
objects once, update only affected previews, and create one history entry on
release. Local geometry/mask caches survive transform changes. No spatial tree,
worker GUI thread, or additional high-frequency timer was needed.

Screenshot boards cache their original locked image once at the viewport's
physical resolution (`logical size × devicePixelRatio`, once). Drawing, erasing
and moving annotations reuse that raster and the original image/PNG references.
Only changes to viewport size, DPI or clipping rebuild the display cache. Unlocking
the screenshot returns it to normal editable-image rendering; undo can restore
the original cached state. Locked images are excluded from editable candidates
and Smart Guide targets. Freehand updates repaint just the changing curve tail,
with stroke/antialias padding. See the current screenshot comparison in
[PERFORMANCE.md](PERFORMANCE.md).

All GUI work runs on the Qt GUI thread. Cursor tracking exists only during
placement; feedback timers stop after their animation. Application exit removes
hotkeys, timers, overlays, windows, status icon, and the platform's instance lock.

## Known limits and verification

- Boards and undo histories remain session-only. Snapping preferences and the
  global-shortcut preset persist. Closing a board or exiting discards its contents.
- Images are limited to 64 million pixels; the editable clipboard payload is
  limited to 96 MB. Large image imports encode PNG once and may briefly pause.
- The executable is unsigned. No installer or automatic update mechanism is included.
- Protected/secure desktop content may be unavailable to Windows screenshot APIs.
- Actual native checks ran on one 1920×1080 display at 100%. Real mixed-DPI,
  negative-coordinate displays and monitor removal still need hardware testing.
- Clipboard image interoperability was verified between Windows processes;
  hand-operated Paint/Word/OneNote/Discord/browser/Snipping Tool checks remain on
  the manual checklist, along with a clean Windows machine deployment test.

See [TEST_RESULTS.md](TEST_RESULTS.md) for the release results, archive integrity
checks and the exact outstanding manual checks. [PERFORMANCE.md](PERFORMANCE.md)
includes the 4K screenshot and clipboard measurements.
