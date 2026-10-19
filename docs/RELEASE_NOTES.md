# Mini Whiteboard V1.2

**Verified Windows release with a Mac preview.** Hold a shortcut, move the pointer,
and release to place a whiteboard or capture a screenshot region.

## Downloads and launch

- **Windows 10/11, x64:** `WinMiniWhiteboardV1.2.zip`. Extract it, open the
  Mini Whiteboard folder, and run Mini Whiteboard.exe. Keep `_internal` with it.
- **macOS 14+, PREVIEW:** `MacMiniWhiteboardV1.2-Preview.zip`. Extract on a Mac,
  move Mini Whiteboard.app to Applications and open it. Interactive Mac acceptance
  remains **NOT RUN**. The preview is ad-hoc signed and has not been notarized.

Both downloads include Python and Qt. Launch opens only a tray/menu-bar icon.
Windows is unsigned. If a trusted Mac download is blocked, use Apple's documented
[Open Anyway process](https://support.apple.com/en-au/102445).

## What changed

- **Windows Ctrl+Alt+W/S:** point at the first corner, hold, move, then release
  W/S **or any required modifier**. W makes a board; S captures a locked screenshot
  board with Draw active. No initial board, second press, click/drag or minimum hold.
- **Mac:** Control+Option+W/S, or the existing Command+Option+Shift+W/S preset,
  uses the same gesture. All four directions and negative desktop coordinates work.
- Repeated activations and competing shortcuts cannot confirm/restart a hold.
  Escape/menu cancellation and invalid selections clear the preview. Remaining
  held S/W cannot switch the newly focused board's tool. Minimum board size stays
  160 x 100 logical units; screenshots below 4 x 4 desktop units cancel.
- Text wraps naturally to a stored local width, with character fallback for URLs.
  Soft wraps leave plain text unchanged; Enter inserts a real newline. Editing,
  committed rendering and reopening match. Moves/transforms/window resizing keep
  the stored width. Tall text retains its content and follows the caret while editing.
- Wrapped text hit testing avoids a Mac Qt stall from expanding every glyph's
  tolerance outline. Shaped glyph outlines still provide painted/erasure geometry.
- Mac CI uses a free macos-15 runner. Deployment target, Info.plist and runtime
  minimum stay **14.0**. No paid runner, spending or permission-policy changes.
- F1/help, menus, current guides and the app-rendered placement GIF teach the new workflow.

## Held-key defect investigation

The preserved V1.1 executable and source reproduced a board plus a renewed outline
under a hold with repeated key-down injections. MOD_NOREPEAT was already present;
the application accepted extra activation events as two-press confirmation/restart
and retained undersized anchors. V1.2 adds explicit hold/release latching and shared
ownership, and never restarts an invalid selection. A permanently unrecoverable
outline was not reproduced in the controlled diagnostic; later valid input recovered.

## Actual verification

Release source: **08b3893be06755c59b9fcd56970b94f9a160419a**.

- Windows 11 build 26200, Python 3.12.14 x64: **191 discovered, 189 passed,
  2 Mac-only skips**; final build gate 5.648 s.
- **112 Windows native checks**, **45 external-focus real input checks**,
  **25 packaged executable checks**, plus **3 native Windows wrapped-editor tests**.
- Windows ZIP: **174 files**, all CRCs and file SHA-256 values match the verified
  distribution; **17 verified dependency notice files**; executable metadata 1.2.
- [Hosted Windows checks](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39256527582):
  191 discovered, 189 passed, 2 skips in 5.358 s; Python 3.12.10, Windows Server 2025.
- [Mac CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/39256527611):
  **191 passed** in 9.471 s, repeated before packaging in 8.825 s. Actual runner:
  **macOS 15.7.9 arm64**, Universal2 Python **3.13.15**, Qt/PySide6 **6.11.2**,
  PyInstaller **6.22.3**, PyObjC **12.2.2**.
- Mac **Universal2** bundle: **769 checks**, signatures/linkage/symlinks/notices;
  limited Cocoa startup 8 s, exit 0; **375 ZIP entries**, `ditto` extraction and
  full file/mode/symlink revalidation; **15 verified dependency notice files**.
- Both Actions artifact digests matched; the Mac-created inner ZIP was transferred
  unchanged. It was never extracted/recompressed as an app on Windows.
- Existing performance workloads, screenshot display cache invariants, workflow
  lint, source compilation, dependency consistency and documentation links checked.

**NOT RUN:** interactive Mac shortcuts/releases/Escape, focus/menu/Spaces/TCC,
real Retina/multi-monitor behaviour; macOS 14 or Intel execution; physical mixed-DPI,
Windows 10/clean-machine deployment, hand-operated IME/context menus and extended use.
Universal2 structural validation does not establish execution on Intel or macOS 14.

## SHA-256

| Package | Bytes | SHA-256 |
|---|---:|---|
| WinMiniWhiteboardV1.2.zip | 37,781,414 | `ced6df9c1fce90fa62bf24f7b0b1b1e1f079ddd61da1ae3082755ced97fc65d8` |
| MacMiniWhiteboardV1.2-Preview.zip | 56,424,554 | `35a0937ddf393b3d8c25305a4cca3258ba292cacb7cd0381d00be9881ffd2d40` |

`SHA256SUMS.txt` also covers the separate dependency-notice ZIP and the exact
Qt/PySide/PyObjC source archives attached below. Both app packages contain the
licenses and notice-hash manifests. Mini Whiteboard's own source is MIT licensed.

V1.1 and its assets remain intact. [Placement demo](https://raw.githubusercontent.com/nottbradd/MiniWhiteboard/v1.2/docs/media/placement.gif)

[Windows download](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2/WinMiniWhiteboardV1.2.zip)
| [Mac preview download](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2/MacMiniWhiteboardV1.2-Preview.zip)
| [Checksums](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2/SHA256SUMS.txt)
| [Dependency notices](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.2/MiniWhiteboardV1.2-DependencyNotices.zip)

## Historical V1.1 release notes

# Mini Whiteboard V1.1

**Stable Windows release with a Mac preview.** Place a small whiteboard anywhere
with two presses, then draw, type or annotate a screenshot.

## Downloads

| Download | Platform | Status |
|---|---|---|
| [WinMiniWhiteboardV1.1.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.1/WinMiniWhiteboardV1.1.zip) | Windows 10/11, 64-bit | Stable Windows release |
| [MacMiniWhiteboardV1.1-Preview.zip](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.1/MacMiniWhiteboardV1.1-Preview.zip) | macOS 14+ | Mac preview; interactive acceptance outstanding |

Both packages include Python and the libraries they need. Launching the app
shows a tray/menu-bar icon; it opens no board until you place one.

**Windows:** extract the ZIP, open the **Mini Whiteboard** folder and run
**Mini Whiteboard.exe**. Keep the executable and `_internal` folder together.
The Windows package is unsigned.

**Mac preview:** extract the ZIP on macOS and move **Mini Whiteboard.app** to
Applications. The app is ad-hoc signed. If macOS blocks a trusted copy, follow
[Apple's Open Anyway instructions](https://support.apple.com/en-au/102445).
Screen capture may request Screen Recording permission.

## Two presses to place a board

1. Point at one corner and press **Ctrl+Alt+W** on Windows or
   **Control+Option+W** on Mac. Release the keys.
2. Move to the opposite corner; the dotted outline shows the proposed board.
3. Press the same shortcut again to create it. Escape cancels placement.

![Two-press placement demo](https://raw.githubusercontent.com/nottbradd/MiniWhiteboard/v1.1/docs/media/placement.gif)

The demo uses the actual app controller and renderer on a controlled desktop.

## Included in V1.1

- Freehand drawing, seven shapes, multiline text and a temporary colour palette.
- Multiple selection with shared movement, scaling and rotation.
- Circular partial erasing and whole-stroke erasing.
- Smart Guides, optional Grid Snap, object locking and front/back ordering.
- Editable copy/cut/paste/duplicate, image paste and local image drops.
- A global screenshot shortcut: **Ctrl+Alt+S** on Windows or
  **Control+Option+S** on Mac, then drag a region to annotate.
- Independent boards and undo/redo. Text editors keep typing and editor undo
  separate from tool shortcuts.

Press **F1** in a board for all shortcuts. Boards last for the current session;
only preferences are saved. The application has no account, service or telemetry.

## Verification

| Check | Actual result |
|---|---|
| Windows automated suite | 160 tests passed; 2 Mac-only tests skipped (162 discovered) |
| Windows native GUI regressions | 110 checks passed |
| Real Windows keyboard/mouse workflow | 31 checks passed |
| Packaged Windows executable | 17 checks passed |
| Windows ZIP | 174 files; CRC and every file SHA-256 verified |
| Windows dependency notices | 17 files; all hashes verified |
| Mac automated suite | 162 tests passed |
| Mac bundle | Universal2; 769 checks passed |
| Mac packaged startup | 8-second check passed; normal exit |
| Mac ZIP and dependency notices | ditto extraction/metadata verified; 15 notice hashes verified |

[Windows CI](https://github.com/nottbradd/MiniWhiteboard/actions/runs/38108550793)
and [Mac build/verification](https://github.com/nottbradd/MiniWhiteboard/actions/runs/38108550854)
passed for the release source. The Mac runner was macOS 14.8.9 on arm64 with
Python 3.13.15; checking both architectures does not establish Intel execution.

Windows download SHA-256:
`99c5d6e8e7737dd0ef7c2d701004b30b69f66ff428c41524243a06e81c83ae69`.

Mac preview SHA-256:
`6e624db8d1214ae9229e600ecc1bf0b1cc605fab3fcfb867a39015cc4e28ec92`.

Interactive Mac hotkeys, external focus, menus, permissions, capture, Spaces and
physical display checks remain **NOT RUN**. Intel execution remains **NOT RUN**.
Physical mixed-DPI Windows arrangements and clean-machine deployment also remain
**NOT RUN**. See the [Mac checklist](https://github.com/nottbradd/MiniWhiteboard/blob/v1.1/docs/MACOS_CHECKLIST.md)
and [complete test report](https://github.com/nottbradd/MiniWhiteboard/blob/v1.1/docs/TEST_RESULTS.md).

## Checksums and dependency sources

`SHA256SUMS.txt` accompanies the downloadable packages and dependency source
archives. The packages contain license texts, exact dependency versions and
notice hashes. The Qt/PySide 6.11.2 source archives attached to this release are
for developers rebuilding or replacing those libraries; they are not required
to run the app. The Mac bridge's PyObjC core source archive is included too.
See the [dependency source guide](https://github.com/nottbradd/MiniWhiteboard/blob/v1.1/assets/licenses/SOURCES.md).

Mini Whiteboard's own code and assets are MIT licensed. Dependencies retain
their original licenses. [Feedback and bug reports](https://github.com/nottbradd/MiniWhiteboard/issues)
are welcome; include your operating system and steps to reproduce a problem.
