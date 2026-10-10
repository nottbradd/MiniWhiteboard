# GitHub repository, builds and publication

The repository is [nottbradd/MiniWhiteboard](https://github.com/nottbradd/MiniWhiteboard).
It already contains the source on `main`. Repository preparation does not change
its visibility; the final visibility change is described below.

## Verified Mac build

[The October 1 run](https://github.com/nottbradd/MiniWhiteboard/actions/runs/36831877399)
succeeded for source commit `7cd78288558ed1120fa39d7fabf331d438034c2f`.
It ran on macOS 14.8.9, arm64, with universal2 Python 3.13.15, PySide6/Qt 6.11.2,
PyInstaller 6.22.3 and PyObjC 12.2.2. It passed all 156 tests, built and validated
the Universal2 bundle, passed an eight-second packaged Cocoa startup check with
normal termination, and verified the `ditto` ZIP after clean extraction.

The limited startup check does not establish interactive Mac behaviour.
[MACOS_CHECKLIST.md](MACOS_CHECKLIST.md) records those remaining **NOT RUN** checks.

## Run the workflows

In the repository, choose **Actions → macOS V1.1 → Run workflow**, select **main**,
then run it. Relevant source/build/test pushes to main also trigger it;
documentation-only pushes do not. **Windows tests** runs on code/config main pushes, pull
requests to main and manual dispatches. It tests the source without rebuilding
the Windows release.

The Mac job uses `macos-14`, Python 3.13 and pinned GitHub actions. It checks
imports/platform selection, runs the complete suite, builds using the existing
shell/spec, validates the bundle, briefly launches its owned app process and
creates and round-trips the ZIP. Bundle checks cover metadata, frozen modules,
Mach-O architecture/linkage, symlinks and signatures. Windows binaries fail
validation. If no WindowServer login session is available, the startup check
explicitly reports **NOT RUN**. Universal2 is the default; a real architecture
mismatch on an arm64 host is required before an arm64 fallback.

**Runner availability:** GitHub has announced October 2026 interruptions and
November 2 retirement for `macos-14`. See
[the runner notice](https://github.com/actions/runner-images/issues/13518).
When changing the runner, rerun the pipeline and record its actual OS and
architecture. The application's minimum deployment target remains macOS 14.0.

## Download the Mac tester artifact

Open a successful run and download **MacMiniWhiteboardV1.1** under **Artifacts**.
Extract GitHub's outer archive on Windows to obtain the already-created inner ZIP:

```text
MacMiniWhiteboardV1.1.zip
└── Mini Whiteboard.app
```

Keep that inner ZIP unchanged when transferring it to a Mac. Extract it on macOS;
this preserves Mac permissions and symlinks. The initial ad-hoc signed app is a
tester build. See README for installation and Apple's Open Anyway instructions.

Download **macos-v1.1-verification** from the same run for environment, tests,
build, bundle, startup and archive reports. Artifacts are retained for 30 days,
subject to repository limits; the October 1 artifacts expire on October 31.

For the October 1 run, the inner ZIP is **74,214,960 bytes** with SHA-256:

```text
56402e4443d09abac57c1a010017bf78d3de3217d9ef80a8898abb3a85cd63f1
```

Compare a downloaded inner ZIP from its folder in PowerShell:

```powershell
Get-FileHash -LiteralPath .\MacMiniWhiteboardV1.1.zip -Algorithm SHA256
```

Do not confuse the inner ZIP's hash with GitHub's outer artifact digest. Do not
use an artifact from a failed run as a verified build. Actions artifacts and
stable GitHub Releases serve different purposes. No stable release has been
published; dependency notices and interactive acceptance remain binary-release
work, described in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Work on the source

Clone the existing repository rather than creating another one:

```powershell
git clone https://github.com/nottbradd/MiniWhiteboard.git
Set-Location MiniWhiteboard
git status
git remote -v
```

For changes, review and stage the intended source files, commit and push using
your normal Git credentials. Keep tokens out of remote URLs and committed files.
Generated environments, builds, archives and verification output are ignored.

## Make the repository public

The source now has an MIT license, contribution guidance, issue/PR templates,
public-facing documentation and automated workflows. Before changing visibility,
review the current source and the history. The initial commit's documentation
still contains historical machine-specific paths. The current documentation
uses portable paths. A scan of the existing history found no common credential
signatures or tracked generated artifacts; it cannot prove the absence of every
possible secret.

When you choose to publish, open **Settings → General → Danger Zone → Change
repository visibility**, choose **Public**, and complete GitHub's confirmation.
GitHub explains the effects in
[its visibility guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).
This exposes source/history and Actions logs to visitors. Public source does not
require publishing the tester ZIP as a stable release.

Suggested **About** description:

> A lightweight desktop whiteboard for drawing, text and screenshot annotations.
> Windows app with a macOS preview; built with Python and PySide6.

Suggested topics: `whiteboard`, `desktop-app`, `pyside6`, `python`, `windows`, `macos`.
