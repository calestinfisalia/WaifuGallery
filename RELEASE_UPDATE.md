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

The manifest must point to releases that already exist and contain the required platform asset. Keep it at the **latest published version per platform**, not at a source version whose package has not been published yet. The current source versions are Windows `0.1.14`, Linux `0.1.13`, and Android `0.1.12`; Windows and Android have platform releases, while Linux remains at its last published version until its next package is ready.

## Current handoff: complete compatibility release `v0.1.14`

Windows `0.1.14` (`windows-v0.1.14`) and Android `0.1.12` (`android-v0.1.12`) have been published as platform releases with `--latest=false`. The compatibility release `v0.1.13` remains GitHub's **Latest** for legacy clients. `updates.json` points Windows and Android to their new platform releases; Linux remains at `0.1.12` on `v0.1.13`. Do not publish the compatibility release until the Linux `0.1.13` build is ready.

The next compatibility release is expected to contain:

| Platform | App version | Required release assets |
| --- | --- | --- |
| Windows | `0.1.14` | `WaifuGallery-Setup-x64.exe`, `WaifuGallery-Portable-x64.exe` |
| Linux | `0.1.13` | `Waifu-Gallery-0.1.13-x86_64.AppImage`, `Waifu-Gallery-0.1.13-x86_64.flatpak` |
| Android | `0.1.12` (`versionCode` `11`) | `app-release.apk` |

The Windows and Android binaries are available from the platform releases above. Do not substitute binaries from `v0.1.13` or rebuild them with older source.

### Linux-agent steps

1. Inspect `git status` before syncing; preserve any local work. Fetch/pull the source and verify the checked-out versions are Windows `0.1.14`, Linux `0.1.13`, and Android `0.1.12` with Android `versionCode` `11`. Confirm `updates.json` points Windows to `windows-v0.1.14`, Android to `android-v0.1.12`, and Linux to `v0.1.13`. If anything differs, stop and ask the maintainer. Do not reset or discard local changes.
2. On a **native x86_64 Linux host** (not Windows or WSL), from `linux`, run:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 -m compileall -q waifu_gallery
   bash ./release.sh
   ```

   The release script requires Python 3.10+, `flatpak`, `flatpak-builder`, `appimagetool`, ImageMagick's `magick`, and the user Flatpak SDK `org.freedesktop.Sdk//24.08`. The exact asset names above assume an x86_64 host; stop and ask before substituting a different architecture. Build directly into a staging directory outside Git, then download the already published Windows and Android assets:

   ```bash
   export ASSET_DIR="$HOME/releases/waifu-gallery/compatibility-v0.1.14"
   mkdir -p "$ASSET_DIR"
   RELEASE_OUTPUT_DIR="$ASSET_DIR" bash ./release.sh
   gh release download windows-v0.1.14 --repo calestinfisalia/WaifuGallery \
     --pattern WaifuGallery-Setup-x64.exe --pattern WaifuGallery-Portable-x64.exe \
     --dir "$ASSET_DIR"
   gh release download android-v0.1.12 --repo calestinfisalia/WaifuGallery \
     --pattern app-release.apk --dir "$ASSET_DIR"
   ```

3. Confirm all five assets are in `ASSET_DIR` with the exact names in the table. Stop and ask the maintainer if any asset is missing or its app version does not match the table.
4. Confirm `v0.1.14` is unused, then create **one stable compatibility release** (not another platform-only release), so legacy apps using GitHub's `releases/latest` still see every platform:

   ```bash
   gh auth status
   gh release create v0.1.14 \
     "$ASSET_DIR/WaifuGallery-Setup-x64.exe" \
     "$ASSET_DIR/WaifuGallery-Portable-x64.exe" \
     "$ASSET_DIR/Waifu-Gallery-0.1.13-x86_64.AppImage" \
     "$ASSET_DIR/Waifu-Gallery-0.1.13-x86_64.flatpak" \
     "$ASSET_DIR/app-release.apk" \
     --title "Waifu Gallery 0.1.14 Compatibility Release" \
     --notes "Compatibility release: Windows 0.1.14, Linux 0.1.13, Android 0.1.12." \
     --latest \
     --repo calestinfisalia/WaifuGallery
   ```

   Do not mark the release as a draft or prerelease. The explicit `--latest` makes this complete release the legacy update channel.
5. Verify the exact tag with `gh release view v0.1.14 --repo calestinfisalia/WaifuGallery --json tagName,isDraft,isPrerelease,assets`. Confirm all five filenames are present and GitHub reports a SHA-256 digest for `WaifuGallery-Setup-x64.exe` and `app-release.apk`. Confirm `v0.1.14` is the latest release.
6. Only after verification, change all three `updates.json` entries to Windows `0.1.14`, Linux `0.1.13`, and Android `0.1.12`, setting every `release_tag` to `v0.1.14`. Commit and push that feed update. Never advertise an artifact before its release exists.
7. Verify the public `updates.json` and release once more. Keep the compatibility release as `releases/latest` while supporting old clients.

## Version files

Update all version declarations for the target platform:

- **Windows:** `windows/waifu_gallery/__init__.py`, `windows/pyproject.toml`, and the default `AppVersion` in `windows/setup_windows.iss`. `windows/build_release.ps1` reads the app version and builds the setup and portable EXEs.
- **Linux:** `linux/waifu_gallery/__init__.py` and `linux/pyproject.toml`. `linux/release.sh` uses the project version to name both packages.
- **Android:** `android/app/build.gradle.kts` (`versionName` and a strictly increasing `versionCode`).

Do not bump versions for unaffected platforms. Keep the user-facing version numeric; platform identity belongs in the manifest key and release tag, not in strings like `win-0.1.13`.

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

To keep legacy clients working, publish a **compatibility release** using the conventional tag `vX.Y.Z` with the Windows installer and portable EXE, Linux packages, and Android APK. The package versions inside it may differ by platform. Point all three manifest entries at their latest app versions but at this compatibility release tag. The latest complete compatibility release is `v0.1.13`, with Windows `0.1.13`, Linux `0.1.12`, and Android `0.1.11`. Until `v0.1.14` is complete, newer Windows and Android clients use their platform-specific releases while Linux continues to use `v0.1.13`. See the current handoff above before preparing the next release.

If future releases are platform-only, GitHub's global `releases/latest` may no longer contain assets for every platform. Keep publishing compatibility releases while legacy clients need automatic updates, or provide a manual update path for them.

## Validation checklist

- Windows: from `windows`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`.
- Linux: from `linux`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`; build packages on Linux, not on Windows.
- Android: run `.\gradlew.bat :app:testDebugUnitTest :app:assembleRelease`; inspect the release APK's `versionName` and `versionCode`.
- Confirm the source version, built package version, manifest version, tag, asset name, and digest all refer to the same platform release.
- Never overwrite another platform's manifest entry to make the global version numbers match.
