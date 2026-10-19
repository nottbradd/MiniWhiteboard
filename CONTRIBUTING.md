# Contributing to Mini Whiteboard

Bug reports, documentation improvements and focused changes are welcome. Use
the [README](README.md) to set up a Windows or macOS development environment.
Linux is currently unsupported.

## Before changing the app

Read [SPEC.md](docs/SPEC.md) for current behaviour and [PLAN.md](docs/PLAN.md) for the
design decisions. Shared drawing, documents and tools belong in the shared
modules. Native behaviour belongs in `mini_whiteboard/platform/windows/` or
`mini_whiteboard/platform/macos/`. Tests use fake platform services when they
do not need a real desktop.

Keep these behaviours covered when making changes:

- Board and screenshot creation each use one hold, pointer movement, then release.
  Releasing any required key ends the gesture; repeated activations cannot restart it.
- Tool keys work only in the active canvas. A text editor owns its typing,
  clipboard commands and undo while it is active.
- A gesture commits one document action; cancellation adds no history entry.
- Closing the last board leaves the tray/menu-bar utility running.
- Documents remain session-only; saved preferences stay separate from them.

## Validation

Install the development requirements, then run the full automated suite:

```powershell
# Windows, from the project directory
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m unittest discover -v
```

```bash
# macOS, from the project directory
.venv-macos/bin/python -m pip install -r requirements-dev.txt -r requirements-macos.txt
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m unittest discover -v
```

Add focused regression coverage when changing behaviour. Documentation-only
changes do not need new tests. The Windows tests workflow runs for code/config pull requests
to `main`; the macOS build workflow runs for relevant pushes to `main` and manual
dispatches.

Use [MANUAL_TESTING.md](docs/MANUAL_TESTING.md) and
[MACOS_CHECKLIST.md](docs/MACOS_CHECKLIST.md) for native acceptance. Native scripts can
operate windows, hotkeys, the clipboard and screen capture on your desktop; run
them deliberately in a suitable test session. Report the OS, display setup and
checks actually performed. Mark unperformed GUI/hardware checks **NOT RUN**.
Offscreen tests cannot prove native focus, permissions or physical display behaviour.

## Pull requests and reports

Keep changes focused and describe their resulting behaviour. Include validation
results and remaining limitations in the pull request. For a bug, include the OS,
app version, whether you used source or a packaged build, and reproducible steps.

Generated environments, builds, ZIPs and verification output are ignored. Keep
credentials, private screenshots and machine-specific paths out of commits and
public reports. Verification logs belong in local output or Actions artifacts;
the repository documents their results.

For a suspected security issue, use GitHub's private vulnerability reporting if
it is enabled. Otherwise ask the maintainer for a private reporting channel
without posting exploit details or credentials in a public issue.

## License

Contributions to this project's own source and assets are provided under the
[MIT license](LICENSE). Preserve applicable notices when adding third-party
material. Dependencies retain their own terms; see
[THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).
