# Waifu Gallery for Linux

This directory is a separate Linux port of the Windows Python/PySide6 application. Shared provider, video, filter, DoH, favorites, media-info, and backup features are aligned with Windows 0.1.11 while Linux launch and packaging files remain separate.

## Status

The source includes the shared Windows 0.1.3–0.1.11 desktop features, including Rule34.xxx credentials, configurable media and tag filters, DoH resolvers, video playback, volume/mute, stream resolution selection, image/video counts, media information, automatically saved settings, immediate DoH disable, resizable application-styled dialogs, section-based encrypted cross-platform backups, persistent download paths, startup release checks, OLED Dark, and PIN-protected Safety & Privacy controls. Linux-specific runtime behavior still needs validation on a Linux desktop; check frameless-window resizing and multimedia codec availability under the target Wayland/X11 desktop before packaging a release.

The source uses PySide6, Qt Multimedia, requests, Qt SVG assets, and per-user `QSettings`. Network access is needed for image providers, optional DNS over HTTPS, and the background GitHub release check at startup.

## Features

- Random browsing, tag search, paged results, zoom/pan, favorites, downloads, and media information.
- Danbooru, yande.re, Gelbooru, and Rule34.xxx providers; Gelbooru and Rule34.xxx require provider credentials.
- SFW/NSFW rating, male-only and gore filters, custom blocked tags, image/video selection, and configurable video stream resolution.
- Video play/pause, seeking, volume/mute, buffering and playback-error feedback, and fullscreen controls.
- Resizable application-styled Settings, Favorites, and Downloads windows, plus an in-app release-notes prompt when an update is available.
- Downloads history, including saved file paths, is retained locally across app restarts and can be cleared from the Downloads window.
- Optional process-local DoH using Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard DNS, or a custom RFC 8484 endpoint.
- Safety & Privacy settings with an optional guardian PIN, maximum rating and allowed-tag policy, plus a separate PIN lock for Favorites. PINs are salted and hashed locally; failed attempts trigger a cooldown.
- Dark, Light, System, and OLED Dark themes.
- Encrypted, cross-platform user data export/import for favorites, provider credentials, and portable preferences.

The application filters content only by provider metadata and tags. Follow each provider's usage rules. Credentials are stored in the user's QSettings profile and are not encrypted by the application.
Parental controls and the Favorites lock are in-app restrictions, not tamper-proof OS controls. Rating and allowed-tag rules depend on provider metadata and cannot guarantee that every post is correctly labeled or protect files downloaded outside the app.

## Encrypted user data backup

Open Settings → Backup & Restore to export or import a `.wgbak` file. Linux exports include favorites, Gelbooru and Rule34.xxx credentials, the current theme, and portable preferences (provider/rating, search and content filters, custom search terms, DoH, media filter, ambient mode, and video resolution). Imports respect the sections selected in a backup and leave unselected data unchanged. Download folders, safety PINs/policies, and window state are excluded.

The version 2 format is shared with Windows and Android, records included sections, and uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM; version 1 backups remain importable. Choose a passphrase of at least 8 characters and keep it safe; it cannot be recovered. PINs and parental policy are device-local and excluded from backups. Merge adds missing included favorites and keeps existing included provider credentials; Replace replaces included favorites and provider credentials. Included portable preferences are imported with either option, while unselected sections and the current download folder are retained. Only the exported file is encrypted; credentials remain in the platform's existing QSettings storage.
Export and import use app-styled passphrase/confirmation dialogs and the application's own file browser instead of operating-system dialogs.

## UI behavior and troubleshooting

- Search result cards display the media only, with no post title. Changing pages clears the previous cards while the new page loads.
- Small provider thumbnails are scaled to the search card's preview area rather than left at their original tiny pixel size.
- Zoomed images remain pannable by dragging; scrollbars stay hidden. Search, Favorites, and Media Info use thin capsule scrollbars.
- Video buffering shows a centered spinner without a surrounding card. Player controls and progress use gray accents without the purple outline.
- Provider notices use a gray capsule background without the purple outline.
- The bottom media footer shows `16 images, 4 videos`-style counts on Search results; for a loaded image in Random or a Search/Favorites detail, it shows provider, rating, and preview/original resolution. Refreshing, replacing media, or leaving those views clears it. Media Info includes provider and rating. Favorites stays open while browsing its images.
- The Back button is hidden while viewing a favorite, and download history entries retain a readable row height.

For a reproducible bug report, include Linux distribution/desktop session (Wayland or X11), image or video, steps, and a screenshot or exact error. UI implementation lives in `waifu_gallery/ui/`; keep behavior aligned with `../windows/waifu_gallery/ui/`. Check changes with `python -m compileall waifu_gallery/ui` and `git diff --check`.

## Linux 0.1.11

### Fixes

- **Video player:** improved playback controls and buffering feedback.
- **Settings UI:** fixed desktop Settings layout and ambient-mode toggle behavior.

### New features

- **Safety & Privacy:** optional guardian PIN, parental maximum-rating and allowed-tag controls, plus a separate PIN lock for Favorites.
- **Themes:** OLED Dark is available alongside Dark, Light, and System.
- **Downloads:** history retains each saved file's path across restarts and can be cleared from the Downloads window.
- **Encrypted backups:** version 2 exports include section metadata and the current theme; imports can preserve unselected sections and still accept version 1 backups.
- Linux 0.1.11 release assets include AppImage and Flatpak bundles for x86_64. Verify playback and resizing on the target desktop; codec support depends on the system/runtime.

## Linux 0.1.8

- **Search fix:** editing a query now cancels a pending automatic open from previous results, preventing a media viewer from opening unexpectedly after a refresh.
- **Video thumbnail fix:** the play badge is attached to its thumbnail rather than shown as a separate popup.
- **Downloads:** added a cancel button for active downloads and clearer filename, status, and progress rows.
- **Favorites and media details:** search results show separate image/video totals; favorite details no longer show a redundant Back button, and image details include rating and resolution.
- **Encrypted backups:** added app-styled passphrase prompts and an in-app file browser for exporting and importing cross-platform backups.
- Linux runtime and packaging still require verification on a Linux desktop; no Linux release artifact is included.

## Linux 0.1.10

- **Settings:** renamed **Backup & Data** to **Backup & Restore**.
- Linux runtime and packaging still require verification on a Linux desktop; no Linux release artifact is included.

## Linux 0.1.9

- **Search:** prevent a full-text auto-selection when the search field receives focus, while keeping Ctrl+A available.
- **Media Type menu:** reduce the submenu width.
- The Linux updater still provides release notes only; Linux packages are not downloaded or installed automatically.
- Linux runtime and packaging still require verification on a Linux desktop; no Linux release artifact is included.

## Run from source

Use Python 3.10 or newer and make sure your distribution has Python venv support installed. From this directory, run:

```bash
bash ./run.sh
```

The script creates `.venv`, installs `requirements.txt`, and starts the application. It does not create an AppImage or Flatpak.

## Packaging

Build AppImage and Flatpak packages from a Linux environment. The build host
needs Python 3.10+, `python3-venv`, Flatpak, Flatpak Builder, `appimagetool`, and ImageMagick (`magick`).
Before the first Flatpak build, configure Flathub and install its 24.08 runtime
and SDK (use your distribution's package manager for the build tools):

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.freedesktop.Platform//24.08 org.freedesktop.Sdk//24.08
```

From this directory, run:

```bash
bash ./release.sh
```

The script reads the version from `pyproject.toml`, builds both packages, and
writes them to `~/releases/waifu-gallery/` by default, keeping the large
artifacts off a Windows-mounted repository drive. Its Python environment, pip
cache, and staging files use Linux's temporary directory and are removed after
the build. To save the release files somewhere else, set `RELEASE_OUTPUT_DIR`,
for example:

```bash
RELEASE_OUTPUT_DIR="$HOME/releases/waifu-gallery" bash ./release.sh
```

Flatpak requests network access for providers and home-directory access to
preserve the app's existing download and backup file access.

Build and verify the release on Linux before distribution, including image and
video playback, image saving, window resizing, DNS over HTTPS, and provider
access. For wider Linux compatibility, build on an older supported
distribution and test the resulting artifacts on the target distributions.

## License and credits

Waifu Gallery application source is licensed under the repository [MIT License](../LICENSE). Toolbar SVGs retain their Lucide/Feather notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. Artwork and provider images retain their creators' rights.
