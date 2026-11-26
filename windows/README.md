# Waifu Gallery

Waifu Gallery is a separate Python desktop project built around the product ideas developed for this repository: random image browsing, tag search, provider and rating filters, paged results, image zoom, credits, and downloads.

This folder has its own implementation and UI. It does not import the GTK/Android application modules or bundle their icons and mascot. It uses APIs from Danbooru and yande.re, with optional credential-based access to Gelbooru and Rule34.xxx. Provider posts and artwork remain the property of their respective creators and services; follow each provider's usage rules.

## Current features

- Windows desktop interface implemented with Python and PySide6.
- Random image browsing and tag search across Danbooru and yande.re; Gelbooru and Rule34.xxx can be enabled with your own API credentials. Selecting a provider keeps requests on that provider. Choosing All merges deduplicated results from eligible providers for each Search page; Random selects by the first successful metadata response and loads the preview asynchronously, trying another provider if that preview fails.
- Rating choices for SFW, NSFW, or all results. NSFW results require enabling the option in Settings.
    - Optional tag-based gore and AI-generated post filtering, male-only tag exclusion, and custom blocked tags configured in Settings. AI filtering uses provider tags such as `ai-generated` and `ai-assisted`; untagged content may remain visible.
- Search gallery with 50 results per page and provider filters. Changing content filters reloads the search from page 1.
- When the default rating is **Only NSFW**, Settings → Filters → Default rating lets you include Questionable and Explicit posts together, or select either rating alone. This level is saved with the other portable preferences.
- When the search field is not focused, **R** refreshes the active view and **Left/Right** navigate adjacent media in the detail viewer. Search keeps up to 10 recent queries locally (shown with a clock-arrow icon) and suggests only character and series tags from the selected provider (or eligible providers under All), marked with a search icon. Clicking or editing the search field shows recent queries. Suggestions appear from a persistent provider-and-prefix cache immediately while typing, then refresh in the background after a 300 ms debounce when older than 24 hours; cached suggestions remain available offline. A no-results typo suggestion is clickable and never rewrites the query automatically.
- Clicking a search result opens an in-window detail page; scroll over the image to zoom and drag to pan. Previous/next navigation works through search results and favorites. Credits appear in the app menu while a full image or video is open.
- Random and searched image/video posts, configurable in Settings and the main window's Media Type menu. Choose PNG Only to request PNG files; transparency depends on the individual file. Video playback uses the built-in player and requires codecs supported by Qt Multimedia.
- Display settings can automatically load the original-resolution image after showing its preview; the manual full-image button is hidden while this option is on and remains available when it is off.
- Optional ambient background blur, which can be turned off in Settings.
- The toolbar download button saves the currently displayed media; the Downloads history, including each saved file's path, remains available across app restarts. Failed downloads can be retried per file or together from the Downloads window's top-right menu, which also clears history.
- Settings → Providers → Status connection checks each provider API and displays its HTTP response or a concise timeout, connection, TLS, or request error.
- Favorites thumbnails that fail to load show a short reason, such as Timeout or Network error; the full failure detail is available in the tooltip.
- Favorites can be filtered by media type (all, images, videos, or transparent PNGs) and ordered newest-to-oldest or oldest-to-newest from the top-right filter button. Both selections persist. Favorite thumbnails are cached locally by default; toggle caching, view disk usage, or clear the cache under Settings → General → Image cache. Turning caching off stops disk reads and writes but keeps existing files until cleared.
- Settings content adapts to the window size, and long image-viewer error messages wrap instead of being clipped.
- Right-click a favorite for Download, Select image/Deselect image, or Remove from favorites. Selecting an image reveals icon actions for selecting all, deleting selected favorites, and downloading them. Clicking Select all again clears the selection and hides the actions. Bulk downloads use the configured folder and skip existing destination files or paths already queued.
- The Favorites image count is shown in the window footer. Downloading from Favorites queues the file without automatically opening Downloads.
- User-defined search terms used by Random.
- Settings are saved automatically as you change them; close Settings whenever you're done. Saved search terms, download folder, favorite image cache, keyword cache, and search history have separate pages under General; the default rating is under Filters.
- Display settings include Dark, Light, System, and OLED Dark themes with color previews, plus optional automatic full-resolution image loading.
- Checks GitHub Releases in the background on launch and shows an in-app release-notes prompt when an update is available. You can also check manually in Settings → Updates.
- Icon-only toolbar actions with bundled Lucide SVG assets and tooltips; the app/window icon uses `waifugallery.ico`.
- PIN entry, notices, and confirmations use the app's own dialogs; file pickers continue to use the Windows file manager.
- Optional process-local DNS over HTTPS, with Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard, and a custom RFC 8484 HTTPS endpoint.
- Encrypted, cross-platform user data export/import for favorites, provider credentials, and portable preferences.
- Safety & Privacy settings with an optional guardian PIN, maximum rating, and optional allowed-tag policy. A separate optional Favorites PIN protects opening the Favorites view.

The application only filters results using metadata provided by each image service. Always follow each provider's usage rules.
Parental controls and the Favorites lock are in-app restrictions, not tamper-proof OS controls; someone with access to the same Windows account can alter local application data. Tag and rating rules depend on provider metadata and are not a guarantee that every post is correctly labeled, and these controls cannot protect media already downloaded outside the app.

## Safety & Privacy

Open Settings → Safety & Privacy to set up or manage parental control and the separate Favorites lock. Use Set PIN or Change PIN to manage each PIN; PIN entry and verification use an in-app dialog. Enabling, disabling, changing, or removing a configured PIN requires that feature's PIN. PINs are stored as salted PBKDF2-HMAC-SHA256 hashes, not as plain text, and failed attempts trigger an increasing local cooldown. Allowed tags use OR matching: a post must contain at least one configured tag.

PINs and parental policy are device-local and are intentionally excluded from encrypted backups. Importing a backup does not replace or disable a parental policy already configured on this Windows installation. Removing a PIN disables its protection without deleting favorites; parental rating and tag settings are retained.

## Encrypted user data backup

Open Settings → Backup & Restore to export or import a `.wgbak` file. Before export, choose whether to include Favorites, Provider logins, Theme, and/or Settings. Settings include provider/rating and its NSFW rating level, search and content filters including the AI-generated filter, custom search terms, DoH, media filter, ambient mode, and video resolution. Parental control and Favorites lock PINs/policies, download folders, and window state are not included.

The version 2 format is shared with Linux and Android, records the included sections, and uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM. Version 1 backups remain importable. Set a passphrase of at least 8 characters; it cannot be recovered. Unselected sections remain unchanged when importing. Unsupported desktop themes are identified in the import summary and left unchanged. If favorites are included, choose **Add new** to keep existing favorites and add unique images, or **Replace all** to replace the favorites list. Existing provider credentials are kept; backup credentials fill accounts that are not configured yet. Included portable preferences are imported, and the current download folder is retained. The export is encrypted; credentials in Windows QSettings remain subject to the existing local storage behavior.
Export and import use the native Windows file picker to open or save backup files, with app-styled passphrase and confirmation dialogs.

## UI behavior and troubleshooting

- Search result cards display the media only, with no post title. Changing pages clears the previous cards while the new page loads.
- The toolbar download action is hidden on Search results until a media item is opened.
- Small provider thumbnails are scaled to the search card's preview area rather than left at their original tiny pixel size.
- Zoomed images remain pannable by dragging; scrollbars stay hidden. Search, Favorites, and Media Info use thin capsule scrollbars.
- Video buffering shows a centered spinner without a surrounding card. Compact player controls use the active theme's purple accent, a round seek knob, and a thin gray buffered segment.
- The bottom media footer shows `16 images, 4 videos`-style counts on Search results. For an image in Random or a Search/Favorites detail, both manual and automatic loading show `Load Full Image` with animated dots, followed by the full dimensions when complete. Before loading, manual mode shows only the preview dimensions; automatic mode shows `Load full size...` without full dimensions. Refreshing, replacing media, or leaving those views clears it. Media Info includes provider and rating. Favorites stays open while browsing its images; the Back button is hidden while viewing a favorite.
- Main, Favorites, Settings, Downloads, and other app windows follow the focused window in the stacking order.
- App windows remember their sizes and provide minimize controls. Resizing Favorites avoids rebuilding its tiles or repeatedly scanning thumbnails; the main image uses a fast preview during resizing and restores final scaling when resizing settles. Closing the main window also closes its open dialogs.
- Download history uses compact, unboxed rows with newest downloads at the top, progress/status, a cancel action for active transfers, and a folder action for saved files. The application icon is retained, and the full path remains available in the filename tooltip.
- Provider notices use a gray capsule background without the purple outline.
- The update dialog uses the full `assets/Iro-chan-update-pose.png` artwork in a clear right-side column; the release notes and download status stay readable beside/below it. Download percentage is a separate label beside a thin progress bar.

For a reproducible bug report, include Windows version, image or video, steps, and a screenshot or exact error. UI implementation lives in `waifu_gallery/ui/`; keep behavior aligned with `../linux/waifu_gallery/ui/`. Check changes with `python -m compileall waifu_gallery/ui` and `git diff --check`.

### Search suggestions: development handoff

- The search field is shared by Random and Search views. Suggestion generation must remain page-independent; `test_async_search_suggestions_open_popup_with_search_icon` in `tests/test_window_focus.py` covers the async result path while Random is active.
- `waifu_gallery/ui/main_window.py` owns the query debounce, local history, stale-request checks, and popup placement. Suggestions start after two characters and replace only the final comma-separated term. The popup matches the search field width, sits 6 px below it, and moves above it when there is not enough screen space below.
- `waifu_gallery/providers.py` implements `BooruCatalog.suggest_tags`. Suggestions are restricted to character (category 4) and series/copyright (category 3) tags. All uses eligible providers; Gelbooru and Rule34.xxx require configured credentials.
- `waifu_gallery/suggestion_cache.py` persists up to 256 provider/prefix entries in the app's QSettings store with a 24-hour freshness window. Stale values remain visible when the provider request fails or the app is offline. This data is separate from the favorite image cache and is not included in backup/export behavior.
- Recent queries are stored locally under `search/recent_queries` (maximum 10). Do not include them in backup/export behavior. The dropdown intentionally uses icons, not thumbnails: search icon for tag suggestions, the clock-arrow `waifu_gallery/assets/history.svg` for history, and `waifu_gallery/assets/x.svg` to remove an individual history entry.
- Typo correction remains a separate, explicit action after a search returns no results; selecting it applies the corrected tag. Suggestions and corrections must not silently rewrite or submit the user's query.
- Focused UI/provider coverage is in `tests/test_window_focus.py` and `tests/test_provider_media.py`. From `windows/`, run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`, `.\.venv\Scripts\python.exe -m compileall -q waifu_gallery`, and `git diff --check`. The 0.1.27 release suite passed 115 tests.

### Update dialog preview and window diagnostics

The update dialog uses `waifu_gallery/assets/Iro-chan-update-pose.png` and places release notes and download progress beside the artwork. Its minimum size is 800×540 and its default size is 1024×730. The preview below is a mock only; it cannot download or install an update.

To preview the dialog without downloading or installing anything, run this from PowerShell in `windows/` while the virtual environment is available:

```powershell
@'
import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from waifu_gallery.ui.main_window import MainWindow
from waifu_gallery.ui.updates import ReleaseNotesDialog

class PreviewMainWindow(MainWindow):
    def show_random(self):
        pass

    def _check_for_startup_update(self):
        pass

app = QApplication(sys.argv)
app.setApplicationName("Waifu Gallery - Update Preview")
app.setOrganizationName("Fisalia Cantarella")
app.setStyle(QStyleFactory.create("Fusion"))
owner = PreviewMainWindow()
owner.hide()
dialog = ReleaseNotesDialog(
    "v0.1.11 (preview)",
    "https://github.com/calestinfisalia/WaifuGallery/releases",
    "- Preview note one.\n- Preview note two.",
    "",
    "",
)
dialog.setStyleSheet(owner.styleSheet())
dialog.begin_download()
dialog.download_status.setText("Preview only - no update is being downloaded.")
dialog.set_download_progress(57)
dialog.download_button.setText("Preview only")
dialog.download_button.setEnabled(False)
dialog.finished.connect(app.quit)
dialog.show()
dialog.raise_()
dialog.activateWindow()
raise SystemExit(app.exec())
'@ | .\.venv\Scripts\python.exe -
```

The preview displays a mock 57% progress value; its disabled button cannot start a real download or installer.

On Windows, the app records its own top-level window and small centered Qt widget/window show/hide events to help diagnose brief popups. The rotating log is at `%LOCALAPPDATA%\WaifuGallery\logs\window-events.log`; it includes the window class/title/bounds and for centered Qt popups their object name and parent chain. It does not record widget text, tooltips, or accessibility labels.

## Windows 0.1.30 (release build prepared)

- **NSFW filter:** include Questionable (Q) and Explicit (E) posts together by default, or select either rating separately in Settings → Filters → Default rating.
- **Video player:** fix the volume slider control appearing as a square instead of a round knob.
- **Backup and restore:** preserve the selected NSFW rating level, while existing backups default to Questionable + Explicit.
- Windows source version: 0.1.30.
- Release assets are built locally and have not yet been published.

## Windows 0.1.27

- **Favorites:** group the sort choices under a dedicated Time submenu beside Media type.
- **Backup and restore:** show a clear import confirmation followed by a separate Add new/Replace all favorites choice; skip duplicate images using post IDs, checksums, and image URLs.
- **Settings:** keep Keyword cache and Search history cards compact instead of stretching their contents across the whole window.
- Windows source version: 0.1.27.
- **Release assets:** [Setup installer](https://github.com/calestinfisalia/WaifuGallery/releases/download/windows-v0.1.27/WaifuGallery-Setup-x64.exe) and [portable app](https://github.com/calestinfisalia/WaifuGallery/releases/download/windows-v0.1.27/WaifuGallery-Portable-x64.exe).

## Windows 0.1.16

- **Preview quality:** prefer medium provider samples for sharper initial image display.
- **Image loading:** the detail view stays blank with its loading indicator until the new preview is ready, instead of briefly showing a cached gallery thumbnail.
- **About:** reposition the mascot slightly toward the center and add a clickable project repository link.
- Windows source version: 0.1.16.
- Windows Setup and portable release builds are published in GitHub release [`v0.1.16`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/v0.1.16).

## Windows 0.1.17

- **Random browsing:** restore the Download action after leaving Search mode.
- Windows source version: 0.1.17.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.17`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.17).

## Windows 0.1.18

- **Filters:** add an optional Hide AI-generated posts setting using provider tags such as `ai-generated` and `ai-assisted`. Untagged posts may remain visible.
- Windows source version: 0.1.18.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.18`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.18).

## Windows 0.1.19

- **Filters:** changing Hide AI-generated refreshes Random immediately and reloads Search from page 1, so enabling or disabling the filter applies to the visible results.
- Windows source version: 0.1.19.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.19`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.19).

## Windows 0.1.20

- **AI labels:** identify AI-tagged image and video posts in Random, Search, and detail views.
- **Fullscreen:** image fullscreen uses the same dark background as video and restores the ambient background when exiting.
- **Media Info:** arrange tags in two columns.
- **Filter settings:** correctly persist Windows Registry string booleans so disabled filters remain disabled after reopening Settings.
- Windows source version: 0.1.20.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.20`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.20).

## Windows 0.1.21

- **Installer:** replace the default wizard illustration with the transparent Iro-chan tablet pose.
- Windows source version: 0.1.21.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.21`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.21).

## Windows 0.1.23

- **Updates:** publish the current Windows fixes as 0.1.23 so installations on 0.1.22 can detect and install this release.
- Windows source version: 0.1.23.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.23`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.23).

## Windows 0.1.24

- **Favorites:** add newest/oldest sorting and a configurable thumbnail cache; batch large gallery loads and keep resizing responsive. Show the Favorites count in its footer, and do not open Downloads automatically when queuing a favorite.
- **Image viewing:** add optional automatic full-resolution loading, preserve zoom and pan while loading, improve resize rendering, and keep the footer stable while status messages change.
- **Window behavior:** improve focus, minimize, taskbar previews, remembered sizes, and Windows snap support; close app dialogs and clean up download workers when the main window closes.
- **Ambient mode and navigation:** smooth the background fade and keep navigation controls lightweight while resizing.
- Windows source version: 0.1.24.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.24`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.24).

## Windows 0.1.25

- **Fullscreen photos:** restore the opaque capsule background on toolbar controls, including while ambient backgrounds update.
- Windows source version: 0.1.25.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.25`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.25).

## Windows 0.1.22

- **Installer:** replace the top-right CD image with the Peace Sign artwork and use the Neon Waves artwork in a dark blue wizard theme.
- **Downloads:** retry failed items individually or retry all failures from the Downloads menu; clear download history from the same menu.
- **Media Info:** allow resizing from every window edge without the Tags heading forcing an oversized minimum width.
- Windows source version: 0.1.22.
- Windows Setup and portable release builds are published in GitHub release [`windows-v0.1.22`](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.22).

## Windows 0.1.15

- **License:** new Windows builds from this source are distributed under GNU GPL version 3 or later; the installer presents the license and the portable build includes a copy.
- **Favorites:** downloading selected favorites asks for confirmation before queuing.
- Windows source version: 0.1.15.

## Windows 0.1.14

- **Search and providers:** All-provider search combines results across eligible providers; random browsing selects a fast response and can fall back if preview loading fails.
- **Favorites and downloads:** improved favorite loading, selection, and download controls.
- **Media and settings:** refined video controls, provider connection status, and settings navigation.
- The source version was 0.1.14.

## Windows 0.1.13

- **Updates:** the app now checks the Windows-specific release entry in the repository update manifest, so Linux and Android releases do not change the Windows update version.
- **Settings:** refined the capsule scrollbar styling.

## Windows 0.1.12

- **Settings:** refined the scrollbar styling.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.11

### Fixes

- **Video player:** improved fullscreen controls, themed seek/volume colors, and made buffered media easier to see.
- **Settings UI:** fixed desktop layout and interaction issues.
- **Ambient mode:** fixed the toggle and removed bright edges from the blurred background.
- **Provider notices:** fixed rounded capsule corners during fade effects.

### New features

- **Security & Privacy:** optional guardian PIN, parental maximum-rating and allowed-tag controls, plus a separate PIN lock for Favorites. PINs are salted and hashed locally; failed attempts trigger a cooldown.
- **Themes:** added OLED Dark alongside Dark, Light, and System, with color previews.
- **Encrypted backups:** version 2 `.wgbak` files let users select sections for export/import and retain compatibility with version 1 backups.
- **Downloads:** history retains each saved file's path across restarts.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.8

- **Search fix:** editing a query now cancels a pending automatic open from the previous results, preventing a media viewer from opening unexpectedly after a refresh.
- **Video thumbnail fix:** the play badge is now attached to its thumbnail instead of appearing as a separate popup window.
- **Downloads:** added a cancel button for active downloads and clearer filename, status, and progress rows.
- **Favorites and media details:** search results show separate image/video totals; favorite details no longer show a redundant Back button, and image details include rating and resolution.
- **Encrypted backups:** added app-styled passphrase prompts and an in-app file browser for exporting and importing cross-platform backups.
- **Update and About:** added the Iro-chan mascot and refined the application-styled layouts.
- Added local Windows window-event diagnostics to help investigate transient popups.
- Release artifacts: `WaifuGallery-Portable-x64.exe` and `WaifuGallery-Setup-x64.exe`.

## Windows 0.1.10

- **Settings:** renamed **Backup & Data** to **Backup & Restore**.
- **Update prompt:** corrected the mascot orientation.
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
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\run.ps1
```

The process-scoped policy change applies only to the current PowerShell session and is discarded when that session closes. It does not change the machine or user execution policy.

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

Starting with this source revision, original Waifu Gallery application code is licensed under the GNU GPL version 3 or later; see the repository [LICENSE](../LICENSE). Versions published before this license change remain under their included MIT license. Bundled Lucide SVGs retain their ISC and Feather-derived MIT notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. The application logo and provider images retain their respective creators' rights and are not relicensed by the application license.
