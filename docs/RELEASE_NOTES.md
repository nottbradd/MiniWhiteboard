# Release notes

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

The reported loop was reproduced with native Windows mouse input before the fix.
Additional reproduced defects: stale editor signals closing a replacement session,
whitespace drafts entering history, existing cleared text staying invisible,
non-Text dismissal starting canvas work, rotation-handle activation during text
continuation, palette click replay, embedded menu lifetime/focus loss, and
Escape remaining latched after idle.

Local Windows 11 build 26200, Python 3.12.14 x64, Qt/PySide6 6.11.2:
**213 discovered, 211 passed, two Mac-only skips**. Twenty-two new regressions cover
overlay press/release, blank/whitespace history, existing deletion/undo, rapid and
double clicks, old callbacks, popup input, controls/other targets, transformed
panned editing and lifecycle. The Windows native suite passed 111 checks,
external-focus hold/release checks passed 49, and the dedicated native textbox audit passed 18 (including the exact
loop, whitespace, repeated cycles, menu focus, palette dismissal and deletion/undo).
The final executable passed 34 packaged checks, including native textbox
dismissal/continuation, cleared-text undo and palette dismissal. Its 174-file ZIP
passed CRC/every-file SHA-256 validation; all 17 dependency notice hashes passed.
String version is 1.2.1; numeric Windows/manifest version is 1.2.1.0.
The 28 screenshot workloads retained one cache build and no source painting or
decoding during annotation. Documentation/source-archive links, workflow lint,
compilation and dependency consistency passed. Hosted Mac/Windows CI and public
asset verification are pending.

**NOT RUN:** interactive Mac acceptance; macOS 14 and Intel execution; physical
mixed-DPI/multi-monitor arrangements; Windows 10/clean-machine deployment;
hand-operated IME and prolonged use. Mac remains a preview. Scripted native input
does not establish a full hand-operated acceptance pass.

[Testing guide](TESTING.md) · [Dependency notices](THIRD_PARTY_NOTICES.md)

## Earlier releases

- [V1.2](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.2):
  hold → move → release creation, repeat protection and naturally wrapped text.
  Windows release and Mac preview, with original verification and checksums.
- [V1.1](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.1):
  drawing, text, shapes, group transforms, erasers, clipboard/images, colours,
  guides, locking and screenshot annotation. Windows release and Mac preview.

Those release notes, tagged source and assets retain the historical results.
