# Waifu Gallery for Android

Waifu Gallery for Android is a standalone Kotlin/Jetpack Compose implementation. It was written for this project with its own provider, search, and gallery code; the general idea of browsing random waifu images was inspired by [NyarchLinux/WaifuDownloader](https://github.com/NyarchLinux/WaifuDownloader). It does not include the original GTK source or launcher artwork. Its Android package ID is `com.fisalia.waifugallery`, so it installs separately from Waifu Downloader for Android.

Android's source and latest published version is `0.1.29` (`versionCode` `27`), under the Android-specific `android-v0.1.29` release tag. Android's version can advance independently from Windows and Linux.

The custom Waifu Gallery launcher icon is not included yet. Android uses its generic fallback icon until the new artwork is added. Toolbar symbols use AndroidX Compose Material Icons from the declared dependency.

## Features

- Random image browsing with pull-to-refresh, comma-separated and prefix tag search, provider selection, and SFW/NSFW rating filters. Auto mode falls back across providers and adds the video tag to random requests when video-only is selected. Search follows the selected default provider and applies image/video filters at the provider; changing content filters reloads search from page 1.
- Danbooru, yande.re, Gelbooru, and Rule34.xxx providers. Gelbooru and Rule34.xxx are enabled after signing in with each provider's user ID and API key. Settings → Providers can test each API connection and show its HTTP status or concise timeout, TLS, DNS, and connection error.
- Paged search results, full-size image viewing, swipe navigation, pinch-to-zoom, and animated double-tap focal zoom; double-tap again to reset and swipe while zoomed to pan. An optional Display setting automatically loads full-size images after their previews.
- All-provider Search runs eligible providers concurrently and merges deduplicated results in round-robin order. Random requests return the first eligible provider with results and cancel slower requests; if an Auto random request gets provider errors without a result, it retries once before reporting failure.
- Image and video posts, with fullscreen video playback, circular buffering/loading indicators, dark translucent player controls, double-tap 5-second seeking, right-side volume swipes, left-side brightness swipes, and a preferred video resolution.
- AI badge on tagged image and video posts, shown on full-size media at the upper left and on thumbnails at the lower right.
- Back navigation returns from Search details to results, from results to Random, and exits from Random.
- Fullscreen media hides the app chrome and system bars. Videos rotate to match their media orientation and restore the previous orientation when leaving fullscreen or switching to a photo; photos keep the device orientation. Fullscreen images extend edge-to-edge through display cutouts, use a plain black background, and retain fullscreen while swiping between posts; image overlays auto-hide after three seconds and reappear on tap.
- Media info for the artist, provider, rating, source, post ID, and tags.
- Image source/artist information when provided by the upstream post.
- Compact download cards show progress and retry states; cancel an active transfer with the X button. Use the Downloads screen's top-right menu to retry all failed downloads or clear finished history. Download history and each saved file's destination are retained locally across app restarts. Tap a completed item to open the saved media in an installed gallery or video app.
- Local favorites with image/video badges and separate totals; choose newest-first or oldest-first order, and optionally cache favorite thumbnails with controls to view cache usage or clear it. Long-press a favorite to download it, select it, or remove it. Selection mode supports select/deselect all, bulk removal with confirmation, and bulk download that skips duplicate or already queued/saved media. Search results and favorite video thumbnails show a play icon. Also includes custom random-search terms, configurable male-only/gore/AI-generated/tag filters, and optional ambient blurred backgrounds.
- Safety & Privacy controls with PIN-protected Favorites and parental maximum-rating/allowed-tag filters. PINs are salted and hashed locally and are excluded from encrypted user-data backups; parental filtering relies on provider metadata and is not OS-level supervision.
- Optional DNS over HTTPS using Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard DNS, or a custom HTTPS resolver URL.
- Asynchronous GitHub release checks on app launch, with a dismissible in-app update prompt for newer stable versions. You can also check manually in **Settings → Updates**. Update downloads show determinate or indeterminate progress and verify the APK checksum before installation. About and update dialogs feature the Iro-chan mascot.
- Save to `Pictures/Waifu Gallery` by default, or choose a persistent Android folder.
- Encrypted, cross-platform user data backup and restore, including favorites, provider credentials, and portable preferences.

Android Settings, Favorites, and Downloads open full-screen as separate app-styled screens. Settings has categories for Browsing, Providers, Network, Filters, Display, Downloads, Favorites, Safety & Privacy, Backup & Restore, Updates, and About. **Settings → Providers** opens a submenu with separate pages for the default provider, provider accounts, and connection status, following the Safety & Privacy navigation pattern. The **Safety & Privacy** category can require a PIN to enter Favorites and can restrict content by maximum rating and optional allowed tags; a guardian PIN protects the parental policy and protected settings. The **Filters** category controls image/video selection, default rating, built-in filters, and custom blocked tags, which can be added or removed individually. From search results, open Filters through the toolbar's three-dot menu to choose a provider and rating. Gelbooru and Rule34.xxx require your own user ID and API key; enter them under **Settings → Providers → Provider accounts**. Credentials are stored in app-private SharedPreferences, are not separately encrypted by Waifu Gallery, and are not included in the APK. Logging out immediately clears the saved credentials and updates the account state.
The preferred video resolution selects the largest listed provider rendition at or below the chosen height when available; otherwise playback uses the source URL.

## Encrypted user data backup

Open **Settings → Backup & Restore** to export or import a `.wgbak` file through Android's document picker. Android exports favorites, Gelbooru/Rule34.xxx credentials, and portable preferences (provider, NSFW option, search terms and content filters including the AI-generated filter, DoH settings, media filter, ambient mode, and video resolution). Android does not use desktop themes. Its selected download folder is device-specific and is not included.

The version 2 format is interoperable with Windows and Linux, records included sections, and uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM; version 1 backups remain importable. Choose a passphrase of at least 8 characters; it cannot be recovered. Android imports only the included sections and leaves unselected data unchanged. Merge adds missing included favorites and keeps provider credentials already present on the device; Replace replaces included favorites and provider credentials. Included portable preferences are imported with either option. Local credentials remain in app-private SharedPreferences and are not separately encrypted by Waifu Gallery; only the exported backup is encrypted.

## Android 0.1.29

- **Images:** add an optional auto-load full-resolution setting after the preview appears; manual mode remains available when disabled. Keep the preview visible and show a wrapping error if full-size loading fails.
- **Favorites:** add newest/oldest sorting and a configurable thumbnail cache with usage and clear controls.
- Android source version: `0.1.29`; `versionCode`: `27`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.29/app-release.apk).
- Update feed: `android-v0.1.29`.

## Android 0.1.28

- **Downloads:** add a top-right menu to retry all failed downloads or clear download history.
- **Search:** reduce the search field height to 44 dp.
- **Image zoom:** keep pinch zoom anchored to the gesture centroid to prevent horizontal images jumping while zooming.
- Android source version: `0.1.28`; `versionCode`: `26`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.28/app-release.apk).
- Update feed: `android-v0.1.28`.

## Android 0.1.27

- **Fullscreen images:** remove safe-area padding so zoomed photos can extend to the top edge and display cutout.
- **Search:** All-provider search now merges deduplicated results from eligible providers in round-robin order.
- Android source version: `0.1.27`; `versionCode`: `25`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.27/app-release.apk).
- Update feed: `android-v0.1.27`.

## Android 0.1.26

- **Random refresh:** forward drag gestures from the static image content to pull-to-refresh; refresh remains disabled in fullscreen.
- Android source version: `0.1.26`; `versionCode`: `24`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.26/app-release.apk).
- Update feed: `android-v0.1.26`.

## Android 0.1.25

- **Random refresh:** pull down on Random to load another image; the toolbar refresh icon is removed, and the current image remains visible while refreshing.
- **Fullscreen images:** extend edge-to-edge through display cutouts.
- Android source version: `0.1.25`; `versionCode`: `23`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.25/app-release.apk).
- Update feed: `android-v0.1.25`.

## Android 0.1.24

- **Fullscreen photos:** preserve the device orientation instead of rotating to match the photo.
- Android source version: `0.1.24`; `versionCode`: `22`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.24/app-release.apk).
- Update feed: `android-v0.1.24`.

## Android 0.1.23

- **Fullscreen images:** extend through display cutouts and retain fullscreen while swiping between posts.
- Android source version: `0.1.23`; `versionCode`: `21`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.23/app-release.apk).
- Update feed: `android-v0.1.23`.

## Android 0.1.22

- **Image viewing:** show the thumbnail while a larger preview loads; fullscreen controls and badges auto-hide after three seconds and reappear on tap.
- **Fullscreen presentation:** disable the ambient background for images and use a plain black background; animate double-tap zoom and reset.
- Android source version: `0.1.22`; `versionCode`: `20`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.22/app-release.apk).
- Update feed: `android-v0.1.22`.

## Android 0.1.21

- **AI labels:** place the badge on the upper-left of full-size tagged image/video media while leaving thumbnail badges on the lower-right.
- **Back navigation:** Search detail returns to results; Search results return to Random; Back from Random exits the app.
- Android source version: `0.1.21`; `versionCode`: `19`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.21/app-release.apk).
- Update feed: `android-v0.1.21`.

## Android 0.1.20

- **AI labels:** show an AI badge on image posts tagged `ai-generated` or `ai-assisted`.
- Android source version: `0.1.20`; `versionCode`: `18`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.20/app-release.apk).
- Update feed: `android-v0.1.20`.

## Android 0.1.19

- **Maintenance release:** rebuilds the Android APK at version `0.1.19`; no Android-specific behavior changed from 0.1.18.
- Android source version: `0.1.19`; `versionCode`: `17`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.19/app-release.apk).

## Android 0.1.18

- **Filters:** changing Hide AI-generated or removing custom blocked tags reloads Search from page 1; Random refreshes immediately.
- Android source version: `0.1.18`; `versionCode`: `16`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.18/app-release.apk).

## Android 0.1.17

- **Filters:** add an optional Hide AI-generated posts setting using provider tags such as `ai-generated` and `ai-assisted`. Untagged posts may remain visible.
- Android source version: `0.1.17`; `versionCode`: `15`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/android-v0.1.17/app-release.apk).

## Android 0.1.16

- **Preview quality:** prefer medium provider samples for sharper initial image display.
- **Settings and Downloads:** simplify the settings categories and grouped preferences; compact the download history.
- **Search:** support pull-to-refresh while retaining existing results during refresh.
- **About:** add a clickable project repository link.
- Android source version: `0.1.16`; `versionCode`: `14`.
- Release artifact: [`app-release.apk`](https://github.com/calestinfisalia/WaifuGallery/releases/download/v0.1.16/app-release.apk).
- The optional AI-generated post filter was added to the source after the `0.1.16` APK and is available in `0.1.17`.

## Android 0.1.15

- **License:** new Android builds from this source are distributed under GNU GPL version 3 or later; the full license text is included in the APK.
- **Favorites:** downloading selected favorites asks for confirmation before queuing.
- Android source version: `0.1.15`; `versionCode`: `13`.

## Android 0.1.14

- **Legacy updater compatibility:** the APK version matches the `v0.1.14` compatibility release tag so clients using the old global `releases/latest` flow do not repeatedly offer the same APK.
- Android source version: `0.1.14`; `versionCode`: `12`.

## Android 0.1.12

- **Updates:** the app now checks the Android-specific release entry in the repository update manifest, independent of Windows and Linux releases.
- **Favorites:** long-press actions, multi-select, bulk removal, and deduplicated bulk downloads are available.
- **Provider selection:** Auto search and random browsing use the first provider that returns results instead of waiting for every provider.
- **Provider diagnostics:** Settings → Providers can test all provider endpoints and report HTTP status or connection errors.
- **SFW random recovery:** Auto retries once when provider errors prevent a random result; HTML responses are identified separately from malformed API data.
- **Downloads:** download cards are more compact, and the X action cancels an active transfer without stopping the remaining queue.
- Android source version: `0.1.12`; `versionCode`: `11`.

## Android 0.1.11

### Fixes

- **Video player:** improved fullscreen playback controls and player behavior.
- **Settings UI:** fixed Android Settings layout and interaction issues.

### New features

- **Safety & Privacy:** added parental maximum-rating and allowed-tag controls, a guardian PIN, and a separate PIN lock for Favorites.
- **Downloads:** history retains saved file destinations across app restarts.
- **Encrypted backups:** version 2 files record included sections, allow selective import/export, and remain compatible with version 1 backups.
- Release artifact: `app-release.apk` (`versionCode` 9).

## Android 0.1.10

- **Video playback:** start playback as soon as the player is prepared, without requiring an extra play/pause interaction.
- **Image viewing:** keep focal zoom and pinch/pan movement within the displayed image bounds.
- **Random video fallback:** request the video tag and skip providers that do not support video-only results.
- **Player UI:** center the video and buffering indicator, and align the seekbar thumb with its track.
- **Gallery:** show play badges on video thumbnails and clarify separate image/video totals.
- **About and update dialogs:** add the mascot accent and align About text with desktop.
- **Settings:** rename **Backup & Data** to **Backup & Restore**.
- Release artifact: `app-release.apk` (`versionCode` 8).

## Android 0.1.9

- **Download and install updates:** download the APK from the GitHub release, verify its SHA-256 digest, and open Android's package installer after the user chooses **Install update**.
- Android requires the user to allow installs from this app (if not already allowed) and confirm the installation.
- Release artifact: `app-release.apk` (`versionCode` 7).

## Android 0.1.8

- **Fullscreen fix:** fullscreen media now rotates to match the media's orientation and restores the device's previous orientation when fullscreen closes.
- **Favorites:** video thumbnails have a visible play badge, and image/video totals are shown separately so video posts are easier to distinguish.
- Release artifact: `app-release.apk`.

## Android 0.1.7

- Added encrypted cross-platform export and import for favorites, provider credentials, and portable preferences.
- Release artifact: `app-release.apk`.

## Build and run

Open this folder in Android Studio and let Gradle sync. Use an Android 10 (API 29) or newer emulator/device, then run the `app` configuration. To build a debug APK from PowerShell:

```powershell
.\gradlew.bat :app:assembleDebug
```

The APK is written to `app\build\outputs\apk\debug\app-debug.apk`. This project does not include machine-specific `local.properties`; configure the Android SDK through `ANDROID_HOME` or create a local file on your own machine.

### Current APK signing

For now, the release build intentionally uses Gradle's local debug signing configuration; a dedicated release keystore has not been configured. Keep using the same local debug key for APK updates, because Android will not install an update signed with a different certificate. Do not commit the keystore or its credentials. Migrating to a securely stored release key is deferred.

To build the release APK used for distribution:

```powershell
.\gradlew.bat :app:assembleRelease
```

The release APK is written to `app\build\outputs\apk\release\app-release.apk`.

## License and attribution

Starting with this source revision, original Waifu Gallery Android application code is copyright (C) 2026 Calestin Fisalia and licensed under the GNU GPL version 3 or later; see [LICENSE](LICENSE). Android versions published before this license change remain under their included MIT license. NyarchLinux/WaifuDownloader is acknowledged as inspiration for the general random-image feature, not as the source of this Kotlin/Compose implementation. Third-party libraries and Material icons retain their own licenses; consult their respective project notices.
