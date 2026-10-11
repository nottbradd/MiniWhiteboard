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
| Windows automated suite | 160 tests passed |
| Windows native GUI regressions | 110 checks passed |
| Real Windows keyboard/mouse workflow | 31 checks passed |
| Packaged Windows executable | 17 checks passed |
| Windows ZIP | 172 files; CRC and every file SHA-256 verified |
| Windows dependency notices | 15 files; all hashes verified |
| Fresh Mac preview build | Verification pending before publication |

Windows download SHA-256:
`d0de836c042366ff6802bc758990b473744d55b7964ac367b3c32ce25cc385c7`.

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
to run the app. See the [dependency source guide](https://github.com/nottbradd/MiniWhiteboard/blob/v1.1/assets/licenses/SOURCES.md).

Mini Whiteboard's own code and assets are MIT licensed. Dependencies retain
their original licenses. [Feedback and bug reports](https://github.com/nottbradd/MiniWhiteboard/issues)
are welcome; include your operating system and steps to reproduce a problem.
