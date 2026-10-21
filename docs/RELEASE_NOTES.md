# Release notes

## V1.3

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

### Verification and limitations

Windows source checks: 235 tests discovered, 233 passed and two Mac-only symlink
checks skipped. The final Windows executable passed 34 packaged checks and exact OCR for all
three clean/dark/transparent fixtures with restricted PATH and the socket audit guard.
Actual Windows captures verify native background-dependent frost
and unchanged opaque ink. Thirty theme/hide cycles returned to the same GDI/user
resource counts. Real OCR matches clean printed multiline, punctuation, number,
URL, dark and transparent fixtures exactly; scaled/rotated/masked fixtures and
service cancellation/limits are covered. Difficult layouts and handwriting can
still produce recognition errors.

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
