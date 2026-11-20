# Windows 0.1.27, Linux 0.1.20, and Android 0.1.32 Release Notes

All three platform releases are published. The platform update feed points to each release independently; GitHub Latest remains the compatibility release `v0.1.16` for older clients.

## Version comparison

| Platform | Previous published version | Current release | Package |
| --- | --- | --- | --- |
| Windows | [0.1.26](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.26) | [0.1.27](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.27) | Setup and portable x64 applications |
| Linux | [0.1.19](https://github.com/calestinfisalia/WaifuGallery/releases/tag/linux-v0.1.19) | [0.1.20](https://github.com/calestinfisalia/WaifuGallery/releases/tag/linux-v0.1.20) | x86_64 AppImage and Flatpak |
| Android | [0.1.31](https://github.com/calestinfisalia/WaifuGallery/releases/tag/android-v0.1.31) | [0.1.32](https://github.com/calestinfisalia/WaifuGallery/releases/tag/android-v0.1.32) | APK (`versionCode` 30) |

## What's included

- Android backup export now offers the same section selection as desktop. Import keeps the existing file selection flow, then asks whether to add unique favorites or replace the full favorites list. Duplicate favorite images are skipped when adding, across platforms.
- Desktop Favorites filters now group media type and time ordering consistently. Settings keyword-cache and search-history pages have clearer category and time information.
- Search autocomplete, suggestion cache, and history behavior are included in the published platform builds, with cache data kept separate from image thumbnails.
- Windows/Linux desktop refinements include PNG-only filtering using the provider's `transparent_png` tag where relevant, smoother media presentation, and updated fullscreen video controls.

## Release assets

- [Windows 0.1.27](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.27)
- [Linux 0.1.20](https://github.com/calestinfisalia/WaifuGallery/releases/tag/linux-v0.1.20)
- [Android 0.1.32](https://github.com/calestinfisalia/WaifuGallery/releases/tag/android-v0.1.32)

The public update manifest is [`updates.json`](https://github.com/calestinfisalia/WaifuGallery/blob/main/updates.json). It is updated only after the corresponding release and required assets have been published and verified.

## Windows 0.1.28 release notes

Windows `0.1.28` is the next Windows-only release after `0.1.27`. Linux `0.1.20` and Android `0.1.32` are unchanged.

### Fixes and improvements

- Media Info tag browsing now uses a lightweight list model instead of creating a button widget for every tag, reducing layout work while resizing the dialog. Selecting a tag still searches for similar media.
- The main search field keeps its smooth resize animation, and the Home button now sits beside Back in the navigation group.
- Image view and fullscreen image zoom can magnify up to 20×. Load the original-resolution image first to inspect its full detail.
- Favorites and dialog presentation refinements from the stable desktop UI are retained.

### Release assets

- `WaifuGallery-Setup-x64.exe`
- `WaifuGallery-Portable-x64.exe`
- `LICENSE-GPL-3.0.txt`

The `windows-v0.1.28` release and Windows update-feed entry are published separately after the Windows packages are built and verified.
