# Waifu Gallery for Linux

This directory is a separate Linux port of the Windows Python/PySide6 application. Shared provider, video, filter, DoH, favorites, and media-info features are aligned with Windows 0.1.7 while Linux launch and packaging files remain separate.

## Status

The source includes the Windows 0.1.3–0.1.7 application features, including Rule34.xxx credentials, configurable media and tag filters, DoH resolvers, video playback, volume/mute, stream resolution selection, image/video counts, media information, automatically saved settings, immediate DoH disable, resizable application-styled dialogs, encrypted cross-platform user-data backups, and startup release checks. Linux-specific runtime behavior has not been validated on a Linux desktop yet; check frameless-window resizing and multimedia codec availability under the target Wayland/X11 desktop before packaging a release.

The source uses PySide6, Qt Multimedia, requests, Qt SVG assets, and per-user `QSettings`. Network access is needed for image providers, optional DNS over HTTPS, and the background GitHub release check at startup.

## Features

- Random browsing, tag search, paged results, zoom/pan, favorites, downloads, and media information.
- Danbooru, yande.re, Gelbooru, and Rule34.xxx providers; Gelbooru and Rule34.xxx require provider credentials.
- SFW/NSFW rating, male-only and gore filters, custom blocked tags, image/video selection, and configurable video stream resolution.
- Video play/pause, seeking, volume/mute, buffering and playback-error feedback, and fullscreen controls.
- Resizable application-styled Settings, Favorites, and Downloads windows, plus an in-app release-notes prompt when an update is available.
- Optional process-local DoH using Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard DNS, or a custom RFC 8484 endpoint.
- Encrypted, cross-platform user data export/import for favorites, provider credentials, and portable preferences.

The application filters content only by provider metadata and tags. Follow each provider's usage rules. Credentials are stored in the user's QSettings profile and are not encrypted by the application.

## Encrypted user data backup

Open Settings → Backup & Data to export or import a `.wgbak` file. Backups include favorites, Gelbooru and Rule34.xxx credentials, and portable preferences (provider/rating, search and content filters, custom search terms, DoH, media filter, ambient mode, and video resolution). Download folders and window state are excluded.

The version 1 format is shared with Windows and Android and uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM. Choose a passphrase of at least 8 characters and keep it safe; it cannot be recovered. Merge adds missing favorites and keeps existing provider credentials; Replace uses the backup's favorites and credentials. Both import the backup's portable preferences, while the current download folder is retained. Only the exported file is encrypted; credentials remain in the platform's existing QSettings storage.

## UI behavior and troubleshooting

- Search result cards display the media only, with no post title. Changing pages clears the previous cards while the new page loads.
- Small provider thumbnails are scaled to the search card's preview area rather than left at their original tiny pixel size.
- Zoomed images remain pannable by dragging; scrollbars stay hidden. Search, Favorites, and Media Info use thin capsule scrollbars.
- Video buffering shows a centered spinner without a surrounding card. Player controls and progress use gray accents without the purple outline.
- Provider notices use a gray capsule background without the purple outline.
- The bottom media footer is blank except for a loaded image in Random or Search detail, where it shows provider, image type, and preview/original resolution. Refreshing, replacing media, or leaving those views clears it.

For a reproducible bug report, include Linux distribution/desktop session (Wayland or X11), image or video, steps, and a screenshot or exact error. UI implementation lives in `waifu_gallery/ui/`; keep behavior aligned with `../windows/waifu_gallery/ui/`. Check changes with `python -m compileall waifu_gallery/ui` and `git diff --check`.

## Run from source

Use Python 3.10 or newer and make sure your distribution has Python venv support installed. From this directory, run:

```bash
bash ./run.sh
```

The script creates `.venv`, installs `requirements.txt`, and starts the application. It does not create an AppImage or Flatpak.

## Packaging

AppImage and Flatpak packaging are not configured yet. Build and verify the application on Linux first, including image/video playback, image saving, window resizing, DNS over HTTPS, and provider access.

## License and credits

Waifu Gallery application source is licensed under the repository [MIT License](../LICENSE). Toolbar SVGs retain their Lucide/Feather notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. Artwork and provider images retain their creators' rights.
