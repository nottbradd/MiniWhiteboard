# Release notes

## V1.3.1 review 03 — unpublished

The public [V1.3.1 release](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3.1)
is unchanged. This candidate requires visual approval before publication.

- Rounded boards and temporary surfaces retain their antialiased alpha fringe.
  Binary window/widget clipping previously cut that fringe into steps. The
  Windows backdrop is now explicitly input-transparent across processes.
- Minimise and delete use matching theme surfaces and centred vector icons,
  consistent 30 × 28 logical-pixel targets and safe minimum-board insets. Delete
  has restrained red hover/pressed feedback; tooltips and accessible names remain.
- Both hold → move → release previews use rounded glass material, a thin rim and
  a low tint. Native frost has a lightweight fallback; reduced transparency/high
  contrast use an unfilled two-tone perimeter. White remains the default board.
- Boundary artwork, cached screenshot display and the real temporary editor use
  alpha clipping. The saved capture excludes all preview material.

### Verification in progress

Baseline: 244 tests discovered, 242 passed and two Mac-only skips. Revised suite:
255 discovered, 253 passed and two Mac-only skips. New regressions cover corner
alpha at five scales, control bounds/fonts/feedback, preview material cleanup,
capture coordinates and real editor ownership.

Native Windows surface checks passed 177 assertions at each of 100%, 125%, 150%,
175% and 200% application scaling. These include original native captures and all
four enlarged corner crops, separately owned cross-process mouse delivery,
normal/minimum sizes, three backgrounds, both controls, all four preview/capture
directions and exact original screenshot pixels. The physical monitor remained
1920 × 1080 at 100%; physical mixed-DPI transitions remain **NOT RUN**.

Final general/package checks, comparable performance measurements and fresh
Windows/Mac candidate archives are still being verified. Interactive Mac
acceptance, macOS 14/Intel execution, Windows 10 and clean-machine deployment
remain **NOT RUN**. Mac remains a preview.

## V1.3.1

Published [21 October 2026](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3.1).
Stable Windows release with a clearly labelled Mac preview download.

- Glass uses one rounded native backdrop and one continuous light-catching edge.
  The smaller rectangular frosted core and parallel perimeter lines are removed.
  Matching menus have roomier rows, clearer selected/focused states and bold
  headings. White retains its established default appearance.
- F1 help groups shortcuts into two columns on larger desktops, reflows to one
  scrolling column on smaller desktops and shows the selected H binding.
- A restrained 140 ms edge light catch accompanies Glass creation, restore,
  theme changes and temporary surfaces. Repeated triggers keep the original
  deadline. Hide/close stops it; reduced motion suppresses it. Document content
  never moves, scales or fades as part of presentation.
- Removed OCR actions, workers/backends, engine/language payload and exclusive
  dependencies. Original V1.3 assets, attribution and dependency sources remain.
- Saved Windows Hide All choices remain Ctrl+Alt+H and Ctrl+Alt+Shift+H. Failed
  H registration preserves W/S. Restore All preserves the foreground application.
- Text/editor fonts, wrapping, masks, transforms, clipboard output, history,
  screenshot caching and hold → move → release placement remain unchanged.
- Queued placement activation now preserves a textbox opened immediately after
  creation. Help text is laid out when requested, avoiding that work during placement.

Mac remains a preview. Glass uses supported compositor
frost, static shading and an edge highlight; it has no optical refraction,
desktop-capture loop or native Apple Liquid Glass dependency.

### Material correction

The previous Windows host could retain stale dark-background material when a
background update and popup entry occurred together. Focus, HWND identity and
host order were unchanged; waiting over a second did not repair the displayed
pixels, while closing the popup did. A successful native-effect flag did not
establish visible correctness. The precise internal DWM cache decision is not
exposed by its API.

Windows now uses a host backdrop brush and an explicit rounded compositor clip.
The visual fills the board's bounds. One physical pixel of antialias coverage
sits under its painted rim, with matching corner centres. There is no inset
frosted rectangle, desktop readback, activation workaround or polling timer.
Unsupported systems, reduced transparency and high contrast retain solid fallbacks.

### Verification

Built from [`8d0f10a`](https://github.com/nottbradd/MiniWhiteboard/commit/8d0f10a69e9a239a12fdbf80bf561cc8690b8773)
on `codex/v1.3.1-liquid-glass`.
[Windows CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39570524574) and
[Mac CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39570529848) passed
for that exact source. The release tag includes subsequent documentation changes;
application code, build inputs and the approved package bytes are unchanged.

| Check | Actual result |
|---|---|
| Baseline | 237 discovered; Windows 235 passed plus two Mac-only skips |
| Final source suite | 244 discovered; Windows 242 passed plus two skips; Mac all 244 passed twice; project watchdog |
| Windows native | 112 general, 61 hotkey/focus, 22 textbox, 15 appearance/geometry and 49 material/state/motion checks |
| Final executable | 37 package checks and 17 supplementary native Glass/H/menu/help checks |
| Material | Independent owned background process; focused/unfocused comparisons, all popups, live background changes, same-turn update/popup, recreation and fallbacks passed |
| Native clipping | 244 outside-corner pixel probes at each of normal/minimum sizes showed no backdrop leakage; 244 input probes passed through; all four diagonal grips worked |
| Presentation | Native enabled frames use an injected test policy; OS motion remained disabled. Reduced motion suppressed the effect. Strict 180 ms wall-clock condition assertions, interruption and loaded-thread checks passed |
| Resources | After warmup, 30 further source menu/theme/hide cycles: GDI/User 47/60 → 47/59. Twenty frozen hide/restore cycles: 47/57 → 47/57. Hosts released, owned shadows hidden, timers stopped and normal shutdown passed |
| Windows package | 174 runtime files, 153 frozen modules; all ZIP CRC/file SHA-256 and 17 notice hashes verified; 1.3.1 strings, 1.3.1.0 numeric/manifest metadata |
| Mac builder | macOS 15.7.9 arm64, universal2 Python 3.13.15, Qt/PySide6 6.11.2, PyInstaller 6.22.3 and PyObjC 12.2.2 |
| Mac bundle/archive | Universal2, 14.0 minimum; 770 architecture/linkage/signature/symlink/module/notice checks before and after ditto extraction; 15 notices, 375 ZIP entries and metadata round-trip passed |
| Mac startup/transfer | Eight-second Cocoa launch and normal exit passed; finished Mac ZIP transferred unchanged and checked against the Mac hash |
| Retained content | Three font/layout/glyph/clipboard fixtures, including 24,000 wrapped Unicode characters, remained byte-identical; native ink stayed opaque |
| Other checks | Dependencies, compilation, workflow lint, 32 local documentation links and OCR absence checks passed |

Windows measurements and captures used build 26200 x64, Python 3.12.14,
Qt/PySide6 6.11.2 and one 1920 × 1080 display at 100%. Both saved H choices
remain available. Ctrl+Alt+H is occupied by another app on this PC; tests selected,
persisted/reloaded and natively exercised the shipped Ctrl+Alt+Shift+H alternative.
The source and final executable captures were personally inspected. Interactive
Mac acceptance is not established by CI or bundle validation.

### Performance against the previous reviewed candidate

Both preserved and revised packages ran on the same Windows machine. Startup
uses five alternating warm launches per package; these small samples vary by run.

| Measurement | Previous candidate | V1.3.1 |
|---|---:|---:|
| Median launch to tray | 399.5 ms | 411.3 ms |
| Tray working set / private memory | 56.59 / 26.66 MiB | 56.71 / 26.93 MiB |
| CPU time in separate 60-second tray-idle samples | 0.0 s | 0.0 s |
| Visible Glass blank-board working set / private memory | 79.85 / 35.59 MiB | 80.15 / 35.07 MiB |
| Native dot-to-observed-pixel median, Glass blank | 38.93 ms | 39.71 ms |
| Native dot-to-observed-pixel median, Glass screenshot | 37.39 ms | 38.09 ms |
| White processing median of medians / worst p95 | 1.89 / 5.01 ms | 1.87 / 5.41 ms |
| Glass processing median of medians / worst p95 | 1.87 / 5.29 ms | 1.58 / 4.91 ms |
| Wrapped-text hit path median / p95 | 0.049 / 0.108 ms | 0.048 / 0.089 ms |

Native latency uses 16 dots per case and includes input delivery, compositor
and GDI observation. Control runs observed every dot in the first capture;
capture-only medians were 21–26 ms. Repeated Glass blank medians were 44.00 /
44.89 ms, with p95 51.00 / 48.35 ms. The screenshot repeat was 44.31 / 44.27 ms.
These measurements do not isolate display latency or establish a universal speedup.

Source measurements use 28 workloads with 120 events each, 20 strokes, 20 shapes,
10 text objects and blank/1080p/1440p/4K backgrounds. The preserved source was
repeated in the same dependency environment. Initial White/Glass medians were
1.82 / 2.14 ms; the table uses the matched repeat. Individual timings varied:
White 1080p marquee median was 0.71 → 0.93 ms. Every screenshot cache built once;
source-image paint/decode work stayed zero. The long-text geometry and pixel
fixtures were unchanged. Detailed samples remain in local verification evidence.

### Downloads

The approved Windows archive and the Mac-created preview archive are published
unchanged. [Checksums, dependency notices and exact dependency sources](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3.1)
accompany the downloads.

| Package | Bytes | SHA-256 |
|---|---:|---|
| [WinMiniWhiteboardV1.3.1.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.1/WinMiniWhiteboardV1.3.1.zip) | 37,822,209 | `9cbebd8f864430637e659c47a76227c988ef9d3c75fb6e5e285dc7d55c466b60` |
| [MacMiniWhiteboardV1.3.1-Preview.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.1/MacMiniWhiteboardV1.3.1-Preview.zip) | 56,452,627 | `caefb39d524e3102685209fcdf7c016ffaa4f35e28c5d74fa48c2972df33c392` |

Windows is unsigned. Mac is ad-hoc signed and not notarized.

**NOT RUN:** interactive Mac appearance/shortcuts/focus, permission/capture flows,
Spaces, Retina and physical multi-monitor acceptance; macOS 14 and Intel execution;
Windows 10, clean-machine deployment, physical mixed-DPI arrangements and extended
hand-operated IME/RTL/handle ergonomics. Mac native animation/performance were not
measured.


## V1.3

Published [21 October 2026](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3).

- Every outside textbox click now finishes editing and deselects it. The same
  press/release/double-click cannot start another editor or tool action. A separate
  click can create/edit text. Blank drafts preserve history/redo; clearing existing
  text remains one deletion. Keyboard finish retains useful selection/presets.
- Added global saved **White / Glass** appearance. Windows 11 22621+ uses native
  DWM Acrylic behind the artwork; Mac uses NSVisualEffectView. Unsupported effects,
  reduced transparency and high contrast use a solid readable fallback. Artwork,
  original image pixels, masks, geometry and clipboard output remain unchanged.
- Brief 140 ms top-edge emphasis and feedback fades respect reduced motion.
  Hide is immediate. No animated backgrounds, idle repaint or desktop-capture loop.
- Added offline **Extract Text…** for existing images, including locked screenshots.
  Review/correct, then explicitly Copy or Insert as wrapped text. Insertion is one
  undo action. Windows bundles Tesseract 5.5.3 and English data; Mac uses Vision.
  English is the guaranteed language. OCR is fallible and never automatically
  changes clipboard or document. Original-resolution input is rectified from display
  transforms, masked/clipped, composited on white and normalized for dark backgrounds.
- Added **Ctrl+Alt+H** / **Control+Option+H** Hide All / Restore All. Only the visible
  recorded batch returns; manually minimized, individually restored/deleted and new
  boards follow the rules in README. Restore preserves the foreground application.
  Conflict warnings are nonblocking and retain working W/S bindings.
- OCR has one process plus one queued request across the app, a 20-second timeout,
  16-million-pixel/32-MiB input and 100,000-character output limits. Hide/close,
  source changes and cancellation invalidate results and stop owned worker processes.

### Release verification

Release source: [`60e8f15`](https://github.com/nottbradd/MiniWhiteboard/commit/60e8f1534aef4870d3694482cc9f4d6032d1ed59).
[Windows CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39551606504) and
[Mac CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39551606590) passed for that source.

| Check | Actual result |
|---|---|
| Windows automated suite | 236 discovered; 234 passed, two Mac-only symlink skips |
| Mac automated suite | All 236 passed, repeated before packaging |
| Windows desktop checks | 112 general checks, 20 native text checks, 60 hotkey/focus checks with the H conflict/test-chord limitation below; 9 native Glass/OCR/resource checks |
| Final Windows executable | 35 packaged checks plus exact clean/dark/transparent OCR; restricted PATH, invalid external data path, Unicode/space paths and Python socket audit guard |
| Windows ZIP | 219 runtime files, every CRC/file SHA-256 checked; 35 notice hashes; strings 1.3, numeric/manifest 1.3.0.0 |
| Mac runner | macOS 15.7.9 arm64; Python 3.13.15, Qt/PySide6 6.11.2, PyInstaller 6.22.3, PyObjC 12.2.2 |
| Mac bundle | Universal2, 14.0 minimum; 829 architecture/linkage/signature/symlink/notice checks before packaging and after ditto extraction; 32 notice hashes |
| Mac startup and OCR | Limited startup passed; source and frozen Vision matched all three clean/dark/transparent fixtures exactly |
| Mac ZIP | 402 entries; CRC, metadata roundtrip and complete extracted-app revalidation passed; transferred unchanged from Mac |
| Other checks | Source compilation, dependencies, workflow lint and local documentation links passed |

Windows measurements used Windows 11 build 26200 x64, Python 3.12.14 and
Qt/PySide6 6.11.2. Compared with the preserved V1.2.1 package on the same machine:

| Measurement | V1.2.1 | V1.3 |
|---|---:|---:|
| Median warm startup to tray, five samples | 275.6 ms | 282.9 ms |
| Median working set | 53.2 MiB | 56.8 MiB |
| Median private memory | 25.3 MiB | 27.6 MiB |
| CPU time in a 60-second idle sample | 0.0 s | 0.0 s |
| Median of 28 event-latency medians | 1.303 ms | 1.252 ms |
| Worst event p95 across those cases | 4.586 ms | 2.974 ms |
| Windows ZIP size | 37,783,789 bytes | 44,755,989 bytes |

The annotation fixture uses 20 strokes, 20 shapes and 10 text objects on blank,
1080p, 1440p and 4K backgrounds (120 samples per case). Each screenshot cache
built once; source decode/image-paint counters stayed zero during annotation.
These are processing timings, not display FPS. A 24,400-character wrapped textbox
had a 0.046 ms median / 0.063 ms p95 hit path. Six real OCR jobs left GDI/user counts,
history and clipboard unchanged (971 ms median including review-window lifecycle).
A noisy 24.9 MB 4K input cancelled cleanly; maximum GUI heartbeat gap was 77.7 ms.
Thirty native theme/hide cycles returned to unchanged GDI/user counts.

### Downloads

| Package | Bytes | SHA-256 |
|---|---:|---|
| [WinMiniWhiteboardV1.3.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3/WinMiniWhiteboardV1.3.zip) | 44,755,989 | `15e870dca619f25f198b5cde4b3dcaa44be0b369da1d4918bf03c4b137a226ff` |
| [MacMiniWhiteboardV1.3-Preview.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3/MacMiniWhiteboardV1.3-Preview.zip) | 56,918,634 | `aa559058e7d1ed68b2239a57f7975c5202a59bb0ddf1e05dbfae057b27c5d9c9` |

[Checksums](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3/SHA256SUMS.txt), dependency notices and exact dependency sources accompany the [V1.3 release](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3). The Mac preview is ad-hoc signed, not notarized; Windows is unsigned.

### Limitations and checks not run

On this machine another application already owns Ctrl+Alt+H (Windows error 1409).
The actual default conflict path preserves W/S. Native H dispatch, held repeats,
release orders and external-focus restore passed using a temporary
Ctrl+Alt+Shift+H test binding; the shipped Windows binding remains Ctrl+Alt+H.
The original failed default-binding test is retained in local verification records.

Mac remains a preview. Interactive Glass, native shortcuts/focus, Screen Recording
permissions, Spaces, Retina and physical multi-monitor behaviour remain **NOT RUN**.
Execution on macOS 14 and Intel hardware, Windows 10, clean-machine disconnected
operation and physical mixed-DPI testing are also **NOT RUN**. Restricted-path OCR
checks with a Python network audit guard are separate from clean-machine testing.

## V1.2.1

Windows bug-fix release with a clearly labelled macOS 14+ preview.

### Changes

- Clicking outside a blank or whitespace-only textbox dismisses it without
  creating a replacement or starting a canvas action. A separate next click
  immediately creates text. Discarding a draft preserves undo/redo.
- Clearing existing text removes that object in one undoable operation.
  Undo restores content, width, transforms, masks, colour and stacking.
- Old editor callbacks cannot finish a newer session. Double-click dismissal
  follows the same ownership rule. Meaningful Text-mode continuation remains
  available with one click and cannot activate a transform handle.
- Transformed editor context menus retain their editing session while open;
  deferred focus callbacks recognize menus embedded in the proxy scene, and
  outside menu dismissal restores editor focus.
- Dismissing the colour palette no longer replays a click into a canvas tool.
- Escape detection resets for a fresh global creation hold after idle.
- Repository documentation is consolidated into usage, contribution, release,
  testing and dependency guides. Historical releases remain available below.

### Verification

Release source: [e1d976c5c2ea389fe6b339f15d88442bd34815fe](https://github.com/nottbradd/MiniWhiteboard/commit/e1d976c5c2ea389fe6b339f15d88442bd34815fe).
Published [20 October 2026](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.2.1).

The loop was reproduced with native Windows input: the outside press finished
the editor and then reached the active Text tool. The patch gives that press one
owner. Additional reproduced fixes cover whitespace/history, invisible cleared
text, stale sessions, unintended drawing/transforms, embedded menu lifetime/focus,
palette click replay and Escape rearming after idle.

| Check | Actual result |
|---|---|
| Windows build gate | 213 discovered: 211 passed, two Mac-only skips, 6.343 s; Windows 11 build 26200, Python 3.12.14 x64 |
| Windows native regressions | 111 GUI/controller checks; 49 external-focus W/S checks; 18 native textbox checks; eight supplementary assertions for clicks in an owned separate application |
| Final Windows executable | 34 packaged checks, including native blank dismissal, continued typing, deletion/undo/redo and palette dismissal |
| Windows ZIP/notices | 174 files, every CRC/file SHA-256 verified; 17 notice hashes; strings 1.2.1, numeric/manifest 1.2.1.0 |
| [Windows CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39388714120) | 211 passed, two skips, 6.771 s; Windows Server 2025, Python 3.12.10 x64 |
| [Mac CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39388714069) | 213 passed, 13.697 s; repeated before build, 8.579 s |
| Mac builder | macOS 15.7.9 arm64; Universal2 Python 3.13.15; Qt/PySide6 6.11.2, PyInstaller 6.22.3, PyObjC 12.2.2 |
| Mac bundle/startup | Universal2, 769 checks; eight-second Cocoa startup/normal exit 0; deployment/runtime/plist minimum 14.0 |
| Mac ZIP/notices | 375 entries; ditto extraction plus full file/mode/symlink/bundle revalidation; 15 notice hashes; Mac-created ZIP transferred unchanged |
| Other checks | 28 screenshot workloads retain cache invariants; workflow lint, compilation, dependencies and 31 documentation/source-archive links passed |
| Publication | Nine uploaded asset digests match; all public asset links and tagged demo return HTTP 200; both app downloads and checksums rehashed anonymously |

Twenty-two new regressions cover visible overlay press/release, blank/whitespace
history, exact existing-text deletion/undo, rapid/double clicks, stale callbacks,
popup input, controls/other targets, transformed/panned editing and lifecycle.
Native checks used one 1920×1080 display at 100%. Screenshot timings measure
GUI-thread work; they do not certify display FPS.

**NOT RUN:** interactive Mac shortcuts/Escape, focus/menu/Spaces, Screen Recording
permission/capture and Retina/multi-monitor acceptance; macOS 14 and Intel
execution; physical mixed-DPI Windows arrangements, Windows 10/clean deployment,
hand-operated IME/RTL/emoji, handle/editor ergonomics and prolonged use.
Mac remains a preview. Universal2 inspection does not establish Intel execution.

### Downloads and SHA-256

| Package | Bytes | SHA-256 |
|---|---:|---|
| [WinMiniWhiteboardV1.2.1.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2.1/WinMiniWhiteboardV1.2.1.zip) | 37,783,789 | `7e876fe8786596fe9d95072ce2111bb88a4f96330e9750541ac4316ebbce5f55` |
| [MacMiniWhiteboardV1.2.1-Preview.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2.1/MacMiniWhiteboardV1.2.1-Preview.zip) | 56,427,689 | `54b8fe6f2db52bfc1938679fbdc26539a454888f7963d5d43d165c63ab9bc1cb` |

[Checksums](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2.1/SHA256SUMS.txt)
cover both apps, the separate notice ZIP and five exact dependency source archives.
Both apps retain license texts and source/rebuild information. Earlier assets and
repository visibility are unchanged.

[Testing guide](TESTING.md) · [Dependency notices](THIRD_PARTY_NOTICES.md)

## Earlier releases

- [V1.2](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.2):
  hold → move → release creation, repeat protection and naturally wrapped text.
  Windows release and Mac preview, with original verification and checksums.
- [V1.1](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.1):
  drawing, text, shapes, group transforms, erasers, clipboard/images, colours,
  guides, locking and screenshot annotation. Windows release and Mac preview.

Those release notes, tagged source and assets retain the historical results.
