# Build the Mac tester from your Windows PC

The source repository and macOS workflow are prepared locally. **The workflow has
not run on GitHub yet.** There is no remote repository configured. The connected
GitHub account is `nottbradd`; the local GitHub CLI is not installed and Git
Credential Manager has no signed-in GitHub accounts. Your GitHub Project can
track work, but a repository is needed to hold these files and run Actions.

The existing Windows release ZIPs remain unchanged. Do not upload the Windows
environment, distributions or ZIPs with the source.

## 1. Create the repository

Sign in to [GitHub's new repository page](https://github.com/new) as `nottbradd`.
Choose owner **nottbradd**, name **MiniWhiteboard**, and **Private**. Leave the
README, .gitignore and licence initialization options off: this local repository
already has its files and history. Click **Create repository**.

If that name already exists, inspect the repository before using it. Use another
empty repository name if necessary and substitute its URL below. Do not force-push
over an existing repository.

## 2. Push this prepared repository

Open PowerShell in the project folder:

```powershell
Set-Location -LiteralPath 'C:\Users\RadiumPCs\OneDrive\Desktop\mini whiteboard app'
git status
git log -1 --oneline
git remote -v
git remote add origin https://github.com/nottbradd/MiniWhiteboard.git
git push -u origin main
```

Only add `origin` when `git remote -v` has no existing origin. If there is one,
check its URL first. The push uses Git Credential Manager, which is already
installed with Git; complete its browser sign-in to the intended account. Do not
put an access token in the remote URL or paste credentials into the project.

A local commit is supplied, so you do not need to commit it again. For later
changes, the exact commands are:

```powershell
git add .
git diff --cached --stat
git commit -m "Update Mini Whiteboard macOS CI"
git push origin main
```

The local commit uses `nottbradd` and the account's GitHub no-reply address. You
can choose a different local Git author identity with `git config user.name` and
`git config user.email` before making later commits.

### Optional GitHub CLI route

If you prefer the CLI, install it, reopen PowerShell, then authenticate and create
the empty private repository. Use this route instead of creating it on the website:

```powershell
winget install --id GitHub.cli --exact
# Reopen PowerShell, then return to the project directory.
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh repo create nottbradd/MiniWhiteboard --private --source . --remote origin --push
```

Again, check for an existing repository and remote before creating either.

## 3. Run the Mac workflow

In the repository, go to **Actions → macOS V1.1 → Run workflow**, select **main**,
then click **Run workflow**. Relevant source/build/test pushes to main also run it;
documentation-only pushes do not. If GitHub asks you to enable Actions for this
repository, enable them first.

The job uses the requested real GitHub-hosted `macos-14` runner and Python 3.13.
The checkout, Python setup and artifact actions are pinned to verified revisions
of their current v7 tags. Pip caches downloads using all three requirements files.
The development and Mac requirement files already include the base requirements.

The job prints OS/CPU/Python/package versions, installs dependencies, checks Mac
imports and production platform selection, runs the complete unittest suite,
uses `build_macos.sh` and the existing Mac spec, and validates the bundle. The
build script also retains its own full test gate. No Windows build runs here.

Bundle checks cover the plist, Version 1.1, `com.brad.miniwhiteboard`, LSUIElement,
minimum macOS 14.0, Python/Qt/native bridge/frozen modules, Cocoa plugin, every
Mach-O architecture, dependency install names, internal symlinks and signatures.
Windows PE/EXE/DLL files fail validation. A brief Cocoa launch checks for immediate
failure, then requests normal termination of its owned process. If the runner has
no WindowServer login session, that startup check reports **NOT RUN** explicitly.

The archive is created on macOS with `ditto`. Its root and CRCs are checked; clean
extraction must preserve all files, directories, permissions, hashes and symlinks.
The extracted app undergoes the complete bundle validation again before upload.

Universal2 remains the default. The existing build permits arm64 fallback only
after a real architecture mismatch on an arm64 host. Other build failures fail
the workflow and retain their logs; no test is skipped to obtain a green run.

**Runner availability:** GitHub schedules `macos-14` interruptions during October
2026 and retirement on **November 2, 2026**. The initial workflow retains your
requested label. A failure before checkout may be a runner availability problem;
check [GitHub's runner notice](https://github.com/actions/runner-images/issues/13518).
After retirement, choose an available Mac runner, rerun the entire pipeline and
record its actual OS/architecture; changing the runner does not prove macOS 14
execution. The bundle minimum remains 14.0.

## 4. Download the verified archive

Open the **successful run**. In its **Artifacts** section, download
**MacMiniWhiteboardV1.1**. GitHub supplies an outer artifact archive; extract that
outer archive on Windows to obtain the already-created inner file:

```text
MacMiniWhiteboardV1.1.zip
└── Mini Whiteboard.app
```

Copy the inner **MacMiniWhiteboardV1.1.zip** unchanged to your Windows Desktop.
Keep it zipped on Windows. Do not extract and rebuild that Mac archive on Windows;
the inner ZIP preserves Mac permissions and symlinks. Send that inner file to Mac
testers. They extract it on macOS, move the app to Applications and open it. The
initial app is ad-hoc signed and remains a tester/beta release until interactive
acceptance is done; Apple's Open Anyway guidance is in README.

Download **macos-v1.1-verification** from the same run for tests, environment,
build, bundle, startup, extracted-bundle and ZIP reports. Compare the release
report's SHA-256 with the downloaded inner ZIP:

```powershell
Get-FileHash -LiteralPath "$env:USERPROFILE\OneDrive\Desktop\MacMiniWhiteboardV1.1.zip" -Algorithm SHA256
```

Artifacts are retained for 30 days, subject to repository limits. If a job fails,
open its failing step and download the verification artifact. Fix the actual
dependency/import/test/build/linkage/startup/package failure and rerun; do not
record an artifact from a failed run as a release.

## 5. What success proves

Only after an actual successful runner execution, record **CI VERIFIED** for
dependency installation, real Mac imports, automated tests, PyInstaller build,
bundle metadata/architecture/linkage/signatures, and the ditto ZIP round-trip.
Record limited startup as **CI VERIFIED** only if its own report says PASSED.
Save the run URL, source commit, runner versions, reports and archive SHA-256.
Update CROSS_PLATFORM_REPORT and TEST_RESULTS from those real results.

These interactive checks remain **NOT RUN**: Control+Option+W with another app
focused, real two-press cursor placement, global Escape, menu-bar mouse input,
always-on-top, Screen Recording prompts, screenshot-region interaction, Spaces,
Mission Control, Stage Manager, Retina and physical multi-monitor behaviour.
The full list remains in [MACOS_CHECKLIST.md](MACOS_CHECKLIST.md). A Universal2
binary inspection also does not prove execution on both CPU architectures.
