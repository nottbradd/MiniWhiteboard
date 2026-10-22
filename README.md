# Mini Whiteboard

[![Windows tests](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/windows-tests.yml/badge.svg)](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/windows-tests.yml)
[![macOS build](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/macos-build.yml/badge.svg)](https://github.com/nottbradd/MiniWhiteboard/actions/workflows/macos-build.yml)

Place a small desktop whiteboard by holding a shortcut, moving the pointer and
releasing. Draw, type, paste images and annotate screenshots without a permanent
toolbar. Launch opens only a Windows tray icon or a macOS menu-bar item.

**V1.3.2 is available.** It adds a recommended Windows installer, updated
branding and optional Open at login. Windows is the stable release; Mac remains
a **Universal2 Preview**.

![Mini Whiteboard icon](assets/branding/app-128.png)

## Download V1.3.2

| Download | Platform | Installation |
|---|---|---|
| [Windows installer — recommended](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.2/MiniWhiteboard-1.3.2-Setup.exe) | Windows 10/11, x64 | Run Setup. Installs for your account, adds a Start menu shortcut and offers a desktop shortcut. |
| [Windows portable ZIP](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.2/WinMiniWhiteboardV1.3.2.zip) | Windows 10/11, x64 | Extract the ZIP, open **Mini Whiteboard**, run **Mini Whiteboard.exe**. Keep the entire folder together. |
| [Mac Universal2 Preview ZIP](https://github.com/nottbradd/MiniWhiteboard/releases/download/v1.3.2/MacMiniWhiteboardV1.3.2-Preview.zip) | macOS 14+; arm64 and x86_64 bundle | Extract on a Mac, move **Mini Whiteboard.app** to Applications and open it. Interactive Mac acceptance is **NOT RUN**. |

Python and Qt are included. [Release notes and verification](docs/RELEASE_NOTES.md)
describe this release. [Checksums and dependency sources](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.3.2)
accompany the downloads. [Earlier releases](https://github.com/nottbradd/MiniWhiteboard/releases)
remain available.

Windows is unsigned. The Mac preview is ad-hoc signed and has not been notarized.
For a trusted Mac download blocked by Gatekeeper, follow
[Apple's Open Anyway instructions](https://support.apple.com/en-au/102445).
Interactive Mac acceptance, execution on macOS 14 and Intel hardware remain
**NOT RUN**. Universal2 bundle checks and limited startup do not establish those results.

### Installation and Open at login

The **Windows installer is recommended**. It installs for your
account without an administrator prompt, adds Mini Whiteboard to Start/Search,
and offers a desktop shortcut. The portable ZIP remains available: extract it
and keep its entire folder together. Both launch quietly into the tray.

On Mac, extract the **Universal2 Preview ZIP** on a Mac and move Mini Whiteboard.app
to Applications. Interactive Mac acceptance is **NOT RUN**.

Choose **Open at login** in the tray/menu-bar menu to opt in. It is off by
default. The app reads the OS registration each time the menu opens. If Windows
Startup apps or macOS Login Items blocks it, follow the shown settings action;
the app does not silently enable it again. Choose **Turn off Open at login** to
remove the app's registration while startup is disabled or approval is pending.
Keep portable copies in a permanent folder before enabling startup.
Development and temporary copies cannot register.
Startup registration and controlled command launches were tested. Automatic
launch during an actual Windows sign-in is **NOT RUN (not tested)**.

To update or uninstall Windows, first choose Exit from the tray menu after
keeping any work you need. Setup and uninstall refuse to proceed while the app
is running. Updates retain preferences and startup choice. Uninstall removes its
own shortcuts and login registration; preferences remain for a later reinstall.

![Hold, move and release to place a whiteboard](docs/media/placement.gif)

The demo uses the app controller and renderer on a controlled desktop.

<details>
<summary>A board with drawing, shapes and text</summary>

![Mini Whiteboard with drawing, shapes and text](docs/media/whiteboard.png)

</details>

## Place a board or screenshot

1. Point at the first corner and hold **Ctrl+Alt+W** on Windows or
   **Control+Option+W** on Mac.
2. Keep holding and move to the opposite corner. A temporary outline previews the rectangle.
3. Release W **or any required modifier** to create a focused board.

Use **S** in the same global shortcut to capture a region into a new board
with a locked screenshot background, ready to annotate. Mac's **Global shortcuts**
menu also offers **Command+Option+Shift+W/S/H** when the default conflicts.

Both gestures support four directions and negative desktop coordinates. A board
below 160 × 100 logical pixels, or a capture below 4 × 4 desktop units, cancels.
Escape or the tray/menu cancellation clears a preview. Held repeats cannot
create more boards. Screen capture may request Screen Recording permission on
Mac; a denied or failed capture creates no board.

## Tools and shortcuts

Tools work only in the focused canvas. New boards start in Draw mode.
Press **F1** for the compact shortcut reference.

| Key | Action |
|---|---|
| D, then 1–5 | Draw at 2, 4, 6, 9 or 14 logical px |
| T, then 1–3 | Text at 14, 20 or 28 pt; apply to selected text or the next textbox |
| S, then 1–7 | Rectangle, rounded rectangle, ellipse, line, arrow, triangle, diamond |
| A or V | Select and transform; Shift-click toggles, Shift-marquee adds fully enclosed objects |
| E, then 1–4 | Partial circular eraser at 8, 16, 32 or 64 logical px |
| E, then 5 | Toggle whole-stroke erasing; toggling off returns to circular 16 px |
| C | Temporary colour palette; 1–7 choose presets |
| Arrows / Shift+arrows | Move selection by 1 / 10 logical px |
| Delete / Backspace | Delete selected editable objects |
| Escape | Cancel a gesture or clear selection |

| Action | Windows | Mac |
|---|---|---|
| Copy / cut / paste / duplicate | Ctrl+C / X / V / D | Command+C / X / V / D |
| Select all | Ctrl+A | Command+A |
| Undo / redo | Ctrl+Z / Ctrl+Shift+Z or Ctrl+Y | Command+Z / Command+Shift+Z |
| Bypass snapping | Alt | Option |
| Finish text | Ctrl+Enter or Escape | Command+Return or Escape |

Text wraps to a stored width. Enter adds a newline; the temporary editor follows
the caret for tall content. Resizing the board preserves objects and text width.
While editing, letters, numbers, clipboard commands, arrows, deletion and undo
belong exclusively to the text editor.

Clicking outside **any** active textbox finishes editing and deselects it. That
click cannot start another editor, transform or drawing action. A separate next
click can create or edit text. Meaningful text keeps its whitespace; blank new
drafts disappear without history. Clearing existing text is one undoable deletion.

Selection has shared move, resize and rotation controls. Corners preserve ratio;
edges scale one axis unless Shift is held or the group contains text or images.
Shift snaps rotation to 15°. Shape creation retains square/circle constraints.
Circular erasure cuts every editable object under its swept brush. Whole-stroke
erasure removes an original freehand gesture, including its surviving fragments.
Masks follow objects through transforms and edits.

Right-click for ordering and lock/unlock commands. Paste images or drop local
PNG, JPEG and WEBP files. **Snap & Guides** controls Smart Guides and Grid Snap.
The minus button hides a board while preserving contents and history; the red
× deletes that board. The tray/menu restores boards. Closing the last board
leaves the utility running; choose **Exit/Quit Mini Whiteboard** to end the session.

## Appearance and Hide All

**Appearance → White / Glass** is a global saved preference in the tray/menu.
White is the default. V1.3.1 Glass uses a mostly neutral backing, native frost,
rounded light-catching edges, subtle highlights and matching temporary surfaces.
Interface headings are bold; document text and artwork retain their original
weight, colours and opacity. Windows 11 build 22621+ uses a rounded native compositor backdrop; Windows 10,
unavailable effects and reduced transparency/high contrast use a solid surface.
Mac uses NSVisualEffectView. This is a Liquid Glass-inspired approximation;
it does not implement optical refraction or native Apple Liquid Glass.
OS-owned Mac menus and standard colour/permission dialogs retain native styling.
Temporary menus have roomier rows and a clear selected state. F1 help groups
shortcuts into two columns when space permits and scrolls on smaller desktops.
Reduced motion disables the brief 140 ms edge light catch and feedback fades.
Glass creation, restore and popup presentation never move or fade document content.
There are no animated backgrounds or desktop-capture loops.

<details>
<summary>V1.3.1: actual Windows Glass and Appearance menu</summary>

![V1.3.1 Glass over an owned demonstration background](docs/media/glass-v131-candidate.png)

This is a native Windows capture. The caption and backdrop belong to the test
window; the board has no title bar or permanent toolbar.

</details>

**Ctrl+Alt+H** on Windows, **Control+Option+H** on Mac, or the matching menu action
hides all visible boards immediately. Press again to restore that recorded set
without taking focus from your current app. Already minimized boards stay hidden.
New boards remain visible outside an older hidden batch. Individually restored
or deleted boards leave the batch; a later manual minimize is respected. Held H
repeats and key release cannot toggle again. Mac's alternate preset includes H;
normal Command+H remains a system shortcut.

On Windows, **Hide All shortcut** in the tray menu offers **Ctrl+Alt+H** and
**Ctrl+Alt+Shift+H**. Your explicit choice is saved for the next launch. A conflict
keeps W/S working; choose the alternative or retry the unavailable binding.
The app never silently switches shortcuts. Mac retains its existing W/S/H presets.

OCR and Extract Text are removed in V1.3.1, including their engine and language data.
Historical V1.3 release assets and notes remain available.

## Limitations and development

- Documents are session-only. Only preferences are saved.
- Windows 11 has scripted native and packaged checks. Windows 10, clean-machine
  deployment and physical mixed-DPI arrangements still need testing.
- Mac remains a preview. Interactive shortcuts, focus, permissions, capture,
  Spaces and Retina/multi-monitor acceptance are outstanding. Floating windows
  use normal Space membership; coverage over every full-screen app is not guaranteed.
- Linux is unsupported. Images are limited to 64 million pixels and editable
  clipboard data to 96 MB. Protected desktop content may be unavailable to capture.
- The app has no accounts, network service or telemetry.

[CONTRIBUTING](CONTRIBUTING.md) covers source setup, architecture and rebuilding.
[Testing and troubleshooting](docs/TESTING.md) covers native checks and remaining
hardware acceptance. [Report a bug](https://github.com/nottbradd/MiniWhiteboard/issues)
with the version, OS and reproduction steps.

## License

Mini Whiteboard's own source and assets use the [MIT license](LICENSE).
Dependencies retain their own terms; see [third-party notices](docs/THIRD_PARTY_NOTICES.md).
Both packages contain license texts, exact dependency versions, notice hashes
and the [source/rebuild guide](assets/licenses/SOURCES.md).
