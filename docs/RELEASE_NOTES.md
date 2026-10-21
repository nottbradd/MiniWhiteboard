# Release notes

## V1.3.1 candidate — unpublished

- Revised optional Glass with neutral translucency, generous rounded corners,
  a clear optical edge, thin light-catching rim, static highlights and soft shadow.
  Palette, app-owned menus, help and feedback share the presentation. White keeps
  its top border. Native Mac menus and system dialogs retain their OS behaviour.
- Bold interface headings, medium action labels and regular support text.
  Document/editor fonts, presets, text widths, masks and geometry are unchanged.
  The shortcut reference scrolls on smaller logical desktops while keeping its
  readable font size. Theme-change emphasis has a 140 ms wall-clock deadline;
  showing, restoring or refreshing a native view does not restart it.
- Glass diagonal resize targets follow the visible corner arcs. White retains
  its existing edge targets; transform handles and the small controls keep priority.
- Removed OCR entirely: actions, review UI, workers/backends, Tesseract/English
  payload, exclusive Vision/CoreML requirements, fixtures and collection steps.
  The original V1.3 release, evidence and dependency sources remain available.
- Added saved Windows Hide All choices: Ctrl+Alt+H or Ctrl+Alt+Shift+H. A failed
  binding retains W/S; changing/retrying H leaves those working registrations.
  Existing physical-key suppression and visibility-batch/focus rules remain.

This candidate has not been tagged or published. Public download links remain
V1.3 pending final visual approval. Mac remains a preview. Glass approximates the
approved concept with supported frost, shading and edges; it has no optical
refraction, desktop-capture loop or native Apple Liquid Glass dependency.

### Candidate verification

Application source: [`d1872ad`](https://github.com/nottbradd/MiniWhiteboard/commit/d1872ad3b90bbfb0af6c6cbd0f0f70c829d36976),
on `codex/v1.3.1-liquid-glass`.
[Windows CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39563047451) and
[Mac CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39563051307) passed.
The later receipt records documentation and package hashes; the application and
package tests use this source revision.

| Check | Actual result |
|---|---|
| Baseline before edits | 236 discovered; 234 passed, two Mac-only symlink skips |
| Final Windows suite | 237 discovered; 235 passed, two Mac-only skips; project watchdog runner |
| Final Mac suite | All 237 passed, repeated by the build script |
| Coverage changes | 11 OCR tests removed; 12 retained-feature/package regressions added |
| Windows desktop | 112 general checks, 61 native hotkey/focus checks, 22 textbox checks, 15 Glass/material/resource checks |
| Final executable | 36 package checks; 14 supplementary native Glass/H checks, including diagonal resizing and the saved shipped alternative |
| Windows package | 174 runtime files; every ZIP CRC/file SHA-256 and 17 notice hashes verified; strings 1.3.1, numeric/manifest 1.3.1.0 |
| Mac builder | macOS 15.7.9 arm64, universal2 Python 3.13.15, Qt/PySide6 6.11.2, PyInstaller 6.22.3, PyObjC 12.2.2 |
| Mac bundle | Universal2, 14.0 minimum; 770 architecture/linkage/signature/symlink/module/notice checks before and after ditto extraction; 15 notice hashes |
| Mac startup/archive | Eight-second Cocoa startup and normal exit passed; 375 ZIP entries, CRC and complete metadata round-trip passed; finished ZIP transferred unchanged |
| Removal | Fresh dependency environment; OCR modules, engines, data and exclusive bridges absent from both packages; frozen module archives inspected |
| Other checks | Dependencies, compilation, workflow lint and local documentation links passed |

Windows measurements used Windows 11 build 26200 x64, Python 3.12.14 and
Qt/PySide6 6.11.2, on one 1920 × 1080 display at 100%. Native captures were
personally inspected on light, dark and busy owned backgrounds, with matching
White content, menus, palette, help and a screenshot board. The package was also
drawn into and hidden/restored through actual native input.

Ctrl+Alt+H remains occupied by another application on this PC (error 1409).
That default conflict retained W/S. The actual tray choice persisted/reloaded
Ctrl+Alt+Shift+H, registered it and dispatched Hide/Restore without taking focus.
Thirty source theme/hide cycles and twenty packaged hide/restore cycles released
their material hosts without increasing GDI/user resources. All 244 sampled
transparent corner points passed input through to the owned background.

Document/editor fonts stayed regular. Three pre/post layout fixtures, including
24,000 characters of wrapped Unicode, retained identical font data, bounds, glyph
geometry and clipboard pixel hashes. The long-text hit path measured a 0.048 ms
median / 0.095 ms p95. Theme changes retained object identity, masks, original
image bytes and history. Native artwork kept exact opaque ink colours.

The package text check observes both ink and the antialiased editor outline.
It remains valid when the caret blinks off, and blank dismissal must remove both.
No timing assertion or unrelated regression was disabled to pass verification.

### Performance compared with V1.3

Both preserved and candidate executables ran on the same machine. Startup and
memory below use five alternating warm launches per package; timings vary by run.

| Measurement | V1.3 | V1.3.1 candidate |
|---|---:|---:|
| Median launch to tray | 394.5 ms | 344.4 ms |
| Median working set | 56.90 MiB | 56.41 MiB |
| Median private memory | 27.91 MiB | 26.59 MiB |
| CPU time in a 60-second tray-idle sample | 0.0 s | 0.0 s |
| Native dot-to-visible median, blank board | 18.03 ms | 18.14 ms |
| Native dot-to-visible median, screenshot board | 18.09 ms | 18.12 ms |
| Windows ZIP | 44,755,989 bytes | 37,813,666 bytes |
| Mac preview ZIP | 56,918,634 bytes | 56,451,944 bytes |

Native dot measurements use 16 samples per case and include compositor/GDI
observation cost. They are not paint-only timings or display FPS. Windows ZIP
size falls by 6,942,323 bytes (15.5%); the Mac ZIP falls by 466,690 bytes (0.8%).

The 28 source workloads cover blank, 1080p, 1440p and 4K backgrounds with 20
strokes, 20 shapes and 10 text objects, 120 events per case. Every screenshot
cache built once; source-image paint/decode work stayed zero. Initial processing
timings varied, so V1.3 was repeated in the same clean environment and both
versions were profiled. Repeated median-of-medians was 1.44 ms for V1.3 and
1.65 ms for the candidate; worst p95 was 4.55 / 4.49 ms. Glass measured 1.65 ms
and 4.19 ms. Dirty painting and cached screenshot paths remain in place.

### Unpublished packages

Staging: `build/candidates/v1.3.1/`. These are candidate archives; no V1.3.1
release/tag or public download replacement has been made.

| Package | Bytes | SHA-256 |
|---|---:|---|
| `WinMiniWhiteboardV1.3.1.zip` | 37,813,666 | `41d7dce50db38b140e1e2f0b7a6d194f0fd934e5f75f2366634338f55720ea57` |
| `MacMiniWhiteboardV1.3.1-Preview.zip` | 56,451,944 | `94c6f34891dc48638bf9fd01202a944572cd86c3bae2bf1e33ebaea5b30f501e` |

Windows is unsigned. Mac is ad-hoc signed and not notarized.

**NOT RUN:** interactive Mac Glass/shortcuts/focus, permissions/capture, Spaces,
Retina and physical multi-monitor acceptance; macOS 14 and Intel execution;
Windows 10, clean-machine deployment, physical mixed-DPI arrangements and extended
hand-operated IME/RTL/handle ergonomics. Native Windows motion effects were off
in the system policy; bounded motion was exercised by portable tests on both
builders. Mac performance and interactive animation were not measured. Visual
approval remains required before publication.


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
