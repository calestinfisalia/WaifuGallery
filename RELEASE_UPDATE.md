# Platform Release and Update Guide

This guide separates the two update paths: platform releases for current clients, and a compatibility release for older clients that still query GitHub `/releases/latest`. Windows, Linux, and Android have independent app versions; a fix for one platform must not bump the versions or manifest entries for the others.

Current published platform versions are Windows `0.1.21`, Linux `0.1.18`, and Android `0.1.19`. Current clients use the exact platform tag in `updates.json`. The compatibility release `v0.1.16` is deliberately marked as GitHub Latest so old clients can still find the bridge update; do not make a platform-only release the global Latest release.

## Release channels

- **Platform update (normal path):** publish only the changed platform under `windows-vX.Y.Z`, `linux-vX.Y.Z`, or `android-vX.Y.Z`. Update only that platform's entry in `updates.json` after its release and assets are verified. This is the path for future releases such as Windows `0.1.22`, Linux `0.1.19`, or Android `0.1.20`.
- **Compatibility update (legacy path):** use the conventional `vX.Y.Z` tag only when intentionally serving clients that still read `/releases/latest`. It must contain the assets required by those legacy clients and be explicitly selected as GitHub Latest. Compatibility releases are coordinated exceptions, not the normal way to publish a platform fix.
- **Bridge behavior:** the existing `v0.1.16` compatibility release lets older clients install a build that reads `updates.json`. Once updated, clients follow their own platform entry and no longer depend on the global Latest endpoint.

## Source of truth

- [`updates.json`](updates.json) is the published update feed. Its `schema_version` is `1`, and each `platforms` entry contains:
  - `version`: the numeric app version, such as `0.1.13`.
  - `release_tag`: the exact GitHub Release tag whose assets belong to that platform update.
- Windows, Linux, and Android clients select only their own manifest entry. They fetch release metadata by that exact tag, not by global latest.
- Windows requires `WaifuGallery-Setup-x64.exe`; its GitHub asset digest must be SHA-256. The portable EXE is also distributed.
- Linux requires at least one version-matched x86_64 AppImage or Flatpak asset. Linux update notices link to the release page; package installation remains manual.
- Android requires `app-release.apk` with a SHA-256 digest. `versionCode` must increase for every APK, even when app versions for other platforms do not change.
- GitHub generates the `digest` field for uploaded release assets. Do not substitute a checksum from a different file or release.

The manifest must point to releases that already exist and contain the required platform asset. Keep it at the **latest published version per platform**, not at a source version whose package has not been published yet. The current feed is Windows `0.1.21` (`windows-v0.1.21`), Linux `0.1.18` (`linux-v0.1.18`), and Android `0.1.19` (`android-v0.1.19`). Linux `0.1.15` was intentionally skipped.

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

## Compatibility release: `v0.1.16`

The compatibility release is published at `v0.1.16` and is marked GitHub Latest. It contains Windows `0.1.16`, Linux `0.1.16`, and Android `0.1.16` assets. Windows `0.1.17` is a separate platform release at `windows-v0.1.17`. Android `versionCode` for the compatibility APK is `14`.

Assets in `v0.1.16` include `WaifuGallery-Setup-x64.exe`, `WaifuGallery-Portable-x64.exe`, `Waifu-Gallery-0.1.16-x86_64.AppImage`, `Waifu-Gallery-0.1.16-x86_64.flatpak`, and `app-release.apk`. The Linux packages include the GNU GPL license. Preserve the Android signing setup documented in `android/README.md`; never commit signing keys or credentials.

This compatibility release is the one-time bridge for clients that still query `/releases/latest`. New clients use the platform feed instead. The current public feed points Windows to `windows-v0.1.21`, Linux to `linux-v0.1.18`, and Android to `android-v0.1.19`.

## Version files

Update all version declarations for the target platform:

- **Windows:** `windows/waifu_gallery/__init__.py`, `windows/pyproject.toml`, and the default `AppVersion` in `windows/setup_windows.iss`. `windows/build_release.ps1` reads the app version and builds the setup and portable EXEs.
- **Linux:** `linux/waifu_gallery/__init__.py` and `linux/pyproject.toml`. `linux/release.sh` uses the project version to name both packages.
- **Android:** `android/app/build.gradle.kts` (`versionName` and a strictly increasing `versionCode`).

Do not bump versions for unaffected platforms during a platform update. Keep the user-facing version numeric; platform identity belongs in the manifest key and release tag, not in strings like `win-0.1.13`. A compatibility release is the exception: it is a coordinated legacy package, and its numeric tag must match Android's APK `versionName` because old Android clients compare those values directly.

## Release a platform update

Use this procedure for normal updates. Build and publish only the platform that changed.

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
8. Keep the legacy compatibility release `v0.1.16` selected as GitHub Latest so a platform-only release does not redirect old clients to a release missing their assets. After publishing, verify `/releases/latest`; if GitHub selected the new platform tag, restore the compatibility target with:

   ```bash
   gh release edit v0.1.16 --latest --repo calestinfisalia/WaifuGallery
   ```

The manifest update is a separate commit after the release exists by design: otherwise clients could see a new version before GitHub has the release asset and checksum.

## Compatibility updates for old clients

Older clients use GitHub's global `/releases/latest` endpoint and do not read `updates.json`. The compatibility release `v0.1.16` is the bridge that upgrades them to clients using the platform feed. Keep this release marked Latest while it is the supported legacy bridge; platform-only releases must not replace it as the global Latest release.

Do not create a compatibility release for every platform fix. Normal fixes use only the platform tag and manifest entry. Create a newer compatibility release only when intentionally providing another update to old clients. That is a coordinated exception and must include all assets required by the legacy clients being supported:

- Windows installer and portable EXE.
- Linux AppImage and Flatpak.
- Android `app-release.apk`.

Legacy Android compares the compatibility tag's numeric version to the APK `versionName`; those must match, and `versionCode` must increase. This means a new compatibility release may require coordinated package/version updates even when the underlying fix affects only one platform. If that coordination is not intended, publish only the platform-specific update and leave the existing compatibility release selected as Latest. Do not change `updates.json` for compatibility-only maintenance unless a platform's actual package version has changed.

When a compatibility release is published, verify its full asset set and make it GitHub Latest. Then verify `/releases/latest` returns that compatibility tag. The new clients continue using their platform-specific manifest entries and exact release tags independently.

## Validation checklist

- Windows: from `windows`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`.
- Linux: from `linux`, run `python -m unittest discover -s tests -v`, `python -m compileall -q waifu_gallery`, and `git diff --check`; build packages on Linux, not on Windows.
- Android: run `.\gradlew.bat :app:testDebugUnitTest :app:assembleRelease`; inspect the release APK's `versionName` and `versionCode`.
- Confirm the source version, built package version, manifest version, tag, asset name, and digest all refer to the same platform release.
- New update path: verify the public manifest selects the changed platform's tag and leaves the other platform entries unchanged.
- Legacy compatibility path: verify `/releases/latest` resolves to the compatibility tag and that release contains the assets required by legacy clients.
- Never overwrite another platform's manifest entry to make the global version numbers match.
