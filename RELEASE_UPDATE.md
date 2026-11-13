# Platform Release and Update Guide

This guide is the release runbook for AI agents and maintainers. Windows, Linux, and Android have independent app versions. Do not use the GitHub repository's global `releases/latest` endpoint for new update checks.

## Source of truth

- [`updates.json`](updates.json) is the published update feed. Its `schema_version` is `1`, and each `platforms` entry contains:
  - `version`: the numeric app version, such as `0.1.13`.
  - `release_tag`: the exact GitHub Release tag whose assets belong to that platform update.
- Windows, Linux, and Android clients select only their own manifest entry. They fetch release metadata by that exact tag, not by global latest.
- Windows requires `WaifuGallery-Setup-x64.exe`; its GitHub asset digest must be SHA-256. The portable EXE is also distributed.
- Linux requires at least one version-matched x86_64 AppImage or Flatpak asset. Linux update notices link to the release page; package installation remains manual.
- Android requires `app-release.apk` with a SHA-256 digest. `versionCode` must increase for every APK, even when app versions for other platforms do not change.
- GitHub generates the `digest` field for uploaded release assets. Do not substitute a checksum from a different file or release.

The manifest must point to releases that already exist and contain the required platform asset. Keep it at the **latest published version per platform**, not at a source version whose package has not been published yet. The current source versions are Windows `0.1.15`, Linux `0.1.13`, and Android `0.1.15`; the feed points to Windows `0.1.15`, Linux `0.1.12`, and Android `0.1.15`, all via compatibility release `v0.1.15`.

## Current compatibility release: `v0.1.15`

Compatibility release `v0.1.15` is published and is GitHub's **Latest**. It contains Windows `0.1.15`, Android `0.1.15` (`versionCode` `13`), and reused Linux `0.1.12` packages. The new Windows and Android builds use GNU GPL version 3 or later. The Linux packages were not rebuilt and remain under their original MIT license; Linux `0.1.13` is pending a native Linux build.

The Android version intentionally matches the compatibility tag. Legacy Android clients query `/releases/latest`, parse the release tag as the app version, and install `app-release.apk`. Android `0.1.15`/code `13` provides the GPL-licensed update and prevents the old updater from offering the same update again.

The `v0.1.15` compatibility release contains:

| Platform | App version | Required release assets |
| --- | --- | --- |
| Windows | `0.1.15` | `WaifuGallery-Setup-x64.exe`, `WaifuGallery-Portable-x64.exe`, `LICENSE-GPL-3.0.txt` |
| Linux (reused; MIT) | `0.1.12` | `Waifu-Gallery-0.1.12-x86_64.AppImage`, `Waifu-Gallery-0.1.12-x86_64.flatpak` |
| Android | `0.1.15` (`versionCode` `13`) | `app-release.apk` (contains the GPL license text) |

`SHA256SUMS-0.1.15.txt` contains hashes for the six payload assets. The Windows and Android assets were built from GPL-licensed source; Linux assets were reused unchanged from `v0.1.14`.

### Later Linux `0.1.13` release

Linux `0.1.13` remains for the maintainer to build on a **native x86_64 Linux host** (not Windows or WSL). Run `python3 -m unittest discover -s tests -v`, `python3 -m compileall -q waifu_gallery`, and `bash ./release.sh` from `linux`. The release script requires Python 3.10+, `flatpak`, `flatpak-builder`, `appimagetool`, ImageMagick's `magick`, and the user Flatpak SDK `org.freedesktop.Sdk//24.08`. It outputs versioned packages under `~/releases/waifu-gallery/` by default. Publish `linux-v0.1.13` with `--latest=false`, then update only the Linux feed entry after verifying its assets and digests. The compatibility release remains the legacy channel; include a newly built Linux package in a future compatibility release before making that newer tag Latest.

## Version files

Update all version declarations for the target platform:

- **Windows:** `windows/waifu_gallery/__init__.py`, `windows/pyproject.toml`, and the default `AppVersion` in `windows/setup_windows.iss`. `windows/build_release.ps1` reads the app version and builds the setup and portable EXEs.
- **Linux:** `linux/waifu_gallery/__init__.py` and `linux/pyproject.toml`. `linux/release.sh` uses the project version to name both packages.
- **Android:** `android/app/build.gradle.kts` (`versionName` and a strictly increasing `versionCode`).

Do not bump versions for unaffected platforms. Keep the user-facing version numeric; platform identity belongs in the manifest key and release tag, not in strings like `win-0.1.13`. For Android compatibility releases specifically, older clients compare the global compatibility tag directly with `versionName`, so make those two numeric versions match.

## Release a platform update

1. Confirm which platform changed and choose its next version only. Check that the release tag is unused:
   - `windows-vX.Y.Z`
   - `linux-vX.Y.Z`
   - `android-vX.Y.Z`
2. Update that platform's version files, code, tests, and release notes. Do not update `updates.json` to a version that has no published release yet.
3. Run the platform's tests and build:
   - Windows, from PowerShell in `windows`: `.\build_release.ps1`. Outputs: `dist-release\WaifuGallery-Setup-x64.exe` and `dist-release\WaifuGallery-Portable-x64.exe`.
   - Linux, from Linux in `linux`: `bash ./release.sh`. Outputs default to `~/releases/waifu-gallery/`; set `RELEASE_OUTPUT_DIR` to change the destination.
   - Android, from PowerShell in `android`: `.\gradlew.bat :app:testDebugUnitTest :app:assembleRelease`. Output: `app\build\outputs\apk\release\app-release.apk`.
4. Commit and push the source/version changes. Create a stable GitHub Release for the platform tag, attach only that platform's release assets, and include concise platform-specific notes. Example:

   ```powershell
   gh auth status
   gh release create windows-v0.1.14 `
     windows\dist-release\WaifuGallery-Setup-x64.exe `
     windows\dist-release\WaifuGallery-Portable-x64.exe `
     --title "Waifu Gallery Windows 0.1.14" `
     --notes "Windows fixes and improvements." `
     --repo calestinfisalia/WaifuGallery
   ```

5. Verify the release by its exact tag with `gh api repos/calestinfisalia/WaifuGallery/releases/tags/<tag>`. Confirm it is not a draft or prerelease, the expected asset names are present, URLs point to that release, and GitHub reports a valid SHA-256 digest for assets that the updater downloads.
6. Only after those checks pass, update **that platform's** `version` and `release_tag` in `updates.json`. Leave the other platform entries unchanged. Commit and push the manifest update so clients can read it from the `main` branch.
7. Verify the public feed and release asset metadata, then test the updater against a prior app version and a fixture where the other platforms have higher versions. Confirm no release for another platform is offered.

The manifest update is a separate commit after the release exists by design: otherwise clients could see a new version before GitHub has the release asset and checksum.

## Migrating clients from the old updater

Previously released apps query the single GitHub `/releases/latest` endpoint and do not read `updates.json`. They cannot be taught the new feed remotely.

To keep legacy clients working, publish a **compatibility release** using the conventional tag `vX.Y.Z` with the Windows installer and portable EXE, Linux packages, and Android APK. The package versions may differ by platform, but legacy Android compares the global tag to the APK's `versionName`; keep those equal to avoid repeated update prompts. The current compatibility release is `v0.1.15`, with Windows `0.1.15`, Linux `0.1.12`, and Android `0.1.15`. See the current handoff above before preparing the next release.

If future releases are platform-only, GitHub's global `releases/latest` may no longer contain assets for every platform. Keep publishing compatibility releases while legacy clients need automatic updates, or provide a manual update path for them.

## Validation checklist

- Windows: from `windows`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`.
- Linux: from `linux`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`; build packages on Linux, not on Windows.
- Android: run `.\gradlew.bat :app:testDebugUnitTest :app:assembleRelease`; inspect the release APK's `versionName` and `versionCode`.
- Confirm the source version, built package version, manifest version, tag, asset name, and digest all refer to the same platform release.
- Never overwrite another platform's manifest entry to make the global version numbers match.
