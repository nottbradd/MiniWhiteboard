# Testing and troubleshooting

Use the packaged release for acceptance checks. Record the app version/source
revision, OS, architecture, display scales and whether input was native or
Qt-delivered. Mark each unperformed check **NOT RUN**. Current results belong in
[release notes](RELEASE_NOTES.md); build/setup commands are in
[CONTRIBUTING](../CONTRIBUTING.md).

## Automated and native checks

The GUI suite uses Qt offscreen and fake platform services.
`scripts.run_tests` runs the complete suite with a 300-second diagnostic watchdog.
It does not establish native focus, global shortcuts, permissions or display behaviour.

Windows desktop checks deliberately operate owned windows, the cursor, clipboard
and capture. Exit an existing Mini Whiteboard instance before running them:

```powershell
.\.venv\Scripts\python.exe -m scripts.native_smoke
.\.venv\Scripts\python.exe -m scripts.hotkey_workflow_check
.\.venv\Scripts\python.exe -m scripts.text_input_check
.\.venv\Scripts\python.exe -m scripts.appearance_check
.\.venv\Scripts\python.exe -m scripts.material_state_check
.\.venv\Scripts\python.exe -m scripts.surface_input_check --output verification/v132-review02/native-100
.\.venv\Scripts\python.exe -m scripts.package_check
```

The hotkey and text checks use native Windows input. The general native smoke
also uses Qt-directed events. Tests abort when ownership/focus cannot be established;
an aborted check is not a pass. They restore the cursor/foreground and close only
owned test processes. Reports are under ignored `.test-artifacts/` and `verification/`.

`surface_input_check` saves original native captures, all four corner crops,
nearest-neighbour 6× enlargements and control close-ups. It confirms delivery of
real mouse presses to a separate owned process while the board remains exposed,
and compares captured screenshot pixels with a clean reference in all four
directions. `QT_SCALE_FACTOR=1.25`, `1.5`, `1.75` and `2` exercise fractional
rendering in separate test processes. These are simulated application scales;
record physical display settings and monitor transitions separately.

On a Mac, run deliberately in an interactive session:

```bash
.venv-macos/bin/python -m scripts.macos_escape_probe
.venv-macos/bin/python -m scripts.macos_native_smoke
.venv-macos/bin/python -m scripts.macos_native_smoke --capture
```

The Escape probe needs another application focused and Accessibility already off.
A pass requires an observed external-focus Escape event, with permission state
and PID recorded. The native smoke uses owned Qt events; physical global input
still needs the checks below. Capture can request Screen Recording permission.

## Installation and login startup

- Use a controlled per-user installation folder and preserve any original
  Mini Whiteboard settings, shortcuts and startup values before testing.
- Check fresh setup without elevation, Start menu/search access, shortcut launch,
  default-off desktop shortcut, optional desktop shortcut and paths containing
  spaces and non-ASCII characters. Keep the full private runtime; do not rely on
  Python installed elsewhere. Record clean-machine execution separately.
- Repeat setup and upgrade a controlled predecessor. Confirm one uninstall entry,
  updated shortcuts, retained preferences and unchanged startup choice. Attempt
  setup and uninstall with a board open: both must refuse; the app/work must live.
- Enable/disable Open at login through the real packaged menu. Check the real
  executable path, quiet launch, manual/automatic overlap, persistence, permission
  errors and external OS disables. Reads/restarts must never reenroll the app.
  Unknown Windows approval records require Startup apps; Mac pending approval
  requires Login Items. **Turn off Open at login** must remove the owned
  registration in either state and leave unrelated startup entries untouched.
- Uninstall and verify files/shortcuts/owned startup cleanup. Restore temporary OS
  values and retained test preferences. Do not terminate another user's app.
- Check fresh GUI defaults without command-line task overrides. Extract the
  portable ZIP into a permanent Unicode folder outside the checkout, verify its
  file hashes, launch with Python absent from PATH, and test its login option.
- Automatic launch during an actual Windows sign-in is **NOT RUN (not tested)**
  for V1.3.2. A controlled launch of the registered command does not establish it.
  To test later, use a disposable Windows session or separate system for two
  actual sign-ins: enabled must produce one quiet tray instance with a working
  creation shortcut; disabled must leave the app closed after the next sign-in.
  Record the package hash, environment and observed results. Do not sign out,
  reboot or disrupt an active user desktop.
- Inspect executable, setup, shortcut and About icons at native 16/20/24/32/48 px
  and larger sizes on light/dark backgrounds. Mac: inspect the bundle ICNS and
  actual menu-bar template appearance, including Retina, where hardware permits.

## Interaction acceptance

### Creation and cancellation

- From an ordinary foreground application, hold W's global shortcut, move and
  release. No initial board/focus change; exactly one focused board on release.
  Repeat all four directions, trigger-first and each modifier-first release.
- Hold with repeats, press competing W/S, cancel with held Escape, then release.
  No restart or remaining W/S typing/tool switch. After idle, cancel another hold
  with Escape again. Menu cancel, display changes and exit remove previews/timers.
- Test undersized/stationary release, then a fresh valid gesture immediately.
  Board minimum is 160 × 100 logical pixels; capture minimum is 4 × 4 desktop units.
- Both rounded glass previews remain legible over bright/dark backgrounds and
  let desktop clicks through. Reduced transparency/high contrast use an unfilled
  two-tone perimeter. Final paper matches the selection; its shadow may extend outside.
- Mac: test both shortcut presets and conflict/retry without overwriting system
  bindings. Check bare external-focus Escape separately; menu cancellation is
  available if delivery is unreliable.

### Text and popup input

- T → click → leave blank → click outside → release/move → allow queued focus
  events to settle. No editor/replacement/object/selection/history remains.
  Repeat with spaces/tabs/newlines, rapid clicks and double-clicks. The next
  separate click immediately starts one editor; redo survives a discarded draft.
- Clear existing text to whitespace, finish and undo/redo. Exact text, width,
  transforms, masks, colour and order return. Meaningful whitespace is preserved.
- Dismiss nonempty text with an outside click: it commits, deselects and leaves
  no editor or transform frame. A separate next click creates/edits one textbox.
  Repeat a full native double-click retargeted from the old overlay to the canvas;
  no drawing/shape/erase/transform action may start.
- Check Escape and Ctrl+Enter / Command+Return, repeated finish callbacks, outside
  controls, another board and a disposable other app. Each clicked target acts once.
- Right-click inside the real editor. Copy/paste and dismiss its menu without
  losing the edit or starting canvas work. Repeat canvas menus and the colour
  popup. Check popup dismissal near board edges and after a tool change.
- Type **Today is day 123**, **A V E 12345 C D S T**, and **1234554321**.
  Check selection/caret, arrows, clipboard, Backspace/Delete, editor undo/redo and
  document undo after commit. Tool keys must not intercept typing.
- Test wrapped/tall text, long URLs, explicit newlines, 14/20/28 pt presets,
  rotated/scaled/masked text and hit coordinates after the editor pans to the caret.
  Reopen without rewrapping; board resize preserves text width and offscreen content.
- Resize, minimize/restore, close and quit while editing. No orphan overlay,
  stale callback, mouse grab or document preview should remain.

### Tools, history and windows

- Check all drawing widths and shapes, creation constraints and line/arrow endpoints.
  A/V topmost selection, Shift membership and four-direction full-containment
  marquees use complete surviving bounds, including artwork outside the viewport.
- Move a mixed group; test all anchored resize handles, proportional text/images,
  non-mirroring and Shift 15° rotation. Escape restores the original snapshot.
- Sweep both erasers rapidly over strokes, outlines, arrowheads, text and images.
  Cuts follow transforms; new drawing crosses old cuts. Whole-stroke mode removes
  every surviving fragment of one original freehand gesture, ignoring shapes/text.
  Check 5/5/5/1/5/4 and independent per-board mode/size memory.
- Copy/cut/paste/duplicate mixed masked selections; check independent IDs,
  stacking, offsets, locking/unlocking, ordering, colours and undo/redo.
  Try external image apps, browser images/screenshots and local file drops.
- Smart Guides/Grid Snap, Alt/Option bypass and preferences work independently
  of document history. Every committed drag is one action; empty edits add none.
- Handles win over window resize targets. Test all eight invisible window
  resize directions and the narrow top drag strip. Controls stay usable above
  passive tool visuals; shadows/rounded cutouts pass input to the desktop.
- Minimize retains contents/history; restore returns the same board and focus.
  Closing the last board keeps the tray/menu alive; Exit/Quit clears all resources.
  Launch twice: one owner. Observe idle CPU for at least 60 seconds.

### Hide All and appearance

- H with mixed visible/minimized boards records only the visible set. Check held
  repeats, each release order, no-board/all-minimized cases, individual restore
  followed by minimize, deletion and a new board during the hidden batch.
- Restore with another owned app focused: its foreground and keyboard focus must
  stay unchanged, including after queued callbacks settle. Check every board's
  geometry, selection, content/history and normal clicking afterward.
- Hide active text, previews, transforms, help, palettes, menus and animations.
  No late popup, shadow, native host, mouse grab or activation timer may remain.
- White is the first-launch default. Persist Glass, switch existing/new boards and
  compare source PNG bytes, document state, masks and clipboard artwork output.
- Verify actual Windows frost with an owned changing bright/dark/busy background;
  successful API calls or offscreen renders alone do not prove blur. Check native
  failure/unsupported-system fallback, reduced transparency/motion and high contrast.
- Use `scripts.appearance_check` for actual Windows White/Glass captures on owned
  light/dark/busy backgrounds, menus, palette, help, screenshot opacity, rounded
  input regions and repeated resource cleanup. Inspect the captures personally;
  successful DWM calls alone cannot establish appearance.
- Test both persisted Windows H choices. When the default conflicts, run
  `scripts.hotkey_workflow_check --hide-shortcut shift`. It chooses the real menu
  option, verifies its saved value and dispatches the shipped binding with native
  input. Test settings are isolated from the user's preferences. Do not take over
  a binding owned by another application.
- Build candidates in a fresh dependency environment. Package checks reject OCR
  engines/data/bridges and inspect frozen modules. Retain all required Qt/Python
  and shared Mac bridge notices. Historical V1.3 packages remain unchanged.
- Compare UI heading/action/support weights and document metrics separately.
  Verify regular text, wrapping, Unicode, transformed editing, masks and exact
  clipboard pixels after a theme switch. Inspect small boards, rounded controls,
  popup navigation and outside-click dismissal.
- The material-state check uses a separate owned background process. Verify native
  foreground identity and that the board remains exposed before comparing pixels.
  Compare focused/unfocused states, all three popups, changes behind open menus,
  same-turn background change/popup entry, handle recreation and native clipping
  at normal/minimum sizes. Retain failure captures rather than treating an enabled
  effect flag as proof of visible material.
- Record actual native motion frames with policy conditions. The check injects
  motion only into its own process, tests enabled/reduced paths and saves frames
  before PNG encoding. Global OS settings stay unchanged. Verify creation,
  nonactivating restore and popup light catches finish within the bounded period;
  repeated triggers, theme changes and hide/close must leave no active timers.
- Help uses two columns on larger logical desktops and one scrolling column on
  smaller ones. Check every section, the selected H binding, keyboard/mouse menu
  navigation, visible check/focus states and unclipped text at larger DPI/font sizes.
- Compare idle CPU/timers, startup, memory, package size, screenshot counters and
  median/p95 paint/input processing on the same fixture/environment. These timings
  measure processing work, not display FPS. Repeat theme/hide cycles and check
  process/widget/native resources return to a stable count.

## Platform and hardware acceptance

- Windows: actual 100/125/150/175/200% scaling, negative X/Y monitors, mixed-DPI
  seams, moving/resizing across displays and disconnect during creation/capture.
  Test Windows 10 and clean deployment without Python as a standard user.
- Mac: real arm64 and Intel execution, macOS 14 execution, menu-bar/accessory
  lifetime, ordinary-app floating without focus theft, Spaces, Mission Control,
  Stage Manager and full-screen limitations. Do not infer these from bundle slices.
- Mac Screen Recording: fresh prompt, deny/grant/revoke/restart, System Settings
  route and frozen-app identity. No microphone/Accessibility permission for capture.
  Validate asymmetric crops, orientation, colours and absence of preview/cursor.
- Retina/non-Retina, mixed scales, cross-display crops and desktop gaps.
  Cache dimensions equal viewport × DPR once; original screenshot pixels survive.
- Inspect IME, RTL, emoji, context-menu ergonomics, transformed editor focus,
  handle usability and long sessions with large images/history.
- Test downloaded/quarantined packages using normal OS security flows.
  Windows is unsigned; the Mac preview is ad-hoc signed and not notarized.

Interactive Mac acceptance, macOS 14 execution and Intel execution remain
**NOT RUN** unless a release explicitly supplies new observed evidence.
Physical mixed-DPI and clean-machine Windows acceptance are also outstanding.

## Performance diagnostics

```powershell
.\.venv\Scripts\python.exe -m scripts.performance_check --frames 16 --output verification/performance.json
.\.venv\Scripts\python.exe -m scripts.screenshot_performance --frames 60 --repeats 2 --output verification/screenshot-performance.json
.\.venv\Scripts\python.exe -m scripts.raster_cache_check
.\.venv\Scripts\python.exe -m scripts.v11_performance
```

Mac can run the screenshot workload with `--native`. Use its venv interpreter.
Fixtures cover 10/100/500 mixed objects and blank/1080p/1440p/4K screenshots.
Record input-event median/p95, paint area, selected count and cache counters.
These timings measure GUI-thread work, not display FPS or a universal speedup.
Annotation work should build one screenshot cache and perform no source decode
or source-background painting per sample. Preserve original image identity/history.

## Troubleshooting

- **No board at launch:** find the tray/menu icon and use the global shortcut.
  Hidden Windows tray icons can conceal it.
- **Shortcut unavailable:** close another owner or choose Retry global shortcut.
  On Mac try the alternate preset. Check normal tool keys only with canvas focus.
- **Capture denied/empty:** check Screen Recording permission on Mac and relaunch
  if requested. Protected/secure desktop content may be unavailable.
- **Windows app missing libraries:** extract and retain the whole runtime folder,
  including `_internal`; do not run an isolated executable.
- **Mac startup blocked:** use [Apple's supported Open Anyway process](https://support.apple.com/en-au/102445)
  only for a trusted copy. Do not disable Gatekeeper globally.
- **Mac archive changed after transfer:** obtain the already-created inner ZIP
  from Actions or Releases. Transfer it byte-for-byte; do not extract/repack on Windows.
- **A native check fails:** keep its report and include OS, version, display setup
  and reproducible steps in a bug report. Remove private content before sharing.

The one Mac workflow uses the standard macos-15 runner, minimum target 14.0,
Universal2 intent and conditional architecture fallback. Actions artifacts contain
environment, tests, bundle, limited startup and ditto round-trip reports.
Packaging validates dependency notices independently on each builder.
