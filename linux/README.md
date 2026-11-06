# Waifu Gallery for Linux

This directory is a separate Linux porting workspace. It starts as a copy of the Windows Python/PySide6 implementation so Linux-specific changes can be developed here without changing `windows/`.

## Status

This is a porting baseline, not a Linux release yet. The UI currently uses a frameless window and contains Windows-specific native resize handling. Review and adapt that code for Linux window managers and Wayland/X11 before relying on the UI. The Linux build and runtime have not been verified yet.

The source uses PySide6, requests, Qt SVG assets, and per-user `QSettings`. Network access is needed for image providers and optional DNS over HTTPS.

## Run from source

Use Python 3.10 or newer and make sure your distribution has Python venv support installed. From this directory, run:

```bash
bash ./run.sh
```

The script creates `.venv`, installs `requirements.txt`, and starts the application. It does not create an AppImage or Flatpak.

## Packaging

AppImage and Flatpak packaging are not configured yet. Build and verify the application on Linux first, then add Linux-specific packaging metadata and test image saving, window resizing, DNS over HTTPS, and provider access.

## License and credits

Waifu Gallery application source is licensed under the repository [MIT License](../LICENSE). Toolbar SVGs retain their Lucide/Feather notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. Artwork and provider images retain their creators' rights.
