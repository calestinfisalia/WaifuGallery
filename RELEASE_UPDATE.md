# Platform Release and Update Guide

This guide is the release runbook for AI agents and maintainers. Windows, Linux, and Android can have independent app versions. Windows `0.1.17` is published in `windows-v0.1.17`; Android remains at `0.1.16`, and Linux remains at `0.1.12` until its package is added manually. New update checks must use the exact platform release tag from `updates.json`, not the global `releases/latest` endpoint.

## Source of truth

- [`updates.json`](updates.json) is the published update feed. Its `schema_version` is `1`, and each `platforms` entry contains:
  - `version`: the numeric app version, such as `0.1.13`.
  - `release_tag`: the exact GitHub Release tag whose assets belong to that platform update.
- Windows, Linux, and Android clients select only their own manifest entry. They fetch release metadata by that exact tag, not by global latest.
- Windows requires `WaifuGallery-Setup-x64.exe`; its GitHub asset digest must be SHA-256. The portable EXE is also distributed.
- Linux requires at least one version-matched x86_64 AppImage or Flatpak asset. Linux update notices link to the release page; package installation remains manual.
- Android requires `app-release.apk` with a SHA-256 digest. `versionCode` must increase for every APK, even when app versions for other platforms do not change.
- GitHub generates the `digest` field for uploaded release assets. Do not substitute a checksum from a different file or release.

The manifest must point to releases that already exist and contain the required platform asset. Keep it at the **latest published version per platform**, not at a source version whose package has not been published yet. Current source versions are Windows `0.1.17`, Linux `0.1.16`, and Android `0.1.16`; the feed is Windows `0.1.17` (`windows-v0.1.17`), Linux `0.1.12` (`v0.1.15`), and Android `0.1.16` (`v0.1.16`). Skip the Linux `0.1.15` package and add Linux `0.1.16` to release `v0.1.16` manually later.

## Previous compatibility release: `v0.1.15`

Compatibility release `v0.1.15` contains Windows `0.1.15`, Android `0.1.15` (`versionCode` `13`), and reused Linux `0.1.12` packages. It is superseded by `v0.1.16`. The Windows and Android builds use GNU GPL version 3 or later. The Linux packages were not rebuilt and remain under their original MIT license.

The Android version intentionally matches the compatibility tag. Legacy Android clients query `/releases/latest`, parse the release tag as the app version, and install `app-release.apk`. Android `0.1.15`/code `13` provides the GPL-licensed update and prevents the old updater from offering the same update again.

The `v0.1.15` compatibility release contains:

| Platform | App version | Required release assets |
| --- | --- | --- |
| Windows | `0.1.15` | `WaifuGallery-Setup-x64.exe`, `WaifuGallery-Portable-x64.exe`, `LICENSE-GPL-3.0.txt` |
| Linux (currently published; MIT) | `0.1.12` | `Waifu-Gallery-0.1.12-x86_64.AppImage`, `Waifu-Gallery-0.1.12-x86_64.flatpak` |
| Android | `0.1.15` (`versionCode` `13`) | `app-release.apk` (contains the GPL license text) |

`SHA256SUMS-0.1.15.txt` contains hashes for the six existing payload assets. The Windows and Android assets were built from GPL-licensed source; Linux assets were reused unchanged from `v0.1.14`.

## Current compatibility release: `v0.1.16`

Release `v0.1.16` is the compatibility release for legacy clients and contains Windows `0.1.16`, Android `0.1.16`, and will receive Linux assets manually later. Windows `0.1.17` is a separate platform-only update in `windows-v0.1.17`. The Linux `0.1.15` package is skipped.

Android `versionCode` is `14`. Preserve the current Android signing setup documented in `android/README.md`; do not commit signing keys or credentials. The feed points Windows to `windows-v0.1.17`, Android to `v0.1.16`, and Linux to `0.1.12` / `v0.1.15` until its package is added.

The `v0.1.16` release contains the `0.1.16` Windows and Android assets. The Windows `0.1.17` platform release contains `WaifuGallery-Setup-x64.exe`, `WaifuGallery-Portable-x64.exe`, and `LICENSE-GPL-3.0.txt`. Legacy Linux clients do not yet have a Linux package in the latest compatibility release. Do not change the Linux manifest entry until matching assets are attached.

### Add Linux `0.1.16` assets later

Build on a **native x86_64 Linux host** after validating window behavior under Wayland and X11 and multimedia codec availability in the intended runtime. From `linux`, run tests and build into a staging directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q waifu_gallery
bash -n ./release.sh
ASSET_DIR="$HOME/releases/waifu-gallery/linux-v0.1.16"
mkdir -p "$ASSET_DIR"
RELEASE_OUTPUT_DIR="$ASSET_DIR" bash ./release.sh
```

Confirm the outputs are `Waifu-Gallery-0.1.16-x86_64.AppImage` and `Waifu-Gallery-0.1.16-x86_64.flatpak`, and that each includes the GNU GPL license. Upload both to the existing compatibility release without replacing its Windows or Android assets:

```bash
gh release upload v0.1.16 \
  "$ASSET_DIR/Waifu-Gallery-0.1.16-x86_64.AppImage" \
  "$ASSET_DIR/Waifu-Gallery-0.1.16-x86_64.flatpak" \
  --repo calestinfisalia/WaifuGallery
```

Verify the uploaded asset names and SHA-256 digests, then update only Linux in `updates.json` to version `0.1.16` and release tag `v0.1.16`. Commit/push the manifest and verify the public feed.

## Version files

Update all version declarations for the target platform:

- **Windows:** `windows/waifu_gallery/__init__.py`, `windows/pyproject.toml`, and the default `AppVersion` in `windows/setup_windows.iss`. `windows/build_release.ps1` reads the app version and builds the setup and portable EXEs.
- **Linux:** `linux/waifu_gallery/__init__.py` and `linux/pyproject.toml`. `linux/release.sh` uses the project version to name both packages.
- **Android:** `android/app/build.gradle.kts` (`versionName` and a strictly increasing `versionCode`).

Do not bump versions for unaffected platforms, except for the coordinated `0.1.16` release, which uses the same source version for all three. Keep the user-facing version numeric; platform identity belongs in the manifest key and release tag, not in strings like `win-0.1.13`. For Android compatibility releases specifically, older clients compare the global compatibility tag directly with `versionName`, so make those two numeric versions match.

## Release a platform update

The Windows 0.1.17 update follows the platform-only procedure below.

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

To keep legacy clients working, publish a **compatibility release** using the conventional tag `vX.Y.Z` with the Windows installer and portable EXE, Linux packages, and Android APK. The package versions may differ by platform, but legacy Android compares the global tag to the APK's `versionName`; keep those equal to avoid repeated update prompts. The compatibility release is `v0.1.16`, with Windows `0.1.16`, Linux `0.1.12`, and Android `0.1.16`. Windows `0.1.17` is released separately. The `v0.1.16` release will gain Linux assets after the maintainer adds them manually.

If future releases are platform-only, GitHub's global `releases/latest` may no longer contain assets for every platform. Keep publishing compatibility releases while legacy clients need automatic updates, or provide a manual update path for them.

## Validation checklist

- Windows: from `windows`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`.
- Linux: from `linux`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`; build packages on Linux, not on Windows.
- Android: run `.\gradlew.bat :app:testDebugUnitTest :app:assembleRelease`; inspect the release APK's `versionName` and `versionCode`.
- Confirm the source version, built package version, manifest version, tag, asset name, and digest all refer to the same platform release.
- Never overwrite another platform's manifest entry to make the global version numbers match.
