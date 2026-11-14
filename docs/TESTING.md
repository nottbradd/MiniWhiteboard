# Testing and troubleshooting

## V1.3.6 floating tools and drawing

Run `python -m unittest tests.test_floating_tools tests.test_live_stroke` for
settings, placement, pointer state, lifecycle, text completion and exact live/
committed geometry and raster regressions. `scripts.floating_tools_check`
captures implemented widgets; `--native` runs only on the isolated Windows builder.
Qt scale overrides check layout and logical target sizes, not physical displays.
Check White with and without its selected background on both themes. Native
captures must show the current presented state; a successful widget grab alone
does not prove that the desktop has presented that frame. Retain stale frames
and capture-readiness timing alongside corrected captures.

Real-pen checklist: enable Show floating tools, tap each tool, hold for options,
drag the grip, change boards, finish text then draw, and repeat at
100/125/150/175/200%. Check barrel-button/right-click, touch, movement cancellation
and duplicate input. Check above/below/inside placement at taskbars and negative
origins, Hide/Restore, external focus, screenshots and closure. **NOT RUN** without
suitable hardware.

`scripts/drawing_performance.py --source CHECKOUT --rapid 20 --output REPORT.json`
uses the same synthetic workload against either checkout. Run sequentially in
fresh processes; add `--toolbar` for V1.3.6. Reports contain samples, mean, p50,
p95, maxima, CPU time, working set, paint and release cost. Input is an unpaced
backlog with a paint opportunity every four samples (240/60 Hz equivalent), not
hardware latency or FPS. Profiling adds overhead: compare unprofiled runs.
Use `--contexts boundary` for strokes crossing the canvas edge; clipping costs
must be reported separately. Rapid cycles exercise both circular and whole-stroke
erasing. Earlier reports using whole-stroke erasing alone retain that scope.

`scripts.packaged_drawing_check` requires an isolated GitHub-hosted Windows
desktop and an explicit executable SHA-256. It injects native mouse input and
probes the GUI thread with bounded WM_NULL messages. Report the measured input
duration and probe samples; the nominal 240 Hz request is not proof of a 240 Hz
device or screen. Run it through the Defender diagnostic workflow so protection,
pre/post scans and blocked runs are retained alongside package identity.

Use 16.7 ms as a diagnostic 60 Hz processing budget and 100 ms as a noticeable
stall threshold, not a functional assertion or guarantee. Record longer stalls;
never reduce input or skip endpoints to obtain a pass. Native frozen observations
and Windows package/Defender acceptance remain separate. V1.3.4 Microsoft analysis
does not cover a new executable. Record installer, ZIP and EXE hashes per run.
The frozen review-02 source is `b4b9d27`. Review-01 remains unchanged. Split
`scripts.early_release_matrix --mode early-default-full` using `--case-start`
and `--case-count` when needed; the 15 original cases each retain their full
preceding workload. Checkpoint the selected indices before execution and keep
per-case progress, input traces and window state even when the watchdog stops
a child. Retry only an unresolved group, never substitute an earlier EXE pass.

Use the packaged release for acceptance checks. Record the app version/source
revision, OS, architecture, display scales and whether input was native or
Qt-delivered. Mark each unperformed check **NOT RUN**. Current results belong in
[release notes](RELEASE_NOTES.md); build/setup commands are in
[CONTRIBUTING](../CONTRIBUTING.md).

## Security reports and release acceptance

V1.3.4 HotkeyPatch has an unresolved report of a Defender quarantine and Setup
blocking during Preparing to Install. **Suspicious Behaviour** is the reported
category, not a threat name. Preserve the original download and record the exact
threat name, detection time/time zone, action, affected resource, Defender versions
and original installer/ZIP SHA-256 when available. Do not restore a quarantined
file to gather its hash. Redact personal paths and device identifiers before
sharing diagnostics. See [Microsoft's Defender event reference](https://learn.microsoft.com/en-us/defender-endpoint/troubleshoot-microsoft-defender-antivirus).

A school or work device can separately restrict unapproved applications through
[App Control or AppLocker](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/appcontrol-and-applocker-overview).
Ask its administrator to identify the relevant event and approval policy. The MIT
license, a publisher signature, Defender classification and organizational approval
are different things. A policy restriction does not establish the cause of a
Defender quarantine. Do not disable protection, create exclusions or bypass the
organization's controls.

The manual [Defender investigation workflow](../.github/workflows/windows-defender.yml)
targets the fixed, published V1.3.4 HotkeyPatch hashes on a disposable hosted Windows
VM. It records the initial runner configuration, removes the runner's broad
exclusions, enables protection, updates intelligence and requires observed active
real-time, behaviour, downloaded-file, archive and cloud protection before fetching
samples. It preserves Defender events and histories on failure. This script refuses
to operate on a local desktop or self-hosted runner. Its programmatic downloads and
Expand-Archive extraction are explicitly **not browser/Explorer acceptance**.

The Server workflow uploads a scan/environment checkpoint before runtime testing,
then rechecks the same files' hashes and scans them before execution. Subprocesses
write progress, stdout/stderr and deadline results to separate operation folders.
Setup has a 60-second limit, uninstall 45 seconds and each native suite 180 seconds;
outer step budgets leave time for final evidence collection and upload. A missing
artifact or timed-out operation is incomplete evidence, never a successful check.
An unresponsive runner can still prevent its final upload; the earlier checkpoint
does not prove anything about operations performed after it.
Branch pushes run the portable diagnostics; manual dispatch can select the
installer, portable package or both. The portable run compares fresh capture and
capture after one zero-size board cancellation separately from the full sequence.

The separate [Windows client workflow](../.github/workflows/windows-client.yml)
uses the hosted Windows 11 ARM image and x64 emulation. It verifies active Defender
before entering the primary package URL in visible Edge, and uses Explorer's
Extract all dialog for the portable ZIP. It records screenshots, UI state and
origin-marker presence without removing markers or bypassing warnings. Reference
payloads obtained programmatically are labelled separately. Desktop readiness,
download, extraction and execution are distinct stages: reaching one does not
accept the others. Retained attempts include desktop/focus failures and a run
that returned no evidence artifact. This environment also cannot establish native
x64, school-policy or clean-PC behaviour.

The [V1.3.6 client workflow](../.github/workflows/windows-v136-client.yml) first
downloads and extracts a harmless text fixture, then uploads that evidence before
requesting application bytes. It downloads the frozen Actions artifact through
visible Edge and extracts the exact installer and ZIP through Explorer. This
unpublished-candidate route is distinct from a published release URL. Hashes and
inherited download-origin markers identify each file; no marker is added or removed.
Browser completion requires the normal **Open file** action, not only bytes on
disk. Normal Shell launches and visible setup/uninstall wizards retain warning
captures. The ordinary **Open File – Security Warning** may be accepted with
**Run** only after identifying the exact requested file/hash, leaving **Always
ask before opening this file** checked. This is recorded separately from
SmartScreen, Defender or policy blocks, which are not bypassed. Glass captures use the exact frozen EXE over
owned light and busy backgrounds. Record hosted ARM64 emulation and Test Mode
limitations separately from native x64 retail-client acceptance. Normal WSL setup
is permitted only in the owned disposable VM. Record the initial desktop before
one bounded install/update attempt; the official Microsoft MSI is a fallback for
the image stub that rejects its own install command. Verify its pinned hash and
Microsoft signature. Do not install a Linux distribution or reboot. Save setup
logs before the harmless preflight, which must complete browser download,
Explorer extraction and a three-second stable-foreground observation. A stale
WSL prompt may be closed once; recurrence or another obstruction stops the check.
No security setting or download-origin marker is weakened to make a check pass.

Source graphics diagnostics run for full, comparison and visual checks. Focused
editing, gesture and installer checks reuse applicable graphics evidence and keep
the protected browser/Explorer preflight. A source diagnostic failure is not an
execution result for the frozen package.

The `comparison` subset captures published V1.3.4 HotkeyPatch, V1.3.6 tools off,
V1.3.6 tools on, and White controls over the same two owned backgrounds. Record
all backdrop HWNDs, stacking, styles, visibility and lifetime. Source-only API
results and independent D3D11 capability probes are separate from frozen-binary
evidence; a successful capability probe does not identify WUC's internal device.
The `upgrade` subset exercises the normal wizard against the exact HotkeyPatch
predecessor, including cancellation, pre-copy failure and mid-copy rollback.
Wait for the owned tray window to respond before injecting a first shortcut;
record startup time separately. Background captures require their expected painted
pixels as well as a responsive owned window. Keep translated text entirely inside
the pixel measurement region. Capture-reference patterns must cover both tested
regions and settle before the timed input sequence begins; retain exact pixel
equality and the original release schedules.
`client_uia_check` queries frozen Qt controls in a separate process without a Qt
GUI apartment, and retains the actual accessibility tree and errors. Match the
observed accessible role (checkable Qt tool buttons are CheckBox controls). When
switching boards, wait for the replacement toolbar before querying its state.
Clipboard export readiness requires both the image and editable MIME formats
within the existing export deadline; record format, owner and sequence changes.
These waits are outside the measured creation gesture. An Inno
running-app prompt's Cancel button exits the attempted setup without closing the
application. Source fallback injection is labelled separately from an environment
automatically selecting fallback and from acceptance of the unchanged executable.

The final client step opens Windows Security and records its Protection history
page read-only. Retain the page capture, Defender events and API history together;
no threat action, protection setting or history is changed. A missing UI result
is incomplete evidence even when the API history is empty.

`packaged_shortcut_check --trace-transition` records only its tagged test input,
foreground changes and the owned application's window/thread state. It retains
the original assertion timing and observes a late preview separately, including
release and result geometry. These observations cannot convert a failed assertion
into a pass. Source callback profiling is a separate diagnostic and does not
execute or accept the published EXE. Keep the failure until the cause is understood;
do not increase a timeout solely to obtain a passing run. On the emulated client,
the opt-in `--functional-deadline-ms 2000` mode separates functional completion
from the original 120 ms preview/150 ms result observations. Earlier traces showed
late working previews and correct final geometry; each new case retains whether
the original timing was met and its observed latency. Foreground loss, duplicate
results, wrong geometry or missed completion still fail. Fixed-schedule early
release tests remain separate and do not wait for a preview before releasing.

A replacement release requires an evidence-supported resolution and tests of the
exact frozen candidate files. Record Windows/Defender versions, active/passive
mode, cloud settings, exclusions and download-origin information. Test the genuine
browser-download path and normal extraction where available, then both fresh
installation and portable execution, an upgrade with retained settings/startup,
running-app refusal and uninstall. Exercise normal board/capture, hold/release,
text/wrapping, selection, undo/redo, Hide/Restore, controls and tray/settings routes
with protection enabled. Check file survival and hashes, Protection History and
events through a recorded observation period. A zero scan exit code or a clean
scan alone is insufficient; record SmartScreen, Smart App Control and publisher
warnings separately. Earlier source/CI results do not accept a different EXE.

If Microsoft analysis is needed, use its
[software-developer submission](https://www.microsoft.com/en-us/wdsi/filesubmission)
with only the public samples and sanitized diagnostics. Record the actual
submission ID and determination. Pending review is not a clean determination.
Release notes must identify incomplete checks and the exact Microsoft response
without turning either into a pass or a definitive classification. V1.3.6's
official Windows release uses the unchanged review-02 files, with the documented
limitations explicitly accepted for that release. Microsoft's completed written
analyst response satisfies its authorised review policy; the portal's file-level
determination remained Pending on 14 November 2026. See the
[release notes](RELEASE_NOTES.md#v136--windows-release--mac-universal2-preview--14-november-2026).
Actual Windows sign-in retains its existing **NOT RUN (not tested)** waiver.

## Automated and native checks

The GUI suite uses Qt offscreen and fake platform services.
`scripts.run_tests` runs the complete suite with a 300-second diagnostic watchdog.
It does not establish native focus, global shortcuts, permissions or display behaviour.

Windows desktop checks deliberately operate owned windows, the cursor, clipboard
and capture. Exit an existing Mini Whiteboard instance before running them:

```powershell
.\.venv\Scripts\python.exe -m scripts.native_smoke
.\.venv\Scripts\python.exe -m scripts.hotkey_workflow_check
.\.venv\Scripts\python.exe -m scripts.creation_shortcut_check
.\.venv\Scripts\python.exe -m scripts.selection_pointer_check --output verification/v134-review01/selection-100
.\.venv\Scripts\python.exe -m scripts.text_input_check
.\.venv\Scripts\python.exe -m scripts.appearance_check
.\.venv\Scripts\python.exe -m scripts.material_state_check
.\.venv\Scripts\python.exe -m scripts.surface_input_check --output verification/v134-review01/native-100
.\.venv\Scripts\python.exe -m scripts.package_check
.\.venv\Scripts\python.exe -m scripts.packaged_shortcut_check
```

The hotkey and text checks use native Windows input. The general native smoke
also uses Qt-directed events. Tests abort when ownership/focus cannot be established;
an aborted check is not a pass. They restore the cursor/foreground and close only
owned test processes. Reports are under ignored `.test-artifacts/` and `verification/`.

The creation matrix exercises both sides of Win/Alt/Shift and each required key released first,
held repeats, external text/menu focus, Escape and an owned conflict/retry.
It records existing third-party conflicts as **NOT RUN**; `--require-both` makes
either conflict fail that check. The general native smoke can continue unrelated
checks with `--allow-shortcut-conflict`, explicitly recording the limitation.
Neither option changes the application's bindings or takes a shortcut from its owner.
CI requires both native creation shortcuts. Release acceptance also requires
successful native W and Q gestures in the final packaged Windows executable;
registration probes or controller-directed previews do not satisfy that check.
The packaged matrix also observes foreground changes during gestures, checks all
four placement directions, rapid consecutive creation and external text/menu
isolation, and saves actual W/Q preview captures. A capture-service failure is
injected only in the source native check; the next real Q gesture must recover.
The pointer regression uses native mouse input and checks actual selected IDs,
moved transforms and undo against adjacent, reversed-order and rotated notes.

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
  and is not a candidate or release gate under the existing waiver. A controlled
  launch of the registered command does not establish it.
  To test later, use a disposable Windows session or separate system for two
  actual sign-ins: enabled must produce one quiet tray instance with a working
  creation shortcut; disabled must leave the app closed after the next sign-in.
  Record the package hash, environment and observed results. Do not sign out,
  reboot or disrupt an active user desktop.
- Inspect executable, setup, shortcut and About icons at native 16/20/24/32/48 px
  and larger sizes on light/dark backgrounds. Mac: inspect the bundle ICNS and
  actual menu-bar template appearance, including Retina, where hardware permits.

## Interaction acceptance

### Hotkey settings and recovery

- Open tray/menu bar → Settings → Hotkeys with a creation conflict present.
  Check every status against native registration. A conflict on default Windows
  Ctrl+Win+Shift+W must be reported accurately; an unavailable shortcut is not a
  successful positive gesture result.
- Record and manually select different modifiers and trigger keys for each action.
  Recording must not create, capture or hide. Check modifier-only/unsupported
  input, duplicate chords, failed OS registration, rollback and its status.
- Cancel, Escape and closing the dialog restore normal registration. Reset Defaults
  only edits pending values. Apply must save only a fully registered configuration.
  Verify restart/upgrade persistence and migration of old Hide All/Mac choices.
- Test the explicit Windows compatibility preset and independent custom keys.
  Run `scripts.packaged_shortcut_check --profile custom` and
  `scripts.packaged_shortcut_check --profile default --available-defaults` on the
  final EXE. The script reports unavailable defaults separately. Native scripts
  temporarily save test preferences and restore the user's values afterward.
- Windows reserves Ctrl+Esc and Ctrl+Shift+Esc. A reserved draining subset must
  not abort placement. If the full held Escape chord is unavailable, verify the
  warning and tray-menu cancellation without attempting to override the OS.

### Creation and cancellation

- The Windows V1.3.4 hotkey patch defaults to **Ctrl+Win+Shift+W/Q**; Mac shortcuts and Windows Hide All choices
  are unchanged. Test left/right modifiers, all release orders, Start/menu focus
  after completion/cancellation and ordinary modifier use outside a gesture.
- From an ordinary foreground application, hold the configured creation shortcut, move and
  release. No initial board/focus change; exactly one focused board on release.
  Repeat all four directions, trigger-first and each modifier-first release.
- Hold with repeats, press competing creation/capture chords, cancel with held Escape, then release.
  No restart or remaining trigger-key typing/tool switch. After idle, cancel another hold
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

- Place short text in wide adjacent wrapping boxes in both creation orders.
  Click visible glyphs and drag: the intended note must be selected/moved, even
  inside another selection's broad frame. Repeat multiline, rotated/masked text,
  actual overlapping ink, locked backgrounds, board moves/resizes and DPR changes.
- Check dark/light/busy screenshot boards under both appearance defaults: no
  white top strip, gutters or control cut-outs. Check normal/minimum sizes,
  compact feedback wrapping, hit padding and high-contrast/reduced-transparency
  fallbacks. Original PNG bytes and clean clipboard pixels must remain exact.
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
- **Shortcut unavailable:** open tray/menu-bar **Settings → Hotkeys** and record or
  manually select an available chord. The Windows compatibility preset and Mac
  alternate preset are explicit choices. Check normal tool keys only with canvas focus.
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
