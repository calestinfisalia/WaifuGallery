# Waifu Gallery for Linux

This directory is a separate Linux port of the Windows Python/PySide6 application. Shared provider, video, filter, DoH, favorites, and media-info features are aligned with Windows 0.1.5 while Linux launch and packaging files remain separate.

## Status

The source includes the Windows 0.1.3–0.1.5 application features, including Rule34.xxx credentials, configurable media and tag filters, DoH resolvers, video playback, volume/mute, stream resolution selection, image/video counts, media information, automatically saved settings, and immediate DoH disable. Linux-specific runtime behavior has not been validated on a Linux desktop yet; check frameless-window resizing and multimedia codec availability under the target Wayland/X11 desktop before packaging a release.

The source uses PySide6, Qt Multimedia, requests, Qt SVG assets, and per-user `QSettings`. Network access is needed for image providers and optional DNS over HTTPS.

## Features

- Random browsing, tag search, paged results, zoom/pan, favorites, downloads, and media information.
- Danbooru, yande.re, Gelbooru, and Rule34.xxx providers; Gelbooru and Rule34.xxx require provider credentials.
- SFW/NSFW rating, male-only and gore filters, custom blocked tags, image/video selection, and configurable video stream resolution.
- Video play/pause, seeking, volume/mute, buffering and playback-error feedback, and fullscreen controls.
- Optional process-local DoH using Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard DNS, or a custom RFC 8484 endpoint.

The application filters content only by provider metadata and tags. Follow each provider's usage rules. Credentials are stored in the user's QSettings profile and are not encrypted by the application.

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
