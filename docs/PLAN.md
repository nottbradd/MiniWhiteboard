# Approved implementation plan

## V1.1 release and repository polish — approved 2026-10-11

Publish V1.1 as a stable Windows release with a clearly labelled Mac preview.
Rebuild both packages with dependency notices and source access, run the
Windows native regressions, and use a fresh hosted Mac build for the preview.
Keep interactive Mac and physical hardware checks marked NOT RUN until observed.

Add a placement GIF and screenshot made with the app, repository description
and discovery topics, and direct download links. Move reference guides into
`docs/`, keep README/CONTRIBUTING/LICENSE at the root, and rename the launcher
to `main.py`. Update references and validate the build workflows. Prepare a
short post for the owner to publish. The Windows package/native gates and the
fresh hosted Mac pipeline passed. App ZIPs, notice collections, checksums and
source archives are staged for the V1.1 release. Results are in
[TEST_RESULTS.md](TEST_RESULTS.md).

The sections below record earlier decisions; the earlier instruction to leave
the repository private was superseded by the subsequent publication request.

## Historical public repository preparation — 2026-10-10

The user requested preparation for public visibility and chose the MIT license.
Add LICENSE, third-party scope/notices, public-facing README, contribution and
issue/PR guidance, and a Windows automated-test workflow. Replace current
machine-specific documentation paths with portable paths and record observed
Mac CI evidence. Review tracked history for generated artifacts and credential
signatures. Validate the workflows and automated suite before pushing. Preserve
application code, Version 1.1 and existing binary packages. Keep visibility
private for the user's final publishing step.

## GitHub-hosted macOS completion — approved update (2026-10-01)

The build/automated verification stage will use the real GitHub-hosted `macos-14`
runner; an owned Mac is no longer needed for this stage. Interactive acceptance
still requires observed native use and remains NOT RUN. Mac application source
is retained unless real testing reveals a defect. Windows release files remain
untouched and are excluded from the Mac workflow.

Prepared: local Git main branch, artifact/environment/cache exclusions, LF rules,
`.github/workflows/macos-v1.1.yml`, headless import check, stronger bundle/ZIP
verification, owned-process startup check and runner result summary. The workflow
uses Python 3.13, existing requirements/build shell/spec, full failure gates,
ditto archive/extraction, and the requested artifact name. Local verification is
recorded in TEST_RESULTS. The actual October 1 Mac workflow succeeded and was
reviewed on October 10: 156 tests, Universal2 build/validation, limited Cocoa
startup and ditto ZIP round-trip all passed. The repository now exists at
[nottbradd/MiniWhiteboard](https://github.com/nottbradd/MiniWhiteboard).

Next: download the verified inner tester ZIP unchanged and complete interactive
acceptance. Preserve global input/menu/TCC/window/Spaces/Retina/multi-monitor
NOT RUN statuses until observed use. See [GITHUB_SETUP.md](GITHUB_SETUP.md).

## Cross-platform Version 1.1 — implementation status (updated 2026-10-10)

The cross-platform plan and amendments are approved. Product version remains 1.1.
The older milestones below record the history; this section governs current work.

1. **Done:** preserved and SHA-256-verified source (71 files), distribution (165
   files), build outputs (17 files) and the existing Desktop tester ZIP under
   `verification/baselines/windows-v11-20261001/`.
2. **Done:** introduced Runtime/Desktop/Hotkeys/Capture services, moved native
   Windows code behind the adapter, retained the shared model/canvas/tool modules.
3. **Passed before substantial Mac code:** 126 shared regressions, 110 Windows
   native checks and the real W/S input workflow. Later tests expanded the suite.
4. **Implemented, native Mac NOT RUN:** accessory lifetime, QLockFile, floating
   Cocoa windows, Carbon press/release registration with repeat suppression,
   temporary Escape probe, persisted shortcut presets and platform help/fonts.
5. **Implemented, native Mac NOT RUN:** ScreenCaptureKit permission/capture path,
   asynchronous cancellation, per-display point/pixel composition and native
   verification scripts. Shared clipboard and screenshot caching are retained.
6. **Implemented:** Mac spec/icon/build/signature/architecture/ZIP verification,
   separate Windows candidate output and exact platform archive names. The Mac
   build attempts Universal2 and only falls back on a demonstrated architecture
   mismatch. No native Mac build is claimed on Windows.
7. **Done:** 143 automated tests, 111 final native checks, 33 real-input checks and
   16 packaged checks passed. The new Windows ZIP is on Desktop; all 165 files
   match the final build, and the previous tester archive is unchanged.
8. **CI VERIFIED:** the hosted Mac run built and validated the real Universal2
   `.app` and its ditto ZIP, including a limited packaged startup check. Transfer
   the finished ZIP unchanged; Desktop delivery has not been verified here.
   Bare-Escape feasibility and interactive acceptance remain NOT RUN.

Follow-up source audit: capture's QObject/timer creation is deferred until after
QApplication and parented to it. Two startup-order regressions bring the latest
suite to 145 passing tests. The Mac-only change is excluded from the verified
Windows build; the Desktop archive remains unchanged.

No Mac Pin control is introduced. Boards use a floating level without recurring
focus changes. Global Escape remains provisional until the native probe passes;
menu-bar cancellation is available without Accessibility. See
[CROSS_PLATFORM_REPORT.md](CROSS_PLATFORM_REPORT.md) for actual results and
[MACOS_CHECKLIST.md](MACOS_CHECKLIST.md) for exact continuation commands.

Approved by the user on 2026-09-29. The earlier plan-only restriction is lifted.
The selection, transforms, and eraser update was also approved on 2026-09-29.
SPEC.md incorporates the current requirements. This plan retains the placement
architecture and records the approved update below.

## Recommended approach

Build and verify the tray app and exact two-press placement workflow before
adding drawing tools. The first milestone creates a blank board at the selected
bounds, so placement, focus, scaling, and cleanup can be tested independently.
The existing application, tray, Windows integration, and object canvas are retained.

## 1. First milestone: two-press placement

### Explicit placement states

A dedicated placement controller uses this state machine:

| Current state | Event | Result |
|---|---|---|
| Idle | Ctrl+Alt+W | Capture the first corner; show the outline; enter placement mode. |
| Placing | Mouse moves | Update the opposite corner while keeping the first corner fixed. |
| Placing | Ctrl+Alt+W, valid size | Capture the current cursor position, remove the preview, create and focus a new board. |
| Placing | Ctrl+Alt+W, too small | Show brief feedback and continue placement with the original first corner. |
| Placing | Escape | Remove the preview and return to idle without changing existing boards. |

Mouse clicks and hotkey release do not confirm placement. Each completed
placement creates a separate board.

### Native hotkey integration

- Register Ctrl+Alt+W through Windows RegisterHotKey with MOD_CONTROL,
  MOD_ALT, and MOD_NOREPEAT.
- Receive WM_HOTKEY through Qt's native event filter on the GUI thread.
- Sample the cursor when each hotkey event arrives, so confirmation uses the
  current position rather than the previous preview frame.
- Report registration failure visibly, including that another application may
  already own the shortcut.

References:
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
- https://doc.qt.io/qt-6/qabstractnativeeventfilter.html

### Preview and cancellation

Use transparent, frameless preview windows with round translucent white dots
and faint offset shadows, completely transparent interior and exterior, input
transparency, and no keyboard focus. A cursor-tracking timer runs only during
placement, approximately 60 updates per second, repainting only when necessary.

Register Escape temporarily during placement, allowing cancellation while
another application remains focused. Unregister it immediately afterward. If
cancellation cannot be registered, abort placement with a visible explanation.

Confirmation, cancellation, errors, and application exit share one cleanup path
that stops the timer and removes every preview window.

Reference: https://doc.qt.io/qt-6/qt.html#WindowType-enum

### Coordinates and display scaling

- Store both corners in native physical desktop coordinates, including negative
  coordinates.
- Normalize with min(x1,x2), min(y1,y2), abs(x2-x1), abs(y2-y1).
- Keep that physical rectangle authoritative for preview and final paper body.
- Use preview windows per monitor, painting only the outline portions that
  intersect each display.
- Convert physical coordinates to local Qt logical coordinates at explicit
  boundaries.
- Establish Per-Monitor V2 awareness before windows exist and preserve it in
  the packaged build.
- Account separately for any shadow outside the paper body.

Mixed-scale Windows screens can produce gaps in Qt's logical desktop geometry;
do not independently convert corners and then subtract global Qt positions.
For a selection spanning monitors, use the monitor with the largest overlap
to determine initial board scale and the 160 x 100 logical-pixel minimum, then
verify against the created window's effective DPI.

References:
- https://doc.qt.io/qt-6/highdpi.html
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-monitorfromrect
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getdpiforwindow

### Milestone acceptance gate

- Placement starts while another normal application has focus.
- Holding the shortcut produces only the first press.
- Placement works in all four directions.
- Escape cancels without disturbing existing boards.
- An undersized selection retains the original anchor and permits another
  confirmation attempt.
- Blank board physical body bounds match the preview.
- Negative coordinates, fractional scaling, and mixed-scale boundaries work.
- Repeated placement creates independent boards.
- No preview windows or tracking timers remain afterward.

## 2. Prevent shortcuts from interfering with text

An active text editor owns typing and text-editing commands. One board input
router uses an explicit editing state and focus check.

| Context | Input handling |
|---|---|
| Placement active | Global Ctrl+Alt+W confirms; Escape cancels placement. |
| Textbox being edited | Letters, numbers, navigation, selection, clipboard commands, Delete, Backspace, and text undo go to the editor. |
| Focused board, no text editing | D/T/S/A/V/E select tools; numbers use the current tool mapping; editing commands affect canvas objects. |
| Another application focused | Board tool shortcuts are inactive. |

Use a real Qt text editor configured for plain text, preserving normal
multiline editing and clipboard behavior.

Concrete safeguards:
1. Dispatch ordinary tool keys through the canvas input handler, guarded by
   board focus and no active text edit.
2. Disable canvas actions that could compete with the editor during editing.
3. Handle ShortcutOverride where needed so editor keys reach the focus widget
   before parent shortcuts activate.
4. Route Ctrl+Z/redo to exactly one history: editor during typing, board outside
   editing.
5. Enter inserts a newline. Ctrl+Enter/Escape commit; clicking outside commits.
6. Retain selection after committing so T then 1/2/3 changes the text size.
7. A committed editing session is one board undo operation; discard newly
   created empty textboxes.

Early regression: type "Today is day 123" and verify exact text, unchanged
tool, unchanged font size. Also check every tool letter, numeric shortcut,
deletion, paste, and editor undo.
Reference: https://doc.qt.io/qt-6/qevent.html#Type-enum

## 3. Application structure

PySide6 is the only runtime dependency; use standard-library ctypes for
Windows integration. main.py remains a small entry point.

| Area | Responsibility |
|---|---|
| Application and tray | Startup, board registry, tray menu, restore order, shutdown |
| Windows integration | Native hotkeys, single-instance mutex, physical geometry, DPI helpers |
| Placement | State machine, preview windows, size validation |
| Board window | Paper appearance, controls, moving, edge/corner resizing |
| Document model | Immutable strokes, text, shapes, affine transforms, local masks, stable IDs and stacking order |
| Canvas and tools | Painting, hit-testing, interaction previews, selection, editor |
| Commands and settings | Per-board undo/redo; centralized shortcuts and styling |
| Tests and packaging | Logic tests, GUI checks, Windows checklist, PyInstaller |

Use a custom QWidget/QPainter canvas backed by document objects. Selection,
unfinished interactions, and undo state remain separate from rendering.
Window resizing changes the visible viewport; object coordinates remain
unchanged, including objects temporarily outside the visible area.

## 4. Approved selection, transforms, and eraser update

### Implementation order and conflicts

Protect the existing two-press placement and lifecycle tests first. Implement
model/geometry support, multi-selection and transforms, transformed text editing,
eraser modes, then verification/documentation/packaging.

A and V share one selection state. A/V uses the shared transform box for all
objects; S retains single-line/arrow endpoint editing. Text gains proportional
transform handles. E defaults to partial circular erasure; key 5 removes only
freehand strokes. Shift during transform resizing preserves the current group
aspect ratio; square/circle constraints remain during shape creation.

No permanent toolbar, sidebar, properties panel, persistence format, or new
runtime dependency is introduced.

### Model and geometry interfaces

- Extend each immutable object with an identity-default Affine and a tuple of
  immutable Erasure records. Each record describes a swept circular brush and
  its mapping into object-local coordinates.
- Keep original geometry, editable text, IDs, stacking order, and mask history.
  One Stroke ID still identifies one original pen-down/up gesture and all its
  surviving fragments. Group transforms never merge objects.
- Store selected IDs and an oriented SelectionFrame outside document history.
  Capture before-state and frame once at gesture start; preview replacements
  separately and commit one immutable after-state on release.
- Share local painted geometry, surviving ink, transformed bounds, and swept
  brush geometry across rendering, selection, and erasing. Include stroke widths,
  filled arrowheads, and Qt-shaped text glyph outlines. Full bounds are independent
  of viewport clipping and exclude UI decorations.
- Preserve closed-shape interior selection, subtracting local erasures after
  applying thin-stroke hit tolerance. Erased regions remain unselectable.
- Clip original rendering through local masks. Cache base geometry and bounded
  mask unions; reuse the previous union during long brush drags.

### Selection and transforms

- A/V direct selection chooses the topmost hit; Shift+click toggles membership.
  Marquees normalize all four directions and select only fully contained bounds,
  with 0.01 logical-pixel boundary tolerance. Shift+marquee adds.
- Use a 3-logical-pixel drag threshold. Empty clicks clear. Dragging a selected
  object or box interior moves the group; empty space outside starts a marquee.
- Draw one oriented frame with eight circular resize handles and an offset
  rotation handle. Visual handle diameter is 8 physical pixels, connector offset
  24 physical pixels, and hit radius 10 logical pixels. Convert using current DPR.
  Object transforms never scale the controls. Handle input stays inside canvas.
- Keep the captured frame orientation during and after the transform. Rebuild
  on membership/content changes or undo/redo. Window gestures stay separate.
- Move with a shared translation. Scale geometry, pen widths, masks, and spacing
  about the opposite handle. Corners are proportional; edges can scale one axis.
  Shift makes edge scaling proportional. Text-containing groups always scale
  proportionally, anchoring the opposite edge midpoint for edge gestures.
- Clamp frame dimensions to at least 1 logical pixel and reject non-finite
  transforms. Crossing the anchor never mirrors. Full affine matrices preserve
  correct results when nonuniform scaling follows rotation.
- Rotate objects and their positions about the frame centre. Shift snaps the
  frame orientation to 15-degree increments. Every preview derives from the
  original snapshot, avoiding incremental geometry distortion.
- Escape restores exact document/frame state. Selection-only operations and
  ineffective edits do not create undo entries. Backspace/Delete removes the
  selected collection and clears selection as one action.

### Transformed text editing

Use the existing real QTextEdit in a temporary transparent QGraphicsView and
QGraphicsProxyWidget overlay. Apply the object's transform and clip its local
mask while editing. Preserve ordinary plain-text selection, multiline editing,
clipboard, context menus, text deletion, and QTextEdit undo.

The canvas router requires active-board focus, canvas focus, and no editor.
Ordinary tool keys are never global QShortcuts; ShortcutOverride ensures the
editor owns typing, including A V E 12345. Ctrl+Enter/Escape/outside click commit;
a newly created empty textbox is discarded. A committed session is one document
undo action. Editor focus and popup lifecycle are checked offscreen and natively.

T then 1/2/3 sets displayed 14/20/28 pt size for all selected text objects in one
action. Account for each object's uniform transform scale. Retain rotation and
masks. Masks stay at their object-local positions across content edits; copied
text remains the underlying plain text.

### Eraser

- Central sizes: 8, 16, 32, 64 logical-pixel diameters. Each board starts in circular
  mode at 16 px and remembers its last mode and circular diameter.
- Keys 1–4 choose a diameter and circular mode; 5 toggles whole-stroke mode.
  Entering retains the current targeting diameter; toggling off resets to 16 px.
- Show a two-tone circular cursor and brief mode/size feedback. Hide the circle
  outside canvas, during text editing, and after leaving the tool.
- Sweep the complete capsule between pointer samples, including the initial
  stationary circle. Map it through each affected object's inverse transform.
- Circular mode adds masks to all intersected existing objects, including text,
  shape outlines and fills. Remove fully erased objects within the same action.
  Future objects have empty masks and render over old erased regions normally.
- Whole-stroke mode tests surviving transformed freehand ink, then removes its
  original Stroke ID and every surviving fragment. Shapes and text are ignored.
- One drag creates one undo entry across all affected objects. Escape discards
  previews without adding history. Undo/redo restores exact masks and identities.

## 5. Verification and delivery

Automate four-direction/full-containment selection, Shift membership, transformed
bounds, offscreen artwork, mixed-object transforms, anchor preservation, snapping,
non-mirroring, exact cancellation/history, multi-delete, swept partial erasure,
remaining-ink targeting, stroke identity, all eraser settings, masks after later
transforms, future content over cuts, and rotated/masked text input and presets.

Run original placement/lifecycle regressions before and after integration, then
native Windows smoke and actual two-press key checks. Inspect native screenshots
of shared transforms, masked editing, committed text, and updated F1 help.
Rebuild the no-console executable and check the packaged process/manifest.

Update SPEC.md, this plan, README, F1 help, manual checklist, and TEST_RESULTS.md.
Report actual check counts/results and any unavailable GUI/hardware checks.
Real mixed-DPI/negative-monitor testing, clean-machine deployment, extended
manual ergonomics, and long idle observation must be identified as NOT RUN when
unavailable. Deliver complete source and the whole distribution folder.

## 6. Polish/performance implementation — 2026-09-29

1. Establish the 65-test regression baseline. Instrument real gesture processing
   plus paint events with 10/100/500 mixed objects. Capture timings and cProfile
   before changing production interaction code.
2. Test native WS_EX_TOPMOST, actual Z-order with a focused ordinary owned window,
   and no repeated focus stealing. These checks passed, so keep the two existing
   controls and omit the conditional pin feature.
3. Reduce canvas inset 6→2 px, top strip 32→11 px, edge grip 6→2 px, controls
   28×26→24×20 px, and control text 20→16 px. Keep border 1 px, corner radius 12 px,
   and exterior shadow 8 px. Apply rounded document clipping and control cutouts.
4. Paint tool chrome on one passive tooltip-style native surface per board.
   It has transparent input and no activation; native tests verify these flags
   and actual focus. Cursor pixels may extend beyond the board. Fixed immutable
   creation/brush clips prevent editing outside valid canvas pixels.
5. Add cached Scene records (object/bounds/hit bounds) and sparse preview records.
   Use broad-phase bounds for painting, selection and erasing. Repaint old/new
   affected regions padded by 3 px; marquee/cursor motion repaint only the overlay.
   Reuse source local-mask geometry across transforms and preview records on commit.
   Store paint data in each record; fill cached stroke outlines instead of asking
   Qt to stroke every curve again. Coalesce dense dirty regions above 16 rectangles
   and apply the rounded document clip only to artwork touching its boundary.
6. Replace placement strokes with QPainterPath circles (2.5 px, ~6 px gap, 75%
   white) and two faint expanding shadow layers. Update old/new perimeter strips
   only when the rectangle changes. Preserve the native timer and state machine.
7. Implement 5 as a toggle with explicit default-size return. Keep 1–4 immediate
   circular selection, use dashed stroke targeting and existing transient feedback.
8. Add bounded-work, clipping, passive-focus and typing tests; rerun identical
   timing workloads and native/real-key/package checks. Inspect owned-window
   screenshots. Update documentation and rebuild the distribution.

The baseline showed full-canvas painting at every sample: roughly 40–52 ms per
update with 500 objects. Updated profiles show that bounds scanning is a small
part of total cost, so no spatial tree was added. All mutation/rendering remains
on the GUI thread with no new high-frequency timer. Timing tables, limits and
final check counts are in TEST_RESULTS.md and verification/performance-*.json.

Qt window-type reference: https://doc.qt.io/qt-6/qt.html#WindowType-enum

## 7. Version 1.1 implementation and release — 2026-09-30

The user requested complete implementation and replacement of the tester ZIP.
Use the requested **1.1** release label, retaining the previous development
build's features even though that build used the label 1.2.0.

1. Preserve the 81-test baseline and exact two-press Ctrl+Alt+W workflow.
2. Extend immutable objects with colour/locking and add ImageObject with original
   PNG bytes, natural dimensions, affine transform, masks and stable identity.
   Reuse scene paint records so affine previews never decode the image again.
3. Add validated editable JSON MIME plus normal Windows image output. Implement
   copy/cut/paste/duplicate, 16 px repeat offsets, file drops and image fitting.
   Centralize commands so keyboard and context menus share history behaviour.
4. Add grouped arrow nudges, select-all, stable front/back ordering, lock/unlock
   and a compact palette with presets/custom/recent colours. Keep all new keys
   inside the active canvas router; QTextEdit owns them while editing.
5. Build Smart Guides from cached bounds once per gesture, with sorted nearby
   lookup, 6 px threshold, 10 px optional grid and Alt override. Reuse the passive
   decoration surface and dirty painting. Share/persist only tray preferences.
6. Add native Ctrl+Alt+S and a separate click-drag capture controller. Hide overlays
   and flush desktop composition before physical-coordinate GDI capture. Start a
   new board with a locked image and Draw ready. Preserve W's independent state.
7. Generate Windows file/product/manifest versions from APP_VERSION; update F1,
   README, SPEC, this plan, manual checks and actual test/performance reports.
8. Run offscreen/native/real-key regressions, Windows clipboard IPC and known-pixel
   capture checks. Measure 4K image transforms and multi-object clipboard work.
9. Build the GUI executable, verify launch/runtime/metadata, stage a clean archive,
   validate every ZIP entry against the distribution and replace the located
   `Desktop/MiniWhiteboard.zip`. Preserve its filename.

Implementation decisions: custom MIME is JSON rather than an executable object
format; source images retain full pixels; external clipboard previews have a
4096 px limit. PNG import has a one-time encoding cost. Mixed text/image selections
always resize proportionally. Screenshot and placement overlays differ only in
input capture and their confirmation controllers. A 1-alpha capture veil was
verified with real Windows mouse input. Qt's actual dark-theme background colour
is sampled in the native screenshot test instead of assuming white.

See TEST_RESULTS.md for the completed release checks, binary/archive details and
outstanding manual/hardware verification; PERFORMANCE.md records measured costs.

## 8. Version 1.1 screenshot/border refinement — 2026-09-30

1. Establish the 112-test baseline. Profile identical 20-stroke/20-shape/10-text
   blank and screenshot boards before edits, in Qt offscreen and native Windows.
   Use 1080p/1440p/4K sources and instrument paint/decode/geometry/history activity.
2. The original code already shared image data in history and cached decoding.
   It repeatedly passed the source image through its scale/clip painting path.
   Drawing invalidated the growing stroke's complete bounds. Locked objects were
   rejected late in broad-phase tool queries and screenshot edges entered guides.
3. Add a view-only ScreenshotBackground cache at viewport physical resolution,
   keyed by size/DPR/clip. Preserve original PNG, object identity and stacking.
   Normal annotation work reuses the raster; unlock/changes use normal rendering,
   and undo can restore the eligible background. Compare pixels at fractional DPR.
4. Cache editable candidate order, exclude locked images from guide targets,
   filter non-strokes early for stroke erasing, and invalidate only changed curve
   tails. Keep sparse gesture/history operations and passive overlays unchanged.
5. Remove the full outline pen and paint one grey top line. Remove the screenshot
   side/bottom inset so no white rim remains. Preserve corner shape, shadow,
   controls, top drag strip and valid document clipping. Route invisible 7 px
   edge/corner targets directly from idle canvas pointer events; handles win.
6. Add cache/identity/pixel/dirty/resize tests and native real-mouse resize checks.
   Repeat the before/after workloads, run full regressions/hotkeys, build and
   verify the no-console executable, then replace and verify the existing ZIP.
7. Keep Version 1.1. Update current visual/usage docs, benchmarks, actual results
   and remaining hardware checks. Preserve earlier evidence as historical data.

Completed: 126 automated tests, 110 native checks, 33 real-input checks and 16
packaged checks passed. The GUI executable was rebuilt/launched and the Desktop
ZIP replaced, reopened and verified against all 165 distribution files. Native
timings are close to blank-board timings in the matched fixture; total before/
after medians are mixed. PERFORMANCE.md records that limitation alongside the
cache reuse, reduced drawing area and paired raster measurements.
