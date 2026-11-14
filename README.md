# Waifu Gallery

![Waifu Gallery repository banner](waifugallery-repo-benner.png)

Waifu Gallery is an independent media browsing application with separate Windows, Linux, and Android implementations.

## Projects

- [Windows](windows/README.md) — Python and PySide6 desktop application (source version 0.1.15).
- [Linux](linux/README.md) — Python and PySide6 desktop port (source version 0.1.15), sharing provider, media, and backup features; platform runtime and packaging still need Linux verification.
- [Android](android/README.md) — Kotlin and Jetpack Compose mobile application (source version 0.1.15).

The desktop and Android applications provide random browsing, tag search, provider and rating filters, media viewing, media information, and downloads. Windows and Android include PIN-protected Favorites and parental content controls. Feature availability and platform requirements are documented in each project README.

## Platform-specific updates

Windows, Linux, and Android versions advance independently. Clients read their own version and release tag from [`updates.json`](updates.json), then fetch assets and GitHub-provided SHA-256 digests from that exact release tag. Keep the manifest entries at the latest published release for each platform; update only the affected platform after its GitHub release has been published.

Platform release tags use `windows-vX.Y.Z`, `linux-vX.Y.Z`, and `android-vX.Y.Z`. Android also increments `versionCode` for every APK. When migrating existing installations from the old shared `releases/latest` checker, publish one compatibility release containing all three platform packages before switching to platform-only releases; old clients cannot read the manifest.

See [RELEASE_UPDATE.md](RELEASE_UPDATE.md) for the agent-ready build, publish, manifest-update, migration, and validation procedure.

## Version 0.1.15

- **License:** new Windows, Linux, and Android source builds use GNU GPL version 3 or later. Linux 0.1.12 binaries already published under this release retain their original MIT license; build Linux 0.1.15 separately.
- **Favorites:** bulk downloads ask for confirmation before queuing selected media on Windows, Linux, and Android.
- See the platform READMEs and [RELEASE_UPDATE.md](RELEASE_UPDATE.md) for release assets and license transition details.

## Version 0.1.12

- **Windows:** refined Settings scrollbars; Windows Setup and portable x64 release builds.
- **Linux:** published x86_64 AppImage and Flatpak packages with Flatpak runtime compatibility and legacy-profile data migration.
- **Android:** SFW Auto random retries once after provider errors; download cards are more compact and active downloads can be cancelled.
- See the platform READMEs for release-specific details.

## Version 0.1.11

- **Fixes:** improved the desktop video player, fixed desktop and Android Settings UI issues, and corrected the ambient-mode toggle.
- **New features:** added Safety & Privacy on Windows and Android, including parental content controls and a Favorites lock; added more Windows themes; and enabled selecting backup sections.
- **Downloads:** history retains saved file paths across restarts.
- See the platform READMEs for release-specific details and Linux verification status.

## Encrypted user data backups

Windows, Linux, and Android provide **Settings → Backup & Restore**. Android Settings opens full-screen with separate category pages. Windows export lets you choose Favorites, Provider logins, Theme, and Settings before creating the encrypted `.wgbak` file. Linux export and Android export include the data supported by those platforms; Android does not use desktop themes. Download history and locations, safety PINs/policies, and window state are excluded.

The shared version 2 format records which sections are included and uses PBKDF2-HMAC-SHA256 (600,000 iterations) and AES-256-GCM; version 1 backups remain importable. Choose a passphrase of at least 8 characters and keep it safe; there is no recovery option. Import validates and decrypts the entire file before writing anything, and leaves unselected sections unchanged. Unsupported desktop themes are reported during confirmation and left unchanged; Android does not apply themes. **Merge** adds missing favorites and keeps credentials already configured on the device; **Replace** replaces included favorites and provider credentials. Included portable settings are imported with either option. The local download location is retained.

This encrypts the exported file only. Provider credentials remain stored using each platform's existing local settings storage, so protect access to your device as usual.
Windows and Linux use app-styled dialogs and an in-app file browser for backup passphrases and file selection; Android uses its system document picker.

## Desktop UI behavior and bug reports

The Windows and Linux desktop apps share the same UI behavior: search cards show media without titles and scale small provider previews to fill their tiles; changing search pages clears old results while loading; the toolbar download action stays hidden on Search until a media item is opened; zoom hides scrollbars but retains drag-to-pan; Search, Favorites, and Media Info use thin capsule scrollbars; and video buffering uses a bare spinner with gray controls/progress. Provider notices use gray capsules without a purple outline. The footer shows image/video counts on Search results and provider, media rating, and resolution for a loaded image in Random or a Search/Favorites detail; it clears while loading or outside those views. Media Info includes provider and rating. Favorites stays open while browsing its images, and the Back button is hidden in favorite-media details. Download history uses compact unboxed rows with newest downloads at the top, progress/status, a cancel action for active transfers, and a folder action for saved files; the application icon is retained. Random-image metadata and search-loading overlays, plus desktop Settings opening, have been fixed.

With provider set to **All**, desktop Search queries eligible providers concurrently and merges each provider's page into a deduplicated, round-robin page. Random chooses the provider with the first successful metadata response, then fetches its preview asynchronously; if that preview fails, Auto tries another provider. Selecting a specific provider keeps the request on that provider. **Settings → Providers → Status connection** checks each provider API and reports its HTTP response or a concise network/request error. In Favorites, failed thumbnails show a short cause with full details in a tooltip. Right-click a favorite for Download, Select image/Deselect image, or Remove from favorites; selecting media reveals icon actions for select all, bulk delete, and bulk download. Bulk downloads skip existing destination files and paths already in the download queue.

When reporting a regression, include the OS, whether the media is an image or video, the exact steps to reproduce it, and a screenshot or error text. For desktop issues, check both `windows/waifu_gallery/ui/` and `linux/waifu_gallery/ui/`: changes to shared behavior should remain in sync. Run `python -m compileall` on the changed Python files and `git diff --check` before handing off a fix.

## Community

- See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and pull request guidance.
- Report security issues according to [SECURITY.md](SECURITY.md).

## License and credits

Starting with this source revision, original Waifu Gallery application code is licensed under **GNU GPL version 3 or later**; see [LICENSE](LICENSE). Original desktop application code is copyright (C) 2026 Calestin Fisalia; original Android application code is copyright (C) 2026 Fisalia Cantarella. Android includes the same license at [android/LICENSE](android/LICENSE). Versions published before this license change remain available under the license included with those versions (MIT).

The general idea of browsing random waifu images was inspired by [NyarchLinux/WaifuDownloader](https://github.com/NyarchLinux/WaifuDownloader). Waifu Gallery is an independent implementation and does not include its GTK source or artwork.

Bundled toolbar SVGs in the Windows app are from [Lucide](https://github.com/lucide-icons/lucide); their ISC and Feather-derived MIT notices are in [LUCIDE-LICENSE.txt](windows/waifu_gallery/assets/LUCIDE-LICENSE.txt). The `waifugallery.png` artwork and images fetched from providers are not relicensed by the application license; their rights remain with their respective creators.

Third-party libraries retain their own licenses. Review their respective license notices when redistributing builds.

## Support

If you would like to support Waifu Gallery's development, you can do so on [Ko-fi](https://ko-fi.com/calestinfisalia).
