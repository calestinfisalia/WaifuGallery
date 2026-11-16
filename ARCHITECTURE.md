# Waifu Gallery — Architecture

## System overview

Waifu Gallery is three platform applications in one repository. Windows and Linux are independent Python/PySide6 desktop applications with intentionally aligned behavior. Android is an independent Kotlin/Jetpack Compose application. There is no shared application binary, backend, or common UI module.

```text
Windows UI ──> Windows provider/data modules ──> booru APIs and media hosts
Linux UI   ──> Linux provider/data modules   ──> booru APIs and media hosts
Android UI ──> Android ViewModel/data modules ──> booru APIs and media hosts
      │                    │
      ├── local settings, favorites, downloads
      ├── encrypted .wgbak import/export
      └── updates.json ──> GitHub Releases/assets
```

The arrows describe logical dependencies, not a shared implementation. Each platform owns its network, persistence, UI, and packaging code.

## Platform components

### Windows and Linux desktop

- `windows/waifu_gallery/` and `linux/waifu_gallery/` contain separate implementations.
- `ui/main_window.py` is the main Qt window and coordinates the desktop views and dialogs.
- `ui/` also separates workers, viewers, video controls, favorites, downloads, preferences, themes, and backup/update presentation.
- `models.py` defines immutable `ImagePost` and `SearchPage` data structures.
- `providers.py` owns provider requests, response normalization, filtering, random/search selection, downloads, and video streaming support. Concurrent provider work uses Python thread-pool facilities.
- `settings.py`, `pin_security.py`, `data_backup.py`, and `doh.py` own local preferences, PIN verification, backup encoding, and optional DNS-over-HTTPS behavior.
- Desktop preferences and credentials use platform `QSettings`; the application does not separately encrypt those local values.
- Windows and Linux should remain behaviorally aligned, but platform-specific file dialogs, packaging, and runtime constraints are intentionally distinct. Compare both trees when changing shared desktop behavior.

### Android

- `android/app/src/main/java/com/fisalia/waifugallery/MainActivity.kt` contains Compose UI and screen composition.
- `MainViewModel.kt` holds screen state and coordinates user actions with data services using `StateFlow` and coroutines.
- `data/ImagePost.kt` defines post models and common post helpers.
- `data/BooruApi.kt` handles provider requests, response parsing, filtering, provider racing, and connection status checks using OkHttp and coroutines.
- `data/AppPreferences.kt` persists app settings, favorites, download state, and PIN verification data in app-private SharedPreferences.
- `data/UserDataBackup.kt` implements Android's backup model, validation, serialization, encryption, and decryption.
- `data/ReleaseUpdateChecker.kt` reads the Android update target, validates the GitHub release asset, downloads the APK, and verifies its SHA-256 before installation is offered.
- Compose, Android lifecycle, Coil, OkHttp, and Android document/storage APIs provide UI, image loading, networking, and platform integration.

## Main data flows

### Random and search

1. The UI collects user input and current preferences.
2. The platform's view/controller layer passes a request to its provider/data module.
3. The provider module requests one or more APIs, normalizes responses into the platform's post model, and applies supported tag/media/rating filters.
4. Results, provider errors, and paging state return to the UI for presentation.
5. Media bytes are loaded from provider media URLs; this is separate from the metadata/API request.

In automatic/all-provider modes, implementations may race providers, merge/deduplicate search results, or fall back after errors. These details differ by mode and platform; consult the provider implementation and platform README before changing the algorithm.

### Local state

- Preferences and favorites are local to the platform installation.
- Provider credentials are required only for credential-gated providers and remain in platform settings storage.
- Download history may store file paths/URIs; downloads themselves are saved to a user-selected/default destination.
- Safety PINs and parental policies are device-local and excluded from backup.
- There is no server-side user state or synchronization.

### Encrypted user-data backup

- The `.wgbak` envelope identifies the `waifu-gallery-user-data` format and its version.
- Version 2 records included sections (`favorites`, `providers`, `theme`, `settings`) and is the cross-platform format; version 1 remains importable.
- Version 2 derives a 256-bit key using PBKDF2-HMAC-SHA256 (600,000 iterations), then encrypts/authenticates the payload using AES-256-GCM. A random salt and nonce are stored with the encrypted envelope; versioned associated data binds the format version.
- Import validates/decrypts before applying selected data. Merge retains already configured provider credentials and adds missing favorites; Replace replaces included favorites/credentials. Portable settings are applied when included; unselected sections remain untouched.
- The exported file is encrypted. This does not encrypt credentials in local QSettings or SharedPreferences.
- Desktop export/import can select sections; platform UI and supported fields differ. Android does not use desktop themes. Download folders, safety PINs/policies, and window state are not portable.

When modifying the format, update all three codecs and cross-platform tests/fixtures together. Preserve backward compatibility unless a deliberate format migration is documented.

### Updates

1. The client reads its own platform entry from the repository's `updates.json`.
2. The entry points to a platform-specific GitHub release tag and version.
3. The client checks that release and expected asset exist and are stable.
4. The downloaded file is checked against its SHA-256 digest before installation/use.

Platform releases are independent (`windows-vX.Y.Z`, `linux-vX.Y.Z`, `android-vX.Y.Z`). The compatibility release path for old clients is separate. Never update a feed entry to a source version until the release artifact is published and verified. See `RELEASE_UPDATE.md` for release operations.

## External systems and trust boundaries

- Provider APIs and media hosts are untrusted external network services. They can fail, change schemas, rate-limit, or return incomplete metadata.
- Credentials are user-provided and must not be logged, placed in source, or included in release artifacts.
- Optional DoH changes DNS resolution for applicable provider requests; it does not make provider content or the network trustworthy.
- GitHub is used for update metadata and release assets. Validate tag, asset identity, trusted HTTPS URLs, stability, and digest before using an update.
- PIN locks and parental filtering protect only in-app flows and rely on local state/provider metadata. They are not security boundaries against a device owner or privileged process.
- The backup passphrase protects the exported file, not live local preferences or credentials.

## Change guidance

- For desktop UI behavior, inspect and generally update both `windows/waifu_gallery/ui/` and `linux/waifu_gallery/ui/`.
- For provider behavior, compare both desktop `providers.py` implementations and Android `data/BooruApi.kt`; avoid assuming their APIs or data models are interchangeable.
- Keep UI concerns out of provider parsing where existing module boundaries permit.
- Add focused tests alongside the platform implementation. Existing test suites are under `windows/tests/`, `linux/tests/`, and `android/app/src/test/`.
- Keep platform READMEs and `SPECIFICATION.md` aligned with user-visible behavior; keep `RELEASE_UPDATE.md` authoritative for release procedures.
