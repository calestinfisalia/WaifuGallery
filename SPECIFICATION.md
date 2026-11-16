# Waifu Gallery — Product Specification

## Purpose

Waifu Gallery is a local-first media browser for discovering, viewing, organizing, and downloading image and video posts from supported booru services. It has separate Windows, Linux, and Android applications. Each application is implemented for its platform; this repository does not contain a shared cross-platform runtime.

This document describes the product's current scope and constraints to help maintainers and AI agents evaluate changes. Platform-specific details and release state can change; confirm them in the relevant platform README and source before implementation.

## Goals

- Make random browsing and tag-based search available through a consistent set of supported providers.
- Let users inspect media and metadata, save favorites, and download media.
- Provide explicit content filters and optional in-app safety controls.
- Keep user preferences and favorites local, with an encrypted, interoperable backup path.
- Deliver independent updates for each platform without requiring unrelated platforms to release together.

## Users and operating assumptions

- Users browse public provider catalogs and may optionally enter credentials for providers that require them.
- Network access is required for provider queries, media retrieval, optional DNS-over-HTTPS, and release checks.
- Provider APIs, availability, metadata quality, rate limits, terms, and media hosting are outside the application's control.
- The application does not host or curate the media catalog.

## Functional requirements

### Browsing and providers

- Support random media requests and tag-based search, including paged results where supported.
- Support Danbooru and yande.re without user credentials; Gelbooru and Rule34.xxx require the user's own credentials for authenticated access.
- Allow choosing an individual provider or an automatic/all-provider mode, subject to the platform's implementation.
- Normalize provider results into a common post shape with identity, provider, media URLs, rating, tags, artists, source, dimensions, and video variants when available.
- Report provider failures to the user rather than presenting a failed request as an empty successful result.

### Media and organization

- Display image and video media, relevant post information, and available resolution/artist/source details.
- Support image viewing, zoom/pan, and platform-appropriate video controls.
- Allow users to favorite posts and download media. Retain the favorites and download history/location information supported by each platform.
- Support bulk favorite actions on desktop and Android where implemented.

### Filters and safety

- Support rating, media-type, built-in tag, and custom-tag filters where available.
- Optional filtering is based on provider-supplied tags and ratings. Missing or incorrect upstream metadata can cause content to pass a filter.
- Optional Favorites PIN and parental rating/allowed-tag controls are local, in-app restrictions. They are not operating-system parental controls and cannot prevent access to downloaded files or protect against changes made by someone with access to the user's account/device.
- AI-generated labels/filters are tag-based; they do not classify media independently.

### Settings, backup, and updates

- Persist platform preferences locally.
- Offer encrypted `.wgbak` export/import with cross-platform version 2 interoperability and version 1 import compatibility.
- Keep backup selection/import semantics platform-appropriate. Unsupported settings (for example desktop themes on Android) must be left unchanged and reported when applicable.
- Check the platform-specific update entry in `updates.json`; only offer a release that exists, is stable, contains the expected artifact, and has a verified checksum.
- Do not advance an update-feed entry before the matching platform release and asset are published and verified.

## Platform scope

| Platform | Implementation | Important platform-specific behavior |
| --- | --- | --- |
| Windows | Python, PySide6, Qt Multimedia | Windows-native file picker; QSettings persistence; portable and installer release channels. |
| Linux | Python, PySide6, Qt Multimedia | Separate Linux port and packaging; app-styled backup file browser; validate runtime behavior under the target desktop session and multimedia codecs. |
| Android | Kotlin, Jetpack Compose | Android document picker and storage APIs; app-private SharedPreferences; Android-specific settings/navigation and APK updates. |

The desktop applications have closely aligned behavior but are separate source trees (`windows/` and `linux/`). Android is a separate Kotlin application under `android/`. Do not assume a code change in one platform automatically changes the others.

## Non-functional requirements and constraints

- **Privacy:** favorites, settings, and provider credentials are stored locally. Provider credentials in local settings are not separately encrypted by Waifu Gallery. Only the exported backup file is encrypted.
- **Backup security:** version 2 uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM. Passphrases must have at least 8 characters and cannot be recovered. PINs, parental policy, and device-specific download folders are excluded.
- **Content safety:** rating/tag filters are best-effort metadata filters, not guarantees. Users must follow each provider's terms and applicable laws.
- **Reliability:** slow, unavailable, or rate-limited providers should produce an actionable error or a documented fallback, not a misleading success.
- **Release integrity:** platform versions are independent. Android `versionCode` must increase for each APK. GitHub-provided SHA-256 digests must match the published artifact.
- **Packaging:** current Android release configuration uses the debug signing configuration; establish production signing before treating APK distribution as a hardened release process. Linux package/runtime behavior requires validation on Linux.
- **Licensing:** consult repository and platform license/third-party notices before redistributing source or bundled assets. Media fetched from providers remains subject to its creators' rights and provider terms.

## Out of scope

- Hosting, mirroring, or redistributing provider media.
- A Waifu Gallery account, cloud sync, or remote user-data service.
- Guaranteed content classification, moderation, or OS-level parental supervision.
- Automatic migration of every platform-specific setting between platforms; only the documented backup sections are portable.
- Treating Windows, Linux, and Android as a single shared-code application.

## Acceptance checklist for product changes

Before calling a feature complete:

1. Confirm which platform(s) are in scope and inspect their existing behavior.
2. Preserve provider attribution, error visibility, and cancellation behavior.
3. Check how the feature interacts with filters, favorites, downloads, backup, and update flows where relevant.
4. Add focused tests for new behavior and run the narrowest applicable test/build commands.
5. Update the platform README and this specification when user-visible scope or limitations change.
6. For a release, verify the built artifact and digest before changing `updates.json`.
