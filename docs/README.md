# Documentation

Start with the [main README](../README.md) for downloads, setup and shortcuts.

| Guide | What it covers |
|---|---|
| [Release notes](RELEASE_NOTES.md) | V1.1 Windows release and Mac preview, downloads and verification |
| [Specification](SPEC.md) | Application behaviour and requirements |
| [Implementation plan](PLAN.md) | Approved design and implementation history |
| [Test results](TEST_RESULTS.md) | Actual automated, native and packaging results |
| [Windows manual checklist](MANUAL_TESTING.md) | GUI and physical display checks |
| [Mac acceptance checklist](MACOS_CHECKLIST.md) | Remaining native Mac checks and commands |
| [Cross-platform report](CROSS_PLATFORM_REPORT.md) | Shared code, platform adapters and delivery evidence |
| [Performance](PERFORMANCE.md) | Canvas and screenshot measurements |
| [GitHub builds and releases](GITHUB_SETUP.md) | Workflows, artifacts and release publication |
| [Third-party notices](THIRD_PARTY_NOTICES.md) | Dependency licenses, sources and library replacement |
| [Sharing draft](SHARING.md) | A short post ready for the owner to publish |

Contribution guidance stays at [CONTRIBUTING.md](../CONTRIBUTING.md), and the
project license stays at [LICENSE](../LICENSE).

## Reproduce the placement demo

The [placement GIF](media/placement.gif) and [board screenshot](media/whiteboard.png)
are rendered from the actual application on a controlled desktop. No personal
desktop content is captured. The demo drives the real two-press placement
controller and verifies that only the second press creates a board. Physical
Windows hotkeys are verified separately by the native workflow check.

On Windows, with the development environment installed:

```powershell
.\.venv\Scripts\python.exe -m pip install Pillow==12.3.0
.\.venv\Scripts\python.exe -m scripts.make_demo
```

Pillow is needed only to encode the GIF. `--frames-only` renders PNG frames
without it. Demo frames and generated verification reports stay under the
ignored `verification/` directory. The script uses the Windows Segoe UI fonts;
inspect any regenerated media before publishing it.
