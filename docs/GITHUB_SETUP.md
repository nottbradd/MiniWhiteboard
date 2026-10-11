# GitHub repository, builds and releases

The public repository is [nottbradd/MiniWhiteboard](https://github.com/nottbradd/MiniWhiteboard).
Its About description and topics identify the app, Python/PySide6, Windows and
Mac support. The homepage points to the latest release. The main README includes
download links, the placement GIF and a screenshot.

## V1.1 publication

[V1.1 is published](https://github.com/nottbradd/MiniWhiteboard/releases/tag/v1.1).
The release tag points to `cf5330949ecd4ccf1a0c9d4cb9e63fc3bdceb926`.
All eight asset digests were compared with the local verified files. Anonymous
checks of both app download links and the demo returned HTTP 200.

The owner approved a **stable Windows release with a clearly labelled Mac
preview**. The two app assets are `WinMiniWhiteboardV1.1.zip` and
`MacMiniWhiteboardV1.1-Preview.zip`. The Mac preview label appears in the asset
name, release notes and README. Automated Mac verification does not establish
interactive acceptance; the [Mac checklist](MACOS_CHECKLIST.md) remains NOT RUN.

The [release notes](RELEASE_NOTES.md) describe the downloads and actual checks.
The release also includes SHA256SUMS and the exact Qt/PySide source archives.
Every app contains its dependency notices. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
explains the contents and source/replacement instructions.

The short [sharing draft](SHARING.md) is prepared for the owner to publish.

## Run the workflows

Choose **Actions → macOS V1.1 → Run workflow**, select **main**, then run it.
Relevant source/build/test or dependency-notice pushes to main also trigger it.
**Windows tests** runs on code/config main pushes, pull requests to main and
manual dispatches. It tests the source without rebuilding the Windows release.

The Mac job uses `macos-14`, Python 3.13 and pinned GitHub actions. It checks
imports and platform selection, runs the full suite, stages dependency notices,
builds the app, validates the bundle, briefly launches its owned app process,
and creates and round-trips a ZIP with `ditto`. Checks cover metadata, frozen
modules, Mach-O architecture/linkage, symlinks and signatures. If no WindowServer
login session is available, startup is explicitly NOT RUN. Universal2 is the
default; a real architecture mismatch on an arm64 host is required before an
arm64 fallback. Windows binaries fail Mac bundle validation.

**Runner availability:** GitHub has announced October 2026 interruptions and
November 2 retirement for `macos-14`. See [the runner notice](https://github.com/actions/runner-images/issues/13518).
When changing runners, rerun the pipeline and record its actual OS and
architecture. The application's minimum deployment target remains macOS 14.0.

## Obtain the Mac build artifact

Open a successful run and download **MacMiniWhiteboardV1.1** under **Artifacts**.
Extract GitHub's outer archive to obtain the already-created inner file:

```text
MacMiniWhiteboardV1.1.zip
└── Mini Whiteboard.app
```

Transfer that inner ZIP unchanged. Renaming it to
`MacMiniWhiteboardV1.1-Preview.zip` for publication does not change its bytes.
Extract on macOS to preserve permissions and symlinks. Download
**macos-v1.1-verification** from the same run for environment, test, build,
bundle, startup and archive reports. Actions artifacts are retained for 30 days;
GitHub Release downloads are separate assets.

Compare the inner archive with its Mac builder's report before uploading:

```powershell
Get-FileHash -LiteralPath .\MacMiniWhiteboardV1.1-Preview.zip -Algorithm SHA256
```

The inner ZIP hash differs from the outer Actions artifact digest. Publish only
an artifact from a successful build, with its actual test results and preview
status preserved.

## Prepare a future release

1. Build Windows and run the owned-window native checks and packaged-app checks.
2. Run the Mac pipeline and inspect its real reports. Complete interactive Mac
   acceptance before advertising Mac as stable.
3. Check dependency notices and source access, ZIP hashes and archive contents.
4. Stage a GitHub Release with a version tag, concrete notes, platform packages,
   checksums and dependency source archives. Verify uploaded digests against the
   local files, then publish the reviewed release.
5. Update README and test results, and prepare any sharing message separately.

Generated environments, builds, archives and verification output are ignored.
Keep credentials out of URLs, files and logs. Contribution guidance is in
[CONTRIBUTING.md](../CONTRIBUTING.md). Use ordinary commits that describe actual
changes; stars and visitor feedback come from people who try the project.
