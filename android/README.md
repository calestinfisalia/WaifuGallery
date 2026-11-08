# Waifu Gallery for Android

Waifu Gallery for Android is a standalone Kotlin/Jetpack Compose implementation. It was written for this project with its own provider, search, and gallery code; the general idea of browsing random waifu images was inspired by [NyarchLinux/WaifuDownloader](https://github.com/NyarchLinux/WaifuDownloader). It does not include the original GTK source or launcher artwork. Its Android package ID is `com.fisalia.waifugallery`, so it installs separately from Waifu Downloader for Android.

The Android release version is aligned with the desktop projects (`0.1.4`). Android's `versionCode` is `2` and continues to increase independently for each Android update.

The custom Waifu Gallery launcher icon is not included yet. Android uses its generic fallback icon until the new artwork is added. Toolbar symbols use AndroidX Compose Material Icons from the declared dependency.

## Features

- Random image browsing, character/tag search, provider selection, and SFW/NSFW rating filters.
- Danbooru, yande.re, Gelbooru, and Rule34.xxx providers. Gelbooru and Rule34.xxx are enabled after signing in with each provider's user ID and API key.
- Paged search results, full-size image viewing, swipe navigation, and pinch-to-zoom.
- Image and video posts, with native playback controls, double-tap 5-second seeking, right-side volume swipes, left-side brightness swipes, and a preferred video resolution.
- Media info for the artist, provider, rating, source, post ID, and tags.
- Image source/artist information when provided by the upstream post.
- Download queue with progress and retry states.
- Local favorites, custom random-search terms, configurable male-only/gore/tag filters, and optional ambient blurred backgrounds.
- Optional DNS over HTTPS using Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard DNS, or a custom HTTPS resolver URL.
- Save to `Pictures/Waifu Gallery` by default, or choose a persistent Android folder.

Gelbooru and Rule34.xxx require your own user ID and API key. Enter them under Provider accounts in Preferences; credentials are stored on the device and are not included in the APK. The Media setting controls whether random browsing and search include images, videos, or both.
The preferred video resolution selects the largest listed provider rendition at or below the chosen height when available; otherwise playback uses the source URL.

## Build and run

Open this folder in Android Studio and let Gradle sync. Use an Android 10 (API 29) or newer emulator/device, then run the `app` configuration. To build a debug APK from PowerShell:

```powershell
.\gradlew.bat :app:assembleDebug
```

The APK is written to `app\build\outputs\apk\debug\app-debug.apk`. This project does not include machine-specific `local.properties`; configure the Android SDK through `ANDROID_HOME` or create a local file on your own machine.

## License and attribution

The Waifu Gallery Android application source is licensed under the MIT License; see [LICENSE](LICENSE). NyarchLinux/WaifuDownloader is acknowledged as inspiration for the general random-image feature, not as the source of this Kotlin/Compose implementation. Third-party libraries and Material icons retain their own licenses; consult their respective project notices.
