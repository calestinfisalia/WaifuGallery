# Waifu Gallery

Waifu Gallery is a separate Python desktop project built around the product ideas developed for this repository: random image browsing, tag search, provider and rating filters, paged results, image zoom, credits, and downloads.

This folder has its own implementation and UI. It does not import the GTK/Android application modules or bundle their icons and mascot. It uses APIs from Danbooru and yande.re, with optional credential-based access to Gelbooru and Rule34.xxx. Provider posts and artwork remain the property of their respective creators and services; follow each provider's usage rules.

## Current features

- Windows desktop interface implemented with Python and PySide6.
- Random image browsing and tag search across Danbooru and yande.re; Gelbooru and Rule34.xxx can be enabled with your own API credentials. Selecting a provider searches only that provider. Choosing All combines available providers for search and tries providers in order for Random until an image loads.
- Rating choices for SFW, NSFW, or all results. NSFW results require enabling the option in Settings.
  - Optional tag-based gore filtering, male-only tag exclusion, and custom blocked tags configured in Settings. These filters depend on provider tags and cannot detect untagged content.
- Search gallery with 50 results per page and provider filters.
- Clicking a search result opens an in-window detail page; scroll over the image to zoom and drag to pan. Previous/next navigation works through search results and favorites. Credits appear in the app menu while a full image or video is open.
- Random and searched image/video posts, configurable in Settings. Video playback uses the built-in player and requires codecs supported by Qt Multimedia.
- Optional ambient background blur, which can be turned off in Settings.
- The toolbar download button saves the currently displayed media; the download list, progress, and clearable history are in the app menu.
- User-defined search terms used by Random.
- Settings are saved automatically as you change them; close Settings whenever you're done.
- Checks GitHub Releases in the background on launch and shows an in-app release-notes prompt when an update is available.
- Icon-only toolbar actions with bundled Lucide SVG assets and tooltips; the app/window icon uses `waifugallery.ico`.
- Optional process-local DNS over HTTPS, with Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard, and a custom RFC 8484 HTTPS endpoint.
- Encrypted, cross-platform user data export/import for favorites, provider credentials, and portable preferences.

The application only filters results using metadata provided by each image service. Always follow each provider's usage rules.

## Encrypted user data backup

Open Settings → Backup & Data to export or import a `.wgbak` file. Backups include favorites, Gelbooru and Rule34.xxx credentials, and portable preferences (provider/rating, search and content filters, custom search terms, DoH, media filter, ambient mode, and video resolution). Download folders and window state are not included.

The format is shared with Linux and Android and uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM. Set a passphrase of at least 8 characters; it cannot be recovered. Merge adds missing favorites and keeps existing provider credentials, while Replace uses the backup's favorites and credentials. Both import the backup's portable preferences, and the current download folder is retained. The export is encrypted; credentials in Windows QSettings remain subject to the existing local storage behavior.
Export and import use app-styled passphrase/confirmation dialogs and the application's own file browser instead of operating-system dialogs.

## UI behavior and troubleshooting

- Search result cards display the media only, with no post title. Changing pages clears the previous cards while the new page loads.
- Small provider thumbnails are scaled to the search card's preview area rather than left at their original tiny pixel size.
- Zoomed images remain pannable by dragging; scrollbars stay hidden. Search, Favorites, and Media Info use thin capsule scrollbars.
- Video buffering shows a centered spinner without a surrounding card. Player controls and progress use gray accents without the purple outline.
- The bottom media footer shows `16 images, 4 videos`-style counts on Search results; for a loaded image in Random or a Search/Favorites detail, it shows provider, rating, and preview/original resolution. Refreshing, replacing media, or leaving those views clears it. Media Info includes provider and rating. Favorites stays open while browsing its images; the Back button is hidden while viewing a favorite.
- Download history entries retain a readable row height and show the full status in a tooltip when it does not fit.
- Provider notices use a gray capsule background without the purple outline.

For a reproducible bug report, include Windows version, image or video, steps, and a screenshot or exact error. UI implementation lives in `waifu_gallery/ui/`; keep behavior aligned with `../linux/waifu_gallery/ui/`. Check changes with `python -m compileall waifu_gallery/ui` and `git diff --check`.

On Windows, the app records its own top-level window and small centered Qt widget/window show/hide events to help diagnose brief popups. The rotating log is at `%LOCALAPPDATA%\WaifuGallery\logs\window-events.log`; it includes the window class/title/bounds and for centered Qt popups their object name and parent chain. It does not record widget text, tooltips, or accessibility labels.

## Windows 0.1.8

- **Search fix:** editing a query now cancels a pending automatic open from the previous results, preventing a media viewer from opening unexpectedly after a refresh.
- **Video thumbnail fix:** the play badge is now attached to its thumbnail instead of appearing as a separate popup window.
- **Downloads:** added a cancel button for active downloads and clearer filename, status, and progress rows.
- **Favorites and media details:** search results show separate image/video totals; favorite details no longer show a redundant Back button, and image details include rating and resolution.
- **Encrypted backups:** added app-styled passphrase prompts and an in-app file browser for exporting and importing cross-platform backups.
- **Update and About:** added the Iro-chan mascot and refined the application-styled layouts.
- Added local Windows window-event diagnostics to help investigate transient popups.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.9

- **Update installer:** download the Windows Setup directly from the verified GitHub release, check its SHA-256 digest, then choose **Install now** to open it.
- **Search:** prevent a full-text auto-selection when the search field receives focus, while keeping Ctrl+A available.
- **Media Type menu:** reduce the submenu width.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.7

- Added encrypted, interoperable user-data export/import for favorites, provider credentials, and portable preferences.
- Refined Random image metadata and fixed the Search loading overlay and Settings opening errors.
- Updated provider notices to gray capsules without a purple outline.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.6

- Updated video slider track colors and handles; the player favorite icon is now shown only in fullscreen controls.
- Settings, Favorites, Downloads, and update notices use resizable application-styled windows instead of operating-system dialog chrome.
- Checks GitHub Releases on startup and shows the release notes when a newer stable version is available.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.5

- Settings changes are saved immediately; close Settings when finished. DoH can be toggled off immediately to restore system DNS.
- Fixed DoH shutdown and kept Windows feature changes synchronized with the Linux port.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.4

- Made Settings, Media Info, and Favorites non-modal so the main window and multiple dialogs can be used at the same time.
- Updated Favorites with application-styled window controls, image/video counts, a play indicator on video thumbnails, and removable favorites.
- Refined Settings controls for removing saved search terms and blocked tags, and removed distracting focus outlines.
- Settings now save automatically, and disabling DoH immediately restores the system DNS resolver.
- Added rounded provider error notices with fade-in and fade-out transitions.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.3

- Added video volume and mute controls, plus a preferred stream resolution setting. The player selects an available provider rendition at or below the chosen limit when possible.
- Improved video playback lifecycle, buffering/status updates, and fullscreen controls; video thumbnails and search results report image and video counts separately.
- Added centered load progress for media and full-resolution image retrieval. Display previews are decoded at a capped size for faster viewing; downloads keep the provider's original media.
- Updated media information and clickable tag search, along with refreshed player icons and release packaging for portable and setup builds.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Run on Windows

Install Python 3.10 or newer, then run:

```powershell
.\run.ps1
```

The first run creates `.venv`; each run installs or updates dependencies from `requirements.txt` before starting, so new project dependencies are picked up by existing environments.

To build the Windows folder distribution after the first run:

```powershell
.\build_windows.ps1
```

The output is `dist\Waifu Gallery\Waifu Gallery.exe`.

Build both release files after running the application at least once:

```powershell
.\build_release.ps1
```

The script creates `dist-release\WaifuGallery-Setup-x64.exe` and `dist-release\WaifuGallery-Portable-x64.exe`. It requires Inno Setup 7 for the installer.

The installer detects the existing Waifu Gallery installation and asks before updating it. It reuses the previous install folder and replaces the program files in place. Settings are stored in the current Windows user's registry and downloads are stored in the selected download folder, so an update keeps both. The portable executable does not install or replace the installed app.

## Provider credentials

Gelbooru is optional. Open Settings, enter your Gelbooru user ID and API key, and choose Gelbooru as the provider.

Rule34.xxx is also optional and requires its own API credentials. Sign in to Rule34.xxx, open [Account Options](https://rule34.xxx/index.php?page=account&s=options), and find the API Access Credentials section. If the API key is empty, enable the `Generate New Key?` option and save. Enter that user ID and API key in Waifu Gallery Settings, then choose Rule34.xxx. These are API credentials, not your account password.

DNS-over-HTTPS is optional. Open Settings → Network, enable or disable it at any time, and choose a built-in resolver or enter a custom HTTPS endpoint that supports RFC 8484 DNS wire format. Settings are saved automatically. Custom endpoint hostnames are bootstrapped through the system DNS resolver.

Credentials are stored for the current Windows user through `QSettings`; they are not encrypted by this application, so do not share or commit them. Rule34.xxx's [API terms](https://rule34.xxx/index.php?page=tos) prohibit ads and paywalls for apps using its API and ask clients not to hammer the service.

## Icon credits

Toolbar icons use SVG assets from [Lucide](https://github.com/lucide-icons/lucide), licensed under ISC. The application icon uses the project artwork `waifugallery.png`. The Lucide license notice is included in `waifu_gallery/assets/LUCIDE-LICENSE.txt`.

## License status

The Waifu Gallery application source code is licensed under the MIT License; see the repository [LICENSE](../LICENSE). Bundled Lucide SVGs retain their ISC and Feather-derived MIT notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. The application logo and provider images retain their respective creators' rights and are not relicensed by the application license.
