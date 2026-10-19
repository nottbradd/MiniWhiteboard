# Mini Whiteboard specification - Version 1.2

V1.2 delivery is complete. Release source 08b3893 and the actual Windows/Mac
checks, package hashes and remaining NOT RUN acceptance are recorded in
[TEST_RESULTS.md](TEST_RESULTS.md). The [v1.2 release](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.2)
contains the verified Windows ZIP and labelled Mac preview.

## V1.2 governing requirements - 2026-10-19

This section supersedes the historical two-press placement and mouse-drag
screenshot rules retained below. Other drawing, selection, window and native
capture requirements remain in force.

- Windows: hold Ctrl+Alt+W for a board or Ctrl+Alt+S for a screenshot, move the
  pointer, then release the trigger or any required modifier. Mac defaults are
  Control+Option+W/S; the alternate is Command+Option+Shift+W/S.
- Anchor on complete shortcut activation. Preview is nonactivating, dotted,
  mouse-transparent and supports four directions/negative desktop coordinates.
  No result on press, no clicks/second press/minimum hold duration.
- One native hold latch and one shared creation owner. Repeats/duplicates cannot
  confirm/restart; competing shortcuts are ignored. Pending capture retains
  ownership. Cancellation drains held triggers before fresh activation; remaining
  S/W cannot become canvas/editor input when a completed board gains focus.
- Release always ends selection. Below 160x100 logical units for a board, or
  4x4 desktop units for capture, cancel fully with brief feedback. Retain native
  physical/logical placement, capture size/fit checks and locked background cache.
- Native adapters detect release with external focus. Windows samples only the
  registered keys during an active hold/necessary release cleanup, every 8 ms;
  idle has no tracking timer. Carbon hotkey release plus temporary hardware state
  sampling handles Mac modifier release without new TCC permission requests.
- Escape (including held shortcut modifiers), menu cancel, exit, display changes,
  errors and permission interruption clear previews and tracking. Native trigger
  latches drain after cancellation. Capture uses generation checks, queued GUI
  delivery, native timeout plus a 20-second controller timeout and overlay exclusion.
- Text stores validated integral local logical `layout_width`, 24..100000 units.
  New width is board-right minus insertion x minus 8, clamped to those limits.
  Missing legacy clipboard width defaults to 320; explicit invalid/nonfinite,
  boolean or unreasonable values fail. Layout caches include width.
- Editor, committed painting and glyph outlines share word wrapping with character
  fallback. Soft wraps do not modify plain text; Enter inserts a real newline.
  Text retains width, masks, identity and content through edits/transforms/clipboard/
  duplication/history. Board resize changes only the viewport. A temporary editor
  view follows the caret for tall text; no permanent scrollbars or board resizing.
- Editor focus owns ordinary tool keys, clipboard, arrows, delete/backspace and
  undo. Ctrl+Enter / Command+Return, Escape and outside click still finish editing.
- Build V1.2 in separate staging directories. Mac CI uses free `macos-15`; deployment
  target, Info.plist and runtime minimum remain 14.0. Keep official action pins,
  Universal2 intent/fallback policy and all existing validation gates.
- Publish new v1.2 assets: WinMiniWhiteboardV1.2.zip and
  MacMiniWhiteboardV1.2-Preview.zip, checksums, notices and dependency source.
  Preserve v1.1. Transfer the Mac-created ZIP unchanged. Native interactive Mac,
  Intel/macOS 14 execution and unavailable hardware checks remain NOT RUN.

## Historical V1.1 specification

# Mini Whiteboard specification — Version 1.1

Updated 2026-10-11 for release publication; Version 1.1 is retained.
The cross-platform addendum
below supersedes earlier Windows-only wording and release paths. Sections 10–11
retain the shared feature and screenshot refinements.
The sections below incorporate the new requirements; placement and lifecycle
requirements remain in force. Shape-mode endpoint editing is preserved.

Build a complete desktop application called “Mini Whiteboard” for Windows 10/11
and macOS 14+, keeping one shared PySide6 implementation.

## Cross-platform V1.1 addendum

### V1.1 release and repository polish — 2026-10-11

- Publish a stable Windows V1.1 release and a clearly labelled Mac preview.
  Keep native interactive Mac acceptance and Intel execution marked NOT RUN
  until observed. This supersedes the earlier private-visibility and overall
  tester-release wording below.
- Provide app ZIPs, SHA-256 checksums, dependency license texts and exact Qt/PySide
  source archives. Rebuild and verify both app packages before publication;
  preserve the previous Windows distribution while preparing the new one.
- Exclude unused Qt Virtual Keyboard, QML, Quick and PDF products. Verify the
  intended notices and check the actual libraries shipped by each platform.
- Put direct downloads, an authentic placement GIF and an app screenshot near
  the top of README. Set the repository description, topics and release homepage.
- Keep README, CONTRIBUTING and LICENSE at the root. Move reference documents
  into `docs/` and rename the launcher to `main.py`, updating all live references.
- Prepare a short sharing post for the owner to publish.

### Historical source publication addendum — 2026-10-10

- Use the user-selected MIT license for the project's own source/assets. Keep
  dependency license scope and binary-release obligations documented separately.
- Provide portable public setup instructions, contribution guidance and issue/PR
  templates. Exclude generated artifacts and credentials from source commits.
- Run automated Windows tests on main pushes and pull requests. Preserve the
  existing Mac build/verification workflow and already verified Windows binaries.
- Record the observed October 1 hosted Mac success in the verification documents;
  keep interactive Mac acceptance and Intel execution marked NOT RUN.
- Prepare the existing repository while retaining private visibility. Public
  visibility is a separate publishing step chosen by the user.

### GitHub-hosted Mac release addendum — 2026-10-01

- Build and automatically verify on a real GitHub-hosted `macos-14` runner through
  `.github/workflows/macos-v1.1.yml`; support workflow_dispatch and relevant main
  pushes. Documentation-only changes need not rebuild. Use Python 3.13, pip cache,
  existing requirements, full automated tests and existing shell/spec build logic.
- Report OS/architecture/Python/Qt/PySide6/PyInstaller/PyObjC versions without
  secrets. Check production Mac imports and selection independently of test fakes.
- Validate the `.app`, native architectures, runtime/dependency linkage, Version
  1.1, bundle identifier/accessory mode/minimum version and Windows-file exclusion.
  Briefly launch/cleanly terminate an owned packaged process when a native session
  is available; record NOT RUN explicitly when unavailable.
- Create `MacMiniWhiteboardV1.1.zip` on macOS with ditto, inspect/extract/revalidate
  it, and upload the exact inner ZIP as artifact `MacMiniWhiteboardV1.1`. Preserve
  permissions/symlinks/metadata. Keep tests/build/check logs as a separate artifact.
- Preserve the Mac application implementation until actual test failures justify
  changes. Do not rebuild or modify the Windows release in this job. Version
  source/tests/requirements/specs/build scripts/docs/workflows/required assets;
  exclude environments, caches, outputs, local logs and generated release ZIPs.
- After an actual successful run, record automated Mac results as CI VERIFIED with
  evidence. Global hotkeys/two-press placement/Escape, menu interaction, topmost,
  Screen Recording prompts/selection, Mission Control/Spaces/Stage Manager,
  Retina and physical multi-monitor checks remain NOT RUN without interactive use.
  The release remains a tester/beta until native acceptance. The cross-platform
  goal is not complete before a successful actual CI run.

### Platform implementation requirements

- Keep Version **1.1**, bundle ID **com.brad.miniwhiteboard**, minimum macOS **14.0**.
- Preserve/hash the existing Windows source/build/release before refactoring.
  Pass existing automated and relevant native Windows checks after the platform
  boundary is introduced and before substantial Mac implementation.
- Shared document, geometry, canvas, tools, transforms, erasing, images, clipboard,
  colour, snapping, undo and screenshot caches remain in place. Runtime, Desktop,
  Hotkeys and Capture services own native differences; tests may inject a fake.
- Windows retains Win32 RegisterHotKey/MOD_NOREPEAT, physical placement/GDI capture,
  PMv2 scaling, mutex, tray lifetime and the existing no-console build.
- macOS uses an accessory/LSUIElement status utility: one menu item, no startup
  board/dashboard/Dock workflow, last-board close keeps the app alive. Use QLockFile
  for single-instance ownership, without a service or network server.
- Mac W/S defaults are **Control+Option+W/S**; offer persisted
  **Command+Option+Shift+W/S**. Native registration is event-driven, reports
  conflicts, supports retry and unregisters on exit. Repeats and releases must
  never confirm the exact press → move → second-distinct-press W workflow.
- Prototype bare global Escape while another app is focused with Accessibility
  off. Record actual results. If unavailable, explicitly report the limitation;
  temporary menu-bar cancellation is the least invasive alternative. Do not add
  Accessibility requests, keyboard polling or persistent focus capture.
- Mac boards float above ordinary windows without recurring focus stealing.
  Retain rounded frameless paper, a top border only, shadow, thin drag strip,
  invisible resize zones and the same two controls. No Pin button or Pinned action.
  Use conservative Space membership; verify Mission Control, Stage Manager and
  full-screen apps before making claims about those environments.
- All V1.1 tools remain shared. Qt's native Command editing conventions and Option
  snapping bypass apply on Mac. Active text editors exclusively own letters,
  numbers, clipboard and editor undo; canvas tools require active board/canvas focus.
- macOS capture uses ScreenCaptureKit still images, explicit Screen Recording
  preflight/request and a System Settings route. Denied/failed/empty captures
  create no board. No microphone/Accessibility permission for capture. Keep Escape
  active while an asynchronous capture is pending; discard stale callbacks.
- Mac desktop coordinates are points. Capture each intersected display using
  local points and that display's pixel scale, then compose the pieces explicitly.
  Handle negative origins and mixed scales. Apply DPR once in display caching.
- Preserve locked screenshot caching, dirty painting, immutable PNG identity,
  sparse gesture previews and exclusion from editable/snapping candidates.
- Keep QClipboard/custom MIME; verify Preview/browser/screenshots/Finder formats
  before adding a native fallback. Persist guides, grid and shortcut preset via
  QSettings; boards stay session-only.
- Build the Mac `.app` on macOS. Include Version 1.1 metadata, icon, bundle ID,
  minimum version, accessory setting and capture purpose. Attempt a complete
  Universal2 stack; document any real blocker and allow arm64 first. Do not claim
  Intel execution from a binary-slice check alone. Keep Mac dependencies out of Windows.
- Initial ad-hoc signing is acceptable. Document Apple's Open Anyway flow and
  leave Developer ID/notarisation/stapling available for a future release.
- Deliver separate **WinMiniWhiteboardV1.1.zip** (`Mini Whiteboard/` with EXE/runtime)
  and **MacMiniWhiteboardV1.1.zip** (`Mini Whiteboard.app`). Preserve old Windows
  artifacts. Create/verify the Mac ZIP using ditto on Mac; transfer without repacking.
- Final archives belong on the Windows Desktop after verification. Clearly report
  PASSED/FAILED/NOT RUN, including native GUI/hardware checks. Windows work cannot
  claim a Mac build; provide exact Mac continuation steps and finish independent work.

Implementation evidence is in TEST_RESULTS.md and CROSS_PLATFORM_REPORT.md;
MACOS_CHECKLIST.md defines the outstanding native acceptance gate.

This is a keyboard-first, minimalist floating whiteboard utility. It should
run quietly in the system tray when not being used.

Implement the application, not just a plan, mock-up, or code skeleton.
Use Python and PySide6. Keep dependencies minimal and organise the code
into sensible modules rather than one enormous file.

Read the existing repository before making changes. If it is empty,
create the complete project. Consult current official documentation where
necessary, especially for Windows hotkeys, transparent windows, and DPI
handling.

CORE EXPERIENCE

I want to create a small whiteboard anywhere on my desktop by defining
its two opposite corners with my cursor and a global keyboard shortcut.

There must be no permanent drawing toolbar, ribbon, sidebar, colour
palette, or large title bar. Tools are controlled through keyboard shortcuts.

The whiteboard should feel like a clean, floating piece of white paper,
not a conventional paint application.


TWO-PRESS WHITEBOARD CREATION — THE MOST IMPORTANT REQUIREMENT

Global shortcut: Ctrl+Alt+W.

This must work while another normal desktop application has focus.

First press:
Record the cursor’s current screen position as the FIRST CORNER.
Enter placement mode, but do not create a whiteboard yet.

While moving the mouse:
Keep the first corner fixed.
Show a live rectangle of small round translucent white dots between the first corner
and the cursor’s current position.

The desktop must remain visible inside and outside this preview.
Do not display a solid white rectangle until placement is confirmed.
Use a preview outline that remains visible over light and dark backgrounds.

Second press:
Record the cursor’s current position as the OPPOSITE CORNER.
Remove the preview overlay.
Create the actual whiteboard within the selected rectangle.
Focus the new whiteboard so it is ready to use.

This is:
PRESS → MOVE MOUSE → PRESS AGAIN.

It is NOT:
- Press once to open a preset-size board.
- Click and drag with the mouse button.
- Release the hotkey to finish placement.

The user does not need to hold the shortcut or a mouse button while
moving between the two corners.

Placement must work in every direction. The first point could become
any of the four corners, not necessarily the top-left corner.

Calculate the normalised rectangle using the minimum x/y values and
absolute coordinate differences.

Handle:
- Multiple monitors.
- Monitors with negative desktop coordinates.
- Windows display scaling.
- Correct conversion between physical screen coordinates and Qt logical
  coordinates where required.

The final whiteboard body must match the preview bounds. A decorative
shadow may extend outside those bounds.

Escape cancels placement without creating anything or changing existing
whiteboards.

Reject selections smaller than 160 × 100 logical pixels with a subtle
message and remain in placement mode. Do not silently replace them with
a preset-size whiteboard.

Prevent keyboard auto-repeat from treating one held shortcut as two
separate presses.

Allow multiple independent whiteboards. Whenever no placement operation
is active, Ctrl+Alt+W starts creation of a NEW board. Existing boards must
not be erased or replaced.


APPEARANCE AND WINDOW BEHAVIOUR

Use these visual defaults:
- White background.
- Thin, approximately 1 px light-grey TOP border only. No side/bottom outline.
- No canvas inset on the sides/bottom; 11 px top drag strip
  (previously 32). Reserve compact 24 × 20 px control targets above artwork.
- Invisible 7 px resize zones on every edge/corner, independent of visual borders.
- Soft rounded corners, approximately 12 px radius.
- Very subtle shadow.
- Near-black drawing and text by default; C chooses a per-board colour.
- Clean system sans-serif font.
- Antialiased text, lines, and shapes.

No standard Windows title bar and no permanent tool controls.

The only permanent buttons are two small controls in the top-right:
- A neutral-grey minus for minimising.
- A red × for deleting/closing that whiteboard.

Make the icons visually small but give them comfortable click targets.
Use subtle hover feedback. Keep the controls separate from the drawable
content so drawing does not accidentally activate them.

Keep visible whiteboards above ordinary application windows, but do not
continually steal keyboard focus.

Clicking outside a whiteboard should let the user interact with other
applications normally. No invisible full-screen overlay may remain after
placement ends.

Allow moving the entire whiteboard by dragging a narrow empty area along
its top edge, excluding the controls.

Allow resizing the window using its edges and corners, with appropriate
resize cursors.

Resizing the window must not stretch or scale its contents. Preserve
objects outside the temporarily visible area so enlarging the window
reveals them again.

Do not show scrollbars or an infinite-canvas interface.


KEYBOARD-FIRST TOOL SYSTEM

Tool shortcuts operate only in the focused whiteboard, except for the
global creation shortcut.

Remember the last selected size for each tool. Default a newly created
whiteboard to the drawing tool.

D — DRAW

Press D to activate freehand drawing.
Hold the left mouse button and move to draw.

Use smooth, responsive strokes with round caps and joins.

Number keys select pen thickness:
1 = 2 logical pixels
2 = 4 logical pixels
3 = 6 logical pixels
4 = 9 logical pixels
5 = 14 logical pixels

Changing thickness affects subsequent strokes, not existing strokes.

A click without dragging should create a dot.

Store each completed stroke as an independent object so it can be
selected, erased, and undone.


T — TEXT

Press T to activate text placement.
Click inside the canvas to create a textbox and begin typing.

Support:
- Multiline text.
- Normal text selection, cursor movement, copy, paste, and deletion.
- Double-clicking existing text to edit it.
- Moving existing text using the selection tool.

Outside active text editing, number keys choose font size:
1 = 14 pt
2 = 20 pt
3 = 28 pt

Apply the chosen displayed size to every selected text object in Text mode,
including text previously scaled using transform handles.
Otherwise, remember that size for the next textbox.

Textboxes should have no visible background or permanent border.
Show a subtle editing/selection outline only when needed.

Enter inserts a new line.
Ctrl+Enter finishes editing.
Escape also finishes editing without deleting the text.
Clicking outside the textbox commits the edit.

Remove newly created textboxes that are left completely empty.

IMPORTANT INPUT RULE:
While a textbox is actively being edited, ordinary keys must type normally.
Letters such as A, T, D, S, V and E, and numbers 1 through 5, must NOT
activate tools or change sizes.

To change font size with the ordinary number shortcuts, finish editing,
keep/select the text object, enter Text mode, and press the desired number.

Do not solve this by preventing users from typing those characters.


S — SHAPES

Press S to enter shape mode.
Within shape mode, number keys select the shape:

1 = Rectangle
2 = Rounded rectangle
3 = Ellipse
4 = Straight line
5 = Single-headed arrow
6 = Triangle
7 = Diamond

Remember the most recently selected shape.

Click and drag to define a shape’s position and dimensions.
Show a live preview while dragging.
Release the mouse button to commit it.

Use outlined, unfilled shapes by default, with the board's active stroke colour.
Use a filled arrowhead where appropriate.

Hold Shift while creating:
- A rectangle: constrain to a square.
- An ellipse: constrain to a circle.
- Other closed shapes: preserve aspect ratio.
- A line or arrow during creation: snap its angle to 45-degree increments.

After creation, shapes must remain individually selectable, movable,
and resizable. Do not flatten them into a background image.

A/V uses one shared transform box for selected objects. In S mode, lines
and arrows additionally retain draggable endpoint handles. During transform
resizing, Shift preserves the current aspect ratio rather than forcing 1:1.

Escape cancels an unfinished shape preview.


1. A — SELECTION TOOL

Press A to activate the selection-and-transform tool.

Keep V as a backwards-compatible alias for the SAME tool. Do not create
separate selection states or competing implementations for A and V.

MARQUEE SELECTION

Click and drag on empty canvas to draw a rectangular selection marquee.
Use a thin dashed outline and a very subtle translucent fill.

Support dragging in all four directions.

On release, select ONLY objects entirely contained inside the rectangle.

Important:
- An object partly inside and partly outside must NOT be selected.
- Merely intersecting the marquee is not sufficient.
- Check the complete rendered bounds in canvas coordinates, accounting
  for stroke thickness, rotation, and scaling.
- Objects exactly touching the boundary count as contained, allowing a
  small numerical tolerance.
- Do not include selection handles or other interface decoration in
  object bounds.
- Objects extending beyond the whiteboard’s viewport must not count as
  fully contained just because their outside portions are clipped.

Apply this consistently to freehand strokes, text, and shapes.

An ordinary marquee replaces the previous selection.
Shift+marquee adds fully contained objects to the existing selection.

DIRECT SELECTION

Click an object to select it. Where objects overlap, choose the topmost
matching object. Give thin strokes a reasonable hit-test tolerance.

Shift+click toggles that object’s membership in the selection.

Clicking empty canvas without dragging clears the selection.

Dragging a selected object, or the interior of the current selection’s
transform box, moves the selection. Starting a drag on empty canvas
outside that box starts a new marquee.

Escape clears the selection when no interaction is in progress.

Selection must never include the whiteboard’s border, window controls,
or interface overlays.


2. SHARED TRANSFORM BOX — MOVE, RESIZE, ROTATE

When one or more objects are selected, show one shared transform box
around the selection, similar to a familiar graphics editor.

Appearance:
- A thin, unobtrusive outline.
- Small white circular resize handles with a contrasting outline.
- Handles at the corners and edge midpoints.
- A separate circular rotation handle just above the top-middle point,
  connected by a short line.
- Visually small handles with larger, comfortable hit targets.
- Appropriate hover and dragging cursors.

Handles should stay a consistent on-screen size regardless of object
scale or Windows display scaling.

MOVE

Dragging within the selected group moves all selected objects together,
preserving their relative positions and stacking order.

RESIZE

Dragging a resize handle scales the selection relative to the opposite
handle or edge, which stays anchored.

Corner handles scale proportionally by default.

For selections without text:
- Edge handles can resize along one axis.
- Holding Shift locks the current aspect ratio.

For selections containing text:
- Keep resizing proportional so glyphs are never stretched or squashed.
- Make all enabled resize handles respect this constraint.
- Scale text size and layout while retaining real, editable text.
- The existing T → 1/2/3 font-size presets must continue to work afterward.

A multi-object resize must transform the group as one unit: scale both
the objects and their spacing relative to the shared anchor. Do not
resize each object independently around its own centre.

Scale drawn geometry and stroke widths consistently.

Prevent zero-sized or invalid transforms. Do not introduce accidental
mirroring when a handle is dragged across the opposite edge.

ROTATE

Dragging the rotation handle rotates the whole selection around the
centre of the shared transform box.

Use continuous rotation by default.
Hold Shift to snap to 15-degree increments.

Rotate both each object and its position relative to the group centre.
Do not just rotate objects individually in place.

Text, shapes, and freehand strokes must all support rotation.

The transform box and handles should visually follow the transformation
rather than jumping around during the drag.

EDITABILITY AND INTERACTION

Do not flatten the selection into a bitmap or permanently merge its
objects. After deselecting, every object must remain independently
selectable and editable.

Calculate transformations from the state captured at drag start, rather
than repeatedly transforming the previous mouse-move result and
accumulating distortion.

Escape during a move, resize, or rotation cancels that operation and
restores the exact pre-drag state.

Give transform handles input priority over ordinary canvas interactions.
Transforming objects must not accidentally move or resize the whiteboard
window.

Keep the original window-edge resizing and top-strip window dragging
working separately.


3. BACKSPACE / DELETE

When the canvas has focus and text is NOT actively being edited:

Backspace or Delete removes ALL selected objects in one operation.

This must:
- Work for individual objects and multi-object selections.
- Clear the selection afterward.
- Be undoable as one action.
- Do nothing when there is no selection.
- Never close or delete the whiteboard itself.

While editing a textbox, Backspace and Delete must retain normal
text-editing behaviour instead of deleting canvas objects.


4. E — CIRCULAR ERASER WITH TWO MODES

Press E to activate the eraser.

While the eraser is active:
1 = Circular eraser, 8 logical-pixel diameter.
2 = Circular eraser, 16 logical-pixel diameter.
3 = Circular eraser, 32 logical-pixel diameter.
4 = Circular eraser, 64 logical-pixel diameter.
5 = Toggle whole-stroke eraser mode.

Keep these sizes in central configuration so they are easy to adjust.

The first use defaults to circular mode at size 2.

Remember the last selected mode and circular diameter for each board.

Pressing 1–4 always selects that diameter AND returns to circular mode.
Pressing 5 toggles whole-stroke mode. Toggling OFF always returns to the
DEFAULT circular size 2 (16 px), regardless of the previous diameter.

Entering whole-stroke mode retains the current circular diameter as its targeting
footprint. Keys 1–4 immediately exit this mode and choose that circular diameter.

Display an outlined circular cursor showing the actual erasing area.
Use a solid thin circle in circular mode and a subtly dashed circle in whole-stroke
mode. Switch the visual immediately when the mode changes; use neutral colours.
Make it visible on both white space and dark ink without adding a toolbar.

Show brief feedback when changing size or mode, such as:
“Eraser · 16 px”
“Eraser · Whole stroke”

The cursor must not appear in the document or remain visible after
switching tools or leaving the canvas.


5. CIRCULAR MODE — ERASE ONLY INSIDE THE BRUSH

Holding the left mouse button and dragging removes only painted content
inside the circular brush’s swept path.

For example, dragging through the middle of a long drawn stroke must
remove that middle section while leaving both outside sections intact.

Do not delete an entire object just because the circular eraser touches it.

Support partial erasure of freehand strokes, shape outlines/fills, and
rendered text. Keep underlying objects editable, using object-local
erasure masks or another suitable non-destructive representation where
needed.

Do not implement this by painting white over the canvas.
Erased regions must actually stop rendering and participating in hit tests.

Erasure must remain attached to the affected object:
- Moving it must not leave the erased area behind.
- Scaling or rotating it must transform the erasure consistently.
- Deselecting or editing it must not silently restore erased content.

Preserve underlying text as text and shapes as shapes. Do not flatten
the entire canvas to support erasing.

Apply erasure to existing artwork beneath the brush, including overlapping
objects. A later stroke drawn across a previously erased area must appear
normally; do not leave a permanent canvas-level mask that erases future
objects.

Handle the full swept area between successive pointer positions, not
just isolated circular stamps at mouse-event positions.

Fast drags must not leave gaps or jump over thin strokes.

Completely erased objects must not remain selectable as invisible junk.


6. WHOLE-STROKE MODE — KEY 5

In this mode, touching any surviving painted portion of a freehand stroke
removes that entire stroke.

A stroke means one original pen-down to pen-up drawing gesture.

If circular erasing previously split that stroke into visible fragments,
whole-stroke mode must remove all remaining fragments belonging to that
original stroke, not just the fragment under the cursor.

Preserve a logical stroke identity to support this behaviour.

Dragging across multiple strokes removes every stroke intersected by the
brush’s swept path, including between mouse-event positions.

Whole-stroke mode targets freehand strokes only. It must not unexpectedly
delete an entire textbox or closed shape. Those objects can be removed
through selection plus Backspace/Delete, or partially erased in circular
mode.

Hit-test against actual remaining artwork after rotation, scaling, and
previous erasures, not stale bounds or already-erased portions.


7. INPUT ROUTING AND UNDO/REDO

All ordinary tool shortcuts apply only to the focused whiteboard when
no textbox is actively being edited.

Typing A, V, E, or 1–5 inside a textbox must insert those characters
normally. Do not intercept text selection or text-editing shortcuts.

Preserve the distinction between editor undo while typing and document
undo outside text editing.

Add complete undo/redo coverage for:
- Moving, resizing, and rotating a selection.
- Deleting multiple selected objects.
- Partial circular erasure.
- Whole-stroke erasure.

One continuous mouse drag must create ONE undoable operation, even when
it affects many objects.

Undo must restore exact geometry, text properties, masks, stroke
identities, and stacking order. Redo must reproduce the result.

Escape during an active eraser gesture cancels that gesture and restores
its pre-drag state without adding an undo entry.

Do not turn selection-only changes into document-edit undo operations.


EDITING SHORTCUTS AND FEEDBACK

Support:
Ctrl+Z = Undo
Ctrl+Y or Ctrl+Shift+Z = Redo
Delete/Backspace = Delete all selected objects in one operation when not editing text
Escape = Cancel the current preview/interaction or clear selection
F1 = Show/hide a compact shortcut reference

Undo/redo must cover:
- Drawing and creating objects.
- Erasing and deleting.
- Moving, resizing, and rotating selections.
- Committed text edits and font-size changes.

Treat one continuous drag as one undo action, not hundreds of actions.

While editing text, use normal text-editing behaviour for shortcuts such
as Backspace, Delete, and Ctrl+Z. Avoid triggering both the text editor’s
undo and the canvas undo simultaneously.

Do not add a toolbar to communicate the current tool.

Instead, briefly display a small, non-interactive label when a tool or
size changes, such as “Draw · 3” or “Shape · Arrow”, then fade it away.

Use appropriate cursors for drawing, text, selection, and resizing.
The F1 reference should appear only when requested and should not change
the canvas layout.


BACKGROUND, MINIMISING, AND CLOSING

On launch, show only a system-tray icon. Do not open a default whiteboard,
dashboard, splash screen, or console window in the normal packaged build.

The minus button hides that board to the system tray while preserving
all its contents, geometry, and undo history.

Provide a tray menu listing existing boards, using simple names such as
“Whiteboard 1”, with an indication of whether they are minimised.
Choosing a board restores and focuses it at its previous position.

Double-clicking the tray icon should restore the most recently minimised
board, if one exists.

The red × deletes that individual board and its contents, not the entire
application. Give it a tooltip that makes this clear.

Closing the last board must leave the app running in the tray.
Only an explicit “Exit Mini Whiteboard” tray action should terminate it.

Disk persistence across application exits is not required for this
version. Do not lose content merely because a board is minimised.

Include “Keyboard shortcuts” and “Exit Mini Whiteboard” in the tray menu.

Use a single-instance guard so launching the app twice does not create
duplicate tray icons or competing hotkey registrations.

Do not add startup entries, install a Windows service, or require
administrator privileges.


IMPLEMENTATION AND PERFORMANCE

Use a proper object-based canvas/document model. Keep stroke, text,
shape, selection, and undo state separate from painting.

Prefer event-driven behaviour. Avoid busy-wait loops or continuous
high-frequency polling when idle.

Any cursor-tracking timer needed for the placement preview should run
only during placement and stop immediately on confirmation or cancellation.

Use Windows’ native global-hotkey registration, including repeat
suppression, and integrate it safely with the Qt event loop.

Handle hotkey-registration failure visibly and helpfully rather than
silently pretending the shortcut is available.

Keep GUI operations on the GUI thread.
Clean up hotkeys, preview overlays, timers, and tray resources on exit.

Keep styling values and shortcut mappings centralised and easy to change.

Do not add accounts, cloud syncing, AI features, networking, a web server,
or unrelated features.


DELIVERABLES

Create:
- Complete working source code.
- Dependency/install instructions.
- A straightforward development launch command.
- A README covering all shortcuts and the two-press placement workflow.
- A Windows build script or PyInstaller configuration for a no-console
  executable.
- Tests for the non-GUI logic where practical.
- A manual Windows testing checklist for GUI and operating-system behaviour.

Implement and test incrementally:
First get the tray app and exact two-press placement working.
Then implement the floating board and tools.
Then add editing, undo/redo, polish, and packaging.

Do not leave the core interactions as TODOs.


ACCEPTANCE CHECKS

Verify that:
1. Ctrl+Alt+W starts placement while another application is focused.
2. The first cursor point stays fixed and the preview follows the second.
3. Only the second distinct shortcut press creates the board.
4. Placement works in all directions, and Escape cancels it cleanly.
5. The finished board matches the preview’s position and dimensions.
6. Tool shortcuts and number mappings work without a toolbar.
7. Typing “Today is day 123” inserts exactly that text without switching tools.
8. Text supports moving, proportional scaling, rotation, partial erasure, and font-size presets while remaining editable.
9. Shapes can be created, selected, moved, and scaled after creation.
10. Undo/redo restores actual document state.
11. Minimising preserves content and restoring returns the same board.
12. Deleting one board leaves other boards and the tray app running.
13. No invisible overlay intercepts desktop input after placement.
14. Idle operation does not continuously consume CPU.

Run the checks available in your environment. Clearly distinguish what
you actually tested from Windows-specific behaviour that still needs
manual verification.

Finish with the exact commands to install, run, test, and build the app,
plus any genuine remaining limitations.

8. VERIFICATION AND DELIVERY

Add automated tests where practical and a manual GUI checklist covering:

- Marquee selection in every drag direction.
- Fully contained objects selected; partially contained objects excluded.
- Correct containment after rotation and scaling.
- Shift+click and Shift+marquee selection changes.
- Moving, resizing, and rotating mixed-object selections.
- Text remaining editable and proportionally scaled.
- Backspace/Delete removing the whole selection as one undo action.
- Circular erasure preserving artwork outside the brush.
- Fast eraser drags producing continuous results.
- Erasing transformed objects without coordinate errors.
- Whole-stroke mode removing all remaining fragments of a touched stroke.
- Keys 1–4 returning from whole-stroke mode to circular mode.
- Erasure staying attached when objects are moved, resized, or rotated.
- Newly drawn content remaining visible over previously erased areas.
- Typing “A V E 12345” without activating tools.
- Undo/redo and Escape cancellation restoring exact state.
- Existing whiteboard placement, minimising, restoration, and deletion
  continuing to work.

9. POLISH AND PERFORMANCE REQUIREMENTS

These requirements supersede conflicting earlier visual and eraser-mode rules.

- Keep the existing two-press Ctrl+Alt+W workflow, document tools/transforms,
  history, tray, native coordinates, rounded corners and exterior soft shadow.
- The 1 px top border remains thin. The refinement in section 11 supersedes this
  earlier inset change. Reduce the effective internal inset to roughly
  one third of its former value. Do not count the exterior 8 px shadow as internal
  padding. Reduce control-strip padding without allowing drawing over controls.
- Render the eraser cursor, selection controls and marquee above document
  clipping on a passive surface. A circle near any edge/corner must stay complete,
  except where window controls correctly occlude it. Keep real drawing/erasing
  inside valid canvas pixels; never expand the document to fit cursor visuals.
- New strokes/shapes record their creation clip. Circular eraser sweeps record their
  current valid canvas clip before inverse transformation. These immutable clips
  keep outside pixels unchanged after later window resizing. Resizing alone must
  still preserve all existing offscreen artwork and complete selection bounds.
  Whole-stroke targeting is limited to the valid canvas, then removes the entire
  touched original stroke, including its offscreen fragments.
- Verify actual native always-on-top state and Z-order after another ordinary
  window receives focus. If reliable, retain it without adding a pin button.
  If unreliable, add the minimal per-board pin toggle described in the request,
  preserving document, selection, history, geometry and activation state.
- Placement preview uses round 2.5 logical-pixel dots, target 6 px gaps and 75%
  white opacity. Use a very faint dark offset shadow for bright backgrounds.
  No rectangle fill, continuous stroke, conventional dashes, or warning colours.
  Centralize all visual constants; use one QPainter surface per monitor and
  repaint only old/new edge regions when the physical rectangle changes.
- Profile circular/stroke erasing, marquee, movement of one/many objects,
  resizing, rotation and repaint at 10/100/500 mixed partially erased objects
  before optimizing. Preserve reproducible before/after measurements.
- Track old/new affected bounds and antialias padding. Cull painting against
  dirty regions. Use cached bounds before detailed hit/eraser geometry; preserve
  topmost hit selection and complete marquee containment. Add a spatial index
  only if scanning cached bounds remains a measured bottleneck.
- Capture selected source objects/frame once per gesture. Update sparse previews
  for affected objects; do not copy/serialize the entire document per sample.
  Commit one history action on release and restore on Escape. Reuse local paths
  and masks across affine transform previews; invalidate only changed geometry.
- Erasing uses an analytic swept capsule between samples (no discrete gaps or
  unnecessary tiny samples), candidates from swept bounds, and incremental mask
  unions. No eraser timer, background GUI mutation or full-board raster mask.
- Text editing must insert exactly 1234554321 and preserve tool/mode/size state.
  Keep active-editor and active-board/canvas focus guards plus ShortcutOverride.
- Verify all four edges/corners, light/dark preview backgrounds, focus and
  click-through, eraser toggle sequence 5/5/5/1/5/4, unchanged placement and
  lifecycle, 10/100/500 workloads and history correctness. Report actual measured
  improvements separately from native/manual behaviours not tested.

10. VERSION 1.1 RELEASE REQUIREMENTS — 2026-09-30

These additions extend all earlier placement, selection, text, eraser and polish
requirements. The requested release label is 1.1, including features from the
previous development build that had been labelled 1.2.0.

- Central APP_VERSION is "1.1". About, tray, F1, QApplication metadata, source
  --version output, Windows file/product resources and build assembly version use
  it (Windows numeric form 1.1.0.0). Keep the no-console, asInvoker, PMv2 build.
- Ctrl+C/X/V/D copy/cut/paste/duplicate any unlocked selected strokes, shapes,
  text and images. Preserve all original geometry, local masks/clips, transforms,
  colour, widths, text and relative stacking. New copies receive independent IDs.
  Same-board pastes advance 16 px each time; first cross-board paste keeps source
  coordinates, then advances 16 px per repeat. Duplicate always advances 16 px.
- Windows clipboard holds schema-versioned, validated JSON using
  application/x-mini-whiteboard-objects+json and a normal transparent image.
  The external image uses surviving selection bounds, capped at 4096 px longest
  side, and excludes tool decorations. Editable content remains full fidelity.
  Inspect clipboard only on a command, with no clipboard polling.
- Images paste from Windows image/DIB MIME, PNG/JPEG/WEBP MIME or local file URLs.
  PNG/JPG/JPEG/WEBP file drops are accepted. Immutable PNG source bytes and natural
  dimensions are retained with cached QImage decode and smooth display scaling.
  Initially fit to 90% of the viewport without upscaling; centre at an in-canvas
  cursor or board centre, clamped to the viewport. Images participate in selection,
  masks, transforms, snapping, copy, ordering and history. All resize handles for
  a selection containing an image preserve aspect ratio, as for text.
- Reject unreadable images or images above 64 million pixels and editable MIME
  payloads above 96 MB with temporary feedback, leaving the document unchanged.
- Arrows move selected objects by 1 logical pixel, Shift+Arrows by 10. Consecutive
  nudges within 0.4 seconds with the same membership/history position merge for undo.
- C opens a compact rounded, shadowed temporary palette. Numbered presets:
  1 near-black, 2 red, 3 blue, 4 green, 5 yellow, 6 purple, 7 white. Include native
  Custom colour and up to seven recent colours. Dismiss on choice, Escape or an
  outside click. Recolour selected compatible objects in one action; images are
  unchanged. Also remember the chosen default per board for future objects.
- Ctrl+A selects all unlocked surviving objects. Retain Shift-click toggling,
  additive full-containment marquee and Escape priorities. Right-click uses a
  small QMenu: Cut, Copy, Paste, Duplicate, Delete, Bring to front, Send to back,
  Lock selection; direct locked hits expose Unlock this object. A Locked objects
  submenu also allows recovery of hidden or covered locked objects.
- Locked objects render normally but ordinary selection, transforms, deletion
  and either eraser ignore them. Lock/unlock and stable group reordering are undoable.
- The canvas router requires an active board, canvas focus and no active editor.
  The real transformed QTextEdit retains ShortcutOverride and owns letters,
  C/numbers, Ctrl+A/C/X/V/Z, arrows, Delete and Backspace. No tool-level global
  QAction/QShortcut is introduced. Editor and document undo stay separate.
- Tray structure: New Whiteboard, Screenshot to Whiteboard, Whiteboards submenu,
  Snap & Guides submenu, Keyboard shortcuts, About Mini Whiteboard, Exit Mini
  Whiteboard. Show Retry global shortcut only after registration trouble.
- Snap & Guides shares preferences globally through QSettings. Smart Guides
  defaults ON, Grid Snap OFF; checkmarks reflect current state. Persist only
  these preferences; boards/documents remain session-only.
- Smart targets are other objects' surviving axis-aligned bounds and board
  edges/centres. Cache/sort targets once per move/resize gesture and query nearby
  values within 6 logical px. Limit irrelevant orthogonal spans. Show subtle
  translucent guides on the passive decoration overlay, never in clipboard data.
- Grid uses a 10 logical-pixel spacing. Nearby smart alignment wins; otherwise
  grid aligns movement/resize. Alt disables both. Proportional resize adjusts on
  the handle's resize ray, choosing a reachable axis while preserving its anchor
  and ratio. No mirroring. Clear guides on finish, cancel, preference change or
  loss of alignment. No extra per-pointer detailed geometry scans or document copy.
- Register Ctrl+Alt+S with the same native RegisterHotKey/MOD_NOREPEAT event
  infrastructure as W. Each registration reports failure independently.
- S capture: show a live-desktop overlay per monitor with dotted rectangle;
  click anchors physical coordinates, drag changes the region, release confirms.
  A one-alpha veil makes the overlay receive native mouse input. Escape cancels;
  switching W/S cancels the other workflow. Capture only after hiding all overlays
  and synchronizing desktop composition. GDI reads the physical virtual-desktop
  rectangle, including negative coordinates; all resources are released.
- Create a screenshot board around the selected region, preserving image aspect
  ratio and filling the usable canvas where dimensions allow. Minimum board size
  remains 160×100 logical px. The image starts locked and Draw is ready, with a
  temporary unlock hint. Screenshot creation is an undoable image insertion.
- Ctrl+Alt+W is unchanged: first hotkey anchor, mouse movement, second distinct
  hotkey confirm. Neither click-drag nor hotkey release confirms W placement.
- Each edit is one immutable before/after operation; gesture previews remain
  sparse. Selection and application preferences create no history. No dashboard,
  permanent toolbar, file/project UI, accounts, network service or new runtime
  dependency is introduced.
- Run original regressions, new automated tests, native clipboard/capture/keys,
  10/100/500 benchmarks and 4K image interactions. Document actual versus pending
  hardware/manual checks. Build and launch the executable, then replace the
  existing Desktop/MiniWhiteboard.zip with only the new distribution and verify
  every entry, hashes, runtime files and embedded Version 1.1. Retain the project.

11. SCREENSHOT PERFORMANCE AND TOP-ONLY BORDER REFINEMENT

Keep Version 1.1 and all existing tools, tray behaviour and hotkeys.

- Profile matched blank/screenshot boards before production edits. Give each
  20 strokes, 20 shapes and 10 text objects. Measure drawing, both erasers,
  marquee and movement/resize/rotation of 10 annotations. Test source images at
  1920×1080, 2560×1440 and 3840×2160; report native versus offscreen measurements.
- Retain the captured ImageObject and original immutable PNG. Its logical
  identity, stacking, masks and history are unaffected by rendering optimisation.
- Cache the original locked, unchanged capture at the viewport's physical size,
  multiplying logical dimensions by DPR exactly once. Bake its original transform
  and rounded/control clipping into a premultiplied display image once, then
  reuse one-to-one raster blits under Qt's dirty-region clip. No per-frame decode,
  source resampling, QImage/QPixmap conversion or full-size buffer creation.
- Cache key contains viewport size, DPR and document clip, never annotation
  contents/history. Annotation edits do not invalidate it. Changes to viewport,
  scale or clipping rebuild it. An unlocked or changed capture uses normal image
  rendering with the existing decode/paint cache. Undoing back to the original
  locked object can reuse the unchanged background cache.
- Keep locked objects out of the scene's editable candidate list before bounds
  queries. Clicks/marquees/erasers exclude them; context unlock still queries all
  objects. Whole-stroke mode filters non-strokes before intersection tests.
  Smart Guide targets omit locked images and use cached nearby annotation bounds.
- Freehand invalidation covers old/new tail control points plus pen radius and
  antialias padding. Earlier smoothed segments stay untouched. Erasure and
  transforms retain their bounded dirty regions; overlay-only movement never
  requires document painting. Verify incremental and complete-render pixel equality.
- Undo snapshots share immutable image objects and bytes. Confirm with identity
  checks that annotation operations neither copy nor serialize screenshot data.
  There is no clipboard polling or clipboard dependency while annotating.
- Fill rounded white paper without an outline pen. Paint only a centred 1 px
  neutral-grey top line. Retain the existing radius, soft exterior shadow, narrow
  top drag area, minimise/delete controls and always-on-top behaviour. Remove
  side/bottom canvas inset as well, so screenshots have no white rim either.
- Canvas clipping follows the actual rounded paper and reserved control holes.
  Content cannot cover controls. The passive tool overlay continues beyond the
  paper so cursors/handles are not truncated at its edges.
- Use invisible EDGE_GRIP=7 logical px zones, routed explicitly from idle canvas
  pointer events to the existing window resize implementation. Controls and
  transform handles take priority; active drawing/eraser drags retain their input.
- Verify top/side/bottom pixels, cache reuse and invalidation, 100/125/150/200%
  raster DPR, all eight native resize directions, unlock/transform/undo and all
  Version 1.1 regressions. Rebuild, launch and replace the same tester ZIP, then
  reopen and verify the actual archive against the new build.
