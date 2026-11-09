# Waifu Gallery for Android

Waifu Gallery for Android is a standalone Kotlin/Jetpack Compose implementation. It was written for this project with its own provider, search, and gallery code; the general idea of browsing random waifu images was inspired by [NyarchLinux/WaifuDownloader](https://github.com/NyarchLinux/WaifuDownloader). It does not include the original GTK source or launcher artwork. Its Android package ID is `com.fisalia.waifugallery`, so it installs separately from Waifu Downloader for Android.

The Android release version is aligned with the desktop projects (`0.1.7`). Android's `versionCode` is `5` and continues to increase independently for each Android update.

The custom Waifu Gallery launcher icon is not included yet. Android uses its generic fallback icon until the new artwork is added. Toolbar symbols use AndroidX Compose Material Icons from the declared dependency.

## Features

- Random image browsing, comma-separated and prefix tag search, provider selection, and SFW/NSFW rating filters. Search follows the selected default provider and applies image/video filters at the provider.
- Danbooru, yande.re, Gelbooru, and Rule34.xxx providers. Gelbooru and Rule34.xxx are enabled after signing in with each provider's user ID and API key.
- Paged search results, full-size image viewing, swipe navigation, and pinch-to-zoom.
- Image and video posts, with fullscreen video playback, circular buffering/loading indicators, dark translucent player controls, double-tap 5-second seeking, right-side volume swipes, left-side brightness swipes, and a preferred video resolution.
- Media info for the artist, provider, rating, source, post ID, and tags.
- Image source/artist information when provided by the upstream post.
- Download queue with progress and retry states.
- Local favorites, custom random-search terms, configurable male-only/gore/tag filters, and optional ambient blurred backgrounds.
- Optional DNS over HTTPS using Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard DNS, or a custom HTTPS resolver URL.
- Asynchronous GitHub release checks on app launch, with a dismissible in-app update prompt for newer stable versions.
- Save to `Pictures/Waifu Gallery` by default, or choose a persistent Android folder.
- Encrypted, cross-platform user data backup and restore, including favorites, provider credentials, and portable preferences.

Gelbooru and Rule34.xxx require your own user ID and API key. Enter them under Provider accounts in Preferences; credentials are stored on the device and are not included in the APK. Logging out immediately clears the saved credentials and updates the account state. The Media setting controls whether random browsing and search include images, videos, or both.
The preferred video resolution selects the largest listed provider rendition at or below the chosen height when available; otherwise playback uses the source URL.

## Encrypted user data backup

In Preferences, scroll to **Backup & Data** to export or import a `.wgbak` file through Android's document picker. Backups include favorites, Gelbooru/Rule34.xxx credentials, and portable preferences (provider, NSFW option, search terms and content filters, DoH settings, media filter, ambient mode, and video resolution). Android's selected download folder is device-specific and is not included.

The version 1 format is interoperable with Windows and Linux and uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM. Choose a passphrase of at least 8 characters; it cannot be recovered. Merge adds missing favorites and keeps provider credentials already present on the device; Replace uses the backup's favorites and credentials. Both import portable preferences. Credentials in SharedPreferences remain stored according to the existing local storage behavior; only the exported backup is encrypted.

## Android 0.1.7

- Added encrypted cross-platform export and import for favorites, provider credentials, and portable preferences.
- Release artifact: `app-release.apk`.

## Build and run

Open this folder in Android Studio and let Gradle sync. Use an Android 10 (API 29) or newer emulator/device, then run the `app` configuration. To build a debug APK from PowerShell:

```powershell
.\gradlew.bat :app:assembleDebug
```

The APK is written to `app\build\outputs\apk\debug\app-debug.apk`. This project does not include machine-specific `local.properties`; configure the Android SDK through `ANDROID_HOME` or create a local file on your own machine.

To build the release APK used for distribution:

```powershell
.\gradlew.bat :app:assembleRelease
```

The release APK is written to `app\build\outputs\apk\release\app-release.apk`.

## License and attribution

The Waifu Gallery Android application source is licensed under the MIT License; see [LICENSE](LICENSE). NyarchLinux/WaifuDownloader is acknowledged as inspiration for the general random-image feature, not as the source of this Kotlin/Compose implementation. Third-party libraries and Material icons retain their own licenses; consult their respective project notices.
