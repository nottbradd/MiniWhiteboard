"""Summarise actual runner reports without upgrading interactive acceptance."""
import json
from pathlib import Path
from mini_whiteboard import APP_VERSION


def main():
    print(f"## Mini Whiteboard {APP_VERSION} macOS Universal2 Preview candidate\n")
    print("| Check | Actual result |\n|---|---|")
    for label, filename in (("Mac imports", "macos-import-smoke.json"),
                            ("App bundle", "macos-package-check.json"),
                            ("Limited startup", "macos-startup-check.json"),
                            ("Extracted app", "macos-extracted-package-check.json"),
                            ("ditto ZIP", "macos-release.json")):
        report = json.loads((Path("verification")/filename).read_text(encoding="utf-8"))
        print(f"| {label} | {report['status']} |")
    report = json.loads(Path("verification/macos-release.json").read_text(encoding="utf-8"))
    print(f"\nBundle architecture: `{report['architecture']}`.\n")
    print(f"ZIP SHA-256: `{report['sha256']}`.\n")
    print("The complete unittest logs are in the verification artifact. This is a tester/beta build.")
    print("\nInteractive Mac acceptance: **NOT RUN**. Global keys, hold/release cursor placement, "
          "Escape with another app focused, menu mouse interaction, always-on-top, permission "
          "prompts, screenshot selection, Spaces, Mission Control, Stage Manager, real Retina "
          "and physical multi-monitor behaviour remain on docs/TESTING.md.")
    print("\nDownload **MacMiniWhiteboardV1.3.2-Review02** below. Extract GitHub's outer artifact archive "
          "to obtain **MacMiniWhiteboardV1.3.2-Preview.zip**; transfer that inner ZIP unchanged.")


if __name__ == "__main__":
    main()
