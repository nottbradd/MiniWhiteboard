# Manual Windows testing checklist — Version 1.2

Use the final built executable unless a step explicitly mentions source. Record
Windows version, display arrangement, each display's scaling, and actual results.
Do not mark an item PASS just because an automated model test passes. See
[TEST_RESULTS.md](TEST_RESULTS.md) for the actual release checks.
The V1.1 package passed 110 native GUI checks, 31 real input checks and 17
packaged checks on one Windows 11 display at 100%. Physical mixed-DPI,
clean-machine/Windows 10 deployment, hand-operated IME and extended use remain
NOT RUN. Use the published ZIP or the current release output below.

## A. Launch, tray, and hold/release placement

1. Exit any running instance using **Exit Mini Whiteboard** in the tray menu. Launch
   `dist\windows-v12\Mini Whiteboard\Mini Whiteboard.exe`. Expect one tray icon, no board,
   console, dashboard, or splash. Look in the hidden tray-icon area if necessary.
2. Focus a disposable Notepad document. Point at the first corner and hold
   Ctrl+Alt+W. Expect a dotted transparent preview, no board and no focus change.
3. Move while holding for several seconds. Repeated key-downs cannot confirm,
   restart or change the first corner. Competing S is ignored.
4. Release W first, then repeat releasing Control first and Alt first. Each
   hold creates one focused board at the sampled bounds. Remaining held S/W
   must not become tools. A fresh physical hold works after the keys drain.
5. Test four directions and negative desktop coordinates. A stationary release
   cancels completely with brief feedback and leaves no waiting outline.
6. Select less than 160 x 100 logical pixels. Expect cancellation; a fresh hold
   immediately starts a new selection that can complete normally.
7. Escape while held cancels, including with another app focused. Held repeats
   cannot restart it. Repeat menu cancellation, display changes and app exit.
8. Create three boards using separate holds. Each preserves the other boards.
9. During placement click a harmless button in a test application through the
   preview. Expect it to receive the click. Cancel and repeat clicks inside and
   outside the former outline. Expect no invisible overlay interception.
10. Temporarily register Ctrl+Alt+W in another utility (or run a separate native
    RegisterHotKey test). Launch Mini Whiteboard. Expect a visible conflict
    explanation. Release the other binding and choose **Retry global shortcut**.
    Verify creation then works. Restore the other utility's original setting.

## B. Multiple monitors and scaling — requires suitable hardware

1. In Windows Settings → System → Display, put a second monitor left of and then
   above the primary, producing negative X and Y coordinates. Use each monitor
   for the four placement directions from A5. Expect correct physical bounds.
2. Test Windows scale values 100%, 125%, 150%, 175%, and 200%. At each scale, test
   a normal selection and the 160 × 100 logical minimum. For example, at 150%,
   the minimum is 240 × 150 physical pixels. One pixel smaller must be rejected.
3. Use two adjacent monitors with different scaling (for example 100% and 150%).
   Begin on one and confirm on the other, in both directions. Expect a continuous
   physical outline and a final paper body at the same bounds. A shadow may
   extend outside; no extra white margin may extend outside.
4. Repeat across monitor seams with the selected rectangle mostly on the first
   monitor, mostly on the second, and close to equal overlap. Confirm no sudden
   size or position jump and no incorrect minimum-size substitution.
5. Move a board between differently scaled monitors. Expect readable text,
   appropriate scaling, unchanged document coordinates, and working controls.
6. Begin placement and disconnect a monitor. Expect cancellation and removal of
   all previews. Reconnect and verify a fresh placement works.

Restore your preferred display arrangement/scaling after these checks. Emulated
scale tests are supplementary; they do not replace actual mixed-monitor testing.

## C. Paper window, controls, and desktop interaction

1. Inspect the white fill, approximately 1 px light-grey TOP border only, approximately
   12 px rounded corners, subtle shadow, dark ink, and system sans-serif type.
   Expect only the grey minus and red delete controls permanently visible.
2. Hover/click both controls. Targets should be comfortable, hover subtle, and
   the delete tooltip explicit about deleting this board and its contents.
3. Draw close to the controls. The canvas starts 11 px below the top edge and
   reaches the sides/bottom; its control cutouts must exclude the buttons.
   Drawing must not accidentally activate a control.
4. Drag the empty top strip, excluding controls. Use the invisible 7 px zones to
   resize each edge/corner. Expect matching cursors and a minimum usable window.
5. Draw/text near the bottom-right, shrink the window until they are hidden, then
   enlarge it. Expect the original objects at their original sizes/coordinates.
   There must be no canvas scrollbars or zoom/stretch behavior.
6. Click another application. It must receive keyboard input while the board
   remains above ordinary windows. Wait several seconds: the board must not
   repeatedly steal focus.
7. Click through the shadow and rounded-corner cutouts onto a harmless control
   in another application. Expect the underlying application to receive input.

## D. Draw and text — include the exact typing regression

1. Press D, try each 1–5 thickness, draw curves and sharp changes of direction.
   Expect round caps/joins and responsive strokes. A click must make a dot.
   Changing thickness must leave earlier strokes unchanged.
2. Press T, click, and type exactly **Today is day 123**. Expect that exact string,
   no tool changes, and no font-size changes. Also type **A V E 12345**,
   **1234554321**, and **TDSVE 1234567**.
3. Use Enter for multiple lines, arrows, Shift+arrows, mouse selection, Ctrl+A,
   Ctrl+C, Ctrl+V, Delete, Backspace, Ctrl+Z, Ctrl+Y, and Ctrl+Shift+Z. Expect normal
   editor behavior; a text undo must not remove an unrelated canvas object.
4. Finish separately with Ctrl+Enter, Escape, and clicking outside. Expect text
   retained and editor outline removed. A new empty textbox must disappear.
5. Double-click text from Draw, Text, Shape, and Select modes. Expect editing
   without an accidental stroke/shape being left behind.
6. Finish editing, press V, select and move the text. Press T then 1, 2, 3.
   Expect 14, 20, 28 pt text, with clean glyphs. Font changes must undo/redo.
7. In T mode with no text selected, choose a size and create a new textbox. Expect
   that size for the new object; other text is unchanged.
8. Try long multiline text and non-ASCII text/paste. Verify the editor and
   committed rendering agree in position, font, and line breaks. Partially
   hidden text must reappear when the board is enlarged.

## E. Shapes, selection, eraser, and history

1. In S mode create all seven shapes with 1–7. Check outlined unfilled shapes,
   filled arrowheads, live previews, and Shift square/circle/45-degree constraints.
2. Press A, then V. Both must retain the same selection. Click overlapping objects
   to choose the topmost. Check thin-stroke tolerance. Shift+click adds/removes.
3. Marquee in all four directions. Fully enclose some strokes, text, and shapes
   while only crossing others. Only fully contained objects may be selected.
   Include thick strokes and objects exactly on the boundary. Shift+marquee adds.
4. Rotate/scale objects and repeat containment. Shrink the board to clip some
   artwork, then marquee its visible part: the full offscreen object must not be
   selected. Enlarge the board to verify hidden content is preserved.
5. Select a mixed group. Drag a selected object and then empty space inside its
   shared box. All objects and their spacing must move together, preserving order.
   Empty clicks clear; empty drags outside the box begin a new marquee.
6. Test every corner and edge handle. The opposite anchor stays fixed. Corners
   preserve proportions. Non-text edges can scale one axis; Shift preserves the
   current ratio. Any group containing text scales proportionally at all handles.
   Cross the opposite anchor: no mirroring or zero-sized object is allowed.
7. Rotate groups with the separate handle. Every object and its position must
   rotate around the group centre. Shift snaps to 15 degrees. The box follows
   smoothly during and after each drag. Deselect and edit each object separately.
8. In S mode, move both endpoints of a rotated/scaled line or arrow. A/V still
   shows the shared transform box. Object controls must never move the window;
   top-strip and window-edge dragging must still work separately.
9. Delete and Backspace each remove the whole selection with one undo. No selection
   is a no-op; neither key closes the board. Check normal text deletion in an editor.
10. Press E: first use is 16 px circular mode. Check 1=8, 2=16, 3=32, 4=64. Cut the
    middle of a long stroke: both outside pieces remain. Check shape outlines,
    arrowhead fills, and letters. The brush must cut all overlapping objects.
11. Sweep rapidly across thin strokes with large gaps between mouse samples.
    There must be no skipped lines or isolated-stamp gaps. Artwork outside the
    brush remains unchanged. Fully erased objects must not remain selectable.
12. Move, resize, and rotate partially erased artwork, then erase again. Cuts
    must follow it with correct coordinates. Draw a new stroke over an old cut;
    the new stroke must be visible.
13. Press 5: touch one remaining fragment of a partially erased freehand stroke.
    All fragments of that original stroke must disappear. Crossing multiple
    strokes removes all touched strokes; text and shapes remain. Passing only
    through an old erased gap must not target a stroke.
14. Press 1–4 after mode 5: return to circular mode at that diameter. Switch tools
    and back: remember mode and diameter separately for each board. The two-tone
    brush circle must show its actual area over white and dark ink, and disappear
    on leaving canvas, entering text editing, or changing tools.
    From circular size 4, press 5/5/5/1/5/4. Expect stroke 64 / circular 16 /
    stroke 16 / circular 8 / stroke 8 / circular 64. Whole-stroke targeting is
    subtly dashed; circular mode is solid. Feedback changes immediately.
15. Double-click rotated/scaled/partially erased text. Editing stays in place and
    keeps cuts visible. Type **A V E 12345**, select/copy/paste, undo/redo, Delete,
    Backspace, and multiline input. No tool switch, object deletion, or document
    undo may occur. Test right-click context menus without losing the edit.
16. Finish editing through Escape, Ctrl+Enter, and outside clicks. T then 1/2/3
    sets visible 14/20/28 pt after scaling, including several selected textboxes.
    Rotation and masks remain. Check long text, accented text, RTL and emoji.
17. Undo/redo each move, resize, rotation, multi-delete, partial erase, whole-stroke
    erase, text commit, and font change. Each continuous drag is one action with
    exact geometry, text, masks, IDs, and stacking restored. Selection adds none.
18. During each transform and each eraser mode, press Escape before release.
    The exact original state must return without a history entry. Undo followed
    by a new edit must discard the old redo branch.
19. Inspect circular handle visuals and hit targets at 100/125/150/200% scaling,
    before/after object scaling and moving between differently scaled monitors.
    Handles remain visually small and easy to grab. Check pointer cursors.
20. Check transient feedback and F1. The reference must show A/V, both eraser modes,
    group transforms and selection deletion, without resizing canvas or stealing
    editor focus. No toolbar, sidebar, or properties panel is present.

## F. Tray lifecycle, exit, and packaged build

1. Create boards 1–3 with different content and undo histories. Minimize 1 then 2.
   Expect both in the tray menu with minimized indications. Double-click the tray
   icon: board 2 returns at its prior position. Repeat to restore board 1.
2. Restore a specific board via its tray entry. Verify text, shapes, selection,
   geometry, and undo/redo still work. Work on one board; others remain unchanged.
3. Delete board 2. Expect only its entry/window/content removed. Delete the last
   board: the tray icon remains, and Ctrl+Alt+W can create another.
4. Launch the executable twice. Expect one tray icon and one functioning global
   shortcut. The new process should exit without replacing the first instance.
5. Select **Keyboard shortcuts** in the tray, then close the reference. Select
   **Exit Mini Whiteboard**. Expect process, tray icon, boards, shadows, previews,
   hotkeys, and timers gone. Restart to verify hotkeys can register again.
6. Copy the entire distribution folder to a clean Windows machine with no Python
   installed. Launch as a standard user. Expect the same no-console behavior and
   no installer, service, startup registration, account, or network requirement.
7. Use Task Manager to observe an idle tray app for at least 60 seconds. Expect
   near-zero CPU with no continuous cursor polling. During placement expect brief
   activity; cancel and verify it returns to idle.
8. Exit/relaunch. Expect old boards absent, as disk persistence is outside scope.

## Optional automated native commands

```powershell
.\.venv\Scripts\python.exe -m scripts.native_smoke
.\.venv\Scripts\python.exe -m scripts.hotkey_workflow_check
.\.venv\Scripts\python.exe -m scripts.package_check
```

The hotkey check requires an unlocked, available input desktop and may abort if
another window or user input prevents it from owning focus. Do not interpret an
aborted setup as a passing end-to-end workflow. The package check terminates only
the empty process it created; manually verify normal tray Exit with F5 above.

## G. Border, cursor overlay, dots, and performance

1. Inspect the zero side/bottom inset and 11 px top strip. Expect a 1 px top border
   only, rounded corners and the existing soft shadow. Screenshots have no white rim.
2. Use a 64 px eraser at top/bottom/left/right and all four corners. The full
   circle stays visible beyond the paper. Move across the controls: buttons remain
   above it and receive input. Leave the canvas: cursor overlay disappears.
3. Draw toward and past every edge/corner during a captured drag. Erase similarly,
   then enlarge the board. No new ink or cut should appear beyond the valid canvas
   at the time of the gesture. Existing offscreen artwork must remain intact.
4. Verify selection handles near edges stay visible, and selection/eraser overlays
   disappear during editing, help and minimize/close. Drag/resize the board and
   move it between DPI scales: overlays must remain aligned without taking focus.
5. Inspect placement over white, pale and dark applications. Dots are round,
   translucent white with a faint shadow and clear gaps, with no red or long dash.
   Move quickly, reverse direction, and pause. No trails or stationary flicker.
6. With 10, 100 and 500 mixed strokes/shapes/text (including partially erased
   objects), try both erasers, marquee, move one/many, resize and rotate. Check
   smoothness, continuous cuts, stable handles, absence of stale paint trails,
   single-step history and Escape restoration. Repeat with long freehand strokes.
7. Compare captured timings with `scripts.performance_check`. Record object count,
   selected count, Windows scaling, hardware and actual observed behaviour.
   Offscreen milliseconds do not certify native FPS or prolonged-use performance.

## H. Version 1.1 clipboard, images, palette and selection

1. Select a rotated/erased mixed group. Ctrl+C then Ctrl+V twice: independent IDs,
   original layout, +16/+32 px offsets, masks/colours/order retained. Paste on a
   second board: first paste preserves coordinates. Undo/redo paste/cut/duplicate
   exactly. Copy changes no document history.
2. Copy the group and paste into Paint, Word, OneNote and Discord where available.
   Expect an image without handles or guides. Check transparency and erased gaps.
   Record each application/version actually tried; do not send or publish anything.
3. Copy a Snipping Tool/Win+Shift+S capture and a browser PNG/JPEG, then Ctrl+V into
   the canvas. Drop PNG, JPG, JPEG and WEBP files. Small images keep size; a large
   screenshot fits inside 90% of the board, keeping ratio and source detail.
4. Move/resize/rotate an image and a mixed image/text/drawing selection. Resize
   always keeps ratio; rotations/masks/undo/redo remain exact. Duplicate/delete,
   undo, then zoom by resizing larger: no permanent progressive resampling blur.
5. C opens the compact popover. Try every number 1–7, custom colour and recents.
   Change selected strokes/shapes/text together; image pixels stay unchanged.
   With no selection, new drawing/text/shapes use the colour; other boards keep
   their own colour. Dismiss via choice, Escape and outside click. Check focus,
   popup placement near monitor edges and no taskbar entry.
6. Ctrl+A selects unlocked objects; ordinary/Shift arrows move 1/10 logical px.
   Repeated nudges undo together. Right-click and try every menu command. Front/
   back changes stacking without changing internal group order. Lock objects:
   clicks, marquees, handles and both erasers ignore them. Unlock directly and
   through Locked objects. Undo/redo every change.
7. Edit rotated/masked text. Type `C A V E 1234554321`; try arrows, Ctrl+A/C/X/V/Z,
   Delete and Backspace. All commands act in the editor; no palette or canvas
   edit occurs. Finish and confirm canvas shortcuts return.

## I. Version 1.1 snapping and tray

1. Tray → Snap & Guides: Smart Guides initially checked, Grid Snap unchecked.
   Move/resize near another object's edges/centres and board edges/centre. Expect
   subtle temporary guides and gentle alignment within 6 logical px.
2. Move farther away, finish, cancel and change tools: no guide remains. Copy
   selection while guides were used: no guide in the external clipboard image.
3. Enable Grid Snap, disable Smart Guides: movement/resizing follows a 10 px grid.
   Enable both: nearby smart alignment wins. Alt bypasses both immediately and
   does not change resize ratio or opposite anchor. Test rotated groups.
4. Toggle options from either board's tray session, close/reopen menu and restart.
   Checkmarks/settings persist globally; document undo stays unchanged. Restore
   your preferred options after testing.
5. Check New Whiteboard / Screenshot to Whiteboard / Whiteboards / shortcuts /
   About / Exit. About must show Version 1.2 with no large settings UI.

## J. Version 1.2 screenshot and release

1. From an ordinary app hold Ctrl+Alt+S, move, then release a known pattern.
   Expect exact captured pixels without preview dots, a board at the same region,
   locked screenshot and Draw ready. Annotate immediately. Unlock via context menu.
2. Cancel with Escape while holding or capture is pending. Test competing W/S holds. No stale
   overlay, held mouse capture or global Escape binding may remain. Verify W is
   also hold→move→release, including reverse corners and each release order.
3. Capture on each display, across boundaries, left/above-primary coordinates,
   100/125/150/175/200% scaling and mixed-DPI arrangements. Check output pixels,
   placement and proportional fitting. Try a region near minimum board dimensions.
4. Inspect F1 at all scaling levels; it must not resize the board. All new keys
   and eraser-5 toggle are listed. Check colour popup and context menu usability.
5. Inspect EXE Properties → Details: File/Product version 1.1. Extract the updated
   Desktop/MiniWhiteboard.zip into a clean folder and test on Windows without
   Python. Keep `_internal`; confirm launch, images, both hotkeys and tray exit.
6. Use a 4K screenshot plus 100 annotations and a 500-object board for prolonged
   move/resize/rotate/copy/erase use. Check responsiveness, memory over history and
   idle CPU for at least 60 seconds. Record hardware and distinguish measurements
   from subjective responsiveness.

## K. Screenshot caching and top-border refinement

1. Repeat the same 20 strokes, 20 shapes and 10 text objects on a blank board and
   a Ctrl+Alt+S board. Compare drawing, both erasers, marquee and movement/resize/
   rotation of 10 annotations. Repeat with 1080p/1440p/4K sources. Record source
   size, actual viewport, DPI, timings and hardware; note any visible stutter.
2. Draw a long curling stroke, erase across it rapidly, move/transform annotations,
   cancel and undo/redo. Check no stale trails or partial repaint artifacts; the
   screenshot should remain unchanged and locked. Cache builds must not increase
   during annotation work. Original PNG/decoded data must remain shared.
3. Resize the board and move it between DPI scales. Check cache dimensions equal
   logical viewport × DPR once, accurate clipping and sharpness, and no per-frame
   rebuild once size/DPI settles. Undo annotations should not rebuild the cache.
4. Unlock the screenshot, move/resize/rotate/copy it and check guides. Undo back to
   the original locked state. All source pixels and object identity must survive.
5. Inspect blank/screenshot boards against bright and dark desktops: one subtle
   top line, no grey or white frame at sides/bottom, rounded lower corners and
   unchanged soft shadow. Controls must remain visible with reserved input holes.
6. Exercise all 7 px edge/corner resize targets, correct cursors and the narrow
   top drag area. Try transform handles overlapping those zones: object handles
   win. Start drawing inside, then drag over the edge: the tool keeps its gesture.
7. Retest the extracted executable and desktop ZIP. Version stays 1.1; check the
   executable SHA-256 against the current release manifest to distinguish builds.

## V1.2 wrapped text acceptance

- [ ] Insert near the left/right edges; verify wrapping, the 8 px margin and
  24 px minimum, long URLs, Enter newlines and unchanged plain text.
- [ ] Commit/reopen: line breaks match. Tall content keeps the caret visible in
  the temporary editor, preserves every character and never resizes the board.
- [ ] Test 14/20/28 pt presets, rotated/masked text, proportional group scaling,
  copy/paste/duplicate, editor/document undo, and erasure on later wrapped lines.
- [ ] Board resize preserves committed width/content/history, including offscreen text.
- [ ] A V E 12345, arrows, clipboard, Delete/Backspace remain owned by the editor.
